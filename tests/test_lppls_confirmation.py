import numpy as np
import pandas as pd

from scripts.lppls.confirmation import (
    score_margin, score_institutional, score_iv, score_ofi, aggregate,
)


def _s(values):
    return pd.Series(values, index=pd.bdate_range("2026-07-01", periods=len(values)))


def test_score_margin_accelerating_leverage():
    fin = _s(list(np.linspace(3000, 3050, 20)) + list(np.linspace(3060, 3300, 10)))
    assert score_margin(fin)["score"] == 1        # 近 5 日增速 z > 1


def test_score_margin_flat_and_short_history():
    assert score_margin(_s([3000.0] * 30))["score"] == 0
    assert score_margin(_s([3000.0] * 5)) is None  # < 10 筆


def test_score_institutional_buy_then_sell():
    fnet = _s([1e9] * 17 + [-2e9, -1e9, -1e9])    # 20日累計買超但近3日轉賣
    assert score_institutional(fnet)["score"] == 1
    steady = _s([1e9] * 20)
    assert score_institutional(steady)["score"] == 0


def test_score_iv_inverted_term_or_low_vrp():
    vrp = _s([5.0] * 30)
    assert score_iv(term_slope_latest=-0.5, vrp_series=vrp)["score"] == 1
    low_vrp = _s([5.0] * 29 + [-3.0])
    assert score_iv(term_slope_latest=0.5, vrp_series=low_vrp)["score"] == 1
    assert score_iv(term_slope_latest=0.5, vrp_series=vrp)["score"] == 0


def test_score_ofi_price_up_flow_fading():
    fading = _s([0.5, 0.4, 0.3, 0.1, -0.1])
    assert score_ofi(fading, index_ret5=0.03)["score"] == 1
    assert score_ofi(fading, index_ret5=-0.02)["score"] == 0
    rising = _s([0.1, 0.2, 0.3, 0.4, 0.5])
    assert score_ofi(rising, index_ret5=0.03)["score"] == 0


def test_aggregate_labels():
    full = {"margin": {"score": 1}, "inst": {"score": 1},
            "iv": {"score": 1}, "ofi": {"score": 1}}
    assert aggregate(full)["label"] == "強警戒"
    mid = {"margin": {"score": 1}, "inst": {"score": 1},
           "iv": {"score": 0}, "ofi": {"score": 0}}
    assert aggregate(mid)["label"] == "中性"
    weak = {"margin": {"score": 0}, "inst": None,
            "iv": {"score": 0}, "ofi": {"score": 1}}
    agg = aggregate(weak)
    assert agg["label"] == "降級"
    assert agg["n_available"] == 3
