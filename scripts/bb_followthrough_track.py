"""bb_followthrough_track.py — Daily BB Buy follow-through tracker.

For 5 trading days after each BB Buy breakout, tracks close/vol/flow
performance, classifies status (confirmed/watch/failed/波段/graduated),
and applies 5 pattern rules learned from historical BB Buy analysis
(analysis/bb_followthrough_verify_2026-07-03.md).

Fires 15:30 Mon-Fri via launchd `com.lulala.bb-followthrough`
(1hr after bb-squeeze @ 14:30 — OHLCV bar already landed).

CLI:
    python scripts/bb_followthrough_track.py                    # live push
    python scripts/bb_followthrough_track.py --dry-run          # print only
    python scripts/bb_followthrough_track.py --backfill 2026-07-01,2026-07-02,2026-07-03
    python scripts/bb_followthrough_track.py --state PATH
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date as dtdate, datetime
from pathlib import Path

import psycopg2

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "data" / "bb_followthrough_state.json"
HISTORY_PATH = REPO / "data" / "bb_followthrough_history.json"
THEMES_DIR = REPO / "themes"
BB_LOG = Path.home() / "Library" / "Logs" / "bb-squeeze.log"

DB_CONFIG = {
    "host": "localhost", "port": 5432, "dbname": "tmf_market_data",
    "user": "tmf", "password": os.environ.get("TMF_PG_PASSWORD", "tmf_dev_2026"),
    "connect_timeout": 5,
}

INBOX_STREAM = "claude:inbox"

STRONG_THEMES = {"MLCC", "5G", "NVIDIA", "AI_伺服器", "CoWoS", "EUV", "ABF_載板", "矽晶圓", "HBM"}
GRADUATE_DAYS = 5
FAIL_MIN_DAYS = 2
CONFIRM_RET_PCT = 5.0
FAIL_RET_PCT = -3.0

# Regex for parsing bb-squeeze.log Buy lines
BUY_LINE_RE = re.compile(
    r"•\s*(\d{4,5})\s+(\S.*?)\s*"
    r"\(([+-][\d.]+)%,\s*vol×([\d.]+),\s*5D 外資\s+([+-][\d.]+)億\)"
)
DATE_HEADER_RE = re.compile(r"BB Squeeze 巡檢\s*(\d{4}-\d{2}-\d{2})")


# ------------------------------------------------------------------ #
# BB log parsing (detailed — extracts vol× / 外資 / name / ret)
# ------------------------------------------------------------------ #
def parse_bb_log_detailed(as_of_date: str | None = None) -> dict[str, dict]:
    """Parse BB log block for as_of_date (or latest if None).
    Returns {ticker: {"name","ret_today_pct","vol_ratio","foreign_5d_oku"}}.
    Only Buy section — Avoid/Watch not extracted here.
    """
    if not BB_LOG.exists():
        return {}
    try:
        text = BB_LOG.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    blocks = text.split("────────────────────────────────────────────────────────────")
    target = None
    for block in blocks[::-1]:  # latest first
        m = DATE_HEADER_RE.search(block)
        if not m:
            continue
        block_date = m.group(1)
        if as_of_date is None or block_date == as_of_date:
            target = block
            break
    if target is None:
        return {}

    # Extract Buy section: between "🟢 Buy:" and "🔴 Avoid:" (or "🟡 Watch:")
    buy_start = target.find("🟢 Buy:")
    if buy_start < 0:
        return {}
    buy_end = target.find("🔴 Avoid:", buy_start)
    if buy_end < 0:
        buy_end = target.find("🟡 Watch:", buy_start)
    if buy_end < 0:
        buy_end = len(target)
    buy_section = target[buy_start:buy_end]

    result: dict[str, dict] = {}
    for m in BUY_LINE_RE.finditer(buy_section):
        ticker, name, ret, vol, foreign = m.group(1), m.group(2).strip(), m.group(3), m.group(4), m.group(5)
        result[ticker] = {
            "name": name,
            "ret_today_pct": float(ret),
            "vol_ratio": float(vol),
            "foreign_5d_oku": float(foreign),
        }
    return result


# ------------------------------------------------------------------ #
# Theme mapping (from themes/*.md)
# ------------------------------------------------------------------ #
_THEME_CACHE: dict[str, list[str]] | None = None
_TICKER_BOLD_RE = re.compile(r"\*\*(\d{4,5})\s")


def load_theme_map() -> dict[str, list[str]]:
    global _THEME_CACHE
    if _THEME_CACHE is not None:
        return _THEME_CACHE
    result: dict[str, list[str]] = {}
    if not THEMES_DIR.exists():
        _THEME_CACHE = result
        return result
    for th_md in THEMES_DIR.glob("*.md"):
        theme = th_md.stem
        if theme.lower() == "readme":
            continue
        try:
            text = th_md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in _TICKER_BOLD_RE.finditer(text):
            t = m.group(1)
            result.setdefault(t, []).append(theme)
    _THEME_CACHE = result
    return result


def get_themes(ticker: str) -> list[str]:
    return load_theme_map().get(ticker, [])


# ------------------------------------------------------------------ #
# DB queries
# ------------------------------------------------------------------ #
def fetch_daily_snapshot(conn, ticker: str, as_of: str) -> dict | None:
    """Fetch close+volume for ticker on as_of date."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT close, volume FROM stock_daily_ohlcv
             WHERE symbol=%s AND ts::date=%s
             LIMIT 1
        """, (ticker, as_of))
        r = cur.fetchone()
        if not r:
            return None
        close, vol = float(r[0]), int(r[1] or 0)

        # 60D avg vol (excluding today) for vol_ratio
        cur.execute("""
            SELECT AVG(volume) FROM stock_daily_ohlcv
             WHERE symbol=%s AND ts::date < %s
               AND ts::date >= (%s::date - INTERVAL '80 days')
        """, (ticker, as_of, as_of))
        va = float(cur.fetchone()[0] or 0)
        vol_ratio = vol / va if va else 0.0

        # 1D foreign flow (as_of only)
        cur.execute("""
            SELECT foreign_net, close_price FROM institutional_stock
             WHERE symbol=%s AND date=%s
        """, (ticker, as_of))
        fr = cur.fetchone()
        if fr:
            fn, cp = fr
            f_1d = float(fn or 0) * float(cp or close) / 1e8
        else:
            f_1d = 0.0

        return {
            "close": close, "volume": vol, "vol_ratio": vol_ratio,
            "foreign_1d_oku": f_1d,
        }


def fetch_20d_foreign(conn, ticker: str, as_of: str) -> float:
    """20D 外資 累計 in 億 TWD (as_of inclusive, backward 20 trading days)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT date FROM institutional_stock
             WHERE date <= %s AND symbol=%s
             ORDER BY date DESC LIMIT 20
        """, (as_of, ticker))
        dates = [r[0] for r in cur.fetchall()]
        if not dates:
            return 0.0
        cur.execute("""
            SELECT SUM(foreign_net), SUM(foreign_net * NULLIF(close_price, 0)::float)
              FROM institutional_stock
             WHERE symbol=%s AND date = ANY(%s)
        """, (ticker, dates))
        f_sh, f_twd = cur.fetchone()
        if not f_twd or f_twd == 0:
            # OTC fallback: use latest close
            cur.execute("SELECT close FROM stock_daily_ohlcv WHERE symbol=%s ORDER BY ts DESC LIMIT 1", (ticker,))
            px = float(cur.fetchone()[0]) if cur.rowcount else 0
            return float(f_sh or 0) * px / 1e8
        return float(f_twd) / 1e8


# ------------------------------------------------------------------ #
# State I/O
# ------------------------------------------------------------------ #
def load_state(path: Path) -> dict:
    if not path.exists():
        return {"last_updated": None, "tracked": {}}
    with open(path) as f:
        return json.load(f)


def save_state(state: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)


def load_disposition(path: Path | None = None) -> set[str]:
    """Load active disposition ticker set from data/disposition_current.json."""
    p = path or (REPO / "data" / "disposition_current.json")
    if not p.exists():
        return set()
    try:
        with open(p) as f:
            return set(json.load(f).get("active", {}).keys())
    except Exception:
        return set()


def append_history(entry: dict, path: Path) -> None:
    """Append a graduated/failed entry to lifetime history log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if path.exists():
        try:
            with open(path) as f:
                history = json.load(f)
        except Exception:
            history = []
    # Idempotency: drop any prior entry for the same (ticker, graduated_on) so a
    # watchdog re-run on the same day replaces rather than duplicates it.
    key = (entry.get("ticker"), entry.get("graduated_on"))
    if any(k is not None for k in key):
        history = [
            h for h in history
            if (h.get("ticker"), h.get("graduated_on")) != key
        ]
    history.append(entry)
    with open(path, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2, default=str)


# ------------------------------------------------------------------ #
# Verdict + Rules
# ------------------------------------------------------------------ #
def classify(entry: dict) -> str:
    days = entry.get("days_tracked", 0)
    cum = entry.get("cumret_pct", 0)
    max_ret = entry.get("max_cumret_pct", cum)
    if days == 0:
        return "just_added"
    if days == 1:
        if cum >= CONFIRM_RET_PCT: return "confirmed"
        if cum <= FAIL_RET_PCT: return "failed"
        return "watch"
    if days >= 2:
        if cum >= CONFIRM_RET_PCT: return "波段"
        if cum <= FAIL_RET_PCT: return "failed"
        if max_ret > CONFIRM_RET_PCT and cum < 0: return "failed"  # 假突破 (拉高拉回)
        return "watch"
    return "watch"


def apply_rules(entry: dict) -> list[str]:
    tags = []
    vol_at = entry.get("vol_ratio_at_entry", 0)
    f5_at = entry.get("foreign_5d_at_entry", 0)
    f20_at = entry.get("foreign_20d_at_entry", 0)
    themes = entry.get("themes", [])

    if vol_at > 10:
        tags.append("⚠️ Rule 1: Vol×10+ 出貨型態")
    if f20_at < -5 and f5_at > 5:
        tags.append("⚠️ Rule 2: pump 型態 (20D neg + 5D 大買)")
    matched = set(themes) & STRONG_THEMES
    if len(matched) >= 3:
        tags.append(f"🟢 Rule 3: 三重主題 ({','.join(sorted(matched))}) 拉回可買")
    elif len(matched) >= 2:
        tags.append(f"🟢 Rule 3: 雙主題 ({','.join(sorted(matched))})")
    if 2 <= vol_at <= 5 and 0.3 <= f5_at <= 5:
        tags.append("✅ Rule 4: ideal follow-through 條件")
    if entry.get("in_disposition"):
        tags.append("⚠️ Rule 5: 處置期間 (量能失真, BB signal 不可信)")
    return tags


# ------------------------------------------------------------------ #
# Core update logic
# ------------------------------------------------------------------ #
def add_new_breakouts(state: dict, today_buys: dict, as_of: str, conn, disposition_set: set[str] | None = None) -> list[str]:
    """Add today's new BB Buys (not already tracked) to state. Returns list of newly added tickers."""
    disposition_set = disposition_set or set()
    added = []
    for ticker, info in today_buys.items():
        if ticker in state["tracked"]:
            continue  # already tracking (e.g. re-BB Buy)
        f20 = fetch_20d_foreign(conn, ticker, as_of)
        entry = {
            "first_seen": as_of,
            "name": info["name"],
            "entry_close": None,  # will fill from OHLCV snapshot below
            "vol_ratio_at_entry": info["vol_ratio"],
            "foreign_5d_at_entry": info["foreign_5d_oku"],
            "foreign_20d_at_entry": f20,
            "themes": get_themes(ticker),
            "in_disposition": ticker in disposition_set,
            "days_tracked": 0,
            "daily_snapshots": [],
            "max_cumret_pct": 0.0,
            "min_cumret_pct": 0.0,
            "cumret_pct": 0.0,
            "status": "just_added",
            "rules_hit": [],
        }
        snap = fetch_daily_snapshot(conn, ticker, as_of)
        if snap is None:
            continue  # 資料尚未入庫
        entry["entry_close"] = snap["close"]
        entry["daily_snapshots"].append({
            "d": as_of, "close": snap["close"], "vol_ratio": snap["vol_ratio"],
            "foreign_1d": snap["foreign_1d_oku"], "cumret_pct": 0.0,
        })
        entry["rules_hit"] = apply_rules(entry)
        state["tracked"][ticker] = entry
        added.append(ticker)
    return added


def update_existing(state: dict, as_of: str, conn, disposition_set: set[str] | None = None) -> list[str]:
    """For each tracked ticker: append today's snapshot, recompute cumret + status.
    Returns list of tickers that had their status change today."""
    disposition_set = disposition_set or set()
    changed = []
    for ticker, entry in state["tracked"].items():
        # skip if already snapshotted for as_of
        if entry["daily_snapshots"] and entry["daily_snapshots"][-1]["d"] == as_of:
            continue
        snap = fetch_daily_snapshot(conn, ticker, as_of)
        if snap is None:
            continue  # OHLCV not yet ingested for as_of
        entry_close = entry["entry_close"]
        cumret = (snap["close"] - entry_close) / entry_close * 100 if entry_close else 0
        entry["daily_snapshots"].append({
            "d": as_of, "close": snap["close"], "vol_ratio": snap["vol_ratio"],
            "foreign_1d": snap["foreign_1d_oku"], "cumret_pct": round(cumret, 2),
        })
        entry["days_tracked"] += 1
        entry["cumret_pct"] = round(cumret, 2)
        entry["max_cumret_pct"] = round(max(entry.get("max_cumret_pct", 0), cumret), 2)
        entry["min_cumret_pct"] = round(min(entry.get("min_cumret_pct", 0), cumret), 2)
        # 若進入 disposition,更新 flag 並重跑 rules
        now_disp = ticker in disposition_set
        if now_disp != entry.get("in_disposition", False):
            entry["in_disposition"] = now_disp
            entry["rules_hit"] = apply_rules(entry)
        old_status = entry.get("status", "just_added")
        new_status = classify(entry)
        entry["status"] = new_status
        if new_status != old_status:
            changed.append(ticker)
    return changed


def graduate_stale(state: dict, as_of: str, dry_run: bool = False) -> list[str]:
    """Remove tickers hitting graduation conditions. Return graduated tickers.
    Appends to history only if not dry_run.
    """
    graduated = []
    keep = {}
    for ticker, entry in state["tracked"].items():
        days = entry.get("days_tracked", 0)
        status = entry.get("status", "just_added")
        if days >= GRADUATE_DAYS:
            entry["_reason_graduated"] = f"D+{days} 達 {GRADUATE_DAYS} 天觀察上限"
            graduated.append(ticker)
        elif status == "failed" and days >= FAIL_MIN_DAYS:
            entry["_reason_graduated"] = "Failed 確認"
            graduated.append(ticker)
        else:
            keep[ticker] = entry
    if graduated and not dry_run:
        for t in graduated:
            entry = state["tracked"][t]
            append_history({
                "ticker": t, "name": entry["name"], "first_seen": entry["first_seen"],
                "graduated_on": as_of, "final_status": entry.get("status"),
                "days_tracked": entry.get("days_tracked"),
                "cumret_pct": entry.get("cumret_pct"),
                "max_cumret_pct": entry.get("max_cumret_pct"),
                "min_cumret_pct": entry.get("min_cumret_pct"),
                "reason": entry.get("_reason_graduated"),
                "rules_hit": entry.get("rules_hit", []),
                "snapshots": entry.get("daily_snapshots"),
            }, HISTORY_PATH)
    state["tracked"] = keep
    return graduated


# ------------------------------------------------------------------ #
# Digest
# ------------------------------------------------------------------ #
def build_digest(state: dict, as_of: str, added: list[str], graduated: list[str]) -> str:
    now = datetime.now().strftime("%H:%M")
    lines = [f"# 📊 BB Follow-through 追蹤 {as_of} {now} (追蹤中 {len(state['tracked'])} 檔)"]

    by_status: dict[str, list[dict]] = {"just_added": [], "confirmed": [], "波段": [], "watch": [], "failed": []}
    for ticker, entry in state["tracked"].items():
        entry_view = dict(entry)
        entry_view["ticker"] = ticker
        by_status.setdefault(entry.get("status", "watch"), []).append(entry_view)

    def _fmt_line(e: dict, show_entry_snap: bool = False) -> str:
        last = e["daily_snapshots"][-1] if e["daily_snapshots"] else {}
        d = e.get("days_tracked", 0)
        cum = e.get("cumret_pct", 0)
        cs = last.get("close", 0)
        vr = last.get("vol_ratio", 0)
        f1 = last.get("foreign_1d", 0)
        rules = e.get("rules_hit", [])
        rule_tag = " · ".join(rules) if rules else ""
        if d == 0:  # just_added, show entry snap
            f5 = e.get("foreign_5d_at_entry", 0)
            return f"  • **{e['ticker']} {e['name']}** ${cs:.1f} vol×{vr:.2f} 5D外資{f5:+.2f}億 → {rule_tag or '一般'}"
        return (f"  • **{e['ticker']} {e['name']}** D+{d} 累計{cum:+.2f}% "
                f"vol×{vr:.2f} 外資{f1:+.2f}億 → {rule_tag or 'follow-through'}")

    if by_status["just_added"]:
        lines.append(f"\n## 🆕 Just Added (D+0, 今日新突破 {len(by_status['just_added'])} 檔)")
        for e in by_status["just_added"]:
            lines.append(_fmt_line(e, show_entry_snap=True))

    if by_status["confirmed"]:
        lines.append(f"\n## ✅ Confirmed (D+1+ 續強 {len(by_status['confirmed'])} 檔)")
        for e in by_status["confirmed"]:
            lines.append(_fmt_line(e))

    if by_status["波段"]:
        lines.append(f"\n## 📈 In波段 (D+2+ 累計 >+5% {len(by_status['波段'])} 檔)")
        for e in by_status["波段"]:
            lines.append(_fmt_line(e))

    if by_status["watch"]:
        lines.append(f"\n## 🟡 Watch (盤整或反轉觀察 {len(by_status['watch'])} 檔)")
        for e in by_status["watch"]:
            lines.append(_fmt_line(e))

    if by_status["failed"]:
        lines.append(f"\n## 🔴 Failed (假突破/收黑 {len(by_status['failed'])} 檔)")
        for e in by_status["failed"]:
            lines.append(_fmt_line(e))

    if graduated:
        lines.append(f"\n## 🎓 Graduated ({len(graduated)} 檔今日移出 state)")
        for t in graduated:
            lines.append(f"  • {t}")

    lines.append(f"\n源: scripts/bb_followthrough_track.py · state {STATE_PATH.name}")
    return "\n".join(lines)


def has_meaningful_events(state: dict, added: list[str], graduated: list[str]) -> bool:
    """Push to inbox only if there's something meaningful to report."""
    if added or graduated:
        return True
    for e in state["tracked"].values():
        if e.get("status") in ("confirmed", "波段", "failed"):
            return True
    return False


def push_inbox(msg: str) -> bool:
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.xadd(INBOX_STREAM, {"topic": "bb-followthrough", "msg": msg,
                              "tags": "twse,bb,followthrough,daily,alert"})
        return True
    except Exception as e:
        print(f"[err] inbox push failed: {e}", file=sys.stderr)
        return False


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #
def process_one_date(state: dict, as_of: str, conn, dry_run: bool, disposition_set: set[str] | None = None) -> tuple[list[str], list[str], str]:
    """Process a single date: parse today's log, add new, update existing, graduate stale.
    Returns (added, graduated, digest)."""
    disposition_set = disposition_set or set()
    today_buys = parse_bb_log_detailed(as_of_date=as_of)
    print(f"[info] {as_of} — BB log parsed: {len(today_buys)} Buy tickers", file=sys.stderr)

    # First update existing entries with as_of snapshot (before adding new, so new ones get D+0)
    changed = update_existing(state, as_of, conn, disposition_set=disposition_set)
    print(f"[info] {as_of} — status changed: {len(changed)}", file=sys.stderr)

    # Add new BB Buys not already tracked
    added = add_new_breakouts(state, today_buys, as_of, conn, disposition_set=disposition_set)
    print(f"[info] {as_of} — new breakouts added: {len(added)}", file=sys.stderr)

    # Graduate stale entries
    graduated = graduate_stale(state, as_of, dry_run=dry_run)
    print(f"[info] {as_of} — graduated: {len(graduated)}", file=sys.stderr)

    state["last_updated"] = as_of
    digest = build_digest(state, as_of, added, graduated)
    return added, graduated, digest


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true", help="Print only, no state write, no push")
    p.add_argument("--backfill", default="", help="Comma-separated dates YYYY-MM-DD to process sequentially")
    p.add_argument("--state", default=str(STATE_PATH))
    args = p.parse_args()

    state = load_state(Path(args.state))
    disposition_set = load_disposition()
    print(f"[info] disposition active: {len(disposition_set)} tickers loaded", file=sys.stderr)
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        if args.backfill:
            dates = [d.strip() for d in args.backfill.split(",") if d.strip()]
            digests = []
            all_added = []
            all_graduated = []
            for d in dates:
                added, grad, digest = process_one_date(state, d, conn, args.dry_run, disposition_set=disposition_set)
                all_added.extend(added)
                all_graduated.extend(grad)
                digests.append(digest)
            print("\n\n".join(digests))
            digest = digests[-1] if digests else ""
        else:
            as_of = dtdate.today().isoformat()
            added, grad, digest = process_one_date(state, as_of, conn, args.dry_run, disposition_set=disposition_set)
            print(digest)
    finally:
        conn.close()

    if args.dry_run:
        print("\n[dry-run] state NOT saved, inbox NOT pushed", file=sys.stderr)
        return 0

    save_state(state, Path(args.state))
    print(f"[ok] state saved to {args.state}", file=sys.stderr)

    if has_meaningful_events(state, [], []):
        push_inbox(digest)
        print("[ok] pushed to claude:inbox topic=bb-followthrough", file=sys.stderr)
    else:
        print("[skip] no meaningful events, not pushing", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
