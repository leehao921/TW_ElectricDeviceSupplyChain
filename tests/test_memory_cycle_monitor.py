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


from pathlib import Path
import pytest
from scripts.memory_cycle_monitor import load_inputs

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_inputs_full_fixture():
    inp = load_inputs(FIXTURES / "memory_cycle_full.yaml")
    assert inp.last_updated == "2026-06-25"
    assert len(inp.ddr4_8gb_spot_usd) == 4
    assert inp.ddr4_8gb_spot_usd[0].label == "2026-03"
    assert inp.ddr4_8gb_spot_usd[-1].price == 3.45
    assert len(inp.ddr5_16gb_contract_usd) == 3
    assert inp.ddr5_16gb_contract_usd[0].label == "2025Q4"
    assert inp.mu_next_quarter_gm_guide == 0.86


def test_load_inputs_minimal_fixture():
    inp = load_inputs(FIXTURES / "memory_cycle_minimal.yaml")
    assert len(inp.ddr4_8gb_spot_usd) == 2
    assert len(inp.ddr5_16gb_contract_usd) == 2
    assert inp.mu_next_quarter_gm_guide is None


def test_load_inputs_sorts_unordered_dates(tmp_path):
    p = tmp_path / "unordered.yaml"
    p.write_text("""
last_updated: 2026-06-25
notes: ""
ddr4_8gb_spot_usd:
  - {month: "2026-06", price: 3.45}
  - {month: "2026-04", price: 2.85}
  - {month: "2026-05", price: 3.12}
""")
    inp = load_inputs(p)
    labels = [pp.label for pp in inp.ddr4_8gb_spot_usd]
    assert labels == ["2026-04", "2026-05", "2026-06"]


def test_load_inputs_raises_on_missing_required_field(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("notes: 'missing last_updated'\n")
    with pytest.raises(ValueError, match="last_updated"):
        load_inputs(p)


from scripts.memory_cycle_monitor import compute_s2a_ddr4


def _ddr4(prices: list[float]) -> list[PricePoint]:
    return [PricePoint(label=f"2026-{i+1:02d}", price=p) for i, p in enumerate(prices)]


def test_s2a_green_when_positive_mom():
    r = compute_s2a_ddr4(_ddr4([3.0, 3.2, 3.45]))
    assert r.light == GREEN
    assert "+" in r.value  # e.g. "+7.8%"


def test_s2a_yellow_on_first_negative_mom():
    r = compute_s2a_ddr4(_ddr4([3.0, 3.2, 3.1]))  # latest down
    assert r.light == YELLOW


def test_s2a_red_on_two_consecutive_negative_mom():
    r = compute_s2a_ddr4(_ddr4([3.5, 3.2, 3.0]))  # two down months
    assert r.light == RED


def test_s2a_consecutive_resets_on_positive_in_between():
    # down, up, down → latest negative but not consecutive → YELLOW not RED
    r = compute_s2a_ddr4(_ddr4([3.5, 3.2, 3.4, 3.3]))
    assert r.light == YELLOW


def test_s2a_na_when_fewer_than_2_points():
    r = compute_s2a_ddr4(_ddr4([3.0]))
    assert r.light == "N/A"
