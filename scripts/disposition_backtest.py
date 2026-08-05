#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""disposition_backtest.py — 處置解除回補 backtest (alpha #3, 2026-08-05 plan).

假說: 處置期間 5/20 分鐘撮合 + 預收款券 = 人為流動性稅 → 解除後溢價回歸;
外資處置前有買超者回補概率更高。

資料: TWSE announcement/punish 歷史查詢 (季度分段) × institutional_stock
(TWSE only — OTC 無 close_price,已揭露)。一次性可重跑,不排程。

用法: python scripts/disposition_backtest.py [--since 2025-01-01]
產出: analysis/disposition_backtest_<today>.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import statistics
import sys
import time
from pathlib import Path

TZ_TPE = dt.timezone(dt.timedelta(hours=8))
REPO = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = REPO / "analysis"
PUNISH_URL = "https://www.twse.com.tw/announcement/punish"
SLEEP_S = 3.0                 # 禮貌間隔


# ------------------------------------------------------------------ #
# Pure
# ------------------------------------------------------------------ #
def roc_date(s: str):
    try:
        y, m, d = s.strip().split("/")
        return "%04d-%02d-%02d" % (int(y) + 1911, int(m), int(d))
    except (ValueError, AttributeError):
        return None


def parse_episodes(fields: list, data: list) -> list:
    """punish rows → [{code, name, announce, start, end, nth}] (只留 4 位數股票)。"""
    idx = {f: i for i, f in enumerate(fields or [])}
    ci = idx.get("證券代號", 2)
    ni = idx.get("證券名稱", 3)
    ai = idx.get("公布日期", 1)
    pi = idx.get("處置期間", 6)
    ti = idx.get("處置次數", 7)
    out = []
    for row in data or []:
        try:
            code = str(row[ci]).strip()
            if len(code) != 4 or not code.isdigit():
                continue                      # 濾權證/ETN (5-6 位)
            span = str(row[pi])
            a, b = span.split("～")
            start, end = roc_date(a), roc_date(b)
            if not start or not end:
                continue
            out.append({"code": code, "name": str(row[ni]).strip(),
                        "announce": roc_date(str(row[ai])),
                        "start": start, "end": end, "nth": str(row[ti]).strip()})
        except (ValueError, IndexError):
            continue
    return out


def forward_return(series: list, release: str, horizon: int = 5):
    """series=[(date, close)] 升冪。t0=release 當日或之前最近交易日,
    回 t0→t0+horizon 交易日報酬;前向樣本不足 → None。"""
    dates = [d for d, _ in series]
    i0 = None
    for i in range(len(dates) - 1, -1, -1):
        if dates[i] <= release:
            i0 = i
            break
    if i0 is None or i0 + horizon >= len(series):
        return None
    return series[i0 + horizon][1] / series[i0][1] - 1


def window_flow(flows: list, anchor: str, days: int = 5, direction: str = "before"):
    """flows=[(date, v)] 升冪。anchor 前/後 days 個交易日的累計。"""
    if direction == "before":
        sel = [v for d, v in flows if d < anchor][-days:]
    else:
        sel = [v for d, v in flows if d > anchor][:days]
    return sum(sel) if sel else 0.0


def _stats(vals: list) -> dict:
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "mean": statistics.mean(vals),
            "median": statistics.median(vals),
            "win": sum(1 for v in vals if v > 0) / len(vals)}


# ------------------------------------------------------------------ #
# I/O
# ------------------------------------------------------------------ #
def fetch_punish(since: dt.date, until: dt.date) -> list:
    import requests
    episodes = []
    cur = since
    while cur <= until:
        chunk_end = min(cur + dt.timedelta(days=89), until)
        r = requests.get(PUNISH_URL, params={
            "response": "json", "startDate": cur.strftime("%Y%m%d"),
            "endDate": chunk_end.strftime("%Y%m%d")}, timeout=20)
        r.raise_for_status()
        j = r.json()
        episodes.extend(parse_episodes(j.get("fields"), j.get("data")))
        print("[fetch] %s..%s → 累計 %d 檔次" % (cur, chunk_end, len(episodes)),
              file=sys.stderr)
        cur = chunk_end + dt.timedelta(days=1)
        time.sleep(SLEEP_S)
    return episodes


def _db():
    import psycopg2
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user="tmf", password=os.environ.get("DB_PASSWORD", "tmf_dev_2026"),
        dbname="tmf_market_data")


def fetch_stock(conn, code: str):
    """(price series, foreign value flow series) 升冪;無 TWSE close → ([], [])。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT date, close_price, foreign_net * close_price FROM institutional_stock "
        "WHERE symbol=%s AND close_price > 0 ORDER BY date", (code,))
    rows = cur.fetchall()
    cur.close()
    prices = [(d.isoformat(), float(c)) for d, c, _ in rows]
    flows = [(d.isoformat(), float(f or 0)) for d, _, f in rows]
    return prices, flows


def render(today, since, episodes, results, seg) -> str:
    md = "# 處置解除回補 backtest (disposition_backtest)\n\n"
    md += "**產出:** %s　**樣本期:** %s 起　**episodes:** %d (TWSE 4 位數股票)\n\n" % (
        today, since, len(episodes))
    md += ("> 假說: 處置流動性稅 → 解除後溢價回歸;外資處置前買超者回補概率高。\n"
           "> 限制: institutional_stock 只含 TWSE 上市 close (上櫃處置股不在樣本);\n"
           "> 解除日後不足 horizon 交易日的 episode 不計報酬。\n\n")
    md += "## 解除後報酬\n\n| 分組 | n | +5D mean | +5D median | +5D 勝率 | +10D mean | +10D 勝率 |\n|---|--:|--:|--:|--:|--:|--:|\n"
    for label in ("全樣本", "處置前外資買超", "處置前外資賣超"):
        s5, s10 = seg[label]
        md += "| %s | %d | %s | %s | %s | %s | %s |\n" % (
            label, s5.get("n", 0),
            "%.2f%%" % (100 * s5["mean"]) if s5.get("n") else "—",
            "%.2f%%" % (100 * s5["median"]) if s5.get("n") else "—",
            "%.0f%%" % (100 * s5["win"]) if s5.get("n") else "—",
            "%.2f%%" % (100 * s10["mean"]) if s10.get("n") else "—",
            "%.0f%%" % (100 * s10["win"]) if s10.get("n") else "—")
    md += "\n## 最近 15 個 episodes\n\n| 代號 | 名稱 | 處置期間 | 次數 | 前5D外資(億) | +5D | +10D |\n|---|---|---|---|--:|--:|--:|\n"
    for r in sorted(results, key=lambda x: x["end"], reverse=True)[:15]:
        md += "| %s | %s | %s~%s | %s | %.1f | %s | %s |\n" % (
            r["code"], r["name"], r["start"][5:], r["end"][5:], r["nth"],
            r["pre_flow"] / 1e8,
            "%.1f%%" % (100 * r["ret5"]) if r["ret5"] is not None else "未滿",
            "%.1f%%" % (100 * r["ret10"]) if r["ret10"] is not None else "未滿")
    md += ("\n## Verification log\n\n- 來源: TWSE announcement/punish 季度分段實抓;"
           "報酬與外資金額由 institutional_stock (close_price>0) 計算。\n"
           "- 統計為簡單平均,無市場中性調整 — 解讀時對照同期大盤。\n")
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2025-01-01")
    args = ap.parse_args()
    since = dt.date.fromisoformat(args.since)
    today = dt.datetime.now(TZ_TPE).date()

    episodes = fetch_punish(since, today)
    print("[info] %d stock episodes" % len(episodes), file=sys.stderr)

    conn = _db()
    results = []
    cache = {}
    try:
        for ep in episodes:
            if ep["code"] not in cache:
                cache[ep["code"]] = fetch_stock(conn, ep["code"])
            prices, flows = cache[ep["code"]]
            if not prices:
                continue                     # OTC / 無 close 覆蓋
            results.append({**ep,
                            "pre_flow": window_flow(flows, ep["start"], 5, "before"),
                            "post_flow": window_flow(flows, ep["end"], 5, "after"),
                            "ret5": forward_return(prices, ep["end"], 5),
                            "ret10": forward_return(prices, ep["end"], 10)})
    finally:
        conn.close()

    seg = {
        "全樣本": (_stats([r["ret5"] for r in results]),
                  _stats([r["ret10"] for r in results])),
        "處置前外資買超": (_stats([r["ret5"] for r in results if r["pre_flow"] > 0]),
                        _stats([r["ret10"] for r in results if r["pre_flow"] > 0])),
        "處置前外資賣超": (_stats([r["ret5"] for r in results if r["pre_flow"] <= 0]),
                        _stats([r["ret10"] for r in results if r["pre_flow"] <= 0])),
    }
    md = render(today.isoformat(), args.since, episodes, results, seg)
    ANALYSIS_DIR.mkdir(exist_ok=True)
    out = ANALYSIS_DIR / ("disposition_backtest_%s.md" % today.isoformat())
    out.write_text(md, encoding="utf-8")
    print("[done] %d episodes with TWSE data → %s" % (len(results), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
