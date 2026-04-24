"""Smoke tests for the migration runner.

These tests do not require a running Postgres — they only validate that the
bundled SQL file exists, is non-empty, and contains the expected DDL.
"""

from pathlib import Path

MIGRATION_FILE = Path(__file__).parent / "001_init.sql"


def test_migration_file_exists():
    assert MIGRATION_FILE.exists(), f"missing migration file: {MIGRATION_FILE}"


def test_migration_file_not_empty():
    assert MIGRATION_FILE.stat().st_size > 0, "migration file is empty"


def test_migration_contains_news_items_table():
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS news_items" in sql


def test_migration_contains_all_four_tables():
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    for table in ("news_items", "mops_disclosures", "finmind_fundamentals", "ingest_runs"):
        assert table in sql, f"migration missing table: {table}"


def test_migration_enables_pgvector():
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
