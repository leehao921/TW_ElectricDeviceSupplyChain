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
- [MLCC_008004_technical_deep_dive](concepts/MLCC_008004_technical_deep_dive.md) — 永久技術 reference:規格命名陷阱 + 技術門檻 4 維度 + Murata GRM011 SKU 詳表 + 006003 next-gen
- [MLCC_008004_TW_verification](concepts/MLCC_008004_TW_verification.md) — 6/1 驗證版:3090 升 #1, 新增 3030 德律 + 3189 景碩;TW Ni paste 0 玩家為結構性卡點;隱藏 R&D = 1/5
- [Vera_Rubin_BOM](concepts/Vera_Rubin_BOM.md) — VR200 12 細類 BOM (DB store);+62.6% YoY vs GB300;CCL +265% / PCB +234% / Connector +200%;TW alpha: 2330/2383/3037/2313/3533

## Trading

- [positions](trading/positions.md) — 00763U @ 31.47 cost · take-profit ladder 36.5/37.5/39/41 · stop 34/33/31
- [playbooks](trading/playbooks.md) — TWD breach 31.80 · DXY macro sensitivity (β −1.47) · Basis extreme short · 00763U ladder · Pair trade rules

## Research (詳細研究 slice, subordinate to concepts)

`vault/research/008004/` — 11 個 unit slice 支撐 MLCC_008004 系列概念頁 (各 200-400 行, 全部 sourced):
- [01_spec_and_global_leaders](research/008004/01_spec_and_global_leaders.md) — 規格 + Big-4 量產 + Murata GRM011 SKU 詳表
- [02_tw_mid_2327_2492](research/008004/02_tw_mid_2327_2492.md) — TW 中游 2327/2492 對 008004 exposure (零)
- [03_tw_niche_3026_6173](research/008004/03_tw_niche_3026_6173.md) — TW 利基 3026/6173 (與 008004 反方向)
- [04_tw_upstream_materials](research/008004/04_tw_upstream_materials.md) — TW 上游 BaTiO₃ + paste
- [05_tw_distributors_3090_8043](research/008004/05_tw_distributors_3090_8043.md) — TW 代理通路 3090/8043
- [06_downstream_and_takeaway](research/008004/06_downstream_and_takeaway.md) — 下游 BOM + pair trade + 風險
- [07_distributors_deep](research/008004/07_distributors_deep.md) — 8043/3090 深度驗證 (6/1)
- [08_upstream_deep](research/008004/08_upstream_deep.md) — 6173/4760 深度驗證 (6/1)
- [09_hidden_candidates](research/008004/09_hidden_candidates.md) — TW 隱藏候選 (3030 德律 / 3189 景碩)
- [10_rd_pipeline](research/008004/10_rd_pipeline.md) — 2327/2492 R&D pipeline 6 維度驗證
- [11_catalyst_calendar](research/008004/11_catalyst_calendar.md) — Catalyst calendar 2026/6 – 2027/H1

`vault/research/vera_rubin_bom/` — 12 個 BOM 細類 slice (Unit 16-27, 共 ~3000 行) 支撐 Vera_Rubin_BOM 概念頁:
- [16_gpu_silicon](research/vera_rubin_bom/16_gpu_silicon.md) — Rubin GPU TSMC N3P + CoWoS-L 4x reticle (+57%)
- [17_cpu_silicon](research/vera_rubin_bom/17_cpu_silicon.md) — Vera ARM Olympus 88 cores (+86%)
- [18_hbm4](research/vera_rubin_bom/18_hbm4.md) — HBM4 8-stack 12-Hi 22 TB/s (+67%, price-driven)
- [19_dram_ssd](research/vera_rubin_bom/19_dram_ssd.md) — LPDDR5X 27TB + SSD 774TB
- [20_passives](research/vera_rubin_bom/20_passives.md) — MLCC + 鉭電容 $4,335 (+171%)
- [21_pcb_hdi](research/vera_rubin_bom/21_pcb_hdi.md) — PCB +234% (Megtron 9 + HVDC backplane)
- [22_ccl](research/vera_rubin_bom/22_ccl.md) — CCL +265% (M6→M8)
- [23_abf](research/vera_rubin_bom/23_abf.md) — ABF +82% (Morgan Stanley anchor)
- [24_power](research/vera_rubin_bom/24_power.md) — 800V HVDC sidecar (+32%)
- [25_cooling](research/vera_rubin_bom/25_cooling.md) — Liquid cooling +12% (anchor)
- [26_connectors_network](research/vera_rubin_bom/26_connectors_network.md) — NVLink 6 + 224G (+200%)
- [27_optical_chassis](research/vera_rubin_bom/27_optical_chassis.md) — 800G+1.6T + CPO <15% 試樣

`vault/research/cleanup/` — repo 整理 audit 報告 (2026-06-01):
- [pilot_audit](research/cleanup/pilot_audit_2026-06-01.md) — Pilot_Reports 品質 (1734/1735 clean, 1 ticker 3622 < 8 wikilinks)
- [untracked_audit](research/cleanup/untracked_audit_2026-06-01.md) — 27 untracked files 分類 (a/b/c/d)
- [system_audit](research/cleanup/system_audit_2026-06-01.md) — 14 stale plans + 21 worktrees + /tmp leftover

## Inbox (Redis → Vault weekly dumps)

- (no dumps yet — first sync scheduled for next Sunday 22:00 TWT)

## Meta

- [schema](meta/schema.md) — Vault conventions, frontmatter, page categories, workflows (ingest/query/lint)
- [log](log.md) — Chronological vault event log

## Entities

Vault `entities/` holds 1-line stubs that link back to `../Pilot_Reports/{Industry}/{Ticker}_{name}.md` (no duplication). Populate on demand when a ticker becomes deeply analyzed (e.g., 4 ticker deep-dives 5/12 already in `Pilot_Reports/`; stub here when next referenced).

## External raw sources (NOT in vault, linked from concepts)

- `../Pilot_Reports/` — 926 ticker .md (raw research)
- `../themes/` — 29 thematic supply chain .md (added Vera_Rubin.md 6/1, MLCC.md 5/26, 邊緣運算.md 5/20)
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
| concepts | 9 |
| trading | 2 |
| inbox | 1 (2026-W20 snapshot) |
| meta | 2 |
| entities | 0 (on-demand) |
| **Total** | **20** |
