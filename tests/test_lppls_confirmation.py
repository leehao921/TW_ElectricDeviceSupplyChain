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
    """Fix 1: term_slope 倒掛定義 Near>Far → slope POSITIVE = backwardation = stress."""
    vrp = _s([5.0] * 30)
    # slope > 0 → Near>Far 倒掛 → score 1
    assert score_iv(term_slope_latest=+0.5, vrp_series=vrp)["score"] == 1
    # low vrp regardless of slope (slope < 0 = contango, normal)
    low_vrp = _s([5.0] * 29 + [-3.0])
    assert score_iv(term_slope_latest=-0.5, vrp_series=low_vrp)["score"] == 1
    # slope < 0 (contango/normal) + normal vrp → score 0
    assert score_iv(term_slope_latest=-0.5, vrp_series=vrp)["score"] == 0


def test_score_iv_inverted_dict_fields():
    """inverted flag must reflect the corrected sign convention."""
    vrp = _s([5.0] * 30)
    r = score_iv(term_slope_latest=+0.5, vrp_series=vrp)
    assert r["inverted"] is True
    r2 = score_iv(term_slope_latest=-0.5, vrp_series=vrp)
    assert r2["inverted"] is False


def test_score_iv_skew_steep_triggers():
    """Fix 2: steep skew (> 80th pct) → score 1 even with normal slope + normal vrp."""
    vrp = _s([5.0] * 30)
    # normal contango slope, normal vrp, but skew has last value well above 80th pct
    skew = _s([2.0] * 29 + [5.0])   # 29 values at 2.0, last at 5.0 → clearly > 80th pct
    r = score_iv(term_slope_latest=-0.5, vrp_series=vrp, skew_series=skew)
    assert r["score"] == 1
    assert r["skew_steep"] is True


def test_score_iv_skew_in_returned_dict():
    """skew_steep key must always appear in result dict when called."""
    vrp = _s([5.0] * 30)
    skew = _s([2.0] * 30)  # flat skew, not steep
    r = score_iv(term_slope_latest=-0.5, vrp_series=vrp, skew_series=skew)
    assert "skew_steep" in r
    assert r["skew_steep"] is False
    assert r["score"] == 0


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


def test_aggregate_all_none_is_data_insufficient():
    """Fix 3: all layers None → 資料不足 (distinct label), n_available=0."""
    agg = aggregate({"margin": None, "inst": None, "iv": None, "ofi": None})
    assert agg["label"] == "資料不足"
    assert agg["n_available"] == 0


def test_aggregate_single_layer_full_score_not_强警戒():
    """Fix 3: single layer fires (score=1), three None → n=1, total=1 = n, but n<2 → 中性."""
    agg = aggregate({"margin": {"score": 1}, "inst": None, "iv": None, "ofi": None})
    assert agg["label"] != "強警戒"
    assert agg["label"] == "中性"
