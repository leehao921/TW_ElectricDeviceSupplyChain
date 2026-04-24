# Transform `My-TW-Coverage` → Taiwan Electronics Supply-Chain Knowledge Platform

## Context

The repo (now pushed to `github.com/leehao921/TW_ElectricDeviceSupplyChain`) currently holds 1,735 Taiwan-ticker Markdown reports spanning 98 sectors — 87 of which are non-electronics (banks, food, textiles, retail, etc.). The user wants to:

1. **Narrow scope** to Taiwan 電子類股 supply chain only — semiconductor upstream/downstream, IC design houses, PCB, passive components, packaging/testing, equipment/materials.
2. **Fuse knowledge with live data** by combining three existing assets:
   - Markdown reports + wikilinks (this repo — the semantic layer)
   - `trading-timescaledb` Docker container at `localhost:5432` (the quantitative layer — ticks, trades, institutional flows, OFI, options IV)
   - `knowledge-platform-*` Docker stack (FalkorDB `:6380` + pgvector Postgres `:5433` — the graph & embedding layer)
3. **Add an ingestion layer** for scheduled news and fundamentals (MOPS 重大訊息, CNA/經濟日報/工商時報 RSS, Yahoo+Google News, FinMind, TWSE 證交所公開資料).
4. **Expose AI-agent research tools via MCP** so an LLM agent can answer "which tickers are exposed to [[CoWoS]] and have had material disclosures this week, and how did their prices move?"

Architectural reference: `/Users/lulala/Documents/coding/Knowledge_manager` — reuse its Graphiti+FalkorDB+Schema-Registry pattern with a new `group_id="tw-electronics"` and a dedicated Postgres DB to avoid schema collisions.

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│   TW_ElectricDeviceSupplyChain (this repo — semantic layer)         │
│                                                                     │
│   Pilot_Reports/  themes/  WIKILINKS.md  network/  scripts/         │
│         │                                                           │
│         │ (supply-chain facts, wikilinks, themes)                   │
│         ▼                                                           │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │  INGESTION DAEMON (APScheduler, Docker)                  │     │
│   │  ingestion/scheduler.py                                  │     │
│   │    • 08:30  MOPS 重大訊息 crawler                          │     │
│   │    • 09:00  TWSE 證交所 (三大法人、融資融券、成交資訊)          │     │
│   │    • hourly CNA / 經濟 / 工商 RSS                          │     │
│   │    • 4×/day Yahoo + Google News per electronics ticker   │     │
│   │    • daily   FinMind monthly-revenue + shareholding      │     │
│   │    • weekly  rebuild WIKILINKS.md + themes/ + graph      │     │
│   └──────────────────────────────────────────────────────────┘     │
│         │                             │                             │
│         ▼                             ▼                             │
└─────────┼─────────────────────────────┼─────────────────────────────┘
          │                             │
┌─────────▼──────────┐      ┌───────────▼──────────────────────────┐
│ trading-timescaledb│      │   knowledge-platform-*  (reused)      │
│ (READ-ONLY from    │      │   ┌──────────────────────────────┐   │
│  this platform)    │      │   │ FalkorDB :6380               │   │
│                    │      │   │   group_id="tw-electronics"  │   │
│ ticks, trades,     │      │   │   Nodes: Company, Ticker,    │   │
│ institutional_*,   │      │   │          Tech, Material,     │   │
│ stock_ofi,         │      │   │          Theme, NewsEvent    │   │
│ iv_*, signals,     │      │   │   Edges: SUPPLIES, USES,     │   │
│ futures_ohlcv,     │      │   │          COMPETES, EXPOSED_TO│   │
│ market_snapshots   │      │   └──────────────────────────────┘   │
│                    │      │   ┌──────────────────────────────┐   │
│                    │      │   │ Postgres :5433               │   │
│                    │      │   │   NEW DB: tw_electronics     │   │
│                    │      │   │     news_items (+pgvector)   │   │
│                    │      │   │     mops_disclosures         │   │
│                    │      │   │     twse_daily_metrics       │   │
│                    │      │   │     finmind_fundamentals     │   │
│                    │      │   │     ingest_runs              │   │
│                    │      │   └──────────────────────────────┘   │
└────────────────────┘      └───────────────────────────────────────┘
          ▲                             ▲
          │                             │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────────────────────────────┐
          │  MCP SERVER: tw-electronics-research                │
          │  mcp_server/server.py  (FastMCP stdio)              │
          │                                                     │
          │  • list_tickers(sector?, theme?)                    │
          │  • get_report(ticker)                               │
          │  • find_tickers_exposed_to(wikilink)   → graph      │
          │  • get_supply_chain(ticker, depth)     → graph      │
          │  • get_recent_news(ticker, days)       → pg + vec   │
          │  • search_news_semantic(query, k)      → pgvector   │
          │  • get_mops_disclosures(ticker, days)  → pg         │
          │  • get_price_history(ticker, range)    → timescale  │
          │  • get_institutional_flow(ticker, days)→ timescale  │
          │  • get_theme_cohort(theme)             → files+graph│
          └─────────────────────────────────────────────────────┘
                         ▲
                         │ stdio
                         │
                  Claude Code agent
```

**Key reuse decisions:**
- **Do not duplicate Graphiti code.** Import from the existing `Knowledge_manager/mcp_servers/graphiti_server.py` helpers or call its MCP — partition by Graphiti `group_id`.
- **Do not duplicate embeddings.** Keep Ollama + `bge-m3` as-is.
- **Add a new Postgres DB** (`tw_electronics`) on the same `knowledge-platform-postgres-1` container to keep schemas separate from the personal knowledge platform.

---

## Implementation Plan

### Phase 0 — Preflight (no code yet)

1. Confirm `knowledge-platform-postgres-1` exec works with user `knowledge` and can `CREATE DATABASE tw_electronics`.
2. Confirm `trading-timescaledb` read access with user `tmf` / DB `tmf_market_data` from the host.
3. Sanity-check which containers in the `tmf-*` stack actually populate the tables we want to read (`ticks`, `institutional_daily`, `stock_ofi`). Note any restarting/unhealthy ones (`tmf-tick-collector` and `tmf-futures-ohlcv-collector` were restarting — flag to user but do not try to fix as part of this plan).

### Phase A — Scope prune (electronics-only)

**Sectors to KEEP (11, ~1,115 reports)**: `Semiconductors`, `Semiconductor Equipment & Materials`, `Electronic Components`, `Computer Hardware`, `Communication Equipment`, `Consumer Electronics`, `Electronics & Computer Distribution`, `Electrical Equipment & Parts`, `Specialty Industrial Machinery`, `Software - Infrastructure`, `Scientific & Technical Instruments`.

**Delete** all other 87 folders under `Pilot_Reports/`. Git history retains them; no archive repo per user decision.

Update:
- `CLAUDE.md` — rewrite preamble to reflect electronics-only focus; keep wikilink rules unchanged.
- `README.md` — update description, counts, and purpose.
- `task.md` — regenerate batch list to reference only electronics tickers.
- `scripts/build_wikilink_index.py`, `scripts/build_themes.py`, `scripts/build_network.py` — run after prune so `WIKILINKS.md`, `themes/`, `network/graph_data.json` reflect the new corpus.
- `scripts/audit_batch.py` — no code change; just re-run against remaining batches.

Then: `git commit -m "refactor: narrow scope to Taiwan electronics supply chain"` and push to `personal` remote.

### Phase B — Ingestion & storage layer

New top-level folder: `ingestion/`.

**New Postgres schema** (`tw_electronics` DB on `knowledge-platform-postgres-1`):

```sql
-- ingestion/migrations/001_init.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE news_items (
  id           BIGSERIAL PRIMARY KEY,
  source       TEXT NOT NULL,            -- 'mops' | 'cna' | 'udn' | 'ctee' | 'yahoo' | 'google' | 'finmind'
  source_url   TEXT UNIQUE,
  published_at TIMESTAMPTZ NOT NULL,
  title        TEXT NOT NULL,
  body         TEXT,
  tickers      TEXT[] NOT NULL DEFAULT '{}',  -- ['2330','2317']
  wikilinks    TEXT[] NOT NULL DEFAULT '{}',  -- ['CoWoS','AI 伺服器']
  embedding    vector(1024),
  ingested_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON news_items USING gin(tickers);
CREATE INDEX ON news_items USING gin(wikilinks);
CREATE INDEX ON news_items USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE mops_disclosures (
  id            BIGSERIAL PRIMARY KEY,
  ticker        TEXT NOT NULL,
  disclosure_ts TIMESTAMPTZ NOT NULL,
  category      TEXT,
  subject       TEXT NOT NULL,
  body          TEXT,
  source_url    TEXT UNIQUE,
  ingested_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON mops_disclosures (ticker, disclosure_ts DESC);

CREATE TABLE twse_daily_metrics (
  trade_date        DATE NOT NULL,
  ticker            TEXT NOT NULL,
  foreign_net       BIGINT,
  investment_trust_net BIGINT,
  dealer_net        BIGINT,
  margin_balance    BIGINT,
  short_balance     BIGINT,
  PRIMARY KEY (trade_date, ticker)
);

CREATE TABLE finmind_fundamentals (
  ticker          TEXT NOT NULL,
  report_month    DATE NOT NULL,     -- YYYY-MM-01
  monthly_revenue BIGINT,
  yoy_pct         NUMERIC,
  mom_pct         NUMERIC,
  PRIMARY KEY (ticker, report_month)
);

CREATE TABLE ingest_runs (
  id           BIGSERIAL PRIMARY KEY,
  job_name     TEXT NOT NULL,
  started_at   TIMESTAMPTZ NOT NULL,
  finished_at  TIMESTAMPTZ,
  status       TEXT NOT NULL,   -- 'ok' | 'fail' | 'partial'
  rows_written INT,
  error        TEXT
);
```

**New collectors** (one file per source, all async `httpx` + structured logging):

```
ingestion/
├── __init__.py
├── config.py                 # env loading, ticker universe (derived from Pilot_Reports/)
├── db.py                     # asyncpg pool, embed() helper calling Ollama bge-m3
├── universe.py               # scan Pilot_Reports/*/*.md → electronics ticker list
├── collectors/
│   ├── mops.py               # https://mops.twse.com.tw 重大訊息 crawler
│   ├── twse.py               # https://www.twse.com.tw/rwd/zh/fund/... 三大法人/融資融券
│   ├── rss_cna.py            # 中央社 CNA RSS
│   ├── rss_udn.py            # 經濟日報 RSS
│   ├── rss_ctee.py           # 工商時報 RSS
│   ├── yahoo_news.py         # Yahoo 股市 per-ticker
│   ├── google_news.py        # Google News RSS per-ticker
│   └── finmind.py            # FinMind free-tier API
├── ner.py                    # ticker+wikilink extraction from news body (regex + wikilink dict)
├── migrations/
│   └── 001_init.sql
└── scheduler.py              # APScheduler, runs all jobs, logs to ingest_runs
```

`config.py` reuses existing env pattern from Knowledge_manager. `db.py` reuses embedding call pattern — call `http://localhost:11434/api/embeddings` with `bge-m3`.

`ner.py` is the key link back to the semantic layer: for each news article, extract
- **tickers** — regex `\b\d{4}\b` filtered against `universe.py` ticker set
- **wikilinks** — string match against `WIKILINKS.md` vocabulary (~4,904 terms)

Then each news row carries `tickers[]` and `wikilinks[]` as arrays, making graph/report joins trivial.

### Phase C — Graph layer (Graphiti group)

Add `graph/` folder with a one-shot + incremental writer that pushes supply-chain facts into FalkorDB under `group_id="tw-electronics"`.

```
graph/
├── __init__.py
├── client.py                 # GraphitiClient wrapper, group_id="tw-electronics"
├── bootstrap.py              # read all Pilot_Reports/*.md → extract edges → add_episode()
└── incremental.py            # on news ingest, if high-confidence supply-chain edge, promote to graph
```

**Node types**: `Company`, `Ticker`, `Technology`, `Material`, `Theme`, `NewsEvent`.
**Edge types**: `SUPPLIES`, `USES`, `COMPETES_WITH`, `EXPOSED_TO`, `MENTIONED_IN`.

`bootstrap.py` parses the `## 供應鏈位置` and `## 主要客戶及供應商` sections (structure already documented in `CLAUDE.md`) into episode text Graphiti can ingest. Reuse its existing extraction prompts — do not re-implement.

### Phase D — MCP research server

New top-level folder `mcp_server/`. Single FastMCP stdio server; 10 tools (see architecture diagram).

```
mcp_server/
├── __init__.py
├── server.py                 # FastMCP tool definitions
├── tools/
│   ├── reports.py            # list_tickers, get_report, get_theme_cohort (reads Pilot_Reports + themes/)
│   ├── graph.py              # find_tickers_exposed_to, get_supply_chain (FalkorDB)
│   ├── news.py               # get_recent_news, search_news_semantic, get_mops_disclosures (pg + pgvector)
│   └── market.py             # get_price_history, get_institutional_flow (trading-timescaledb)
└── README.md                 # MCP tool reference
```

`market.py` opens a read-only asyncpg pool to `trading-timescaledb` using the `tmf` user — document that this is strictly read-only from this platform's perspective.

Register the MCP server in a **project-local** `.mcp.json` (NOT inject into Knowledge_manager's `.mcp.json`) so the two platforms stay independent. Example entry:

```json
{
  "mcpServers": {
    "tw-electronics-research": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/Users/lulala/Documents/coding/My-TW-Coverage",
               "mcp", "run", "mcp_server/server.py"],
      "env": {
        "PG_NEWS_DSN": "postgresql://knowledge:knowledge@localhost:5433/tw_electronics",
        "PG_TRADING_DSN": "postgresql://tmf:tmf_dev_2026@localhost:5432/tmf_market_data",
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6380",
        "GRAPHITI_GROUP_ID": "tw-electronics",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "EMBEDDING_MODEL": "bge-m3",
        "REPO_ROOT": "/Users/lulala/Documents/coding/My-TW-Coverage"
      }
    }
  }
}
```

### Phase E — Scheduler (Docker)

New Dockerfile + docker-compose.override.yml in repo root, joining the existing `knowledge-platform` network:

```
docker/
├── Dockerfile                # python:3.11-slim, installs ingestion/ + graph/
├── docker-compose.yml        # tw-electronics-scheduler service
└── .env.example              # TZ=Asia/Taipei, FINMIND_TOKEN=..., etc.
```

The scheduler container mounts the repo read-only and runs APScheduler with jobs defined in `ingestion/scheduler.py`. It uses `host.docker.internal` to reach `knowledge-platform-postgres-1` / `trading-timescaledb` if not on the same user-defined network; otherwise join both via `docker network connect`.

### Phase F — Docs, skills, CI

- `CLAUDE.md` — add new sections: "Ingestion pipeline", "MCP tools", "Reading trading data".
- `README.md` — document the new architecture + quickstart.
- `docs/plans/2026-04-22-electronics-platform.md` — commit a copy of this plan (per user's global `docs/plans/` rule).
- `.claude/skills/` — add `ingest-news`, `query-supply-chain`, `research-ticker` skills that wrap the MCP tools.
- `requirements.txt` — add `asyncpg`, `httpx`, `apscheduler`, `feedparser`, `beautifulsoup4`, `graphiti-core`, `fastmcp`, `python-frontmatter`.
- `.github/workflows/audit.yml` — run `scripts/audit_batch.py --all` on PR to catch wikilink regressions.

---

## Critical Files (created / modified)

| Action | Path | Purpose |
|---|---|---|
| DELETE | `Pilot_Reports/<87 non-electronics sectors>/` | Scope narrow |
| MODIFY | `CLAUDE.md`, `README.md`, `task.md` | Reflect new scope |
| RE-RUN | `scripts/build_wikilink_index.py`, `build_themes.py`, `build_network.py` | Regenerate indexes |
| CREATE | `ingestion/*` (see Phase B tree) | News + fundamentals collectors |
| CREATE | `ingestion/migrations/001_init.sql` | Postgres schema |
| CREATE | `graph/client.py`, `graph/bootstrap.py`, `graph/incremental.py` | Graph writes |
| CREATE | `mcp_server/server.py` + `mcp_server/tools/*` | 10 research tools |
| CREATE | `.mcp.json` (project-local) | Register MCP server |
| CREATE | `docker/Dockerfile`, `docker/docker-compose.yml` | Scheduler container |
| CREATE | `.github/workflows/audit.yml` | Wikilink regression CI |
| CREATE | `docs/plans/2026-04-22-electronics-platform.md` | Plan commit per global rule |

## Reused components (do NOT reimplement)

| From | Purpose |
|---|---|
| `Knowledge_manager/mcp_servers/graphiti_server.py` | Graphiti client setup, embedding pattern |
| `Knowledge_manager/src/schema_registry/` | If we need entity/relation validation — call via MCP |
| `trading-timescaledb` tables: `ticks`, `trades`, `institutional_daily`, `stock_ofi`, `iv_metrics`, `signals` | Market data — READ ONLY |
| Existing scripts: `add_ticker.py`, `update_financials.py`, `update_enrichment.py`, `discover.py`, `build_*` | Unchanged; continue to manage Markdown layer |
| `WIKILINKS.md` vocabulary (4,904 terms) | Drives NER in `ingestion/ner.py` |

---

## Verification Plan

End-to-end test after each phase:

**After Phase A (prune):**
```bash
ls Pilot_Reports/ | wc -l                          # expect 11
find Pilot_Reports -name "*.md" | wc -l            # expect ~1,115
python scripts/audit_batch.py --all -v             # no regressions
python scripts/build_wikilink_index.py             # WIKILINKS.md shrinks
```

**After Phase B (ingestion):**
```bash
docker exec knowledge-platform-postgres-1 psql -U knowledge -d tw_electronics -c "\dt"
# expect: news_items, mops_disclosures, twse_daily_metrics, finmind_fundamentals, ingest_runs

python -m ingestion.collectors.mops --since 7d     # smoke: prints N disclosures
python -m ingestion.collectors.rss_cna             # smoke: prints N articles
# row check:
docker exec knowledge-platform-postgres-1 psql -U knowledge -d tw_electronics \
  -c "SELECT source, COUNT(*) FROM news_items GROUP BY source;"
```

**After Phase C (graph):**
```bash
python -m graph.bootstrap                          # one-shot load
# verify in FalkorDB:
docker exec knowledge-platform-falkordb-1 redis-cli -p 6379 \
  GRAPH.QUERY graphiti 'MATCH (n:Entity {group_id:"tw-electronics"}) RETURN count(n)'
```

**After Phase D (MCP):**
Start a Claude Code session in this repo and confirm the MCP server shows up:
```
/mcp   → tw-electronics-research connected, 10 tools
```
Ask the agent:
> "Find every Taiwan ticker exposed to CoWoS that had a material disclosure in the last 14 days, and show last 5 sessions of institutional flow."

Expect it to chain `find_tickers_exposed_to("CoWoS")` → `get_mops_disclosures(ticker,14)` → `get_institutional_flow(ticker,5)`.

**After Phase E (scheduler):**
```bash
docker compose -f docker/docker-compose.yml up -d tw-electronics-scheduler
docker logs -f tw-electronics-scheduler            # watch first scheduled fire
docker exec knowledge-platform-postgres-1 psql -U knowledge -d tw_electronics \
  -c "SELECT job_name, status, rows_written FROM ingest_runs ORDER BY started_at DESC LIMIT 20;"
```

**End-to-end demo** (the acceptance test):
In a Claude Code session here, run the prompt:
> "Find the top 10 electronics tickers with rising institutional accumulation over the last 5 sessions AND at least one [[CoWoS]] or [[HBM]] news mention this week. Summarize each with its supply-chain position."

This should execute — and if it does, the platform works.

---

## Known Risks & Mitigations

1. **`tmf-tick-collector` and `tmf-futures-ohlcv-collector` are restarting** — flag to user separately; NOT a dependency of this plan (we only read the tables, we don't author them).
2. **FinMind free tier has rate limits** — back off + cache in `finmind_fundamentals`. Fail soft.
3. **NER precision on news** — first pass uses regex+dict, not ML. Acceptable for v1; monitor false-positive ticker tagging via `audit_batch.py`.
4. **Graphiti ingest is LLM-expensive** — cap bootstrap to 1,115 electronics reports only; run off-hours.
5. **Docker container reaching host services** — use `host.docker.internal` and test explicitly in Phase E; alternative is joining `knowledge-platform_default` network.
6. **Deleting 620 non-electronics reports is irreversible from the working tree** — confirmed by user; git history retains them. Push commit BEFORE any further destructive changes.

---

## Phasing for delivery

| Phase | Rough scope | Why in this order |
|---|---|---|
| A | Prune non-electronics | Clean corpus first — every downstream step indexes this set |
| B | Ingestion layer | Data flowing end-to-end before graph/MCP |
| C | Graph bootstrap | Uses corpus from A and runs once — cheap to redo |
| D | MCP server | Needs B+C for non-trivial queries |
| E | Scheduler | Last — stabilizes everything built above |
| F | Docs & CI | Trailing, after the system works |

Each phase ends with a commit on `master`, pushed to `personal` remote. No PR since this is a solo repo.
