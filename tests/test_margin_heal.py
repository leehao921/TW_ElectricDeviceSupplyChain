"""margin_morning_heal 純函式測試 — 前一交易日判定"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import margin_morning_heal as mh  # noqa: E402


def test_prev_trading_day_normal_weekday():
    # 週四 → 週三
    assert mh.prev_trading_day(date(2026, 9, 3), set()) == date(2026, 9, 2)


def test_prev_trading_day_monday_goes_to_friday():
    assert mh.prev_trading_day(date(2026, 8, 31), set()) == date(2026, 8, 28)


def test_prev_trading_day_skips_holiday():
    # 週三為假日 → 週四的前一交易日 = 週二
    hol = {"2026-09-02"}
    assert mh.prev_trading_day(date(2026, 9, 3), hol) == date(2026, 9, 1)


def test_needs_heal_threshold():
    assert mh.needs_heal(0) is True
    assert mh.needs_heal(418) is True      # 短收 (TWSE-only ~1300 之下)
    assert mh.needs_heal(2218) is False
