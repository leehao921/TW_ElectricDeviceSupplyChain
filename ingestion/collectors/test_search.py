"""Unit tests for Unit 5 collectors (Yahoo/Google News/FinMind).

Uses saved HTML/XML/JSON fixtures under ./fixtures/. Runs without network
or Postgres. Execute with:

    python3 -m unittest ingestion.collectors.test_search -v
"""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from . import finmind, google_news, yahoo_news
from ._common import parse_relative_time

FIXTURES = Path(__file__).parent / "fixtures"


def _load_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _load_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class RelativeTimeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2024, 11, 15, 12, 0, tzinfo=timezone.utc)

    def test_chinese_hours(self):
        result = parse_relative_time("3小時前", now=self.now)
        self.assertEqual(result, datetime(2024, 11, 15, 9, 0, tzinfo=timezone.utc))

    def test_chinese_days(self):
        result = parse_relative_time("2天前", now=self.now)
        self.assertEqual(result, datetime(2024, 11, 13, 12, 0, tzinfo=timezone.utc))

    def test_english_hours(self):
        result = parse_relative_time("5 hours ago", now=self.now)
        self.assertEqual(result, datetime(2024, 11, 15, 7, 0, tzinfo=timezone.utc))

    def test_iso_date_passthrough(self):
        result = parse_relative_time("2024-11-15T02:00:00+00:00")
        self.assertEqual(result, datetime(2024, 11, 15, 2, 0, tzinfo=timezone.utc))

    def test_unparseable_returns_none(self):
        self.assertIsNone(parse_relative_time("recently"))
        self.assertIsNone(parse_relative_time(""))


class YahooListingTests(unittest.TestCase):
    def test_parses_three_items(self):
        html = _load_text("yahoo_listing.html")
        items = yahoo_news.parse_listing(html, "https://tw.stock.yahoo.com/")
        self.assertEqual(len(items), 3)
        # Titles are plain text (no surrounding whitespace or <time> leakage).
        for it in items:
            self.assertTrue(it["title"])
            self.assertTrue(it["href"].startswith("https://"))
        self.assertIn("台積電", items[0]["title"])

    def test_time_text_captured(self):
        html = _load_text("yahoo_listing.html")
        items = yahoo_news.parse_listing(html, "https://tw.stock.yahoo.com/")
        times = [it["time_text"] for it in items]
        self.assertIn("3小時前", times)
        self.assertTrue(any(t.startswith("2024-11-15") for t in times))

    def test_deduplicates_repeated_hrefs(self):
        html = (
            '<a href="/news/dup-story-112233.html">Same article once</a>'
            '<a href="/news/dup-story-112233.html">Same article twice</a>'
        )
        items = yahoo_news.parse_listing(html, "https://tw.stock.yahoo.com/")
        self.assertEqual(len(items), 1)

    def test_skips_navigation_tab(self):
        # Yahoo renders its "news" tab as <a href="/news/">新聞</a>; that must
        # never end up in the scraped items.
        html = '<a href="/quote/2330.TW/news/">新聞</a><a href="/news/real-442211.html">真 新聞 標題</a>'
        items = yahoo_news.parse_listing(html, "https://tw.stock.yahoo.com/")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "真 新聞 標題")


class YahooArticleTests(unittest.TestCase):
    def test_body_extracts_paragraphs(self):
        html = _load_text("yahoo_article.html")
        body = yahoo_news.parse_article(html)
        self.assertIn("CoWoS", body)
        self.assertIn("NVIDIA", body)
        # Header and footer are outside <article>, so they must not leak in.
        self.assertNotIn("site header", body)
        self.assertNotIn("footer text", body)
        # Empty <p></p> should not produce a blank line.
        self.assertNotIn("\n\n", body)

    def test_fallback_when_no_article_tag(self):
        html = "<html><body><p>hello</p><p>world</p></body></html>"
        self.assertEqual(yahoo_news.parse_article(html), "hello\nworld")


class GoogleNewsFeedTests(unittest.TestCase):
    def test_parses_two_valid_items(self):
        items = google_news.parse_feed(_load_bytes("google_news.xml"), limit=10)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "台積電 2330 Q3 毛利率再創新高")
        self.assertEqual(items[0].source_url, "https://news.google.com/rss/articles/abc123")
        self.assertEqual(
            items[0].published_at,
            datetime(2024, 11, 14, 8, 30, tzinfo=timezone.utc),
        )

    def test_limit_applied(self):
        items = google_news.parse_feed(_load_bytes("google_news.xml"), limit=1)
        self.assertEqual(len(items), 1)

    def test_ner_populates_row(self):
        items = google_news.parse_feed(_load_bytes("google_news.xml"), limit=10)
        row = items[0].as_row()
        self.assertIn("2330", row["tickers"])
        self.assertIn("CoWoS", row["wikilinks"])

    def test_build_feed_url_includes_company_name(self):
        url = google_news.build_feed_url("2330", "台積電")
        self.assertIn("2330", url)
        # URL-encoded Chinese chars.
        self.assertIn("hl=zh-TW", url)
        self.assertIn("ceid=TW:zh-Hant", url)

    def test_build_feed_url_without_company_name(self):
        url = google_news.build_feed_url("9999", None)
        self.assertIn("q=9999", url)


class FinMindParserTests(unittest.TestCase):
    def test_parses_revenue_rows(self):
        payload = json.loads(_load_text("finmind_2330.json"))
        rows = finmind.parse_rows("2330", payload)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0].report_month.isoformat(), "2024-01-01")
        self.assertEqual(rows[0].monthly_revenue, 215793000000)
        self.assertEqual(str(rows[0].yoy_pct), "7.88")

    def test_nulls_become_none(self):
        payload = json.loads(_load_text("finmind_2330.json"))
        rows = finmind.parse_rows("2330", payload)
        april = rows[3]
        self.assertIsNone(april.monthly_revenue)
        self.assertIsNone(april.yoy_pct)
        self.assertIsNone(april.mom_pct)

    def test_falls_back_to_date_field(self):
        payload = {"data": [{"date": "2023-07-10", "revenue": 100, "stock_id": "2330"}]}
        rows = finmind.parse_rows("2330", payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].report_month.isoformat(), "2023-07-01")

    def test_empty_payload(self):
        self.assertEqual(finmind.parse_rows("2330", {"data": []}), [])
        self.assertEqual(finmind.parse_rows("2330", {}), [])

    def test_since_to_start_date(self):
        self.assertEqual(finmind._since_to_start_date("2024-01"), "2024-01-01")
        self.assertEqual(finmind._since_to_start_date("2024-01-15"), "2024-01-15")


if __name__ == "__main__":
    unittest.main()
