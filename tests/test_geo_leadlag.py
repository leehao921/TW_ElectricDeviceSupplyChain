import numpy as np
import pandas as pd

from scripts.geo_attr.leadlag import classify_event, false_alarm_rate

DATES = pd.bdate_range("2025-01-01", periods=200)


def _z(cross_offsets, trigger_pos=100, nan_frac=0.0):
    """z 序列: 預設 0,指定 offset(相對 trigger)處 = 3.0。"""
    vals = pd.Series(0.0, index=DATES)
    for off in cross_offsets:
        vals.iloc[trigger_pos + off] = 3.0
    if nan_frac:
        n = int(len(vals) * nan_frac)
        vals.iloc[:n] = np.nan
    return vals


def test_classify_leading():
    r = classify_event(_z([-10, -9]), DATES, DATES[100])
    assert r["category"] == "領先"
    assert r["first_cross"] == -10


def test_classify_coincident():
    assert classify_event(_z([0]), DATES, DATES[100])["category"] == "同步"
    assert classify_event(_z([-2]), DATES, DATES[100])["category"] == "同步"
    assert classify_event(_z([2]), DATES, DATES[100])["category"] == "同步"


def test_classify_lagging_and_silent():
    assert classify_event(_z([4]), DATES, DATES[100])["category"] == "落後"
    assert classify_event(_z([]), DATES, DATES[100])["category"] == "沉默"


def test_classify_boundary_minus3_is_leading():
    r = classify_event(_z([-3]), DATES, DATES[100])
    assert r["category"] == "領先"
    assert r["first_cross"] == -3


def test_classify_insufficient_data():
    z = _z([], nan_frac=0.95)   # 觀察窗 [70..105] 全 NaN (190/200 NaN)
    assert classify_event(z, DATES, DATES[100])["category"] == "資料不足"


def test_false_alarm_rate_exact():
    """手算:
    情境 A — 指數全程平盤 100: z 警報在 pos 50, 60(皆在事件排除窗
    [100−30, 100+20]=[70,120] 之外)。平盤 → 20 日 forward min return = 0 > −3%
    → 兩者皆誤報 → far = 1.0, n_alerts = 2。
    情境 B — 指數 pos 65 起跌至 90(−10%): pos50 的 forward 窗 51..70 含 pos65
    下跌(r_min=−10%<−3%)→ 非誤報; pos60 窗 61..80 自 pos65 起在低檔(r_min=90/100−1=−10%)
    → 亦非誤報 → far = 0.0, n_alerts = 2。"""
    index_flat = pd.Series(100.0, index=DATES)
    z = pd.Series(0.0, index=DATES)
    z.iloc[50] = 3.0
    z.iloc[60] = 3.0
    events = [dict(trigger_date=DATES[100])]
    far, n = false_alarm_rate(z, index_flat, events)
    assert (far, n) == (1.0, 2)

    vals = [100.0] * 65 + [90.0] * 135
    index_drop = pd.Series(vals, index=DATES)
    far2, n2 = false_alarm_rate(z, index_drop, events)
    assert n2 == 2
    assert far2 == 0.0


def test_false_alarm_rate_no_alerts():
    index_flat = pd.Series(100.0, index=DATES)
    z = pd.Series(0.0, index=DATES)
    far, n = false_alarm_rate(z, index_flat, [dict(trigger_date=DATES[100])])
    assert far is None and n == 0
