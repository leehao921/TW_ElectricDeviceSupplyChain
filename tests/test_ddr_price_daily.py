# -*- coding: utf-8 -*-
"""Tests for scripts/ddr_price_daily.py — DRAMeXchange 現貨日更 (pure layers)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ddr_price_daily import (  # noqa: E402
    TARGET_ITEMS,
    monthly_series,
    parse_spot,
    update_yaml_ddr4,
)

SAMPLE = """
<td><a href="/Price/Dram_Spot"><img src="x.gif">DDR4 8Gb (1Gx8) 3200</a></td>
<td class="tab_tr_gray">74.00</td>
<td class="tab_tr_gray">20.80</td>
<td class="tab_tr_gray">74.00</td>
<td class="tab_tr_gray">20.80</td>
<td class="tab_tr_gray">42.504</td>
<td class="tab_tr_font9">1.25%</td>
<td><a href="/Price/Dram_Spot"><img src="x.gif">DDR5 16Gb (2Gx8) 4800/5600</a></td>
<td class="tab_tr_gray">99.00</td>
<td class="tab_tr_gray">30.00</td>
<td class="tab_tr_gray">99.00</td>
<td class="tab_tr_gray">30.00</td>
<td class="tab_tr_gray">55.100</td>
<td class="tab_tr_font9">-0.30%</td>
"""


class TestParseSpot:
    def test_extracts_session_average_and_change(self):
        out = parse_spot(SAMPLE)
        assert out["DDR4 8Gb (1Gx8) 3200"]["avg"] == 42.504
        assert out["DDR4 8Gb (1Gx8) 3200"]["chg_pct"] == 1.25
        assert out["DDR5 16Gb (2Gx8) 4800/5600"]["avg"] == 55.1
        assert out["DDR5 16Gb (2Gx8) 4800/5600"]["chg_pct"] == -0.30

    def test_missing_item_absent(self):
        out = parse_spot("<td>nothing here</td>")
        assert out == {}

    def test_targets_defined(self):
        assert "DDR4 8Gb (1Gx8) 3200" in TARGET_ITEMS
        assert "DDR5 16Gb (2Gx8) 4800/5600" in TARGET_ITEMS


class TestMonthlySeries:
    def test_mtd_average_per_month(self):
        hist = {
            "2026-07-30": {"DDR4 8Gb (1Gx8) 3200": {"avg": 40.0}},
            "2026-07-31": {"DDR4 8Gb (1Gx8) 3200": {"avg": 42.0}},
            "2026-08-10": {"DDR4 8Gb (1Gx8) 3200": {"avg": 42.0}},
            "2026-08-11": {"DDR4 8Gb (1Gx8) 3200": {"avg": 43.0}},
        }
        s = monthly_series(hist, "DDR4 8Gb (1Gx8) 3200")
        assert s == [("2026-07", 41.0), ("2026-08", 42.5)]

    def test_missing_item_days_skipped(self):
        hist = {"2026-08-11": {"other": {"avg": 1.0}}}
        assert monthly_series(hist, "DDR4 8Gb (1Gx8) 3200") == []


class TestUpdateYamlDdr4:
    YAML = """last_updated: 2026-06-25
notes: "Initial template — please replace with real TrendForce numbers."

ddr4_8gb_spot_usd:
  - {month: "2026-04", price: 2.85}
  - {month: "2026-05", price: 3.12}

ddr5_16gb_contract_usd:
  - {quarter: "2026Q1", price: 4.20}
  - {quarter: "2026Q2", price: 5.10}

mu_next_quarter_gm_guide: 0.86
mu_next_quarter_rev_qoq: 0.20
"""

    def test_replaces_ddr4_series_keeps_manual_fields(self):
        out = update_yaml_ddr4(self.YAML, [("2026-07", 40.5), ("2026-08", 42.5)],
                               today="2026-08-11")
        assert '{month: "2026-07", price: 40.5}' in out
        assert '{month: "2026-08", price: 42.5}' in out
        assert '{month: "2026-04"' not in out          # 舊 series 整段被取代
        assert '{quarter: "2026Q2", price: 5.10}' in out  # 手動欄位保留
        assert "mu_next_quarter_gm_guide: 0.86" in out
        assert "last_updated: 2026-08-11" in out

    def test_yaml_still_loadable_by_monitor(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mcm", Path(__file__).resolve().parents[1] / "scripts" / "memory_cycle_monitor.py")
        mcm = importlib.util.module_from_spec(spec)
        sys.modules["mcm"] = mcm
        spec.loader.exec_module(mcm)
        out = update_yaml_ddr4(self.YAML, [("2026-07", 40.5), ("2026-08", 42.5)],
                               today="2026-08-11")
        tmp = Path("/tmp/test_mcm_inputs.yaml")
        tmp.write_text(out, encoding="utf-8")
        inputs = mcm.load_inputs(tmp)
        assert [p.price for p in inputs.ddr4_8gb_spot_usd] == [40.5, 42.5]
        assert len(inputs.ddr5_16gb_contract_usd) == 2
