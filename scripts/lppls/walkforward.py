"""Walk-forward 引擎＋回檔事件偵測＋事前通過準則評估（spec §3）。

準則（寫死，不得事後放寬）:
  1. >=5% 回檔事件中，至少半數事前 30 交易日內有 LPPLS 訊號
  2. False positive（訊號後 20 日內未跌 >3%）比率 < 50%
  3. 訊號日 20 日 forward return 劣於無訊號日（中位數 + Mann-Whitney U one-sided）
"""
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from scripts.lppls.fitter import SIGNAL_TC_WITHIN, fit


def detect_drawdowns(series: pd.Series, threshold: float = 0.05):
    """滾動高點回落 >= threshold 的事件；觸發後直到收復前高不重複計。"""
    events, peak, peak_date, armed = [], -np.inf, None, True
    for date, px in series.items():
        if px >= peak:
            peak, peak_date, armed = px, date, True
        elif armed and (peak - px) / peak >= threshold:
            events.append(dict(peak_date=peak_date, trigger_date=date,
                               depth=(peak - px) / peak))
            armed = False
    return events


def walk_forward(series: pd.Series, window: int = 100, step: int = 5,
                 half_life: float = 50.0) -> pd.DataFrame:
    """每 step 日 refit 一次，回傳原始擬合表（不含 signal 欄，由 with_signal 套）。"""
    rows = []
    for end in range(window, len(series) + 1, step):
        win = series.iloc[end - window:end]
        f = fit(win.values, half_life=half_life)
        rows.append(dict(date=series.index[end - 1], r2=f.r2,
                         tc_days=f.days_to_tc(window), m=f.m, omega=f.omega,
                         B=f.B, qualifies=f.qualifies, refined=f.refined))
    return pd.DataFrame(rows).set_index("date")


def with_signal(wf: pd.DataFrame, r2_min: float = 0.7) -> pd.DataFrame:
    out = wf.copy()
    out["signal"] = (out["qualifies"] & (out["r2"] >= r2_min)
                     & (out["tc_days"] > 0) & (out["tc_days"] <= SIGNAL_TC_WITHIN))
    return out


def forward_return(series: pd.Series, date, horizon: int = 20):
    """(期末報酬, 期間最低點報酬)；不足 horizon 日回傳 (None, None)。"""
    pos = series.index.get_loc(date)
    fwd = series.iloc[pos + 1: pos + 1 + horizon]
    if len(fwd) < horizon:
        return None, None
    p0 = series.iloc[pos]
    return float(fwd.iloc[-1] / p0 - 1.0), float(fwd.min() / p0 - 1.0)


def evaluate(series: pd.Series, wf: pd.DataFrame, events,
             lookback: int = 30, horizon: int = 20) -> dict:
    sig_dates = set(wf.index[wf["signal"]])
    captured = 0
    for ev in events:
        pos = series.index.get_loc(ev["trigger_date"])
        window_dates = set(series.index[max(0, pos - lookback):pos])
        if sig_dates & window_dates:
            captured += 1
    fp = tot = 0
    sig_fwd, nosig_fwd = [], []
    for d in wf.index:
        r_end, r_min = forward_return(series, d, horizon)
        if r_end is None:
            continue
        if d in sig_dates:
            tot += 1
            if r_min > -0.03:
                fp += 1
            sig_fwd.append(r_end)
        else:
            nosig_fwd.append(r_end)
    mw_pvalue = None
    if len(sig_fwd) >= 3 and len(nosig_fwd) >= 3:
        mw_pvalue = float(mannwhitneyu(sig_fwd, nosig_fwd,
                                       alternative="less").pvalue)
    return dict(
        n_events=len(events), captured=captured,
        capture_rate=(captured / len(events)) if events else None,
        n_signals=int(wf["signal"].sum()), n_signals_evaluable=tot,
        fp_rate=(fp / tot) if tot else None,
        sig_fwd_median=float(np.median(sig_fwd)) if sig_fwd else None,
        nosig_fwd_median=float(np.median(nosig_fwd)) if nosig_fwd else None,
        mw_pvalue=mw_pvalue,
    )
