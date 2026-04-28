"""經濟日報 (UDN Money) industry/tech RSS collector.

Feed: https://money.udn.com/rssfeed/news/1001/5591
  (category: 產業科技 — industry & tech, closest fit for electronics coverage)
Run:  python3 -m ingestion.collectors.rss_udn --dry-run --limit 20
"""
from __future__ import annotations

from ._rss_base import run_cli

SOURCE = "udn"
FEED_URL = "https://money.udn.com/rssfeed/news/1001/5591"


if __name__ == "__main__":
    run_cli(SOURCE, FEED_URL)
