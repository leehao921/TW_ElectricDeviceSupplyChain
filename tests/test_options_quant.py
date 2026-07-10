"""Tests for scripts/options_quant.py — pure analysis layer only (no DB)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import options_quant as oq


class TestParseWindow:
    def test_parses_hhmm_range(self):
        assert oq.parse_window("09:00-12:00") == ("09:00", "12:00")

    def test_rejects_bad_format(self):
        with pytest.raises(ValueError):
            oq.parse_window("9am-noon")

    def test_rejects_inverted(self):
        with pytest.raises(ValueError):
            oq.parse_window("12:00-09:00")


class TestSelectFrontExpiry:
    def test_picks_shortest_tenor_with_data(self):
        df = pd.DataFrame({
            "expiry": ["20260715", "20260819", "20260916"],
            "n": [120, 118, 90],
        })
        assert oq.select_front_expiry(df, min_rows=10) == "20260715"

    def test_skips_expiry_with_too_few_rows(self):
        df = pd.DataFrame({"expiry": ["20260715", "20260819"], "n": [3, 200]})
        assert oq.select_front_expiry(df, min_rows=10) == "20260819"

    def test_empty_returns_none(self):
        assert oq.select_front_expiry(pd.DataFrame({"expiry": [], "n": []}), min_rows=10) is None


class TestPercentileWithVerification:
    def test_percentile_and_log(self):
        hist = pd.Series([1.0, 2.0, 3.0, 4.0] * 15)  # n=60
        pct, log = oq.percentile_verified(3.5, hist, metric_name="VRP")
        assert 70 <= pct <= 80
        assert any("n=60" in line for line in log)

    def test_insufficient_history_returns_none(self):
        hist = pd.Series([1.0] * 19)  # n=19 < 20
        pct, log = oq.percentile_verified(3.5, hist, metric_name="VRP")
        assert pct is None
        assert any("insufficient-history(n=19)" in line for line in log)

    def test_small_but_usable_history_flags_n(self):
        hist = pd.Series(list(range(30)))  # 20 <= n < 60
        pct, log = oq.percentile_verified(15, hist, metric_name="VRP")
        assert pct is not None
        assert any("n=30" in line for line in log)

    def test_nan_value_returns_none_not_zero(self):
        # NaN must not rank as 0th percentile (would fake expansion-risk).
        hist = pd.Series(list(range(60)))
        pct, log = oq.percentile_verified(float("nan"), hist, metric_name="VRP")
        assert pct is None
        assert any("NaN" in line for line in log)

    def test_exactly_min_history_computes(self):
        hist = pd.Series(list(range(20)))  # n == MIN_HISTORY boundary
        pct, _ = oq.percentile_verified(10, hist, metric_name="VRP")
        assert pct is not None


def _mk_strikes(rows):
    return pd.DataFrame(rows, columns=["strike", "call_put", "iv", "gamma", "delta", "volume"])


def _mk_oi(rows):
    return pd.DataFrame(rows, columns=["strike", "cp", "open_interest", "settle_date"])


class TestAnalyzeGex:
    def test_flip_between_put_and_call_mass(self):
        strikes = _mk_strikes([
            (45000, "P", 0.30, 0.0002, -0.4, 100),
            (45000, "C", 0.30, 0.0002, 0.6, 100),
            (46000, "P", 0.28, 0.0001, -0.2, 50),
            (46000, "C", 0.28, 0.0003, 0.4, 50),
        ])
        oi = _mk_oi([
            (45000, "P", 20000, "2026-07-08"),  # big put OI low  -> negative GEX below
            (45000, "C", 1000, "2026-07-08"),
            (46000, "P", 500, "2026-07-08"),
            (46000, "C", 15000, "2026-07-08"),  # big call OI high -> positive GEX above
        ])
        sec = oq.analyze_gex(strikes, oi, spot=45500.0)
        m = sec["metrics"]
        assert m["flip"] is not None and 45000 < m["flip"] <= 46000
        assert m["total_gex"] != 0
        assert len(m["top_strikes"]) <= 5
        assert "T+1" in " ".join(sec["verification"])  # OI staleness disclosed

    def test_spot_below_flip_is_expansion_zone(self):
        strikes = _mk_strikes([(45000, "P", 0.3, 0.0002, -0.4, 10),
                               (46000, "C", 0.3, 0.0002, 0.4, 10)])
        oi = _mk_oi([(45000, "P", 30000, "2026-07-08"),
                     (46000, "C", 30000, "2026-07-08")])
        sec = oq.analyze_gex(strikes, oi, spot=44000.0)
        assert sec["metrics"]["zone"] == "expansion"

    def test_empty_inputs_yield_data_gap(self):
        sec = oq.analyze_gex(_mk_strikes([]), _mk_oi([]), spot=45000.0)
        assert sec["metrics"]["total_gex"] is None
        assert "DATA GAP" in sec["verdict"]


def _mk_bars(closes, date="2026-07-09"):
    idx = pd.date_range(f"{date} 09:00", periods=len(closes), freq="1min", tz="Asia/Taipei")
    c = pd.Series(closes, index=idx)
    return pd.DataFrame({"bucket": idx, "open": c.values, "high": c.values * 1.0005,
                         "low": c.values * 0.9995, "close": c.values})


class TestAnalyzeIvRv:
    def test_flat_prices_give_zero_rv_positive_vrp(self):
        bars = _mk_bars([45000.0] * 180)
        atm = pd.Series([0.30] * 180)
        hist = pd.DataFrame({"vrp": np.linspace(-0.05, 0.25, 60)})
        sec = oq.analyze_iv_rv(atm, bars, hist)
        m = sec["metrics"]
        assert m["rv"] == pytest.approx(0.0, abs=1e-9)
        assert m["vrp"] == pytest.approx(0.30, abs=1e-6)
        assert m["percentile"] is not None
        assert any("percentile" in v for v in sec["verification"])

    def test_no_adjective_without_history(self):
        bars = _mk_bars([45000, 45100, 44950, 45200] * 45)
        atm = pd.Series([0.30] * 180)
        hist = pd.DataFrame({"vrp": [0.1] * 5})  # n=5 < 20
        sec = oq.analyze_iv_rv(atm, bars, hist)
        assert sec["metrics"]["percentile"] is None
        assert "insufficient-history" in " ".join(sec["verification"])
        for word in ("貴", "便宜", "極端", "罕見"):
            assert word not in sec["verdict"]

    def test_empty_bars_data_gap(self):
        sec = oq.analyze_iv_rv(pd.Series([0.3]), _mk_bars([]), pd.DataFrame({"vrp": []}))
        assert "DATA GAP" in sec["verdict"]


def _mk_metrics(n=180, skew_start=0.05, skew_end=0.05, date="2026-07-09"):
    idx = pd.date_range(f"{date} 09:00", periods=n, freq="1min", tz="Asia/Taipei")
    return pd.DataFrame({
        "time": idx,
        "atm_iv": np.linspace(0.32, 0.30, n),
        "skew_25d": np.linspace(skew_start, skew_end, n),
        "rr_25d": -np.linspace(skew_start, skew_end, n),
        "pcr_volume": np.linspace(0.8, 1.1, n),
        "iv_term_slope": np.full(n, -0.03),
        "underlying_price": np.linspace(45800, 45500, n),
    })


class TestAnalyzeTermSkew:
    def test_deltas_and_percentile(self):
        df = _mk_metrics(skew_start=0.04, skew_end=0.12)
        hist = pd.DataFrame({"skew_delta": np.linspace(-0.02, 0.03, 60)})
        sec = oq.analyze_term_skew(df, hist)
        m = sec["metrics"]
        assert m["skew_delta"] == pytest.approx(0.08, abs=1e-6)
        assert m["skew_delta_pct"] == 100.0  # 0.08 above entire history
        assert m["atm_iv_delta"] == pytest.approx(-0.02, abs=1e-6)

    def test_data_gap_flag(self):
        df = _mk_metrics(n=30)
        df = pd.concat([df.iloc[:10], df.iloc[25:]])  # 15-min hole
        sec = oq.analyze_term_skew(df, pd.DataFrame({"skew_delta": []}))
        assert "DATA GAP" in sec["verdict"]


class TestAnalyzeFlow:
    def test_oi_delta_top_strikes(self):
        oi_now = _mk_oi([(45000, "P", 25000, "2026-07-09"), (45500, "C", 8000, "2026-07-09"),
                         (46000, "C", 12000, "2026-07-09")])
        oi_prev = _mk_oi([(45000, "P", 10000, "2026-07-08"), (45500, "C", 9000, "2026-07-08"),
                          (46000, "C", 5000, "2026-07-08")])
        df = _mk_metrics()
        sec = oq.analyze_flow(df, oi_now, oi_prev)
        m = sec["metrics"]
        builds = dict((k, v) for k, v, cp in m["top_oi_builds"])
        assert builds.get(45000.0) == 15000
        assert m["pcr_mean"] == pytest.approx(0.95, abs=0.01)

    def test_missing_prev_oi_noted(self):
        sec = oq.analyze_flow(_mk_metrics(), _mk_oi([(45000, "P", 100, "2026-07-09")]), _mk_oi([]))
        assert "無前日 OI" in sec["verdict"] or "no prior OI" in sec["verdict"]
