from __future__ import annotations
import sys
from pathlib import Path
import math
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import pb_percentile as pbp  # noqa: E402


def test_compute_bvps_drops_nan_and_nonpositive():
    equity = {2021: float("nan"), 2022: 1000.0, 2023: 1100.0, 2024: -50.0}
    shares = 100.0
    bvps = pbp.compute_bvps(equity, shares)
    assert bvps == {2022: 10.0, 2023: 11.0}   # 2021 NaN dropped, 2024 negative dropped


def test_compute_bvps_empty_when_shares_missing():
    assert pbp.compute_bvps({2023: 1100.0}, 0.0) == {}
    assert pbp.compute_bvps({2023: 1100.0}, None) == {}


def _prices(pairs):
    idx = pd.to_datetime([d for d, _ in pairs])
    return pd.Series([p for _, p in pairs], index=idx)


def test_build_pb_series_asof_annual_join():
    bvps = {2022: 10.0, 2023: 11.0}
    prices = _prices([
        ("2022-06-30", 50.0),   # before 2022 year-end -> no prior FY -> dropped
        ("2023-06-30", 100.0),  # most recent FY-end <= date is 2022-12-31 -> bvps 10 -> pb 10
        ("2024-01-02", 110.0),  # FY 2023-12-31 -> bvps 11 -> pb 10
    ])
    pb = pbp.build_pb_series(prices, bvps)
    assert list(pb.round(4)) == [10.0, 10.0]        # first row dropped
    assert len(pb) == 2


def test_build_pb_series_empty_bvps_returns_empty():
    pb = pbp.build_pb_series(_prices([("2023-06-30", 100.0)]), {})
    assert len(pb) == 0


def test_pct_rank_strict_less_than():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert pbp.pct_rank(s, 4.0) == 60.0     # 3 of 5 strictly < 4
    assert pbp.pct_rank(s, 1.0) == 0.0
    assert pbp.pct_rank(s, 6.0) == 100.0


def test_classify_bands():
    assert pbp.classify(90.0) == "RED"
    assert pbp.classify(85.0) == "RED"      # boundary inclusive
    assert pbp.classify(84.9) == "YELLOW"
    assert pbp.classify(70.0) == "YELLOW"   # boundary inclusive
    assert pbp.classify(69.9) == "GREEN"
    assert pbp.classify(10.0) == "GREEN"


def _linear_prices(start, end, n, price_lo, price_hi):
    idx = pd.date_range(start, end, periods=n)
    vals = [price_lo + (price_hi - price_lo) * i / (n - 1) for i in range(n)]
    return pd.Series(vals, index=idx)


def test_compute_pb_light_happy_red():
    # 300 trading days across 2 fiscal years; price rises so latest P/B is top of range
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    equity = {2022: 1000.0, 2023: 1000.0}   # BVPS 10 both years (shares 100)
    res = pbp.compute_pb_light(prices, equity, shares=100.0, ticker="TEST")
    assert res["light"] == "RED"
    assert res["percentile"] >= 85.0
    assert res["pb_current"] == pytest.approx(30.0, rel=1e-3)   # 300 / 10
    assert res["n_days"] >= 250
    assert res["p85"] > 0 and res["p70"] > 0


def test_compute_pb_light_na_when_no_bvps():
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    res = pbp.compute_pb_light(prices, equity={2023: float("nan")}, shares=100.0, ticker="TEST")
    assert res["light"] == "N/A"
    assert res["percentile"] is None


def test_compute_pb_light_na_when_thin_history():
    prices = _linear_prices("2024-06-03", "2024-12-31", 100, 100.0, 120.0)  # <250 days
    res = pbp.compute_pb_light(prices, equity={2023: 1000.0}, shares=100.0, ticker="TEST")
    assert res["light"] == "N/A"
    assert "thin" in res["source"]


def test_na_result_has_bvps_key_none():
    # shape-stable: consumers B/C can read res["bvps"] on ANY result, incl. N/A
    res = pbp.compute_pb_light(_prices([("2023-06-30", 100.0)]),
                               equity={2023: float("nan")}, shares=100.0, ticker="TEST")
    assert res["light"] == "N/A"
    assert "bvps" in res
    assert res["bvps"] is None


def test_light_from_cutoffs_matches_bands():
    assert pbp.light_from_cutoffs(30.0, p70=20.0, p85=25.0) == "RED"
    assert pbp.light_from_cutoffs(25.0, p70=20.0, p85=25.0) == "RED"    # boundary
    assert pbp.light_from_cutoffs(22.0, p70=20.0, p85=25.0) == "YELLOW"
    assert pbp.light_from_cutoffs(20.0, p70=20.0, p85=25.0) == "YELLOW"  # boundary
    assert pbp.light_from_cutoffs(10.0, p70=20.0, p85=25.0) == "GREEN"


def test_cache_roundtrip(tmp_path):
    p = tmp_path / "cache.json"
    cache = {"2408": {"bvps": 54.99, "p70": 5.0, "p85": 6.5, "asof": "2026-07-09", "n_days": 1214}}
    pbp.save_cache(cache, p)
    loaded = pbp.load_cache(p)
    assert loaded["2408"]["p85"] == 6.5


def test_load_cache_missing_file_returns_empty(tmp_path):
    assert pbp.load_cache(tmp_path / "nope.json") == {}


def _fake_fetcher(prices, equity, shares):
    def _f(ticker):
        return prices, equity, shares
    return _f


def test_pb_light_cache_miss_computes_and_writes(tmp_path):
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    equity = {2022: 1000.0, 2023: 1000.0}
    p = tmp_path / "cache.json"
    res = pbp.pb_light("TEST", cache_path=p, today="2026-07-09",
                       fetcher=_fake_fetcher(prices, equity, 100.0))
    assert res["light"] == "RED"
    assert pbp.load_cache(p)["TEST"]["p85"] > 0        # cutoffs persisted


def test_pb_light_fresh_cache_uses_fast_path(tmp_path):
    p = tmp_path / "cache.json"
    pbp.save_cache({"TEST": {"bvps": 10.0, "p70": 15.0, "p85": 25.0,
                             "asof": "2026-07-08", "n_days": 300}}, p)

    def _boom(ticker):
        raise AssertionError("fetcher must not be called on fresh cache hit")

    res = pbp.pb_light("TEST", latest_close=300.0, cache_path=p,
                       today="2026-07-09", fetcher=_boom)
    assert res["pb_current"] == pytest.approx(30.0)    # 300 / 10
    assert res["light"] == "RED"                        # 30 >= p85 25


def test_pb_light_stale_cache_recomputes(tmp_path):
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    equity = {2022: 1000.0, 2023: 1000.0}
    p = tmp_path / "cache.json"
    pbp.save_cache({"TEST": {"bvps": 10.0, "p70": 15.0, "p85": 25.0,
                             "asof": "2026-06-01", "n_days": 300}}, p)   # >7d old
    res = pbp.pb_light("TEST", cache_path=p, today="2026-07-09",
                       fetcher=_fake_fetcher(prices, equity, 100.0))
    assert res["source"].startswith("yfinance")         # recomputed, not fast path


@pytest.mark.live
def test_live_2408_is_red(tmp_path):
    try:
        res = pbp.pb_light("2408", cache_path=tmp_path / "c.json", today="2026-07-09")
    except Exception as e:
        pytest.skip(f"network/yfinance unavailable: {e}")
    if res["light"] == "N/A":
        pytest.skip(f"yfinance returned no data: {res['source']}")
    assert res["pb_current"] > 5.0             # elevated regime
    assert res["percentile"] >= 85.0           # top of 5y history
    assert res["light"] == "RED"


def test_main_prints_light(capsys, tmp_path, monkeypatch):
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    equity = {2022: 1000.0, 2023: 1000.0}
    monkeypatch.setattr(pbp, "fetch_yf", _fake_fetcher(prices, equity, 100.0))
    rc = pbp.main(["TEST", "--cache", str(tmp_path / "c.json"), "--today", "2026-07-09"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "TEST" in out and "RED" in out
