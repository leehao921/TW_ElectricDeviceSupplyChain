"""Lean-forward event-driven factor extraction.

Implements rule #3 of the Jay (Two Sigma) 3-rule SOP from epic
https://github.com/leehao921/secret/issues/13.

Standard risk models (Barra, Northfield) are backward-looking — they only see
the factor *after* it's been priced for months. For emergent narratives (TPU
supply chain, Trump tariff, Mag-7 spillover, 外資 capitulation), the cleanest
read on "what's the new risk" is the **event-day cross-section**: when the
narrative re-priced everything, who moved together?

This script:

1. Reads `analysis/event_calendar.yaml` for canonical event dates.
2. For each event, fetches daily Close from yfinance for top-30 electronics
   tickers across `[E-1, E, E+1, E+2]`.
3. Computes cumulative event-window return: `(Close[E+1] - Close[E-1]) / Close[E-1]`,
   falling back to `Close[E+2]` if `E+1` is non-trading.
4. Standardizes the cross-section (z-score across tickers within each event).
5. Persists the top-15 long + top-15 short loadings to
   `emergent_factor_baskets` (the table from `ingestion/migrations/002_emergent_factors.sql`).
6. For `tpu_rally_peak` (2026-04-24), also writes a brief commentary to
   `analysis/reports/event_factor_tpu_rally_peak.md`.

Usage:
    # Single event:
    python3 analysis/event_factor_extractor.py --event tpu_rally_peak
    # All events from the calendar:
    python3 analysis/event_factor_extractor.py --all
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

import asyncpg
import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[1]
CALENDAR_PATH = REPO_ROOT / "analysis" / "event_calendar.yaml"
REPORTS_DIR = REPO_ROOT / "analysis" / "reports"
DB_DSN = "postgresql://knowledge:knowledge@localhost:5433/tw_electronics"

# Universe = 20 tickers from ingestion/snapshots/tpu.py:_ROWS plus 9 more
# market-cap leaders. Deduplicated. Marketplace mapping decides .TW vs .TWO
# yfinance suffix.
_TPU_TICKERS = [
    "2330", "2303", "3711", "2449", "3037", "8046", "3189", "2383", "6213", "2313",
    "6269", "6274", "3289", "3587", "6191", "3443", "3661", "3035", "6533", "2454",
]
_EXTRA_TICKERS = ["2317", "2412", "2308", "2002", "1303", "1301", "2603", "2882", "2881"]
_TPEX_TICKERS = {"6274", "3289", "3587", "6533"}  # OTC; need yfinance ".TWO" suffix
TICKERS = list(dict.fromkeys(_TPU_TICKERS + _EXTRA_TICKERS))

TOP_N = 15  # top-N long + top-N short per event


def load_calendar() -> list[dict]:
    """Tiny YAML parser — calendar is simple `name`/`date`/`narrative` pairs."""
    text = CALENDAR_PATH.read_text(encoding="utf-8")
    events: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "events:":
            continue
        if stripped.startswith("- "):
            if current is not None:
                events.append(current)
            current = {}
            stripped = stripped[2:]
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if current is None:
            continue
        current[key] = value
    if current is not None:
        events.append(current)
    for ev in events:
        if isinstance(ev.get("date"), str):
            ev["date"] = datetime.fromisoformat(ev["date"]).date()
    return events


def yfinance_symbol(t: str) -> str:
    """Return the yfinance ticker. TPEX (OTC) names need `.TWO`, TWSE use `.TW`."""
    return f"{t}.TWO" if t in _TPEX_TICKERS else f"{t}.TW"


def fetch_event_window(event_date: date, tickers: list[str]) -> pd.DataFrame:
    start = (event_date - timedelta(days=5)).isoformat()
    end = (event_date + timedelta(days=10)).isoformat()
    syms = [yfinance_symbol(t) for t in tickers]
    df = yf.download(syms, start=start, end=end, auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"].copy()
    else:
        close = df[["Close"]].rename(columns={"Close": syms[0]})
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    rename_map = {yfinance_symbol(t): t for t in tickers}
    close = close.rename(columns=rename_map)
    return close


def event_window_returns(close: pd.DataFrame, event_date: date) -> pd.Series:
    """Cumulative return from D-1 close to D+1 close (or D+2 fallback)."""
    target = pd.Timestamp(event_date)
    available = close.index
    pre_dates = available[available < target]
    post_dates = available[available > target]
    if len(pre_dates) == 0 or len(post_dates) == 0:
        return pd.Series(dtype=float)
    d_pre = pre_dates[-1]
    d_post = post_dates[0]
    if len(post_dates) >= 2 and (d_post - target).days < 1:
        d_post = post_dates[1]
    return (close.loc[d_post] / close.loc[d_pre] - 1.0).dropna()


def standardize(returns: pd.Series) -> pd.Series:
    if len(returns) < 2:
        return returns
    mean = returns.mean()
    std = returns.std(ddof=0)
    return (returns - mean) / std if std > 0 else returns - mean


async def upsert_basket(conn: asyncpg.Connection, event: dict, loadings: pd.Series) -> int:
    longs = loadings.sort_values(ascending=False).head(TOP_N)
    shorts = loadings.sort_values(ascending=True).head(TOP_N)
    rows: list[tuple] = []
    for rank, (ticker, val) in enumerate(longs.items(), start=1):
        rows.append((event["name"], event["date"], ticker, float(val), rank, "long"))
    for rank, (ticker, val) in enumerate(shorts.items(), start=1):
        rows.append((event["name"], event["date"], ticker, float(val), rank, "short"))
    await conn.execute(
        "DELETE FROM emergent_factor_baskets WHERE event_name = $1", event["name"]
    )
    await conn.executemany(
        """
        INSERT INTO emergent_factor_baskets
          (event_name, event_date, ticker, loading, rank, side)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (event_name, ticker) DO UPDATE SET
          loading = EXCLUDED.loading, rank = EXCLUDED.rank, side = EXCLUDED.side,
          extracted_at = now()
        """,
        rows,
    )
    return len(rows)


def write_tpu_commentary(event: dict, loadings: pd.Series) -> Path:
    longs = loadings.sort_values(ascending=False).head(TOP_N)
    shorts = loadings.sort_values(ascending=True).head(TOP_N)
    lines = [
        f"# Event Factor — {event['name']} ({event['date']})",
        "",
        f"**Narrative:** {event.get('narrative', '(none)')}",
        f"**Universe:** {len(TICKERS)} TW electronics tickers",
        "",
        "## Top long loadings (basket the event lifted)",
        "",
        "| Rank | Ticker | z-loading |",
        "|---:|:--|---:|",
    ]
    for r, (t, v) in enumerate(longs.items(), start=1):
        lines.append(f"| {r} | {t} | {v:+.3f} |")
    lines += [
        "",
        "## Top short loadings (basket the event hurt)",
        "",
        "| Rank | Ticker | z-loading |",
        "|---:|:--|---:|",
    ]
    for r, (t, v) in enumerate(shorts.items(), start=1):
        lines.append(f"| {r} | {t} | {v:+.3f} |")
    lines += [
        "",
        "_Loadings = (event-window return) z-scored across the cross-section. "
        "Generated by `analysis/event_factor_extractor.py`._",
    ]
    out_path = REPORTS_DIR / f"event_factor_{event['name']}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


async def process_event(event: dict, conn: asyncpg.Connection) -> int:
    print(f"  → fetching {event['name']} ({event['date']}) …", file=sys.stderr)
    close = fetch_event_window(event["date"], TICKERS)
    returns = event_window_returns(close, event["date"])
    if returns.empty:
        print(f"    skipped — no data around {event['date']}", file=sys.stderr)
        return 0
    loadings = standardize(returns)
    n = await upsert_basket(conn, event, loadings)
    print(f"    upserted {n} rows", file=sys.stderr)
    if event["name"] == "tpu_rally_peak":
        out = write_tpu_commentary(event, loadings)
        print(f"    commentary → {out}", file=sys.stderr)
    return n


async def amain(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--event", help="Single event name to extract")
    p.add_argument("--all", action="store_true", help="Process every event in the calendar")
    args = p.parse_args(argv)

    if not args.event and not args.all:
        p.error("specify --event NAME or --all")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    events = load_calendar()
    if args.event:
        events = [ev for ev in events if ev.get("name") == args.event]
        if not events:
            print(f"event '{args.event}' not found in {CALENDAR_PATH}", file=sys.stderr)
            return 1

    conn = await asyncpg.connect(DB_DSN)
    total = 0
    try:
        for ev in events:
            total += await process_event(ev, conn)
    finally:
        await conn.close()
    print(f"\nupserted {total} rows across {len(events)} events", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(amain(argv))


if __name__ == "__main__":
    sys.exit(main())
