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


def test_render_cm30_line_with_percentile():
    msg = mv.render("2026-08-27", fin_now=546937698, fin_5d_chg=0, vix=25.8,
                    vix_5d_chg=None, fin_up=[], fin_down=[], short_up=[],
                    cm30={"vix_30d": 26.2, "rv_21d": 26.8, "vrp_30d": -0.55,
                          "vrp_pct": 35.0, "n": 53})
    assert "VIX30(常數期限) 26.2" in msg and "RV21 26.8" in msg
    assert "VRP30 -0.6" in msg and "pct 35" in msg   # -0.55 → -0.6 (round-half-even 顯示)


def test_render_cm30_insufficient_history_no_pct():
    msg = mv.render("2026-08-27", fin_now=1e8, fin_5d_chg=0, vix=None,
                    vix_5d_chg=None, fin_up=[], fin_down=[], short_up=[],
                    cm30={"vix_30d": 26.2, "rv_21d": 26.8, "vrp_30d": -0.55,
                          "vrp_pct": None, "n": 12})
    assert "歷史<20日不予分位" in msg


def test_render_weekly_inversion_alarm():
    base = dict(fin_now=1e8, fin_5d_chg=0, vix=None, vix_5d_chg=None,
                fin_up=[], fin_down=[], short_up=[])
    hot = mv.render("2026-07-29", **base,
                    cm30={"vix_30d": 31.2, "rv_21d": None, "vrp_30d": None,
                          "vix_w": 39.5, "wm_spread": 8.2, "vrp_pct": None, "n": 5})
    assert "🚨 倒掛 +8.2" in hot
    calm = mv.render("2026-08-27", **base,
                     cm30={"vix_30d": 23.4, "rv_21d": None, "vrp_30d": None,
                           "vix_w": 22.9, "wm_spread": -0.6, "vrp_pct": None, "n": 5})
    assert "正價差 -0.6" in calm and "🚨" not in calm


# ══════════════════════════════════════════════════════════════════════════════
# 週選行必須永遠出現 — 起源: 2026-09-16 查出 product_code='TX2' 寫死
#
# 舊碼 `if cm30 and cm30.get("vix_w") is not None:` 把整行包住, NULL 時整行消失。
# 68 個交易日只有 19 日有 vix_w, 但讀日報的人看不出「今天少了一行」——
# 缺值必須看得見才會有人去修, 這正是它能壞兩個多月的原因之一。
#
# 同時把選腿 (root + DTE) 印出來: 新口徑每週換腿, 不標的話讀者無從判斷這個
# IV 是 D1 還是 D13 —— 而 7/29 那個 +8.2 的「實證錨點」其實是 DTE=14。
# ══════════════════════════════════════════════════════════════════════════════
_BASE = dict(fin_now=1e8, fin_5d_chg=0, vix=None, vix_5d_chg=None,
             fin_up=[], fin_down=[], short_up=[])


def test_weekly_line_survives_null_vix_w():
    """2026-09-11 實況: 只有 DTE=0 結算腿 → vix_w NULL, 但這行不可以消失。"""
    msg = mv.render("2026-09-11", **_BASE,
                    cm30={"vix_30d": 26.7, "rv_21d": None, "vrp_30d": None,
                          "vix_w": None, "wm_spread": None, "vrp_pct": None, "n": 5})
    assert "週選IV" in msg, "NULL 時整行消失 — 正是壞了兩個月沒人發現的原因"
    assert "n/a" in msg
    assert "🚨" not in msg          # 不知道 ≠ 沒事, 但也不可以報警


def test_weekly_line_shows_root_and_dte():
    """2026-09-16 實況: TXX DTE=2, wm +1.40 → 微倒掛且標明選了哪條腿。"""
    msg = mv.render("2026-09-16", **_BASE,
                    cm30={"vix_30d": 27.69, "rv_21d": None, "vrp_30d": None,
                          "vix_w": 29.09, "wm_spread": 1.40, "vrp_pct": None, "n": 5,
                          "vix_w_root": "TXX", "vix_w_dte": 2})
    assert "週選IV(TXX D2) 29.1" in msg
    assert "⚠️ 微倒掛 +1.4" in msg


def test_weekly_line_without_audit_columns_still_renders():
    """審計欄位缺席 (舊資料列) 時退回不帶 root 的標示, 不得拋例外。"""
    msg = mv.render("2026-07-29", **_BASE,
                    cm30={"vix_30d": 31.2, "rv_21d": None, "vrp_30d": None,
                          "vix_w": 39.5, "wm_spread": 8.2, "vrp_pct": None, "n": 5})
    assert "週選IV" in msg and "39.5" in msg


def test_weekly_line_when_cm30_missing_entirely():
    """vix_daily 完全沒有可用列 → 仍要印出一行 n/a, 而不是靜靜少一行。"""
    msg = mv.render("2026-09-14", **_BASE, cm30=None)
    assert "週選IV" in msg and "n/a" in msg


# ══════════════════════════════════════════════════════════════════════════════
# collector stderr 必須轉出到 routine log — 起源: 2026-09-17 live 驗收
#
# vix_daily.py 修好了「查無候選時完全靜默」(D3), 但 run_collectors 用
# capture_output=True 且只在拋例外時 print —— 成功路徑下 collector 的
# WARNING/ERROR 全部被吃掉。實測: grep 無可用週選腿 ~/Library/Logs/margin-vix.log
# → 0, docker logs 也看不到 (docker exec 的輸出不進容器 log)。
# 修了「collector 不出聲」卻沒接「出了聲沒人聽」—— 與原始 TX2 事故同族。
# ══════════════════════════════════════════════════════════════════════════════
import subprocess  # noqa: E402


def test_run_collectors_forwards_stderr_on_success(monkeypatch, capsys):
    """成功路徑: collector 的 WARNING 必須轉出, 不得因 returncode=0 而消音。"""
    class R:
        stderr = "[WARNING] 2026-09-15: 無可用週選腿 (DTE>=1) — vix_w=NULL\n"
    monkeypatch.setattr(mv.subprocess, "run", lambda *a, **k: R())
    mv.run_collectors("2026-09-17")
    assert "無可用週選腿" in capsys.readouterr().err


def test_run_collectors_surfaces_stderr_on_failure(monkeypatch, capsys):
    """失敗路徑: 除了一行 [warn], 還要把 collector 的 traceback 帶出來。

    只印 CalledProcessError 的 repr 等於只知道 exit code —— debug 不動。
    """
    def boom(cmd, *a, **k):
        raise subprocess.CalledProcessError(1, cmd, stderr="Traceback: KeyError 'd'\n")
    monkeypatch.setattr(mv.subprocess, "run", boom)
    mv.run_collectors("2026-09-17")
    err = capsys.readouterr().err
    assert "[warn]" in err
    assert "KeyError 'd'" in err
