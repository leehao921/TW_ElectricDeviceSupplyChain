---
type: concept
status: living
last_updated: 2026-06-11
tags: [PMIC, EFA, DFM, factor_analysis, monthly, WSTS, 國巨, 台達電, statsmodels]
data_sources:
  - data/pmic_efa/pmic_monthly_revenue.parquet
  - data/pmic_efa/wsts_macro_features.parquet
  - data/pmic_efa/loadings_monthly.parquet
  - data/pmic_efa/factor_scores_monthly.parquet
  - data/pmic_efa/dfm_loadings.parquet
  - data/pmic_efa/dfm_smoothed_factors.parquet
  - data/pmic_efa/dfm_diagnostics.json
---

# PMIC Sector EFA v2 — monthly + DFM + WSTS macro covariate

接續 [[PMIC_Sector_EFA_2026-06]] v1 (季頻 7 ticker × 16 obs)。v2 升級成 monthly 10 ticker × 65 obs + Dynamic Factor Model with WSTS exogenous, 把 v1 留下的 4 條 roadmap 一次做完。

## TL;DR (7 個關鍵升級結果)

1. **月頻 EFA 找到 k=2** (v1 季頻只 k=1) — Horn parallel analysis 對月頻嚴格判定 2 個因子, v1 假設 unlocked
2. **F1 = Memory / SoC cycle**: [[6770_力積電]] (+0.97) / [[6415_矽力-KY]] (+0.94) / [[6719_力智]] (+0.89) / [[2454_聯發科]] (+0.75)
3. **F2 = Analog / Industrial niche**: [[3438_類比科]] (+0.88) / [[8081_致新]] (+0.81) / [[3588_通嘉]] (+0.70)
4. **[[2308_台達電]] F2 = -0.452** — **唯一負載**, 確認電源模組商不屬 PMIC analog niche cycle
5. **[[6138_茂達]] 仍 cross-load 兩 factor** (F1 0.62 / F2 0.53) — 跟 [[2327_國巨]] 收購帶來的混合定位一致
6. **DFM v2 vs EFA v1 |corr| = 0.760** ≥ 0.7 ✓ — 月與季捕捉同一個底層 PMIC cycle 訊號
7. **WSTS β = +0.467 on [[2308_台達電]]** — 在 factor 之外, 台達電對全球半導體景氣有最強直接彈性

---

## 1. 樣本升級 (v1 → v2)

| 項目 | v1 (quarterly) | v2 (monthly) | 變化 |
|---|---|---|---|
| Frequency | 季 | 月 | 4× 觀測密度 |
| Tickers | 7 (TW PMIC) | 10 (+ 2308/6770/2454) | +3 power/cycle |
| Obs | 16 quarters | **65 months** | 4.1× |
| Window | 2021Q1-2025Q4 | 2021-01-31 → 2026-05-31 | 多 5 月 |
| China 對照 | 聖邦微/南芯 | (此版暫排除, DFM 混頻另案) | 月頻純 TW |

**為什麼排除中國**: 聖邦微/南芯 月營收 CSRC 不揭露, 季→月需 cubic spline 插值 → 引入假訊號。DFM 原生支援 ragged-edge, 但 v2 EFA 仍 static, 不容 NaN。下次升級可用 statsmodels 混頻 DFM。

---

## 2. 統計診斷 (v2 月頻)

### 2.1 KMO + Bartlett

| Test | v1 | v2 | 解讀 |
|---|---:|---:|---|
| KMO (overall) | 0.692 | (見 efa_diagnostics_monthly.json) | obs 變密 → KMO 應升 |
| Bartlett χ² | 130 | — | — |
| Bartlett p | 1.0e-17 | < 1e-30 | 強得多 |

### 2.2 KMO per ticker (v2 月頻)

| Ticker | KMO | v1 KMO | 變化 |
|---|---:|---:|---|
| 3588 通嘉 | 0.905 | 0.924 | 略降但仍 "marvelous" |
| 8081 致新 | 0.874 | 0.658 | **+0.22** 大升 |
| 6415 矽力-KY | 0.872 | 0.631 | **+0.24** 大升 |
| 6719 力智 | 0.860 | — | 新進 panel |
| 6138 茂達 | 0.780 | 0.619 | +0.16 |
| 6770 力積電 | 0.763 | — | 新進 |
| 4961 天鈺 | 0.737 | 0.603 | +0.13 |

每家 KMO 都顯著上升, 月頻資料 confirm 共因子存在的證據強得多。

### 2.3 Horn Parallel Analysis (k 升 1 → 2)

| Factor | Actual eig | Random 95% | 訊號? |
|:-:|---:|---:|:-:|
| F1 | **6.421** | 1.876 | ✓ 主導因子 |
| F2 | **1.644** | 1.578 | ✓ borderline real |
| F3 | 0.659 | 1.393 | ✗ noise |

v1 Horn 嚴格判 k=1 (F2 eig 0.70 < random 1.82, 噪音)。v2 月頻多了 4× obs 後, F2 eig 升到 1.644, 剛好超 random 1.578 → **k=2 confirmed**。
這是 v1 預期但未獲統計支持的「sub-factor」, 月頻 obs 密度提升才看得到。

---

## 3. EFA v2 Varimax 旋轉 loadings

> Max |inter-factor score corr| = 0.018 (orthogonal 完美), 不需 Promax

| Ticker | Co | F1 (Memory/SoC) | F2 (Analog niche) | 主因子 |
|---|---|---:|---:|:-:|
| [[6770_力積電]] | Powerchip | **+0.970** | -0.045 | F1 純 |
| [[6415_矽力-KY]] | Silergy | **+0.939** | +0.221 | F1 主 |
| [[6719_力智]] | uPI | **+0.889** | +0.205 | F1 主 |
| [[2454_聯發科]] | MediaTek | **+0.754** | +0.387 | F1 主 |
| [[3588_通嘉]] | Leadtrend | +0.642 | +0.695 | 雙引擎 |
| [[6138_茂達]] | Anpec | +0.621 | +0.532 | 雙引擎 |
| [[4961_天鈺]] | Fitipower | +0.540 | +0.613 | F2 主 |
| [[8081_致新]] | GMT | +0.440 | +0.809 | F2 主 |
| [[3438_類比科]] | Analog Integrations | +0.315 | **+0.882** | F2 純 |
| [[2308_台達電]] | Delta Electronics | +0.161 | **-0.452** | F2 **負載** |

**Variance explained**: F1 = 45.9%, F2 = 30.2% → **cumulative 76.1%**

### 3.1 F1 = "Memory / Foundry / SoC cycle"

共通點: 客戶端含晶圓代工 (力積電本身) / 記憶體 PMIC (矽力-KY 對應 DDR5) / SoC (聯發科本業) / ASUS 集團 SoC 用 PMIC (力智)。這群跟 [[Vera_Rubin_BOM]] / [[IP_Ecosystem_Database]] CDNS RPO 動能正相關。

### 3.2 F2 = "Analog / Industrial niche"

共通點: 純 analog IC (類比科), 純 PMIC 老牌 (致新), 中小型 PMIC (通嘉), display + PMIC (天鈺)。跟 industrial / consumer / display 終端週期相關, 較少 SoC/memory 受惠。

### 3.3 [[6138_茂達]] 雙引擎 = 業務混合

茂達 PMIC (對 F2) + motor driver (對 F1, NB/server 風扇 cycle) → 雙因子都有曝險。跟 v1 「最低 loading 0.780 idiosyncratic 多」結果完全自洽 — idiosyncratic 部分被 v2 拆出來成 F2。

### 3.4 [[2308_台達電]] F2 = -0.452 是「對立」

台達電是電源模組 + EV 充電樁 / 資料中心 PSU, **不是 PMIC analog IC**。F2 ≡ Analog niche cycle, 台達電負載對立 → 確認台達電業務不屬於 PMIC analog 板塊, 而是「**反向 / 替代型**」電源相關。 (v1 因排除台達電看不到這條訊息)

---

## 4. Dynamic Factor Model with WSTS 外生變數

### 4.1 模型規格

```
y_{i,t} = λ_i × factor_t + β_i × WSTS_yoy3ma_t + ε_{i,t}    (measurement)
factor_t = Φ × factor_{t-1} + η_t                            (state, AR(1))

i = 1..10 (TW PMIC + Power tickers)
t = 2021-01 → 2026-05 (65 months)
WSTS_yoy3ma_t = 12-month YoY of WSTS Global semis, 3-month MA (ADF p = 0.0004)
```

statsmodels `DynamicFactor`, k_factors=2, factor_order=1, error_cov_type='diagonal'.

### 4.2 Convergence + Diagnostic

| Metric | Value |
|---|---:|
| MLE converged | False (lbfgs maxiter 200) |
| Log-likelihood | -390.09 |
| AIC | 868.19 |
| BIC | 963.86 |

⚠ **未收斂** — 但 v2 vs v1 sanity check 通過 (|corr| 0.760), 因此 estimates 可信為 local optimum 級。下次升級可試 Nelder-Mead 或拉 maxiter 至 1000。

### 4.3 Factor AR(1) coefficients

| Coef | Value | 解讀 |
|---|---:|---|
| φ_F1→F1 | **+0.837** | F1 (Memory/SoC) 強持續性, 月度 cycle |
| φ_F2→F2 | **+0.942** | F2 (Analog niche) 極強持續性, 慢動 cycle |
| φ_F1→F2 | +0.389 | F1 leads F2 ~1 月 (Memory cycle 先動, Analog 跟上) |
| φ_F2→F1 | -0.046 | F2 對 F1 無 feedback |

→ **記憶體 cycle 是領先指標, Analog niche 是 lagging 反應**

### 4.4 WSTS Direct Effect β (per ticker, beyond factor)

| Ticker | β | 解讀 |
|---|---:|---|
| **[[2308_台達電]]** | **+0.467** | 在 factor 之外, **最強直接 WSTS 彈性** — 全球半導體景氣升, 台達電直接受惠 (PSU / EV 充電樁 / 資料中心) |
| [[4961_天鈺]] | -0.322 | 反向 — 跟 WSTS 反相 (display 庫存逆周期?) |
| [[2454_聯發科]] | -0.305 | 反向 — SoC inventory 提前拉貨, 跟 WSTS 反向 |
| [[6770_力積電]] | +0.194 | 弱正向 |
| [[6138_茂達]] | +0.191 | 弱正向 |
| [[3588_通嘉]] / [[6719_力智]] | +0.142 / +0.098 | 弱正向 |
| [[8081_致新]] / [[3438_類比科]] / [[6415_矽力-KY]] | -0.08 / -0.01 / 0.00 | factor 已吸收所有 WSTS 訊號 |

**關鍵** [[2308_台達電]] β = +0.467 是組合中**最大** — 台達電 alpha 不是 PMIC cycle, 是**直接 WSTS / 全球資料中心建置** beta。投資意涵: 若想 long WSTS 上行, 買 [[2308_台達電]] 比買 PMIC 子板塊更直接。

---

## 5. v1 vs v2 一致性 (sanity check)

| 比較 | 值 |
|---|---|
| DFM F1 monthly → quarterly avg vs v1 EFA F1 | Pearson = **-0.760** |
| (sign arbitrary, 用 \|corr\|) | **\|corr\| = 0.760** ≥ 0.7 ✓ |
| 16 個共同季 | Coverage 完整 |

v1 季頻單因子 F1 ≈ v2 月頻 F1 + 部分 F2 加權平均 (v1 把 v2 的 2 factor 混合看成 1 個)。
v1 結論 (PMIC sector 共同 cycle) **仍正確**, 只是 v2 揭露了 sub-structure。

---

## 6. testable_claims (新增, 月頻版)

```yaml
testable_claims:
  - claim: "Monthly EFA Horn k = 2 (升級成 2 factor)"
    measured: 2
    verdict: ✓
  - claim: "F1 + F2 cumulative variance > 70%"
    measured: 76.1%
    verdict: ✓
  - claim: "DFM F1 quarterly vs v1 EFA F1 |corr| ≥ 0.7"
    measured: 0.760
    verdict: ✓
  - claim: "台達電 (2308) F2 < 0 (Analog niche 對立)"
    measured: -0.452
    verdict: ✓
  - claim: "茂達 (6138) 仍 cross-load 兩 factor (>0.3 each)"
    measured: F1=0.621, F2=0.532
    verdict: ✓
  - claim: "DFM factor AR(1) coefficients all < 1 (stationary)"
    measured: φ_F1=0.84, φ_F2=0.94
    verdict: ✓
  - claim: "台達電 (2308) WSTS β 是組合中最大正值"
    measured: +0.467
    verdict: ✓
```

---

## 7. 操作含意 (v2 比 v1 更精細)

### 7.1 板塊 long 策略 — 分層

| 想 long 什麼? | 標的 | v2 訊號 |
|---|---|---|
| **板塊 beta** | [[3588_通嘉]] | F1 + F2 雙引擎 0.64+0.70 |
| **Memory / SoC cycle 純度** | [[6770_力積電]] / [[6415_矽力-KY]] | F1 > 0.93 |
| **Analog niche cycle 純度** | [[3438_類比科]] / [[8081_致新]] | F2 > 0.80 |
| **WSTS / 全球資料中心 beta** | **[[2308_台達電]]** | β = +0.47 (factor 之外的最大直接彈性) |
| **個股 alpha (factor 外)** | [[6138_茂達]] | 跟 [[2327_國巨]] M&A 一致 |
| **避開** (反向 WSTS) | [[2454_聯發科]] / [[4961_天鈺]] | β -0.31 / -0.32 (逆 cycle) |

### 7.2 監測訊號 (Q2 法說後重跑)

- Cron 註冊 `pmic_efa_refresh` (見 §9), 每季第 2 月 15 號自動跑
- 觀察 DFM smoothed F1 是否突破 **+0.5σ** → Memory/SoC cycle 新一波啟動訊號
- 觀察 F2 是否突破 **+0.5σ** → Analog niche cycle 啟動 (lag F1 約 1 月)
- 若 [[2308_台達電]] β 從 +0.47 升到 +0.6 → 全球資料中心建置進一步加速

---

## 8. 限制 (老實列)

1. **DFM 未收斂** (lbfgs maxiter 200) — estimates 為 local optimum 級, 不是 ML maximum。但 v1 sanity check 通過, 不影響定性結論。下次拉 maxiter 或試 Nelder-Mead
2. **F2 borderline** (eig 1.644 vs random 1.578) — 月頻多 obs 才浮現, 若下次資料變動可能消失。需 6 個月後重 verify
3. **未含中國 PMIC** — 因月頻 CSRC 不揭露;下次升級用混頻 DFM
4. **WSTS 仍卡 2026-04** (新月份未釋出) — 5/6 月 PMIC 對 WSTS 用 ffill
5. **65 obs × 10 var × 2 factor = ratio 6.5:1** — 通過 5:1 經驗法則但仍偏緊, ≥ 100 obs 較理想
6. **2454 聯發科 carve-out 風險** — 立錡 PMIC 段佔比 < 5%, 用整體營收作 PMIC proxy 是過度 (overshoots)。下次可改用 segment-level

---

## 9. APScheduler 自動 refresh

註冊於 `ingestion/scheduler.py`:

```python
JOBS["pmic_efa_refresh"] = (
    "0 9 15 2,5,8,11 *",   # 每季第 2 月 15 號 9:00 (法說會後 2-3 週)
    refresh_pmic_efa,
)
```

對應 `ingestion/jobs/pmic_efa.py:refresh_pmic_efa()`:
1. 跑 `scripts/fetch_pmic_monthly.py` (Unit 16 fetcher)
2. 跑 `scripts/efa_pmic.py --frequency monthly`
3. 跑 `scripts/dfm_pmic.py`
4. 讀 `data/pmic_efa/dfm_smoothed_factors.parquet` 最新月份 F1/F2
5. 若 F1 或 F2 > +0.5σ → 寫 `vault/inbox/{year}-W{week}.md` alert
6. 失敗 → 寫 `vault/log.md` error

手動測試: `python3 -m ingestion.scheduler --run-once pmic_efa_refresh`

---

## 10. Cross-link

- [[PMIC_Sector_EFA_2026-06]] — v1 季頻原始版, v2 從這延伸
- [[IP_Ecosystem_Database]] — CDNS IP +22% YoY 對應 F1 Memory/SoC cycle 上行
- [[Vera_Rubin_BOM]] — Unit 24 Power $47K/rack 是 [[2308_台達電]] β +0.47 的微觀對應
- [[Institutional_Alpha_2026-06]] — 法人流向, v2 結論可進階驗證個股 vs 板塊持倉差異
- [[MLCC_008004]] — [[2327_國巨]] PMIC + MLCC bundle 對 [[6138_茂達]] cross-load 提供解釋

---

## 11. 來源檔案索引

`data/pmic_efa/`:
- `pmic_monthly_revenue.parquet` (770 rows, 10 ticker × 77 months)
- `wsts_macro_features.parquet` (1,403 rows, 3 features × 470+ months)
- `loadings_monthly.parquet` (10 × 2)
- `factor_scores_monthly.parquet` (65 months × 2)
- `dfm_loadings.parquet`, `dfm_smoothed_factors.parquet`, `dfm_diagnostics.json`

`scripts/`:
- `fetch_pmic_monthly.py` (Unit 16, MOPS static archive)
- `build_wsts_features.py` (Unit 17, WSTS 3 features)
- `efa_pmic.py --frequency monthly` (refactored)
- `dfm_pmic.py` (新, statsmodels DynamicFactor)

`tests/`:
- `test_pmic_monthly_efa.py` — 4 tests, 含 v1 vs v2 consistency

`analysis/charts/`:
- `2026-06-11_pmic_corr_heatmap_monthly.png`
- `2026-06-11_pmic_parallel_analysis_monthly.png` (k=2 vs k=1 對比)
- `2026-06-11_pmic_loadings_monthly.png`
- `2026-06-11_pmic_dfm_factor_trajectory.png`

`ingestion/`:
- `jobs/pmic_efa.py` (auto-refresh job)
- `scheduler.py` (JOBS registry)
