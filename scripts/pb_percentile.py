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
