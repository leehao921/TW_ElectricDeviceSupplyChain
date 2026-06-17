# Build stock_daily_ohlcv Collector + Migrate BB Scanner to DB

**Created:** 2026-06-17 (Wed)
**Repos:** `/Users/lulala/Documents/coding/database/` (collector) + `/Users/lulala/Documents/coding/My-TW-Coverage/` (BB scanner refactor)
**Owner:** leehao921

---

## Context

### Why this is being built
This session's BB squeeze scanner (`smart_money_analysis.py` Section 8) currently pulls yfinance live for 926 tickers on every run — adds ~60 seconds, has hit yfinance rate-limit (today's run dropped from 923 → 700 coverage), can't run offline, and provides no path to multi-year backtest.

The earlier session built `tmf-fx-collector` (PR #141) for the analogous gap on FX data. Same pattern should apply to per-ticker daily OHLCV: collect once, cache in TimescaleDB, downstream consumers (smart_money, future backtests) read from DB instantly.

### Intended outcome
1. **`stock_daily_ohlcv` hypertable** in `trading-timescaledb`, fed by a new `tmf-stock-daily-collector` container that runs **twice daily** (14:30 TPE primary + 07:00 TPE backstop) for the 926-ticker electronics universe.
2. **1-year initial backfill** (2025-06-17 → 2026-06-17) populated as part of the deployment.
3. `smart_money_analysis.py:fetch_ohlcv_universe` rewritten to **read from DB by default**, with `--ohlcv-source yfinance` fallback flag preserved for offline / debug use.
4. Smart-money report wall-clock drops from ~75s → < 5s. yfinance rate-limit risk eliminated for normal daily runs.

### User-confirmed scope (this session)
- **Backfill:** 1 year (2025-06-17 → 2026-06-17), ~250 TD × 926 = ~230k rows
- **Schedule:** Twice daily — 14:30 TPE (after TWSE 13:30 close, primary fetch) + 07:00 TPE (backstop to catch anything missed)
- **Universe:** 926 Pilot_Reports electronics tickers (same set BB scanner uses)

---

## Design

### Architecture — mirrors fx-collector

```
trading-timescaledb
  └── stock_daily_ohlcv (NEW hypertable, partitioned on ts)
        columns: ts, symbol, open, high, low, close, volume, source, source_close_tz, ingested_at
        PK: (ts, symbol, source_close_tz)

docker-compose.yml
  └── tmf-stock-daily-collector (NEW service, mirrors tmf-fx-collector)
        ├── image: python:3.11-slim
        ├── command: pip install -r requirements-pipeline.txt → scripts/stock_daily_ohlcv_scheduler.sh
        └── env: TIMESCALE_* same as other collectors

scripts/collectors/stock_daily_ohlcv.py (NEW)
  ├── argparse: --date, --start-date, --end-date, --tickers-file, --dry-run
  ├── yfinance batch (.TW chunks of 50, then .TWO fallback) — copy from BB scanner
  ├── psycopg2 upsert with ON CONFLICT
  └── exit 0 on success, 1 on no rows

scripts/stock_daily_ohlcv_scheduler.sh (NEW)
  └── daemon loop with TWO schedule times: 14:30 and 07:00 TPE
       → at each fire, runs collector for "yesterday TPE date" (07:00 case) or today (14:30 case)

scripts/collectors/tw_electronics_tickers.txt (NEW)
  └── 926-line snapshot of Pilot_Reports tickers (4-digit ticker per line)

tests/test_stock_daily_ohlcv.py (NEW)
  └── date parse / timestamp conversion / yfinance mock / upsert SQL shape / CLI flag tests
```

### Schema migration (NEW SQL file)
**`sql/migrations/2026-06-17-stock-daily-ohlcv.sql`:**
```sql
CREATE TABLE IF NOT EXISTS stock_daily_ohlcv (
    ts              timestamptz NOT NULL,
    symbol          text        NOT NULL,
    open            double precision,
    high            double precision,
    low             double precision,
    close           double precision,
    volume          bigint,
    source          text DEFAULT 'yfinance',
    source_close_tz text DEFAULT 'TWSE_1330TPE',
    ingested_at     timestamptz DEFAULT now(),
    PRIMARY KEY (ts, symbol, source_close_tz)
);
SELECT create_hypertable('stock_daily_ohlcv', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_stock_daily_ohlcv_symbol_ts
    ON stock_daily_ohlcv (symbol, ts DESC);
```

`source_close_tz = 'TWSE_1330TPE'` documents the convention: ts = TWSE 13:30 TPE close instant in UTC (= 05:30 UTC). This parallels fx_daily's `'NY17ET'`.

### Module template (copied from `scripts/collectors/fx_daily.py`)

| Function | Responsibility |
|---|---|
| `_build_pg_conn()` | Copy verbatim |
| `_parse_date(s)` | Copy verbatim |
| `_twse_close_utc(d)` | NEW — date d → `datetime(d, 13, 30) Asia/Taipei` → UTC. Parallels fx's `_ny_close_utc()`. |
| `fetch_one_ticker_chunk(tickers, start, end)` | NEW — yfinance batch download with `.TW` first then `.TWO` fallback for missing. Returns rows. |
| `upsert_rows(conn, rows)` | NEW — INSERT ... ON CONFLICT (ts, symbol, source_close_tz) DO UPDATE. |
| `main(argv)` | argparse → resolve date range → load ticker list → loop in chunks of 50 → upsert |

### Scheduler with TWO daily fires

`scripts/stock_daily_ohlcv_scheduler.sh`:
```bash
SCHEDULE_TIMES=("14:30" "07:00")  # primary + backstop

# Modified seconds_until_next_run() to find the earliest upcoming entry
# from SCHEDULE_TIMES (handles wrap to next day)

# 14:30 fire: collector --date <today TPE>
# 07:00 fire: collector --date <yesterday TPE>  (TWSE 13:30 of prior day finalised)
# Both fires upsert; ON CONFLICT handles dedup naturally.
```

### Ticker universe sync

The 926-ticker list lives in `My-TW-Coverage/Pilot_Reports/`. The collector is in `database/`. For v1, **snapshot-and-commit**: a one-off `scripts/sync_tickers_to_collector.py` (in My-TW-Coverage) walks Pilot_Reports and emits the txt file, which the user copies into the database repo at PR time. The 926-line text file is small and changes rarely (1-2 tickers per batch update); manual sync is fine.

A follow-up automation could be a pre-commit hook in My-TW-Coverage that warns if Pilot_Reports changed without ticker list sync. Out of scope here.

### Downstream changes in My-TW-Coverage

`scripts/smart_money_analysis.py`:
- `fetch_ohlcv_universe(tickers, period='3mo')` → new internal: try DB read first, fall back to yfinance only if rows insufficient.
- New CLI flag: `--ohlcv-source {db,yfinance,auto}` (default `auto`).
- New helper `load_ohlcv_from_db(conn, tickers, start_date, end_date)` reads `stock_daily_ohlcv`, reconstructs `{ticker: pd.DataFrame}` map matching the yfinance shape (columns Open/High/Low/Close/Volume, indexed by datetime).
- BB compute path stays unchanged — it sees same dict shape.

### Backfill plan (run once at deployment)

```bash
# In database/, after collector merged:
docker exec tmf-stock-daily-collector python /opt/tmf/scripts/collectors/stock_daily_ohlcv.py \
    --start-date 2025-06-17 --end-date 2026-06-17
```

- ~230k rows over 60 yfinance batch calls (926 / 50 ≈ 19 batches × 1 year range request)
- Inter-batch sleep 2 sec → ~38s + yfinance fetch time ≈ 8-12 min total
- Idempotent (ON CONFLICT UPDATE) — safe to re-run

### Edge cases handled inline

1. **yfinance rate-limit during backfill** — chunk-level retry with 30s sleep on `YFRateLimitError`; max 3 retries before logging and continuing.
2. **OTC tickers** (.TWO suffix) — `.TW` first, missing chunked retry with `.TWO`. Same fallback chain BB scanner uses.
3. **Today's bar not yet finalised** (14:30 fire) — yfinance may return partial bar; we accept it. The 07:00 backstop next morning over-writes with the finalised version (ON CONFLICT UPDATE).
4. **Date alignment** — yfinance bars index by trading date in TPE. `_twse_close_utc(d)` always produces the same UTC instant for date `d` regardless of when the collector ran. This guarantees ON CONFLICT correctly de-dupes.
5. **Weekend/holiday no-data** — yfinance returns empty for those dates; collector exits 1 with "no rows to upsert" log line (matches futures_oi pattern).
6. **Empty ticker list file** — collector fails early with clear error.

### Out of scope (deferred)
- Auto-sync of ticker list between repos (manual snapshot for v1)
- Coverage > 926 tickers (Pilot_Reports universe only for v1)
- Backfill > 1 year (user explicitly opted for 1Y; can be re-run for more history later via `--start-date 2020-01-01`)
- Renaming the existing empty `stock_ohlcv_1m` view (it's a 1-minute aggregate over a never-built hypertable; not our concern)
- Replacing institutional_stock.close_price with the new table (institutional_stock is a different dataset and keeps its own close_price field)

---

## Files to create / modify

### In `/Users/lulala/Documents/coding/database/` (PR #1)

| File | Action |
|---|---|
| `sql/migrations/2026-06-17-stock-daily-ohlcv.sql` | **NEW** — CREATE TABLE + hypertable + index |
| `scripts/collectors/stock_daily_ohlcv.py` | **NEW** — ~280 LOC, mirrors `fx_daily.py` |
| `scripts/stock_daily_ohlcv_scheduler.sh` | **NEW** — ~80 LOC, two daily fires |
| `scripts/collectors/tw_electronics_tickers.txt` | **NEW** — 926 tickers, one per line |
| `tests/test_stock_daily_ohlcv.py` | **NEW** — mirrors `test_fx_daily.py`, ~180 LOC |
| `docker-compose.yml` | **EDIT** — add `tmf-stock-daily-collector` service block after `tmf-fx-collector` |
| `scripts/ops/local_ci.sh` | **EDIT** — add `test_stock_daily_ohlcv` to phase test list |

### In `/Users/lulala/Documents/coding/My-TW-Coverage/` (PR #2)

| File | Action |
|---|---|
| `scripts/smart_money_analysis.py` | **EDIT** — rewrite `fetch_ohlcv_universe()` to read DB, add `--ohlcv-source` flag |
| `scripts/sync_tickers_to_collector.py` | **NEW** — small helper to emit `tw_electronics_tickers.txt` from Pilot_Reports |
| `analysis/smart_money_2026-06-17.md` | **OUTPUT** — first DB-backed run, expect < 5s |
| `docs/plans/2026-06-17-stock-daily-ohlcv-collector.md` | **NEW** — copy of this plan per CLAUDE.md DevOps trail |

---

## Verification

### PR #1 (database/) end-to-end

1. **Schema migration applied:**
   ```bash
   docker exec trading-timescaledb psql -U tmf -d tmf_market_data -f /docker-entrypoint-initdb.d/2026-06-17-stock-daily-ohlcv.sql
   # Or via psql piping if not auto-applied
   docker exec trading-timescaledb psql -U tmf -d tmf_market_data -c "\d stock_daily_ohlcv"
   # Expect: 9 columns, PK on (ts, symbol, source_close_tz), hypertable confirmed
   ```

2. **Unit tests:**
   ```bash
   cd /Users/lulala/Documents/coding/database
   python3 -m pytest tests/test_stock_daily_ohlcv.py -v
   # All green
   ```

3. **Dry-run single day:**
   ```bash
   docker compose build tmf-stock-daily-collector
   docker compose up -d tmf-stock-daily-collector
   docker exec tmf-stock-daily-collector python /opt/tmf/scripts/collectors/stock_daily_ohlcv.py \
       --date 2026-06-16 --dry-run
   # Expect: ~900 rows printed (some delisted skip), no DB write
   ```

4. **Live single day:**
   ```bash
   docker exec tmf-stock-daily-collector python /opt/tmf/scripts/collectors/stock_daily_ohlcv.py \
       --date 2026-06-16
   docker exec trading-timescaledb psql -U tmf -d tmf_market_data -c \
       "SELECT COUNT(*) FROM stock_daily_ohlcv WHERE ts::date = '2026-06-16';"
   # Expect: ~900 rows
   ```

5. **1-year backfill:**
   ```bash
   docker exec tmf-stock-daily-collector python /opt/tmf/scripts/collectors/stock_daily_ohlcv.py \
       --start-date 2025-06-17 --end-date 2026-06-17
   docker exec trading-timescaledb psql -U tmf -d tmf_market_data -c \
       "SELECT symbol, MIN(ts)::date, MAX(ts)::date, COUNT(*) FROM stock_daily_ohlcv WHERE symbol IN ('3019','2455','6668') GROUP BY symbol;"
   # Expect each: first ~ 2025-06-17, last ~ 2026-06-17, count ~ 250
   ```

6. **Scheduler restart:**
   ```bash
   docker compose restart tmf-stock-daily-collector
   docker logs tmf-stock-daily-collector --tail 25
   # Expect: "Starting stock daily OHLCV scheduler" + initial run + correct sleep_until until next fire
   ```

7. **Spot-check vs yfinance independent:**
   - Pick 3019 2026-06-16: DB close should equal yfinance 164.00 within 0.01
   - Pick OTC ticker 8016 (.TWO): DB volume should equal yfinance volume

### PR #2 (My-TW-Coverage) end-to-end

8. **smart_money_analysis.py with DB-backed BB scanner:**
   ```bash
   python3 scripts/smart_money_analysis.py --as-of 2026-06-16 --window 20
   # Expect: wall-time < 10s (vs prior ~75s)
   # Expect: Section 8 output matches prior PR's output for same as_of
   #   (3019/2455/6668 in Buy, 6784/3664/5248 in Avoid)
   ```

9. **yfinance fallback flag:**
   ```bash
   python3 scripts/smart_money_analysis.py --as-of 2026-06-16 --window 20 --ohlcv-source yfinance
   # Expect: behaves identically to legacy path (~60s, hits yfinance)
   ```

10. **Independent reconcile** (matches earlier 3-layer verification work):
   - DB-backed scanner BBW(3019) = 12.4673 (matches independent recompute)
   - DB-backed scanner 5D 外資(3019) = +14.06 億 (matches DB raw query)

If 1–10 all pass, both PRs merge: `database/` first, then `My-TW-Coverage/` with the dependency on the table existing.
