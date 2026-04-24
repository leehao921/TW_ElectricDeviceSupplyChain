"""工商時報 (CTEE) tech/industry RSS collector.

Feed: https://www.ctee.com.tw/feed
  NOTE: CTEE sits behind Cloudflare WAF and may return 403 for non-browser
  clients. Override with ``--url`` or set a browser-like UA upstream if needed.
Run:  python3 -m ingestion.collectors.rss_ctee --dry-run --limit 20
"""
from __future__ import annotations

from ._rss_base import run_cli

SOURCE = "ctee"
FEED_URL = "https://www.ctee.com.tw/feed"


if __name__ == "__main__":
    run_cli(SOURCE, FEED_URL)
