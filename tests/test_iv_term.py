"""IV 期限表 (2026-10-07): IV → 與前一到期差 + ±1σ 點數區間,手機 40 字寬內。"""
import sys
from datetime import datetime
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


def test_dip_flagged():
    assert any(ln.startswith("⚠ 10/12 低於前後") for ln in _lines())


def test_front_inversion_flagged():
    L = iv_term_lines([("20261007", 22.0), ("20261012", 20.3), ("20261021", 23.7)],
                      {}, ("TXF", 50000.0), NOW)
    assert any("前端倒掛" in ln for ln in L)


def test_missing_forward_uses_ref_and_fits_mobile():
    L = iv_term_lines(CURVE, {}, ("TXF", 50111.0), NOW)
    assert all(_w(ln) <= 40 for ln in L)


def test_empty_curve_returns_nothing():
    assert iv_term_lines([], {}, ("TXF", 50000.0), NOW) == []
