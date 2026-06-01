---
type: research
status: draft
last_updated: 2026-06-01
source_unit: 14
tags: [cleanup, untracked, git_hygiene]
---

# Unit 14: Untracked Files Categorization (27 files)

Source: `git status --short | grep '^??'` run against main repo
`/Users/lulala/Documents/coding/My-TW-Coverage` on 2026-06-01.
27 top-level entries; several are directories holding multiple files
(actual file count is ~50). Recursive expansion shown where relevant.

## TL;DR — top 3 actions

1. **Commit (a) immediately** — 4 vault scripts + 2 themes are CLAUDE.md
   contractual dependencies. Without them `vault_session_boot.py` and the
   cron pipeline cannot run; concept pages reference `themes/UAV.md` and
   `themes/邊緣運算.md` via wikilinks. One feature commit per logical group.
2. **Commit (b) in three batched commits** — (i) `analysis/` Asia panel
   dashboard + reports + 3 panel scripts (one self-contained Phase 3–6
   feature), (ii) `vault/concepts/*.md` (5 concept pages already referenced
   by index/log), (iii) `vault/{meta,projects,trading,user,inbox}/` (vault
   skeleton the CLAUDE.md spec mandates).
3. **Add `data/` and `vault/.obsidian/` to `.gitignore`** — parquet/HTML
   artefacts are regenerable from scripts in (a)/(b); Obsidian workspace
   config is per-user. Move (d) ingestion scripts to coordinator for a
   "still in use?" call before tracking.

## (a) TRACK 必須 (核心 vault 依賴) — 6 files

| Path | Reason | Suggested commit subject |
|---|---|---|
| `scripts/claude_msg.py` | CLAUDE.md §"Cross-session messaging shortcuts" calls this directly. Drives `claude:inbox` Redis stream. Without it boot prints nothing. | `feat(scripts): add claude_msg.py cross-session Redis messaging CLI` |
| `scripts/vault_session_boot.py` | CLAUDE.md §"Boot sequence" mandates this as FIRST tool call every session. MEMORY.md `feedback_session_boot_protocol.md` reinforces. | `feat(scripts): add vault_session_boot.py — mandatory session boot summary` |
| `scripts/vault_lint.py` | CLAUDE.md §"Lint cadence" wires this to Sun 22:00 cron. Surfaces orphans / stale claims / index drift. | `feat(scripts): add vault_lint.py — weekly vault health checker` |
| `scripts/redis_to_vault.py` | CLAUDE.md §"Weekly Redis → Vault sync" wires this to same cron. Drains Redis stream + Postgres `signal_alerts` → `vault/inbox/YYYY-WW.md`. | `feat(scripts): add redis_to_vault.py — weekly Redis→vault drain` |
| `themes/UAV.md` | Referenced by `vault/concepts/edge_ai_inference.md` frontmatter (`related: [..., ../../themes/UAV.md, ...]`) and by Edge AI narrative ("相關主題: [[UAV]]"). | `feat(themes): add UAV supply-chain theme (28 cos, gov procurement)` |
| `themes/邊緣運算.md` | Referenced by `vault/concepts/edge_ai_inference.md` `related:` list as primary theme. Anchors NVIDIA ACIE narrative cited in concept page. | `feat(themes): add 邊緣運算 (Edge AI inference) theme — Jetson/SOM/IPC` |

## (b) TRACK 應該 (有價值) — 19 files (across 4 dir groups)

### b.1 Asia covariance panel (Phase 3–6 self-contained feature) — 7 files

| Path | Reason | Suggested commit subject |
|---|---|---|
| `scripts/fetch_asia_panel.py` | Phase 3.1 — yfinance fetch for 13 Asia indices + 10 FX pairs. Input to covariance pipeline. | (combine below) |
| `scripts/validate_asia_panel.py` | Phase 3.2 — TWT anchoring, z-score outlier flag, UPSERT to `asia_index_daily`/`fx_daily`. | (combine below) |
| `scripts/compute_asia_covariance.py` | Phase 5 — produces cov_3y / corr_3y / rolling β / regime shifts. Concept `vault/concepts/covariance_panel.md` cites these outputs. | (combine below) |
| `analysis/dashboard_builder.py` | Phase 6 — Plotly + Jinja2 HTML dashboard (TAIEX candle + corr heatmap + cluster matrix + TXF-TAIEX basis). | (combine below) |
| `analysis/dashboards/2026-05-15_asia_panel/index.html` | Rendered dashboard output (266 KB self-contained HTML). Already symlinked as `latest`. | (track this one snapshot for reference; future renders → gitignore) |
| `analysis/reports/2026-05-15_asia_market_covariance.md` | TXF-anchored 3y correlation write-up; cited from `vault/concepts/covariance_panel.md`. | (combine below) |
| `analysis/reports/2026-05-15_asia_market_panel_audit.md` | Ingestion audit (per-symbol rows, missing, anchoring decisions). | (combine below) |

Suggested single commit for b.1:
`feat(asia-panel): Phase 3–6 Asia covariance pipeline + 2026-05-15 report`

(Optionally split into two: `feat(scripts): asia panel fetch/validate/cov` + `feat(analysis): dashboard_builder + 2026-05-15 asia covariance report`.)

### b.2 Vault concept pages — 5 files

| Path | Reason | Suggested commit subject |
|---|---|---|
| `vault/concepts/TXF.md` | Active concept; frontmatter `related: [DXY.md, covariance_panel.md, ../trading/playbooks.md]`. Foundational anchor concept. | `feat(vault): add TXF/DXY/covariance_panel/FOPLP/edge_ai concept pages` |
| `vault/concepts/DXY.md` | Active concept; back-reffed by TXF + covariance_panel. | (same commit) |
| `vault/concepts/covariance_panel.md` | Active concept linking to Phase 3–6 outputs (b.1). | (same commit) |
| `vault/concepts/FOPLP.md` | Monitoring concept; `related: [../projects/active.md, ../../themes/FOPLP.md]`. FOPLP theme already tracked (cf. recent commit `cf91522 feat(themes): add FOPLP/...`). | (same commit) |
| `vault/concepts/edge_ai_inference.md` | Monitoring concept; references UAV + 邊緣運算 themes from (a). | (same commit) |

### b.3 Vault skeleton (CLAUDE.md mandated structure) — 10 files

| Path | Reason | Suggested commit subject |
|---|---|---|
| `vault/meta/schema.md` | CLAUDE.md §"Vault structure" lists this as conventions/frontmatter/workflows spec. | `feat(vault): add meta/projects/trading/user/inbox skeleton (boot dependencies)` |
| `vault/projects/active.md` | `vault_session_boot.py` prints this in boot summary (CLAUDE.md §"Boot sequence" step 2). | (same commit) |
| `vault/projects/pending.md` | Companion to active.md per schema. | (same commit) |
| `vault/projects/completed.md` | Companion to active.md per schema. | (same commit) |
| `vault/trading/positions.md` | Boot step 4 — "Open trading positions". | (same commit) |
| `vault/trading/playbooks.md` | Referenced by TXF concept (`related: [..., ../trading/playbooks.md]`). | (same commit) |
| `vault/user/preferences.md` | Boot step 3 — "User preferences (style + hard rules)". | (same commit) |
| `vault/user/profile.md` | Companion to preferences.md per schema. | (same commit) |
| `vault/user/tools.md` | Companion to preferences.md per schema. | (same commit) |
| `vault/inbox/2026-W20.md` | Output of `redis_to_vault.py`; one weekly snapshot worth tracking as reference. Future weekly drains → `.gitignore` or `git add -f`. | (same commit; future entries: evaluate per-week) |

## (c) GITIGNORE (生成物 / 暫存) — 2 entries (12 files)

| Path | Reason | .gitignore pattern |
|---|---|---|
| `data/` (8 parquet files incl. `data/raw/`) | All `*.parquet` are regenerated by `scripts/fetch_asia_panel.py`, `scripts/validate_asia_panel.py`, `scripts/compute_asia_covariance.py`. Sizes 7 KB – 517 KB. Source of truth is `trading-timescaledb` (per CLAUDE.md "authoritative Taiwan market-data source"). | `data/*.parquet`<br>`data/raw/` |
| `vault/.obsidian/` (5 JSON files) | Per-user Obsidian workspace config (app.json, appearance.json, core-plugins.json, community-plugins.json, graph.json). Not part of canonical vault content. | `vault/.obsidian/` |

Recommended `.gitignore` additions:

```gitignore
# Asia panel pipeline outputs — regenerable from scripts/{fetch,validate,compute}_asia_*.py
# Source of truth is trading-timescaledb (see CLAUDE.md "Purpose")
data/*.parquet
data/raw/

# Obsidian per-user workspace config (vault content stays tracked)
vault/.obsidian/
```

## (d) EVALUATE (需用戶確認) — 2 files

| Path | 開頭內容摘要 | 建議 |
|---|---|---|
| `ingestion/news_collector.py` | "Phase 4: RSS news collector. ... UPSERTs into `market_news` ... idempotent." Has `feedparser` import. | **ASK COORDINATOR**: is the `market_news` table still populated by this script, or was it superseded by another collector? If active → track as `feat(ingestion): add RSS news_collector for market_news`. If dead → delete instead of tracking. dashboard_builder.py references "news event vertical lines" so something feeds news. |
| `ingestion/txf_backfill.py` | "Phase 2: TXF/TAIEX hybrid backfill. ... yfinance ^TWII + TAIFEX TXF daily scrape best-effort ... compute_basis." | **ASK COORDINATOR**: dashboard_builder.py Phase 6 mentions "TXF-TAIEX basis line (skipped with placeholder if no basis data)" → backfill may already be needed. Likely TRACK if Phase 2 still runs; if superseded by `trading-timescaledb` collector → delete. Per MEMORY `feedback_no_duplicate_infra.md`, verify it doesn't duplicate an existing `tmf-*` collector before tracking. |

Both files look complete (not WIP stubs) and follow the same Phase numbering as the b.1 panel scripts, suggesting they're part of the same project. Default recommendation if coordinator can't reach user: **TRACK both** under `feat(ingestion): Phase 2 TXF backfill + Phase 4 news collector` — they're cheap to keep and the alternative (silently dropping working code) is worse than the alternative (carrying a small amount of dead code).

## 統整 cleanup actions

Suggested commit sequence (coordinator to execute, NOT this unit):

1. `git add scripts/claude_msg.py scripts/vault_session_boot.py scripts/vault_lint.py scripts/redis_to_vault.py` → 4 separate commits or 1 grouped commit `feat(scripts): add vault session boot/lint/messaging/redis-drain CLIs`.
2. `git add themes/UAV.md themes/邊緣運算.md` → `feat(themes): add UAV + 邊緣運算 themes (Edge AI / drone narratives)`.
3. `git add scripts/fetch_asia_panel.py scripts/validate_asia_panel.py scripts/compute_asia_covariance.py analysis/dashboard_builder.py analysis/dashboards/ analysis/reports/2026-05-15_asia_market_*.md` → `feat(asia-panel): Phase 3–6 Asia covariance pipeline + 2026-05-15 dashboard`.
4. `git add vault/concepts/{TXF,DXY,covariance_panel,FOPLP,edge_ai_inference}.md` → `feat(vault): add 5 concept pages (TXF/DXY/covariance/FOPLP/edge_ai)`.
5. `git add vault/meta/ vault/projects/ vault/trading/ vault/user/ vault/inbox/` → `feat(vault): add boot-dependency skeleton (meta/projects/trading/user/inbox)`.
6. Append to `.gitignore` the `data/*.parquet`, `data/raw/`, `vault/.obsidian/` patterns → `chore(gitignore): exclude regenerable parquet + obsidian workspace`.
7. **DEFER**: `ingestion/news_collector.py`, `ingestion/txf_backfill.py` — coordinator confirms "still in use" then either tracks or deletes.

Total expected commits: 6 grouped (5 feature + 1 chore) + 1 deferred decision.

## Sources

- `git status --short | grep '^??'` (27 entries) — main repo `/Users/lulala/Documents/coding/My-TW-Coverage` at 2026-06-01 13:20 TWT.
- `head -10 themes/UAV.md themes/邊緣運算.md vault/concepts/*.md analysis/reports/2026-05-15_asia_market_*.md` — frontmatter verification.
- `head -20 scripts/{claude_msg,vault_session_boot,vault_lint,redis_to_vault,fetch_asia_panel,validate_asia_panel,compute_asia_covariance}.py analysis/dashboard_builder.py ingestion/{news_collector,txf_backfill}.py` — docstring/purpose verification.
- `cat .gitignore` — existing rules reviewed (already excludes `analysis/reports/*.pdf`, `*.html`, `tick_*.csv`, etc; consistent with Asia panel HTML being a deliberate exception worth tracking once).
- `ls vault/.obsidian/` — confirmed 5 workspace JSON files, no vault content.
- `ls data/` and `ls data/raw/` — confirmed 11 parquet files totalling ~1.4 MB, all regenerable.
- CLAUDE.md §"Boot sequence", §"Vault structure", §"Lint cadence", §"Weekly Redis → Vault sync" — authoritative spec for vault dependencies.
- MEMORY.md `feedback_session_boot_protocol.md`, `reference_cross_session_inbox.md`, `feedback_no_duplicate_infra.md` — confirm script criticality and ingestion-dedup caveat.
