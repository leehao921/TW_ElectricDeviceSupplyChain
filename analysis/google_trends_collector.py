"""Google Trends collector — narrow scope per user direction (2026-05-05):

- Themes: AI 資料中心, 半導體
- TW weighted top stocks: 2330 台積電, 2317 鴻海, 2454 聯發科, 2382 廣達, 2308 台達電,
  2881 富邦金, 2882 國泰金, 2412 中華電, 1301 台塑, 2330 (already)... ~10 names
- Special short-term watch: 1513 中興電 (separate hourly cron)

Daily mode (--mode=daily): 90-day daily history for all keywords.
Hourly mode (--mode=hourly-1513): 7-day hourly history for 1513 only.

Each row UPSERTs into `google_trends_daily` (table from
ingestion/migrations/004_google_trends.sql), so re-running today refreshes
recent buckets without losing earlier history.

Rate-limit-friendly: pytrends batches ≤ 4 keywords per call, sleeps 5s between
batches. A full daily run is ~2 minutes, well below pytrends limits.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
import warnings
from datetime import datetime, timezone, timedelta

warnings.filterwarnings("ignore")

import asyncpg
from pytrends.request import TrendReq

DB_DSN = "postgresql://knowledge:knowledge@localhost:5433/tw_electronics"
TPE = timezone(timedelta(hours=8))

# Narrow scope per user spec
THEMES = ["AI 資料中心", "半導體"]

WEIGHTED_STOCKS = [
    # Real TAIEX top 10 by market cap (verified via yfinance 2026-05-05).
    # Cumulative weight ≈ 90.8% of TAIEX.
    "台積電",      # 2330  65.87% (one stock = 2/3 of TAIEX)
    "台達電",      # 2308   6.38%
    "聯發科",      # 2454   5.69%
    "鴻海",        # 2317   3.78%
    "日月光投控",  # 3711   2.59%
    "富邦金",      # 2881   1.42%
    "廣達",        # 2382   1.40%
    "國泰金",      # 2882   1.28%
    "中信金",      # 2891   1.19%
    "中華電",      # 2412   1.19%
]

SHORT_TERM_WATCH = ["中興電"]  # 1513 — special hourly cron

BATCH_SIZE = 4   # pytrends max 5; we use 4 with safety
SLEEP_BETWEEN_BATCHES = 5
MAX_RETRIES = 3


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def fetch_batch(pt: TrendReq, keywords: list[str], timeframe: str, geo: str = "TW"):
    """Fetch one batch with retry + exponential backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            pt.build_payload(keywords, timeframe=timeframe, geo=geo)
            df = pt.interest_over_time()
            if df is None or df.empty:
                return None
            df = df.drop(columns=["isPartial"], errors="ignore")
            return df
        except Exception as e:
            wait = (2 ** attempt) * 3
            print(f"  retry {attempt+1}/{MAX_RETRIES} after {wait}s: {e}", file=sys.stderr)
            time.sleep(wait)
    return None


async def upsert_rows(conn, keyword: str, geo: str, df, granularity: str) -> int:
    rows = []
    for ts, score in df[keyword].dropna().items():
        rows.append((keyword, geo, ts.to_pydatetime().replace(tzinfo=timezone.utc),
                     granularity, int(score)))
    if not rows:
        return 0
    await conn.executemany(
        """
        INSERT INTO google_trends_daily (keyword, geo, ts, granularity, score)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (keyword, geo, ts, granularity) DO UPDATE SET
            score = EXCLUDED.score, fetched_at = now()
        """, rows,
    )
    return len(rows)


async def run_daily() -> int:
    """Fetch 90-day daily for all themes + weighted stocks (TW)."""
    pt = TrendReq(hl="zh-TW", tz=480)
    all_keywords = THEMES + WEIGHTED_STOCKS + SHORT_TERM_WATCH
    print(f"[gt_daily] fetching {len(all_keywords)} keywords, batched 4 at a time",
          file=sys.stderr)

    conn = await asyncpg.connect(DB_DSN)
    total_rows = 0
    try:
        for batch in chunks(all_keywords, BATCH_SIZE):
            df = fetch_batch(pt, batch, "today 3-m", "TW")
            if df is None:
                print(f"  [gt_daily] batch {batch} failed", file=sys.stderr)
                time.sleep(SLEEP_BETWEEN_BATCHES)
                continue
            for kw in batch:
                if kw not in df.columns:
                    continue
                n = await upsert_rows(conn, kw, "TW", df, "daily")
                total_rows += n
                print(f"  [gt_daily] {kw}: upserted {n} rows", file=sys.stderr)
            time.sleep(SLEEP_BETWEEN_BATCHES)
    finally:
        await conn.close()
    print(f"[gt_daily] DONE — {total_rows} rows total", file=sys.stderr)
    return total_rows


async def run_hourly_1513() -> int:
    """Fetch 7-day hourly history for 1513 中興電 only."""
    pt = TrendReq(hl="zh-TW", tz=480)
    print(f"[gt_1513_hourly] fetching 7d hourly for 中興電", file=sys.stderr)

    conn = await asyncpg.connect(DB_DSN)
    try:
        df = fetch_batch(pt, ["中興電"], "now 7-d", "TW")
        if df is None:
            print(f"  [gt_1513_hourly] failed", file=sys.stderr)
            return 0
        n = await upsert_rows(conn, "中興電", "TW", df, "hourly")
        print(f"[gt_1513_hourly] DONE — {n} rows", file=sys.stderr)
        return n
    finally:
        await conn.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["daily", "hourly-1513"], required=True)
    args = p.parse_args()
    if args.mode == "daily":
        return asyncio.run(run_daily())
    elif args.mode == "hourly-1513":
        return asyncio.run(run_hourly_1513())


if __name__ == "__main__":
    sys.exit(main() or 0)
