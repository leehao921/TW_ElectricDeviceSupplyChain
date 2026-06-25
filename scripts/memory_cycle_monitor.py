"""Memory cycle sell-signal monitor for 南亞科 2408 / 華邦電 2344.

See docs/superpowers/specs/2026-06-25-memory-cycle-monitor-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Light constants
GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

# Thresholds per spec §4 S1
PB_THRESHOLDS: dict[str, dict[str, float]] = {
    "2408.TW": {"yellow": 1.8, "red": 2.5},
    "2344.TW": {"yellow": 1.5, "red": 2.0},
}

# Spec §4 S2 thresholds
DDR5_QOQ_YELLOW_PCT = 10.0  # below this in absolute QoQ → yellow
DDR5_QOQ_RED_PCT = 5.0      # below this → red
DDR5_DECAY_YELLOW = 0.5     # 衰減 >50% → yellow when 3 quarters available


@dataclass
class PricePoint:
    """One row from the YAML price series."""
    label: str   # "2026-04" or "2026Q1"
    price: float


@dataclass
class Inputs:
    """Parsed memory_cycle_inputs.yaml."""
    last_updated: str
    notes: str
    ddr4_8gb_spot_usd: list[PricePoint] = field(default_factory=list)
    ddr5_16gb_contract_usd: list[PricePoint] = field(default_factory=list)
    mu_next_quarter_gm_guide: float | None = None
    mu_next_quarter_rev_qoq: float | None = None


@dataclass
class SignalResult:
    """One signal's computed light + human-readable value + raw detail."""
    light: str            # GREEN | YELLOW | RED | "N/A"
    value: str            # short string for report (e.g. "+10.6%")
    detail: dict[str, Any] = field(default_factory=dict)


def load_inputs(path: str | Path) -> Inputs:
    """Parse memory_cycle_inputs.yaml into an Inputs dataclass.

    Sorts price series by label (string sort works for both "2026-04" and "2026Q1").
    Raises ValueError on missing required fields.
    """
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    if "last_updated" not in raw:
        raise ValueError("YAML missing required field: last_updated")

    def _parse_series(rows: list[dict], label_key: str) -> list[PricePoint]:
        if not rows:
            return []
        pts = [PricePoint(label=str(r[label_key]), price=float(r["price"])) for r in rows]
        pts.sort(key=lambda pp: pp.label)
        return pts

    return Inputs(
        last_updated=str(raw["last_updated"]),
        notes=str(raw.get("notes", "")),
        ddr4_8gb_spot_usd=_parse_series(raw.get("ddr4_8gb_spot_usd") or [], "month"),
        ddr5_16gb_contract_usd=_parse_series(raw.get("ddr5_16gb_contract_usd") or [], "quarter"),
        mu_next_quarter_gm_guide=raw.get("mu_next_quarter_gm_guide"),
        mu_next_quarter_rev_qoq=raw.get("mu_next_quarter_rev_qoq"),
    )


def compute_s2a_ddr4(series: list[PricePoint]) -> SignalResult:
    """S2a: DDR4 8Gb 現貨價 MoM.

    Green: latest MoM ≥ 0%
    Yellow: latest MoM < 0% (single negative month)
    Red: latest 2 consecutive months MoM < 0%
    N/A: <2 data points
    """
    if len(series) < 2:
        return SignalResult(light="N/A", value="insufficient data")

    def _mom(a: PricePoint, b: PricePoint) -> float:
        return (b.price - a.price) / a.price * 100

    latest_mom = _mom(series[-2], series[-1])
    value = f"{latest_mom:+.1f}%"

    if latest_mom >= 0:
        return SignalResult(light=GREEN, value=value, detail={"mom_pct": latest_mom})

    # latest is negative; check previous month
    if len(series) >= 3:
        prev_mom = _mom(series[-3], series[-2])
        if prev_mom < 0:
            return SignalResult(
                light=RED, value=value,
                detail={"mom_pct": latest_mom, "prev_mom_pct": prev_mom},
            )

    return SignalResult(light=YELLOW, value=value, detail={"mom_pct": latest_mom})


def compute_s2b_ddr5(series: list[PricePoint]) -> SignalResult:
    """S2b: DDR5 16Gb 合約價 QoQ — dual threshold.

    With 3+ quarters (full mode):
      Green:  QoQ ≥ +10% AND decay < 50%
      Yellow: QoQ < +10% OR decay > 50%
      Red:    QoQ < +5% or negative

    With exactly 2 quarters (degraded — no decay computable):
      Green:  QoQ ≥ +10%
      Yellow: +5% ≤ QoQ < +10%
      Red:    QoQ < +5% or negative
    """
    if len(series) < 2:
        return SignalResult(light="N/A", value="insufficient data")

    def _qoq(a: PricePoint, b: PricePoint) -> float:
        return (b.price - a.price) / a.price * 100

    latest_qoq = _qoq(series[-2], series[-1])
    detail: dict[str, Any] = {"qoq_pct": latest_qoq, "decay_pct": None}

    # Compute decay if 3+ quarters available
    if len(series) >= 3:
        prev_qoq = _qoq(series[-3], series[-2])
        if prev_qoq > 0:
            decay = (prev_qoq - latest_qoq) / prev_qoq
            detail["decay_pct"] = decay * 100
            detail["prev_qoq_pct"] = prev_qoq

    # Red (absolute) — applies in both modes
    if latest_qoq < DDR5_QOQ_RED_PCT:
        return SignalResult(light=RED, value=f"{latest_qoq:+.1f}%", detail=detail)

    # Yellow checks
    if latest_qoq < DDR5_QOQ_YELLOW_PCT:
        return SignalResult(light=YELLOW, value=f"{latest_qoq:+.1f}%", detail=detail)
    if detail["decay_pct"] is not None and detail["decay_pct"] / 100 > DDR5_DECAY_YELLOW:
        return SignalResult(light=YELLOW, value=f"{latest_qoq:+.1f}%", detail=detail)

    return SignalResult(light=GREEN, value=f"{latest_qoq:+.1f}%", detail=detail)


def _light_for_pb(pb: float, thresholds: dict[str, float]) -> str:
    if pb >= thresholds["red"]:
        return RED
    if pb >= thresholds["yellow"]:
        return YELLOW
    return GREEN


_LIGHT_RANK = {GREEN: 0, YELLOW: 1, RED: 2}


def _worst(*lights: str) -> str:
    known = [lg for lg in lights if lg in _LIGHT_RANK]
    if not known:
        return "N/A"
    return max(known, key=_LIGHT_RANK.__getitem__)


def compute_s1_pb(pbs: dict[str, float | None]) -> SignalResult:
    """S1: P/B valuation premium for 2408.TW and 2344.TW.

    Takes the worst-known light of the two. If a ticker is None it's recorded
    as N/A but doesn't drag the overall light down (still uses worst of known).
    """
    detail: dict[str, Any] = {}
    lights = []
    parts = []
    for ticker, pb in pbs.items():
        if pb is None:
            detail[ticker] = "N/A"
            lights.append("N/A")
            parts.append(f"{ticker}=N/A")
            continue
        lg = _light_for_pb(pb, PB_THRESHOLDS[ticker])
        detail[ticker] = {"pb": pb, "light": lg}
        lights.append(lg)
        parts.append(f"{ticker}={pb:.2f}")

    return SignalResult(light=_worst(*lights), value=", ".join(parts), detail=detail)


def fetch_pb(ticker: str) -> float | None:
    """Fetch P/B for a ticker via yfinance.

    Primary: info['priceToBook']. Fallback: marketCap / (bookValue * sharesOutstanding).
    Returns None on any failure (caller treats as N/A).
    """
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info
        pb = info.get("priceToBook")
        if pb is not None and pb > 0:
            return float(pb)
        mc = info.get("marketCap")
        bv = info.get("bookValue")
        so = info.get("sharesOutstanding")
        if mc and bv and so and bv * so > 0:
            return float(mc / (bv * so))
    except Exception:
        pass
    return None


def detect_monthly_weakness(closes: list[float]) -> bool:
    """Spec §4 S3: latest month close < min of prior 3 months close.

    `closes` is chronological; index -1 is latest. Need ≥4 points.
    """
    if len(closes) < 4:
        return False
    prior_3_min = min(closes[-4:-1])
    return closes[-1] < prior_3_min
