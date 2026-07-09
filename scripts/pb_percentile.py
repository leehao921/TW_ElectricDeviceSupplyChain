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
