"""signal_backtest 純函式測試 — daily event harness (plan 2026-08-28 Phase B)"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import signal_backtest as sb  # noqa: E402


def _dates(n, start="2025-01-06"):
    return pd.bdate_range(start, periods=n)


def test_rolling_pct_event_needs_history():
    d = _dates(300)
    vals = [1.0] * 299 + [50.0]  # 最後一天暴衝
    s = pd.Series(vals, index=d)
    ev = sb.rolling_pct_events(s, window=252, pct=0.98, min_history=252)
    assert list(ev) == [d[-1]]          # 只有最後一天; 前 252 日不足不判


def test_decluster_per_symbol_10d():
    d = _dates(30)
    events = pd.DataFrame({"symbol": ["A", "A", "A", "B"],
                           "date": [d[0], d[5], d[20], d[5]]})
    out = sb.decluster(events, gap_days=10)
    a = out[out.symbol == "A"].date.tolist()
    assert d[0] in a and d[5] not in a and d[20] in a   # 10 日內重複剔除
    assert len(out[out.symbol == "B"]) == 1


def test_forward_ret_uses_nth_trading_day():
    d = _dates(30)
    close = pd.DataFrame({"A": range(100, 130)}, index=d).astype(float)
    r = sb.forward_ret(close, "A", d[3], n=5)
    assert abs(r - (108 / 103 - 1) * 100) < 1e-9        # 第 5 個交易日
    assert sb.forward_ret(close, "A", d[28], n=5) is None  # 不足 5 日 → None


def test_event_stats_vs_same_day_market():
    # 事件報酬 vs 同日市場中位 (基準逐日配對, 非全期混合)
    ev = pd.DataFrame({"ret": [2.0, -1.0, 3.0], "mkt": [0.5, 0.5, 1.0]})
    st = sb.event_stats(ev)
    assert st["n"] == 3
    assert st["median"] == 2.0
    assert st["excess_median"] == 1.5                    # median(ret-mkt)
    assert abs(st["hit_beat"] - 2 / 3) < 1e-9


def test_grade_daily_thresholds():
    good = {"n": 30, "excess_median": -1.2, "hit_beat": 0.30}
    assert sb.grade_daily(good) == "VALIDATED"           # 超額 -1.2% + 命中偏離 20pp
    thin = {"n": 10, "excess_median": -3.0, "hit_beat": 0.2}
    assert sb.grade_daily(thin) == "INSUFFICIENT"
    weak = {"n": 30, "excess_median": -1.1, "hit_beat": 0.46}
    assert sb.grade_daily(weak) == "WEAK"     # 超額過門檻但 beat 偏離不足
    assert sb.grade_daily({"n": 30, "excess_median": -0.3, "hit_beat": 0.48}) == "NO-EDGE"
