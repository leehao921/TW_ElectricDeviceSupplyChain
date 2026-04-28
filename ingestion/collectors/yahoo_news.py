"""Yahoo Taiwan stock news collector.

Scrapes `https://tw.stock.yahoo.com/quote/{ticker}.{suffix}/news` for a ticker
(suffix is `TW` for TWSE-listed, `TWO` for OTC — we try TW first, fall back
on 404). Parses listing + article pages with BeautifulSoup using robust
attribute-substring selectors because Yahoo rotates generated class names.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..ner import extract as ner_extract
from ..universe import all_tickers
from ._common import make_client, parse_relative_time, run_news_collector

SOURCE = "yahoo"
LISTING_URL = "https://tw.stock.yahoo.com/quote/{ticker}.{suffix}/news"
RATE_LIMIT_SECONDS = 1.0


@dataclass
class YahooNewsItem:
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


def parse_listing(html: str, base_url: str) -> list[dict]:
    """Extract (title, href, time_text) triples from a Yahoo listing page."""
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []
    seen: set[str] = set()

    # Prefer the robust selector, but fall back to any anchor pointing at /news/.
    anchors = soup.select('li[class*="Card"] a[href*="/news/"]')
    if not anchors:
        anchors = soup.select('a[href*="/news/"]')

    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href or href in seen:
            continue
        # Skip the navigation tab ("/news" or "/news/") and other non-article hrefs.
        # Real Yahoo article hrefs are shaped "/news/<slug>-<digits>.html".
        if not href.rstrip("/").split("/")[-1].endswith(".html"):
            continue
        title = (a.get_text(strip=True) or a.get("title") or "").strip()
        if not title or len(title) < 6:
            continue
        # Nearby <time> element (if present) gives us the relative or ISO stamp.
        time_text = ""
        time_el = a.find("time") or a.find_next("time")
        if time_el:
            time_text = (time_el.get("datetime") or time_el.get_text(strip=True) or "").strip()
        items.append({
            "title": title,
            "href": urljoin(base_url, href),
            "time_text": time_text,
        })
        seen.add(href)
    return items


def parse_article(html: str) -> str:
    """Extract the main text of a Yahoo article page as a single string."""
    soup = BeautifulSoup(html, "lxml")
    # Yahoo articles consistently wrap body copy in <article>; fall back to
    # concatenated <p> tags when the wrapper markup changes.
    article = soup.find("article")
    root = article if article else soup
    paragraphs = [p.get_text(" ", strip=True) for p in root.find_all("p")]
    return "\n".join(p for p in paragraphs if p)


async def _fetch_listing_html(client: httpx.AsyncClient, ticker: str) -> str | None:
    """Try .TW, fall back to .TWO on 404. Returns HTML or None if both fail."""
    for suffix in ("TW", "TWO"):
        url = LISTING_URL.format(ticker=ticker, suffix=suffix)
        resp = await client.get(url)
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        return resp.text
    return None


async def collect(
    ticker: str,
    *,
    limit: int = 20,
    client: httpx.AsyncClient | None = None,
) -> list[YahooNewsItem]:
    own_client = client is None
    client = client or make_client()
    try:
        listing_html = await _fetch_listing_html(client, ticker)
        if listing_html is None:
            return []
        base_url = LISTING_URL.format(ticker=ticker, suffix="TW")
        parsed = parse_listing(listing_html, base_url)[:limit]

        items: list[YahooNewsItem] = []
        for entry in parsed:
            await asyncio.sleep(RATE_LIMIT_SECONDS)
            try:
                article_resp = await client.get(entry["href"])
                article_resp.raise_for_status()
                body = parse_article(article_resp.text)
            except httpx.HTTPError as exc:
                print(f"  skip {entry['href']}: {exc}", file=sys.stderr)
                continue
            published = parse_relative_time(entry["time_text"]) or datetime.now(timezone.utc)
            items.append(YahooNewsItem(
                title=entry["title"],
                source_url=entry["href"],
                published_at=published,
                body=body,
            ))
        return items
    finally:
        if own_client:
            await client.aclose()


def _preview(it: YahooNewsItem) -> str:
    return f"  {it.published_at.isoformat()} | {it.title}\n    {it.source_url}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Yahoo 股市 news collector")
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

    async def _collect(ticker: str, client: httpx.AsyncClient) -> list[YahooNewsItem]:
        return await collect(ticker, limit=args.limit, client=client)

    asyncio.run(run_news_collector(
        SOURCE, tickers, _collect,
        dry_run=args.dry_run, format_preview=_preview,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
