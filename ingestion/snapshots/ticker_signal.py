"""Per-ticker 3-factor early-outlier signal — daily build + upsert.

Three independent factors, **2-of-3 trigger** for a qualifying alert:

1. **flow_z**:    5-day rolling sum of (foreign_net + trust_net) for the
                  ticker, z-scored vs the trailing 60d distribution of 5-day
                  rolling sums. Source: ``institutional_stock`` in
                  ``trading-timescaledb`` (read-only).
2. **news_z**:    7-day count of ``news_items`` rows mentioning the ticker,
                  z-scored vs the trailing 90d daily-count distribution.
3. **wikilink_heat**: count of distinct co-occurring ``[[wikilinks]]`` in
                  ``news_items`` from the last 7 days that mention the ticker.

Designed to run from :mod:`ingestion.scheduler` via the
``ticker_signal_daily`` job (17:00 Asia/Taipei, Mon-Fri) — 30 minutes after
TWSE close so ``institutional_stock`` is fully ingested.

See ``docs/plans/2026-05-05-signal-layer.md`` for the full design and the
backtest acceptance criterion (≥55% 10d hit rate before promoting to prod).
"""
from __future__ import annotations

import json
import logging
import math
import os
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .. import db

LOGGER = logging.getLogger("ingestion.snapshots.ticker_signal")

PG_TRADING_DSN = os.environ.get(
    "PG_TRADING_DSN",
    "postgresql://tmf:tmf_dev_2026@localhost:5432/tmf_market_data",
)

FLOW_WINDOW = 60         # trading days for flow z-score reference
FLOW_K = 5               # rolling sum length for the value under test
NEWS_BASELINE_DAYS = 90  # days for news_z baseline
NEWS_RECENT_DAYS = 7     # window for the value under test
WIKILINK_WINDOW_DAYS = 7

FLOW_THRESHOLD = 2.0
NEWS_THRESHOLD = 2.0
WIKILINK_THRESHOLD = 5

WEIGHTS = {"flow": 0.5, "news": 0.3, "wikilink": 0.2}


# -- Trading-DB connection (read-only) --------------------------------------


async def _connect_trading():
    import asyncpg
    return await asyncpg.connect(PG_TRADING_DSN)


# -- Factor 1: flow z-score -------------------------------------------------


async def _compute_flow_z(ticker: str, as_of: date) -> Optional[dict]:
    """Return ``{raw, mean, std, z}`` for the latest 5d rolling-sum, or None
    if we have insufficient history.

    Values are kept in NTD (BIGINT from institutional_stock) — the digest
    formats them as 億 TWD downstream.
    """
    conn = await _connect_trading()
    try:
        rows = await conn.fetch(
            """
            SELECT date, COALESCE(foreign_net, 0) + COALESCE(trust_net, 0) AS net
              FROM institutional_stock
             WHERE symbol = $1
               AND date <= $2
             ORDER BY date DESC
             LIMIT $3
            """,
            ticker,
            as_of,
            FLOW_WINDOW + FLOW_K + 5,
        )
    finally:
        await conn.close()

    if len(rows) < FLOW_WINDOW + FLOW_K:
        return None

    values = [int(r["net"]) for r in reversed(rows)]
    rolling = [sum(values[i - FLOW_K + 1: i + 1]) for i in range(FLOW_K - 1, len(values))]
    if len(rolling) < FLOW_WINDOW + 1:
        return None

    today_sum = float(rolling[-1])
    hist = [float(v) for v in rolling[-(FLOW_WINDOW + 1):-1]]
    mean = statistics.mean(hist)
    std = statistics.pstdev(hist)
    z = (today_sum - mean) / std if std > 0 else 0.0
    return {"raw": today_sum, "mean": mean, "std": std, "z": z}


# -- Factor 2: news density z-score -----------------------------------------


_NEWS_Z_SQL = """
WITH per_day AS (
  SELECT (published_at AT TIME ZONE 'Asia/Taipei')::date AS d,
         t AS ticker,
         count(*) AS hits
    FROM news_items, unnest(tickers) t
   WHERE published_at > $1::timestamptz - ($2::text || ' days')::interval
     AND published_at <= $1::timestamptz
     AND t = $3
   GROUP BY 1, 2
), days AS (
  -- pad zero-hit days into the baseline so std reflects true variance
  SELECT generate_series(
           ($1::timestamptz - ($2::text || ' days')::interval)::date,
           ($1::timestamptz - INTERVAL '1 day')::date,
           '1 day'::interval
         )::date AS d
), padded AS (
  SELECT days.d, COALESCE(per_day.hits, 0) AS hits
    FROM days
    LEFT JOIN per_day ON per_day.d = days.d
)
SELECT
  (SELECT COALESCE(sum(hits), 0)
     FROM padded
    WHERE d > ($1::timestamptz - ($4::text || ' days')::interval)::date) AS recent_hits,
  (SELECT COALESCE(avg(hits), 0)
     FROM padded
    WHERE d <= ($1::timestamptz - ($4::text || ' days')::interval)::date) AS baseline_avg,
  (SELECT COALESCE(stddev(hits), 0)
     FROM padded
    WHERE d <= ($1::timestamptz - ($4::text || ' days')::interval)::date) AS baseline_std;
"""


async def _compute_news_z(ticker: str, as_of: datetime) -> Optional[dict]:
    """Return ``{recent, baseline_avg, z}`` for news density using a Poisson
    model: σ ≈ √(k·μ) where k = NEWS_RECENT_DAYS and μ is the per-day
    baseline rate from the older window.

    Poisson is the right model for count data — sample-stddev on a
    zero-heavy 90d window collapses (or explodes) for sparse tickers.
    Returns None when the baseline is essentially zero (no coverage).
    """
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            _NEWS_Z_SQL,
            as_of, str(NEWS_BASELINE_DAYS), ticker, str(NEWS_RECENT_DAYS),
        )

    recent = int(row["recent_hits"])
    avg = float(row["baseline_avg"] or 0)

    if avg < 0.05:
        return None

    expected = NEWS_RECENT_DAYS * avg
    sigma = math.sqrt(expected) if expected > 0 else 0.0
    z = (recent - expected) / sigma if sigma > 0 else 0.0
    return {"recent": recent, "baseline_avg": avg, "z": z}


# -- Factor 3: wikilink heat -----------------------------------------------


_WIKILINK_HEAT_SQL = """
WITH agg AS (
  SELECT w AS wikilink, count(*) AS hits
    FROM news_items, unnest(tickers) t, unnest(wikilinks) w
   WHERE published_at > $1::timestamptz - ($2::text || ' days')::interval
     AND published_at <= $1::timestamptz
     AND t = $3
   GROUP BY w
)
SELECT
  (SELECT count(*) FROM agg) AS heat,
  (SELECT json_agg(row_to_json(t)) FROM (
     SELECT wikilink, hits FROM agg ORDER BY hits DESC LIMIT 20
   ) t) AS top;
"""


async def _compute_wikilink_heat(ticker: str, as_of: datetime) -> dict:
    """Return ``{heat, top}`` — true distinct count + top 20 (wikilink, hits)."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            _WIKILINK_HEAT_SQL, as_of, str(WIKILINK_WINDOW_DAYS), ticker,
        )
    top_raw = row["top"]
    if isinstance(top_raw, str):
        top_raw = json.loads(top_raw)
    top = [(t["wikilink"], int(t["hits"])) for t in (top_raw or [])]
    return {"heat": int(row["heat"] or 0), "top": top}


# -- Public: per-ticker compute --------------------------------------------


async def compute_factors(ticker: str, as_of: Optional[datetime] = None) -> dict:
    """Compute all three factors for ``ticker`` as of ``as_of`` (defaults: now).

    Returns a dict with keys: flow, news, wikilink, factors_hit, composite.
    Missing factors are stored as ``None``; the composite ignores NULL terms
    and renormalizes weights over the surviving factors.
    """
    if as_of is None:
        as_of = datetime.now(timezone(timedelta(hours=8)))

    flow = await _compute_flow_z(ticker, as_of.date())
    news = await _compute_news_z(ticker, as_of)
    wiki = await _compute_wikilink_heat(ticker, as_of)

    fired = 0
    if flow is not None and abs(flow["z"]) >= FLOW_THRESHOLD:
        fired += 1
    if news is not None and news["z"] >= NEWS_THRESHOLD:
        fired += 1
    if wiki["heat"] >= WIKILINK_THRESHOLD:
        fired += 1

    composite = _composite_score(flow, news, wiki)

    return {
        "ticker": ticker,
        "as_of": as_of.date().isoformat(),
        "flow": flow,
        "news": news,
        "wikilink": wiki,
        "factors_hit": fired,
        "composite": composite,
    }


def _cap(x: float, ceiling: float) -> float:
    return max(-ceiling, min(ceiling, x))


def _composite_score(flow: Optional[dict], news: Optional[dict], wiki: dict) -> float:
    """Weighted blend with NULL-aware renormalization. Sign comes from flow.

    Caps individual components so a single 8σ outlier doesn't dominate.
    """
    parts: list[tuple[float, float]] = []  # (weight, contribution)
    if flow is not None:
        flow_term = _cap(flow["z"], 4.0)
        parts.append((WEIGHTS["flow"], flow_term))
    if news is not None:
        news_term = _cap(news["z"], 4.0)
        parts.append((WEIGHTS["news"], news_term))
    wiki_term = min(wiki["heat"], 10) / 2.0  # 0..5 scale
    parts.append((WEIGHTS["wikilink"], wiki_term))

    total_w = sum(w for w, _ in parts)
    if total_w == 0:
        return 0.0
    return sum(w * v for w, v in parts) / total_w


# -- Public: build daily digest --------------------------------------------


async def _ticker_universe() -> list[str]:
    from ..universe import all_tickers
    return sorted(all_tickers())


async def build_and_upsert_alerts(as_of: Optional[datetime] = None) -> int:
    """Compute factors for every electronics ticker, upsert qualifying rows
    into ``signal_alerts``, and write a daily markdown digest. Returns the
    count of alerts emitted (factors_hit >= 2)."""
    if as_of is None:
        as_of = datetime.now(timezone(timedelta(hours=8)))
    trade_date = as_of.date()

    universe = await _ticker_universe()
    all_results: list[dict] = []
    for ticker in universe:
        try:
            r = await compute_factors(ticker, as_of)
        except Exception as exc:  # noqa: BLE001 — keep crawling
            LOGGER.warning("ticker_signal %s failed: %s", ticker, exc)
            continue
        if r["factors_hit"] >= 1 or (r["flow"] and abs(r["flow"]["z"]) >= 1.5):
            all_results.append(r)

    pool = await db.get_pool()
    upserted = 0
    qualifying = 0
    async with pool.acquire() as conn:
        for r in all_results:
            details = {
                "flow": r["flow"],
                "news": r["news"],
                "wikilink_top": r["wikilink"]["top"],
            }
            await conn.execute(
                """
                INSERT INTO signal_alerts
                  (trade_date, ticker, flow_z, news_z, wikilink_heat,
                   factors_hit, composite, details)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                ON CONFLICT (trade_date, ticker) DO UPDATE SET
                  flow_z = EXCLUDED.flow_z,
                  news_z = EXCLUDED.news_z,
                  wikilink_heat = EXCLUDED.wikilink_heat,
                  factors_hit = EXCLUDED.factors_hit,
                  composite = EXCLUDED.composite,
                  details = EXCLUDED.details
                """,
                trade_date, r["ticker"],
                r["flow"]["z"] if r["flow"] else None,
                r["news"]["z"] if r["news"] else None,
                r["wikilink"]["heat"],
                r["factors_hit"], float(r["composite"]),
                json.dumps(details, ensure_ascii=False),
            )
            upserted += 1
            if r["factors_hit"] >= 2:
                qualifying += 1

    LOGGER.info(
        "ticker_signal upserted=%d qualifying(2-of-3)=%d as_of=%s",
        upserted, qualifying, trade_date,
    )
    return qualifying
