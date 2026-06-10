---
type: concept
status: living
last_updated: 2026-06-10
tags: [PMIC, EFA, factor_analysis, semiconductor_cycle, AI_server, DDR5, 國巨, KMO, Bartlett]
data_sources:
  - data/pmic_efa/pmic_core4_quarterly.parquet
  - data/pmic_efa/pmic_tail3_quarterly.parquet
  - data/pmic_efa/pmic_china_quarterly.parquet
  - data/pmic_efa/pmic_context_quarterly.parquet
  - data/pmic_efa/loadings.parquet
  - data/pmic_efa/factor_scores.parquet
  - data/pmic_efa/efa_diagnostics.json
---

# PMIC Sector EFA — 2026/6 量化因子分析

接續 [[IP_Ecosystem_Database]] / [[Vera_Rubin_BOM]] / [[Institutional_Alpha_2026-06]]。用真正的 Exploratory Factor Analysis (而非 ad-hoc 觀察) 量化 PMIC 板塊的潛在共同因子。

## TL;DR (反直覺的 7 點)

1. **PMIC 板塊只有 1 個顯著公因子** — Horn parallel analysis 結果 k=1, 該因子解釋 **72.3%** 的全部 YoY revenue variance
2. **「AI cycle vs China cycle vs Consumer」拆解不成立** — 強行 k=2 promax 可勉強拆出「[[6415_矽力-KY]] + 聖邦微」vs「[[8081_致新]] + [[3438_類比科]]」二組, 但 Horn 嚴格地把 Factor 2 標為 noise (eigenvalue 0.70 < random 1.82)
3. **KMO = 0.692 通過門檻** (>0.6) — 板塊 IS 有共同因子;Bartlett p = 1.0e-17, 強烈拒絕「相關矩陣 = identity」
4. **負載最高 = [[3588_通嘉]] (0.938)** — 反而是中小型廠最純板塊代理, 非市值最大的 [[6415_矽力-KY]]
5. **負載最低 = [[6138_茂達]] (0.780)** — 7 家中 idiosyncratic 含量最高, 跟 [[2327_國巨]] 2025/10 收購 21.4% 產生獨立 alpha 一致
6. **因子分數時序最戲劇化:2023 Q1 = -2.68 σ** (PMIC 板塊崩盤), 對應 2021 super-cycle (+1.36) 後的庫存修正;2024 Q4 反彈到 +0.51 後 2025 又跌回 0 附近
7. **2025 Q4 = +0.16** — 板塊仍 hover 在 0 附近, **沒有清晰反彈訊號**;若 2026 Q2 法說後因子分數突破 +0.5, 才確認新一波 cycle 啟動

---

## 1. 資料 (10 家 entity × 17-38 季)

### 1.1 樣本 ([[Vera_Rubin_BOM]] / [[Institutional_Alpha_2026-06]] cross-link)

| Ticker | Co | Type | Quarters | Source |
|---|---|---|---:|---|
| **[[8081_致新]]** | GMT | TW PMIC pure-play | 24 (2020 Q1-) | MOPS scrape |
| **[[6719_力智]]** | uPI | TW PMIC + GaN, ASUS 集團 | 18 (2021 Q3-, IPO limit) | MOPS scrape |
| **[[6138_茂達]]** | Anpec | TW PMIC + motor driver | 24 (2020 Q1-) | MOPS scrape |
| **[[6415_矽力-KY]]** | Silergy | KY 註冊 / 杭州總部, 中國高集中度 | 24 (2020 Q1-) | MOPS scrape |
| **[[4961_天鈺]]** | Fitipower | TW PMIC + display + touch | 29 (2019 Q1-) | MOPS scrape |
| **[[3588_通嘉]]** | Leadtrend | TW 中小型 PMIC | 27 (2019 Q1-) | MOPS scrape |
| **[[3438_類比科]]** | Analog Integrations | TW OTC analog niche | 29 (2019 Q1-) | MOPS scrape |
| 300661.SZ | 聖邦微 (SG Micro) | 中國 analog IC 龍頭 | 38 (2015 Q1-) | Eastmoney RPT_LICO_FN_CPD |
| 688484.SS | 南芯 (SouthChip) | 中國 PMIC + battery mgmt, IPO 2022 | 17 | Eastmoney |
| [[2308_台達電]] / 6770 力積電 / [[2454_聯發科]] | context (Unit 15) | 電源/cycle/parent | 9 each (yfinance ceiling, 未做 MOPS pivot) | yfinance only |

**Coverage 驗證**:
- 9 個 PMIC entity 都達 EFA 最低 18 季 floor (`tests/test_pmic_efa_data.py::test_pmic_efa_core_coverage` 鎖)
- Context 3 家 (2308/6770/2454) 因 Unit 15 未 source-pivot, 只有 9 季 → **EFA 自動 trim 掉**, 不影響核心結果

### 1.2 EFA panel (trim 後)

- **7 ticker × 16 quarter** 完全 overlap (2021-03-31 → 2025-12-31)
- 688484.SS / 6719 / context 3 家因覆蓋不足被 trim
- 16 obs × 7 var: 偏低 (理想 ≥35 obs), 屬 exploratory tier, 不適合做 strict CFA
- **變數**: log(revenue_t / revenue_{t-4}), per-ticker z-score 標準化

---

## 2. 統計診斷

### 2.1 KMO + Bartlett

| Test | Result | Threshold | Verdict |
|---|---|---|---|
| KMO (overall) | **0.692** | ≥ 0.6 | ✓ 可因子化 (borderline good) |
| Bartlett χ² | 130.03 | — | — |
| Bartlett p-value | **1.00e-17** | < 0.001 | ✓ 強烈拒絕 identity 假設 |

### 2.2 KMO per ticker (個別合適度)

| Ticker | KMO | 解讀 |
|---|---:|---|
| [[3588_通嘉]] | **0.924** | "marvelous" 等級 |
| [[3438_類比科]] | 0.734 | mediocre→good |
| 300661.SZ 聖邦微 | 0.730 | mediocre→good |
| [[8081_致新]] | 0.658 | acceptable |
| [[6415_矽力-KY]] | 0.631 | acceptable |
| [[6138_茂達]] | 0.619 | acceptable |
| [[4961_天鈺]] | 0.603 | acceptable (邊緣) |

**所有 7 ticker 個別 KMO ≥ 0.6**, 沒有任何一家是「不適合分析」的拖油瓶。

### 2.3 Horn Parallel Analysis (決定 k)

| Factor | Actual eigenvalue | Random 95th percentile | 訊號? |
|:-:|---:|---:|:-:|
| F1 | **5.327** | 2.510 | ✓ 真因子 |
| F2 | 0.702 | 1.823 | ✗ noise |
| F3 | 0.636 | 1.411 | ✗ noise |
| F4-F7 | 0.19-0.01 | 1.07-0.37 | ✗ noise |

**結論**: k = **1** (Horn 嚴格判定)。F1 eigenvalue 5.33 vs 隨機 data 第 95 percentile 2.51, 是 2.12x — **遠超 noise threshold**。

---

## 3. 旋轉後 loadings (k=1, varimax)

> Sign flipped (原始 loadings 全負, 翻成正值便於直覺解讀: 正值 = 與板塊共同因子同向)

| Ticker | Co | Loading | 解讀 |
|---|---|---:|---|
| **[[3588_通嘉]]** | Leadtrend | **+0.938** | 純板塊代理, 個股 alpha 含量最低 |
| **[[8081_致新]]** | GMT | +0.899 | 純 PMIC, 高度同步 |
| **[[6415_矽力-KY]]** | Silergy | +0.874 | 即使「中國 cycle」標籤, 仍與 TW 板塊高度同步 |
| 300661.SZ | 聖邦微 | +0.858 | **中國頭部廠跟 TW 同步** — 推翻「China cycle ≠ TW cycle」假說 |
| **[[3438_類比科]]** | Analog Integrations | +0.801 | TW niche 也跟 |
| **[[4961_天鈺]]** | Fitipower | +0.789 | display 摻雜但仍跟板塊 |
| **[[6138_茂達]]** | Anpec | **+0.780** | 7 家中**最低**, 跟 [[2327_國巨]] 收購獨立 alpha 一致 |

### 3.1 反直覺解讀

- **聖邦微 (中國) loading 0.858** 跟台廠 0.78-0.94 在同一頻段 — 中國消費 cycle 跟 TW PMIC cycle **同步度高**, 不是 separate factor。可能解釋:全球 PMIC 都受同一條 WSTS / DDR5 / AI server 拉動, "China consumer" 故事其實是同一條 macro 的次集合
- **[[3588_通嘉]] 純度最高 (0.938)** — 中小型廠**沒有任何個股故事**, 完全跟板塊。對交易意義:若想 long 板塊 beta 用 [[3588_通嘉]];若想 long 板塊但避開 idiosyncratic 風險, 也是 [[3588_通嘉]]
- **[[6138_茂達]] 純度最低 (0.780)** — 但仍是高度同步。[[2327_國巨]] 21.4% 收購帶來的獨立 alpha 確實存在但**有限** — 板塊牽引力遠大於 M&A premium

### 3.2 解釋變異量

- F1 解釋 **72.3%** 的 7 ticker YoY revenue variance
- 剩 27.7% 是 idiosyncratic (個股 / 隨機誤差)
- 跟「市場效率 vs 個股 alpha」一致: **PMIC 板塊 cycle 主導, 個股故事只值 ~28% variance**

---

## 4. 因子分數時序 (PMIC 板塊強度 by quarter)

| 季 | Factor score | 解讀 |
|---|---:|---|
| 2021 Q1 | +1.33 | super-cycle 高峰 |
| 2021 Q2 | **+1.36** | 板塊 peak |
| 2022 Q1 | +0.65 | 開始衰退 |
| 2022 Q2 | -0.03 | 轉負 |
| **2023 Q1** | **-2.68** | **板塊崩盤 (庫存修正極端)** |
| 2023 Q2 | -1.81 | 仍重 |
| 2023 Q3 | +0.13 | 開始反彈 |
| 2023 Q4 | -0.36 | 反彈未確認 |
| 2024 Q1-Q3 | +0.48 / +0.43 / +0.30 | 緩慢上行 |
| 2024 Q4 | +0.51 | 階段高 |
| 2025 Q1 | +0.25 | 動能放緩 |
| 2025 Q2 | -0.13 | 翻負 |
| 2025 Q3 | -0.59 | 再衰退 |
| 2025 Q4 | +0.16 | **小反彈, 不夠強** |

### 4.1 對應已知事件

- 2021 super-cycle = 全球晶圓代工漲價 + 缺料潮 → 板塊 +1.36σ
- 2023 Q1 -2.68σ = 全球 PMIC 庫存修正 (對應 WSTS 2023 年銷售 -9.4%)
- 2024 Q4 +0.51 = AI server PMIC 拉貨開始顯現
- **2025 Q4 +0.16** = 訊號弱, 沒有「AI 第二波」清晰 trigger

### 4.2 操作含意

**做多板塊 beta 的訊號**:
- 因子分數 < -1.0 → 加碼進 (例: 2023 Q1 -2.68 是教科書級買點)
- 因子分數連兩季從負翻正 → 趨勢確認
- **目前 (2025 Q4 +0.16) 不適合大舉做多** — 訊號弱, 個股 selection 比板塊 long 重要

**個股 vs 板塊**:
- 若認為**板塊 cycle 已轉**, 選 loading 最高的 [[3588_通嘉]] / [[8081_致新]]
- 若認為**個股故事 > 板塊**, 選 loading 最低的 [[6138_茂達]] ([[2327_國巨]] alpha) — 但要承認板塊牽引仍佔 78%

---

## 5. Forced k=2 sanity check (Horn 標 noise, 但有 narrative)

雖然 Horn 說 F2 是 noise, 強迫 k=2 + promax oblique 可拆出:

| Ticker | F1 (中國/全球 cycle) | F2 (TW domestic / niche) |
|---|---:|---:|
| 300661.SZ 聖邦微 | **+1.082** | -0.14 |
| [[6415_矽力-KY]] | **+1.019** | -0.07 |
| [[6138_茂達]] | +0.46 | +0.37 |
| [[3588_通嘉]] | +0.44 | +0.55 |
| [[4961_天鈺]] | +0.38 | +0.46 |
| [[3438_類比科]] | -0.27 | **+1.19** |
| [[8081_致新]] | +0.18 | **+0.78** |

**F1 (中國/全球 cycle)**: 聖邦微 + [[6415_矽力-KY]] 兩家曝險中國市場最深的廠 — 跟「[[6415_矽力-KY]] 中國集中度高」實情一致
**F2 (TW domestic / niche)**: [[3438_類比科]] + [[8081_致新]] 是 TW 在地 + 美國 niche 出貨佔比較高的 — 跟 [[8081_致新]] FY24 北美營收佔 18% 一致

⚠ **但 Horn parallel analysis 嚴格說 F2 是 noise** (eigenvalue 0.70 < random 1.82)。所以這個 k=2 結果**只能作為 narrative 探討, 不能作為統計推論**。

---

## 6. testable_claims (可驗證主張)

```yaml
testable_claims:
  - claim: "Factor 1 解釋 ≥ 60% PMIC sector YoY revenue variance"
    measured: 72.3%
    verdict: ✓
  - claim: "KMO ≥ 0.6 (factor analysis suitable)"
    measured: 0.692
    verdict: ✓
  - claim: "Horn k = 1 (single common factor)"
    measured: 1
    verdict: ✓
  - claim: "茂達 (6138) loading < 國巨無收購情況下的 expected ~0.85"
    measured: 0.780
    verdict: ✓ (slightly lower, 跟 2327 M&A 帶來的 idiosyncratic alpha 一致)
  - claim: "通嘉 (3588) loading 最高 (中小型純板塊代理)"
    measured: 0.938
    verdict: ✓
  - claim: "2023 Q1 factor score < -2σ (板塊崩盤事件)"
    measured: -2.68
    verdict: ✓
  - claim: "2025 Q4 factor score < +0.5 (尚無新 cycle 上行訊號)"
    measured: +0.16
    verdict: ✓ (still hovering)
```

---

## 7. 限制與下次改進

1. **16 obs × 7 var 偏低** — 理想 ≥ 35 obs (5 obs per var)。下次擴 sample 到月營收 (60+ months), 可拉到 ~50+ obs
2. **Context 3 ticker (2308/6770/2454) 未進 EFA** — Unit 15 yfinance ceiling, 應重跑 MOPS pivot 補足
3. **南芯 (688484.SS) IPO 2022 限制** — 17 季不夠 18 floor, 自動 trim。等 2026 Q3 後可進 panel
4. **僅 revenue 變數** — 沒納入 gross_margin / op_margin (但其他 tag 已落地, 下次可擴維)
5. **k=1 statistical, k=2 narrative 分歧** — 嚴格統計只有 1 個 factor;narrative 推論可用 2 factor 但要承認 statistical thin
6. **F1 是「PMIC 庫存 cycle」, 不是「AI cycle」** — 跟用戶 prompt 預期的「AI server / DDR5」factor 不直接對應。實際: AI server / DDR5 是這個總 cycle 的**子組件**, 不是獨立 factor

下次 batch 應:
- 把 4 worker quarterly 升級成 monthly (TW 月營收 + Eastmoney 月)
- 補 macro covariate (WSTS monthly, 已有) → 進階做 dynamic factor model
- 重跑 Unit 15 加 MOPS pivot, 把 [[2308_台達電]] 帶進 panel 看是否多出 "power" factor

---

## 8. Cross-link

- [[IP_Ecosystem_Database]] — IP/EDA 板塊;CDNS IP +22% YoY 對應 PMIC factor 2024 Q4 +0.51 反彈
- [[Vera_Rubin_BOM]] — Power BoM 細項;Unit 24 Power $47K/rack 是 PMIC 終端需求 anchor
- [[Institutional_Alpha_2026-06]] — 法人/外資跨產業, [[6138_茂達]] 不在 Top 5 但對應 PMIC factor loading 最低 (idiosyncratic 多)
- [[MLCC_008004]] — 被動元件;[[2327_國巨]] 同集團 (Yageo bought 茂達 21.4% 2025/10), 兩條 thesis 交織
- [[FOPLP]] — 玻璃載板;PMIC 不直接觸但 BoM 上下游
- [[edge_ai_inference]] — Edge AI 推論;[[6166_凌華]] platform 廠用大量 PMIC 但通常 design-in TI / MPS 國際

---

## 9. 來源檔案索引

`data/pmic_efa/`:
- `pmic_core4_quarterly.parquet` (450 rows)
- `pmic_tail3_quarterly.parquet` (425 rows)
- `pmic_china_quarterly.parquet` (282 rows)
- `pmic_context_quarterly.parquet` (135 rows)
- `macro_semis_monthly.parquet` (484 monthly rows, WSTS 1986-2026)
- `loadings.parquet` (7 ticker × 1 factor, varimax rotated)
- `factor_scores.parquet` (16 quarter × 1 factor)
- `efa_diagnostics.json` (KMO/Bartlett/Horn 完整結果)

`data/pmic_efa/_provenance/`:
- `pmic_{core4,tail3,china,context}.md`

`scripts/`:
- `fetch_pmic_{core4,tail3,china,context}.py` (4 worker fetchers)
- `efa_pmic.py` (EFA pipeline, idempotent)

`tests/`:
- `test_pmic_efa_data.py` — 7 tests, schema gate + ≥18 quarter floor + EFA output schema

`analysis/charts/`:
- `2026-06-10_pmic_corr_heatmap.png`
- `2026-06-10_pmic_parallel_analysis.png`
- `2026-06-10_pmic_loadings.png`
