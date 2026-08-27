"""四層泡沫 confirmation（spec §4）— pure scorer 與 DB loader 分離。

層次: margin(融資增速)/inst(法人高檔調節)/iv(IV結構)/ofi(價漲流衰竭)。
各層 None = 資料不足，不計入分母。
標籤: 全滿且n>=2=強警戒, >=一半=中性, n=0=資料不足, 其餘=降級。
"""
import contextlib

import numpy as np
import pandas as pd

from scripts.lppls.db import connect

# ---------- pure scorers ----------


def score_margin(fin_series: pd.Series):
    """融資餘額 5 日增速 z-score > 1 → 正回饋加速中。"""
    if len(fin_series) < 10:
        return None
    chg5 = fin_series.diff(5).dropna()
    if len(chg5) < 5 or chg5.std() == 0:
        return dict(score=0, z=0.0)
    z = float((chg5.iloc[-1] - chg5.mean()) / chg5.std())
    return dict(score=int(z > 1.0), z=z)


def score_institutional(fnet_series: pd.Series):
    """20 日累計外資買超 > 0 且近 3 日轉賣 → 高檔調節。"""
    if len(fnet_series) < 20:
        return None
    cum20 = float(fnet_series.tail(20).sum())
    last3 = float(fnet_series.tail(3).sum())
    return dict(score=int(cum20 > 0 and last3 < 0), cum20=cum20, last3=last3)


def score_iv(term_slope_latest, vrp_series: pd.Series, skew_series: pd.Series = None):
    """term slope 倒掛(Near>Far, slope>0) 或 VRP 落入自身 20% 分位以下 或 skew 陡化(> 自身 80% 分位)。

    term_slope 定義（上游 option_sentiment_math.compute_term_spread）:
        term_slope = Near ATM IV − Far ATM IV
        POSITIVE → Near > Far → backwardation（壓力/倒掛）
        NEGATIVE → Near < Far → contango（正常）
    """
    if term_slope_latest is None and (vrp_series is None or vrp_series.empty):
        return None
    # Fix 1: slope > 0 → Near>Far 倒掛 (backwardation) → stress signal
    inverted = term_slope_latest is not None and term_slope_latest > 0
    vrp_low = False
    if vrp_series is not None and vrp_series.notna().sum() >= 10:
        vrp_low = bool(vrp_series.iloc[-1] < vrp_series.quantile(0.2))
    # Fix 2: skew 陡化 component
    skew_steep = False
    if skew_series is not None and skew_series.notna().sum() >= 10:
        skew_steep = bool(skew_series.iloc[-1] > skew_series.quantile(0.8))
    return dict(score=int(inverted or vrp_low or skew_steep),
                inverted=inverted, vrp_low=vrp_low, skew_steep=skew_steep)


def score_ofi(ofi_daily: pd.Series, index_ret5: float):
    """指數 5 日漲但成分 OFI 分數 5 日斜率轉負 → 買方衰竭背離。"""
    if len(ofi_daily) < 5:
        return None
    tail = ofi_daily.tail(5)
    slope = float(np.polyfit(np.arange(len(tail)), tail.values, 1)[0])
    return dict(score=int(index_ret5 > 0 and slope < 0), slope=slope,
                index_ret5=float(index_ret5))


def aggregate(layers: dict):
    avail = {k: v for k, v in layers.items() if v is not None}
    total = sum(v["score"] for v in avail.values())
    n = len(avail)
    if n == 0:
        # Fix 3: all layers None → distinct 資料不足 label
        label = "資料不足"
    elif total == n and n >= 2:
        # Fix 3: 強警戒 requires ALL layers fire AND at least 2 available layers
        # single-layer full score must not produce 強警戒
        label = "強警戒"
    elif total >= n / 2:
        label = "中性"
    else:
        label = "降級"
    return dict(total=total, n_available=n, label=label, layers=layers)

# ---------- DB loaders（thin，Task 8 實跑驗證） ----------


def load_margin(asof) -> pd.Series:
    # 限定 TWSE：多市場列日後出現會造成序列跳點 → 假性 z>1
    sql = ("SELECT date, sum(fin_value_kilo_ntd) AS fin FROM margin_market_daily "
           "WHERE market = 'TWSE' AND date <= %s GROUP BY date ORDER BY date")
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn, params=(asof,)).set_index("date")["fin"]


def load_institutional(asof, components) -> pd.Series:
    sql = ("SELECT date, sum(foreign_net * close_price) AS fnet "
           "FROM institutional_stock WHERE symbol = ANY(%s) AND date <= %s "
           "GROUP BY date ORDER BY date")
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn,
                           params=(list(components), asof)).set_index("date")["fnet"]


def load_iv(asof):
    sql = ("SELECT date, term_slope, vrp_30d, iv_skew_25d FROM vix_daily "
           "WHERE date <= %s ORDER BY date")
    with contextlib.closing(connect()) as conn:
        df = pd.read_sql(sql, conn, params=(asof,)).set_index("date")
    if df.empty:
        return None, pd.Series(dtype=float), pd.Series(dtype=float)
    ts_series = df["term_slope"].dropna()
    latest = float(ts_series.iloc[-1]) if not ts_series.empty else None
    return latest, df["vrp_30d"].dropna(), df["iv_skew_25d"].dropna()


def load_ofi_daily(asof, components) -> pd.Series:
    sql = ("SELECT ts::date AS date, avg(value) AS ofi FROM stock_ofi "
           "WHERE signal_type = 'ofi_score' AND symbol = ANY(%s) "
           "AND ts::date <= %s GROUP BY 1 ORDER BY 1")
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn,
                           params=(list(components), asof)).set_index("date")["ofi"]


def confirm(asof, components, index_ret5: float):
    """LPPLS 訊號日的四層旁證總評。"""
    term_slope, vrp, skew = load_iv(asof)
    layers = dict(
        margin=score_margin(load_margin(asof)),
        inst=score_institutional(load_institutional(asof, components)),
        iv=score_iv(term_slope, vrp, skew),
        ofi=score_ofi(load_ofi_daily(asof, components), index_ret5),
    )
    return aggregate(layers)
