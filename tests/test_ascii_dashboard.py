"""ascii_dashboard 純函式測試 — 對沖牆渲染/比率"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ascii_dashboard as ad  # noqa: E402


def test_hbar_scales_to_width():
    assert ad.hbar(100, 100, 10) == "█" * 10
    assert ad.hbar(50, 100, 10) == "█" * 5
    assert ad.hbar(0, 100, 10) == ""
    assert ad.hbar(1, 100, 10) == "▏"     # 非零最少一格 (細條)


def test_wall_rows_marks_walls_and_spot():
    oi = {46100: {"P": 30000, "C": 5000},
          46300: {"P": 10000, "C": 8000},
          46500: {"P": 2000, "C": 40000}}
    rows = ad.wall_rows(oi, spot=46331.0, width=10)
    txt = "\n".join(rows)
    assert "46500" in txt and "CW" in txt          # call wall 標記
    assert "PW" in txt                             # put wall 標記
    assert sum("◀" in r for r in rows) == 1        # 現價箭頭僅一列 (最近履約價)
    # 現價箭頭應在 46300 列 (距 46331 最近)
    assert "◀" in [r for r in rows if "46300" in r][0]


def test_wall_rows_tags_zero_gamma():
    oi = {46100: {"P": 300, "C": 100}, 46300: {"P": 100, "C": 200},
          46500: {"P": 50, "C": 300}}
    rows = ad.wall_rows(oi, spot=46331.0, width=8, zg=46317.8)
    # ZG 標在最接近 flip 的履約價列 (46300)
    assert any("ZG" in r and "46300" in r for r in rows)
    assert not any("ZG" in r for r in ad.wall_rows(oi, spot=46331.0, width=8))


def test_pc_ratio():
    oi = {46100: {"P": 300, "C": 100}, 46500: {"P": 100, "C": 300}}
    assert abs(ad.pc_ratio(oi) - 100.0) < 1e-9
