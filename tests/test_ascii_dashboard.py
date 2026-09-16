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


# ══════════════════════════════════════════════════════════════════════════════
# 複合 regime 行的 None-safe — 起源: 2026-09-16 08:40 txf-level-map log
#
#   [warn] iv-curve/regime layer failed: unsupported format string passed to
#          NoneType.__format__
#
# compute_composite 只在「W1+W2+M1 三腿的 net gamma 有穿零」時才有 zero-gamma;
# 08:40 當下週選腿還沒被 collector 寫入 (weekly-root 修復 09:04 才補上),
# 只剩兩條月選腿 → 無穿零 → zg=None → f"{None:,.0f}" TypeError。
#
# 例外發生在 IV curve 兩行「已經 append 之後」, 所以曲線活著、只有複合行被靜默
# 吞掉 —— 讀報的人看不出少了一行。這是 fmt_num 已存在卻沒被套用的漏網之魚。
# ══════════════════════════════════════════════════════════════════════════════
class _StubRegime:
    """把 gex_regime_monitor 的五個函式換成可控 stub。"""

    @staticmethod
    def install(monkeypatch, *, comp, raises=False):
        import gex_regime_monitor as g
        monkeypatch.setattr(g, "iv_curve",
                            lambda conn, spot: [("20261021", 26.7), ("20261118", 25.0)])
        monkeypatch.setattr(g, "front_iv_history", lambda conn: [])
        monkeypatch.setattr(g, "z_windows",
                            lambda v, h, **kw: {"w20": {"z": None, "n": 0}})
        # classify_regime 不 stub — 它對 None 回傳 None 正是要一起驗的行為。

        def _comp(conn, spot):
            if raises:
                raise RuntimeError("boom")
            return comp
        monkeypatch.setattr(g, "compute_composite", _comp)


class TestCompositeLineNullSafety:
    def _run(self, monkeypatch, capsys, **kw):
        _StubRegime.install(monkeypatch, **kw)
        cur = _FakeCur((18.5, 19.2, 14.0, 5.2, None, None))
        lines, _ = ad.vol_section_lines(None, cur, 45577.0)
        return "\n".join(lines), capsys.readouterr().err

    def test_none_zero_gamma_still_renders_composite_line(self, monkeypatch, capsys):
        """zg=None 時複合行必須降級成 n/a 而非整行消失。"""
        txt, err = self._run(monkeypatch, capsys,
                             comp={"zg": None, "total_gex": -1.23e10})
        assert "複合(W1+W2+M1)" in txt, "複合行被靜默吞掉 — 正是 9/16 08:40 的症狀"
        assert "ZG n/a" in txt
        # classify_regime 對 None 回 None; 不可把 "None" 直接印進報告
        assert "None" not in txt
        assert "iv-curve/regime layer failed" not in err

    def test_none_total_gex_still_renders_composite_line(self, monkeypatch, capsys):
        txt, err = self._run(monkeypatch, capsys,
                             comp={"zg": 46200.0, "total_gex": None})
        assert "複合(W1+W2+M1)" in txt
        assert "GEX n/a" in txt
        assert "None" not in txt
        assert "iv-curve/regime layer failed" not in err

    def test_both_present_renders_numbers(self, monkeypatch, capsys):
        """spot 45577 < ZG 46200 且 GEX<0 → 真 classify_regime 判 EXPANSION。"""
        txt, _ = self._run(monkeypatch, capsys,
                           comp={"zg": 46200.0, "total_gex": -1.23e10})
        assert "EXPANSION" in txt
        assert "ZG 46,200" in txt and "-123億/1%" in txt

    def test_iv_curve_survives_when_composite_layer_breaks(self, monkeypatch, capsys):
        """真正的例外仍 fail-soft, 但必須印出 traceback 而非只有一行訊息。

        靜默吞例外正是 2026-09-10~15 dashboard crash 四天沒人發現的原因。
        """
        txt, err = self._run(monkeypatch, capsys, comp=None, raises=True)
        assert "IV curve:" in txt          # 前面的行不受牽連
        assert "複合(W1+W2+M1)" not in txt
        assert "Traceback" in err          # 有 traceback 才 debug 得動
        assert "boom" in err
