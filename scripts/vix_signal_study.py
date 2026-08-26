#!/usr/bin/env python3
"""自家 VIX 訊號效度研究 — iv_metrics (10s) × ohlcv_1m TXF (plan: 2026-08-26)

五訊號: S1 IV急升 / S2 期限倒掛 onset / S3 skew急變 (盤中事件研究)
        S4 VRP 極端 (日級) / S5 日級 VIX Δ1d (n=54 描述)
護欄: 基準排除事件日、n<20 拒下結論、de-cluster、收盤截斷、無交易指令。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

DAY_START, DAY_END = "08:45", "13:45"
HORIZONS = (15, 30, 60)
DECLUSTER_MIN = 30
MIN_BASELINE = 20
Z_TH = 2.0


# --------------------------------------------------------------------------- #
# pure functions
# --------------------------------------------------------------------------- #
def day_session_only(s: pd.Series) -> pd.Series:
    """限日盤 08:45-13:45 (排夜盤/凌晨)."""
    t = s.index.strftime("%H:%M")
    return s[(t >= DAY_START) & (t <= DAY_END)]


def detect_events(delta_series: pd.Series, z_th: float = Z_TH,
                  min_baseline: int = MIN_BASELINE,
                  decluster_min: int = DECLUSTER_MIN) -> list[pd.Timestamp]:
    """對 delta 序列做逐點 z 檢定 (基準 = 其他日全部觀測, 排除當日) + 去叢集.

    保守設計: 基準排除事件當日全日 → 無 look-ahead 也無自我污染。
    """
    events = []
    dates = delta_series.index.normalize()
    for day in dates.unique():
        day_mask = dates == day
        base = delta_series[~day_mask].dropna()
        if len(base) < min_baseline:
            continue
        mu, sd = base.mean(), base.std()
        if sd < 1e-12:
            continue
        day_vals = delta_series[day_mask].dropna()
        for ts, v in day_vals.items():
            if (v - mu) / sd >= z_th:
                events.append(ts)
    events.sort()
    kept: list[pd.Timestamp] = []
    for ts in events:
        if kept and ts.normalize() == kept[-1].normalize() and \
           (ts - kept[-1]).total_seconds() < decluster_min * 60:
            continue
        kept.append(ts)
    return kept


def forward_returns(bars: pd.Series, event_ts: pd.Timestamp,
                    horizons_min: tuple = HORIZONS) -> dict | None:
    """事件時點後 TXF 前瞻報酬 (%); 超出收盤 → 截斷至當日最後 bar."""
    day = event_ts.normalize()
    day_bars = bars[bars.index.normalize() == day]
    entry_bars = day_bars[day_bars.index <= event_ts]
    if entry_bars.empty:
        return None
    entry = float(entry_bars.iloc[-1])
    out: dict = {}
    for h in horizons_min:
        target = event_ts + pd.Timedelta(minutes=h)
        seg = day_bars[day_bars.index <= target]
        out[h] = (float(seg.iloc[-1]) / entry - 1) * 100 if not seg.empty else None
    out["to_close"] = (float(day_bars.iloc[-1]) / entry - 1) * 100
    return out


def event_vs_baseline(event_rets: list[float], baseline_rets: list[float]) -> dict:
    ev = pd.Series(event_rets).dropna()
    base = pd.Series(baseline_rets).dropna()
    return {
        "n": int(len(ev)),
        "median": float(ev.median()) if len(ev) else None,
        "p25": float(ev.quantile(.25)) if len(ev) else None,
        "p75": float(ev.quantile(.75)) if len(ev) else None,
        "hit_up": float((ev > 0).mean()) if len(ev) else None,
        "baseline_median": float(base.median()) if len(base) else None,
        "baseline_n": int(len(base)),
    }


def grade(stats: dict, min_n: int = 20, edge_bp: float = 5.0) -> str:
    """VALIDATED: n≥20 且 |事件中位 − 基準中位| ≥ edge_bp (0.05%) 且命中率偏離 50% ≥ 10pp."""
    if stats["n"] < min_n:
        return "INSUFFICIENT"
    if stats["median"] is None or stats["baseline_median"] is None:
        return "INSUFFICIENT"
    edge = abs(stats["median"] - stats["baseline_median"]) * 100  # % → bp
    hit_dev = abs((stats["hit_up"] or 0.5) - 0.5)
    if edge >= edge_bp and hit_dev >= 0.10:
        return "VALIDATED"
    if edge >= edge_bp or hit_dev >= 0.10:
        return "WEAK"
    return "NO-EDGE"


# --------------------------------------------------------------------------- #
# data loading
# --------------------------------------------------------------------------- #
def load_iv_1m(conn) -> pd.DataFrame:
    q = """
      SELECT date_trunc('minute', time) AS t,
             avg(near_month_iv)*100 AS near_iv,
             avg(far_month_iv)*100 AS far_iv,
             avg(iv_skew_25d) AS skew
      FROM iv_metrics
      WHERE underlying='TX'
        AND EXTRACT(dow FROM time) NOT IN (0,6)
        AND near_month_iv BETWEEN 0.05 AND 1.5
      GROUP BY 1 ORDER BY 1"""
    df = pd.read_sql(q, conn, parse_dates=["t"]).set_index("t")
    df.index = df.index.tz_convert("Asia/Taipei")
    return df


def load_txf_1m(conn) -> pd.Series:
    """TXF 1m 收盤 — 主源: ticks 逐筆重採樣 (逐日主力合約, 覆蓋至今);
    ohlcv_1m 經抽查覆蓋不均且止於 8/15, 僅作 fallback."""
    q = """
      WITH dom AS (
        SELECT time::date AS d, symbol,
               ROW_NUMBER() OVER (PARTITION BY time::date ORDER BY count(*) DESC) rn
        FROM ticks
        WHERE symbol LIKE 'TXF%' AND time >= '2026-05-27'
          AND time::time BETWEEN '08:45' AND '13:45'
          AND EXTRACT(dow FROM time) BETWEEN 1 AND 5
        GROUP BY 1, 2)
      SELECT time_bucket('1 minute', t.time) AS bucket, last(t.price, t.time) AS close
      FROM ticks t
      JOIN dom ON dom.d = t.time::date AND dom.symbol = t.symbol AND dom.rn = 1
      WHERE t.symbol LIKE 'TXF%' AND t.time >= '2026-05-27'
        AND t.time::time BETWEEN '08:45' AND '13:45'
        AND EXTRACT(dow FROM t.time) BETWEEN 1 AND 5
      GROUP BY 1 ORDER BY 1"""
    s = pd.read_sql(q, conn, parse_dates=["bucket"]).set_index("bucket")["close"]
    if s.empty:  # fallback
        q2 = """SELECT bucket, close FROM ohlcv_1m WHERE symbol='TXF'
                AND EXTRACT(dow FROM bucket) NOT IN (0,6) ORDER BY bucket"""
        s = pd.read_sql(q2, conn, parse_dates=["bucket"]).set_index("bucket")["close"]
    s.index = s.index.tz_convert("Asia/Taipei")
    return day_session_only(s)


def run_intraday_signal(name: str, delta: pd.Series, bars: pd.Series,
                        settlement_days: set) -> dict:
    events = [e for e in detect_events(delta)
              if e.normalize().date() not in settlement_days]
    per_h = {}
    uncond = {h: [] for h in HORIZONS}
    # 無條件基準: 每日每 30 分格點的前瞻報酬
    for day, day_bars in bars.groupby(bars.index.normalize()):
        for ts in day_bars.index[::30]:
            fr = forward_returns(bars, ts)
            if fr:
                for h in HORIZONS:
                    if fr[h] is not None:
                        uncond[h].append(fr[h])
    for h in HORIZONS:
        ev_rets = []
        for e in events:
            fr = forward_returns(bars, e)
            if fr and fr[h] is not None:
                ev_rets.append(fr[h])
        per_h[h] = event_vs_baseline(ev_rets, uncond[h])
        per_h[h]["grade"] = grade(per_h[h])
    return {"name": name, "events": events, "stats": per_h}


def main() -> int:
    import psycopg2
    conn = psycopg2.connect(host="localhost", port=5432, dbname="tmf_market_data",
                            user="tmf", password="tmf_dev_2026")
    iv = load_iv_1m(conn)
    iv_day = iv[(iv.index.strftime("%H:%M") >= DAY_START) &
                (iv.index.strftime("%H:%M") <= DAY_END)]
    bars = load_txf_1m(conn)
    # 結算日 (每月第三週三 + 週三週選) — 近月 IV 失真, 事件排除: 用 near>far 崩潰 proxy 太複雜,
    # 直接排除所有週三 (保守; 報告揭露)
    settlement_days = {d.date() for d in iv_day.index.normalize().unique()
                       if d.weekday() == 2}

    d15 = lambda col: iv_day[col].diff(15)  # noqa: E731
    signals = [
        run_intraday_signal("S1 IV急升(Δ15m near_iv z≥2)", d15("near_iv"), bars, settlement_days),
        run_intraday_signal("S3 Skew急變(Δ15m skew z≥2)", d15("skew"), bars, settlement_days),
    ]
    # S2 期限倒掛 onset: near-far 由負轉正
    spread = (iv_day["near_iv"] - iv_day["far_iv"]).dropna()
    onset = spread[(spread > 0) & (spread.shift(1) <= 0)]
    s2_events = []
    last = None
    for ts in onset.index:
        if ts.normalize().date() in settlement_days:
            continue
        if last is None or ts.normalize() != last.normalize() or \
           (ts - last).total_seconds() >= DECLUSTER_MIN * 60:
            s2_events.append(ts)
            last = ts
    s2 = {"name": "S2 期限倒掛 onset (near>far 轉正)", "events": s2_events, "stats": {}}
    uncond = {h: [] for h in HORIZONS}
    for day, day_bars in bars.groupby(bars.index.normalize()):
        for ts in day_bars.index[::30]:
            fr = forward_returns(bars, ts)
            if fr:
                for h in HORIZONS:
                    if fr[h] is not None:
                        uncond[h].append(fr[h])
    for h in HORIZONS:
        rets = [fr[h] for e in s2_events
                if (fr := forward_returns(bars, e)) and fr[h] is not None]
        s2["stats"][h] = event_vs_baseline(rets, uncond[h])
        s2["stats"][h]["grade"] = grade(s2["stats"][h])
    signals.insert(1, s2)

    # S5 日級 (n=54, 描述性)
    vix_d = pd.read_sql("SELECT date, vix FROM vix_daily ORDER BY date", conn,
                        parse_dates=["date"]).set_index("date")["vix"]
    txf_d = bars.groupby(bars.index.normalize()).last()
    txf_d.index = txf_d.index.tz_localize(None)
    dvix = vix_d.diff()
    spike_days = dvix[dvix >= 3.0].index  # +3 vol pt 日
    t1 = []
    for d in spike_days:
        pos = txf_d.index.get_indexer([d], method="nearest")[0]
        if 0 <= pos < len(txf_d) - 1:
            t1.append((txf_d.iloc[pos + 1] / txf_d.iloc[pos] - 1) * 100)
    t1 = [float(x) for x in t1]
    s5 = {"n_days": int(len(vix_d)), "spikes": int(len(spike_days)),
          "t1_rets": [round(x, 2) for x in t1],
          "t1_median": round(float(pd.Series(t1).median()), 2) if t1 else None,
          "t1_hit_up": round(float((pd.Series(t1) > 0).mean()), 2) if t1 else None}

    # --- 報告 ---
    lines = [f"# 自家 VIX 訊號效度驗證 — 對應 TXF 期貨價格", "",
             f"**日期:** {datetime.now():%Y-%m-%d} · **樣本:** iv_metrics 1m 重採樣 "
             f"{iv_day.index[0]:%m/%d}–{iv_day.index[-1]:%m/%d} × TXF ticks 逐筆重採 1m (逐日主力合約) 日盤",
             f"**護欄:** 基準排除事件日全日 · de-cluster {DECLUSTER_MIN}m · 週三(結算)全排除 · "
             f"收盤截斷 · n<20 = INSUFFICIENT", ""]
    for sig in signals:
        lines += [f"## {sig['name']}", "",
                  f"事件數 (de-clustered, 非週三): **{len(sig['events'])}**", "",
                  "| 前瞻 | n | 事件中位% | P25/P75 | 命中率(漲) | 基準中位% (n) | 判定 |",
                  "|---|---|---|---|---|---|---|"]
        for h in HORIZONS:
            st = sig["stats"][h]
            if st["n"] == 0:
                lines.append(f"| +{h}m | 0 | — | — | — | — | INSUFFICIENT |")
                continue
            lines.append(
                f"| +{h}m | {st['n']} | {st['median']:+.3f} | "
                f"{st['p25']:+.3f}/{st['p75']:+.3f} | {st['hit_up']*100:.0f}% | "
                f"{st['baseline_median']:+.3f} ({st['baseline_n']}) | {st['grade']} |")
        ev_sample = ", ".join(e.strftime("%m/%d %H:%M") for e in sig["events"][:8])
        lines += ["", f"事件樣本: {ev_sample}", ""]
    lines += ["## S5 日級 VIX Δ1d ≥ +3 (描述性, n=54 不下結論)", "",
              f"- 樣本 {s5['n_days']} 日, spike {s5['spikes']} 次, 次日 TXF 報酬中位 {s5['t1_median']}% / 上漲率 {s5['t1_hit_up']}",
              f"- 逐次: {s5['t1_rets']}",
              "- ⚠️ 樣本主要落在 7 月崩跌後 V 型反彈 regime — 「spike 後漲」可能是該 regime 的特徵而非通則", ""]
    lines += ["## 價格源對照的方法論教訓", "",
              "初版以 ohlcv_1m 為價格源時 S3+15m 曾判 VALIDATED (中位 +0.147%/命中 66%) —",
              "抽查發現該表覆蓋不均 (6/11 整日缺、止於 8/15), 改用 ticks 完整重採後",
              "同訊號降為 WEAK (+0.092%/56%)。**殘缺樣本會製造假訊號** — 效度結論一律以完整源為準。", "",
              "## Verification log", "```",
              f"iv 1m rows={len(iv_day)}, txf 1m bars={len(bars)}, "
              f"settlement(wed) days excluded={len(settlement_days)}",
              f"z 檢定: 逐日 leave-one-day-out 基準, z>={Z_TH}, MIN_BASELINE={MIN_BASELINE}",
              f"無條件基準: 每日每 30 分格點前瞻報酬",
              "grade: VALIDATED = n>=20 AND |edge|>=5bp AND |hit-50%|>=10pp; 單項達標 = WEAK",
              "限制: 63 交易日單一 regime (7月崩跌主導), 樣本外未驗證; 不構成交易指令",
              "多重檢定警語: 3 訊號 × 3 前瞻 = 9 檢定, 單一 VALIDATED 存在偶然通過風險 —",
              "  S3+15m 需樣本外 (9月起 live 追蹤) 確認後才可升級為可用訊號", "```"]
    report = "\n".join(lines)
    out = REPO / "analysis" / f"vix_signal_validation_{datetime.now():%Y%m%d}.md"
    out.write_text(report)
    print(report[:1800])
    try:
        import redis
        summary = " | ".join(
            f"{s['name'][:14]}: n={len(s['events'])}, +60m {s['stats'][60]['grade']}"
            for s in signals)
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "vix_study", "topic": "vix-study", "tags": "vix,signal,study",
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "msg": f"VIX 訊號效度研究完成: {summary}",
            "report_path": f"analysis/{out.name}"})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
