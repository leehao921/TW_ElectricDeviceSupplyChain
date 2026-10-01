#!/usr/bin/env python3
"""產業全景 treemap 每日 routine — launchd com.lulala.sector-treemap, 交易日 15:35.

database 的 stock-daily 排程 15:20 寫完 stock_quote_daily / sector_index_daily 後:
  1. 重建 artifacts/sector_treemap/data.json
  2. 寫可獨立開啟的 analysis/sector_treemap_<date>.html (資料內嵌)
  3. 推 claude:inbox topic=sector-treemap (指數漲跌 + 前三大貢獻產業與主力)

線上 artifact 不會自動更新: headless claude 沒有 Artifact 工具 (2026-10-01 實測),
需在互動 session 說「更新產業全景」以同一 URL 重新發佈 data.json。

    python scripts/sector_treemap_routine.py [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sector_treemap as st  # noqa: E402

ARTIFACT_URL = "https://claude.ai/artifact/FtphAZXNDkU4K2VccBzqpH"
PAGE = ROOT / "artifacts" / "sector_treemap" / "index.html"
DATA = ROOT / "artifacts" / "sector_treemap" / "data.json"
TPE = dt.timezone(dt.timedelta(hours=8))


def _xadd(msg: str, tags: str, as_of: str) -> None:
    subprocess.run(["redis-cli", "XADD", "claude:inbox", "*",
                    "ts", dt.datetime.now(TPE).strftime("%Y-%m-%d %H:%M"),
                    "from", "sector_treemap", "topic", "sector-treemap", "tags", tags,
                    "as_of", as_of, "msg", msg], check=True, capture_output=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="build + print, no files or inbox")
    args = ap.parse_args(argv)
    today = dt.datetime.now(TPE).date().isoformat()

    import psycopg2
    conn = psycopg2.connect(host="localhost", port=5432, user="tmf",
                            password="tmf_dev_2026", dbname="tmf_market_data")
    try:
        cur = conn.cursor()
        cur.execute("SELECT max(date)::text FROM stock_quote_daily")
        latest = cur.fetchone()[0]
        data = st.load(conn, latest) if latest else {"markets": {}}
    finally:
        conn.close()

    if not data["markets"]:
        print("stock_quote_daily empty")
        return 1
    line = st.summary_line(data)
    stale = latest != today
    msg = (f"🗺️ 產業全景 {line}" + (f"\n⚠️ 資料日 {latest} ≠ 今日 {today} (休市或 15:20 來源未出)" if stale else "")
           + f"\n本機: analysis/sector_treemap_{latest}.html・線上 {ARTIFACT_URL} 需在 session 說「更新產業全景」重新發佈"
           + "\n(分析標註·不構成交易指令)")
    print(msg)
    if args.dry_run:
        return 0

    DATA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    out = ROOT / "analysis" / f"sector_treemap_{latest}.html"
    out.write_text(st.render_standalone(PAGE.read_text(), data))
    _xadd(msg, "sector,treemap" + (",stale" if stale else ""), latest)
    print(f"wrote {DATA.relative_to(ROOT)}, {out.relative_to(ROOT)}; inbox OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
