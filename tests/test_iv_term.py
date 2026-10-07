"""IV 期限表 (2026-10-07): IV → 與前一到期差 + ±1σ 點數區間,手機 40 字寬內。"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from iv_term import iv_term_lines  # noqa: E402

NOW = datetime(2026, 10, 6, 16, 40)          # TPE naive
CURVE = [("20261007", 18.1), ("20261012", 16.3), ("20261014", 18.1),
         ("20261021", 20.9), ("20261118", 22.7)]
FWD = {"20261007": 49817.0, "20261012": 49834.0, "20261014": 49877.0,
       "20261021": 50103.0, "20261118": 50291.0}


def _lines():
    return iv_term_lines(CURVE, FWD, ("TXF", 50111.0), NOW)


def _w(s):
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def test_header_and_one_row_per_expiry():
    L = _lines()
    assert L[0] == "IV 期限 · TXF 50,111"
    assert L[1].split() == ["到期", "天", "IV", "差", "±1σ", "區間"]
    assert [ln.split()[0] for ln in L[2:7]] == ["10/07", "10/12", "10/14", "10/21", "11/18"]


def test_diff_vs_previous_expiry():
    rows = [ln.split() for ln in _lines()[2:7]]
    assert [r[3] for r in rows] == ["—", "-1.8", "+1.8", "+2.8", "+1.8"]


def test_sigma_points_and_range_centred_on_forward():
    # 10/21: 結算 13:30, 距 14.87 天 → 50103 × 0.209 × √(14.87/365) ≈ 2113
    r = _lines()[5].split()
    assert r[1] == "15" and abs(int(r[4]) - 2113) <= 3
    assert r[5] == "48.0-52.2k"


HOL = {date(2026, 10, 9), date(2026, 10, 10)}       # 國慶補假 (五) + 國慶 (六)


def test_trading_sessions_skip_weekend_and_holiday():
    from iv_term import trading_sessions
    # 10/06 16:40 收盤後 → 10/07,10/08,(10/09 補假),10/12 = 3 場
    assert trading_sessions("20261012", NOW, HOL) == 3
    assert trading_sessions("20261007", NOW, HOL) == 1
    # 盤中 (13:30 前) 當天算一場
    assert trading_sessions("20261007", datetime(2026, 10, 7, 9, 0), HOL) == 1


def test_no_false_alarm_from_expiry_eve_and_holiday_weekend():
    """10/06 實例: 10/07 結算前一晚 + 10/12 跨國慶連假 → 交易日口徑下兩警示都不該出現。"""
    L = iv_term_lines(CURVE, FWD, ("TXF", 50111.0), NOW, holidays=HOL)
    assert not any(ln.startswith("⚠") for ln in L), L


def test_genuine_dip_still_flagged():
    curve = [("20261014", 18.0), ("20261021", 15.0), ("20261028", 19.0)]
    L = iv_term_lines(curve, {}, ("TXF", 50000.0), NOW, holidays=set())
    assert any(ln.startswith("⚠ 10/21 低於前後") for ln in L)


def test_genuine_front_inversion_flagged_but_expiring_leg_ignored():
    inv = [("20261014", 22.0), ("20261021", 18.0), ("20261028", 19.0)]
    assert any("前端倒掛 10/14 > 10/21" in ln
               for ln in iv_term_lines(inv, {}, ("TXF", 50000.0), NOW, holidays=set()))
    expiring = [("20261007", 30.0), ("20261014", 18.0), ("20261021", 19.0)]
    assert not any("前端倒掛" in ln
                   for ln in iv_term_lines(expiring, {}, ("TXF", 50000.0), NOW, holidays=set()))


def test_missing_forward_uses_ref_and_fits_mobile():
    L = iv_term_lines(CURVE, {}, ("TXF", 50111.0), NOW)
    assert all(_w(ln) <= 40 for ln in L)


def test_empty_curve_returns_nothing():
    assert iv_term_lines([], {}, ("TXF", 50000.0), NOW) == []
