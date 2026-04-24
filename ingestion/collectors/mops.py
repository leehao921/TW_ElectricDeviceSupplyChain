"""MOPS 重大訊息 collector.

Scrapes the "current day material information" JSON API backing the MOPS SPA
(https://mops.twse.com.tw/mops/api/t05st02) across a rolling date window,
fetches per-disclosure detail for the body text, filters to the electronics
ticker universe, and upserts into the `mops_disclosures` table keyed by
source_url.

CLI: ``python3 -m ingestion.collectors.mops --since 7d --limit 100``
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

import httpx

from ..db import connect, log_run
from ..universe import electronics_tickers

LOGGER = logging.getLogger("ingestion.collectors.mops")

API_BASE = "https://mops.twse.com.tw/mops/api"
LIST_ENDPOINT = f"{API_BASE}/t05st02"
DETAIL_ENDPOINT = f"{API_BASE}/t05st02_detail"
DETAIL_VIEW_URL = "https://mops.twse.com.tw/mops/#/web/t05st02"

# Conservative 2 req/s rate limit shared between list + detail calls.
REQUEST_INTERVAL_SEC = 0.5

# Taipei is UTC+8 with no DST; MOPS returns ROC-year dates without a zone.
TAIPEI_TZ = timezone(timedelta(hours=8))

_SINCE_RE = re.compile(r"^(\d+)\s*d$", re.IGNORECASE)


@dataclass(frozen=True)
class Disclosure:
    ticker: str
    disclosure_ts: datetime
    category: Optional[str]
    subject: str
    body: Optional[str]
    source_url: str


# --- parsing helpers ---------------------------------------------------------


def parse_since(value: str) -> int:
    """Parse a ``--since`` value like ``7d`` into an integer day count."""
    m = _SINCE_RE.match(value.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f"--since must look like '7d' or '1d', got {value!r}"
        )
    days = int(m.group(1))
    if days <= 0:
        raise argparse.ArgumentTypeError("--since must be a positive number of days")
    return days


def roc_to_iso_date(roc: str) -> date:
    """Convert ROC-calendar date string ``'115/04/22'`` -> ``date(2026, 4, 22)``."""
    y, m, d = roc.split("/")
    return date(int(y) + 1911, int(m), int(d))


def parse_disclosure_ts(roc_date: str, hhmmss: str) -> datetime:
    """Combine MOPS ``'115/04/22'`` + ``'17:32:32'`` into a timezone-aware UTC datetime."""
    iso_date = roc_to_iso_date(roc_date)
    hh, mm, ss = (int(p) for p in hhmmss.split(":"))
    local = datetime(iso_date.year, iso_date.month, iso_date.day, hh, mm, ss, tzinfo=TAIPEI_TZ)
    return local.astimezone(timezone.utc)


def build_source_url(company_id: str, market_kind: str, enter_date: str, serial: int) -> str:
    """Canonical, stable URL per disclosure (used as DB unique key)."""
    return (
        f"{DETAIL_VIEW_URL}?companyId={company_id}"
        f"&marketKind={market_kind}&enterDate={enter_date}&serialNumber={serial}"
    )


def iter_list_rows(payload: dict) -> Iterable[list]:
    """Yield raw disclosure rows from a t05st02 response, tolerating empty results."""
    result = payload.get("result") or {}
    for row in result.get("data") or []:
        yield row


def parse_list_row(
    row: Sequence,
    *,
    allowed_tickers: Optional[frozenset] = None,
) -> Optional[Disclosure]:
    """Turn a raw list row into a ``Disclosure`` (no body yet), or None to skip."""
    if len(row) < 6 or not isinstance(row[5], dict):
        return None
    ticker = str(row[2]).strip()
    if allowed_tickers is not None and ticker not in allowed_tickers:
        return None
    params = row[5].get("parameters") or {}
    enter_date = params.get("enterDate")
    serial = params.get("serialNumber")
    market_kind = params.get("marketKind", "")
    if not (enter_date and serial is not None):
        return None
    return Disclosure(
        ticker=ticker,
        disclosure_ts=parse_disclosure_ts(str(row[0]), str(row[1])),
        category=None,
        subject=str(row[4]).strip(),
        body=None,
        source_url=build_source_url(ticker, market_kind, str(enter_date), int(serial)),
    )


def extract_detail_fields(payload: dict) -> tuple[Optional[str], Optional[str]]:
    """Return ``(category, body)`` from a t05st02_detail response.

    Detail row layout is:
        [serial, date_roc, time, spokesman, title, phone, subject, clause,
         event_date, description]
    """
    result = payload.get("result") or {}
    rows = result.get("data") or []
    if not rows:
        return None, None
    row = rows[0]
    clause = str(row[7]).strip() if len(row) >= 8 and row[7] is not None else None
    body = str(row[9]).strip() if len(row) >= 10 and row[9] is not None else None
    return clause, body


# --- HTTP + orchestration ----------------------------------------------------


def _client_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
        "Origin": "https://mops.twse.com.tw",
        "Referer": "https://mops.twse.com.tw/mops/",
    }


def iter_recent_dates(days: int, *, today: Optional[date] = None) -> Iterable[date]:
    """Yield dates from oldest to newest over the last ``days`` window."""
    anchor = today or datetime.now(TAIPEI_TZ).date()
    for offset in range(days - 1, -1, -1):
        yield anchor - timedelta(days=offset)


async def _post_json(client: httpx.AsyncClient, url: str, body: dict) -> dict:
    r = await client.post(url, json=body, headers=_client_headers(), timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200:
        LOGGER.debug("non-200 MOPS payload for %s %s: %s", url, body, data.get("message"))
    return data


async def fetch_list(client: httpx.AsyncClient, day: date) -> dict:
    """Fetch the full disclosure list for a given ROC day."""
    body = {"year": str(day.year - 1911), "month": str(day.month), "day": str(day.day)}
    return await _post_json(client, LIST_ENDPOINT, body)


async def fetch_detail(client: httpx.AsyncClient, disclosure: Disclosure) -> dict:
    """Fetch the detail row for a disclosure, re-derived from its source URL params."""
    params = _parse_source_url_params(disclosure.source_url)
    return await _post_json(client, DETAIL_ENDPOINT, params)


def _parse_source_url_params(url: str) -> dict:
    """Extract the detail-API body from a disclosure source URL."""
    query = url.split("?", 1)[1] if "?" in url else ""
    parts = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
    return {
        "companyId": parts.get("companyId", ""),
        "marketKind": parts.get("marketKind", ""),
        "enterDate": parts.get("enterDate", ""),
        "serialNumber": int(parts.get("serialNumber", "0")),
    }


async def collect(
    *,
    since_days: int,
    limit: Optional[int],
    dry_run: bool,
    allowed_tickers: Optional[frozenset] = None,
) -> list[Disclosure]:
    """Fetch, enrich, and (unless dry_run) persist disclosures. Returns the list."""
    if allowed_tickers is None:
        allowed_tickers = electronics_tickers()

    disclosures: list[Disclosure] = []
    async with httpx.AsyncClient() as client:
        for day in iter_recent_dates(since_days):
            try:
                payload = await fetch_list(client, day)
            except httpx.HTTPError as exc:
                LOGGER.warning("MOPS list fetch failed for %s: %s", day, exc)
                await asyncio.sleep(REQUEST_INTERVAL_SEC)
                continue

            for row in iter_list_rows(payload):
                parsed = parse_list_row(row, allowed_tickers=allowed_tickers)
                if parsed is not None:
                    disclosures.append(parsed)
                    if limit is not None and len(disclosures) >= limit:
                        break
            await asyncio.sleep(REQUEST_INTERVAL_SEC)
            if limit is not None and len(disclosures) >= limit:
                break

        enriched: list[Disclosure] = []
        for d in disclosures:
            try:
                detail = await fetch_detail(client, d)
                category, body = extract_detail_fields(detail)
                enriched.append(
                    Disclosure(
                        ticker=d.ticker,
                        disclosure_ts=d.disclosure_ts,
                        category=category,
                        subject=d.subject,
                        body=body,
                        source_url=d.source_url,
                    )
                )
            except httpx.HTTPError as exc:
                LOGGER.warning("MOPS detail fetch failed for %s: %s", d.source_url, exc)
                enriched.append(d)
            await asyncio.sleep(REQUEST_INTERVAL_SEC)

    if dry_run:
        for d in enriched:
            print(
                f"{d.disclosure_ts.isoformat()}  {d.ticker}  "
                f"[{d.category or '-'}]  {d.subject[:60]}"
            )
        return enriched

    rows_written = await _write_disclosures(enriched)
    status = "ok" if rows_written == len(enriched) else "partial" if rows_written else "fail"
    await log_run("mops", status, rows_written)
    LOGGER.info("MOPS collector wrote %d/%d rows", rows_written, len(enriched))
    return enriched


async def _write_disclosures(items: Sequence[Disclosure]) -> int:
    if not items:
        return 0
    conn = await connect()
    try:
        rows = [
            (d.ticker, d.disclosure_ts, d.category, d.subject, d.body, d.source_url)
            for d in items
        ]
        # executemany on an UPSERT returns no row count, so we count explicitly.
        written = 0
        for row in rows:
            result = await conn.execute(
                """
                INSERT INTO mops_disclosures
                    (ticker, disclosure_ts, category, subject, body, source_url)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (source_url) DO NOTHING
                """,
                *row,
            )
            if result.endswith(" 1"):
                written += 1
        return written
    finally:
        await conn.close()


# --- CLI ---------------------------------------------------------------------


def build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m ingestion.collectors.mops",
        description="Ingest MOPS 重大訊息 for electronics tickers.",
    )
    parser.add_argument("--since", type=parse_since, default=7,
                        help="Lookback window, e.g. 7d (default) or 1d.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and print rows without writing to the database.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum rows to process.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_argparser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(collect(since_days=args.since, limit=args.limit, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
