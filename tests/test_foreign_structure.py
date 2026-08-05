# -*- coding: utf-8 -*-
"""Tests for scripts/foreign_structure.py — 外資結構背離 (pure layers)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from foreign_structure import (  # noqa: E402
    classify,
    render_report,
    rolling_sum,
    zscore,
)


class TestZscore:
    def test_basic(self):
        z, note = zscore(10, [0] * 10 + [2] * 10)  # mean=1
        assert z is not None and z > 0
        assert note is None

    def test_insufficient_history(self):
        z, note = zscore(5, [1, 2, 3])
        assert z is None
        assert "insufficient-history(n=3)" in note

    def test_degenerate_std(self):
        z, note = zscore(5, [7] * 30)
        assert z is None
        assert "degenerate" in note


class TestRollingSum:
    def test_window(self):
        series = [("d1", 1), ("d2", 2), ("d3", 3), ("d4", 4)]
        out = rolling_sum(series, window=2)
        assert out[-1] == ("d4", 7)
        assert out[1] == ("d2", 3)

    def test_short_series(self):
        out = rolling_sum([("d1", 5)], window=5)
        assert out == [("d1", 5)]


class TestClassify:
    def test_hedged_accumulation(self):
        assert classify(1.2, -0.8) == "hedged_accumulation"

    def test_distribution_cover(self):
        assert classify(-0.9, 0.7) == "distribution_cover"

    def test_aligned_bull(self):
        assert classify(1.0, 1.0) == "aligned_bull"

    def test_aligned_bear(self):
        assert classify(-1.0, -0.6) == "aligned_bear"

    def test_neutral_inside_band(self):
        assert classify(0.2, -0.3) == "neutral"

    def test_none_z_neutral_with_gate(self):
        assert classify(None, -1.0) == "insufficient-history"
        assert classify(1.0, None) == "insufficient-history"


class TestRenderReport:
    def test_contains_classification_and_verification(self):
        rows = [{"date": "2026-08-04", "spot_5d": 61.2e9, "spot_z": 1.1,
                 "fut_net": -87858, "fut_z": -0.9}]
        md = render_report("2026-08-05", "hedged_accumulation", rows,
                          spot_note=None, fut_note=None)
        assert "hedged_accumulation" in md
        assert "Verification log" in md
        assert "-87,858" in md or "-87858" in md

    def test_insufficient_note_rendered(self):
        md = render_report("2026-08-05", "insufficient-history", [],
                          spot_note=None, fut_note="insufficient-history(n=12)")
        assert "insufficient-history(n=12)" in md
