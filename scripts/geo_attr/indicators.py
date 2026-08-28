"""地緣/宏觀指標 → causal z-score（僅用過去值,不含當前點 — 領先性檢驗的因果前提）。

符號約定: 所有指標「值越大 = 壓力越大」。
"""
import pandas as pd


def causal_zscore(s: pd.Series, baseline: int = 250,
                  min_periods: int = 60) -> pd.Series:
    """z_t = (s_t − mean(s[t−baseline, t−1])) / std(同窗)。shift(1) 排除當前點。

    sd=0 且無偏離 → 0.0；sd=0 且有偏離 → ±10 鉗值（靜默期後爆量，觸發下游 z>2 邏輯）。
    歷史不足（NaN sd）→ z 維持 NaN，不干預。
    """
    r = s.rolling(baseline, min_periods=min_periods)
    mu = r.mean().shift(1)
    sd = r.std().shift(1)
    z = (s - mu) / sd
    resid = s - mu
    zero_sd = sd == 0.0
    # sd=0 且 resid=0：真正的零偏離 → z=0.0
    z[zero_sd & (resid == 0)] = 0.0
    # sd=0 且 resid≠0：靜默期後爆量 — 有偏離但無歷史波動，鉗至 ±10 觸發下游 z>2 邏輯
    z[zero_sd & (resid > 0)] = 10.0
    z[zero_sd & (resid < 0)] = -10.0
    # NaN sd（歷史不足）→ z 維持 NaN，不干預
    return z


def gdelt_intensity(count_series: pd.Series, baseline: int = 250,
                    min_periods: int = 60) -> pd.Series:
    """文章量 7 日和 z — 事件聲量爆量。"""
    return causal_zscore(count_series.rolling(7, min_periods=3).sum(),
                         baseline, min_periods)


def gdelt_tone_deterioration(tone_series: pd.Series, baseline: int = 250,
                             min_periods: int = 60) -> pd.Series:
    """(−tone) 7 日均 z — tone 越負(語調惡化)值越大。"""
    return causal_zscore((-tone_series).rolling(7, min_periods=3).mean(),
                         baseline, min_periods)


def brent_shock(close: pd.Series, baseline: int = 250,
                min_periods: int = 60) -> pd.Series:
    """|5 日報酬| z — 斷供上漲與需求崩跌皆為衝擊。"""
    return causal_zscore(close.pct_change(5).abs(), baseline, min_periods)


def twd_depreciation(usdtwd_close: pd.Series, baseline: int = 250,
                     min_periods: int = 60) -> pd.Series:
    """USDTWD 5 日升幅 z — 台幣貶值(資金撤離)為正。"""
    return causal_zscore(usdtwd_close.pct_change(5), baseline, min_periods)


def dxy_strength(dxy_close: pd.Series, baseline: int = 250,
                 min_periods: int = 60) -> pd.Series:
    """DXY 5 日升幅 z — 美元避險走強為正。"""
    return causal_zscore(dxy_close.pct_change(5), baseline, min_periods)


def foreign_sell_accel(fnet_daily: pd.Series, baseline: int = 250,
                       min_periods: int = 60) -> pd.Series:
    """(−外資淨買金額) 5 日和 z — 賣超加速為正。"""
    return causal_zscore((-fnet_daily).rolling(5, min_periods=3).sum(),
                         baseline, min_periods)


def yield_surge(yield_close: pd.Series, baseline: int = 250,
                min_periods: int = 60) -> pd.Series:
    """美債殖利率 5 日變動(百分點) z — 急升(升息/通膨壓力)為正。用 diff 非 pct_change(利率本身是 %)。"""
    return causal_zscore(yield_close.diff(5), baseline, min_periods)


def sox_shock(sox_close: pd.Series, baseline: int = 250,
              min_periods: int = 60) -> pd.Series:
    """費半 5 日跌幅 z — 下跌為正壓力(取負報酬)。"""
    return causal_zscore(-sox_close.pct_change(5), baseline, min_periods)


def usvix_spike(vix_close: pd.Series, baseline: int = 250,
                min_periods: int = 60) -> pd.Series:
    """US VIX 5 日變動(點) z — 急升為壓力。"""
    return causal_zscore(vix_close.diff(5), baseline, min_periods)
