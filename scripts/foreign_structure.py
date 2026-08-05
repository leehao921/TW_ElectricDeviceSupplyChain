#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""foreign_structure.py — 外資結構背離指標 (alpha #1, 2026-08-05 plan).

外資「現貨 5D 淨買 z」 vs 「TXF 淨 OI z」:
  現貨買 + 期貨空 = hedged_accumulation (偏多背離 — 媒體讀「大空單看空」是誤讀)
  現貨賣 + 期貨多 = distribution_cover  (偏空背離 — 對偶 short 結構)
  同向 aligned_bull / aligned_bear;帶內 neutral。

z 對 120D baseline (排除當日), MIN_HISTORY=20 不足 → insufficient-history
(Golden Rule 0)。產出 analysis/foreign_structure_<date>.md + inbox
topic=foreign-structure (report_path → Discord 全文推送)。

launchd: com.lulala.foreign-structure Mon-Fri 16:30 (法人/OI 落地後)。
Plan: docs/plans/2026-08-05-foreign-structure-regime.md
"""
from __future__ import annotations

import datetime as dt
import math
import os
import sys
from pathlib import Path

TZ_TPE = dt.timezone(dt.timedelta(hours=8))
REPO = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = REPO / "analysis"
MIN_HISTORY = 20
BASELINE_DAYS = 120
Z_BAND = 0.5


# ------------------------------------------------------------------ #
# Pure
# ------------------------------------------------------------------ #
def zscore(value, baseline):
    """z vs baseline;樣本不足/退化 → (None, note)。"""
    n = len(baseline)
    if n < MIN_HISTORY:
        return None, "insufficient-history(n=%d)" % n
    mean = sum(baseline) / n
    var = sum((x - mean) ** 2 for x in baseline) / n
    std = math.sqrt(var)
    if std < 1e-9:
        return None, "degenerate-baseline(std~0)"
    return (value - mean) / std, None


def rolling_sum(series, window=5):
    """[(date, v)] → [(date, 近 window 日累計)]。"""
    out = []
    for i, (d, _) in enumerate(series):
        lo = max(0, i - window + 1)
        out.append((d, sum(v for _, v in series[lo:i + 1])))
    return out


def classify(spot_z, fut_z, band=Z_BAND):
    if spot_z is None or fut_z is None:
        return "insufficient-history"
    if spot_z >= band and fut_z <= -band:
        return "hedged_accumulation"
    if spot_z <= -band and fut_z >= band:
        return "distribution_cover"
    if spot_z >= band and fut_z >= band:
        return "aligned_bull"
    if spot_z <= -band and fut_z <= -band:
        return "aligned_bear"
    return "neutral"


_LABELS = {
    "hedged_accumulation": "偏多背離 — 現貨吸籌 + 期貨對沖(空單≠看空)",
    "distribution_cover": "偏空背離 — 現貨出貨 + 期貨回補掩護 (short 結構)",
    "aligned_bull": "同向偏多 — 現貨買 + 期貨翻多",
    "aligned_bear": "同向偏空 — 現貨賣 + 期貨加空",
    "neutral": "中性 — 帶內無背離",
    "insufficient-history": "樣本不足,z 不輸出",
}


def render_report(date, regime, rows, spot_note, fut_note):
    md = "# 外資結構背離 (foreign_structure 自動產生)\n\n"
    md += "**日期:** %s\n**判定:** `%s` — %s\n\n" % (date, regime, _LABELS.get(regime, ""))
    md += ("> 定義: 外資現貨 5D 淨買 z vs TXF 淨 OI z (各對 %dD baseline, 排除當日)。\n"
           "> |z|≥%.1f 才觸發分類;期貨空單搭配現貨買超是對沖倉結構,非方向性看空。\n\n"
           % (BASELINE_DAYS, Z_BAND))
    if rows:
        md += "## 近 10 日\n\n| 日期 | 現貨 5D 淨買(億) | spot z | TXF 淨 OI(口) | fut z |\n|---|--:|--:|--:|--:|\n"
        for r in rows[-10:]:
            md += "| %s | %s | %s | %s | %s |\n" % (
                r["date"],
                "%.0f" % (r["spot_5d"] / 1e8),
                "%.2f" % r["spot_z"] if r.get("spot_z") is not None else "—",
                "{:,}".format(int(r["fut_net"])),
                "%.2f" % r["fut_z"] if r.get("fut_z") is not None else "—")
    md += "\n## Verification log\n\n"
    md += "- spot z: %s\n" % (spot_note or "OK (n>=%d)" % MIN_HISTORY)
    md += "- fut z: %s\n" % (fut_note or "OK (n>=%d)" % MIN_HISTORY)
    md += "- 慣例: MIN_HISTORY=%d, baseline 排除當日, std<1e-9 退化不輸出。\n" % MIN_HISTORY
    return md


# ------------------------------------------------------------------ #
# I/O
# ------------------------------------------------------------------ #
def _db():
    import psycopg2
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user="tmf", password=os.environ.get("DB_PASSWORD", "tmf_dev_2026"),
        dbname="tmf_market_data")


def fetch_spot(conn, days=BASELINE_DAYS + 40):
    """外資現貨淨買「金額」= foreign_net(股數) × close_price。
    close_price 只覆蓋 TWSE 上市 (OTC=0 排除) — 上市外資流向為主體,已足。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT date, sum(foreign_net * close_price) FILTER (WHERE close_price > 0) "
        "FROM institutional_stock WHERE date >= CURRENT_DATE - %s "
        "GROUP BY 1 ORDER BY 1", (days,))
    rows = [(d.isoformat(), float(v)) for d, v in cur.fetchall() if v is not None]
    cur.close()
    return rows


def fetch_futures(conn, days=BASELINE_DAYS + 40):
    cur = conn.cursor()
    cur.execute(
        "SELECT settle_date, net_oi FROM futures_oi_daily "
        "WHERE participant_type='外資' AND underlying='TXF' "
        "AND settle_date >= CURRENT_DATE - %s ORDER BY 1", (days,))
    rows = [(d.isoformat(), float(v)) for d, v in cur.fetchall()]
    cur.close()
    return rows


def push_inbox(summary, date, report_path):
    import subprocess
    fields = ["ts", dt.datetime.now(TZ_TPE).isoformat(), "from", "foreign_structure",
              "topic", "foreign-structure", "tags", "foreign-structure,daily",
              "as_of", date, "msg", summary, "report_path", str(report_path)]
    r = subprocess.run(["redis-cli", "XADD", "claude:inbox", "*", *fields],
                       capture_output=True, text=True, timeout=10)
    return r.returncode == 0


def main():
    conn = _db()
    try:
        spot = fetch_spot(conn)
        fut = fetch_futures(conn)
    finally:
        conn.close()
    if not spot or not fut:
        print("[error] no data (spot=%d fut=%d)" % (len(spot), len(fut)), file=sys.stderr)
        return 1

    spot5 = rolling_sum(spot, 5)
    rows = []
    fut_map = dict(fut)
    for i, (d, s5) in enumerate(spot5):
        if d not in fut_map:
            continue
        s_z, _ = zscore(s5, [v for _, v in spot5[max(0, i - BASELINE_DAYS):i]])
        f_hist = [v for fd, v in fut if fd < d][-BASELINE_DAYS:]
        f_z, _ = zscore(fut_map[d], f_hist)
        rows.append({"date": d, "spot_5d": s5, "spot_z": s_z,
                     "fut_net": fut_map[d], "fut_z": f_z})
    if not rows:
        print("[error] no overlapping dates", file=sys.stderr)
        return 1

    latest = rows[-1]
    _, spot_note = zscore(latest["spot_5d"],
                          [r["spot_5d"] for r in rows[-BASELINE_DAYS - 1:-1]])
    f_hist = [v for fd, v in fut if fd < latest["date"]][-BASELINE_DAYS:]
    _, fut_note = zscore(latest["fut_net"], f_hist)
    regime = classify(latest["spot_z"], latest["fut_z"])

    date = latest["date"]
    md = render_report(date, regime, rows, spot_note, fut_note)
    ANALYSIS_DIR.mkdir(exist_ok=True)
    out = ANALYSIS_DIR / ("foreign_structure_%s.md" % date)
    out.write_text(md, encoding="utf-8")

    summary = ("外資結構 %s: %s | 現貨5D %s億 (z=%s) / TXF淨OI %s口 (z=%s)" % (
        date, regime, "%.0f" % (latest["spot_5d"] / 1e8),
        "%.2f" % latest["spot_z"] if latest["spot_z"] is not None else "n/a",
        "{:,}".format(int(latest["fut_net"])),
        "%.2f" % latest["fut_z"] if latest["fut_z"] is not None else "n/a"))
    push_inbox(summary, date, out)
    print("[%s] %s → %s" % (dt.datetime.now(TZ_TPE).strftime("%F %T"), regime, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
