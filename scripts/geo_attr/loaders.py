"""geo-attr 資料 loaders — gdelt/fx/外資全序列 + Brent yfinance cache。"""
import contextlib
from pathlib import Path

import pandas as pd

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


def load_yf(ticker: str, cache_name: str, start="2024-12-01") -> pd.Series:
    """yfinance 日線 Close,cache 到 analysis/cache/<cache_name>.csv(存在即直讀)。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{cache_name}.csv"
    if cache.exists():
        df = pd.read_csv(cache, parse_dates=["date"])
        df["date"] = df["date"].dt.date
        return df.set_index("date")["close"]
    import yfinance as yf
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
