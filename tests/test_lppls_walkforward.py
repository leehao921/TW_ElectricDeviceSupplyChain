import numpy as np
import pandas as pd
import pytest

from scripts.lppls.fitter import make_synthetic, fit, is_signal, SIGNAL_TC_WITHIN
from scripts.lppls.walkforward import (
    detect_drawdowns, walk_forward, with_signal, evaluate,
)


def _series(values, start="2025-01-02"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


# ---------------------------------------------------------------------------
# detect_drawdowns
# ---------------------------------------------------------------------------

def test_detect_drawdowns_single_event():
    # 100 -> 120 -> 108: decline = (120-108)/120 = 0.10
    vals = list(np.linspace(100, 120, 50)) + list(np.linspace(120, 108, 10))
    events = detect_drawdowns(_series(vals), threshold=0.05)
    assert len(events) == 1
    # Fix 4: depth reflects the full decline (0.10), depth_at_trigger >= 0.05
    assert abs(events[0]["depth"] - 0.10) < 1e-6, (
        f"expected depth ≈ 0.10, got {events[0]['depth']}"
    )
    assert events[0]["depth_at_trigger"] >= 0.05


def test_detect_drawdowns_depth_deepens_after_trigger():
    # Trigger at -5%; keeps declining to -15%. depth should end at ~0.15.
    # Peak = 120 at position 49; then 120->114 (5% drop, triggers), then to 102 (15% drop).
    vals = list(np.linspace(100, 120, 50)) + list(np.linspace(120, 114, 5)) + list(np.linspace(114, 102, 10))
    events = detect_drawdowns(_series(vals), threshold=0.05)
    assert len(events) == 1
    assert events[0]["depth_at_trigger"] == pytest.approx(0.05, abs=1e-4)
    assert events[0]["depth"] == pytest.approx((120 - 102) / 120, abs=1e-4)


def test_detect_drawdowns_no_double_count_until_recovery():
    vals = (list(np.linspace(100, 120, 50)) + list(np.linspace(120, 105, 10))
            + list(np.linspace(105, 110, 10)) + list(np.linspace(110, 100, 10)))
    events = detect_drawdowns(_series(vals), threshold=0.05)
    assert len(events) == 1  # 未收復前高 120，同一事件不重算


def test_detect_drawdowns_flat_no_events():
    assert detect_drawdowns(_series([100.0] * 60), threshold=0.05) == []


# ---------------------------------------------------------------------------
# walk_forward / with_signal
# ---------------------------------------------------------------------------

def test_walk_forward_bubble_series_emits_signal_before_crash():
    bubble = make_synthetic(160, tc=165.0, m=0.5, omega=8.0, noise=0.0005)
    crash = bubble[-1] * np.linspace(0.99, 0.85, 15)
    s = _series(np.concatenate([bubble, crash]))
    wf = with_signal(walk_forward(s, window=100, step=5), r2_min=0.7)
    # index[159] = 崩盤前最後一日（.loc 切片含端點，故用 159 排除首個崩盤日）
    crash_start = s.index[159]
    assert wf.loc[:crash_start, "signal"].any()


def test_walk_forward_flat_series_no_signal():
    s = _series([100.0] * 200)
    wf = with_signal(walk_forward(s, window=100, step=5), r2_min=0.7)
    assert not wf["signal"].any()


# ---------------------------------------------------------------------------
# evaluate — shape / keys
# ---------------------------------------------------------------------------

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
    for key in ("fp_rate", "sig_fwd_median", "nosig_fwd_median", "mw_pvalue",
                "n_events_capturable", "captured_capturable", "capture_rate_capturable",
                "mw_pvalue_nonoverlap", "n_signals_nonoverlap"):
        assert key in result, f"missing key: {key}"
    # capture_rate_capturable is in [0,1] or None if no capturable events
    if result["capture_rate_capturable"] is not None:
        assert 0.0 <= result["capture_rate_capturable"] <= 1.0
    # n_signals_nonoverlap is an int >= 0
    assert isinstance(result["n_signals_nonoverlap"], int)
    assert result["n_signals_nonoverlap"] >= 0


# ---------------------------------------------------------------------------
# Fix 3: exact-value test for evaluate (deterministic, no walk_forward)
# ---------------------------------------------------------------------------

def test_evaluate_exact_values():
    """Hand-crafted series + wf DataFrame with known exact outcomes.

    Series: 10 business days of prices. All prices constant at 100 except
    day 5 (index 5) which is 90 (10% drawdown), and days 6-9 recover to 100.

    Price series (bdate_range starting 2025-01-02):
      idx  0: 2025-01-02  100
      idx  1: 2025-01-03  100
      idx  2: 2025-01-06  100
      idx  3: 2025-01-07  100
      idx  4: 2025-01-08  100   <- peak
      idx  5: 2025-01-09   90   <- trigger (10% drop from 100)
      idx  6: 2025-01-10  100
      idx  7: 2025-01-13  100
      idx  8: 2025-01-14  100
      idx  9: 2025-01-15  100

    Hand-built events:
      trigger_date = 2025-01-09 (idx 5), peak_date = 2025-01-08 (idx 4)

    Walk-forward rows (hand-built) at idx 2, 3, 4, 5:
      date           signal
      2025-01-06     True    <- idx 2: 3 positions before trigger (5-3=2 = start of window)
      2025-01-07     False   <- idx 3
      2025-01-08     False   <- idx 4
      2025-01-09     True    <- idx 5 = trigger_date

    Capture logic (lookback=3): for event at trigger idx=5:
      window = series.index[max(0, 5-3):5] = series.index[2:5] = {idx2, idx3, idx4}
      sig_dates = {idx2 (2025-01-06), idx5 (2025-01-09)}
      sig_dates ∩ window = {idx2} → CAPTURED
      captured=1, capture_rate=1.0

    Boundary: idx2 is EXACTLY at pos_trigger - lookback (5-3=2) → included in window
    Boundary: idx5 = trigger_date is NOT in window (window is [:5], exclusive) → not captured

    Capturable (any wf date in window {idx2,3,4}):
      wf_dates = {idx2, idx3, idx4, idx5}; intersection with window = {idx2,3,4} → non-empty
      n_capturable=1, captured_capturable=1, capture_rate_capturable=1.0

    Forward returns (horizon=3) — each row's p0 is its own price, fwd is next 3 prices:
      idx2 (p0=100): fwd=[idx3,idx4,idx5]=[100, 100, 90]
        r_end = 90/100 - 1 = -0.10
        r_min = min([100,100,90])/100 - 1 = -0.10
        signal=True, r_min=-0.10 <= -0.03 → NOT fp; sig_fwd += [-0.10]

      idx3 (p0=100): fwd=[idx4,idx5,idx6]=[100, 90, 100]
        r_end = 100/100 - 1 = 0.0
        r_min = 90/100 - 1 = -0.10
        signal=False; nosig_fwd += [0.0]

      idx4 (p0=100): fwd=[idx5,idx6,idx7]=[90, 100, 100]
        r_end = 100/100 - 1 = 0.0
        r_min = 90/100 - 1 = -0.10
        signal=False; nosig_fwd += [0.0]

      idx5 (p0=90): fwd=[idx6,idx7,idx8]=[100, 100, 100]
        r_end = 100/90 - 1 = +1/9 ≈ 0.1111
        r_min = 100/90 - 1 = +1/9 ≈ 0.1111  (no decline in fwd window)
        signal=True, r_min=+0.111 > -0.03 → FP; fp += 1; sig_fwd += [1/9]

    Summary:
      fp=1, tot=2, fp_rate = 1/2 = 0.5
      sig_fwd = [-0.10, 1/9] → median = (-0.10 + 1/9) / 2 = (0.1/9) / 2 = 1/180 ≈ +0.005556
      nosig_fwd = [0.0, 0.0] → median = 0.0
    """
    # sig_fwd_median exact value: mean of -0.10 and (1/9)
    # = (-0.10 + 1/9) / 2 = (-9/90 + 10/90) / 2 = (1/90) / 2 = 1/180
    _SIG_FWD_MEDIAN = ((-0.10) + (100.0 / 90.0 - 1.0)) / 2.0  # ≈ 0.005556

    prices = [100.0, 100.0, 100.0, 100.0, 100.0, 90.0, 100.0, 100.0, 100.0, 100.0]
    s = _series(prices)
    # idx: 0=2025-01-02, 1=2025-01-03, 2=2025-01-06, 3=2025-01-07,
    #      4=2025-01-08, 5=2025-01-09, 6=2025-01-10, 7=2025-01-13,
    #      8=2025-01-14, 9=2025-01-15

    dates = s.index
    # Hand-built wf: rows at idx 2, 3, 4, 5
    wf_dates = [dates[2], dates[3], dates[4], dates[5]]
    wf = pd.DataFrame({
        "qualifies": [True, False, False, True],
        "r2":        [0.9, 0.5, 0.5, 0.9],
        "tc_days":   [5.0, 5.0, 5.0, 5.0],
        "signal":    [True, False, False, True],
    }, index=pd.DatetimeIndex(wf_dates, name="date"))

    # Hand-built event: trigger at idx=5
    events = [dict(
        peak_date=dates[4],
        trigger_date=dates[5],
        depth_at_trigger=0.10,
        depth=0.10,
    )]

    result = evaluate(s, wf, events, lookback=3, horizon=3)

    # --- Capture (all events) ---
    # captured=1: sig at idx2 (pos=2) is in window series.index[2:5]
    assert result["n_events"] == 1
    assert result["captured"] == 1
    assert result["capture_rate"] == pytest.approx(1.0)

    # --- Capturable ---
    # window {idx2,3,4} intersects wf_dates {idx2,3,4,5} → event is capturable
    assert result["n_events_capturable"] == 1
    assert result["captured_capturable"] == 1
    assert result["capture_rate_capturable"] == pytest.approx(1.0)

    # --- FP rate ---
    # tot=2, fp=1 (idx5 signal has r_min=+0.111 > -0.03)
    assert result["fp_rate"] == pytest.approx(0.5)

    # --- Forward return medians ---
    # sig_fwd = [-0.10, 100/90-1] → median = (−0.10 + 100/90 − 1) / 2 = 1/180 ≈ 0.005556
    assert result["sig_fwd_median"] == pytest.approx(_SIG_FWD_MEDIAN, rel=1e-9)
    # nosig_fwd = [0.0, 0.0] → median = 0.0
    assert result["nosig_fwd_median"] == pytest.approx(0.0, abs=1e-9)

    # --- Boundary: signal exactly lookback=3 positions before trigger counts ---
    # idx2 = pos_trigger - lookback = 5 - 3 = 2; window = series.index[2:5] → includes idx2
    # Verified: captured=1 above confirms this.

    # --- Boundary: signal on trigger date itself does NOT count for capture ---
    # idx5 (trigger_date) is NOT in window series.index[2:5] = {idx2,3,4}
    # Proof: remove signal at idx2; only idx5 remains → captured drops to 0
    wf2 = wf.copy()
    wf2.loc[dates[2], "signal"] = False  # remove idx2 signal
    result2 = evaluate(s, wf2, events, lookback=3, horizon=3)
    assert result2["captured"] == 0
    assert result2["capture_rate"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Fix 5: predicate-agreement — with_signal agrees with fitter.is_signal row-by-row
# ---------------------------------------------------------------------------

def test_with_signal_agrees_with_fitter_is_signal():
    """with_signal column should match fitter.is_signal() row-by-row.

    We use a small synthetic bubble series (window=100, step=10) for ~6 windows.
    For each walk_forward row, we also call fit() on the same window and
    is_signal() with r2_min=0.7, and assert equality with the signal column.
    """
    bubble = make_synthetic(160, tc=165.0, m=0.5, omega=8.0, noise=0.0005)
    s = _series(bubble)
    window = 100
    step = 10
    r2_min = 0.7

    wf_raw = walk_forward(s, window=window, step=step)
    wf = with_signal(wf_raw, r2_min=r2_min)

    # Re-fit each window and compare
    for end in range(window, len(s) + 1, step):
        date = s.index[end - 1]
        win = s.iloc[end - window:end]
        f = fit(win.values)
        expected = is_signal(f, window, r2_min=r2_min)
        actual = bool(wf.loc[date, "signal"])
        assert actual == expected, (
            f"Mismatch at {date}: with_signal={actual}, is_signal={expected}, "
            f"qualifies={f.qualifies}, r2={f.r2:.3f}, tc_days={f.days_to_tc(window):.1f}"
        )
