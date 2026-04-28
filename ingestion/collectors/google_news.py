"""Google News RSS collector (per ticker).

Queries `https://news.google.com/rss/search?q=<ticker>+<company_name>` with
Traditional-Chinese locale and parses the RSS feed via feedparser. Writes to
`news_items` with source='google'.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import httpx

from ..ner import extract as ner_extract
from ..universe import all_tickers, ticker_name
from ._common import make_client, run_news_collector

SOURCE = "google"
FEED_URL = (
    "https://news.google.com/rss/search?q={query}"
    "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)


@dataclass
class GoogleNewsItem:
    title: str
    source_url: str
    published_at: datetime
    body: str

    def as_row(self) -> dict:
        ner = ner_extract(f"{self.title}\n{self.body}")
        return {
            "source_url": self.source_url,
            "published_at": self.published_at,
            "title": self.title,
            "body": self.body,
            "tickers": ner.tickers,
            "wikilinks": ner.wikilinks,
        }


def build_feed_url(ticker: str, company_name: str | None) -> str:
    terms = [ticker]
    if company_name:
        terms.append(company_name)
    return FEED_URL.format(query=quote_plus(" ".join(terms)))


def _entry_published(entry) -> datetime:
    """feedparser gives us a UTC struct_time in `published_parsed` when it can
    read the date; fall back to now() so the row still satisfies NOT NULL."""
    tm = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tm is None:
        return datetime.now(timezone.utc)
    return datetime(*tm[:6], tzinfo=timezone.utc)


def parse_feed(xml_bytes: bytes, *, limit: int) -> list[GoogleNewsItem]:
    parsed = feedparser.parse(xml_bytes)
    items: list[GoogleNewsItem] = []
    for entry in parsed.entries[:limit]:
        link = (getattr(entry, "link", "") or "").strip()
        title = (getattr(entry, "title", "") or "").strip()
        if not link or not title:
            continue
        items.append(GoogleNewsItem(
            title=title,
            source_url=link,
            published_at=_entry_published(entry),
            body=(getattr(entry, "summary", "") or "").strip(),
        ))
    return items


async def collect(
    ticker: str,
    *,
    limit: int = 20,
    client: httpx.AsyncClient | None = None,
) -> list[GoogleNewsItem]:
    url = build_feed_url(ticker, ticker_name(ticker))
    own_client = client is None
    client = client or make_client()
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return parse_feed(resp.content, limit=limit)
    finally:
        if own_client:
            await client.aclose()


def _preview(it: GoogleNewsItem) -> str:
    return f"  {it.published_at.isoformat()} | {it.title}\n    {it.source_url}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Google News RSS collector")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticker", help="4-digit ticker, e.g. 2330")
    group.add_argument("--all", action="store_true", help="iterate every electronics ticker")
    parser.add_argument("--dry-run", action="store_true", help="parse + print; no DB write")
    parser.add_argument("--limit", type=int, default=20, help="max items per ticker")
    args = parser.parse_args(argv)

    tickers = all_tickers() if args.all else [args.ticker]
    if not tickers:
        print("no tickers to process", file=sys.stderr)
        return 1

    async def _collect(ticker: str, client: httpx.AsyncClient) -> list[GoogleNewsItem]:
        return await collect(ticker, limit=args.limit, client=client)

    asyncio.run(run_news_collector(
        SOURCE, tickers, _collect,
        dry_run=args.dry_run, format_preview=_preview,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
