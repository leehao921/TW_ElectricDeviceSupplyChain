"""中央社 (CNA) financial RSS collector.

Feed: https://feeds.feedburner.com/rsscna/finance
Run:  python3 -m ingestion.collectors.rss_cna --dry-run --limit 20
"""
from __future__ import annotations

from ._rss_base import run_cli

SOURCE = "cna"
FEED_URL = "https://feeds.feedburner.com/rsscna/finance"


if __name__ == "__main__":
    run_cli(SOURCE, FEED_URL)
