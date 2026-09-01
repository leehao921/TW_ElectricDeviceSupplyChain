"""gex_physics_study 純函式測試 — RV/觸牆事件/貫穿事件/sign test"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import gex_physics_study as gp  # noqa: E402


def test_fwd_rv_constant_price_is_zero():
    closes = [100.0] * 30
    assert gp.fwd_rv(closes, i=0, n=15) == 0.0
    assert gp.fwd_rv(closes, i=20, n=15) is None      # 不足 15 bar → None


def test_fwd_rv_scales_with_return_size():
    up1 = [100 * (1.001 ** i) for i in range(20)]
    up2 = [100 * (1.002 ** i) for i in range(20)]
    # 等比路徑報酬固定 → std=0; 改用交錯路徑
    z1 = [100 + (i % 2) * 0.1 for i in range(20)]      # ±0.1 交錯
    z2 = [100 + (i % 2) * 0.2 for i in range(20)]
    r1, r2 = gp.fwd_rv(z1, 0, 15), gp.fwd_rv(z2, 0, 15)
    assert r2 > r1 > 0
    assert gp.fwd_rv(up1, 0, 15) < 1e-6 or gp.fwd_rv(up1, 0, 15) == 0.0


def test_wall_touch_events_from_below_with_decluster():
    wall = 47000.0
    # 前 5 bar 在區外, 第 6 bar high 進入 [wall*0.998, wall)
    highs = [46500.0] * 5 + [46950.0] + [46940.0] * 40 + [46960.0]
    ev = gp.wall_touch_events(highs, wall, side="CW", zone_pct=0.002,
                              lookback=5, decluster_bars=30)
    assert ev[0] == 5
    assert all(e - ev[i] >= 30 for i, e in enumerate(ev[1:]))  # 30 bar 內去重


def test_wall_touch_events_pw_from_above():
    wall = 46000.0
    # PW: 由上方進入 (wall, wall*1.002] 區 — lows 觸及但未跌破
    lows = [46500.0] * 5 + [46050.0] + [46500.0] * 40
    ev = gp.wall_touch_events(lows, wall, side="PW", zone_pct=0.002,
                              lookback=5, decluster_bars=30)
    assert ev == [5]
    # 直接跌破 (low < wall) 不算觸牆事件
    lows2 = [46500.0] * 5 + [45900.0]
    assert gp.wall_touch_events(lows2, wall, side="PW") == []


def test_breakout_events_needs_hold_and_decluster():
    wall = 47000.0
    closes = [46900.0] * 5 + [47010.0, 47020.0, 47030.0] + [47100.0] * 10
    ev = gp.breakout_events(closes, wall, side="CW", hold_bars=3)
    assert ev == [7]                                   # 站穩第 3 根確認
    closes2 = [46900.0] * 5 + [47010.0, 46950.0, 47020.0, 46940.0] * 3
    assert gp.breakout_events(closes2, wall, side="CW", hold_bars=3) == []
    # 來回穿越多次 → decluster_bars 內只記首次
    closes3 = ([46900.0] * 5 + [47010.0] * 3 + [46900.0] * 2 + [47010.0] * 3) \
        + [46900.0] * 2 + [47010.0] * 3
    ev3 = gp.breakout_events(closes3, wall, side="CW", hold_bars=3,
                             decluster_bars=30)
    assert ev3 == [7]


def test_sign_test_p_two_sided():
    # 10 勝 0 負 → p 非常小; 5/5 → p=1
    assert gp.sign_test_p(10, 0) < 0.01
    assert abs(gp.sign_test_p(5, 5) - 1.0) < 1e-9
    assert abs(gp.sign_test_p(0, 0) - 1.0) < 1e-9


def test_skew_stats_right_tail():
    dist = [-10.0] * 40 + [5.0] * 40 + [200.0] * 10    # 肥右尾 (>10% 佔比)
    st = gp.tail_stats(dist)
    assert st["mean"] > st["median"]                   # 右偏
    assert st["p90"] >= 200.0 or st["p90"] > st["median"]
