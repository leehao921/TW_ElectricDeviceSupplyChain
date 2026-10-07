#!/usr/bin/env python3
"""skew 收斂作為上漲領先指標 — 日級回測 (plan: docs/plans/2026-10-07-skew-converge-study.md)

訊號 A: 前月 TXO 25Δ skew 3 日變化 ≤ −1.0 vol-pt (put 溢價收斂)
訊號 B: skew < 0 (call 比 put 貴)
結果: TXF 日盤收盤 T+1/3/5 報酬 vs 非事件日基準;全樣本 Spearman(Δ3 skew, 未來報酬)。
護欄: n<20 不下結論、事件 de-cluster、無分布性形容詞、無交易指令。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
HORIZONS = (1, 3, 5)
LOOKBACK = 3
THRESHOLD = -1.0          # vol-pt
GAP = 3                   # de-cluster: 事件間隔 < 3 交易日合併
MIN_DTE = 5
MIN_N = 20
FIX_DATE = pd.Timestamp("2026-10-05")   # IV 輸入改做市商 mid (database e3ee0fd)


# --------------------------------------------------------------------------- #
# pure functions
# --------------------------------------------------------------------------- #
def front_expiry(expiries, day: pd.Timestamp, min_dte: int = MIN_DTE):
    """距到期 ≥ min_dte 日曆天的最近到期 (避開到期前雜訊);無則 None。"""
    ok = sorted(e for e in expiries if (pd.Timestamp(e) - day).days >= min_dte)
    return ok[0] if ok else None


def _decluster(cands: pd.Index, index: pd.Index, gap: int) -> pd.Index:
    kept, last = [], None
    for t in cands:
        pos = index.get_loc(t)
        if last is None or pos - last >= gap:
            kept.append(t)
            last = pos
    return pd.Index(kept)


def detect_events(skew: pd.Series, lookback: int = LOOKBACK, threshold: float = THRESHOLD,
                  gap: int = GAP) -> pd.Index:
    delta = skew - skew.shift(lookback)
    return _decluster(delta.index[delta <= threshold], skew.index, gap)


def level_events(skew: pd.Series, below: float = 0.0, gap: int = GAP) -> pd.Index:
    return _decluster(skew.index[skew < below], skew.index, gap)


def forward_returns(close: pd.Series, t, horizons=HORIZONS) -> dict:
    pos = close.index.get_loc(t)
    out = {}
    for h in horizons:
        out[h] = ((close.iloc[pos + h] / close.iloc[pos] - 1) * 100
                  if pos + h < len(close) else None)
    return out


def summarize(event_rets, base_rets, min_n: int = MIN_N) -> dict:
    ev = pd.Series([r for r in event_rets if r is not None], dtype=float)
    bs = pd.Series([r for r in base_rets if r is not None], dtype=float)
    out = {"n": len(ev),
           "mean": ev.mean() if len(ev) else None,
           "median": ev.median() if len(ev) else None,
           "hit": (ev > 0).mean() if len(ev) else None,
           "base_n": len(bs),
           "base_mean": bs.mean() if len(bs) else None,
           "base_hit": (bs > 0).mean() if len(bs) else None}
    out["verdict"] = ("樣本不足,不下結論" if len(ev) < min_n
                      else "均值差 %+.2f%% vs 基準" % (out["mean"] - out["base_mean"]))
    return out


# --------------------------------------------------------------------------- #
# I/O
# --------------------------------------------------------------------------- #
def load_skew(conn) -> pd.Series:
    """每日 13:00-13:30 前月 TXO skew_25d 平均 (vol-pt)。"""
    df = pd.read_sql("""
        SELECT (time AT TIME ZONE 'Asia/Taipei')::date AS d, expiry,
               avg(skew_25d) * 100 AS skew, count(*) AS n
        FROM iv_metrics
        WHERE product_code = 'TXO' AND skew_25d IS NOT NULL
          AND (time AT TIME ZONE 'Asia/Taipei')::time BETWEEN '13:00' AND '13:30'
        GROUP BY 1, 2""", conn)
    rows = {}
    for d, g in df.groupby("d"):
        day = pd.Timestamp(d)
        fe = front_expiry(list(g.expiry), day)
        if fe:
            rows[day] = float(g.loc[g.expiry == fe, "skew"].iloc[0])
    return pd.Series(rows).sort_index()


def load_close(conn) -> pd.Series:
    df = pd.read_sql("""
        SELECT (bucket AT TIME ZONE 'Asia/Taipei')::date AS d, last(close, bucket) AS c
        FROM ohlcv_1m_txf
        WHERE symbol = 'TXF'
          AND (bucket AT TIME ZONE 'Asia/Taipei')::time BETWEEN '08:45' AND '13:45'
        GROUP BY 1 ORDER BY 1""", conn)
    return pd.Series(df.c.values, index=pd.to_datetime(df.d)).astype(float)


def _fmt(x, f="+.2f"):
    return "n/a" if x is None or pd.isna(x) else format(x, f)


def study(skew: pd.Series, close: pd.Series) -> dict:
    idx = skew.index.intersection(close.index)
    skew, close_al = skew.loc[idx], close
    res = {"days": len(idx), "start": idx.min(), "end": idx.max(), "signals": {}}
    for name, ev in (("A Δ3≤−1.0", detect_events(skew)), ("B skew<0", level_events(skew))):
        ev = [t for t in ev if t in close_al.index]
        base = [t for t in idx if t not in set(ev)]
        per_h = {}
        for h in HORIZONS:
            er = [forward_returns(close_al, t, (h,))[h] for t in ev]
            br = [forward_returns(close_al, t, (h,))[h] for t in base]
            per_h[h] = summarize(er, br)
        res["signals"][name] = {"events": ev, "h": per_h}
    delta = skew - skew.shift(LOOKBACK)
    res["spearman"] = {}
    for h in HORIZONS:
        fwd = pd.Series({t: forward_returns(close_al, t, (h,))[h] for t in idx}, dtype=float)
        pair = pd.concat([delta, fwd], axis=1).dropna()
        res["spearman"][h] = (pair.iloc[:, 0].rank().corr(pair.iloc[:, 1].rank()), len(pair))
    return res


def render(res: dict, skew: pd.Series) -> str:
    L = ["# skew 收斂 → 上漲領先性 日級回測 (%s)" % date.today().isoformat(), "",
         "分析標註,不構成交易指令。樣本 %s → %s,%d 個交易日。" % (
             res["start"].date(), res["end"].date(), res["days"]), ""]
    for name, s in res["signals"].items():
        L.append("## 訊號 %s — 事件 %d 次" % (name, len(s["events"])))
        L.append("事件日: " + (", ".join(t.strftime("%m/%d") for t in s["events"]) or "無"))
        L.append("")
        L.append("| 期間 | n | 事件均值 | 中位 | 上漲比例 | 基準均值 | 基準上漲比例 | 判讀 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for h, o in s["h"].items():
            L.append("| T+%d | %d | %s%% | %s%% | %s | %s%% | %s | %s |" % (
                h, o["n"], _fmt(o["mean"]), _fmt(o["median"]), _fmt(o["hit"], ".0%"),
                _fmt(o["base_mean"]), _fmt(o["base_hit"], ".0%"), o["verdict"]))
        L.append("")
    L.append("## 全樣本 Spearman(Δ3 skew, 未來報酬)")
    L.append("負值 = skew 收斂 (Δ3 為負) 後傾向上漲。")
    L.append("")
    for h, (rho, n) in res["spearman"].items():
        L.append("- T+%d: ρ = %s (n=%d)" % (h, _fmt(rho), n))
    pre = (skew.index < FIX_DATE).sum()
    L += ["", "## Verification log",
          "- skew: iv_metrics product_code=TXO, 13:00-13:30 skew_25d 平均 ×100, 前月 DTE≥%d" % MIN_DTE,
          "- 價格: ohlcv_1m_txf symbol=TXF 日盤 08:45-13:45 最後一根 close",
          "- 訊號 A: Δ%d skew ≤ %.1f vol-pt;B: skew < 0;de-cluster gap=%d 交易日" % (
              LOOKBACK, THRESHOLD, GAP),
          "- 基準: 同期非事件日;n<%d 一律「樣本不足,不下結論」" % MIN_N,
          "- 資料品質: %d/%d 日在 %s 前 (IV 輸入仍可能用到舊成交價, database e3ee0fd 修)" % (
              pre, len(skew), FIX_DATE.date()),
          "- 本報告未使用 σ/罕見/極端/percentile 等分布性形容詞 (Golden Rule 0 未觸發)"]
    return "\n".join(L) + "\n"


def main() -> int:
    import psycopg2
    sys.path.insert(0, str(REPO / "scripts"))
    from ascii_dashboard import DB
    conn = psycopg2.connect(**DB)
    skew, close = load_skew(conn), load_close(conn)
    res = study(skew, close)
    out = REPO / "analysis" / ("skew_converge_study_%s.md" % date.today().isoformat())
    out.write_text(render(res, skew), encoding="utf-8")
    print(out)
    print(render(res, skew))
    return 0


if __name__ == "__main__":
    sys.exit(main())
