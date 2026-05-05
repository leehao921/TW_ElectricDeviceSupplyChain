"""Re-run NER over existing news_items.tickers using the upgraded
ticker_set + name_map.

The original ingest used ``\\b\\d{4}\\b`` only — that matches random 4-digit
runs in body text (false positives) AND silently misses every article that
names a company without printing its ticker (silent loss). This script
fixes both for the rolling 90-day window so the signal layer can fire on
real spikes (4985 臻鼎-KY, etc.) immediately rather than waiting 90 days
for new ingestion to overwrite.

Usage (from inside the scheduler container):

    python3 scripts/renix_news_tickers.py [--days 90] [--dry-run]

Behavior:
- Selects news_items rows in the last ``--days`` days.
- Reruns ``ner.extract(text, ticker_set=..., name_map=...)`` on
  ``title + body``.
- Updates ``tickers`` on rows where the new tagging differs.
- Reports added/removed counts in aggregate.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Repo root on sys.path so this script runs from the container's /app workdir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingestion import db, ner
from ingestion.universe import electronics_tickers, name_to_ticker


async def run(days: int, dry_run: bool) -> int:
    pool = await db.get_pool()
    ticker_set = electronics_tickers()
    name_map = name_to_ticker()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, body, tickers
              FROM news_items
             WHERE published_at > NOW() - ($1::text || ' days')::interval
            """,
            str(int(days)),
        )

    print(f"[renix] scanning {len(rows)} rows over last {days} days")

    changed = 0
    added_total = 0
    removed_total = 0
    examples: list[tuple[int, list[str], list[str]]] = []

    async with pool.acquire() as conn:
        for r in rows:
            text = f"{r['title'] or ''}\n{r['body'] or ''}"
            new = ner.extract(text, ticker_set=ticker_set, name_map=name_map).tickers
            old = list(r["tickers"] or [])
            if sorted(new) == sorted(old):
                continue
            added = [t for t in new if t not in set(old)]
            removed = [t for t in old if t not in set(new)]
            added_total += len(added)
            removed_total += len(removed)
            if len(examples) < 8:
                examples.append((r["id"], added, removed))
            if not dry_run:
                await conn.execute(
                    "UPDATE news_items SET tickers = $1::text[] WHERE id = $2",
                    new, r["id"],
                )
            changed += 1

    print(f"[renix] rows changed: {changed}")
    print(f"[renix] tickers added: {added_total}, tickers removed: {removed_total}")
    print("[renix] examples (id, added, removed):")
    for ex in examples:
        print(f"  - {ex[0]}: +{ex[1]} -{ex[2]}")
    if dry_run:
        print("[renix] DRY-RUN — no rows updated")
    return changed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--days", type=int, default=90)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    return 0 if asyncio.run(run(args.days, args.dry_run)) >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
