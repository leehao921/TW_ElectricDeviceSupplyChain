"""Rolling follow-through hit-rate stat for the bb-followthrough daily digest.

Recent BB breakouts have been failing a lot (11 of 13 graduated = failed). The
digest should surface a rolling "近N日 follow-through 命中率" computed from the
lifetime history log so weak-tape periods are visible every run.

- compute_hitrate: pure function, windows history by graduated_on, counts success
  (波段/confirmed) vs failed, computes hit_rate / avg peak / median exit.
- format_hitrate_line: renders a concise markdown block, incl. the n==0 branch.
- build_digest: output contains the 命中率 section when history is injected.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bb_followthrough_track as bft  # noqa: E402


def _h(ticker: str, on: str, status: str, cumret: float, maxret: float) -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "first_seen": on,
        "graduated_on": on,
        "final_status": status,
        "days_tracked": 5,
        "cumret_pct": cumret,
        "max_cumret_pct": maxret,
    }


# ------------------------------------------------------------------ #
# compute_hitrate
# ------------------------------------------------------------------ #
def test_compute_hitrate_window_excludes_old_entries():
    hist = [
        _h("A", "2026-06-01", "failed", -8.0, 0.0),   # 38 days before → excluded
        _h("B", "2026-07-01", "波段", 10.0, 12.0),     # in window
        _h("C", "2026-07-05", "failed", -5.0, 2.0),    # in window
    ]
    s = bft.compute_hitrate(hist, as_of="2026-07-09", window_days=30)
    assert s["n"] == 2, "only entries within 30 days counted"
    assert s["n_success"] == 1
    assert s["all_time_n"] == 3
    assert s["all_time_success"] == 1


def test_compute_hitrate_math_and_stats():
    hist = [
        _h("A", "2026-07-02", "波段", 10.0, 12.0),
        _h("B", "2026-07-03", "confirmed", 6.0, 8.0),
        _h("C", "2026-07-04", "failed", -8.0, 2.0),
        _h("D", "2026-07-05", "failed", -4.0, 4.0),
    ]
    s = bft.compute_hitrate(hist, as_of="2026-07-09", window_days=30)
    assert s["n"] == 4
    assert s["n_success"] == 2  # 波段 + confirmed
    assert s["hit_rate_pct"] == 50.0
    # avg max_cumret = (12+8+2+4)/4 = 6.5
    assert abs(s["avg_max_cumret"] - 6.5) < 1e-9
    # median exit of [10,6,-8,-4] sorted [-8,-4,6,10] → (-4+6)/2 = 1.0
    assert abs(s["median_exit_cumret"] - 1.0) < 1e-9


def test_compute_hitrate_median_odd_count():
    hist = [
        _h("A", "2026-07-02", "波段", 10.0, 12.0),
        _h("B", "2026-07-03", "failed", -8.0, 2.0),
        _h("C", "2026-07-04", "failed", -4.0, 4.0),
    ]
    s = bft.compute_hitrate(hist, as_of="2026-07-09", window_days=30)
    # median of [10,-8,-4] sorted [-8,-4,10] → -4
    assert abs(s["median_exit_cumret"] - (-4.0)) < 1e-9


def test_compute_hitrate_empty_window_returns_none():
    hist = [_h("A", "2026-06-01", "failed", -8.0, 0.0)]  # outside 30d window
    s = bft.compute_hitrate(hist, as_of="2026-07-09", window_days=30)
    assert s["n"] == 0
    assert s["hit_rate_pct"] is None
    assert s["avg_max_cumret"] is None
    assert s["median_exit_cumret"] is None
    assert s["all_time_n"] == 1


def test_compute_hitrate_empty_history():
    s = bft.compute_hitrate([], as_of="2026-07-09", window_days=30)
    assert s["n"] == 0
    assert s["all_time_n"] == 0
    assert s["all_time_success"] == 0
    assert s["hit_rate_pct"] is None


def test_compute_hitrate_boundary_inclusive():
    # entry exactly window_days back must be included
    hist = [_h("A", "2026-06-09", "波段", 5.0, 6.0)]
    s = bft.compute_hitrate(hist, as_of="2026-07-09", window_days=30)
    assert s["n"] == 1


# ------------------------------------------------------------------ #
# format_hitrate_line
# ------------------------------------------------------------------ #
def test_format_hitrate_line_populated():
    stats = {
        "window_days": 30, "n": 13, "n_success": 2,
        "hit_rate_pct": 15.384, "avg_max_cumret": 3.2,
        "median_exit_cumret": -8.4, "all_time_n": 13, "all_time_success": 2,
    }
    line = bft.format_hitrate_line(stats)
    assert "命中率" in line
    assert "2/13" in line
    assert "15%" in line
    assert "全期 2/13" in line


def test_format_hitrate_line_empty_window():
    stats = {
        "window_days": 30, "n": 0, "n_success": 0,
        "hit_rate_pct": None, "avg_max_cumret": None,
        "median_exit_cumret": None, "all_time_n": 5, "all_time_success": 3,
    }
    line = bft.format_hitrate_line(stats)
    assert "命中率" in line
    assert "無畢業樣本" in line
    assert "全期 3/5" in line


# ------------------------------------------------------------------ #
# build_digest wiring
# ------------------------------------------------------------------ #
def test_build_digest_includes_hitrate_section():
    state = {"last_updated": "2026-07-09", "tracked": {}}
    hist = [
        _h("A", "2026-07-02", "波段", 10.0, 12.0),
        _h("B", "2026-07-03", "failed", -8.0, 2.0),
    ]
    digest = bft.build_digest(state, "2026-07-09", [], [], history=hist)
    assert "命中率" in digest
    assert "1/2" in digest
