"""margin_vix_daily 純函式測試"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import margin_vix_daily as mv  # noqa: E402


def test_top_movers_split_and_sign():
    rows = [{"symbol": "2330", "delta_fin": 500, "delta_short": 10},
            {"symbol": "2324", "delta_fin": -300, "delta_short": 80},
            {"symbol": "3037", "delta_fin": 900, "delta_short": None},
            {"symbol": "2408", "delta_fin": 0, "delta_short": -5}]
    up, down = mv.top_movers(rows, "delta_fin", n=3)
    assert [r["symbol"] for r in up] == ["3037", "2330"]   # 只留正值, 降冪
    assert [r["symbol"] for r in down] == ["2324"]          # 只留負值


def test_render_contains_names_and_zones():
    labels = {"2324": {"name": "仁寶"}}
    msg = mv.render("2026-08-26", fin_now=546937698, fin_5d_chg=32.0,
                    vix=19.9, vix_5d_chg=-1.2,
                    fin_up=[{"symbol": "2324", "delta_fin": 1200}],
                    fin_down=[], short_up=[], labels=labels)
    assert "2324 仁寶" in msg and "5,469" in msg   # 仟元→億 = ÷1e5
    assert "低波動" not in msg and "常態" in msg  # 19.9 → 常態帶
    assert "\\n" not in msg
