"""vix_signal_study 純函式測試 — 事件偵測/去叢集/前瞻報酬 (plan: 2026-08-26)"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import vix_signal_study as vs  # noqa: E402


def _ts(day, hm):
    return pd.Timestamp(f"2026-08-{day:02d} {hm}:00+08:00")


def test_detect_events_zscore_threshold():
    # 基準日 (8/4-8/7) delta 皆 ~0, 事件日 8/8 10:30 delta=+2.0 → z 遠超 2
    idx, vals = [], []
    wiggle = [0.05, 0.10, 0.15, 0.08]      # 非退化基準 (sd>0)
    for day in (4, 5, 6, 7, 8):
        for i, m in enumerate(range(0, 60, 15)):
            idx.append(_ts(day, f"10:{m:02d}"))
            vals.append(wiggle[i] if not (day == 8 and m == 30) else 2.0)
    s = pd.Series(vals, index=pd.DatetimeIndex(idx))
    events = vs.detect_events(s, z_th=2.0, min_baseline=3, decluster_min=30)
    assert len(events) == 1 and events[0].strftime("%H:%M") == "10:30"


def test_detect_events_decluster_keeps_first():
    idx = [_ts(8, "10:00"), _ts(8, "10:15"), _ts(8, "11:30")]
    base_idx = [_ts(d, "10:00") for d in (4, 5, 6, 7)]
    s = pd.Series([0.0, 0.1, -0.1, 0.05] + [5.0, 5.0, 5.0],
                  index=pd.DatetimeIndex(base_idx + idx))
    events = vs.detect_events(s, z_th=2.0, min_baseline=3, decluster_min=30)
    hhmm = [e.strftime("%H:%M") for e in events]
    assert "10:00" in hhmm and "10:15" not in hhmm   # 30 分內第二發被除
    assert "11:30" in hhmm                            # 隔 75 分 → 保留


def test_forward_returns_alignment_and_close_truncation():
    bars = pd.Series(
        [100.0, 101.0, 102.0, 103.0, 104.0],
        index=pd.DatetimeIndex([_ts(8, "13:20"), _ts(8, "13:25"),
                                _ts(8, "13:30"), _ts(8, "13:35"), _ts(8, "13:40")]))
    r = vs.forward_returns(bars, _ts(8, "13:20"), horizons_min=(10, 60))
    assert abs(r[10] - (102.0 / 100.0 - 1) * 100) < 1e-9   # +10 分 = 13:30 bar
    assert abs(r[60] - (104.0 / 100.0 - 1) * 100) < 1e-9   # 超出收盤 → 截斷至最後 bar
    assert abs(r["to_close"] - 4.0) < 1e-9


def test_forward_returns_none_when_no_entry_bar():
    bars = pd.Series([100.0], index=pd.DatetimeIndex([_ts(8, "09:00")]))
    r = vs.forward_returns(bars, _ts(9, "09:00"), horizons_min=(10,))
    assert r is None                                        # 事件日無 bars → None


def test_event_vs_baseline_stats():
    ev = [1.0, 2.0, -0.5, 3.0]
    base = [0.0, 0.1, -0.1, 0.05, -0.05, 0.2]
    out = vs.event_vs_baseline(ev, base)
    assert out["n"] == 4
    assert out["median"] == 1.5
    assert out["hit_up"] == 0.75                            # 3/4 > 0
    assert out["baseline_median"] == 0.025


def test_session_filter_day_only():
    idx = [_ts(8, "08:50"), _ts(8, "13:40"), _ts(8, "21:00"), _ts(9, "03:00")]
    s = pd.Series([1, 2, 3, 4], index=pd.DatetimeIndex(idx))
    f = vs.day_session_only(s)
    assert list(f.values) == [1, 2]                         # 夜盤全排除
