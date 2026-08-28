"""Tests for geo_composite_daily pure functions and load_yf cache staleness.

Coverage:
- evaluate_strength: regulation / rates / oil channels (incl. oil single-side no-fire)
- evaluate_fragility: iv / foreign / margin components
- light: RED / YELLOW / GREEN tri-state
- settle_alerts: hit / false / under-20-days-no-op / already-settled idempotent
- load_yf staleness: stale → refetch; fresh → no network hit
- C1: settle_alerts works with object-dtype datetime.date index (production dtype)
- I1: _latest_z returns None for empty / all-NaN / None series
- I2: _load_state renames corrupt JSON to .corrupt-<timestamp> instead of silently eating it
"""
from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Import helpers — keep these at module level so pytest can collect them even
# before the implementation files exist (they'll fail with ImportError, which
# surfaces as collection errors rather than silent skips).
# ──────────────────────────────────────────────────────────────────────────────
from scripts.geo_composite_daily import (
    evaluate_strength,
    evaluate_fragility,
    light,
    settle_alerts,
    _latest_z,
    _load_state,
)
from scripts.geo_attr.loaders import load_yf


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _bdate_index(n: int, start="2025-01-02") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


def _index_series(n: int = 250, start="2025-01-02") -> pd.Series:
    """Simple monotonic-ish price series on business days."""
    import numpy as np
    rng = pd.bdate_range(start, periods=n)
    prices = 100 * (1 + pd.Series(range(n), index=rng) * 0.0005)
    return prices


# ══════════════════════════════════════════════════════════════════════════════
# evaluate_strength
# ══════════════════════════════════════════════════════════════════════════════

class TestEvaluateStrength:
    def _base_z(self):
        return {
            "gdelt_semi_export_vol": 0.5,
            "gdelt_tariff_tone": 0.5,
            "ust10y_surge": 0.5,
            "brent_shock": 0.5,
            "gdelt_mideast_oil_vol": 0.5,
        }

    # --- regulation channel ---

    def test_regulation_via_semi_export(self):
        z = self._base_z()
        z["gdelt_semi_export_vol"] = 2.5   # > Z_THR
        r = evaluate_strength(z)
        assert r["regulation"] is True
        assert r["triggered"] is True

    def test_regulation_via_tariff_tone(self):
        z = self._base_z()
        z["gdelt_tariff_tone"] = 2.1
        r = evaluate_strength(z)
        assert r["regulation"] is True
        assert r["triggered"] is True

    def test_regulation_neither_fires_not_triggered(self):
        z = self._base_z()
        # both < 2.0
        r = evaluate_strength(z)
        assert r["regulation"] is False

    def test_regulation_exactly_at_threshold_not_triggered(self):
        z = self._base_z()
        z["gdelt_semi_export_vol"] = 2.0   # not STRICTLY > 2
        r = evaluate_strength(z)
        assert r["regulation"] is False

    # --- rates channel ---

    def test_rates_fires_above_threshold(self):
        z = self._base_z()
        z["ust10y_surge"] = 2.3
        r = evaluate_strength(z)
        assert r["rates"] is True
        assert r["triggered"] is True

    def test_rates_no_fire_below_threshold(self):
        z = self._base_z()
        r = evaluate_strength(z)
        assert r["rates"] is False

    # --- oil channel — DUAL confirmation ---

    def test_oil_both_above_threshold_fires(self):
        z = self._base_z()
        z["brent_shock"] = 2.5
        z["gdelt_mideast_oil_vol"] = 2.1
        r = evaluate_strength(z)
        assert r["oil"] is True
        assert r["triggered"] is True

    def test_oil_only_brent_above_does_not_fire(self):
        """brent_shock > 2 but mideast_oil_vol ≤ 2 → oil = False (single-side FAR is high)."""
        z = self._base_z()
        z["brent_shock"] = 3.0
        z["gdelt_mideast_oil_vol"] = 1.5  # NOT above threshold
        r = evaluate_strength(z)
        assert r["oil"] is False

    def test_oil_only_mideast_above_does_not_fire(self):
        """mideast_oil_vol > 2 but brent_shock ≤ 2 → oil = False."""
        z = self._base_z()
        z["brent_shock"] = 1.5
        z["gdelt_mideast_oil_vol"] = 3.0
        r = evaluate_strength(z)
        assert r["oil"] is False

    def test_oil_neither_above_does_not_fire(self):
        z = self._base_z()
        r = evaluate_strength(z)
        assert r["oil"] is False

    # --- None values treated as not triggered ---

    def test_none_z_values_not_triggered(self):
        z = {k: None for k in self._base_z()}
        r = evaluate_strength(z)
        assert r["regulation"] is False
        assert r["rates"] is False
        assert r["oil"] is False
        assert r["triggered"] is False

    def test_none_oil_brent_not_triggered(self):
        z = self._base_z()
        z["brent_shock"] = None
        z["gdelt_mideast_oil_vol"] = 3.0
        r = evaluate_strength(z)
        assert r["oil"] is False

    # --- triggered = any channel ---

    def test_triggered_false_when_all_channels_clear(self):
        z = self._base_z()
        r = evaluate_strength(z)
        assert r["triggered"] is False

    def test_detail_key_present(self):
        r = evaluate_strength(self._base_z())
        assert "detail" in r


# ══════════════════════════════════════════════════════════════════════════════
# evaluate_fragility
# ══════════════════════════════════════════════════════════════════════════════

class TestEvaluateFragility:

    def test_iv_via_inverted(self):
        r = evaluate_fragility(iv_inverted=True, vrp_neg=False,
                               foreign_z=0.5, margin_score=None)
        assert r["iv"] is True
        assert r["triggered"] is True

    def test_iv_via_vrp_neg(self):
        r = evaluate_fragility(iv_inverted=False, vrp_neg=True,
                               foreign_z=0.5, margin_score=None)
        assert r["iv"] is True
        assert r["triggered"] is True

    def test_iv_neither_flag_false(self):
        r = evaluate_fragility(iv_inverted=False, vrp_neg=False,
                               foreign_z=0.5, margin_score=None)
        assert r["iv"] is False

    def test_foreign_fires_above_threshold(self):
        r = evaluate_fragility(iv_inverted=False, vrp_neg=False,
                               foreign_z=2.3, margin_score=None)
        assert r["foreign"] is True
        assert r["triggered"] is True

    def test_foreign_no_fire_below_threshold(self):
        r = evaluate_fragility(iv_inverted=False, vrp_neg=False,
                               foreign_z=1.9, margin_score=None)
        assert r["foreign"] is False

    def test_foreign_none_not_triggered(self):
        r = evaluate_fragility(iv_inverted=False, vrp_neg=False,
                               foreign_z=None, margin_score=None)
        assert r["foreign"] is False

    def test_margin_score_1_fires(self):
        r = evaluate_fragility(iv_inverted=False, vrp_neg=False,
                               foreign_z=0.5, margin_score=1)
        assert r["margin"] is True
        assert r["triggered"] is True

    def test_margin_score_0_not_fired(self):
        r = evaluate_fragility(iv_inverted=False, vrp_neg=False,
                               foreign_z=0.5, margin_score=0)
        assert r["margin"] is False

    def test_margin_none_not_triggered(self):
        r = evaluate_fragility(iv_inverted=False, vrp_neg=False,
                               foreign_z=0.5, margin_score=None)
        # M3: margin_score=None → margin returns None (not False)
        assert r["margin"] is None
        # None margin must not contribute to triggered
        assert r["triggered"] is False

    def test_all_components_clear_not_triggered(self):
        r = evaluate_fragility(iv_inverted=False, vrp_neg=False,
                               foreign_z=0.5, margin_score=0)
        assert r["triggered"] is False


# ══════════════════════════════════════════════════════════════════════════════
# light
# ══════════════════════════════════════════════════════════════════════════════

class TestLight:

    def _strength(self, triggered: bool) -> dict:
        return {"regulation": triggered, "rates": False, "oil": False,
                "triggered": triggered, "detail": {}}

    def _fragility(self, triggered: bool) -> dict:
        return {"iv": triggered, "foreign": False, "margin": False,
                "triggered": triggered}

    def test_red_both_triggered(self):
        assert light(self._strength(True), self._fragility(True)) == "紅"

    def test_yellow_only_strength(self):
        assert light(self._strength(True), self._fragility(False)) == "黃"

    def test_yellow_only_fragility(self):
        assert light(self._strength(False), self._fragility(True)) == "黃"

    def test_green_neither(self):
        assert light(self._strength(False), self._fragility(False)) == "綠"


# ══════════════════════════════════════════════════════════════════════════════
# settle_alerts
# ══════════════════════════════════════════════════════════════════════════════

class TestSettleAlerts:
    """
    Fixture construction:
      index_s is 250 business days starting 2025-01-02.
      We craft specific price paths to guarantee hit vs false outcomes.

    hit fixture  (alert_date = day 0 in index_s):
      Prices days 1-20 dip to min -4%  →  r_min < -0.03  →  hit
    false fixture (alert_date = day 50):
      Prices days 51-70 only dip to min -1%  →  r_min > -0.03  →  false
    """

    def _make_index_series(self):
        # Use object-dtype datetime.date index — matches production dtype.
        bdays = list(pd.bdate_range("2025-01-02", periods=250).date)
        prices = pd.Series(100.0, index=bdays)
        # hit scenario: days 1..20 (index positions 1..20), trough at day 10 = 95.0
        for i in range(1, 21):
            prices.iloc[i] = 95.0 if i == 10 else 98.0  # min 95 → -5%
        # false scenario: days 51..70, trough at day 60 = 99.0
        for i in range(51, 71):
            prices.iloc[i] = 99.0 if i == 60 else 100.5  # min 99 → -1%
        return prices

    def _base_records(self, index_s):
        # index_s.index is object-dtype datetime.date; .isoformat() directly.
        hit_date = index_s.index[0].isoformat()
        false_date = index_s.index[50].isoformat()
        return [
            {"date": hit_date,   "light": "紅", "strength": {}, "fragility": {}},
            {"date": false_date, "light": "紅", "strength": {}, "fragility": {}},
        ]

    def test_hit_and_false_settled_correctly(self):
        index_s = self._make_index_series()
        asof = index_s.index[80]  # well past both + 20 days (datetime.date)
        records = self._base_records(index_s)
        result = settle_alerts(records, index_s, asof)

        hit_rec = result[0]
        false_rec = result[1]

        assert hit_rec.get("settle") == "hit",   f"Expected hit, got {hit_rec.get('settle')}"
        assert false_rec.get("settle") == "false", f"Expected false, got {false_rec.get('settle')}"

    def test_under_20_days_not_touched(self):
        index_s = self._make_index_series()
        # asof only 10 business days past first alert date
        asof = index_s.index[10]  # datetime.date
        records = self._base_records(index_s)
        result = settle_alerts(records, index_s, asof)

        # neither record has enough distance → no settle written
        assert "settle" not in result[0]
        assert "settle" not in result[1]

    def test_already_settled_not_recalculated(self):
        """Once settle is written, it must not be overwritten on re-run."""
        index_s = self._make_index_series()
        asof = index_s.index[80]
        records = self._base_records(index_s)
        # Pre-populate settle for first record with wrong value
        records[0]["settle"] = "false"  # intentionally wrong
        result = settle_alerts(records, index_s, asof)

        # Must remain "false" (not re-computed to "hit")
        assert result[0]["settle"] == "false"

    def test_non_red_records_not_touched(self):
        index_s = self._make_index_series()
        asof = index_s.index[80]
        date_str = index_s.index[0].isoformat()
        records = [{"date": date_str, "light": "黃", "strength": {}, "fragility": {}}]
        result = settle_alerts(records, index_s, asof)
        assert "settle" not in result[0]

    def test_alert_date_not_in_index_skipped(self):
        """Alert on a weekend/holiday date not in index_s → skip gracefully."""
        index_s = self._make_index_series()
        asof = index_s.index[80]
        records = [
            {"date": "2025-01-04",  "light": "紅", "strength": {}, "fragility": {}},  # Saturday
            {"date": "2025-01-05",  "light": "紅", "strength": {}, "fragility": {}},  # Sunday
        ]
        # Ensure these are NOT in index_s (index is already datetime.date objects)
        idx_dates = set(index_s.index)
        records = [r for r in records if dt.date.fromisoformat(r["date"]) not in idx_dates]
        if not records:
            # if both happen to be bdays for this run, just confirm no crash
            records = [{"date": "2025-01-01", "light": "紅", "strength": {}, "fragility": {}}]
        result = settle_alerts(records, index_s, asof)
        # Should not crash; records without index entry remain unsettled
        for rec in result:
            d = dt.date.fromisoformat(rec["date"])
            if d not in idx_dates:
                assert "settle" not in rec


# ══════════════════════════════════════════════════════════════════════════════
# load_yf cache staleness
# ══════════════════════════════════════════════════════════════════════════════

class TestLoadYfStaleness:
    """
    Staleness rule: cache max_date < today - 1 calendar day → refetch.
    Fresh cache (max_date == today - 1) → read from disk, no network.
    """

    def _write_cache(self, path: Path, max_date: dt.date) -> None:
        """Write a minimal CSV cache with the given max date."""
        import io
        dates = pd.date_range("2025-01-01", max_date, freq="B")
        prices = pd.Series(100.0, index=dates, name="close")
        prices.index = [d.date() for d in prices.index]
        prices.index.name = "date"
        path.write_text(prices.to_frame().to_csv())

    def test_stale_cache_triggers_refetch(self):
        """If cache is 2+ days old, yfinance.Ticker must be called."""
        today = dt.date.today()
        stale_date = today - dt.timedelta(days=3)  # clearly stale

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "test_ticker.csv"
            self._write_cache(cache_file, stale_date)

            mock_hist = pd.DataFrame(
                {"Close": [101.0, 102.0]},
                index=pd.date_range("2025-01-01", periods=2),
            )
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = mock_hist

            with patch("scripts.geo_attr.loaders.CACHE_DIR", cache_dir), \
                 patch("scripts.geo_attr.loaders.yf") as mock_yf:
                mock_yf.Ticker.return_value = mock_ticker
                load_yf("TEST", "test_ticker", start="2025-01-01")

            mock_yf.Ticker.assert_called_once_with("TEST")

    def test_fresh_cache_no_network(self):
        """If cache is fresh (max_date == yesterday), yfinance must NOT be touched."""
        today = dt.date.today()
        fresh_date = today - dt.timedelta(days=1)  # yesterday = fresh

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "test_fresh.csv"
            self._write_cache(cache_file, fresh_date)

            with patch("scripts.geo_attr.loaders.CACHE_DIR", cache_dir), \
                 patch("scripts.geo_attr.loaders.yf") as mock_yf:
                mock_yf.Ticker.side_effect = AssertionError("Network should NOT be called for fresh cache")
                result = load_yf("TEST", "test_fresh", start="2025-01-01")

            # Result must be non-empty and from cache
            assert len(result) > 0

    def test_fresh_cache_today_no_network(self):
        """If cache max_date == today, it's definitely fresh."""
        today = dt.date.today()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "test_today.csv"
            self._write_cache(cache_file, today)

            with patch("scripts.geo_attr.loaders.CACHE_DIR", cache_dir), \
                 patch("scripts.geo_attr.loaders.yf") as mock_yf:
                mock_yf.Ticker.side_effect = AssertionError("Should not hit network for today's cache")
                result = load_yf("TEST", "test_today", start="2025-01-01")

            assert len(result) > 0

    def test_missing_cache_triggers_fetch(self):
        """No cache file → must call yfinance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            mock_hist = pd.DataFrame(
                {"Close": [100.0]},
                index=pd.date_range("2025-01-02", periods=1),
            )
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = mock_hist

            with patch("scripts.geo_attr.loaders.CACHE_DIR", cache_dir), \
                 patch("scripts.geo_attr.loaders.yf") as mock_yf:
                mock_yf.Ticker.return_value = mock_ticker
                load_yf("TEST", "test_missing", start="2025-01-01")

            mock_yf.Ticker.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# C1 — settle_alerts must work with object-dtype datetime.date index
# ══════════════════════════════════════════════════════════════════════════════

class TestSettleAlertsDateDtype:
    """C1 regression: production index_s.index is object-dtype of datetime.date,
    NOT a DatetimeIndex.  settle_alerts must work correctly with native date keys.
    """

    def _make_date_index_series(self):
        """Build a Series whose index is Python datetime.date objects (production dtype)."""
        import numpy as np
        bdays = list(pd.bdate_range("2025-01-02", periods=250).date)
        prices = pd.Series(100.0, index=bdays)
        # hit scenario: positions 1..20, trough at 10 = 95.0 (-5%)
        for i in range(1, 21):
            prices.iloc[i] = 95.0 if i == 10 else 98.0
        # false scenario: positions 51..70, trough at 60 = 99.0 (-1%)
        for i in range(51, 71):
            prices.iloc[i] = 99.0 if i == 60 else 100.5
        return prices

    def test_C1_hit_settled_with_date_index(self):
        """settle_alerts must produce 'hit' when index is object-dtype datetime.date."""
        index_s = self._make_date_index_series()
        # Verify index dtype is object (datetime.date), not DatetimeIndex
        assert not isinstance(index_s.index, pd.DatetimeIndex), (
            "Test fixture must use object-dtype date index, not DatetimeIndex"
        )
        asof = index_s.index[80]  # well past 20 trading days
        hit_date = index_s.index[0]
        records = [{"date": hit_date.isoformat(), "light": "紅", "strength": {}, "fragility": {}}]
        result = settle_alerts(records, index_s, asof)
        assert result[0].get("settle") == "hit", (
            f"C1 FAIL: expected 'hit' got {result[0].get('settle')!r}. "
            "settle_alerts must handle object-dtype datetime.date index."
        )

    def test_C1_false_settled_with_date_index(self):
        """settle_alerts must produce 'false' when index is object-dtype datetime.date."""
        index_s = self._make_date_index_series()
        assert not isinstance(index_s.index, pd.DatetimeIndex)
        asof = index_s.index[80]
        false_date = index_s.index[50]
        records = [{"date": false_date.isoformat(), "light": "紅", "strength": {}, "fragility": {}}]
        result = settle_alerts(records, index_s, asof)
        assert result[0].get("settle") == "false", (
            f"C1 FAIL: expected 'false' got {result[0].get('settle')!r}"
        )

    def test_C1_under_20_days_not_settled_date_index(self):
        """Under 20 trading days must not be settled with date index."""
        index_s = self._make_date_index_series()
        assert not isinstance(index_s.index, pd.DatetimeIndex)
        asof = index_s.index[10]  # only 10 business days
        records = [{"date": index_s.index[0].isoformat(), "light": "紅", "strength": {}, "fragility": {}}]
        result = settle_alerts(records, index_s, asof)
        assert "settle" not in result[0], "C1 FAIL: must not settle with < 20 trading days"


# ══════════════════════════════════════════════════════════════════════════════
# I1 — _latest_z must return None for empty / all-NaN / None input
# ══════════════════════════════════════════════════════════════════════════════

class TestLatestZ:
    """I1 regression: _latest_z must return None (not raise, not return NaN) for
    degenerate inputs — None, empty Series, all-NaN Series.
    """

    def test_I1_none_input_returns_none(self):
        """_latest_z(None) must return None, not raise AttributeError."""
        result = _latest_z(None)
        assert result is None, f"I1 FAIL: _latest_z(None) returned {result!r}, expected None"

    def test_I1_empty_series_returns_none(self):
        """_latest_z(pd.Series([], dtype=float)) must return None."""
        result = _latest_z(pd.Series([], dtype=float))
        assert result is None, f"I1 FAIL: _latest_z(empty) returned {result!r}, expected None"

    def test_I1_all_nan_series_returns_none(self):
        """_latest_z of an all-NaN series must return None, not float('nan')."""
        import math
        s = pd.Series([float("nan"), float("nan")])
        result = _latest_z(s)
        assert result is None, f"I1 FAIL: _latest_z(all-NaN) returned {result!r}, expected None"
        # Extra guard: must not be NaN
        if result is not None:
            assert not math.isnan(result), "I1 FAIL: _latest_z returned NaN instead of None"

    def test_I1_valid_series_returns_float(self):
        """Sanity: _latest_z of a valid series returns the last non-NaN value."""
        s = pd.Series([1.0, 2.0, float("nan"), 3.5])
        result = _latest_z(s)
        assert result == pytest.approx(3.5), f"I1 FAIL: expected 3.5, got {result!r}"

    def test_I1_trailing_nan_returns_none(self):
        """_latest_z checks only the last element; trailing NaN → None."""
        # Per spec: return iloc[-1] or None if NaN — does NOT backfill.
        s = pd.Series([1.0, 2.5, float("nan")])
        result = _latest_z(s)
        assert result is None, (
            f"I1 FAIL: last element is NaN so _latest_z must return None, got {result!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# I2 — _load_state must rename corrupt JSON file instead of silently eating it
# ══════════════════════════════════════════════════════════════════════════════

class TestLoadStateCorruptHandling:
    """I2 regression: when the state file contains invalid JSON, _load_state must
    rename it to geo_composite_state.json.corrupt-<YYYYmmddHHMMSS> (preserving
    the bad data for forensics) and return [], rather than silently swallowing the
    error and losing the evidence.
    """

    def test_I2_corrupt_file_is_renamed(self, tmp_path):
        """Corrupt JSON → file renamed to .corrupt-* → _load_state returns []."""
        state_file = tmp_path / "geo_composite_state.json"
        state_file.write_text("{invalid json!!!", encoding="utf-8")

        result = _load_state(state_file)

        # Must return empty list (graceful degradation)
        assert result == [], f"I2 FAIL: expected [], got {result!r}"

        # Original corrupt file must NOT exist any more
        assert not state_file.exists(), (
            "I2 FAIL: corrupt state file still exists at original path; "
            "it should have been renamed to .corrupt-*"
        )

        # A .corrupt-* file must exist
        corrupt_files = list(tmp_path.glob("geo_composite_state.json.corrupt-*"))
        assert len(corrupt_files) == 1, (
            f"I2 FAIL: expected exactly 1 .corrupt-* file, found: {[f.name for f in corrupt_files]}"
        )

        # The corrupt file must preserve the original (bad) content
        assert corrupt_files[0].read_text(encoding="utf-8") == "{invalid json!!!"

    def test_I2_valid_file_not_renamed(self, tmp_path):
        """Valid JSON file must NOT be renamed."""
        import json
        state_file = tmp_path / "geo_composite_state.json"
        records = [{"date": "2025-01-02", "light": "綠"}]
        state_file.write_text(json.dumps(records), encoding="utf-8")

        result = _load_state(state_file)
        assert result == records
        assert state_file.exists(), "I2 FAIL: valid state file must not be renamed"
        corrupt_files = list(tmp_path.glob("*.corrupt-*"))
        assert len(corrupt_files) == 0, "I2 FAIL: no corrupt file expected for valid JSON"

    def test_I2_missing_file_returns_empty(self, tmp_path):
        """Non-existent state file must return [] without error."""
        state_file = tmp_path / "geo_composite_state.json"
        result = _load_state(state_file)
        assert result == []
