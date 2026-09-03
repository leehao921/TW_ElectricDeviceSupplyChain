#!/usr/bin/env python3
"""margin_daily T+1 盤前自癒 (Mon-Fri 09:05) — 昨日缺/短收才補抓, 平時靜默.

背景: 18:10 routine 抓當日 TWSE 融資資料偶爾未出 (8/27、9/2 兩例),
雖然隔日 18:10 的 prev-day recollect 會自癒, 但整個白天 (盤前儀表、
17:50 日掃) 都吃到 T-2 stale。此 job 把自癒提前到盤前。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOLIDAYS = REPO / "data" / "tw_market_holidays.txt"
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")
MIN_ROWS = 1500        # TWSE+TPEx 全量 ~2200; TWSE-only ~1300 也算短收


def prev_trading_day(today: date, holidays: set) -> date:
    d = today - timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in holidays:
        d -= timedelta(days=1)
    return d


def needs_heal(row_count: int) -> bool:
    return row_count < MIN_ROWS


def load_holidays() -> set:
    if not HOLIDAYS.exists():
        return set()
    return {ln.split("#")[0].strip() for ln in HOLIDAYS.read_text().splitlines()
            if ln.split("#")[0].strip()}


def main() -> int:
    today = date.today()
    hols = load_holidays()
    if today.weekday() >= 5 or today.isoformat() in hols:
        return 0
    target = prev_trading_day(today, hols)

    import psycopg2
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM margin_daily WHERE date=%s", (target,))
        n = cur.fetchone()[0]
    if not needs_heal(n):
        print(f"{target}: {n} rows — healthy, no action")
        return 0

    print(f"{target}: only {n} rows — healing via collector")
    r = subprocess.run(
        ["docker", "exec", "-e", "PYTHONPATH=/opt/tmf:/opt/tmf/src",
         "tmf-stock-daily-collector", "python",
         "scripts/collectors/margin_daily.py", "--date", target.isoformat()],
        capture_output=True, text=True, timeout=300)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM margin_daily WHERE date=%s", (target,))
        after = cur.fetchone()[0]
    ok = not needs_heal(after)
    msg = (f"{'✅' if ok else '🚨'} margin T+1 自癒 {target}: {n} → {after} 列"
           + ("" if ok else f" (仍短收; collector rc={r.returncode})"))
    print(msg)
    try:
        import redis
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "margin_heal", "topic": "margin-heal",
            "tags": "margin,heal", "as_of": today.isoformat(), "msg": msg})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
