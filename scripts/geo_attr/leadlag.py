"""事件窗領先/同步分類＋誤報率（spec Phase C）。

分類(z>2 首次出現的 trigger 相對位置 first):
  first <= −3 → 領先;−2 <= first <= 2 → 同步;first >= 3 → 落後;無 → 沉默。
觀察窗 [−30, +5];窗內 z 有效值 <50% → 資料不足。
誤報率沿用 LPPLS FP 語意(forward_return 復用 walkforward)。
"""
import pandas as pd

from scripts.lppls.walkforward import forward_return

Z_THR = 2.0
PRE, POST = 30, 5
LEAD_MIN = 3


def classify_event(z: pd.Series, index_dates: pd.Index, trigger_date,
                   z_thr: float = Z_THR, pre: int = PRE, post: int = POST,
                   lead_min: int = LEAD_MIN) -> dict:
    pos = index_dates.get_loc(trigger_date)
    window = index_dates[max(0, pos - pre): min(len(index_dates), pos + post + 1)]
    zw = z.reindex(window)
    if zw.notna().mean() < 0.5:
        return dict(category="資料不足", first_cross=None)
    crossed = [index_dates.get_loc(d) - pos for d, v in zw.items() if v > z_thr]
    if not crossed:
        return dict(category="沉默", first_cross=None)
    first = min(crossed)
    if first <= -lead_min:
        cat = "領先"
    elif abs(first) <= 2:
        cat = "同步"
    else:
        cat = "落後"
    return dict(category=cat, first_cross=int(first))


def false_alarm_rate(z: pd.Series, index_series: pd.Series, events,
                     z_thr: float = Z_THR, horizon: int = 20,
                     drop_thr: float = -0.03, pre: int = PRE) -> tuple:
    """非事件期 z>z_thr 的日子,後 horizon 日指數未跌逾 |drop_thr| 的比率。
    事件排除窗 = 各 trigger 的 [−pre, +horizon]。回傳 (far, n_alerts);無警報 → (None, 0)。"""
    excluded = set()
    for ev in events:
        pos = index_series.index.get_loc(ev["trigger_date"])
        lo = max(0, pos - pre)
        hi = min(len(index_series), pos + horizon + 1)
        excluded.update(index_series.index[lo:hi])
    fp = tot = 0
    for d, v in z.items():
        if v is None or not v == v or v <= z_thr or d in excluded:
            continue
        if d not in index_series.index:
            continue
        r_end, r_min = forward_return(index_series, d, horizon)
        if r_end is None:
            continue
        tot += 1
        if r_min > drop_thr:
            fp += 1
    return ((fp / tot) if tot else None, tot)
