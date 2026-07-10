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
    BEFORE date_str. One SQL per source, joined in pandas by day."""
    iv_sql = """
        SELECT (time at time zone 'Asia/Taipei')::date AS d, avg(atm_iv) AS iv_mean
        FROM iv_metrics
        WHERE underlying='TX' AND product_code='TXO'
          AND (time at time zone 'Asia/Taipei')::date < %(d)s::date
          AND (time at time zone 'Asia/Taipei')::date >= %(d)s::date - %(days)s * interval '1 day' * 2
          AND (time at time zone 'Asia/Taipei')::time >= %(s)s::time
          AND (time at time zone 'Asia/Taipei')::time <  %(e)s::time
          AND expiry = (SELECT min(expiry) FROM iv_metrics m2
                        WHERE m2.underlying='TX' AND m2.product_code='TXO'
                          AND (m2.time at time zone 'Asia/Taipei')::date
                            = (iv_metrics.time at time zone 'Asia/Taipei')::date)
        GROUP BY 1 ORDER BY 1 DESC LIMIT %(days)s
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
    return pd.read_sql(iv_sql, conn, params=p), pd.read_sql(bars_sql, conn, params=p)


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
    sign = df["call_put"].map({"C": 1.0, "P": -1.0})
    df = df.assign(gex=df["gamma"] * df["open_interest"] * CONTRACT_MULTIPLIER
                        * spot * spot * 0.01 * sign)
    by_k = df.groupby("strike")["gex"].sum().sort_index()
    cum = by_k.cumsum()
    flip = None
    prev_k, prev_v = None, None
    for k, v in cum.items():
        if prev_v is not None and prev_v < 0 <= v:
            flip = float(k)
            break
        prev_k, prev_v = k, v
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
    verdict = (f"總 GEX {total/1e8:.2f} 億/1%; flip={flip}; spot={spot:.0f} → "
               f"{'磁吸區 (pinning)' if zone == 'pinning' else '放大區 (expansion)'}")
    verification = [
        f"GEX assumptions: naive dealer sign (call +, put -); OI from settle {settle} (T+1 approximation); "
        f"gamma from window-end iv_strikes snapshot; multiplier {CONTRACT_MULTIPLIER}",
    ]
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
    rv = realized_vol_annualized(closes, bars_per_day=270)  # 09:00-13:30 ≈ 270 1m bars
    iv_mean = float(atm_iv_series.dropna().mean())
    vrp = iv_mean - rv
    pct, vlog = percentile_verified(vrp, history_df.get("vrp", pd.Series(dtype=float)),
                                    metric_name="VRP")
    if pct is None:
        verdict = f"VRP {vrp*100:+.1f} vol pts (IV {iv_mean*100:.1f} vs RV {rv*100:.1f})"
    else:
        rich = "選擇權相對已實現波動偏貴" if pct >= 70 else (
               "選擇權相對已實現波動偏便宜" if pct <= 30 else "VRP 居中")
        verdict = (f"VRP {vrp*100:+.1f} vol pts (IV {iv_mean*100:.1f} vs RV {rv*100:.1f}),"
                   f" 60 日同窗 percentile {pct:.0f} → {rich}")
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
    verdict = (f"ATM IV Δ {atm_delta*100:+.1f} pts; skew_25d Δ "
               f"{(skew_delta or 0)*100:+.2f} (pct {pct if pct is not None else 'n/a'}); "
               f"term slope {slope_last}")
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
    verdict = f"PCR(vol) mean {pcr_mean}; top ΔOI: {builds[:3]}"
    if note:
        verdict += f" | {note}"
    return {"metrics": {"pcr_mean": pcr_mean, "top_oi_builds": builds},
            "verdict": verdict, "verification": []}
