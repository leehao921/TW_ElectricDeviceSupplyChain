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
