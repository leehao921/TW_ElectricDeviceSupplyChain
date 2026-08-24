"""etf_00891_watch 純函式測試 — 回檔帶/乖離 trim 帶/股利規則 (2026-08-24 策略參數化)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import etf_00891_watch as ew  # noqa: E402


def test_classify_band_hold():
    # 距高 -13.9%、乖離 +22% (低於 trim 線) → 持有區
    assert ew.classify_band(drawdown=-13.9, dev=22.2) == "hold"


def test_classify_band_add_tiers():
    assert ew.classify_band(drawdown=-21.0, dev=5.0) == "add1"    # -20% 帶: 股利池
    assert ew.classify_band(drawdown=-31.0, dev=-10.0) == "add2"  # -30% 帶: 加倍
    assert ew.classify_band(drawdown=-36.0, dev=-25.0) == "add3"  # -35% 帶: 黑天鵝質押
    assert ew.classify_band(drawdown=-19.9, dev=0.0) == "hold"    # 邊界外


def test_classify_band_trim_needs_high_dev():
    assert ew.classify_band(drawdown=-2.0, dev=46.0) == "trim"    # 乖離 ≥45% 噴出帶
    assert ew.classify_band(drawdown=0.0, dev=44.9) == "hold"     # 差一點不觸發


def test_dividend_rule():
    assert ew.dividend_rule(price=33.7, ma200=27.6) == "hold_cash"    # 價 > MA200 → 留現金
    assert ew.dividend_rule(price=25.0, ma200=27.6) == "reinvest"     # 價 < MA200 → 再投入


def test_detect_cross_band_change_only():
    assert ew.detect_cross("hold", "add1") == "enter_add1"
    assert ew.detect_cross("add1", "hold") == "exit_add1"
    assert ew.detect_cross("hold", "hold") is None
    assert ew.detect_cross(None, "hold") is None   # 首次無 state


def test_build_msg_contains_key_levels():
    msg = ew.build_msg(price=31.2, ath=39.11, drawdown=-20.2, dev=3.0,
                       band="add1", cross="enter_add1", div_rule="reinvest",
                       ma200=30.3)
    assert "🚨" in msg and "31.2" in msg
    assert "add1" in msg or "股利池" in msg
    assert "\\n" not in msg


def test_build_msg_hold_quiet():
    msg = ew.build_msg(price=33.69, ath=39.11, drawdown=-13.9, dev=22.2,
                       band="hold", cross=None, div_rule="hold_cash", ma200=27.6)
    assert "🚨" not in msg
