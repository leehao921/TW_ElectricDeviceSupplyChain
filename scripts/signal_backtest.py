#!/usr/bin/env python3
"""四家族系統性驗證 — S3 乖離過熱 / S4 外資撤投信頂 / L4 左側竭盡 / L3S6 外資結構州.

Daily event harness (plan 2026-08-28 Phase B): 2025-01 起多 regime
(2025 牛市 + 2025-04 關稅崩跌 + 2026-04/07 兩次崩跌)。
護欄: rolling 分位需滿窗、同股 10 日 de-cluster、基準=同日市場中位逐日配對、
n<20 INSUFFICIENT、按半年分段檢 regime 穩定性、無交易指令。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")
HORIZONS = (5, 20)


# --------------------------------------------------------------------------- #
# pure functions
# --------------------------------------------------------------------------- #
def rolling_pct_events(s: pd.Series, window: int = 252, pct: float = 0.98,
                       min_history: int = 252) -> pd.DatetimeIndex:
    """值 ≥ 自身 rolling window 分位 (滿窗才判, 排除自身即時膨脹用 shift)."""
    thr = s.shift(1).rolling(window, min_periods=min_history).quantile(pct)
    return s.index[(s > thr) & thr.notna()]  # 嚴格大於: 常數序列不產生退化事件


def decluster(events: pd.DataFrame, gap_days: int = 10) -> pd.DataFrame:
    """同 symbol gap_days 內只留首次 (calendar days)."""
    out = []
    for sym, g in events.sort_values("date").groupby("symbol"):
        last = None
        for _, row in g.iterrows():
            if last is None or (row["date"] - last).days >= gap_days:
                out.append(row)
                last = row["date"]
    return pd.DataFrame(out).reset_index(drop=True) if out else pd.DataFrame(columns=events.columns)


def forward_ret(close: pd.DataFrame, symbol: str, d: pd.Timestamp, n: int) -> float | None:
    """事件日收盤 → 第 n 個交易日收盤 (%); 不足 → None (不截斷, 日頻嚴格)."""
    if symbol not in close.columns or d not in close.index:
        return None
    pos = close.index.get_loc(d)
    if pos + n >= len(close.index):
        return None
    a, b = close[symbol].iloc[pos], close[symbol].iloc[pos + n]
    if pd.isna(a) or pd.isna(b) or a == 0:
        return None
    return (b / a - 1) * 100


def event_stats(ev: pd.DataFrame) -> dict:
    """ev: columns [ret, mkt] — 逐事件與同日市場中位配對."""
    ev = ev.dropna(subset=["ret", "mkt"])
    if ev.empty:
        return {"n": 0}
    ex = ev.ret - ev.mkt
    return {"n": int(len(ev)), "median": float(ev.ret.median()),
            "excess_median": float(ex.median()),
            "hit_beat": float((ex > 0).mean())}


def grade_daily(st: dict, min_n: int = 20, edge: float = 1.0) -> str:
    """VALIDATED: n≥20 且 |超額中位|≥1.0% 且 beat-rate 偏離 50% ≥ 15pp."""
    if st.get("n", 0) < min_n:
        return "INSUFFICIENT"
    dev = abs(st["hit_beat"] - 0.5)
    if abs(st["excess_median"]) >= edge and dev >= 0.15:
        return "VALIDATED"
    if abs(st["excess_median"]) >= edge or dev >= 0.15:
        return "WEAK"
    return "NO-EDGE"


# --------------------------------------------------------------------------- #
# study
# --------------------------------------------------------------------------- #
def run_family(name: str, events: pd.DataFrame, close: pd.DataFrame,
               mkt_fwd: dict, horizons=HORIZONS) -> dict:
    events = decluster(events)
    res = {"name": name, "n_events": len(events), "stats": {}, "by_half": {}}
    for h in horizons:
        rows = []
        for _, e in events.iterrows():
            r = forward_ret(close, e["symbol"], e["date"], h)
            m = mkt_fwd[h].get(e["date"])
            if r is not None and m is not None:
                rows.append({"ret": r, "mkt": m, "date": e["date"]})
        ev = pd.DataFrame(rows)
        st = event_stats(ev) if not ev.empty else {"n": 0}
        st["grade"] = grade_daily(st)
        res["stats"][h] = st
        if h == horizons[-1] and not ev.empty:  # 分段穩定性 (半年)
            ev["half"] = ev.date.dt.year.astype(str) + "H" + ((ev.date.dt.month > 6) + 1).astype(str)
            for hf, g in ev.groupby("half"):
                res["by_half"][hf] = event_stats(g)
    return res


def main() -> int:
    import psycopg2
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    px = pd.read_sql("""SELECT symbol, ts::date d, close FROM stock_daily_ohlcv
                        WHERE symbol ~ '^[1-9][0-9]{3}$' ORDER BY 1,2""",
                     conn, parse_dates=["d"])
    close = px.pivot(index="d", columns="symbol", values="close")
    # 市場基準: 同日全市場前瞻中位 (逐日配對)
    mkt_fwd = {}
    for h in HORIZONS:
        f = (close.shift(-h) / close - 1) * 100
        mkt_fwd[h] = f.median(axis=1).to_dict()

    inst = pd.read_sql("""SELECT date, symbol, foreign_net*close_price AS fval,
                                 trust_net*close_price AS tval
                          FROM institutional_stock
                          WHERE close_price > 0 AND symbol ~ '^[1-9][0-9]{3}$'""",
                       conn, parse_dates=["date"])
    f20 = (inst.pivot_table(index="date", columns="symbol", values="fval", aggfunc="sum")
               .reindex(close.index).rolling(20).sum())
    t20 = (inst.pivot_table(index="date", columns="symbol", values="tval", aggfunc="sum")
               .reindex(close.index).rolling(20).sum())
    f5 = (inst.pivot_table(index="date", columns="symbol", values="fval", aggfunc="sum")
              .reindex(close.index).rolling(5).sum())

    def zmat(m: pd.DataFrame, win=120, minp=60):
        mu = m.shift(1).rolling(win, min_periods=minp).mean()
        sd = m.shift(1).rolling(win, min_periods=minp).std()
        return (m - mu) / sd.replace(0, np.nan)

    zf, zt = zmat(f20), zmat(t20)

    families = []

    # S3 乖離過熱: dev vs MA20 ≥ 自身 252 日 98pct
    dev = (close / close.rolling(20).mean() - 1)
    ev_rows = []
    for sym in dev.columns:
        for d in rolling_pct_events(dev[sym].dropna()):
            ev_rows.append({"symbol": sym, "date": d})
    families.append(run_family("S3 乖離過熱 (dev≥自身252日98pct)",
                               pd.DataFrame(ev_rows), close, mkt_fwd))

    # S4 外資撤投信頂: zf ≤ -1 且 zt ≥ +1
    mask = (zf <= -1) & (zt >= 1)
    ev4 = [{"symbol": c, "date": d} for d in mask.index for c in mask.columns
           if mask.at[d, c] is True or (mask.at[d, c] == True)]  # noqa: E712
    families.append(run_family("S4 外資撤投信頂 (f20 z≤-1 ∧ t20 z≥+1)",
                               pd.DataFrame(ev4), close, mkt_fwd))

    # L4 左側竭盡: 距 252 日高 ≤ -20% ∧ 前 20D 外資淨賣 ∧ 5D 轉正
    dd = close / close.rolling(252, min_periods=200).max() - 1
    prior_f20 = f20.shift(5)
    mask_l4 = (dd <= -0.20) & (prior_f20 < 0) & (f5 > 0) & (f5.shift(1) <= 0)
    ev_l4 = [{"symbol": c, "date": d} for d in mask_l4.index for c in mask_l4.columns
             if mask_l4.at[d, c] == True]  # noqa: E712
    families.append(run_family("L4 左側竭盡 (距高-20%∧前賣∧5D轉正)",
                               pd.DataFrame(ev_l4), close, mkt_fwd))

    # L3/S6 外資結構州 → TXF 次日/5日 (獨立小樣本)
    fs = pd.read_sql("""SELECT settle_date d, net_oi FROM futures_oi_daily
                        WHERE participant_type='外資' AND underlying='TXF' ORDER BY 1""",
                     conn, parse_dates=["d"]).set_index("d")["net_oi"]
    spot5 = inst.groupby("date").fval.sum().rolling(5).sum() / 1e8
    txf = pd.read_sql("""SELECT bucket::date d, last(close, bucket) c FROM ohlcv_1m_txf
                         WHERE symbol='TXF' GROUP BY 1 ORDER BY 1""",
                      conn, parse_dates=["d"]).set_index("d")["c"]
    common = fs.index.intersection(spot5.index).intersection(txf.index)
    sz = (spot5[common] - spot5[common].rolling(60, min_periods=20).mean()) / \
         spot5[common].rolling(60, min_periods=20).std()
    fz = (fs[common] - fs[common].rolling(60, min_periods=20).mean()) / \
         fs[common].rolling(60, min_periods=20).std()
    state = pd.Series("neutral", index=common)
    state[(sz > 0.5) & (fz < -0.5)] = "hedged_accumulation"
    state[(sz < -0.5) & (fz > 0.5)] = "distribution_cover"
    txf_fwd1 = (txf.shift(-1) / txf - 1) * 100
    txf_fwd5 = (txf.shift(-5) / txf - 1) * 100
    l3_lines = []
    for st_name, g in state.groupby(state):
        r1 = txf_fwd1[g.index].dropna()
        r5 = txf_fwd5[g.index].dropna()
        l3_lines.append(f"| {st_name} | {len(g)} | {r1.median():+.2f}% | {r5.median():+.2f}% |"
                        if len(r1) else f"| {st_name} | {len(g)} | — | — |")

    # --- 報告 ---
    lines = ["# 多空訊號家族系統性驗證", "",
             f"**日期:** {datetime.now():%Y-%m-%d} · **樣本:** {close.index[0]:%Y-%m-%d}–"
             f"{close.index[-1]:%Y-%m-%d} ({len(close)} 交易日, {close.shape[1]} 檔) — "
             "含 2025 牛市與 2025-04/2026-04/2026-07 三次崩跌 (多 regime)", "",
             "**Grade:** VALIDATED = n≥20 ∧ |超額中位|≥1.0% ∧ beat 偏離≥15pp;基準=同日全市場中位逐日配對", ""]
    for fam in families:
        lines += [f"## {fam['name']}", "", f"事件 (de-clustered): **{fam['n_events']}**", "",
                  "| 前瞻 | n | 事件中位% | 超額中位% | beat 率 | 判定 |", "|---|---|---|---|---|---|"]
        for h in HORIZONS:
            st = fam["stats"][h]
            if st["n"] == 0:
                lines.append(f"| +{h}D | 0 | — | — | — | INSUFFICIENT |")
                continue
            lines.append(f"| +{h}D | {st['n']} | {st['median']:+.2f} | "
                         f"{st['excess_median']:+.2f} | {st['hit_beat']*100:.0f}% | {st['grade']} |")
        if fam["by_half"]:
            seg = " · ".join(f"{k}: {v['excess_median']:+.1f}%(n={v['n']})"
                             for k, v in sorted(fam["by_half"].items()) if v.get("n"))
            lines += ["", f"分段 (+{HORIZONS[-1]}D 超額中位): {seg}", ""]
    lines += ["## L3/S6 外資結構州 → TXF (n 小, 最高 WEAK 級)", "",
              "| 州 | 日數 | 次日中位 | +5日中位 |", "|---|---|---|---|"] + l3_lines
    lines += ["", "## Verification log", "```",
              f"px: stock_daily_ohlcv {close.shape}; inst: institutional_stock (close>0 金額)",
              "S3: dev(close/MA20-1) >= shift(1).rolling(252,min252).quantile(.98)",
              "S4: 20D 金額流 z (win120,min60, shift(1) 基準) 外資<=-1 ∧ 投信>=+1",
              "L4: dd(close/rolling252max-1)<=-20% ∧ f20.shift(5)<0 ∧ f5>0 ∧ f5.shift(1)<=0",
              "L3S6: spot5/futOI z (win60,min20) ±0.5 州分類 (foreign_structure 同款), TXF=ohlcv_1m_txf",
              "de-cluster 同股 10 日; 前瞻不足 n 日 → 剔除 (不截斷)", "```"]
    report = "\n".join(lines)
    out = REPO / "analysis" / f"signal_validation_{datetime.now():%Y%m%d}.md"
    out.write_text(report)
    print(report)
    try:
        import redis
        summary = " | ".join(
            f"{f['name'][:10]}: n={f['n_events']}, +{HORIZONS[0]}D {f['stats'][HORIZONS[0]].get('grade','-')}"
            for f in families)
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "signal_backtest", "topic": "signal-ledger",
            "tags": "validation,backtest", "as_of": datetime.now().strftime("%Y-%m-%d"),
            "msg": f"四家族驗證完成: {summary}", "report_path": f"analysis/{out.name}"})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
