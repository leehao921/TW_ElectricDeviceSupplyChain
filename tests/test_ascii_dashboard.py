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


# ══════════════════════════════════════════════════════════════════════════════
# None-safe 格式化 — 起源: com.lulala.dashboard 連續 crash 四個交易日 (2026-09-10~15)
#
# vix_daily.vix_w / wm_spread 自 2026-09-09 起因 quote-quality guard 合法為 NULL,
# 而 vol_section_lines 用 f"{None:+.1f}" → TypeError → 08:30 dashboard 整支 exit 1,
# 且 08:40 level map 因共用同一個 try 靜默掉波動率＋法人兩個區塊。
# ══════════════════════════════════════════════════════════════════════════════
import pytest  # noqa: E402


class _FakeCur:
    """最小 cursor stub — 只回一列 vix_daily。"""

    def __init__(self, row):
        self._row = row

    def execute(self, *a, **kw):
        pass

    def fetchone(self):
        return self._row


class TestFmtNum:
    def test_none_renders_na(self):
        assert ad.fmt_num(None) == "n/a"
        assert ad.fmt_num(None, "+.1f") == "n/a"

    def test_number_uses_spec(self):
        assert ad.fmt_num(5.24, "+.1f") == "+5.2"
        assert ad.fmt_num(-1.0, "+.1f") == "-1.0"
        assert ad.fmt_num(18.5) == "18.5"

    def test_zero_is_not_treated_as_missing(self):
        """0.0 是合法讀值, 不可被當成缺值 (falsy 陷阱)。"""
        assert ad.fmt_num(0.0, "+.1f") == "+0.0"


class TestWmLabel:
    def test_inverted_above_threshold(self):
        assert ad.wm_label(2.5) == "倒掛🚨"

    def test_normal_below_threshold(self):
        assert ad.wm_label(1.0) == "正常"
        assert ad.wm_label(-3.0) == "正常"

    def test_none_is_na_not_normal(self):
        """None 必須是 n/a — 舊碼 `wm and wm > 2` 會把缺值誤報成「正常」。"""
        assert ad.wm_label(None) == "n/a"


class TestVolSectionNullSafety:
    def test_null_vix_w_and_wm_does_not_crash(self):
        """真實 fixture: vix_w / wm_spread 為 NULL (9/9 起的實際狀態)。"""
        cur = _FakeCur((18.5, 19.2, 14.0, 5.2, None, None))
        lines, wm = ad.vol_section_lines(None, cur, 45577.0)
        txt = "\n".join(lines)
        assert "n/a" in txt
        assert "18.5" in txt          # 有值的欄位照常顯示
        assert wm is None

    def test_all_null_row_does_not_crash(self):
        cur = _FakeCur(None)          # vix_daily 完全沒資料
        lines, wm = ad.vol_section_lines(None, cur, 45577.0)
        assert lines and "── 波動率 ──" in lines[0]
        assert wm is None

    def test_full_row_renders_values(self):
        cur = _FakeCur((18.5, 19.2, 14.0, 5.2, 22.0, 2.8))
        lines, wm = ad.vol_section_lines(None, cur, 45577.0)
        txt = "\n".join(lines)
        assert "+5.2" in txt and "+2.8" in txt and "倒掛" in txt
        assert wm == 2.8
