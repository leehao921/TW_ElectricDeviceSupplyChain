"""Periodic job registry for ``ingestion.scheduler``.

Imported for side effect by the scheduler module so the ``JOBS`` mapping is
populated before ``build_scheduler()`` is called. Every job:

- is async,
- returns an ``int`` row count so ``ingest_runs.rows_written`` is recorded,
- is wrapped by ``scheduler._run_job_async`` which catches exceptions and
  logs ``status='success'`` or ``status='error'`` rows for us.

Cadence below is the "Conservative" profile: MOPS every 4h, RSS hourly,
per-ticker news daily, FinMind monthly, Graphiti episode flush 4×/day.
"""

from __future__ import annotations

import asyncio
import logging

from . import db

LOGGER = logging.getLogger("ingestion.jobs")

# Local registry. ``ingestion.scheduler._load_jobs`` copies these into the
# scheduler's own ``JOBS`` dict at startup. Keeping the registry here avoids
# the ``__main__`` vs ``ingestion.scheduler`` double-import gotcha that
# would otherwise leave the running scheduler with a different dict object
# than the one populated at module load time.
JOBS: dict[str, tuple[str, object]] = {}

# RSS feed catalogue — kept here so editing schedules and feed URLs is one file.
_RSS_FEEDS: dict[str, str] = {
    "cna": "https://feeds.feedburner.com/rsscna/finance",
    "udn": "https://udn.com/rssfeed/news/2/6644?ch=news",
    # ctee disabled 2026-04-28: ctee.com.tw RSS is behind Cloudflare WAF that
    # 403s every non-browser-fingerprint client (full Chrome UA already tested
    # in _rss_base.USER_AGENT). Re-enable when we identify a stable alternate
    # source for 工商時報 (FinMind TaiwanStockNews or an official API endpoint).
}


# --- collector wrappers (each returns rows-written) -------------------------


async def _job_mops_recent() -> int:
    """Pull the last day of MOPS material announcements."""
    from .collectors import mops
    items = await mops.collect(since_days=1, limit=None, dry_run=False)
    return len(items)


def _make_rss_job(source: str, feed_url: str):
    """Build an async closure that scrapes one RSS feed and returns row count."""
    async def _runner() -> int:
        from .collectors._rss_base import ingest_rss
        return await ingest_rss(source, feed_url, dry_run=False, limit=50)
    _runner.__name__ = f"_job_rss_{source}"
    return _runner


async def _iter_news_collector(source: str, collect_fn, *, limit: int) -> int:
    """Shared driver for yahoo / google per-ticker collectors.

    Inserts rows in a single shared pool and tolerates per-ticker failures so
    one bad listing page doesn't sink the rest of the run.
    """
    from .collectors._common import insert_news_rows, make_client
    from .universe import all_tickers

    pool = await db.get_pool()
    total = 0
    async with make_client() as client:
        for ticker in sorted(all_tickers()):
            try:
                items = await collect_fn(ticker, limit=limit, client=client)
            except Exception as exc:  # noqa: BLE001 — keep crawling
                LOGGER.warning("%s %s failed: %s", source, ticker, exc)
                continue
            if not items:
                continue
            written = await insert_news_rows(
                pool, source, (it.as_row() for it in items)
            )
            total += written
    return total


async def _job_yahoo_news_all() -> int:
    from .collectors import yahoo_news
    return await _iter_news_collector("yahoo", yahoo_news.collect, limit=20)


async def _job_google_news_all() -> int:
    from .collectors import google_news
    return await _iter_news_collector("google", google_news.collect, limit=20)


async def _job_finmind_revenue() -> int:
    """Refresh monthly revenue rows for every electronics ticker."""
    from .collectors import finmind
    from .universe import all_tickers

    pool = await db.get_pool()
    total = 0
    for ticker in sorted(all_tickers()):
        try:
            rows = await finmind.collect(ticker, since="2024-01")
        except Exception as exc:  # noqa: BLE001 — keep crawling
            LOGGER.warning("finmind %s failed: %s", ticker, exc)
            continue
        if not rows:
            continue
        async with pool.acquire() as conn:
            await conn.executemany(
                finmind.UPSERT_SQL,
                [
                    (r.ticker, r.report_month, r.monthly_revenue, r.yoy_pct, r.mom_pct)
                    for r in rows
                ],
            )
        total += len(rows)
        # Free-tier-friendly pacing between tickers.
        await asyncio.sleep(0.3)
    return total


async def _job_tpu_snapshot_daily() -> int:
    """Refresh the TPU v8x supply-chain valuation + 籌碼 snapshot row."""
    from .snapshots.tpu import build_and_upsert_snapshot
    return await build_and_upsert_snapshot()


async def _job_overnight_signal_daily() -> int:
    """Compute the TXF overnight composite signal (5-factor z-score) and upsert
    to ``news_items``. Runs at 08:45 TPE, before the 09:00 open."""
    from .snapshots.overnight_signal import build_and_upsert_signal
    return await build_and_upsert_signal()


async def _job_event_factor_refresh() -> int:
    """Re-extract emergent factor baskets from the event calendar.

    Runs ``analysis/event_factor_extractor.py --all`` as a subprocess. Each
    event's row-set is replaced (DELETE + INSERT) idempotently. Returns the
    total rows upserted.
async def _job_market_monitor_intraday() -> int:
    """Intraday alert monitor — piggybacks on rss_cna (:15) / rss_udn (:35)
    cadence so we don't add a new high-frequency cron tick. Cron expression
    ``15,35 9-13 * * 1-5``. Returns the count of alerts emitted (0 = quiet).

    Auto-skips weekends + holidays via the ``is_tw_market_open`` check inside
    the script (no recent TXF futures bar ⇒ exit early).
    """
    import subprocess
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "analysis" / "event_factor_extractor.py"
    proc = await asyncio.create_subprocess_exec(
        "python3", str(script), "--all",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"event_factor_extractor failed: {stderr.decode()}")
    # Parse the trailing "upserted N rows across M events" line.
    rows = 0
    for line in stderr.decode().splitlines():
        if "upserted" in line and "rows across" in line:
            try:
                rows = int(line.split("upserted")[1].split("rows")[0].strip())
            except (ValueError, IndexError):
                rows = 0
    return rows
    script = repo_root / "analysis" / "market_monitor.py"
    proc = await asyncio.create_subprocess_exec(
        "python3", str(script),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode < 0:
        raise RuntimeError(f"market_monitor died: {stderr.decode()}")
    # The script returns the alert count via exit code (0 = quiet, N = alerts).
    return max(proc.returncode, 0)


async def _job_db_vacuum_weekly() -> int:
    from . import maintenance
    return await maintenance.vacuum_analyze()


async def _job_db_cleanup_runs() -> int:
    from . import maintenance
    return await maintenance.cleanup_ingest_runs(days=90)


async def _job_db_freshness_check() -> int:
    from . import maintenance
    return await maintenance.freshness_check()


async def _job_graphiti_news_incremental() -> int:
    """Stream recently ingested news rows into the Graphiti supply-chain graph.

    The relevance gate inside ``ingest_news_as_episode`` drops items that
    aren't multi-ticker or supply-chain-verb-shaped, so the returned count is
    "episodes added" not "rows considered".
    """
    from graph.incremental import ingest_news_as_episode

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, source, source_url, published_at, title, body, tickers
              FROM news_items
             WHERE ingested_at > NOW() - INTERVAL '5 hours'
             ORDER BY ingested_at DESC
             LIMIT 500
            """
        )

    ingested = 0
    for r in rows:
        result = await ingest_news_as_episode(dict(r))
        if result.get("status") == "ingested":
            ingested += 1
    return ingested


# --- registration ------------------------------------------------------------

# All cron expressions are evaluated in Asia/Taipei via settings.tz
# (see scheduler.py:67).
JOBS["mops_recent"] = ("0 */4 * * *", _job_mops_recent)
JOBS["yahoo_news_all"] = ("0 8 * * *", _job_yahoo_news_all)
JOBS["google_news_all"] = ("0 9 * * *", _job_google_news_all)
JOBS["finmind_revenue"] = ("0 9 11 * *", _job_finmind_revenue)
JOBS["graphiti_news_incremental"] = (
    "30 8,12,16,20 * * *", _job_graphiti_news_incremental
)

# TPU snapshot — 1 hour after market close, weekdays only
JOBS["tpu_snapshot_daily"] = ("30 16 * * 1-5", _job_tpu_snapshot_daily)

# Overnight composite signal — 15 min before TWSE 09:00 open, weekdays only
JOBS["overnight_signal_daily"] = ("45 8 * * 1-5", _job_overnight_signal_daily)

# Event factor refresh — Sunday 02:00 TPE, re-extract all emergent baskets
JOBS["event_factor_refresh_weekly"] = ("0 2 * * 0", _job_event_factor_refresh)
# Intraday market monitor — piggybacks on rss_cna (:15) / rss_udn (:35) cadence.
# Auto-quiet on weekends/holidays via is_tw_market_open() inside the script.
JOBS["market_monitor_intraday"] = ("15,35 9-13 * * 1-5", _job_market_monitor_intraday)

# Database maintenance — weekly VACUUM + run-log cleanup, hourly freshness check
JOBS["db_vacuum_weekly"] = ("0 3 * * 0", _job_db_vacuum_weekly)
JOBS["db_cleanup_runs"] = ("0 4 * * 0", _job_db_cleanup_runs)
JOBS["db_freshness_check"] = ("0 * * * *", _job_db_freshness_check)

# Stagger RSS feed pulls so we don't hammer multiple sources on the same minute.
_RSS_CRON = {"cna": "15 * * * *", "ctee": "25 * * * *", "udn": "35 * * * *"}
for _source, _feed_url in _RSS_FEEDS.items():
    JOBS[f"rss_{_source}"] = (_RSS_CRON[_source], _make_rss_job(_source, _feed_url))
