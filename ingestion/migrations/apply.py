"""Apply Postgres migrations for the tw_electronics database.

Creates the target database (if missing) on the admin connection, then runs
the SQL migration file against it. Prints the tables in the public schema
after applying, mimicking psql's ``\\dt`` output.

Usage:
    python -m ingestion.migrations.apply [--target-db <name>]

Env vars:
    PG_ADMIN_DSN  - DSN for an admin DB (default ``postgres``) used for
                    ``CREATE DATABASE``. Defaults to
                    postgresql://knowledge:knowledge@localhost:5433/postgres
    PG_NEWS_DSN   - DSN for the target DB where the migration runs. Defaults
                    to postgresql://knowledge:knowledge@localhost:5433/tw_electronics
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import asyncpg

DEFAULT_ADMIN_DSN = "postgresql://knowledge:knowledge@localhost:5433/postgres"
DEFAULT_NEWS_DSN = "postgresql://knowledge:knowledge@localhost:5433/tw_electronics"
MIGRATIONS_DIR = Path(__file__).parent
MIGRATION_FILE = MIGRATIONS_DIR / "001_init.sql"  # kept for tests/back-compat


def _replace_dsn_db(dsn: str, db_name: str) -> str:
    """Return ``dsn`` with its path component replaced by ``db_name``."""
    parsed = urlparse(dsn)
    return urlunparse(parsed._replace(path=f"/{db_name}"))


async def _ensure_database(admin_dsn: str, db_name: str) -> bool:
    """Create ``db_name`` via ``admin_dsn`` if it does not exist. Returns True if created."""
    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if exists:
            return False
        # Identifier must be safely quoted; asyncpg does not parameterize DDL.
        quoted = '"' + db_name.replace('"', '""') + '"'
        await conn.execute(f"CREATE DATABASE {quoted}")
        return True
    finally:
        await conn.close()


def _discover_migrations() -> list[Path]:
    """Return all ``NNN_*.sql`` files in MIGRATIONS_DIR, ordered by filename."""
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


async def _apply_migration(dsn: str, sql_files: list[Path]) -> list[str]:
    """Run each SQL file in order against ``dsn``; return public-schema tables."""
    conn = await asyncpg.connect(dsn)
    try:
        for path in sql_files:
            await conn.execute(path.read_text(encoding="utf-8"))
            print(f"[apply]   - {path.name}")
        rows = await conn.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """
        )
        return [r["tablename"] for r in rows]
    finally:
        await conn.close()


async def run(target_db: str, admin_dsn: str, news_dsn: str) -> int:
    # Make sure the news DSN actually points at ``target_db`` so a ``--target-db``
    # override is honoured even when PG_NEWS_DSN was set for a different DB.
    news_dsn = _replace_dsn_db(news_dsn, target_db)

    created = await _ensure_database(admin_dsn, target_db)
    print(f"[apply] database {target_db!r}: {'created' if created else 'exists'}")

    sql_files = _discover_migrations()
    if not sql_files:
        print(f"[apply] ERROR: no migration files in {MIGRATIONS_DIR}", file=sys.stderr)
        return 1

    print(f"[apply] applying {len(sql_files)} migration(s):")
    tables = await _apply_migration(news_dsn, sql_files)
    print("[apply] tables in public schema:")
    for t in tables:
        print(f"  - {t}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Postgres migrations for the tw_electronics database.")
    parser.add_argument(
        "--target-db",
        default=None,
        help="Override the target database name (default: derived from PG_NEWS_DSN or 'tw_electronics').",
    )
    args = parser.parse_args(argv)

    admin_dsn = os.environ.get("PG_ADMIN_DSN", DEFAULT_ADMIN_DSN)
    news_dsn = os.environ.get("PG_NEWS_DSN", DEFAULT_NEWS_DSN)

    if args.target_db:
        target_db = args.target_db
    else:
        parsed = urlparse(news_dsn)
        target_db = (parsed.path.lstrip("/") or "tw_electronics")

    return asyncio.run(run(target_db, admin_dsn, news_dsn))


if __name__ == "__main__":
    raise SystemExit(main())
