"""Unit tests for RSS parsing + NER path (no DB, no network)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ingestion import ner
from ingestion.collectors import _rss_base

FIXTURE = Path(__file__).parent / "fixtures" / "rss_sample.xml"


def test_fixture_exists():
    assert FIXTURE.exists(), f"Fixture missing: {FIXTURE}"


def test_parse_feed_yields_entries():
    rows = list(_rss_base.parse_feed(FIXTURE.read_bytes()))
    assert len(rows) == 3
    urls = [r["source_url"] for r in rows]
    assert urls == [
        "https://example.com/news/1",
        "https://example.com/news/2",
        "https://example.com/news/3",
    ]


def test_parse_feed_extracts_tickers_and_wikilinks():
    rows = list(_rss_base.parse_feed(FIXTURE.read_bytes()))
    first = rows[0]
    assert "2330" in first["tickers"]
    # Wikilink dict in WIKILINKS.md contains CoWoS and HBM — both appear in title.
    assert "CoWoS" in first["wikilinks"]
    assert "HBM" in first["wikilinks"]


def test_parse_feed_irrelevant_entry_has_no_matches():
    rows = list(_rss_base.parse_feed(FIXTURE.read_bytes()))
    weather = rows[1]
    assert weather["tickers"] == []
    # Weather entry contains no known proper nouns from WIKILINKS.md.
    assert weather["wikilinks"] == []


def test_parse_feed_published_at_utc():
    rows = list(_rss_base.parse_feed(FIXTURE.read_bytes()))
    # pubDate is "Mon, 21 Apr 2026 06:00:00 GMT" — must parse to aware UTC.
    published = rows[0]["published_at"]
    assert published.tzinfo is not None
    assert published.year == 2026 and published.month == 4 and published.day == 21
    assert published.hour == 6


def test_ner_ticker_regex_rejects_embedded_digits():
    # "12345" should not yield a 4-digit ticker; "2330" standalone should.
    assert ner.extract("code 12345 is long").tickers == []
    assert ner.extract("see 2330").tickers == ["2330"]


def test_ingest_rss_dry_run_no_db(monkeypatch, capsys):
    """--dry-run path should never hit the DB."""
    import asyncio

    async def fake_fetch(url: str) -> bytes:
        return FIXTURE.read_bytes()

    monkeypatch.setattr(_rss_base, "_fetch_feed_bytes", fake_fetch)

    def boom(*a, **kw):
        raise AssertionError("dry-run must not touch db.get_pool")

    from ingestion import db
    monkeypatch.setattr(db, "get_pool", boom)

    rows_written = asyncio.run(
        _rss_base.ingest_rss("test", "http://ignored", dry_run=True, limit=10)
    )
    assert rows_written == 0
    out = capsys.readouterr().out
    # Relevant entries (1 and 3) should be printed; weather (2) filtered out.
    assert "example.com/news/1" in out
    assert "example.com/news/3" in out
    assert "example.com/news/2" not in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
