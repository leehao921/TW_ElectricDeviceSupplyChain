#!/usr/bin/env python3
"""產業全景 treemap 資料 — 加權 / 櫃買產業彙總 JSON (2026-09-30).

讀 database repo 的 stock_quote_daily + sector_index_daily (scripts/collectors/sector_daily.py),
每市場每產業輸出: 成交值、指數貢獻點、市值加權漲跌、官方類股指數漲跌、成員 (貢獻點/成交值),
以及兩種排行 (貢獻 / 成交值) 各自的「其他成員」— 其漲跌由官方類股指數反推:

    r_other = (R_s·W_s − Σ_top w_i·r_i) / (W_s − Σ_top w_i)      (W = 前日市值)

加權指數以發行股數 × 價計 (IndexS02, 非自由流通), 貢獻點 = shares·Δ / Σ前日市值 × 前日指數。
存託憑證 (產業別 91) 與缺股數者不計權重。

Usage:
    python scripts/sector_treemap.py --date 2026-09-30 --out artifacts/sector_treemap/data.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

INDUSTRY_NAMES = {
    "01": "水泥", "02": "食品", "03": "塑膠", "04": "紡織纖維", "05": "電機機械", "06": "電器電纜",
    "08": "玻璃陶瓷", "09": "造紙", "10": "鋼鐵", "11": "橡膠", "12": "汽車", "14": "建材營造",
    "15": "航運", "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨", "20": "其他", "21": "化學",
    "22": "生技醫療", "23": "油電燃氣", "24": "半導體業", "25": "電腦及週邊設備", "26": "光電",
    "27": "通信網路", "28": "電子零組件", "29": "電子通路", "30": "資訊服務", "31": "其他電子",
    "32": "文化創意", "33": "農業科技", "35": "綠能環保", "36": "數位雲端", "37": "運動休閒",
    "38": "居家生活",
}
TDR = "91"
TOP_N = 12


def _other(members: list, top: list, sector_contrib: float, w_sector: float,
           official_ret, p_index: float, w_market: float):
    rest = [m for m in members if m["code"] not in {t["code"] for t in top}]
    if not rest:
        return None
    w_rest = sum(m["mcap_prev"] for m in rest)
    top_dcap = sum(m["dcap"] for m in top)
    if official_ret is not None and w_rest > 1e-9 * max(w_sector, 1):
        ret = (official_ret / 100 * w_sector - top_dcap) / w_rest * 100
        method = "official_backout"
    else:
        ret = sum(m["dcap"] for m in rest) / w_rest * 100 if w_rest else None
        method = "members"
    return {"n": len(rest), "codes": [m["code"] for m in rest],
            "trade_value": sum(m["trade_value"] for m in rest),
            "contrib_pts": sector_contrib - sum(t["contrib_pts"] for t in top),
            "ret": ret, "ret_method": method}


def _official_ret(ix):
    """Index % from points: the published 2-dp % is amplified by 1/w in the back-out."""
    if not ix:
        return None
    close, pts = ix.get("close"), ix.get("change_pts")
    if close is not None and pts is not None and close - pts:
        return pts / (close - pts) * 100
    return ix.get("change_pct")


def build_market(rows: list, index: dict, top_n: int = TOP_N) -> dict:
    """rows: stock_quote_daily dicts of one market/date; index: industry_code → row (IX = 大盤)."""
    excluded = {"tdr": 0, "no_shares": 0}
    usable = []
    for r in rows:
        if r.get("industry_code") == TDR:
            excluded["tdr"] += 1
        elif not r.get("shares"):
            excluded["no_shares"] += 1
        else:
            usable.append(r)
    w_market = sum(r["shares"] * r["prev_close"] for r in usable)
    ix = index.get("IX") or {}
    p_index = (ix["close"] - ix["change_pts"]) if ix else None
    scale = p_index / w_market if (p_index and w_market) else 0.0

    by_sector: dict = {}
    for r in usable:
        dcap = r["shares"] * (r["close"] - r["prev_close"])
        mcap_prev = r["shares"] * r["prev_close"]
        by_sector.setdefault(r.get("industry_code") or "??", []).append({
            "code": r["code"], "name": r["name"], "close": r["close"],
            "ret": (r["close"] / r["prev_close"] - 1) * 100 if r["prev_close"] else None,
            "trade_value": r.get("trade_value") or 0, "mcap_prev": mcap_prev, "dcap": dcap,
            "contrib_pts": dcap * scale,
        })

    sectors = []
    for code, members in by_sector.items():
        members.sort(key=lambda m: -abs(m["contrib_pts"]))
        w_s = sum(m["mcap_prev"] for m in members)
        contrib = sum(m["contrib_pts"] for m in members)
        official = _official_ret(index.get(code))
        top_c = members[:top_n]
        top_v = sorted(members, key=lambda m: -m["trade_value"])[:top_n]
        sectors.append({
            "code": code, "name": INDUSTRY_NAMES.get(code, code), "n": len(members),
            "trade_value": sum(m["trade_value"] for m in members),
            "contrib_pts": contrib, "mcap_prev": w_s,
            "wret": sum(m["dcap"] for m in members) / w_s * 100 if w_s else None,
            "official_ret": official,
            "members": [{k: m[k] for k in ("code", "name", "close", "ret", "trade_value",
                                            "contrib_pts", "mcap_prev")} for m in members],
            "top": {"contrib": [m["code"] for m in top_c], "value": [m["code"] for m in top_v]},
            "other": {"contrib": _other(members, top_c, contrib, w_s, official, p_index, w_market),
                      "value": _other(members, top_v, contrib, w_s, official, p_index, w_market)},
        })
    sectors.sort(key=lambda s: -s["trade_value"])
    total = sum(s["contrib_pts"] for s in sectors)
    return {
        "index": {"name": ix.get("name"), "prev": p_index, "close": ix.get("close"),
                  "chg_pts": ix.get("change_pts"), "chg_pct": ix.get("change_pct")},
        "contrib_sum_pts": total,
        "residual_pts": (total - ix["change_pts"]) if ix else None,
        "trade_value": sum(s["trade_value"] for s in sectors),
        "excluded": excluded,
        "sectors": sectors,
    }


def render_standalone(page_html: str, data: dict) -> str:
    """Self-contained local page: the artifact page with data inlined (headless claude
    cannot republish the artifact, so the 15:35 routine writes this instead)."""
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>'
            f"<script>window.__SECTOR_DATA__={blob};</script>\n{page_html}\n</body></html>")


def summary_line(data: dict, n: int = 3) -> str:
    """Inbox one-liner: index move + top sectors by |contribution| with their lead stock."""
    parts = []
    for mkt, label in (("TWSE", "加權"), ("TPEX", "櫃買")):
        m = data["markets"].get(mkt)
        if not m:
            continue
        secs = sorted(m["sectors"], key=lambda s: -abs(s["contrib_pts"]))[:n]
        desc = "、".join(
            f"{s['name']} {s['contrib_pts']:+.2f} (主力 {s['members'][0]['name']})"
            for s in secs if s["members"])
        parts.append(f"{label} {m['index']['chg_pts']:+.2f} 點｜{desc}")
    return f"{data['date']} " + "　".join(parts)


def load(conn, date: str) -> dict:
    cur = conn.cursor()
    cur.execute("""SELECT market, code, name, industry_code, close, change, prev_close,
                          trade_value, shares FROM stock_quote_daily WHERE date = %s""", (date,))
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.execute("""SELECT market, industry_code, name, close, change_pts, change_pct
                   FROM sector_index_daily WHERE date = %s""", (date,))
    idx: dict = {}
    for mkt, code, name, close, pts, pct in cur.fetchall():
        idx.setdefault(mkt, {})[code] = {"name": name, "close": close,
                                         "change_pts": pts, "change_pct": pct}
    return {"date": date, "markets": {
        m: build_market([r for r in rows if r["market"] == m], idx.get(m, {}))
        for m in ("TWSE", "TPEX") if any(r["market"] == m for r in rows)}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD; default = latest in stock_quote_daily")
    ap.add_argument("--out", default="artifacts/sector_treemap/data.json")
    args = ap.parse_args(argv)
    import psycopg2
    conn = psycopg2.connect(host="localhost", port=5432, user="tmf",
                            password="tmf_dev_2026", dbname="tmf_market_data")
    try:
        date = args.date
        if not date:
            cur = conn.cursor()
            cur.execute("SELECT max(date)::text FROM stock_quote_daily")
            date = cur.fetchone()[0]
        data = load(conn, date)
    finally:
        conn.close()
    if not data["markets"]:
        print(f"{date}: no stock_quote_daily rows")
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    for m, d in data["markets"].items():
        print(f"{date} {m}: {len(d['sectors'])} sectors, Σ貢獻 {d['contrib_sum_pts']:+.2f} "
              f"vs 官方 {d['index']['chg_pts']:+.2f} (殘差 {d['residual_pts']:+.2f})")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
