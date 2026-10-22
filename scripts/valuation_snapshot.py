"""Snapshot persistence for daily valuation data.

A snapshot is a JSON document keyed by ticker, capturing the minimal set of
numeric fields needed for next-day anomaly detection:

    price, pe, pb, yield_pct, market_cap_m, source

Snapshots live under data/valuation_snapshots/YYYY-MM-DD.json and are
committed to git so the comparison baseline is reproducible.

Used by:
    - scripts/update_valuation.py  (writer, after the daily refresh)
    - scripts/detect_valuation_anomaly.py  (reader, for yday/today comparison)
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "data" / "valuation_snapshots"

# Only these fields persist into the snapshot. Anything else in the bulk
# dict (fiscal_q, trade_value, ...) is dropped to keep diffs minimal.
SNAPSHOT_FIELDS = ("price", "pe", "pb", "yield_pct", "market_cap_m", "source")


def snapshot_path(snapshot_date: str) -> Path:
    return SNAPSHOT_DIR / f"{snapshot_date}.json"


def build_snapshot(bulk: dict, snapshot_date: str) -> dict:
    """Project bulk dict (ticker -> raw fields) into snapshot shape."""
    tickers: dict[str, dict] = {}
    sources: Counter = Counter()
    for ticker, row in bulk.items():
        if not isinstance(row, dict):
            continue
        tickers[ticker] = {f: row.get(f) for f in SNAPSHOT_FIELDS}
        src = row.get("source")
        if src:
            sources[src] += 1
    return {
        "snapshot_date": snapshot_date,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_summary": dict(sources),
        "tickers": tickers,
    }


def save_snapshot(snapshot: dict) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    p = snapshot_path(snapshot["snapshot_date"])
    with p.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, sort_keys=True)
    return p


def load_snapshot(snapshot_date: str) -> dict | None:
    p = snapshot_path(snapshot_date)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def latest_snapshot_before(target_date: str) -> dict | None:
    """Return the most recent snapshot strictly before target_date, or None."""
    if not SNAPSHOT_DIR.exists():
        return None
    candidates = sorted(
        p.stem for p in SNAPSHOT_DIR.glob("*.json") if p.stem < target_date
    )
    if not candidates:
        return None
    return load_snapshot(candidates[-1])
