---
type: project
status: completed
last_updated: 2026-05-15
---

# Completed Projects (Archive)

## 2026-05-15 · 3-year Asia market panel + FX covariance + HTML dashboard
**Plan:** `/Users/lulala/.claude/plans/lovely-sparking-dijkstra.md` (previous version)
**Outcome:** 13 indices × 762 days + 10 FX × 780 days in TimescaleDB + Parquet. 4-chart HTML dashboard. Key finding: [[TXF]]–[[DXY]] 60d β = **−1.47** (2026-05-16) vs 3y 平均 β = **−0.37** → 4× regime shift (數值與 [[covariance_panel]] 同步)。
**Deliverables:** 9,560 + 7,776 + 416 rows in 3 new tables. 14 Parquet files. 1 dashboard. 2 reports. 6 scripts.
**Lesson:** Several yfinance tickers were dead (^TPX → 1306.T, 399006.SZ → 159915.SZ, CNH=X → CNY=X); proxy substitution + 10:1 split forward-adjust handled. TAIFEX scrape was Big5-blocked; ^TWII proxy worked fine. **3y daily covariance is dominated by KS11 (KOSPI) + N225 (Nikkei) — both correlation r > 0.6 (注: r 為相關係數, 非 β; β_60d for [[DXY]] 見上, 數值為 −1.47/−0.37). USD/TWD is near-zero static corr (CBC defends band).**

## 2026-05-12 · 4-stock deep-dive (3706 / 2449 / 5269 / 5469)
**Outcome:** Updated `Pilot_Reports/Computer Hardware/3706_神達.md`, `Semiconductors/2449_京元電子.md`, `Semiconductors/5269_祥碩.md`, `Electronic Components/5469_瀚宇博.md` with primary sources + 16-30 wikilinks each.
**Key facts captured:** 3706 GB200 NVL72 確認 (法說會 何繼武 quote); 2449 NVIDIA AI 測試 >90%; 5269 Techpoint US$390M 併購驅動 +66% YoY; 5469 訂單能見度 2027 H1.

## 2026-05-12 · Quant screen + sector heatmap + database gap fix
**Outcome:** 105 passers from 674 reports, sector heatmap, 5/5–5/11 institutional flow backfill. Fixed `tmf-institutional-collector` capture-all bug (5/5 commit `b99fc3f`).
**Deliverables:** `scripts/screen_quant.py`, `scripts/sector_heatmap.py`, `analysis/reports/2026-05-12_quant_screen.md`, `analysis/reports/2026-05-12_quant_screen.csv` (105 rows).

## 2026-05-12 · PCA factor decomposition (3481 群創 → FOPLP basket)
**Outcome:** Identified glass-substrate-vs-ABF rotation factor (PC2 of pure ODM PCA on 8 stocks: PC1 59.45%, PC2 15.43%). Ingested 3 emergent_factor_baskets to Postgres `tw_electronics`.

## 2026-05-12 · 2317 鴻海 + 6669 緯穎 upstream/downstream PCA
**Outcome:** Pure ODM PCA on 2317/2382/3231/6669/2376/2356/3706/4938 identified "Pure AI vs iPhone dilution" factor (PC2). 6669 緯穎 loading −0.795 (purest AI). 2317 +0.193 (mixed). Ingested as `pure_ai_vs_iphone_dilution_2026_05` basket.

## 2026-05-15 · Cross-session messaging + LLM-maintained vault
**Plan:** `/Users/lulala/.claude/plans/lovely-sparking-dijkstra.md` (current)
**Outcome:** `claude:inbox` Redis stream + `vault/` 12-page wiki + boot protocol + lint tooling. Every new Claude session auto-reads inbox + active projects + preferences at start.
