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
