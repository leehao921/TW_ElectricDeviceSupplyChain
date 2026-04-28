"""FinMind monthly-revenue collector.

Fetches `TaiwanStockMonthRevenue` rows for a ticker and upserts them into
`finmind_fundamentals`. Free tier works without a token (slower limits); set
`FINMIND_TOKEN` for a signed request.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

import httpx

from ..config import FINMIND_TOKEN
from ..db import close_pool, get_pool
from ..universe import all_tickers
from ._common import make_client

API_URL = "https://api.finmindtrade.com/api/v4/data"
DATASET = "TaiwanStockMonthRevenue"
DEFAULT_SINCE = "2024-01"
RATE_LIMIT_SLEEP = 5.0  # FinMind free tier: sleep then retry on 402/429

UPSERT_SQL = """
INSERT INTO finmind_fundamentals (ticker, report_month, monthly_revenue, yoy_pct, mom_pct)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (ticker, report_month) DO UPDATE SET
    monthly_revenue = EXCLUDED.monthly_revenue,
    yoy_pct = EXCLUDED.yoy_pct,
    mom_pct = EXCLUDED.mom_pct
"""


@dataclass
class RevenueRow:
    ticker: str
    report_month: date
    monthly_revenue: int | None
    yoy_pct: Decimal | None
    mom_pct: Decimal | None


def _to_decimal(value) -> Decimal | None:
    if value in (None, "", "NaN"):
        return None
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None


def _to_int(value) -> int | None:
    if value in (None, "", "NaN"):
        return None
    try:
        return int(Decimal(str(value)))
    except (ValueError, ArithmeticError):
        return None


def parse_rows(ticker: str, payload: dict) -> list[RevenueRow]:
    """Normalize FinMind's `{"data": [...]}` payload to RevenueRow objects.

    FinMind returns either:
      - a `revenue_year`/`revenue_month` pair (newer), or
      - a `date` field like `2024-07-10` (older).
    We prefer the numeric pair when present so we always emit YYYY-MM-01.
    Growth fields are sometimes absent on the free tier; we derive them from
    consecutive revenue values so downstream consumers get usable numbers.
    """
    raw_rows: list[RevenueRow] = []
    for item in payload.get("data", []):
        year = item.get("revenue_year")
        month = item.get("revenue_month")
        if year and month:
            report_month = date(int(year), int(month), 1)
        elif item.get("date"):
            parsed = date.fromisoformat(item["date"])
            report_month = parsed.replace(day=1)
        else:
            continue
        raw_rows.append(RevenueRow(
            ticker=ticker,
            report_month=report_month,
            monthly_revenue=_to_int(item.get("revenue")),
            yoy_pct=_to_decimal(item.get("revenue_year_growth") or item.get("YoY")),
            mom_pct=_to_decimal(item.get("revenue_month_growth") or item.get("MoM")),
        ))
    if not raw_rows:
        return raw_rows

    raw_rows.sort(key=lambda r: r.report_month)
    by_month = {r.report_month: r for r in raw_rows}

    def _pct_change(new: int | None, old: int | None) -> Decimal | None:
        if new is None or old is None or old == 0:
            return None
        return (Decimal(new) - Decimal(old)) / Decimal(old) * Decimal(100)

    for row in raw_rows:
        if row.mom_pct is None:
            prev = by_month.get(_shift_month(row.report_month, -1))
            if prev:
                row.mom_pct = _pct_change(row.monthly_revenue, prev.monthly_revenue)
        if row.yoy_pct is None:
            prev_year = by_month.get(_shift_month(row.report_month, -12))
            if prev_year:
                row.yoy_pct = _pct_change(row.monthly_revenue, prev_year.monthly_revenue)
    return raw_rows


def _shift_month(d: date, delta: int) -> date:
    """Return `d` shifted by `delta` calendar months, preserving day=1."""
    month_index = d.year * 12 + (d.month - 1) + delta
    return date(month_index // 12, month_index % 12 + 1, 1)


async def _fetch(
    client: httpx.AsyncClient,
    ticker: str,
    start_date: str,
) -> dict:
    params = {"dataset": DATASET, "data_id": ticker, "start_date": start_date}
    if FINMIND_TOKEN:
        params["token"] = FINMIND_TOKEN

    for attempt in range(2):
        resp = await client.get(API_URL, params=params)
        if resp.status_code in (402, 429):
            if attempt == 0:
                print(
                    f"  rate-limited (HTTP {resp.status_code}); sleeping {RATE_LIMIT_SLEEP}s",
                    file=sys.stderr,
                )
                await asyncio.sleep(RATE_LIMIT_SLEEP)
                continue
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()
    return {"data": []}


def _since_to_start_date(since: str) -> str:
    """Accept YYYY-MM or YYYY-MM-DD; FinMind wants YYYY-MM-DD."""
    return since if len(since) == 10 else f"{since}-01"


async def collect(
    ticker: str,
    *,
    since: str = DEFAULT_SINCE,
    client: httpx.AsyncClient | None = None,
) -> list[RevenueRow]:
    own_client = client is None
    client = client or make_client()
    try:
        payload = await _fetch(client, ticker, _since_to_start_date(since))
        return parse_rows(ticker, payload)
    finally:
        if own_client:
            await client.aclose()


async def _run(tickers: Iterable[str], *, since: str, dry_run: bool) -> None:
    async with make_client() as client:
        for ticker in tickers:
            print(f"[finmind] {ticker}")
            rows = await collect(ticker, since=since, client=client)
            if dry_run:
                for r in rows:
                    print(
                        f"  {r.report_month.isoformat()}  rev={r.monthly_revenue}  "
                        f"YoY={r.yoy_pct}  MoM={r.mom_pct}"
                    )
                continue
            if not rows:
                print("  no rows returned")
                continue
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.executemany(
                    UPSERT_SQL,
                    [
                        (r.ticker, r.report_month, r.monthly_revenue, r.yoy_pct, r.mom_pct)
                        for r in rows
                    ],
                )
            print(f"  wrote {len(rows)} rows")
    if not dry_run:
        await close_pool()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FinMind monthly-revenue collector")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticker", help="4-digit ticker, e.g. 2330")
    group.add_argument("--all", action="store_true", help="iterate every electronics ticker")
    parser.add_argument("--since", default=DEFAULT_SINCE, help="YYYY-MM; default 2024-01")
    parser.add_argument("--dry-run", action="store_true", help="parse + print; no DB write")
    args = parser.parse_args(argv)

    tickers = all_tickers() if args.all else [args.ticker]
    if not tickers:
        print("no tickers to process", file=sys.stderr)
        return 1
    asyncio.run(_run(tickers, since=args.since, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
