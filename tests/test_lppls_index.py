import numpy as np
import pandas as pd
import pytest

from scripts.lppls import index_builder
from scripts.lppls.index_builder import (
    CORE, select_components, build_index, validate_vs_taiex,
)


def _closes(n=400, symbols=None, seed=7):
    symbols = symbols or (CORE + ["3034", "3008"])
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-02", periods=n)
    data = {s: 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
            for s in symbols}
    return pd.DataFrame(data, index=dates)


FAKE_CAPS = {s: 1_000_000.0 - i * 10_000 for i, s in enumerate(CORE)}
FAKE_CAPS.update({"3034": 900_000.0, "3008": 800_000.0})


def test_select_components_core_plus_supplement(monkeypatch):
    monkeypatch.setattr(index_builder, "load_market_caps", lambda tickers: dict(FAKE_CAPS))
    closes = _closes()
    comps, weights = select_components(closes, n_supplement=2)
    assert set(CORE).issubset(comps)
    assert "3034" in comps and "3008" in comps
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_select_components_raises_on_missing_core_cap(monkeypatch):
    caps = {k: v for k, v in FAKE_CAPS.items() if k != "2330"}
    monkeypatch.setattr(index_builder, "load_market_caps", lambda tickers: caps)
    with pytest.raises(ValueError, match="2330"):
        select_components(_closes(), n_supplement=2)


def test_select_components_drops_short_history(monkeypatch):
    monkeypatch.setattr(index_builder, "load_market_caps", lambda tickers: dict(FAKE_CAPS))
    closes = _closes()
    closes.iloc[:50, closes.columns.get_loc("3008")] = np.nan  # 350 < 390 天
    comps, _ = select_components(closes, n_supplement=2, min_days=390)
    assert "3008" not in comps


def test_select_components_raises_on_short_core_history(monkeypatch):
    """CORE ticker with insufficient history must raise ValueError naming the ticker."""
    monkeypatch.setattr(index_builder, "load_market_caps", lambda tickers: dict(FAKE_CAPS))
    closes = _closes()
    # Make 2330 (first CORE ticker) have only 350 non-NaN rows (< 390)
    closes.iloc[:50, closes.columns.get_loc("2330")] = np.nan
    with pytest.raises(ValueError, match="2330"):
        select_components(closes, n_supplement=2, min_days=390)


def test_build_index_base_100_and_weighting():
    dates = pd.bdate_range("2025-01-02", periods=3)
    closes = pd.DataFrame({"AAA": [100.0, 110.0, 121.0],
                           "BBB": [200.0, 200.0, 200.0]}, index=dates)
    idx = build_index(closes, {"AAA": 0.6, "BBB": 0.4})
    assert np.isclose(idx.iloc[0], 100.0)
    assert np.isclose(idx.iloc[1], (0.6 * 1.1 + 0.4 * 1.0) * 100)


def test_validate_vs_taiex_perfect_proxy():
    closes = _closes(n=200, symbols=["AAA"])
    idx = build_index(closes, {"AAA": 1.0})
    corr, n = validate_vs_taiex(idx, closes["AAA"] * 3.0)
    assert corr > 0.999
    assert n > 100


def test_build_index_ffill_fills_short_gap():
    """3-day NaN gap within ffill limit=5 → those rows are filled, no missing dates."""
    dates = pd.bdate_range("2025-01-02", periods=10)
    prices_a = [100.0] * 10
    prices_b = [200.0, 200.0, np.nan, np.nan, np.nan, 200.0, 200.0, 200.0, 200.0, 200.0]
    closes = pd.DataFrame({"AAA": prices_a, "BBB": prices_b}, index=dates)
    idx = build_index(closes, {"AAA": 0.5, "BBB": 0.5}, max_ffill=5)
    # All 10 business days must be present (gap filled by ffill)
    assert len(idx) == 10
    assert idx.notna().all()


def test_build_index_ffill_drops_long_gap():
    """8-day NaN gap exceeds ffill limit=5 → those rows are dropped from the index."""
    dates = pd.bdate_range("2025-01-02", periods=15)
    prices_a = [100.0] * 15
    # 8 consecutive NaNs in BBB starting at row 2
    prices_b = [200.0, 200.0] + [np.nan] * 8 + [200.0, 200.0, 200.0, 200.0, 200.0]
    closes = pd.DataFrame({"AAA": prices_a, "BBB": prices_b}, index=dates)
    idx = build_index(closes, {"AAA": 0.5, "BBB": 0.5}, max_ffill=5)
    # Rows 2–9 (8 gap days): ffill covers rows 2–6 (5 days), rows 7–9 are dropped
    assert len(idx) < 15


def test_build_index_raises_when_empty():
    """All components entirely NaN → px.empty → ValueError."""
    dates = pd.bdate_range("2025-01-02", periods=5)
    closes = pd.DataFrame({"AAA": [np.nan] * 5, "BBB": [np.nan] * 5}, index=dates)
    with pytest.raises(ValueError, match="無任何日期"):
        build_index(closes, {"AAA": 0.5, "BBB": 0.5}, max_ffill=5)
