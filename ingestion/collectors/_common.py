"""Shared helpers for Unit 5 collectors.

Kept tiny on purpose: relative-time parsing, news_items upsert, and the
per-ticker driver that Yahoo/Google share.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Iterable

import asyncpg
import httpx

from ..config import USER_AGENT
from ..db import close_pool, get_pool

_REL_UNITS = {
    "秒": "seconds", "分鐘": "minutes", "分": "minutes",
    "小時": "hours", "天": "days", "日": "days", "週": "weeks", "周": "weeks",
    "month": "months_approx", "月": "months_approx",
    "year": "years_approx", "年": "years_approx",
}

_REL_RE = re.compile(
    r"(?P<num>\d+)\s*(?P<unit>秒|分鐘|分|小時|天|日|週|周|月|年|"
    r"seconds?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)\s*(?:前|ago)?",
    re.IGNORECASE,
)


def parse_relative_time(text: str, *, now: datetime | None = None) -> datetime | None:
    """Normalize strings like '3小時前' or '2 days ago' to a UTC datetime.

    Returns None if the string can't be parsed — callers should fall back to
    their source's absolute timestamp field.
    """
    if not text:
        return None
    now = now or datetime.now(timezone.utc)
    text = text.strip()

    try:
        # ISO/RFC dates — pandas-free parse via fromisoformat; callers can also
        # pass a feedparser-provided struct_time and bypass this helper.
        if "T" in text or re.match(r"^\d{4}-\d{2}-\d{2}", text):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass

    m = _REL_RE.search(text)
    if not m:
        return None
    num = int(m.group("num"))
    unit = m.group("unit").lower()

    # Map English plurals/shorthand onto the Chinese table above.
    english = {
        "second": "seconds", "seconds": "seconds",
        "min": "minutes", "mins": "minutes", "minute": "minutes", "minutes": "minutes",
        "hour": "hours", "hours": "hours", "hr": "hours", "hrs": "hours",
        "day": "days", "days": "days",
        "week": "weeks", "weeks": "weeks",
        "month": "months_approx", "months": "months_approx",
        "year": "years_approx", "years": "years_approx",
    }
    kind = english.get(unit) or _REL_UNITS.get(unit)
    if kind is None:
        return None

    if kind == "months_approx":
        return now - timedelta(days=30 * num)
    if kind == "years_approx":
        return now - timedelta(days=365 * num)
    return now - timedelta(**{kind: num})


INSERT_NEWS_SQL = """
INSERT INTO news_items (source, source_url, published_at, title, body, tickers, wikilinks)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (source_url) DO NOTHING
"""


async def insert_news_rows(
    pool: asyncpg.Pool,
    source: str,
    rows: Iterable[dict],
) -> int:
    """Bulk-insert parsed news rows. Returns the input count (asyncpg's
    executemany can't distinguish inserted vs. skipped on ON CONFLICT)."""
    rows = list(rows)
    if not rows:
        return 0
    async with pool.acquire() as conn:
        await conn.executemany(
            INSERT_NEWS_SQL,
            [
                (
                    source,
                    r["source_url"],
                    r["published_at"],
                    r["title"],
                    r.get("body") or "",
                    r.get("tickers") or [],
                    r.get("wikilinks") or [],
                )
                for r in rows
            ],
        )
    return len(rows)


def make_client() -> httpx.AsyncClient:
    """Uniform httpx client config shared by all collectors."""
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    )


async def run_news_collector(
    source: str,
    tickers: Iterable[str],
    collect_fn: Callable[[str, httpx.AsyncClient], Awaitable[list[Any]]],
    *,
    dry_run: bool,
    format_preview: Callable[[Any], str] | None = None,
) -> None:
    """Driver for Yahoo/Google style news collectors.

    `collect_fn(ticker, client)` must return a list of items. Each item must
    expose `.as_row()` (for DB writes) and ideally str() nicely for dry-run.
    """
    preview = format_preview or (lambda it: str(it))
    async with make_client() as client:
        for ticker in tickers:
            print(f"[{source}] {ticker}")
            items = await collect_fn(ticker, client)
            if dry_run:
                for it in items:
                    print(preview(it))
                continue
            pool = await get_pool()
            written = await insert_news_rows(pool, source, (it.as_row() for it in items))
            print(f"  wrote {written} rows")
    if not dry_run:
        await close_pool()
