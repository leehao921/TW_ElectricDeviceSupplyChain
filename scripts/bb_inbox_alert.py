"""bb_inbox_alert.py — daily BB squeeze + breakout alert pushed to claude:inbox.

Wraps `smart_money_analysis.scan_squeeze()` for headless cron use. Tracks a
persistent consolidation counter so multi-day squeeze candidates are surfaced
even when no breakout has fired yet (the "蹲底 N 天" set).

Pipeline:
    1. Load institutional flow + OHLCV for as_of (DB-backed, ~5s)
    2. Run scan_squeeze → Buy / Avoid / Watch
    3. Read data/bb_consolidation_state.json, increment / drop counters
    4. Build compact Markdown message
    5. XADD to claude:inbox Redis stream

CLI:
    python scripts/bb_inbox_alert.py                      # today
    python scripts/bb_inbox_alert.py --as-of 2026-06-25
    python scripts/bb_inbox_alert.py --dry-run            # no XADD, print only
    python scripts/bb_inbox_alert.py --state-path /tmp/x.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Lazy imports — smart_money_analysis hits psycopg2 / pulls heavy deps. Wrap
# in a function so unit tests of pure helpers don't have to pay that cost.
DEFAULT_STATE_PATH = REPO_ROOT / "data" / "bb_consolidation_state.json"
PERSISTENT_MIN_DAYS = 5
INBOX_STREAM = "claude:inbox"


# ------------------------------------------------------------------ #
# Headless scan (calls into smart_money_analysis)
# ------------------------------------------------------------------ #
@dataclass
class BBScanResult:
    as_of: date
    universe_size: int
    buy_df: pd.DataFrame
    avoid_df: pd.DataFrame
    watch_labels: list[str]


def run_bb_scan_headless(as_of: date | None = None, source: str = "auto") -> BBScanResult:
    """Run BB scan against today (or as_of). Replicates the inline slice in
    smart_money_analysis.main() to stay headless — no markdown rendering, no
    DB connection held longer than needed.
    """
    import psycopg2  # noqa: WPS433

    import smart_money_analysis as sm  # noqa: WPS433

    conn = psycopg2.connect(**sm.DB_CONFIG)
    try:
        resolved_as_of = as_of or sm.latest_data_date(conn)
        dates = sm.trading_days(conn, resolved_as_of, 20)
        df = sm.load_flow(conn, min(dates), resolved_as_of)

        sector_map = sm.build_sector_map()
        theme_map = sm.build_theme_map()
        name_map = sm.build_ticker_name_map()
        universe = set(sector_map.keys()) | set().union(*theme_map.values())

        df, _ = sm.attach_twd(df, resolved_as_of, universe)

        last5_dates = dates[-5:] if len(dates) >= 5 else dates
        df_5d = df[df["date"].isin(last5_dates)].copy()
        per_ticker_5d = sm.per_ticker_window_sum(df_5d)
        per_ticker_5d_cov = per_ticker_5d[per_ticker_5d["symbol"].isin(universe)].copy()

        ohlcv_map = sm.fetch_ohlcv_universe(
            sorted(universe), conn, resolved_as_of, source=source,
        )
        buy_df, avoid_df, watch_labels = sm.scan_squeeze(
            ohlcv_map, sector_map, name_map, theme_map, per_ticker_5d_cov,
            as_of=resolved_as_of,
        )
        return BBScanResult(
            as_of=resolved_as_of,
            universe_size=len(ohlcv_map),
            buy_df=buy_df,
            avoid_df=avoid_df,
            watch_labels=watch_labels,
        )
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Persistence tracking (pure)
# ------------------------------------------------------------------ #
def update_consolidation_state(
    *,
    state_path: Path,
    as_of: date,
    today_tickers: dict[str, str],
) -> dict:
    """Update consecutive-day squeeze counter for each ticker.

    today_tickers: {ticker: status} where status ∈ {"buy", "avoid", "watch"}.
    Tickers not in today's dict are dropped from state (squeeze broken).
    Returns the new state dict and writes it to state_path.
    """
    prior: dict = {}
    if state_path.exists():
        try:
            prior = json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            prior = {}
    prior_days = prior.get("squeeze_days", {})

    as_of_str = as_of.isoformat()

    # Idempotency: if state was already advanced for this as_of (e.g. a watchdog
    # re-run after a partial/crashed first run), return it unchanged rather than
    # re-incrementing consecutive_days.
    if prior.get("as_of") == as_of_str:
        return prior
    new_days = {}
    for ticker, status in today_tickers.items():
        prev = prior_days.get(ticker)
        if prev:
            new_days[ticker] = {
                "first_seen": prev["first_seen"],
                "consecutive_days": int(prev["consecutive_days"]) + 1,
                "last_status": status,
            }
        else:
            new_days[ticker] = {
                "first_seen": as_of_str,
                "consecutive_days": 1,
                "last_status": status,
            }

    new_state = {"as_of": as_of_str, "squeeze_days": new_days}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(new_state, indent=2, ensure_ascii=False))
    return new_state


def extract_persistent_squeeze(
    state: dict,
    *,
    name_map: dict[str, str],
    min_days: int = PERSISTENT_MIN_DAYS,
) -> list[dict]:
    """Return [{ticker, name, consecutive_days, last_status}, ...] for tickers
    with consecutive_days >= min_days, sorted desc by consecutive_days."""
    rows = []
    for ticker, entry in state.get("squeeze_days", {}).items():
        days = int(entry.get("consecutive_days", 0))
        if days < min_days:
            continue
        rows.append({
            "ticker": ticker,
            "name": name_map.get(ticker, ""),
            "consecutive_days": days,
            "last_status": entry.get("last_status", ""),
        })
    rows.sort(key=lambda r: r["consecutive_days"], reverse=True)
    return rows


# ------------------------------------------------------------------ #
# Message rendering (pure)
# ------------------------------------------------------------------ #
def _row_to_buy_line(r: pd.Series) -> str:
    name = r.get("name", "")
    return (
        f"  • {r['ticker']} {name} "
        f"({r['ret_today_pct']:+.2f}%, vol×{r['vol_ratio']:.2f}, "
        f"5D 外資 {r['foreign_5d_oku']:+.2f}億)"
    )


def _row_to_avoid_line(r: pd.Series) -> str:
    name = r.get("name", "")
    reason = r.get("avoid_reason", "?")
    short_reason = reason.split(" (")[0] if " (" in reason else reason
    return (
        f"  • {r['ticker']} {name} "
        f"({short_reason}, {r['ret_today_pct']:+.2f}%)"
    )


def build_inbox_message(
    *,
    as_of: date,
    buy_df: pd.DataFrame,
    avoid_df: pd.DataFrame,
    watch_labels: Iterable[str],
    persistent: list[dict],
    universe_size: int,
) -> str:
    watch_list = list(watch_labels)
    header = (
        f"**BB Squeeze 巡檢 {as_of.isoformat()}** "
        f"({len(buy_df)} Buy / {len(avoid_df)} Avoid / "
        f"{len(watch_list)} Watch / {len(persistent)} 持續盤整≥{PERSISTENT_MIN_DAYS}d) "
        f"· universe={universe_size}"
    )
    lines = [header, ""]

    lines.append("🟢 Buy:")
    if buy_df.empty:
        lines.append("  *無 hits*")
    else:
        for _, r in buy_df.iterrows():
            lines.append(_row_to_buy_line(r))

    lines.append("")
    lines.append("🔴 Avoid:")
    if avoid_df.empty:
        lines.append("  *無 hits*")
    else:
        for _, r in avoid_df.iterrows():
            lines.append(_row_to_avoid_line(r))

    lines.append("")
    lines.append("🟡 Watch:")
    if not watch_list:
        lines.append("  *無 hits*")
    else:
        shown = watch_list[:10]
        suffix = f"  (+{len(watch_list) - 10} more)" if len(watch_list) > 10 else ""
        lines.append("  " + " / ".join(shown) + suffix)

    if persistent:
        lines.append("")
        lines.append(f"⏳ 持續盤整≥{PERSISTENT_MIN_DAYS}d:")
        for p in persistent[:8]:
            name = f" {p['name']}" if p.get("name") else ""
            lines.append(
                f"  • {p['ticker']}{name} ({p['consecutive_days']}d, {p['last_status']})"
            )

    lines.append("")
    lines.append(
        f"源: scripts/smart_money_analysis.py · 詳見 analysis/smart_money_{as_of.isoformat()}.md"
    )
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Inbox push
# ------------------------------------------------------------------ #
def push_to_inbox(
    *,
    message: str,
    as_of: date,
    tags: str = "bb-squeeze,daily",
    redis_host: str = "localhost",
    redis_port: int = 6379,
    report_path: str | None = None,
) -> bool:
    """XADD to claude:inbox via redis-cli. Returns True on success."""
    fields = [
        "ts", datetime.now().astimezone().isoformat(),
        "from", "bb_inbox_alert",
        "topic", "bb-squeeze",
        "tags", tags,
        "as_of", as_of.isoformat(),
        "msg", message,
    ]
    if report_path:
        fields += ["report_path", report_path]
    cmd = [
        "redis-cli", "-h", redis_host, "-p", str(redis_port),
        "XADD", INBOX_STREAM, "*", *fields,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        print(f"[error] XADD failed: {result.stderr.strip()}", file=sys.stderr)
        return False
    print(f"[info] XADD ok, id={result.stdout.strip()}", file=sys.stderr)
    return True


# ------------------------------------------------------------------ #
# Orchestrator
# ------------------------------------------------------------------ #
def collect_today_tickers(scan: BBScanResult) -> dict[str, str]:
    """Build {ticker: status} for all tickers in any of the 3 buckets."""
    out: dict[str, str] = {}
    if not scan.buy_df.empty:
        for tk in scan.buy_df["ticker"]:
            out[tk] = "buy"
    if not scan.avoid_df.empty:
        for tk in scan.avoid_df["ticker"]:
            out[tk] = "avoid"
    for label in scan.watch_labels:
        # watch_labels format: "{ticker} {name}" or "{ticker}.TW {name}"
        ticker = label.split(" ", 1)[0]
        if ticker not in out:
            out[ticker] = "watch"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print message, skip XADD + skip state file write")
    ap.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    ap.add_argument("--source", default="auto",
                    choices=["auto", "db", "yfinance"])
    args = ap.parse_args(argv)

    as_of = (
        datetime.strptime(args.as_of, "%Y-%m-%d").date()
        if args.as_of else date.today()
    )
    state_path = Path(args.state_path)

    print(f"[info] running BB scan as_of={as_of}", file=sys.stderr)
    scan = run_bb_scan_headless(as_of=as_of, source=args.source)
    print(
        f"[info] scan: {len(scan.buy_df)} Buy / {len(scan.avoid_df)} Avoid / "
        f"{len(scan.watch_labels)} Watch (universe {scan.universe_size})",
        file=sys.stderr,
    )

    today_tickers = collect_today_tickers(scan)

    if args.dry_run:
        # Don't mutate state file in dry-run, but compute what it would look like
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json") as tf:
            tmp_path = Path(tf.name)
            if state_path.exists():
                tmp_path.write_text(state_path.read_text())
            state = update_consolidation_state(
                state_path=tmp_path, as_of=scan.as_of, today_tickers=today_tickers,
            )
    else:
        state = update_consolidation_state(
            state_path=state_path, as_of=scan.as_of, today_tickers=today_tickers,
        )

    import smart_money_analysis as sm  # noqa: WPS433
    name_map = sm.build_ticker_name_map()
    persistent = extract_persistent_squeeze(state, name_map=name_map)

    message = build_inbox_message(
        as_of=scan.as_of,
        buy_df=scan.buy_df,
        avoid_df=scan.avoid_df,
        watch_labels=scan.watch_labels,
        persistent=persistent,
        universe_size=scan.universe_size,
    )

    # 量能 regime gate (alpha #4): 量縮/破線時前置警示,訊號本體保留
    # (followthrough 命中率可按 regime 分段)。gate 失敗不得阻擋 alert。
    try:
        from market_regime import banner, get_regime
        b = banner(get_regime())
        if b:
            message = b + "\n\n" + message
    except Exception as e:  # noqa: BLE001
        print(f"[warn] market_regime unavailable: {e}", file=sys.stderr)

    print("─" * 60)
    print(message)
    print("─" * 60)

    if args.dry_run:
        print("[info] dry-run: skipping XADD", file=sys.stderr)
        return 0

    # smart_money 報告非每日產出 (由 smart_money_analysis.py 手動產),存在才附
    report = REPO_ROOT / "analysis" / f"smart_money_{scan.as_of.isoformat()}.md"
    ok = push_to_inbox(
        message=message,
        as_of=scan.as_of,
        redis_host=os.environ.get("REDIS_HOST", "localhost"),
        redis_port=int(os.environ.get("REDIS_PORT", "6379")),
        report_path=str(report) if report.exists() else None,
    )
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
