---
name: ingest-news
description: Trigger a one-off news/fundamentals ingestion job (mops, cna, udn, ctee, yahoo, google, finmind). Use when the user wants fresh news data pulled into the knowledge platform.
---

# Ingest News

Run a single ingestion collector on demand (normally APScheduler runs these on a cron). Writes rows into the `tw_electronics` Postgres database (`news_items`, `mops_disclosures`, `twse_daily_metrics`, `finmind_fundamentals`) and records the run in `ingest_runs`.

## Usage

```bash
python3 -m ingestion.scheduler --run-once <job>
```

## Job names

| Job | Source | What it writes |
|---|---|---|
| `mops` | MOPS 公開資訊觀測站 重大訊息 | `mops_disclosures` |
| `twse` | TWSE 證交所 三大法人 / 融資融券 | `twse_daily_metrics` |
| `cna` | 中央社 CNA RSS | `news_items` (source=cna) |
| `udn` | 經濟日報 UDN RSS | `news_items` (source=udn) |
| `ctee` | 工商時報 RSS | `news_items` (source=ctee) |
| `yahoo` | Yahoo 股市 per-ticker | `news_items` (source=yahoo) |
| `google` | Google News RSS per-ticker | `news_items` (source=google) |
| `finmind` | FinMind monthly revenue + shareholding | `finmind_fundamentals` |

## Examples

```bash
# Pull the latest MOPS disclosures right now
python3 -m ingestion.scheduler --run-once mops

# Pull CNA RSS
python3 -m ingestion.scheduler --run-once cna

# Refresh FinMind fundamentals
python3 -m ingestion.scheduler --run-once finmind
```

## Verify

```bash
docker exec knowledge-platform-postgres-1 psql -U knowledge -d tw_electronics \
  -c "SELECT job_name, status, rows_written, finished_at FROM ingest_runs ORDER BY started_at DESC LIMIT 5;"
```
