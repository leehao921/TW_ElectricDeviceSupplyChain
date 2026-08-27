import numpy as np
import pandas as pd

from scripts.geo_attr.indicators import (
    causal_zscore, gdelt_intensity, gdelt_tone_deterioration, brent_shock,
    twd_depreciation, foreign_sell_accel,
)


def _s(values, start="2025-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_causal_zscore_excludes_current_point():
    # 前 99 點 ~N(0,1) 固定 seed,最後一點 = 100 → z 巨大;
    # 若誤把當前點納入 baseline,std 會被自身撐大,z 明顯縮水
    rng = np.random.default_rng(0)
    s = _s(list(rng.normal(0, 1, 99)) + [100.0])
    z = causal_zscore(s, baseline=250, min_periods=60)
    assert z.iloc[-1] > 30


def test_causal_zscore_insufficient_history_nan():
    s = _s(list(np.arange(50.0)))
    z = causal_zscore(s, baseline=250, min_periods=60)
    assert z.isna().all()


def test_gdelt_intensity_spike():
    counts = _s([10.0] * 90 + [10, 10, 80, 90, 100, 120, 150, 200, 250, 300])
    z = gdelt_intensity(counts, baseline=60, min_periods=30)
    assert z.iloc[-1] > 2.0


def test_tone_deterioration_more_negative_is_higher():
    tone = _s([-1.0] * 90 + [-8.0] * 10)   # tone 驟降(更負)
    z = gdelt_tone_deterioration(tone, baseline=60, min_periods=30)
    assert z.iloc[-1] > 2.0


def test_brent_shock_absolute_both_directions():
    up = _s([70.0] * 95 + [70, 72, 76, 82, 90])      # +28%/5d
    dn = _s([70.0] * 95 + [70, 68, 64, 58, 50])      # -28%/5d
    for series in (up, dn):
        z = brent_shock(series, baseline=60, min_periods=30)
        assert z.iloc[-1] > 2.0


def test_twd_depreciation_sign():
    dep = _s([31.0] * 95 + [31.0, 31.3, 31.7, 32.2, 32.8])   # USDTWD 升=貶值
    z = twd_depreciation(dep, baseline=60, min_periods=30)
    assert z.iloc[-1] > 2.0
    app = _s([31.0] * 95 + [31.0, 30.7, 30.3, 29.8, 29.2])   # 升值 → 不觸發
    z2 = twd_depreciation(app, baseline=60, min_periods=30)
    assert z2.iloc[-1] < 0


def test_foreign_sell_accel_sign():
    sell = _s([1e8] * 95 + [-5e8, -8e8, -9e8, -1.2e9, -1.5e9])  # 轉大幅賣超
    z = foreign_sell_accel(sell, baseline=60, min_periods=30)
    assert z.iloc[-1] > 2.0
    buy = _s([1e8] * 100)
    assert abs(foreign_sell_accel(buy, baseline=60, min_periods=30).iloc[-1]) < 1.0


# --- sd=0 邊界條件: 靜默期後爆量 ---

def test_causal_zscore_flat_then_spike_fires():
    s = _s([5.0] * 100 + [50.0])
    z = causal_zscore(s, baseline=60, min_periods=30)
    assert z.iloc[-1] == 10.0          # 靜默期後爆量必須觸發,不得歸零


def test_causal_zscore_flat_constant_stays_zero():
    s = _s([5.0] * 101)
    z = causal_zscore(s, baseline=60, min_periods=30)
    assert z.iloc[-1] == 0.0


def test_gdelt_intensity_first_event_after_quiet_period():
    counts = _s([2.0] * 100 + [40.0, 45.0, 50.0])   # 死寂後爆量
    z = gdelt_intensity(counts, baseline=60, min_periods=30)
    assert z.iloc[-1] >= 2.0
