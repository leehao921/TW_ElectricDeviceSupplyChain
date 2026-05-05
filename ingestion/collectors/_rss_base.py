"""Shared RSS collector logic.

Thin wrappers in ``rss_cna.py`` / ``rss_udn.py`` / ``rss_ctee.py`` call
``ingest_rss(source, feed_url, dry_run=..., limit=...)`` which:

1. Fetches the feed (httpx) and parses it (feedparser).
2. For each entry, runs NER over ``title + body`` and skips entries with zero
   tickers AND zero wikilinks.
3. Embeds ``title + body[:2000]`` via ``ingestion.db.embed`` (NULL on error).
4. INSERTs into ``news_items`` with ``ON CONFLICT (source_url) DO NOTHING``.
5. Calls ``log_run(source, status, rows_written)``.

CLI helper ``build_arg_parser`` wires ``--dry-run / --limit / --url``.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from calendar import timegm
from datetime import datetime, timezone
from typing import Iterable, Optional

import feedparser
import httpx

from .. import db, ner
from ..universe import electronics_tickers, name_to_ticker

INSERT_SQL = """
INSERT INTO news_items (source, source_url, published_at, title, body, tickers, wikilinks, embedding)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector)
ON CONFLICT (source_url) DO NOTHING
"""

HTTP_TIMEOUT = 20.0
# Browser-like UA: some sources (e.g. CTEE behind Cloudflare) 403 bot-shaped UAs.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
EMBED_BODY_LIMIT = 2000


def build_arg_parser(source: str, default_url: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=f"RSS collector for {source}")
    p.add_argument("--dry-run", action="store_true", help="Parse & report only, no DB write")
    p.add_argument("--limit", type=int, default=50, help="Max items to process")
    p.add_argument("--url", default=default_url, help="Override feed URL (for testing)")
    return p


def _parse_published_at(entry) -> datetime:
    struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if struct is not None:
        return datetime.fromtimestamp(timegm(struct), tz=timezone.utc)
    return datetime.now(tz=timezone.utc)


def _extract_body(entry) -> str:
    content = getattr(entry, "content", None)
    if content:
        try:
            return content[0].get("value", "") or ""
        except (AttributeError, IndexError, TypeError):
            pass
    return getattr(entry, "summary", "") or getattr(entry, "description", "") or ""


async def _fetch_feed_bytes(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return resp.content


def parse_feed(raw: bytes) -> Iterable[dict]:
    """Parse feed bytes and yield normalized row dicts (without embedding/DB work)."""
    parsed = feedparser.parse(raw)
    for entry in parsed.entries:
        title = (getattr(entry, "title", "") or "").strip()
        if not title:
            continue
        source_url = (getattr(entry, "link", "") or "").strip()
        if not source_url:
            continue
        body = _extract_body(entry)
        text = f"{title}\n{body}"
        ner_result = ner.extract(
            text,
            ticker_set=electronics_tickers(),
            name_map=name_to_ticker(),
        )
        yield {
            "title": title,
            "body": body,
            "source_url": source_url,
            "published_at": _parse_published_at(entry),
            "tickers": ner_result.tickers,
            "wikilinks": ner_result.wikilinks,
        }


async def _embed_or_none(text: str) -> Optional[list[float]]:
    try:
        return await db.embed(text)
    except Exception as exc:
        print(f"[embed] failed, inserting NULL: {exc}", file=sys.stderr)
        return None


async def ingest_rss(source: str, feed_url: str, *, dry_run: bool, limit: int) -> int:
    """Fetch, filter, embed, insert. Returns rows_written (0 on dry-run).

    Status logging is the SCHEDULER's responsibility (see
    ``ingestion.scheduler._run_job_async``). This function just returns the
    row count or raises — the wrapper writes ``ingest_runs``. Letting the
    inner write its own row produced confusing duplicate entries
    (``cna`` + ``rss_cna``) and racy double-writes.
    """
    raw = await _fetch_feed_bytes(feed_url)

    relevant: list[dict] = []
    skipped = 0
    for row in parse_feed(raw):
        if limit and len(relevant) >= limit:
            break
        if not row["tickers"] and not row["wikilinks"]:
            skipped += 1
            continue
        relevant.append(row)

    print(
        f"[{source}] parsed: kept={len(relevant)} skipped_no_match={skipped} limit={limit}",
        file=sys.stderr,
    )

    if dry_run:
        for r in relevant:
            print(
                f"- {r['published_at'].isoformat()} | tickers={r['tickers']} wikilinks={r['wikilinks']} | {r['title']}\n  {r['source_url']}"
            )
        return 0

    rows_written = 0
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        for row in relevant:
            embedding = await _embed_or_none(row["title"] + "\n" + row["body"][:EMBED_BODY_LIMIT])
            result = await conn.execute(
                INSERT_SQL,
                source,
                row["source_url"],
                row["published_at"],
                row["title"],
                row["body"],
                row["tickers"],
                row["wikilinks"],
                db.vector_literal(embedding),
            )
            # asyncpg returns "INSERT 0 N" — 0 when ON CONFLICT skipped.
            if result.endswith(" 1"):
                rows_written += 1

    print(f"[{source}] inserted={rows_written}", file=sys.stderr)
    return rows_written


def run_cli(source: str, default_url: str) -> None:
    args = build_arg_parser(source, default_url).parse_args()
    asyncio.run(ingest_rss(source, args.url, dry_run=args.dry_run, limit=args.limit))
