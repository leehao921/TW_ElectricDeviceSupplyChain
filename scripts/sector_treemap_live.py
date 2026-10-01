#!/usr/bin/env python3
"""產業全景盤中版 — Redis `sector:live` → analysis/sector_treemap_live.html (2026-10-01).

database 的 tmf-sector-intraday-collector 每 60 秒把全市場 MIS 報價寫進 Redis
`sector:live`; 本腳本以最新 stock_quote_daily 補發行股數 / 產業別 / 名稱, 沿用
sector_treemap.build_market 彙總, 輸出每 60 秒自動刷新的本機頁。

盤中成交值 = 累計量(張) × 1000 × 現價 (MIS 無成交金額), 頁面標「估」。
launchd com.lulala.sector-treemap-live 每 60 秒觸發; 快照過舊 (盤後/休市) 即靜默退出。

    python scripts/sector_treemap_live.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sector_treemap as st  # noqa: E402

PAGE = ROOT / "artifacts" / "sector_treemap" / "index.html"
OUT = ROOT / "analysis" / "sector_treemap_live.html"
TPE = dt.timezone(dt.timedelta(hours=8))


def live_rows(snap: dict, ref: dict) -> dict:
    out: dict = {}
    for q in snap["quotes"]:
        r = ref.get((q["market"], q["code"]))
        if not r or not r.get("shares") or not r.get("industry_code"):
            continue
        out.setdefault(q["market"], []).append({
            "code": q["code"], "name": r["name"], "industry_code": r["industry_code"],
            "shares": r["shares"], "prev_close": q["prev"], "close": q["last"],
            "change": q["last"] - q["prev"], "trade_value": q["vol_lots"] * 1000 * q["last"],
        })
    return out


def live_index(snap: dict) -> dict:
    out: dict = {}
    for i in snap["indices"]:
        if not i.get("prev"):
            continue
        pts = i["close"] - i["prev"]
        out.setdefault(i["market"], {})[i["industry_code"]] = {
            "name": None, "close": i["close"], "change_pts": pts, "change_pct": pts / i["prev"] * 100}
    return out


def build_live(snap: dict, ref: dict) -> dict:
    rows, idx = live_rows(snap, ref), live_index(snap)
    ts = dt.datetime.fromisoformat(snap["ts"])
    return {"date": f"{ts:%Y-%m-%d %H:%M:%S} 盤中", "live": True,
            "markets": {m: st.build_market(rows[m], idx.get(m, {})) for m in ("TWSE", "TPEX") if rows.get(m)}}


def is_stale(snap: dict, now: dt.datetime, max_age_s: int = 300) -> bool:
    return (now - dt.datetime.fromisoformat(snap["ts"])).total_seconds() > max_age_s


def _reference() -> dict:
    import psycopg2
    conn = psycopg2.connect(host="localhost", port=5432, user="tmf",
                            password="tmf_dev_2026", dbname="tmf_market_data")
    try:
        cur = conn.cursor()
        cur.execute("""SELECT market, code, name, industry_code, shares FROM stock_quote_daily
                       WHERE date = (SELECT max(date) FROM stock_quote_daily)""")
        return {(m, c): {"name": n, "industry_code": i, "shares": s} for m, c, n, i, s in cur.fetchall()}
    finally:
        conn.close()


def main() -> int:
    import redis
    raw = redis.Redis().get("sector:live")
    if not raw:
        return 0
    snap = json.loads(raw)
    if is_stale(snap, dt.datetime.now(TPE)):
        return 0
    data = build_live(snap, _reference())
    OUT.write_text(st.render_standalone(PAGE.read_text(), data, refresh_s=60))
    m = data["markets"].get("TWSE")
    if m:
        print(f"{data['date']} 加權 {m['index']['chg_pts']:+.2f} Σ貢獻 {m['contrib_sum_pts']:+.2f} → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
