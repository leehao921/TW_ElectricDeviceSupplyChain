"""Tests for valuation snapshot persistence + anomaly detection.

Rules under test (from docs/plans/2026-05-23-valuation-anomaly-detection.md):

  R1 |ΔPrice%| > 7%                                 -> HIGH
  R2 |ΔP/E%| > 20% AND |abs ΔP/E| > 3               -> MEDIUM
  R3 |ΔP/B%| > 25% AND |abs ΔP/B| > 0.5             -> MEDIUM
  R4 |ΔMktCap%| > 10% AND divergence vs price > 5pp -> HIGH
  R5 yesterday had data, today missing              -> HIGH
  R6 yield > 0 yesterday, == 0 today                -> INFO

Each rule has at least one positive (fires) and one negative (does not fire)
case. Snapshot IO is tested separately to keep failures localised.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

# Imports under test — these will fail at collection time until the modules
# are written. That IS the RED step.
from valuation_snapshot import (  # noqa: E402
    SNAPSHOT_DIR,
    build_snapshot,
    load_snapshot,
    save_snapshot,
    snapshot_path,
)
from detect_valuation_anomaly import (  # noqa: E402
    Anomaly,
    detect_anomalies,
    format_text,
    rule_price_jump,
    rule_pe_jump,
    rule_pb_jump,
    rule_mktcap_divergence,
    rule_data_missing,
    rule_ex_dividend,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def baseline_ticker() -> dict:
    """A 'yesterday' ticker entry with known sensible values."""
    return {
        "price": 100.0,
        "pe": 20.0,
        "pb": 4.0,
        "yield_pct": 2.0,
        "market_cap_m": 50_000,
        "source": "TWSE",
    }


@pytest.fixture
def snapshot_yday(baseline_ticker) -> dict:
    return {
        "snapshot_date": "2026-05-22",
        "generated_at_utc": "2026-05-22T08:35:00Z",
        "source_summary": {"TWSE": 1},
        "tickers": {"2330": dict(baseline_ticker)},
    }


# ---------------------------------------------------------------------------
# Snapshot IO
# ---------------------------------------------------------------------------


class TestSnapshotIO:
    def test_snapshot_path_uses_date_yyyy_mm_dd(self, tmp_path, monkeypatch):
        monkeypatch.setattr("valuation_snapshot.SNAPSHOT_DIR", tmp_path)
        p = snapshot_path("2026-05-23")
        assert p.parent == tmp_path
        assert p.name == "2026-05-23.json"

    def test_save_then_load_roundtrip(self, tmp_path, monkeypatch, snapshot_yday):
        monkeypatch.setattr("valuation_snapshot.SNAPSHOT_DIR", tmp_path)
        save_snapshot(snapshot_yday)
        loaded = load_snapshot("2026-05-22")
        assert loaded == snapshot_yday

    def test_load_snapshot_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("valuation_snapshot.SNAPSHOT_DIR", tmp_path)
        assert load_snapshot("1999-01-01") is None

    def test_build_snapshot_extracts_minimal_fields(self):
        # Mimics the dict shape that update_valuation.py builds internally.
        bulk = {
            "2330": {
                "price": 1175.0,
                "pe": 26.4,
                "pb": 6.1,
                "yield_pct": 1.4,
                "market_cap_m": 30_482_500,
                "source": "TWSE",
                "fiscal_q": "114Q1",  # extraneous, should be dropped
            },
            "5274": {
                "price": 4500.0,
                "pe": None,  # null is preserved
                "pb": 30.0,
                "yield_pct": None,
                "market_cap_m": None,
                "source": "TPEX",
            },
        }
        snap = build_snapshot(bulk, snapshot_date="2026-05-23")
        assert snap["snapshot_date"] == "2026-05-23"
        assert snap["tickers"]["2330"]["price"] == 1175.0
        assert "fiscal_q" not in snap["tickers"]["2330"]
        assert snap["tickers"]["5274"]["pe"] is None
        # source_summary tallies the source field
        assert snap["source_summary"]["TWSE"] == 1
        assert snap["source_summary"]["TPEX"] == 1


# ---------------------------------------------------------------------------
# Rule R1 — price jump > 7%
# ---------------------------------------------------------------------------


class TestRulePriceJump:
    def test_positive_price_up_10pct_fires(self, baseline_ticker):
        today = dict(baseline_ticker); today["price"] = 110.0  # +10%
        a = rule_price_jump("2330", baseline_ticker, today)
        assert a is not None
        assert a.rule == "R1"
        assert a.severity == "HIGH"

    def test_positive_price_down_8pct_fires(self, baseline_ticker):
        today = dict(baseline_ticker); today["price"] = 92.0  # -8%
        a = rule_price_jump("2330", baseline_ticker, today)
        assert a is not None and a.rule == "R1"

    def test_negative_price_up_5pct_does_not_fire(self, baseline_ticker):
        today = dict(baseline_ticker); today["price"] = 105.0  # +5%
        assert rule_price_jump("2330", baseline_ticker, today) is None

    def test_negative_missing_price_does_not_fire_here(self, baseline_ticker):
        # R5 covers missing data; R1 must not double-fire.
        today = dict(baseline_ticker); today["price"] = None
        assert rule_price_jump("2330", baseline_ticker, today) is None


# ---------------------------------------------------------------------------
# Rule R2 — P/E jump
# ---------------------------------------------------------------------------


class TestRulePEJump:
    def test_positive_pct_and_abs_both_breached(self, baseline_ticker):
        today = dict(baseline_ticker); today["pe"] = 25.0  # +25%, abs +5
        a = rule_pe_jump("2330", baseline_ticker, today)
        assert a is not None and a.rule == "R2" and a.severity == "MEDIUM"

    def test_negative_only_pct_breached_abs_too_small(self):
        # tiny baseline so a 50% move is < 3 abs
        y = {"pe": 2.0}; t = {"pe": 3.5}  # +75% but abs +1.5
        assert rule_pe_jump("2330", y, t) is None

    def test_negative_only_abs_breached_pct_too_small(self):
        # big baseline so +10 abs is < 20%
        y = {"pe": 100.0}; t = {"pe": 115.0}  # +15%, abs +15
        assert rule_pe_jump("2330", y, t) is None

    def test_negative_missing_pe(self, baseline_ticker):
        today = dict(baseline_ticker); today["pe"] = None
        assert rule_pe_jump("2330", baseline_ticker, today) is None


# ---------------------------------------------------------------------------
# Rule R3 — P/B jump
# ---------------------------------------------------------------------------


class TestRulePBJump:
    def test_positive(self, baseline_ticker):
        today = dict(baseline_ticker); today["pb"] = 5.5  # +37.5%, abs +1.5
        a = rule_pb_jump("2330", baseline_ticker, today)
        assert a is not None and a.rule == "R3" and a.severity == "MEDIUM"

    def test_negative_small_abs(self):
        y = {"pb": 0.4}; t = {"pb": 0.6}  # +50% but abs +0.2
        assert rule_pb_jump("2330", y, t) is None

    def test_negative_small_pct(self):
        y = {"pb": 10.0}; t = {"pb": 12.0}  # +20%, fails 25% threshold
        assert rule_pb_jump("2330", y, t) is None


# ---------------------------------------------------------------------------
# Rule R4 — market-cap / price divergence (capital action)
# ---------------------------------------------------------------------------


class TestRuleMktCapDivergence:
    def test_positive_mktcap_jumps_but_price_flat(self, baseline_ticker):
        # +15% mkt cap but price unchanged → capital increase suspect
        today = dict(baseline_ticker); today["market_cap_m"] = 57_500
        a = rule_mktcap_divergence("2330", baseline_ticker, today)
        assert a is not None and a.rule == "R4" and a.severity == "HIGH"

    def test_negative_mktcap_tracks_price(self, baseline_ticker):
        # Both +12% → no divergence
        today = dict(baseline_ticker)
        today["price"] = 112.0
        today["market_cap_m"] = 56_000
        assert rule_mktcap_divergence("2330", baseline_ticker, today) is None

    def test_negative_small_mktcap_move(self, baseline_ticker):
        today = dict(baseline_ticker); today["market_cap_m"] = 53_000  # +6%
        assert rule_mktcap_divergence("2330", baseline_ticker, today) is None


# ---------------------------------------------------------------------------
# Rule R5 — data missing today
# ---------------------------------------------------------------------------


class TestRuleDataMissing:
    def test_positive_price_and_pe_both_missing(self, baseline_ticker):
        today = {"price": None, "pe": None, "pb": None}
        a = rule_data_missing("2330", baseline_ticker, today)
        assert a is not None and a.rule == "R5" and a.severity == "HIGH"

    def test_negative_present_today(self, baseline_ticker):
        today = dict(baseline_ticker)
        assert rule_data_missing("2330", baseline_ticker, today) is None

    def test_negative_was_missing_yesterday_too(self):
        yday = {"price": None, "pe": None, "pb": None}
        today = {"price": None, "pe": None, "pb": None}
        assert rule_data_missing("2330", yday, today) is None


# ---------------------------------------------------------------------------
# Rule R6 — ex-dividend (yield drops to 0)
# ---------------------------------------------------------------------------


class TestRuleExDividend:
    def test_positive(self, baseline_ticker):
        today = dict(baseline_ticker); today["yield_pct"] = 0.0
        a = rule_ex_dividend("2330", baseline_ticker, today)
        assert a is not None and a.rule == "R6" and a.severity == "INFO"

    def test_negative_yield_unchanged(self, baseline_ticker):
        today = dict(baseline_ticker)
        assert rule_ex_dividend("2330", baseline_ticker, today) is None

    def test_negative_was_zero_yesterday_already(self):
        y = {"yield_pct": 0.0}; t = {"yield_pct": 0.0}
        assert rule_ex_dividend("2330", y, t) is None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TestDetectAnomalies:
    def test_returns_empty_when_snapshots_match(self, snapshot_yday):
        today = json.loads(json.dumps(snapshot_yday))
        today["snapshot_date"] = "2026-05-23"
        assert detect_anomalies(snapshot_yday, today) == []

    def test_returns_high_first_then_medium_then_info(self, snapshot_yday):
        today = json.loads(json.dumps(snapshot_yday))
        today["snapshot_date"] = "2026-05-23"
        # mutate one ticker to trip multiple rules
        t = today["tickers"]["2330"]
        t["price"] = 115.0          # +15% → R1 HIGH
        t["pe"] = 25.0              # +25% / +5 → R2 MEDIUM
        t["yield_pct"] = 0.0        # → R6 INFO
        results = detect_anomalies(snapshot_yday, today)
        sevs = [a.severity for a in results]
        assert sevs == sorted(sevs, key=lambda s: {"HIGH": 0, "MEDIUM": 1, "INFO": 2}[s])
        assert "R1" in [a.rule for a in results]
        assert "R2" in [a.rule for a in results]
        assert "R6" in [a.rule for a in results]

    def test_skips_new_listings(self, snapshot_yday):
        today = json.loads(json.dumps(snapshot_yday))
        today["snapshot_date"] = "2026-05-23"
        today["tickers"]["9999"] = {"price": 50.0, "pe": 10.0, "pb": 1.0,
                                    "yield_pct": 0.0, "market_cap_m": 1000,
                                    "source": "TPEX"}
        assert detect_anomalies(snapshot_yday, today) == []


class TestFormatText:
    def test_format_text_groups_by_severity(self):
        anomalies = [
            Anomaly(ticker="2330", rule="R1", severity="HIGH",
                    message="price +9.8%", yday={}, today={}),
            Anomaly(ticker="5274", rule="R2", severity="MEDIUM",
                    message="pe +25%", yday={}, today={}),
        ]
        out = format_text(anomalies)
        assert "HIGH" in out and "MEDIUM" in out
        assert "2330" in out and "5274" in out

    def test_format_text_empty(self):
        out = format_text([])
        assert "no anomaly" in out.lower() or "0 " in out
