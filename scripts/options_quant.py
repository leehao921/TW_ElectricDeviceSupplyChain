#!/usr/bin/env python3
"""TXO 選擇權盤中量化分析 — GEX / IV-RV / term-skew / PCR-OI flow.

Spec: docs/plans/2026-07-09-options-quant-spec.md
Usage: python3 scripts/options_quant.py --date 2026-07-09 --window 09:00-12:00
Read-only vs trading-timescaledb. No trade directives — environment labels only.
"""
import argparse
import os
import re
import sys
import warnings
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")

DB_CONFIG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5432")),
    user=os.environ.get("DB_USER", "tmf"),
    password=os.environ.get("DB_PASSWORD", "tmf_dev_2026"),
    dbname=os.environ.get("DB_NAME", "tmf_market_data"),
)

TZ = "Asia/Taipei"
CONTRACT_MULTIPLIER = 50
HISTORY_DAYS = 60           # percentile lookback (trading days)
MIN_HISTORY = 20            # below this: no percentile, no distributional adjectives
GAP_MINUTES = 5             # window gap threshold for DATA GAP flag


def parse_window(s):
    """'HH:MM-HH:MM' -> (start, end). Raises ValueError on bad/inverted input."""
    m = re.fullmatch(r"(\d{2}:\d{2})-(\d{2}:\d{2})", s)
    if not m:
        raise ValueError(f"window must be HH:MM-HH:MM, got {s!r}")
    start, end = m.group(1), m.group(2)
    if start >= end:
        raise ValueError(f"window start must precede end: {s!r}")
    return start, end


def select_front_expiry(counts_df, min_rows=10):
    """Pick shortest-tenor expiry with enough window rows.

    counts_df: DataFrame[expiry(YYYYMMDD str), n(row count)]. Sorted lexically
    == sorted by date for YYYYMMDD. Settlement weeks need no special case —
    whatever near expiry has data wins (spec §2).
    """
    if counts_df.empty:
        return None
    ok = counts_df[counts_df["n"] >= min_rows]
    if ok.empty:
        return None
    return sorted(ok["expiry"].tolist())[0]


def percentile_verified(value, history, metric_name):
    """Return (percentile 0-100 or None, verification log lines).

    Golden Rule 0: distributional adjectives require this to have run.
    n < MIN_HISTORY -> (None, log with 'insufficient-history(n=X)').
    """
    if pd.isna(value):
        return None, [f"{metric_name}: value=NaN — percentile unavailable"]
    n = int(history.dropna().shape[0])
    if n < MIN_HISTORY:
        return None, [f"{metric_name}: insufficient-history(n={n}) — "
                      f"percentile unavailable, distributional adjectives forbidden"]
    pct = float((history.dropna() < value).mean() * 100.0)
    log = [f"{metric_name}: value={value:.4f} percentile={pct:.0f} vs same-window "
           f"history n={n} (rank = share of history strictly below value)"]
    return pct, log


# ---------------------------------------------------------------------------
# Data-access layer (I/O only, no logic — exercised by the Task 5 live smoke)
# ---------------------------------------------------------------------------

def _connect():
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def fetch_iv_metrics(conn, date_str, start, end):
    """Raw iv_metrics rows for all TXO-family expiries in the window."""
    sql = """
        SELECT time, expiry, product_code, atm_iv, skew_25d, rr_25d,
               pcr_volume, iv_term_slope, underlying_price
        FROM iv_metrics
        WHERE underlying='TX'
          AND time >= %(t0)s::timestamptz AND time < %(t1)s::timestamptz
        ORDER BY time
    """
    t0 = f"{date_str} {start}:00+08"
    t1 = f"{date_str} {end}:00+08"
    return pd.read_sql(sql, conn, params={"t0": t0, "t1": t1})


def fetch_strikes_snapshot(conn, date_str, end, expiry):
    """Latest per-(strike, cp) iv_strikes rows at/before window end for expiry."""
    sql = """
        SELECT DISTINCT ON (strike, call_put)
               strike, call_put, iv, gamma, delta, volume
        FROM iv_strikes
        WHERE expiry = %(expiry)s
          AND time <= %(t1)s::timestamptz AND time >= %(t1)s::timestamptz - interval '15 minutes'
        ORDER BY strike, call_put, time DESC
    """
    return pd.read_sql(sql, conn, params={"expiry": expiry, "t1": f"{date_str} {end}:00+08"})


def fetch_oi(conn, expiry_yyyymmdd, before_date=None):
    """Latest settle-day OI per (strike, cp) for expiry; before_date bounds settle_date."""
    sql = """
        SELECT strike, cp, open_interest, settle_date
        FROM option_oi_daily
        WHERE underlying='TX' AND expiry = %(expiry)s::date
          AND settle_date = (
            SELECT max(settle_date) FROM option_oi_daily
            WHERE underlying='TX' AND expiry = %(expiry)s::date
              AND (%(before)s::date IS NULL OR settle_date < %(before)s::date)
          )
    """
    exp_date = f"{expiry_yyyymmdd[:4]}-{expiry_yyyymmdd[4:6]}-{expiry_yyyymmdd[6:]}"
    return pd.read_sql(sql, conn, params={"expiry": exp_date, "before": before_date})


def fetch_txf_bars(conn, date_str, start, end):
    sql = """
        SELECT bucket, open, high, low, close FROM ohlcv_1m
        WHERE symbol='TXF'
          AND bucket >= %(t0)s::timestamptz AND bucket < %(t1)s::timestamptz
        ORDER BY bucket
    """
    return pd.read_sql(sql, conn, params={"t0": f"{date_str} {start}:00+08",
                                          "t1": f"{date_str} {end}:00+08"})


def fetch_vrp_history(conn, date_str, start, end, days=HISTORY_DAYS):
    """Per-day same-window (ATM IV mean, RV) for the past `days` trading days
    BEFORE date_str. One SQL per source, joined in pandas by day.

    Note: the plan's correlated min-expiry subquery ran >4 min live, so per the
    plan's documented fallback we fetch per-(day, expiry) aggregates and pick
    each day's front (min) expiry in pandas.
    """
    iv_sql = """
        SELECT (time at time zone 'Asia/Taipei')::date AS d, expiry,
               avg(atm_iv) AS iv_mean
        FROM iv_metrics
        WHERE underlying='TX' AND product_code='TXO'
          AND (time at time zone 'Asia/Taipei')::date < %(d)s::date
          AND (time at time zone 'Asia/Taipei')::date >= %(d)s::date - %(days)s * interval '1 day' * 2
          AND (time at time zone 'Asia/Taipei')::time >= %(s)s::time
          AND (time at time zone 'Asia/Taipei')::time <  %(e)s::time
        GROUP BY 1, 2 ORDER BY 1 DESC, 2
    """
    bars_sql = """
        SELECT (bucket at time zone 'Asia/Taipei')::date AS d,
               (bucket at time zone 'Asia/Taipei')::time AS t, close
        FROM ohlcv_1m
        WHERE symbol='TXF'
          AND (bucket at time zone 'Asia/Taipei')::date < %(d)s::date
          AND (bucket at time zone 'Asia/Taipei')::date >= %(d)s::date - %(days)s * interval '1 day' * 2
          AND (bucket at time zone 'Asia/Taipei')::time >= %(s)s::time
          AND (bucket at time zone 'Asia/Taipei')::time <  %(e)s::time
        ORDER BY d, t
    """
    p = {"d": date_str, "s": f"{start}:00", "e": f"{end}:00", "days": days}
    iv_all = pd.read_sql(iv_sql, conn, params=p)
    if not iv_all.empty:
        # Per-day front expiry (lexical min == date min for YYYYMMDD strings),
        # keep the most recent `days` days.
        iv_all = iv_all.sort_values(["d", "expiry"]).groupby("d", as_index=False).first()
        iv_all = iv_all.sort_values("d", ascending=False).head(days)[["d", "iv_mean"]]
    else:
        iv_all = pd.DataFrame({"d": [], "iv_mean": []})
    return iv_all, pd.read_sql(bars_sql, conn, params=p)


def fetch_skew_delta_history(conn, date_str, start, end, days=HISTORY_DAYS):
    """Per-day same-window skew_25d (last - first), TXO only, past `days`
    trading days before date_str. Returns DataFrame[d, skew_delta]."""
    sql = """
        WITH w AS (
          SELECT (time at time zone 'Asia/Taipei')::date AS d, time, skew_25d
          FROM iv_metrics
          WHERE underlying='TX' AND product_code='TXO' AND skew_25d IS NOT NULL
            AND (time at time zone 'Asia/Taipei')::date < %(d)s::date
            AND (time at time zone 'Asia/Taipei')::date >= %(d)s::date - %(days)s * interval '1 day' * 2
            AND (time at time zone 'Asia/Taipei')::time >= %(s)s::time
            AND (time at time zone 'Asia/Taipei')::time <  %(e)s::time
        )
        SELECT d, (max(skew_25d) FILTER (WHERE time = last_t)
                 - max(skew_25d) FILTER (WHERE time = first_t)) AS skew_delta
        FROM (SELECT d, time, skew_25d,
                     min(time) OVER (PARTITION BY d) AS first_t,
                     max(time) OVER (PARTITION BY d) AS last_t
              FROM w) x
        WHERE time IN (first_t, last_t)
        GROUP BY d ORDER BY d DESC LIMIT %(days)s
    """
    p = {"d": date_str, "s": f"{start}:00", "e": f"{end}:00", "days": days}
    return pd.read_sql(sql, conn, params=p)


# ---------------------------------------------------------------------------
# Analysis layer (pure functions — Section = {metrics, verdict, verification})
# ---------------------------------------------------------------------------

def analyze_gex(strikes_df, oi_df, spot):
    """GEX per spec §3.1. Naive dealer convention: call OI +gamma, put OI -gamma.

    GEX(K) = gamma * OI * MULTIPLIER * spot^2 * 0.01  (NTD per 1% move)
    Flip = zero-crossing of cumulative GEX over strikes (ascending).
    zone: 'pinning' if spot in positive-cumulative region (>= flip), else 'expansion'.
    """
    empty = {"metrics": {"total_gex": None, "flip": None, "zone": None, "top_strikes": []},
             "verdict": "GEX: DATA GAP — no strikes/OI rows in window",
             "verification": []}
    if strikes_df.empty or oi_df.empty:
        return empty
    df = strikes_df.merge(oi_df, left_on=["strike", "call_put"],
                          right_on=["strike", "cp"], how="inner")
    if df.empty:
        return empty
    n_before = len(df)
    df = df.dropna(subset=["gamma", "open_interest"])
    n_excluded = n_before - len(df)
    if df.empty:
        return empty
    sign = df["call_put"].map({"C": 1.0, "P": -1.0})
    df = df.assign(gex=df["gamma"] * df["open_interest"] * CONTRACT_MULTIPLIER
                        * spot * spot * 0.01 * sign)
    by_k = df.groupby("strike")["gex"].sum().sort_index()
    cum = by_k.cumsum()
    flip = None
    prev_v = None
    for k, v in cum.items():
        if prev_v is not None and prev_v < 0 <= v:
            flip = float(k)
            break
        prev_v = v
    total = float(by_k.sum())
    zone = None
    if flip is not None:
        zone = "pinning" if spot >= flip else "expansion"
    elif total > 0:
        zone = "pinning"
    elif total < 0:
        zone = "expansion"
    top = (by_k.abs().sort_values(ascending=False).head(5).index.astype(float).tolist())
    settle = str(oi_df["settle_date"].iloc[0])
    if zone == "pinning":
        zone_txt = "磁吸區 (pinning)"
    elif zone == "expansion":
        zone_txt = "放大區 (expansion)"
    else:
        zone_txt = "zone n/a"
    verdict = (f"總 GEX {total/1e8:.2f} 億/1%; "
               f"flip={flip if flip is not None else 'n/a'}; "
               f"spot={spot:.0f} → {zone_txt}")
    verification = [
        f"GEX assumptions: naive dealer sign (call +, put -); OI from settle {settle} (T+1 approximation); "
        f"gamma from window-end iv_strikes snapshot; multiplier {CONTRACT_MULTIPLIER}",
    ]
    if n_excluded > 0:
        verification.append(f"excluded {n_excluded} rows with NaN gamma/OI from GEX")
    return {"metrics": {"total_gex": total, "flip": flip, "zone": zone,
                        "top_strikes": top},
            "verdict": verdict, "verification": verification}


def realized_vol_annualized(closes, bars_per_day):
    """Close-to-close annualized RV from a 1m close series (window subset).

    sigma = std of 1m log returns (population) * sqrt(252 * bars_per_day).
    """
    r = np.diff(np.log(closes.astype(float)))
    if r.size == 0:
        return None
    return float(np.sqrt(np.mean(r * r)) * np.sqrt(252.0 * bars_per_day))


def analyze_iv_rv(atm_iv_series, txf_bars, history_df):
    """VRP = mean window ATM IV - window annualized RV. Percentile vs
    same-window history (history_df['vrp']). Spec §3.2 + Golden Rule 0."""
    if txf_bars.empty or atm_iv_series.dropna().empty:
        return {"metrics": {"rv": None, "iv": None, "vrp": None, "percentile": None},
                "verdict": "IV-RV: DATA GAP — missing bars or ATM IV in window",
                "verification": []}
    closes = txf_bars["close"]
    rv = realized_vol_annualized(closes, bars_per_day=300)  # TXF day session 08:45-13:45 ≈ 300 1m bars
    if rv is None:
        return {"metrics": {"rv": None, "iv": None, "vrp": None, "percentile": None},
                "verdict": "IV-RV: DATA GAP — insufficient bars for RV",
                "verification": []}
    iv_mean = float(atm_iv_series.dropna().mean())
    vrp = iv_mean - rv
    pct, vlog = percentile_verified(vrp, history_df.get("vrp", pd.Series(dtype=float)),
                                    metric_name="VRP")
    vlog.append("RV: intraday-only (day-session 1m bars), overnight variance excluded; "
                "annualized sqrt(252*300)")
    if pct is None:
        verdict = f"VRP {vrp*100:+.1f} vol pts (IV {iv_mean*100:.1f} vs RV {rv*100:.1f})"
    else:
        rich = "選擇權相對已實現波動偏貴" if pct >= 70 else (
               "選擇權相對已實現波動偏便宜" if pct <= 30 else "VRP 居中")
        verdict = (f"VRP {vrp*100:+.1f} vol pts (IV {iv_mean*100:.1f} vs RV {rv*100:.1f}),"
                   f" 同窗歷史 percentile {pct:.0f}（n 見 verification）→ {rich}")
    return {"metrics": {"rv": rv, "iv": iv_mean, "vrp": vrp, "percentile": pct},
            "verdict": verdict, "verification": vlog}


def _window_gaps(times, gap_minutes=GAP_MINUTES):
    """Return list of (start, end) gaps > gap_minutes in a time series."""
    t = pd.Series(pd.to_datetime(times)).sort_values()
    dt = t.diff()
    gaps = []
    for i, d in enumerate(dt):
        if pd.notna(d) and d > pd.Timedelta(minutes=gap_minutes):
            gaps.append((t.iloc[i - 1], t.iloc[i]))
    return gaps


def analyze_term_skew(metrics_df, history_df):
    """Window deltas + path extremes for ATM IV / skew_25d / term slope. Spec §3.3."""
    if metrics_df.empty:
        return {"metrics": {}, "verdict": "TERM/SKEW: DATA GAP — no iv_metrics rows",
                "verification": []}
    df = metrics_df.dropna(subset=["atm_iv"]).sort_values("time")
    if df.empty:
        return {"metrics": {}, "verdict": "TERM/SKEW: DATA GAP — no iv_metrics rows",
                "verification": []}
    gaps = _window_gaps(df["time"])
    skew = df["skew_25d"].dropna()
    skew_delta = float(skew.iloc[-1] - skew.iloc[0]) if len(skew) >= 2 else None
    atm_delta = float(df["atm_iv"].iloc[-1] - df["atm_iv"].iloc[0])
    slope_last = float(df["iv_term_slope"].dropna().iloc[-1]) if df["iv_term_slope"].notna().any() else None
    pct, vlog = (None, [])
    if skew_delta is not None:
        pct, vlog = percentile_verified(skew_delta,
                                        history_df.get("skew_delta", pd.Series(dtype=float)),
                                        metric_name="skew_25d window delta")
    skew_txt = f"{skew_delta*100:+.2f}" if skew_delta is not None else "n/a"
    verdict = (f"ATM IV Δ {atm_delta*100:+.1f} pts; skew_25d Δ "
               f"{skew_txt} (pct {f'{pct:.0f}' if pct is not None else 'n/a'}); "
               f"term slope {f'{slope_last:.4f}' if slope_last is not None else 'n/a'}")
    if gaps:
        gap_txt = ", ".join(f"{a:%H:%M}–{b:%H:%M}" for a, b in gaps)
        verdict = f"DATA GAP {gap_txt} | " + verdict
    return {"metrics": {"atm_iv_delta": atm_delta, "skew_delta": skew_delta,
                        "skew_delta_pct": pct, "term_slope": slope_last,
                        "atm_iv_path_max": float(df["atm_iv"].max()),
                        "atm_iv_path_min": float(df["atm_iv"].min())},
            "verdict": verdict, "verification": vlog}


def analyze_flow(metrics_df, oi_now, oi_prev):
    """PCR path + per-strike OI build/unwind. Spec §3.4."""
    pcr = metrics_df["pcr_volume"].dropna() if not metrics_df.empty else pd.Series(dtype=float)
    pcr_mean = float(pcr.mean()) if not pcr.empty else None
    builds = []
    note = ""
    if oi_prev.empty or oi_now.empty:
        note = "無前日 OI 可比 (no prior OI)"
    else:
        merged = oi_now.merge(oi_prev, on=["strike", "cp"], how="outer",
                              suffixes=("_now", "_prev")).fillna({"open_interest_now": 0,
                                                                  "open_interest_prev": 0})
        merged["d_oi"] = merged["open_interest_now"] - merged["open_interest_prev"]
        top = merged.reindex(merged["d_oi"].abs().sort_values(ascending=False).index).head(5)
        builds = [(float(r.strike), int(r.d_oi), str(r.cp)) for r in top.itertuples()]
    pcr_txt = f"{pcr_mean:.2f}" if pcr_mean is not None else "n/a"
    verdict = f"PCR(vol) mean {pcr_txt}; top ΔOI: {builds[:3]}"
    if note:
        verdict += f" | {note}"
    if metrics_df.empty:
        verdict = "DATA GAP — no metrics rows | " + verdict
    verification = []
    if not oi_now.empty:
        d_now = str(oi_now["settle_date"].max())
        d_prev = str(oi_prev["settle_date"].max()) if not oi_prev.empty else "n/a"
        verification.append(
            f"Flow ΔOI compares settle {d_prev} -> {d_now}; run intraday the "
            f"analysis day's own EOD OI is not yet available (T+1)")
    return {"metrics": {"pcr_mean": pcr_mean, "top_oi_builds": builds},
            "verdict": verdict, "verification": verification}


# ---------------------------------------------------------------------------
# Report layer — labels + markdown
# ---------------------------------------------------------------------------

LABEL_RULES = (
    ("expansion-risk", "總 GEX < 0 且 VRP percentile < 30"),
    ("premium-rich-pinning", "總 GEX > 0 且 VRP percentile > 70"),
    ("hedging-bid", "skew Δ percentile > 80"),
    ("neutral-carry", "其餘 (fallback)"),
)


def vol_labels(sections):
    """Rule-based env labels per spec §4. Multi-label; neutral-carry fallback."""
    g = sections["gex"]["metrics"].get("total_gex")
    vp = sections["iv_rv"]["metrics"].get("percentile")
    sp = sections["term_skew"]["metrics"].get("skew_delta_pct")
    labels = []
    if g is not None and vp is not None and g < 0 and vp < 30:
        labels.append("expansion-risk")
    if g is not None and vp is not None and g > 0 and vp > 70:
        labels.append("premium-rich-pinning")
    if sp is not None and sp > 80:
        labels.append("hedging-bid")
    return labels or ["neutral-carry"]


def render_report(date_str, window, sections, labels):
    lines = [f"# TXO 選擇權盤中量化分析 — {date_str} {window}", ""]
    lines += [f"**Vol 環境標籤:** {', '.join('`%s`' % l for l in labels)}", ""]
    titles = (("gex", "## 1. GEX / Dealer Gamma"), ("iv_rv", "## 2. IV vs RV (VRP)"),
              ("term_skew", "## 3. Term / Skew 盤中動態"), ("flow", "## 4. PCR / OI 資金流"))
    for key, title in titles:
        s = sections[key]
        lines += [title, "", f"**Verdict:** {s['verdict']}", ""]
        for k, v in s["metrics"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    lines += ["## Verification log", ""]
    for key, _ in titles:
        for v in sections[key]["verification"]:
            lines.append(f"- {v}")
    lines += ["", "## 標籤定義", ""]
    for name, rule in LABEL_RULES:
        lines.append(f"- `{name}`: {rule}")
    lines += ["", "> 本報告為環境判定,不出買賣指令。資料 read-only 取自 trading-timescaledb。"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI orchestration
# ---------------------------------------------------------------------------

def _build_vrp_history(iv_hist, bars_hist):
    """Join per-day IV means with per-day RV (from 1m closes) -> DataFrame['vrp']."""
    if iv_hist.empty or bars_hist.empty:
        return pd.DataFrame({"vrp": []})
    rows = []
    rv_by_day = {}
    for d, grp in bars_hist.groupby("d"):
        rv = realized_vol_annualized(grp["close"], bars_per_day=300)
        if rv is not None:
            rv_by_day[d] = rv
    for r in iv_hist.itertuples():
        rv = rv_by_day.get(r.d)
        if rv is not None and pd.notna(r.iv_mean):
            rows.append({"d": r.d, "vrp": float(r.iv_mean) - rv})
    if not rows:
        return pd.DataFrame({"vrp": []})
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="TXO intraday options quant — env labels, no trade directives")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                    help="Trading date YYYY-MM-DD (default: today, Asia/Taipei local)")
    ap.add_argument("--window", default="09:00-13:30", help="Intraday window HH:MM-HH:MM")
    ap.add_argument("--out-dir", default="analysis", help="Output directory for the md report")
    args = ap.parse_args(argv)

    start, end = parse_window(args.window)
    date_str = args.date

    try:
        conn = _connect()
    except Exception as e:
        print(f"ERROR: cannot connect to trading-timescaledb ({DB_CONFIG['host']}:"
              f"{DB_CONFIG['port']}/{DB_CONFIG['dbname']}): {e}", file=sys.stderr)
        sys.exit(1)

    try:
        metrics = fetch_iv_metrics(conn, date_str, start, end)

        # Front expiry (overall nearest live — weekly if listed) for GEX/flow.
        counts = (metrics.groupby("expiry").size().rename("n").reset_index()
                  if not metrics.empty else pd.DataFrame({"expiry": [], "n": []}))
        front = select_front_expiry(counts)

        # TXO-only front expiry for VRP (like-for-like vs TXO-only history).
        txo = metrics[metrics["product_code"] == "TXO"] if not metrics.empty else metrics
        txo_counts = (txo.groupby("expiry").size().rename("n").reset_index()
                      if not txo.empty else pd.DataFrame({"expiry": [], "n": []}))
        txo_front = select_front_expiry(txo_counts)
        txo_metrics = txo[txo["expiry"] == txo_front] if txo_front else txo.iloc[0:0]

        front_metrics = metrics[metrics["expiry"] == front] if front else metrics.iloc[0:0]
        spot_series = front_metrics["underlying_price"].dropna() if not front_metrics.empty \
            else pd.Series(dtype=float)
        spot = float(spot_series.iloc[-1]) if not spot_series.empty else None

        # GEX inputs (front expiry, window-end snapshot + OI knowable AT the
        # window: settle strictly BEFORE the analysis date — spec §3.1 前一
        # 結算日. Unbounded latest would look ahead to the analysis day's own
        # EOD on retrospective runs.
        if front and spot is not None:
            strikes = fetch_strikes_snapshot(conn, date_str, end, front)
            oi_gex = fetch_oi(conn, front, before_date=date_str)
            gex_sec = analyze_gex(strikes, oi_gex, spot=spot)
        else:
            _empty_oi = pd.DataFrame({"strike": [], "cp": [], "open_interest": [],
                                      "settle_date": []})
            gex_sec = analyze_gex(_empty_oi.assign(call_put=[], iv=[], gamma=[],
                                                   delta=[], volume=[])[
                ["strike", "call_put", "iv", "gamma", "delta", "volume"]],
                _empty_oi, spot=spot or 0.0)

        # IV-RV / VRP (TXO front-expiry ATM IV vs TXF RV, TXO-only history).
        bars = fetch_txf_bars(conn, date_str, start, end)
        iv_hist, bars_hist = fetch_vrp_history(conn, date_str, start, end)
        vrp_history = _build_vrp_history(iv_hist, bars_hist)
        iv_rv_sec = analyze_iv_rv(txo_metrics["atm_iv"] if not txo_metrics.empty
                                  else pd.Series(dtype=float), bars, vrp_history)

        # Term / skew (front-expiry window path vs same-window skew_delta history).
        skew_hist = fetch_skew_delta_history(conn, date_str, start, end)
        # Like-for-like: skew_delta percentile history is TXO-only, so the
        # window series must be TXO front too (mirrors the VRP decision).
        term_sec = analyze_term_skew(txo_metrics, skew_hist)

        # Flow (PCR path + day-over-day OI delta on the front expiry).
        # "now" side is bounded to settle <= analysis date (before next day) so
        # retrospective runs weeks later don't pick up future settles; "prev"
        # is the settle before that — spec §3.4 前一結算日 → 最新結算日.
        next_day = (datetime.strptime(date_str, "%Y-%m-%d")
                    + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        oi_now = fetch_oi(conn, front, before_date=next_day) if front else \
            pd.DataFrame({"strike": [], "cp": [], "open_interest": [],
                          "settle_date": []})
        if front and not oi_now.empty:
            latest_settle = str(oi_now["settle_date"].max())
            oi_prev = fetch_oi(conn, front, before_date=latest_settle)
        else:
            oi_prev = pd.DataFrame({"strike": [], "cp": [], "open_interest": [],
                                    "settle_date": []})
        flow_sec = analyze_flow(front_metrics, oi_now, oi_prev)
    finally:
        conn.close()

    sections = {"gex": gex_sec, "iv_rv": iv_rv_sec, "term_skew": term_sec,
                "flow": flow_sec}
    labels = vol_labels(sections)
    md = render_report(date_str, args.window, sections, labels)

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"options_quant_{date_str}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md + "\n")

    print(f"report: {out_path}")
    print(f"front expiry (GEX/flow): {front}; TXO front (VRP): {txo_front}; "
          f"spot: {spot}")
    for key, name in (("gex", "GEX"), ("iv_rv", "IV-RV"),
                      ("term_skew", "TERM/SKEW"), ("flow", "FLOW")):
        print(f"[{name}] {sections[key]['verdict']}")
    print(f"labels: {', '.join(labels)}")


if __name__ == "__main__":
    main()
