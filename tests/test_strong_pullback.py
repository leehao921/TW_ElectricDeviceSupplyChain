"""strong_pullback 純函式測試 — Martin 強勢整理回測 (plan 2026-10-16)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import strong_pullback as sp  # noqa: E402


def _ohlc(closes, highs=None, lows=None, opens=None, vols=None, start="2025-01-06"):
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame({
        "Open": opens if opens is not None else closes,
        "High": highs if highs is not None else closes * 1.01,
        "Low": lows if lows is not None else closes * 0.99,
        "Close": closes,
        "Volume": vols if vols is not None else np.full(n, 1_000_000.0),
    }, index=idx)


# --------------------------------------------------------------------------- #
# step 1a — 強勢排名
# --------------------------------------------------------------------------- #
def test_momentum_pass_needs_30pct_and_top_quartile():
    idx = pd.bdate_range("2025-01-06", periods=130)
    # 8 檔: A 漲 50% (top), B 漲 35% (第二), 其餘 0~10%
    data = {}
    for sym, total in [("A", 0.5), ("B", 0.35), ("C", 0.1), ("D", 0.05),
                       ("E", 0.0), ("F", 0.02), ("G", 0.04), ("H", 0.08)]:
        data[sym] = np.linspace(100, 100 * (1 + total), 130)
    close = pd.DataFrame(data, index=idx)
    out = sp.momentum_pass(close, min_ret=30.0, top_frac=0.25)
    last = out.iloc[-1]
    assert bool(last["A"]) and bool(last["B"])
    assert not bool(last["C"])


def test_momentum_30pct_but_not_top_quartile_fails():
    idx = pd.bdate_range("2025-01-06", periods=130)
    # 全部都漲 40%+ → 只有前 25% 過
    close = pd.DataFrame({s: np.linspace(100, 100 * (1.4 + i * 0.01), 130)
                          for i, s in enumerate("ABCDEFGH")}, index=idx)
    last = sp.momentum_pass(close, min_ret=30.0, top_frac=0.25).iloc[-1]
    assert int(last.sum()) == 2          # 8 × 25% = 2 檔


# --------------------------------------------------------------------------- #
# 指標
# --------------------------------------------------------------------------- #
def test_anchored_vwap_from_anchor():
    df = _ohlc([10, 10, 20, 30], highs=[10, 10, 20, 30], lows=[10, 10, 20, 30],
               vols=[1, 1, 1, 3])
    av = sp.anchored_vwap(df, anchor_pos=2)
    assert np.isnan(av.iloc[1])
    assert av.iloc[2] == pytest.approx(20.0)
    assert av.iloc[3] == pytest.approx((20 * 1 + 30 * 3) / 4)


def test_squeeze_flag_matches_bb_definition():
    # 前 70 根大波動, 最後 25 根幾乎不動 → 擠壓; 第 40 根 60 窗未滿 30 根 → 不判
    rng = np.random.default_rng(0)
    noisy = 100 + np.cumsum(rng.normal(0, 3, 70))
    calm = np.full(25, noisy[-1]) + rng.normal(0, 0.05, 25)
    df = _ohlc(np.concatenate([noisy, calm]))
    ind = sp.add_indicators(df)
    assert bool(ind["squeezed"].iloc[-1])
    assert not bool(ind["squeezed"].iloc[40])


# --------------------------------------------------------------------------- #
# step 1b — 整理轉強
# --------------------------------------------------------------------------- #
def _uptrend_then_base(n_up=60, n_base=30, lows_rising=True):
    up = np.linspace(50, 100, n_up)
    base = 100 + 2 * np.sin(np.linspace(0, 6 * np.pi, n_base)) * np.linspace(1, 0.3, n_base)
    closes = np.concatenate([up, base])
    lows = closes * 0.99
    if lows_rising:
        lows[-10:] = np.maximum(lows[-10:], lows[-30:-10].min() + 1)
    else:
        lows[-3] = lows[-30:-10].min() - 5
    return _ohlc(closes, lows=lows)


def test_higher_low_detected():
    ind = sp.add_indicators(_uptrend_then_base(lows_rising=True))
    assert bool(sp.higher_low(ind))


def test_lower_low_rejected():
    ind = sp.add_indicators(_uptrend_then_base(lows_rising=False))
    assert not bool(sp.higher_low(ind))


def test_downtrend_below_falling_ema_rejected():
    closes = np.linspace(100, 60, 90)
    ind = sp.add_indicators(_ohlc(closes))
    st = sp.consolidation_state(ind)
    assert st["downtrend"] is True
    assert st["pass"] is False


# --------------------------------------------------------------------------- #
# step 2 — 支撐位
# --------------------------------------------------------------------------- #
def test_swing_high_needs_k_bars_each_side():
    closes = [1, 2, 3, 4, 5, 9, 5, 4, 3, 2, 1, 1, 1]
    df = _ohlc(closes, highs=closes)
    sh = sp.swing_highs(df, k=5)
    assert list(sh.index) == [df.index[5]]
    assert sh.iloc[0] == 9


def test_unfilled_gap_kept_filled_gap_dropped():
    # bar1→bar2 跳空 (high1=11 < low2=13), 之後 low 從未 ≤ 11 → 未補
    # bar4→bar5 跳空 (high4=16 < low5=18), bar7 low=15 補掉
    highs = [10, 11, 14, 15, 16, 19, 20, 19]
    lows = [9, 10, 13, 14, 15, 18, 19, 15]
    df = _ohlc([h - 0.5 for h in highs], highs=highs, lows=lows)
    gaps = sp.unfilled_gaps(df)
    assert gaps == [11]


def test_confluence_zone_needs_three_levels_within_band():
    levels = {"ema21": 100.0, "avwap": 100.8, "prior_high": 101.2, "ema50": 90.0}
    z = sp.confluence_zone(levels, close=104.0, band_pct=1.5, min_members=3)
    assert z is not None
    assert set(z["members"]) == {"ema21", "avwap", "prior_high"}
    assert z["low"] == pytest.approx(100.0) and z["high"] == pytest.approx(101.2)


def test_confluence_zone_none_when_only_two():
    levels = {"ema21": 100.0, "avwap": 100.8, "ema50": 90.0}
    assert sp.confluence_zone(levels, close=104.0, band_pct=1.5, min_members=3) is None


def test_confluence_zone_ignores_levels_above_close():
    levels = {"ema21": 100.0, "avwap": 100.8, "prior_high": 101.2}
    assert sp.confluence_zone(levels, close=100.5, band_pct=1.5, min_members=3) is None


# --------------------------------------------------------------------------- #
# step 2 — 第一次回測
# --------------------------------------------------------------------------- #
def test_first_retest_true_when_no_prior_touch():
    # 收在 zone 下 → 站上 → 遠離 → 今日回測
    closes = [95, 96, 103, 106, 108, 107, 102]
    lows = [94, 95, 102.5, 105, 107, 106, 100.5]
    df = _ohlc(closes, lows=lows)
    assert sp.is_first_retest(df, zone_low=100.0, zone_high=101.0)


def test_second_retest_rejected():
    closes = [95, 103, 106, 102, 106, 108, 102]
    lows = [94, 102.5, 105, 100.8, 105, 107, 100.5]   # bar3 已回測過
    df = _ohlc(closes, lows=lows)
    assert not sp.is_first_retest(df, zone_low=100.0, zone_high=101.0)


def test_retest_requires_close_holding_zone():
    closes = [95, 103, 106, 108, 98]                  # 今日收破 zone_low
    lows = [94, 102.5, 105, 107, 97]
    df = _ohlc(closes, lows=lows)
    assert not sp.is_first_retest(df, zone_low=100.0, zone_high=101.0)


# --------------------------------------------------------------------------- #
# step 3/4 — 交易模擬
# --------------------------------------------------------------------------- #
def _trade_frame(rows):
    df = pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "ema9"])
    df.index = pd.bdate_range("2025-03-03", periods=len(df))
    return df


def test_no_entry_when_next_bar_fails_to_break_high():
    df = _trade_frame([[100, 101, 99, 100, 99], [100, 100.5, 99.5, 100, 99]])
    assert sp.simulate_trade(df, signal_pos=0) is None


def test_stopped_out_is_minus_one_r_before_cost():
    df = _trade_frame([
        [100, 101, 99, 100, 99],        # T: high 101, low 99 → stop 99
        [100.5, 102, 100.5, 101.5, 100],  # T+1 突破 101 → entry 101, R=2
        [101, 101, 98, 98.5, 100],      # 跌破 99 → -1R
    ])
    t = sp.simulate_trade(df, signal_pos=0, cost_pct=0.0)
    assert t["entry"] == 101 and t["stop"] == 99
    assert t["r_gross"] == pytest.approx(-1.0)


def test_gap_below_stop_exits_at_open():
    df = _trade_frame([
        [100, 101, 99, 100, 99],
        [100.5, 102, 100.5, 101.5, 100],
        [97, 98, 96, 97, 100],          # 開盤 97 < stop 99 → 以 97 出, -2R
    ])
    t = sp.simulate_trade(df, signal_pos=0, cost_pct=0.0)
    assert t["r_gross"] == pytest.approx(-2.0)


def test_half_at_3r_rest_on_ema9_break():
    df = _trade_frame([
        [100, 101, 99, 100, 99],
        [100.5, 102, 100.5, 101.5, 100],   # entry 101, R=2 → 3R=107
        [102, 108, 102, 107.5, 103],       # 觸 3R 出一半 @107 (+3R)
        [107, 110, 106, 109, 105],
        [108, 108, 104, 104.5, 106],       # 收 104.5 < ema9 106 → 出 104.5 (+1.75R)
    ])
    t = sp.simulate_trade(df, signal_pos=0, cost_pct=0.0)
    assert t["r_gross"] == pytest.approx(0.5 * 3 + 0.5 * 1.75)
    assert t["exit_reason"] == "ema9"


def test_cost_converted_to_r():
    df = _trade_frame([
        [100, 101, 99, 100, 99],
        [100.5, 102, 100.5, 101.5, 100],
        [101, 101, 98, 98.5, 100],
    ])
    t = sp.simulate_trade(df, signal_pos=0, cost_pct=0.585)
    # cost_R = 0.585% × 101 / 2
    assert t["r_net"] == pytest.approx(-1.0 - 0.00585 * 101 / 2)


def test_trade_stats_expectancy():
    trades = pd.DataFrame({"r_net": [3.0, -1.0, -1.0, 1.0]})
    st = sp.trade_stats(trades)
    assert st["n"] == 4
    assert st["win_rate"] == pytest.approx(0.5)
    assert st["mean_r"] == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# 觀察名單有效期 — step1 通過後等回測
# --------------------------------------------------------------------------- #
def test_setup_active_persists_for_window():
    s1 = pd.Series([False, True, False, False, False, False, False],
                   index=pd.bdate_range("2025-03-03", periods=7))
    act = sp.setup_active(s1, window=3)
    assert act.tolist() == [False, True, True, True, False, False, False]


def test_setup_active_window_one_is_identity():
    s1 = pd.Series([False, True, False], index=pd.bdate_range("2025-03-03", periods=3))
    assert sp.setup_active(s1, window=1).tolist() == [False, True, False]


# --------------------------------------------------------------------------- #
# v2 — 分鐘圖觸發 (plan 2026-10-16 v2)
# --------------------------------------------------------------------------- #
def test_is_untested_since_cross():
    hist = _ohlc([95, 96, 103, 106, 108], lows=[94, 95, 102.5, 105, 107])
    assert sp.is_untested(hist, zone_low=100.0, zone_high=101.0)
    hist2 = _ohlc([95, 103, 106, 102, 106], lows=[94, 102.5, 105, 100.8, 105])
    assert not sp.is_untested(hist2, zone_low=100.0, zone_high=101.0)


def _bars(rows, day="2026-10-15"):
    """rows: (HH:MM 結束標籤, open, high, low, close)."""
    idx = pd.to_datetime([f"{day} {r[0]}" for r in rows])
    return pd.DataFrame([r[1:] for r in rows], index=idx,
                        columns=["Open", "High", "Low", "Close"])


def test_trigger_after_dip_into_zone_then_break_prev_high():
    b = _bars([("09:05", 104, 104.5, 103, 103.2),
               ("09:10", 103.2, 103.4, 100.6, 100.9),   # 下探入 zone (≤101.5)
               ("09:15", 100.9, 101.2, 100.4, 101.0),   # 回升, 高 101.2
               ("09:20", 101.0, 102.0, 100.9, 101.8)])  # 破前K高 101.2 → 進場
    t = sp.intraday_trigger(b, zone_low=100.0, zone_high=101.0)
    assert t["entry"] == pytest.approx(101.2)
    assert t["stop"] == pytest.approx(100.4)            # 觸區後至前K的最低
    assert t["entry_ts"] == b.index[3]


def test_no_trigger_without_touching_zone():
    b = _bars([("09:05", 104, 104.5, 103, 103.2), ("09:10", 103.2, 105, 103.1, 104.8)])
    assert sp.intraday_trigger(b, zone_low=100.0, zone_high=101.0) is None


def test_trigger_invalid_after_slicing_through_support():
    b = _bars([("09:05", 101, 101.2, 97.5, 97.8),         # 跌破 zone_low 2% 以上
               ("09:10", 97.8, 99.0, 97.6, 98.8),
               ("09:15", 98.8, 100.5, 98.7, 100.2)])
    assert sp.intraday_trigger(b, zone_low=100.0, zone_high=101.0) is None


def test_resample_to_5min_uses_end_labels():
    idx = pd.date_range("2026-10-15 09:01", periods=10, freq="1min")
    one = pd.DataFrame({"Open": range(10), "High": range(10), "Low": range(10),
                        "Close": range(10)}, index=idx, dtype=float)
    five = sp.resample_bars(one, 5)
    assert list(five.index.strftime("%H:%M")) == ["09:05", "09:10"]
    assert five.iloc[0].tolist() == [0, 4, 0, 4]


def test_intraday_trade_stopped_same_day():
    day = pd.DataFrame(
        [[100, 101, 99, 100, 99], [100.5, 102, 98, 99, 100]],
        columns=["Open", "High", "Low", "Close", "ema9"],
        index=pd.bdate_range("2026-10-14", periods=2))
    bars = _bars([("09:20", 100, 101.0, 100.2, 100.8), ("09:25", 100.8, 100.9, 99.0, 99.2)])
    t = sp.simulate_intraday_trade(day, pos=1, bars_after_entry=bars, entry=100.5, stop=99.5,
                                   cost_pct=0.0)
    assert t["r_gross"] == pytest.approx(-1.0)
    assert t["exit_reason"] == "stop"


def test_intraday_trade_carries_to_daily_management():
    day = pd.DataFrame(
        [[100, 101, 99, 100, 99],
         [100.5, 102, 100, 101.8, 100],       # T: 進場 101, 停損 100 (R=1)
         [102, 104.5, 101.5, 104, 101],       # T+1 觸 3R=104 出一半
         [104, 104.2, 102, 102.5, 103]],      # 收 102.5 < ema9 103 → 出 (+1.5R)
        columns=["Open", "High", "Low", "Close", "ema9"],
        index=pd.bdate_range("2026-10-13", periods=4))
    bars = _bars([("09:30", 101, 101.5, 100.6, 101.4)])
    t = sp.simulate_intraday_trade(day, pos=1, bars_after_entry=bars, entry=101.0, stop=100.0,
                                   cost_pct=0.0)
    assert t["r_gross"] == pytest.approx(0.5 * 3 + 0.5 * 1.5)
    assert t["exit_reason"] == "ema9"


def test_kbars_request_payloads():
    cands = pd.DataFrame({"symbol": ["2357", "3406"],
                          "date": pd.to_datetime(["2026-10-15", "2026-10-14"])})
    reqs = sp.kbars_requests(cands)
    assert reqs[0] == '{"symbol": "2357", "start": "2026-10-15", "end": "2026-10-15"}'
    assert len(reqs) == 2


def test_trigger_skips_zero_risk_flat_bar():
    b = _bars([("09:01", 101, 101, 100.5, 100.5),      # 觸區
               ("09:02", 100.5, 100.5, 100.5, 100.5),  # 平盤 K: 高=低=觸區後最低
               ("09:03", 100.5, 100.8, 100.5, 100.7),  # 破前K高 → entry 100.5 = stop → 跳過
               ("09:04", 100.7, 101.2, 100.6, 101.1)]) # 破 100.8 → entry 100.8, stop 100.5
    t = sp.intraday_trigger(b, zone_low=100.0, zone_high=101.0)
    assert t["entry"] == pytest.approx(100.8)
    assert t["stop"] == pytest.approx(100.5)
