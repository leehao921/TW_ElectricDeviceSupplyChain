"""Database maintenance helpers — VACUUM, run-log cleanup, freshness check.

Wired into ``ingestion.scheduler`` via ``ingestion.jobs``. Each helper is async
and returns an ``int`` so the scheduler logs ``rows_written`` correctly.

- :func:`vacuum_analyze` runs ``VACUUM (ANALYZE)`` on the user-content tables.
  pgvector indexes can drift after heavy upsert traffic; weekly is fine.
- :func:`cleanup_ingest_runs` deletes ``ingest_runs`` older than ``days``
  (default 90) so the table doesn't grow unbounded.
- :func:`freshness_check` flags news sources that haven't ingested in >24h.
  Surfaces silent collector failures by writing a ``status='warn'`` row.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import db

LOGGER = logging.getLogger("ingestion.maintenance")

STALE_HOURS = 24


async def vacuum_analyze() -> int:
    """VACUUM (ANALYZE) the high-churn tables. Returns 0 (no rows written)."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        # asyncpg auto-wraps each ``execute`` in an implicit txn, but VACUUM
        # cannot run inside one. ``acquire`` gives us a connection where we
        # explicitly ``COMMIT`` before vacuuming, then drop back to default.
        await conn.execute("COMMIT")  # close the implicit txn if any
        for tbl in ("news_items", "mops_disclosures", "ingest_runs", "finmind_fundamentals"):
            try:
                await conn.execute(f"VACUUM (ANALYZE) {tbl}")
                LOGGER.info("vacuumed %s", tbl)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("VACUUM %s failed: %s", tbl, exc)
    return 0


async def cleanup_ingest_runs(days: int = 90) -> int:
    """Delete ``ingest_runs`` rows older than ``days``. Returns rows deleted."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM ingest_runs WHERE finished_at < now() - "
            f"interval '{int(days)} days'"
        )
    parts = result.split() if result else []
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0


async def freshness_check() -> int:
    """Flag sources with no rows in the last :data:`STALE_HOURS`.

    Returns the count of stale sources. When non-zero, also writes a
    ``status='warn'`` row to ``ingest_runs`` so the alert surfaces in the
    same query path operators already use to spot job failures.
    """
    pool = await db.get_pool()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_HOURS)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT source, max(ingested_at) AS last_seen
              FROM news_items GROUP BY source
            """
        )
    stale: list[str] = [
        r["source"] for r in rows
        if r["last_seen"] is not None and r["last_seen"] < cutoff
    ]
    if stale:
        LOGGER.warning("stale news sources: %s", stale)
        await db.log_run(
            "freshness_check",
            "warn",
            len(stale),
            error=f"stale sources >{STALE_HOURS}h: {','.join(stale)}",
        )
    return len(stale)
