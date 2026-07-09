"""P/B historical-percentile engine.

Per ticker: pull 5y annual book value + daily close from yfinance, build a
daily P/B series, and report the current P/B's percentile within its own
history as a GREEN / YELLOW / RED light (85 / 70 bands).

Pure functions (compute_bvps ... compute_pb_light) take already-fetched data
and are unit-tested with synthetic fixtures. fetch_yf is the only networked
function. Data gaps -> light="N/A" (never RED) so downstream stop-break rules
fail safe.

See docs/superpowers/specs/2026-07-08-pb-percentile-engine-design.md.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "pb_percentile_cache.json"
RED_PCT = 85.0
YELLOW_PCT = 70.0
MIN_DAYS = 250
STALE_DAYS = 7


def compute_bvps(equity: dict, shares) -> dict:
    """Book value per share per fiscal year. Drop NaN/<=0 equity; shares must be >0."""
    if not shares or shares <= 0:
        return {}
    out = {}
    for year, eq in equity.items():
        if eq is None:
            continue
        if isinstance(eq, float) and math.isnan(eq):
            continue
        if eq <= 0:
            continue
        out[int(year)] = eq / shares
    return out


def build_pb_series(prices: "pd.Series", bvps: dict) -> "pd.Series":
    """Daily P/B = close / (BVPS of most recent fiscal year-end <= date).

    Dates earlier than the first available fiscal year-end are dropped.
    """
    if not bvps or prices is None or len(prices) == 0:
        return pd.Series(dtype=float)
    years = sorted(bvps)
    year_ends = [(pd.Timestamp(y, 12, 31), bvps[y]) for y in years]

    def asof(d):
        chosen = None
        for ye, val in year_ends:
            if ye <= d:
                chosen = val
        return chosen  # None if date precedes first FY-end

    idx = pd.to_datetime(prices.index)
    denom = pd.Series([asof(d) for d in idx], index=prices.index)
    pb = (prices / denom).dropna()
    return pb


def pct_rank(values: "pd.Series", current: float) -> float:
    """Percentile of `current`: fraction of values strictly less, x100."""
    return float((values < current).mean() * 100.0)


def classify(percentile: float, red: float = RED_PCT, yellow: float = YELLOW_PCT) -> str:
    if percentile >= red:
        return "RED"
    if percentile >= yellow:
        return "YELLOW"
    return "GREEN"


def _na(ticker: str, asof: str, source: str) -> dict:
    return {
        "ticker": ticker, "pb_current": None, "percentile": None,
        "light": "N/A", "p70": None, "p85": None, "n_days": 0,
        "source": source, "asof": asof,
    }


def compute_pb_light(prices, equity, shares, ticker="", asof="",
                     red=RED_PCT, yellow=YELLOW_PCT) -> dict:
    """Pure: given fetched inputs, return the light dict. Fails safe to N/A."""
    bvps = compute_bvps(equity, shares)
    if not bvps:
        return _na(ticker, asof, "no valid annual book value")
    latest_bvps = bvps[max(bvps)]
    if latest_bvps <= 0:
        return _na(ticker, asof, "non-positive latest book value")
    series = build_pb_series(prices, bvps)
    if len(series) < MIN_DAYS:
        return _na(ticker, asof, f"thin history ({len(series)} days)")
    current_pb = float(prices.iloc[-1]) / latest_bvps
    percentile = pct_rank(series, current_pb)
    return {
        "ticker": ticker,
        "pb_current": round(current_pb, 4),
        "percentile": round(percentile, 1),
        "light": classify(percentile, red, yellow),
        "p70": round(float(series.quantile(yellow / 100.0)), 4),
        "p85": round(float(series.quantile(red / 100.0)), 4),
        "bvps": round(latest_bvps, 4),
        "n_days": int(len(series)),
        "source": "yfinance annual BVPS 5y",
        "asof": asof,
    }


def light_from_cutoffs(current_pb: float, p70: float, p85: float) -> str:
    """Fast-path light: compare current P/B to cached absolute cutoffs.

    Equivalent to classify(percentile) because p70/p85 ARE the percentile
    cutoffs of the same historical distribution.
    """
    if current_pb >= p85:
        return "RED"
    if current_pb >= p70:
        return "YELLOW"
    return "GREEN"


def load_cache(path=CACHE_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache: dict, path=CACHE_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
