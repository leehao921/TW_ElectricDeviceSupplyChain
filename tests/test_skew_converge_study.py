"""skew 收斂日級研究 (2026-10-07) — 純函式。"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import skew_converge_study as s  # noqa: E402

D = pd.bdate_range("2026-09-01", periods=10)


def test_front_expiry_skips_near_dated():
    exps = ["20260916", "20261021", "20261118"]
    assert s.front_expiry(exps, pd.Timestamp("2026-09-14")) == "20261021"   # 9/16 只剩 2 天
    assert s.front_expiry(exps, pd.Timestamp("2026-09-08")) == "20260916"


def test_delta_events_and_decluster():
    skew = pd.Series([2.0, 2.0, 2.0, 0.9, 0.8, 0.5, 2.0, 2.0, 2.0, 0.5], index=D)
    ev = s.detect_events(skew, lookback=3, threshold=-1.0, gap=3)
    # Δ3: idx3=-1.1 ✓, idx4=-1.2 (距 idx3 <3 合併), idx5=-1.5 (合併), idx9=-1.5 ✓
    assert list(ev) == [D[3], D[9]]


def test_level_events():
    skew = pd.Series([1.0, -0.2, -0.3, 1.0, 1.0, 1.0, -0.1, 1, 1, 1], index=D)
    assert list(s.level_events(skew, below=0.0, gap=3)) == [D[1], D[6]]


def test_forward_returns_in_pct():
    close = pd.Series([100.0, 101, 102, 103, 104, 105, 106, 107, 108, 109], index=D)
    r = s.forward_returns(close, D[2], horizons=(1, 3))
    assert round(r[1], 4) == round((103 / 102 - 1) * 100, 4)
    assert round(r[3], 4) == round((105 / 102 - 1) * 100, 4)
    assert s.forward_returns(close, D[8], horizons=(3,))[3] is None   # 超出資料


def test_summary_refuses_small_n():
    out = s.summarize([0.5, 1.0], [0.1] * 30, min_n=20)
    assert out["n"] == 2 and out["verdict"] == "樣本不足,不下結論"
    assert out["hit"] == 1.0
