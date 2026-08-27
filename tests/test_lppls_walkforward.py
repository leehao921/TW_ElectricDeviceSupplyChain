import numpy as np
import pandas as pd

from scripts.lppls.fitter import make_synthetic
from scripts.lppls.walkforward import (
    detect_drawdowns, walk_forward, with_signal, evaluate,
)


def _series(values, start="2025-01-02"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


def test_detect_drawdowns_single_event():
    vals = list(np.linspace(100, 120, 50)) + list(np.linspace(120, 108, 10))  # -10%
    events = detect_drawdowns(_series(vals), threshold=0.05)
    assert len(events) == 1
    assert events[0]["depth"] >= 0.05


def test_detect_drawdowns_no_double_count_until_recovery():
    vals = (list(np.linspace(100, 120, 50)) + list(np.linspace(120, 105, 10))
            + list(np.linspace(105, 110, 10)) + list(np.linspace(110, 100, 10)))
    events = detect_drawdowns(_series(vals), threshold=0.05)
    assert len(events) == 1  # 未收復前高 120，同一事件不重算


def test_detect_drawdowns_flat_no_events():
    assert detect_drawdowns(_series([100.0] * 60), threshold=0.05) == []


def test_walk_forward_bubble_series_emits_signal_before_crash():
    bubble = make_synthetic(160, tc=165.0, m=0.5, omega=8.0, noise=0.0005)
    crash = bubble[-1] * np.linspace(0.99, 0.85, 15)
    s = _series(np.concatenate([bubble, crash]))
    wf = with_signal(walk_forward(s, window=100, step=5), r2_min=0.7)
    crash_start = s.index[160]
    assert wf.loc[:crash_start, "signal"].any()


def test_walk_forward_flat_series_no_signal():
    s = _series([100.0] * 200)
    wf = with_signal(walk_forward(s, window=100, step=5), r2_min=0.7)
    assert not wf["signal"].any()


def test_evaluate_criteria_shapes():
    bubble = make_synthetic(160, tc=165.0, m=0.5, omega=8.0, noise=0.0005)
    crash = bubble[-1] * np.linspace(0.99, 0.85, 15)
    tail = crash[-1] * np.ones(25)  # 留 forward-return 空間
    s = _series(np.concatenate([bubble, crash, tail]))
    wf = with_signal(walk_forward(s, window=100, step=5), r2_min=0.7)
    events = detect_drawdowns(s, threshold=0.05)
    result = evaluate(s, wf, events)
    assert result["n_events"] == len(events)
    assert 0.0 <= result["capture_rate"] <= 1.0
    assert result["n_signals"] >= 1
    for key in ("fp_rate", "sig_fwd_median", "nosig_fwd_median", "mw_pvalue"):
        assert key in result
