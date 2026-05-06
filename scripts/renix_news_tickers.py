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
    wikilink_vocab = ner.load_wikilink_vocab()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, body, tickers, wikilinks
              FROM news_items
             WHERE published_at > NOW() - ($1::text || ' days')::interval
            """,
            str(int(days)),
        )

    print(f"[renix] scanning {len(rows)} rows over last {days} days")
    print(f"[renix] vocab sizes: tickers={len(ticker_set)}, "
          f"name_map={len(name_map)}, wikilink_vocab={len(wikilink_vocab)}")

    changed = 0
    added_t = 0
    removed_t = 0
    added_w = 0
    removed_w = 0
    examples: list[tuple[int, list[str], list[str], list[str], list[str]]] = []

    async with pool.acquire() as conn:
        for r in rows:
            text = f"{r['title'] or ''}\n{r['body'] or ''}"
            res = ner.extract(text, ticker_set=ticker_set,
                              name_map=name_map,
                              wikilink_vocab=wikilink_vocab)
            new_t = res.tickers
            new_w = res.wikilinks
            old_t = list(r["tickers"] or [])
            old_w = list(r["wikilinks"] or [])
            if sorted(new_t) == sorted(old_t) and sorted(new_w) == sorted(old_w):
                continue
            ad_t = [x for x in new_t if x not in set(old_t)]
            rm_t = [x for x in old_t if x not in set(new_t)]
            ad_w = [x for x in new_w if x not in set(old_w)]
            rm_w = [x for x in old_w if x not in set(new_w)]
            added_t += len(ad_t)
            removed_t += len(rm_t)
            added_w += len(ad_w)
            removed_w += len(rm_w)
            if len(examples) < 6:
                examples.append((r["id"], ad_t, rm_t, ad_w[:5], rm_w[:5]))
            if not dry_run:
                await conn.execute(
                    "UPDATE news_items SET tickers = $1::text[], wikilinks = $2::text[] WHERE id = $3",
                    new_t, new_w, r["id"],
                )
            changed += 1

    print(f"[renix] rows changed: {changed}")
    print(f"[renix] tickers   added={added_t}, removed={removed_t}")
    print(f"[renix] wikilinks added={added_w}, removed={removed_w}")
    print("[renix] examples (id, +tickers, -tickers, +wlinks_top5, -wlinks_top5):")
    for ex in examples:
        print(f"  - {ex[0]}: t+{ex[1]} t-{ex[2]} w+{ex[3]} w-{ex[4]}")
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
