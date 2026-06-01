---
type: user
status: living
last_updated: 2026-05-15
related: [profile.md]
---

# User Tools + Stack Inventory

## Docker containers (always running)

| Container | Port | DB / Purpose |
|---|---:|---|
| `trading-timescaledb` | 5432 | `tmf_market_data` — TW market data (TIMESTAMPTZ Asia/Taipei) |
| `trading-redis` | 6379 | Streams (`tmf:stream:market`, `claude:inbox`), bar sync |
| `tmf-institutional-collector` | — | TWSE BFI82U + T86 → DB, runs 15:15 TWT daily |
| `tmf-redis-bar-sync` | — | Redis 1m bars → TimescaleDB `futures_ohlcv` |
| `tmf-redis-timescale-sync` | — | OFI / IV metrics → DB |
| `knowledge-platform-falkordb` | 6380 | Graphiti graph (`group_id="tw-electronics"`) |
| `knowledge-platform-postgres` | 5433 | `tw_electronics` DB (pgvector + signal_alerts) |

Repos:
- `/Users/lulala/Documents/coding/database/` — TimescaleDB + collectors + Docker compose
- `/Users/lulala/Documents/coding/My-TW-Coverage/` — analysis + Pilot_Reports + vault
- `/Users/lulala/Documents/coding/knowledge-platform/` — FalkorDB + Graphiti

## MCP servers (active in Claude Code)

| Server | Purpose |
|---|---|
| `mcp__postgres-tw-electronics` | Query `tw_electronics` Postgres DB (semantic search via pgvector) |
| `mcp__redis-trading` | Redis ops on port 6380 (NOT 6379 — separate instance for KB) |
| `mcp__claude-in-chrome` | Browser automation |
| `mcp__claude_ai_Canva` | Canva integration |
| `mcp__claude_ai_Gmail`, `Calendar`, `Drive` | Google workspace |
| `mcp__MCP_DOCKER__*` | Docker container management |

## Trading tools

- **Shioaji** (永豐證券 Python API) — login + place orders, has CA password
- **Slash command:** `/shioaji-login` for auth, then place orders via skill
- Reference: `/Users/lulala/.claude/plugins/cache/sinotrade-plugins/shioaji/`

## Python (project requirements)

`My-TW-Coverage/requirements.txt` includes:
- `yfinance>=0.2.0`, `pandas>=2.0.0`, `pyarrow>=14.0`
- `asyncpg`, `httpx`, `apscheduler`, `pydantic-settings`
- `feedparser` (RSS), `beautifulsoup4`, `lxml`
- `graphiti-core`, `falkordb` (graph layer)
- `fastmcp` (MCP server)
- `plotly>=5.20.0`, `jinja2>=3.1.0`, `scipy>=1.10`, `pytz>=2024.1` (added 2026-05-15)
- `redis>=5.0` (added 2026-05-15 for cross-session messaging)

## Custom scripts (`My-TW-Coverage/scripts/`)

| Script | Purpose |
|---|---|
| `add_ticker.py` | Generate new Pilot_Report + fetch financials |
| `update_financials.py` | Refresh 財務概況 (preserves enrichment) |
| `update_enrichment.py` | Re-research 業務簡介/供應鏈/客戶 |
| `update_valuation.py` | Refresh 估值指標 only |
| `discover.py` | Reverse search: buzzword → companies |
| `build_themes.py` | Generate themes/ supply chain maps |
| `audit_batch.py` | Quality check |
| `build_wikilink_index.py` | Rebuild WIKILINKS.md |
| `screen_quant.py` | Quant screener over Pilot_Reports |
| `sector_heatmap.py` | Sector heatmap from screen output |
| `fetch_asia_panel.py` | yfinance batch fetch 13 indices + 10 FX × 3y |
| `validate_asia_panel.py` | Outlier flag + TWT conversion + DB UPSERT |
| `compute_asia_covariance.py` | Static + rolling covariance, TXF-anchored β |
| **`claude_msg.py`** | **Cross-session Redis messaging** (NEW 2026-05-15) |
| `redis_to_vault.py` | Weekly Redis → vault/inbox sync (NEW 2026-05-15) |
| `vault_session_boot.py` | Session-start summary (NEW 2026-05-15) |
| `vault_lint.py` | Orphan / stale / contradiction detection (NEW 2026-05-15) |

## Custom analyses (`My-TW-Coverage/analysis/`)

- `dashboard_builder.py` — Plotly + Jinja2 HTML dashboard generator
- `dashboards/latest/index.html` — Asia panel covariance dashboard
- `reports/YYYY-MM-DD_*.md` — Dated analysis reports
