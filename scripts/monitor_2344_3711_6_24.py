#!/usr/bin/env python3
"""6/24 NVIDIA 股東大會 + Micron 財報日 monitor.

Pulls 2344 華邦電 + 3711 日月光投控 institutional flow + price + writes
alert markdown to vault/inbox/. Run by host cron on 2026-06-24 09:00 TWT.

Triggers reality check for:
- vault/concepts/Vera_Rubin_BOM.md Unit 18 HBM4 thesis (+67% YoY)
- vault/concepts/Institutional_Alpha_2026-06.md (2344 ★★★★★ + 3711 ★★★)

Usage: python3 scripts/monitor_2344_3711_6_24.py
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = REPO_ROOT / "vault" / "inbox"


def query_institutional() -> list:
    """Pull 2344 + 3711 法人 last 5 trading days before 6/24."""
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="tmf_market_data",
        user="tmf", password="tmf_dev_2026",
    )
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT date, symbol,
                  ROUND(foreign_net::numeric/1000) AS f_lots,
                  ROUND(trust_net::numeric/1000)   AS t_lots,
                  ROUND(dealer_net::numeric/1000)  AS d_lots,
                  ROUND(total_net::numeric/1000)   AS tot_lots,
                  close_price
                FROM institutional_stock
                WHERE symbol IN ('2344','3711')
                  AND date >= '2026-06-17' AND date <= '2026-06-24'
                ORDER BY symbol, date;
            """)
            rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def fetch_yfinance_prices() -> dict:
    """Pull yfinance latest 5-day close + volume for 2344 + 3711."""
    import yfinance as yf
    import pandas as pd

    out = {}
    end = datetime.now() + timedelta(days=1)
    start = end - timedelta(days=15)
    for sym, name in [("2344.TW", "華邦電"), ("3711.TW", "日月光投控")]:
        df = yf.Ticker(sym).history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
        )
        df.index = df.index.tz_localize(None)
        out[sym] = (name, df.tail(5)[["Close", "Volume"]])
    return out


def write_alert(rows, prices) -> Path:
    """Write alert markdown to vault/inbox/2026-W26.md."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    out_file = INBOX_DIR / "2026-W26.md"

    ts = datetime.now().strftime("%Y-%m-%d %H:%M TWT")
    content = f"""# 2026-W26 (Jun 22-28) Inbox

## [2026-06-24 {ts.split()[1]}] alert | NVIDIA 股東大會 + Micron 財報日 monitor

**Source**: scripts/monitor_2344_3711_6_24.py (host cron `0 9 24 6 *`)
**Cross-ref**: vault/research/macro_calendar_2026-06.md + Vera_Rubin_BOM.md (Unit 18 HBM4) + Institutional_Alpha_2026-06.md

---

### 2344 華邦電 + 3711 日月光 法人 6/17-6/24 (DB query)

| Date | Symbol | 外資 (張) | 投信 | 自營 | 總 | 收盤 |
|---|---|---:|---:|---:|---:|---:|
"""
    for r in rows:
        d, sym, f, t, dl, tot, px = r
        content += f"| {d} | {sym} | {f:,} | {t:,} | {dl:,} | {tot:,} | {px} |\n"

    content += "\n### yfinance 最近 5 日 (Close + Volume)\n\n"
    for sym, (name, df) in prices.items():
        content += f"\n**{sym} {name}**:\n```\n{df.to_string()}\n```\n"

    content += """
---

## TODO (人工執行)

- [ ] 查 Micron Q3 FY26 (2026-06-24 公布) HBM4/HBM3e ASP + AI server 客戶 capex 訊號
- [ ] 對比 vault/concepts/Vera_Rubin_BOM.md Unit 18 HBM4 thesis 看是否修正
- [ ] 若 Micron miss → 2344/3711 預期回檔 5-10%, 考慮減碼
- [ ] 若 Micron beat → 加碼 ★★★★★ 確認
- [ ] 更新 vault/concepts/Institutional_Alpha_2026-06.md Top 5 排序若需要

## 自動驗證 thesis

| Thesis | 來源 | 6/24 數據是否驗證? |
|---|---|---|
| 2344 ★★★★★ 雙引擎 (institutional_alpha unit 28) | 法人 5/12-6/1 +285K | 看 6/17-6/24 是否續買 |
| 3711 #1 PEG 1.4 (institutional_alpha unit 31) | Q1 OpM 10.10% | 看 6/24 後法人結構 (5/29 已 -13.8K) |
| HBM4 +67% price-driven (Vera_Rubin_BOM unit 18) | wccftech | Micron Q3 ASP 訊號 |
"""

    out_file.write_text(content)
    return out_file


def main():
    print(f"=== 2344/3711 monitor 6/24 ===")
    print(f"Running at: {datetime.now()}")

    print("\n--- DB query 法人 ---")
    rows = query_institutional()
    for r in rows:
        print(r)

    print("\n--- yfinance prices ---")
    prices = fetch_yfinance_prices()
    for sym, (name, df) in prices.items():
        print(f"\n{sym} {name}:")
        print(df.to_string())

    print("\n--- Write inbox alert ---")
    out = write_alert(rows, prices)
    print(f"Wrote: {out}")

    # Optional: terminal-notifier or osascript notification
    try:
        subprocess.run([
            "osascript", "-e",
            'display notification "6/24 NVDA + Micron monitor ran — check vault/inbox/2026-W26.md" with title "2344/3711 Alert"'
        ], check=False)
    except Exception:
        pass


if __name__ == "__main__":
    main()
