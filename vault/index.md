---
type: meta
status: living
last_updated: 2026-05-26
---

# Vault Index

Content-oriented catalog. Every vault page listed here with one-line summary. **Read this first** when answering a content question. Auto-rebuilt by `scripts/vault_lint.py --rebuild-index`.

## User

- [profile](user/profile.md) — TW retail trader, TXF main contract, Shioaji broker, 00763U position
- [preferences](user/preferences.md) — terse Chinese, opinionated, data-cited, no premature selling, β/σ verification rule
- [tools](user/tools.md) — Docker stack + MCP servers + scripts + Python deps

## Projects

- [active](projects/active.md) — Asia panel ✅ 5/15 · FOPLP basket monitoring · 00763U position · TXF watchlist · Vault & cross-session ✅ 5/15
- [pending](projects/pending.md) — Daily refresh cron · Bond+commodity panel · Intraday tick analysis · FalkorDB integration · Shioaji auto-order
- [completed](projects/completed.md) — Asia covariance 5/15 · 4-stock deep-dive 5/12 · Quant screen 5/12 · PCA factor decomposition 5/12 · Vault 5/15

## Concepts

- [TXF](concepts/TXF.md) — User's main contract; basis −591 點 5/15; DXY 60d β regime shift to −1.47
- [DXY](concepts/DXY.md) — Composition (EUR 57.6% + JPY 13.6% + ...); 5/15 close 99.05 (+1% week)
- [covariance_panel](concepts/covariance_panel.md) — 3y Asia panel, 13 indices + 10 FX, TWII-anchored; KOSPI +0.634 dominant
- [FOPLP](concepts/FOPLP.md) — Glass-substrate-vs-ABF rotation basket: LONG 3481/2408/2454, SHORT 8046/3037/3017
- [edge_ai_inference](concepts/edge_ai_inference.md) — Nano-tier (5-67 TOPS) competitor analysis; NVDA Q1 FY27 ACIE $37B catalyst; L1-L4 TW alpha paths
- [MLCC_008004](concepts/MLCC_008004.md) — 008004 (0.25×0.125mm) Big-4 獨占,TW 真實受惠 8043/3090 (Tier 1) > 6173/4760 (Tier 2);2327/2492 漲價 ≠ 008004 切入

## Trading

- [positions](trading/positions.md) — 00763U @ 31.47 cost · take-profit ladder 36.5/37.5/39/41 · stop 34/33/31
- [playbooks](trading/playbooks.md) — TWD breach 31.80 · DXY macro sensitivity (β −1.47) · Basis extreme short · 00763U ladder · Pair trade rules

## Inbox (Redis → Vault weekly dumps)

- (no dumps yet — first sync scheduled for next Sunday 22:00 TWT)

## Meta

- [schema](meta/schema.md) — Vault conventions, frontmatter, page categories, workflows (ingest/query/lint)
- [log](log.md) — Chronological vault event log

## Entities

Vault `entities/` holds 1-line stubs that link back to `../Pilot_Reports/{Industry}/{Ticker}_{name}.md` (no duplication). Populate on demand when a ticker becomes deeply analyzed (e.g., 4 ticker deep-dives 5/12 already in `Pilot_Reports/`; stub here when next referenced).

## External raw sources (NOT in vault, linked from concepts)

- `../Pilot_Reports/` — 926 ticker .md (raw research)
- `../themes/` — 28 thematic supply chain .md (added MLCC.md 5/26, 邊緣運算.md 5/20)
- `../analysis/reports/` — Dated analysis CSV + MD
- `../analysis/dashboards/latest/` — HTML covariance dashboard

## How to use this index

1. User asks content question → read this file
2. Drill into relevant page(s) under categories above
3. If new synthesis emerges → save as new concept page → update this index

## Page count by category

| Category | Pages |
|---|---:|
| user | 3 |
| projects | 3 |
| concepts | 6 |
| trading | 2 |
| inbox | 0 (dynamic) |
| meta | 2 |
| entities | 0 (on-demand) |
| **Total** | **16** |
