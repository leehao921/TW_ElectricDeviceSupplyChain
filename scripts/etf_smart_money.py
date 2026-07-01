#!/usr/bin/env python3
"""etf_smart_money.py — 主動式 ETF 持股 × Smart Money × 產業輪動 報告產生器.

結合三個資料源，輸出 Markdown 至 analysis/：
  1. ETF 持股共識 (positioning) — etf_holdings_daily，各主動 ETF 最新快照的
     breadth（幾檔持有）與 Σ權重。
  2. 三大法人 flow (rotation) — institutional_stock 近 N 交易日投信/外資淨買，
     以當日 stock_daily_ohlcv 收盤價換算億元。
  3. ETF 實際加碼/減碼 — 可回補 ETF 的持股權重時間序列 Δ（真實換手，非 flow 代理）。

Sector 對應取自 Pilot_Reports。純彙總邏輯 (aggregate_consensus / rotation_delta)
有單元測試 (tests/test_etf_smart_money.py)。

Usage:
    python scripts/etf_smart_money.py                 # 預設 flow window 20 天
    python scripts/etf_smart_money.py --flow-window 5
    python scripts/etf_smart_money.py --min-breadth 8 --output /tmp/x.md
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO / "Pilot_Reports"
OUT_DIR = REPO / "analysis"
_FN = re.compile(r"^(\d{4})_")
TZ_TPE = timezone(timedelta(hours=8))

DB_CONFIG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5432")),
    user=os.environ.get("DB_USER", "tmf"),
    password=os.environ.get("DB_PASSWORD", "tmf_dev_2026"),
    dbname=os.environ.get("DB_NAME", "tmf_market_data"),
)


# --------------------------------------------------------------------------- #
# Pure aggregation (unit-tested)
# --------------------------------------------------------------------------- #
def aggregate_consensus(rows):
    """rows: [(etf, code, name, weight)] -> {code: {name,n_etfs,aggw,avgw}}."""
    agg = {}
    for etf, code, name, w in rows:
        d = agg.setdefault(code, {"name": name or "", "etfs": set(), "wsum": 0.0})
        d["etfs"].add(etf)
        d["wsum"] += float(w or 0)
        if name:
            d["name"] = name
    out = {}
    for code, d in agg.items():
        n = len(d["etfs"])
        out[code] = {
            "name": d["name"], "n_etfs": n,
            "aggw": round(d["wsum"], 1),
            "avgw": round(d["wsum"] / n, 2) if n else 0.0,
        }
    return out


def rotation_delta(start_rows, end_rows):
    """Δ aggregate weight per code between two snapshots (real add/trim)."""
    def acc(rows):
        m = {}
        for etf, code, name, w in rows:
            d = m.setdefault(code, {"name": name or "", "etfs": set(), "w": 0.0})
            d["etfs"].add(etf)
            d["w"] += float(w or 0)
            if name:
                d["name"] = name
        return m

    s, e = acc(start_rows), acc(end_rows)
    out = {}
    for code in set(s) | set(e):
        sd, ed = s.get(code), e.get(code)
        ws = sd["w"] if sd else 0.0
        we = ed["w"] if ed else 0.0
        out[code] = {
            "name": (ed or sd)["name"],
            "n_start": len(sd["etfs"]) if sd else 0,
            "n_end": len(ed["etfs"]) if ed else 0,
            "w_start": round(ws, 1), "w_end": round(we, 1),
            "delta": round(we - ws, 1),
        }
    return out


def build_sector_map():
    sm = {}
    for fp in glob.glob(str(REPORTS_DIR / "**" / "*.md"), recursive=True):
        m = _FN.match(os.path.basename(fp))
        if m:
            sm[m.group(1)] = os.path.basename(os.path.dirname(fp))
    return sm


# --------------------------------------------------------------------------- #
# DB access
# --------------------------------------------------------------------------- #
def latest_snapshot_rows(conn):
    cur = conn.cursor()
    cur.execute("""
      WITH latest AS (SELECT DISTINCT ON (etf_code) etf_code,date
                      FROM etf_holdings_daily ORDER BY etf_code,date DESC)
      SELECT h.etf_code,h.constituent_code,h.constituent_name,h.weight_pct
      FROM etf_holdings_daily h JOIN latest l USING(etf_code,date)
      WHERE h.constituent_code ~ '^[0-9]{4}$'""")
    return cur.fetchall()


def rows_on_date(conn, date, etfs):
    cur = conn.cursor()
    cur.execute("""SELECT etf_code,constituent_code,constituent_name,weight_pct
                   FROM etf_holdings_daily
                   WHERE date=%s AND etf_code = ANY(%s) AND constituent_code ~ '^[0-9]{4}$'""",
                (date, list(etfs)))
    return cur.fetchall()


def flow_by_symbol(conn, ndays):
    cur = conn.cursor()
    cur.execute(f"""
      WITH days AS (SELECT DISTINCT date FROM institutional_stock ORDER BY date DESC LIMIT {int(ndays)})
      SELECT i.symbol,
             round((sum(i.trust_net*o.close)/1e8)::numeric,1),
             round((sum(i.foreign_net*o.close)/1e8)::numeric,1)
      FROM institutional_stock i JOIN days d USING(date)
      JOIN stock_daily_ohlcv o ON o.symbol=i.symbol AND o.ts::date=i.date
      GROUP BY i.symbol""")
    return {r[0]: (float(r[1] or 0), float(r[2] or 0)) for r in cur.fetchall()}


def rotation_window(conn, min_days=40):
    """ETFs with >= min_days history + their common first/last dates."""
    cur = conn.cursor()
    cur.execute("SELECT etf_code FROM etf_holdings_daily GROUP BY etf_code "
                "HAVING count(DISTINCT date) >= %s", (min_days,))
    etfs = [r[0] for r in cur.fetchall()]
    if not etfs:
        return etfs, None, None
    cur.execute("""SELECT min(date),max(date) FROM (
        SELECT date FROM etf_holdings_daily WHERE etf_code = ANY(%s)
        GROUP BY date HAVING count(DISTINCT etf_code)=%s) x""", (etfs, len(etfs)))
    lo, hi = cur.fetchone()
    return etfs, lo, hi


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(conn, flow_window, min_breadth):
    sec = build_sector_map()
    cons = aggregate_consensus(latest_snapshot_rows(conn))
    flow = flow_by_symbol(conn, flow_window)
    n_etfs_total = len({r[0] for r in latest_snapshot_rows(conn)})

    L = []
    now = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    L.append(f"# 主動式 ETF 持股 × Smart Money × 產業輪動（自動產生）\n")
    L.append(f"**產生時間:** {now}　**涵蓋主動 ETF:** {n_etfs_total} 檔　"
             f"**Flow 視窗:** 近 {flow_window} 交易日\n")
    L.append("> Smart money = 主動 ETF 經理人(投信)。ETF 持股=持倉(positioning)；"
             "institutional_stock 投信淨買=動作(flow)。\n")

    # 1) consensus
    L.append(f"\n## 一、Smart Money 共識持倉（breadth ≥ {min_breadth}）\n")
    L.append("| 檔 | Code | 名稱 | Sector | 均重% | Σ權重% | 投信flow億 | 外資flow億 |")
    L.append("|--:|---|---|---|--:|--:|--:|--:|")
    ranked = sorted(cons.items(), key=lambda kv: (-kv[1]["n_etfs"], -kv[1]["aggw"]))
    for code, d in ranked:
        if d["n_etfs"] < min_breadth:
            continue
        t, f = flow.get(code, (0.0, 0.0))
        L.append(f"| {d['n_etfs']} | {code} | {d['name'][:10]} | {sec.get(code,'—')[:24]} | "
                 f"{d['avgw']:.2f} | {d['aggw']:.1f} | {t:+.1f} | {f:+.1f} |")

    # 2) sector rollup
    L.append("\n## 二、產業輪動（投信 flow by sector，共識股）\n")
    roll = {}
    for code, d in cons.items():
        if d["n_etfs"] < 5:
            continue
        s = sec.get(code, "—")
        t, f = flow.get(code, (0.0, 0.0))
        r = roll.setdefault(s, {"n": 0, "w": 0.0, "t": 0.0, "f": 0.0})
        r["n"] += 1; r["w"] += d["aggw"]; r["t"] += t; r["f"] += f
    L.append("| Sector | 共識檔 | ΣETF權重% | 投信flow億 | 外資flow億 |")
    L.append("|---|--:|--:|--:|--:|")
    for s, r in sorted(roll.items(), key=lambda kv: -kv[1]["w"]):
        L.append(f"| {s} | {r['n']} | {r['w']:.1f} | {r['t']:+.1f} | {r['f']:+.1f} |")

    # 3) ETF real rotation (add/trim) if history allows
    etfs, lo, hi = rotation_window(conn)
    L.append("\n## 三、主動經理人實際加碼/減碼（ETF 時間序列）\n")
    if lo and hi and lo != hi:
        rot = rotation_delta(rows_on_date(conn, lo, etfs), rows_on_date(conn, hi, etfs))
        L.append(f"可回補 {len(etfs)} 檔 ETF，{lo} → {hi} 的 Σ權重變化：\n")
        L.append("| Code | 名稱 | 檔數起→迄 | Δ權重 | Sector |")
        L.append("|---|---|:-:|--:|---|")
        big = sorted(rot.items(), key=lambda kv: kv[1]["delta"])
        picks = [x for x in big if abs(x[1]["delta"]) >= 3]
        for code, d in (picks[:10] + picks[-10:] if len(picks) > 20 else picks):
            L.append(f"| {code} | {d['name'][:8]} | {d['n_start']}→{d['n_end']} | "
                     f"{d['delta']:+.1f} | {sec.get(code,'—')[:20]} |")
        L.append("\n> Caveat：加碼欄「檔數起<迄」部分為期間內新 ETF 建倉(universe 成長)；"
                 "「減碼到 0 檔」的出清才是乾淨信念訊號。")
    else:
        L.append("（ETF 歷史深度不足，尚無法算實際加碼/減碼；daemon 每交易日 18:30 累積中。）")

    # verification note
    L.append("\n## 資料限制 & Verification Log\n")
    L.append(f"- 數字均為直接彙總：ETF 共識 = count(distinct etf)/sum(weight)；"
             f"flow = 近 {flow_window} 日 Σ(法人淨買股數 × 當日收盤)/1e8 億元。")
    L.append("- 未使用 σ/罕見/極端/percentile 等分布形容詞（golden rule 0 未觸發）。")
    L.append(f"- 涵蓋 {n_etfs_total} 檔主動 ETF；未覆蓋者之共識為下限。可回補歷史僅 date-capable issuer。")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="主動 ETF smart money × 產業輪動 報告")
    ap.add_argument("--flow-window", type=int, default=20, help="投信/外資 flow 交易日數 (預設 20)")
    ap.add_argument("--min-breadth", type=int, default=8, help="共識表最低持有檔數 (預設 8)")
    ap.add_argument("--output", help="輸出路徑 (預設 analysis/etf_smart_money_<date>.md)")
    args = ap.parse_args(argv)

    import psycopg2
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        md = render(conn, args.flow_window, args.min_breadth)
    finally:
        conn.close()

    now = datetime.now(TZ_TPE).strftime("%Y-%m-%d")
    out = Path(args.output) if args.output else OUT_DIR / f"etf_smart_money_{now}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
