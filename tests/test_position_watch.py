"""position_watch 純函式測試 — 持倉觸發哨兵 (2026-08-27: 觸發器排程化缺口修補)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import position_watch as pw  # noqa: E402


MKT = {"2603": {"close": 232.5, "ma10": 238.7, "ma20": 224.1, "foreign_5d": 10.0},
       "2324": {"close": 39.8, "ma10": 40.1, "ma20": 39.5, "foreign_5d": -2.0},
       "2610": {"close": 21.0, "ma10": 20.8, "ma20": 20.9, "foreign_5d": 9.0}}


def test_ma_break_fires_below():
    t = {"id": "x", "type": "ma_break", "symbol": "2603", "ma": 10, "action": "減碼"}
    assert pw.evaluate(t, MKT) is True          # 232.5 < MA10 238.7 → 觸發
    t20 = {"id": "y", "type": "ma_break", "symbol": "2603", "ma": 20, "action": "全出"}
    assert pw.evaluate(t20, MKT) is False       # 232.5 > MA20 224.1 → 未觸發


def test_price_levels():
    assert pw.evaluate({"type": "price_above", "symbol": "2324", "level": 43.5}, MKT) is False
    assert pw.evaluate({"type": "price_below", "symbol": "2324", "level": 36.6}, MKT) is False
    assert pw.evaluate({"type": "price_below", "symbol": "2324", "level": 40.0}, MKT) is True


def test_foreign_5d_threshold():
    assert pw.evaluate({"type": "foreign_5d_above", "symbol": "2610", "level": 3.0}, MKT) is True
    assert pw.evaluate({"type": "foreign_5d_above", "symbol": "2324", "level": 0.0}, MKT) is False


def test_missing_symbol_returns_none():
    assert pw.evaluate({"type": "ma_break", "symbol": "9999", "ma": 10}, MKT) is None


def test_fire_once_state_dedup():
    state = {}
    trig = {"id": "2603_l2", "type": "ma_break", "symbol": "2603", "ma": 10, "action": "減 1/3"}
    fired1 = pw.should_fire(trig, True, state, as_of="2026-08-27")
    fired2 = pw.should_fire(trig, True, state, as_of="2026-08-28")
    assert fired1 is True and fired2 is False   # 持續為真只發一次
    pw.should_fire(trig, False, state, as_of="2026-08-29")
    assert pw.should_fire(trig, True, state, as_of="2026-09-01") is True  # 條件清除後重 arm
