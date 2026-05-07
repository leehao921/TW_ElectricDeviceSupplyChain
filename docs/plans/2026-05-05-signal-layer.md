# 2026-05-05 — Per-ticker Signal Layer (3-factor early-outlier detector)

## Goal

Build a daily signal job that flags individual electronics tickers showing
**unusual concurrent activity** across three independent channels:

1. **Money flow** — 5-day rolling sum of (外資 + 投信) net buy, z-scored vs trailing 60d.
2. **News density** — 7-day count of `news_items` mentioning the ticker, z-scored vs trailing 90d.
3. **Wikilink heat** — count of distinct co-occurring `[[wikilinks]]` in
   `news_items` from the last 7 days that mention the ticker.

User-stated motivation: 2026-04 聯發科 +100% / 4985 臻鼎-KY +100% moves —
he wants advance warning of similar setups, not after-the-fact analysis.

## Why three factors

Single-factor screens miss early signal. 4985's April rally:
- 法人買超先動 (factor 1) — would have triggered ~3 days early.
- 新聞密度同步上升 (factor 2) — confirms it's not noise.
- Co-occurring `[[CoWoS]]` / `[[ABF 載板]]` wikilinks (factor 3) —
  identifies the *narrative* driving the move.

Triggering on **any one** is too noisy. Triggering on **2-of-3 simultaneously**
is the qualifying condition.

---

## Critical files

### New (this plan creates)

- `ingestion/migrations/004_signal_alerts.sql` — `signal_alerts` table.
- `ingestion/snapshots/ticker_signal.py` — main signal-builder module.
- `ingestion/jobs.py` (edit) — register `ticker_signal_daily` cron entry.
- `analysis/signals/` — output dir for daily markdown digests (gitignored
  except for an empty `.gitkeep`).
- `tests/test_ticker_signal.py` — unit tests for z-score math + 2-of-3 gate.

### Existing utilities to reuse

- `mcp_server/tools/market.py` — already opens a read-only connection to
  `trading-timescaledb` and detects the `institutional_stock` schema. Reuse
  `_connect()` + `_get_columns()` rather than re-implementing.
- `ingestion/db.py:get_pool()` + `db.embed()` + `db.vector_literal()` — reused
  to write the daily digest into `news_items` (same pattern as
  `overnight_signal.py`).
- `ingestion/universe.py:all_tickers()` — universe enumeration (926 stocks).
- `scripts/verify_flow_zscore.py` — the established z-score convention; copy
  the rolling-sum + z formula verbatim for factor 1.

---

## Phase 1 — DB migration (`signal_alerts` table)

`ingestion/migrations/004_signal_alerts.sql`:

```sql
CREATE TABLE IF NOT EXISTS signal_alerts (
  id            BIGSERIAL PRIMARY KEY,
  trade_date    DATE NOT NULL,
  ticker        TEXT NOT NULL,
  flow_z        REAL,             -- factor 1 (5d外資+投信 z vs 60d)
  news_z        REAL,             -- factor 2 (7d news count z vs 90d)
  wikilink_heat INTEGER,          -- factor 3 (distinct co-occurring wikilinks, last 7d)
  factors_hit   INTEGER NOT NULL, -- count of factors with |z|>2 OR heat>=N
  composite     REAL NOT NULL,    -- weighted blend (see Phase 3)
  details       JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (trade_date, ticker)
);
CREATE INDEX ON signal_alerts (trade_date DESC, composite DESC);
CREATE INDEX ON signal_alerts (ticker, trade_date DESC);
```

`details` carries the raw numbers (top wikilinks, top news titles, flow
breakdown) so the digest stays compact while the full provenance lives in
the row.

## Phase 2 — Factor implementations (`ticker_signal.py`)

### Factor 1: flow z-score

For each ticker, query `institutional_stock` from `trading-timescaledb` for
the trailing 65 trading days; compute the 5-day rolling sum of
`(foreign_net + trust_net)` per row; the **latest sum** is the value under
test, and the prior 60 sums form the reference distribution. z = (x − μ) / σ.

Mirror `verify_flow_zscore.py` exactly (single source of truth for z-score
convention). Edge case: if a ticker has < 60 days of history, skip.

### Factor 2: news density z-score

Single SQL against the electronics-Postgres `news_items` table:

```sql
WITH per_day AS (
  SELECT date_trunc('day', published_at)::date AS d,
         t AS ticker,
         count(*) AS hits
    FROM news_items, unnest(tickers) t
   WHERE published_at > NOW() - INTERVAL '90 days'
   GROUP BY 1, 2
)
SELECT ticker,
       sum(hits) FILTER (WHERE d > NOW() - INTERVAL '7 days') AS recent_7d,
       avg(hits) FILTER (WHERE d <= NOW() - INTERVAL '7 days') AS baseline_avg,
       stddev(hits) FILTER (WHERE d <= NOW() - INTERVAL '7 days') AS baseline_std
  FROM per_day
 GROUP BY ticker
HAVING sum(hits) FILTER (WHERE d > NOW() - INTERVAL '7 days') > 0;
```

z = (recent_7d − 7 × baseline_avg) / (sqrt(7) × baseline_std). Skip tickers
with baseline_std == 0.

### Factor 3: wikilink heat

```sql
SELECT t AS ticker, count(DISTINCT w) AS heat
  FROM news_items, unnest(tickers) t, unnest(wikilinks) w
 WHERE published_at > NOW() - INTERVAL '7 days'
 GROUP BY t;
```

Scalar (not z-scored): a ticker with ≥ 5 distinct co-occurring wikilinks
in the last 7 days is "thematic-cluster-active". The per-row `details`
column carries the top 10 wikilinks by frequency for the digest.

### Trigger gate

A ticker is **alerted** if **2-of-3** factors fire:

- factor 1 fires: `|flow_z| ≥ 2.0`
- factor 2 fires: `news_z ≥ 2.0` (only positive tail — we want spikes,
  not drought)
- factor 3 fires: `wikilink_heat ≥ 5`

`composite = 0.5 * sign(flow_z) * min(|flow_z|, 4) + 0.3 * min(news_z, 4) + 0.2 * min(wikilink_heat, 10) / 2`

(Caps prevent any single factor from dominating; the
`sign(flow_z)` term keeps the composite directional — large outflow becomes
negative composite.)

## Phase 3 — Daily digest output

Two writes per run:

1. **`signal_alerts` row** for every ticker with `factors_hit >= 1` (so
   we keep history even for sub-threshold movers).
2. **Markdown digest** at `analysis/signals/YYYY-MM-DD.md` listing the top
   20 alerts ranked by `composite`, each with: ticker + 公司名,
   the three factor numbers, the top 3 driving wikilinks, the latest 2 news
   titles. Same digest is also upserted into `news_items` with
   `source='ticker_signal'` so it shows up in MCP queries.

Sample digest row:

```markdown
### 4985 — 臻鼎-KY (composite +3.42, 3/3)
- 資金流: +212 億 (5d) → z=+2.84σ vs 60d 分布 (97 percentile)
- 新聞密度: 18 hits (7d) vs 4.2/wk baseline → z=+2.31σ
- Wikilink heat: 7 → [[ABF 載板]], [[CoWoS]], [[AI 伺服器]], ...
- Latest: 「臻鼎接 NVIDIA GB300 ABF 大單」(2026-05-04)
```

## Phase 4 — Job registration

`ingestion/jobs.py`:

```python
async def _job_ticker_signal_daily() -> int:
    from .snapshots.ticker_signal import build_and_upsert_alerts
    return await build_and_upsert_alerts()

# Daily 17:00 TPE — 30min after market close, after institutional_stock is
# fully ingested by trading-timescaledb but before tpu_snapshot at 16:30
# would otherwise contend for DB. Pick 17:00 to give institutional flow a
# clean window to land.
JOBS["ticker_signal_daily"] = ("0 17 * * 1-5", _job_ticker_signal_daily)
```

## Phase 5 — Backtest harness

`scripts/backtest_signal.py` (separate from prod path). Replays the same
3-factor logic over historical news_items + institutional_stock, computes
forward 5d / 10d / 20d returns for each alerted ticker, reports:

- Hit rate (% alerts where forward 10d return > +5%)
- Information coefficient (Spearman correlation of `composite` vs forward
  10d return)
- Top false-positive cluster (which signal combinations failed?)

Acceptance criterion before promoting to prod: hit rate ≥ 55% on
2024-01 → 2026-03 with ≥ 50 alerts in the period. Below that → tune
thresholds before declaring the layer done.

## Out of scope

- Push notifications (Slack/email/iOS) — separate plan; the digest
  markdown + `news_items` upsert lets MCP/Claude.ai surface alerts on
  demand without a push channel.
- Intraday (sub-daily) cadence — daily is enough for catching multi-day
  trends; intraday burst-detection is deferred until we see whether daily
  alerts actually correlate with multi-day rallies.
- Sector aggregation — per-ticker first; sector roll-up after we trust
  the per-ticker layer.
- Migrating wikilink-heat to graph traversal — using `news_items.wikilinks`
  TEXT[] is faster and simpler. Graphiti graph would add latency and
  duplication risk.

## Verification (to run after each phase merges)

```bash
# Phase 1: migration applies cleanly
docker exec tw-electronics-scheduler python3 -m ingestion.migrations.apply

# Phase 2: factors compute for a known winner (4985)
docker exec tw-electronics-scheduler python3 -c '
import asyncio
from ingestion.snapshots.ticker_signal import compute_factors
print(asyncio.run(compute_factors("4985")))
'
# Expected: {flow_z: +>2, news_z: +>2, wikilink_heat: >=5, factors_hit: 3}

# Phase 4: cron is registered
docker exec tw-electronics-scheduler python3 -c '
from ingestion.jobs import JOBS
print("ticker_signal_daily" in JOBS, JOBS.get("ticker_signal_daily"))
'

# Phase 5: backtest runs and emits hit rate
python3 scripts/backtest_signal.py --start 2024-01-01 --end 2026-03-31
```

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| `news_items` coverage is sparse for small tickers — factor 2 will misfire | Skip tickers with `baseline_avg < 0.5/day`; fall back to 2-of-3 with 1+3 valid |
| `institutional_stock` not yet populated for some tickers | `compute_factors` returns `None` per missing factor, NULL stays in `signal_alerts.flow_z` — composite ignores NULL terms |
| Backtest hit rate below 55% | Don't promote to prod cron yet; iterate on thresholds and weights, document negative result in the plan |
| Look-ahead bias in factor 2 (using `published_at` from articles published *after* the alert date) | Backtest harness explicitly clips to `published_at <= as_of_date - 1` |
