"""geo-attr 資料 loaders — gdelt/fx/外資全序列 + Brent yfinance cache。"""
import contextlib
from pathlib import Path

import pandas as pd
import yfinance as yf

from scripts.lppls.db import connect

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "analysis" / "cache"


def load_gdelt(query_key: str) -> pd.DataFrame:
    sql = ("SELECT date, article_count, avg_tone FROM gdelt_daily "
           "WHERE query_key = %s ORDER BY date")
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn, params=(query_key,)).set_index("date")


def load_fx(pair: str) -> pd.Series:
    sql = "SELECT ts::date AS date, close FROM fx_daily WHERE pair = %s ORDER BY 1"
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn, params=(pair,)).set_index("date")["close"]


def load_foreign_net_value(components) -> pd.Series:
    """外資淨買金額(股數×收盤)全序列,加總成分股。"""
    sql = ("SELECT date, sum(foreign_net * close_price) AS fnet "
           "FROM institutional_stock WHERE symbol = ANY(%s) "
           "GROUP BY date ORDER BY date")
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn,
                           params=(list(components),)).set_index("date")["fnet"]




def _cache_is_fresh(cache: Path) -> bool:
    """Return True if the cache's max date >= (today - 1 calendar day).

    Staleness rule: cache max date < today-1 → stale → refetch.
    Within the same calendar day, subsequent runs must read from cache
    (研究情境不變).
    """
    import datetime as _dt
    try:
        df = pd.read_csv(cache, parse_dates=["date"])
        max_date = df["date"].max()
        if pd.isna(max_date):
            return False
        # Normalise to date object regardless of dtype
        if hasattr(max_date, "date"):
            max_date = max_date.date()
        elif not isinstance(max_date, _dt.date):
            max_date = pd.Timestamp(max_date).date()
        threshold = _dt.date.today() - _dt.timedelta(days=1)
        return max_date >= threshold
    except Exception:
        return False


def load_yf(ticker: str, cache_name: str, start="2024-12-01") -> pd.Series:
    """yfinance 日線 Close,cache 到 analysis/cache/<cache_name>.csv。

    Cache 時效規則:
    - cache 不存在 → 拉網路並寫入
    - cache 最新日期 < 今日−1 (日曆日) → stale → 重抓覆寫
    - cache 最新日期 ≥ 今日−1 → fresh → 直讀 (不觸網)
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{cache_name}.csv"
    if cache.exists() and _cache_is_fresh(cache):
        df = pd.read_csv(cache, parse_dates=["date"])
        df["date"] = df["date"].dt.date
        return df.set_index("date")["close"]
    hist = yf.Ticker(ticker).history(start=start, auto_adjust=False)
    s = hist["Close"]
    s.index = [ts.date() for ts in s.index]
    s.index.name = "date"
    s.name = "close"
    s.to_frame().to_csv(cache)
    return s


def load_brent(start="2024-12-01") -> pd.Series:
    """BZ=F 日線(向後相容 wrapper)。"""
    return load_yf("BZ=F", "brent_daily", start)
