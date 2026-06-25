"""Tests for scripts/memory_cycle_monitor.py — DRAM sell-signal monitor."""
from scripts.memory_cycle_monitor import (
    PB_THRESHOLDS,
    Inputs,
    PricePoint,
    SignalResult,
    GREEN, YELLOW, RED,
)


def test_pb_thresholds_match_spec():
    assert PB_THRESHOLDS["2408.TW"] == {"yellow": 1.8, "red": 2.5}
    assert PB_THRESHOLDS["2344.TW"] == {"yellow": 1.5, "red": 2.0}


def test_signal_result_has_required_fields():
    r = SignalResult(light=GREEN, value="ok", detail={"x": 1})
    assert r.light == "GREEN"
    assert r.value == "ok"
    assert r.detail == {"x": 1}
