"""trading-timescaledb read-only loaders（DB_CONFIG 沿用 options_quant 慣例）。"""
import contextlib
import os
import warnings

import pandas as pd
import psycopg2

warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")

DB_CONFIG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5432")),
    user=os.environ.get("DB_USER", "tmf"),
    password=os.environ.get("DB_PASSWORD", "tmf_dev_2026"),
    dbname=os.environ.get("DB_NAME", "tmf_market_data"),
)


def connect():
    return psycopg2.connect(**DB_CONFIG)


def load_daily_closes(symbols) -> pd.DataFrame:
    """date × symbol 的收盤價寬表。"""
    sql = ("SELECT ts::date AS date, symbol, close FROM stock_daily_ohlcv "
           "WHERE symbol = ANY(%s) ORDER BY 1")
    with contextlib.closing(connect()) as conn:
        df = pd.read_sql(sql, conn, params=(list(symbols),))
    return df.pivot(index="date", columns="symbol", values="close")


def load_taiex() -> pd.Series:
    sql = "SELECT date, close FROM taiex_ema_daily ORDER BY date"
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn).set_index("date")["close"]
