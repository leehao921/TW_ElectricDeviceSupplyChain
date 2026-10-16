"""sector_breadth 純函式測試 — 產業動能廣度儀表 (plan 2026-10-16)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sector_breadth as sb  # noqa: E402


def _panel(n_days=30):
    idx = pd.bdate_range("2026-01-05", periods=n_days)
    close = pd.DataFrame({s: np.full(n_days, 100.0) for s in ["A", "B", "C", "D"]}, index=idx)
    mom = pd.DataFrame(False, index=idx, columns=close.columns)
    return close, mom


def test_breadth_is_share_of_members_passing_momentum():
    close, mom = _panel()
    mom.loc[mom.index[-1], ["A", "B"]] = True
    sector_map = {"A": "Semi", "B": "Semi", "C": "Semi", "D": "PCB"}
    df = sb.sector_breadth(mom, close, sector_map)
    semi = df.set_index("sector").loc["Semi"]
    assert semi["n"] == 3
    assert semi["breadth"] == pytest.approx(2 / 3 * 100)
    assert df.set_index("sector").loc["PCB", "breadth"] == 0


def test_breadth_change_vs_lookback():
    close, mom = _panel()
    mom.loc[mom.index[-21], ["A"]] = True               # 20 個交易日前 1/3
    mom.loc[mom.index[-1], ["A", "B", "C"]] = True      # 今日 3/3
    df = sb.sector_breadth(mom, close, {"A": "Semi", "B": "Semi", "C": "Semi"}, lookback=20)
    row = df.iloc[0]
    assert row["breadth_prev"] == pytest.approx(100 / 3)
    assert row["change"] == pytest.approx(100 - 100 / 3)


def test_breadth_ignores_members_without_price():
    close, mom = _panel()
    close.loc[close.index[-1], "C"] = np.nan             # 停牌/無資料
    mom.loc[mom.index[-1], ["A"]] = True
    df = sb.sector_breadth(mom, close, {"A": "Semi", "B": "Semi", "C": "Semi"})
    assert df.iloc[0]["breadth"] == pytest.approx(50.0)


def test_sorted_by_breadth_desc():
    close, mom = _panel()
    mom.loc[mom.index[-1], ["D"]] = True
    df = sb.sector_breadth(mom, close, {"A": "Semi", "B": "Semi", "D": "PCB"})
    assert list(df["sector"]) == ["PCB", "Semi"]


def test_append_history_is_idempotent_per_date(tmp_path):
    p = tmp_path / "h.csv"
    df = pd.DataFrame({"sector": ["Semi"], "n": [3], "breadth": [10.0]})
    sb.append_history(df, p, "2026-10-16")
    sb.append_history(df.assign(breadth=20.0), p, "2026-10-16")   # 同日重跑 → 覆寫
    sb.append_history(df, p, "2026-10-17")
    h = pd.read_csv(p)
    assert len(h) == 2
    assert h.loc[h.date == "2026-10-16", "breadth"].iloc[0] == 20.0


def test_format_line_top_and_fastest_spread():
    df = pd.DataFrame({"sector": ["Semiconductor Equipment & Materials", "Computer Hardware",
                                  "Electronics & Computer Distribution"],
                       "n": [63, 112, 35], "breadth": [41.9, 25.5, 14.3],
                       "breadth_prev": [45.1, 20.0, 5.7], "change": [-3.2, 5.5, 8.6]})
    line = sb.format_line(df, top=2)
    assert "半導體設備材料 41.9%(-3.2)" in line
    assert "電腦硬體 25.5%(+5.5)" in line
    assert "擴散最快: 電子通路 +8.6" in line


# --------------------------------------------------------------------------- #
# 掛點: treemap routine (日) / signal ledger (週)
# --------------------------------------------------------------------------- #
import sector_treemap_routine as str_routine  # noqa: E402
import signal_ledger as ledger  # noqa: E402


def test_treemap_breadth_line_uses_today(monkeypatch):
    df = pd.DataFrame({"sector": ["Semiconductors"], "n": [10], "breadth": [30.0],
                       "breadth_prev": [20.0], "change": [10.0]})
    seen = {}
    monkeypatch.setattr(sb, "today", lambda write=True: seen.setdefault("w", write) and None
                        or ("2026-10-16", df))
    line = str_routine.breadth_line(write=False)
    assert line.startswith("📊 產業動能廣度")
    assert seen["w"] is False


def test_treemap_breadth_line_swallows_errors(monkeypatch):
    def boom(write=True):
        raise RuntimeError("db down")
    monkeypatch.setattr(sb, "today", boom)
    assert str_routine.breadth_line(write=True) == ""


def test_ledger_breadth_gauge_reads_latest_history(tmp_path):
    p = tmp_path / "h.csv"
    pd.DataFrame({"date": ["2026-10-09", "2026-10-16", "2026-10-16"],
                  "sector": ["Semiconductors", "Semiconductors", "Computer Hardware"],
                  "n": [10, 10, 8], "breadth": [10.0, 30.0, 25.0]}).to_csv(p, index=False)
    g = ledger.breadth_gauge(p)
    assert "2026-10-16" in g and "半導體 30.0%" in g and "電腦硬體 25.0%" in g


def test_ledger_breadth_gauge_missing_file(tmp_path):
    assert ledger.breadth_gauge(tmp_path / "none.csv") == ""
