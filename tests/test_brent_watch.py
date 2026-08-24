"""brent_watch 純函式測試 — 分區/跨線/訊息 (2026-08-24 plan)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import brent_watch as bw  # noqa: E402


def test_classify_zone_bands():
    assert bw.classify_zone(80.0) == "easing"      # <85 緩和帶
    assert bw.classify_zone(85.0) == "neutral"     # 邊界屬中性
    assert bw.classify_zone(92.8) == "neutral"
    assert bw.classify_zone(100.0) == "neutral"
    assert bw.classify_zone(100.1) == "escalation"  # >100 升溫帶


def test_detect_cross_first_run_no_event():
    # 首次執行無 state → 無跨線事件
    assert bw.detect_cross(None, 92.8) is None


def test_detect_cross_down_through_85():
    assert bw.detect_cross(86.2, 84.5) == "cross_below_85"


def test_detect_cross_up_through_100():
    assert bw.detect_cross(99.0, 101.2) == "cross_above_100"


def test_detect_cross_within_band_none():
    assert bw.detect_cross(90.0, 95.0) is None
    assert bw.detect_cross(84.0, 84.9) is None   # 帶內移動不觸發
    assert bw.detect_cross(101.0, 105.0) is None


def test_build_msg_contains_gates_and_price():
    msg = bw.build_msg(price=84.5, chg1d=-1.2, chg5d=-4.0, zone="easing",
                       cross="cross_below_85", corr={"2603": 0.22, "2610": -0.27})
    assert "84.5" in msg
    assert "🚨" in msg                      # 跨線事件標記
    assert "華航" in msg and "2603" in msg  # 兩腿 gate 含義都要在
    assert "\\n" not in msg                 # 禁 literal \n (discord 轉發教訓)


def test_build_msg_neutral_no_alarm():
    msg = bw.build_msg(price=92.8, chg1d=0.5, chg5d=1.0, zone="neutral",
                       cross=None, corr={})
    assert "🚨" not in msg
    assert "92.8" in msg
