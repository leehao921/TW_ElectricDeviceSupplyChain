"""Market-layer tools: READ-ONLY access to `trading-timescaledb`."""

from __future__ import annotations

import os
from typing import Any

PG_TRADING_DSN = os.environ.get(
    "PG_TRADING_DSN",
    "postgresql://tmf:tmf_dev_2026@localhost:5432/tmf_market_data",
)


async def _connect():
    import asyncpg
    return await asyncpg.connect(PG_TRADING_DSN)


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


async def _get_columns(conn, table: str) -> set[str]:
    rows = await conn.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table,
    )
    return {r["column_name"] for r in rows}


async def _detect_tick_schema(conn) -> tuple[str, str, str, str, str] | None:
    """Find a ticks/trades/ohlcv table and detect ticker/time/price/volume cols.

    Returns (table, ticker_col, ts_col, price_col, volume_col) or None.
    """
    for table in ("ticks", "trades", "ohlcv_1m", "ohlcv_1s"):
        names = await _get_columns(conn, table)
        if not names:
            continue
        ticker_col = next((c for c in ("ticker", "symbol", "code") if c in names), None)
        ts_col = next(
            (c for c in ("ts", "time", "timestamp", "trade_time", "bucket") if c in names),
            None,
        )
        price_col = next((c for c in ("price", "close", "last_price") if c in names), None)
        volume_col = next((c for c in ("volume", "size", "qty") if c in names), None)
        if ticker_col and ts_col and price_col:
            return table, ticker_col, ts_col, price_col, volume_col or "1"
    return None


async def get_price_history(ticker: str, days: int = 30) -> list[dict[str, Any]]:
    """Return daily OHLCV bars for `ticker` over the last `days` days."""
    try:
        conn = await _connect()
    except Exception as e:
        return [{"error": f"trading DB unreachable: {e}"}]
    try:
        schema = await _detect_tick_schema(conn)
        if schema is None:
            return [{"error": "no ticks/trades table found in trading DB"}]
        table, tc, ts, pc, vc = schema
        volume_expr = f"SUM({vc})" if vc != "1" else "COUNT(*)"
        query = f"""
            SELECT date_trunc('day', {ts}) AS date,
                   MIN({pc}) AS low,
                   MAX({pc}) AS high,
                   (array_agg({pc} ORDER BY {ts} ASC))[1] AS open,
                   (array_agg({pc} ORDER BY {ts} DESC))[1] AS close,
                   {volume_expr} AS volume
            FROM {table}
            WHERE {tc} = $1
              AND {ts} > NOW() - ($2::text || ' days')::interval
            GROUP BY date_trunc('day', {ts})
            ORDER BY date DESC
        """
        rows = await conn.fetch(query, ticker, str(int(days)))
        return _rows_to_dicts(rows)
    except Exception as e:
        return [{"error": f"price history query failed: {e}"}]
    finally:
        await conn.close()


async def get_institutional_flow(ticker: str, days: int = 5) -> list[dict[str, Any]]:
    """Return rows from `institutional_stock` for `ticker` within the last `days` days."""
    try:
        conn = await _connect()
    except Exception as e:
        return [{"error": f"trading DB unreachable: {e}"}]
    try:
        names = await _get_columns(conn, "institutional_stock")
        if not names:
            return [{"error": "table institutional_stock not found"}]
        ticker_col = next((c for c in ("ticker", "symbol", "code") if c in names), None)
        date_col = next((c for c in ("date", "trade_date", "ts") if c in names), None)
        if not ticker_col or not date_col:
            return [{"error": "institutional_stock missing ticker/date columns"}]
        query = f"""
            SELECT *
            FROM institutional_stock
            WHERE {ticker_col} = $1
              AND {date_col} > NOW() - ($2::text || ' days')::interval
            ORDER BY {date_col} DESC
            LIMIT 200
        """
        rows = await conn.fetch(query, ticker, str(int(days)))
        return _rows_to_dicts(rows)
    except Exception as e:
        return [{"error": f"institutional flow query failed: {e}"}]
    finally:
        await conn.close()
