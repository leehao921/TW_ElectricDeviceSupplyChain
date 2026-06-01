---
type: concept
status: monitoring
last_updated: 2026-06-01
related: [../../themes/Vera_Rubin.md, ../../themes/NVIDIA.md, ../../themes/AI_伺服器.md, ./MLCC_008004.md]
tags: [Vera_Rubin, VR200, BOM, NVIDIA, GB300, Morgan_Stanley, TSMC, CCL, ABF, MLCC, HBM4]
---

# Vera Rubin VR200 BOM — Trader Decision Page

> 12 個 BOM 細類拆解 + DB 存證 + TW alpha 排序。族群供應鏈圖見 [[../../themes/Vera_Rubin.md]]。底層研究見 `vault/research/vera_rubin_bom/{16-27}_*.md` (12 slices, ~3000 行)。

---

## TL;DR — 3 個關鍵 takeaway

1. **單櫃 BOM ~$13.17M vs GB300 $8.10M = +62.6% YoY** (本 batch 12 細類加總);[[Morgan Stanley]] 公開估 ~$7.8M (差距主要在 Optical scale-out 認定)
2. **YoY top 3 細類: CCL +265% / PCB +234% / Connector +200%** — TW 三雄寡占的細類獲利彈性最大 (2383 台光電 / 2313 華通 / 3533 嘉澤)
3. **800V HVDC 是架構革命**, 2308 [[台達電]] TW 唯一 reference design 供應, 但 silicon (GPU+CPU $4.2M) 才是 BOM 主導 (32% 占比)

---

## 12 細類 BOM 排序 (按 YoY % from high to low)

| Rank | 細類 | VR200 ($) | GB300 ($) | YoY | TW alpha # 1 |
|---:|---|---:|---:|---:|---|
| 1 | **CCL** | 38,400 | 10,520 | **+265%** | 2383 [[台光電]] |
| 2 | **PCB** | 390,400 | 117,000 | **+234%** | 2313 [[華通]] |
| 3 | **Connector** | 674,040 | 225,000 | **+200%** | 3533 [[嘉澤]] |
| 4 | **MLCC** | 4,335 | 1,600 | **+171%** | 8043 [[蜜望實]] / 3090 [[日電貿]] |
| 5 | **CPU** | 234,000 | 126,000 | **+86%** | 2330 [[TSMC]] |
| 6 | **ABF** | 199,800 | 109,620 | **+82%** ✓ MS | 3037 [[欣興]] |
| 7 | **HBM** | 1,440,000 | 864,000 | **+67%** | 1717 [[長興]] (周邊) |
| 8 | **GPU** | 3,960,000 | 2,520,000 | **+57%** | 2330 [[TSMC]] |
| 9 | **Optical** | 6,063,900 | 4,017,500 | **+51%** | 3163 [[波若威]] |
| 10 | **Cooling** | 120,780 | 107,675 | **+12%** ✓ MS | 3324 [[雙鴻]] |
| 11 | Memory | — | — | — | 8299 [[群聯]] (NAND) |
| 12 | Power | 46,845 | — | new | 2308 [[台達電]] |

> ✓ MS = [[Morgan Stanley]] anchor 對齊 (ABF +82% / Cooling +12% 是 Morgan Stanley 公開數字, 本 batch 復現)
> MLCC $4,335 vs Morgan Stanley anchor $4,300 (差 0.8%) ✓
> CCL +265% / Connector +200% / Optical +51% 為 worker 自行推估 (M8 升級 + NVLink 6 + 1.6T optics), 信度中等
> Memory 細類 GB300 baseline 缺失 (Unit 19 worker 用 tier string 而非 $ value), 只能定性比較

---

## TW Tier 1 alpha 排序 (跨 12 細類)

### 龍頭 (5/5 強度)

| Ticker | 公司 | 主要 BOM 路徑 | YoY 受惠 |
|---|---|---|---|
| **2330** | [[TSMC]] | GPU (N3P) + CPU (N3P) + CoWoS-L 4x reticle 寡占 | **+57% + +86%** |
| **2383** | [[台光電]] | M8 CCL OAM/UBB share 70-80% | **+265% (族群最強)** |
| **2313** | [[華通]] | GPU board HDI 24-26 層 Megtron 9 | **+234%** |
| **3037** | [[欣興]] | Rubin GPU ABF 主供 (Ibiden 之外唯一) | **+82%** |
| **3533** | [[嘉澤]] | SXM7 socket + UQD + 224G PAM4 | **+200%** |

### 直接受惠 (4/5)

- **2308** [[台達電]] — 800V HVDC sidecar reference design (TW 唯一)
- **3324** [[雙鴻]] — Vera Rubin cooling reference (Auras, MGX)
- **8043** [[蜜望實]] — [[Taiyo Yuden]] MLCC 獨家代理 (含 008004)
- **3090** [[日電貿]] — [[Samsung Electro-Mechanics]] 官方代理
- **6669** [[緯穎]] — NVL144 ODM (Meta/MS/AWS)
- **3711** [[日月光投控]] — HBM-on-CoWoS final assembly
- **2449** [[京元電子]] — KGSD test (AI 營收 75-77%)
- **4958** [[臻鼎-KY]] — PCB #1 + HVDC backplane 厚銅

---

## 為什麼 +62.6% 比 Morgan Stanley $7.8M 高?

我們的 batch 計算到 $13.17M, MS 估 ~$7.8M。差距 = $5.4M。可能原因:

1. **Optical $6.06M 細類偏高** — Unit 27 估 800G $2.6M + 1.6T $3.1M = $5.7M pluggable optics。MS 可能未把 scale-out 全網路 optics 算進「單機架 BOM」(只算 rack 內 NVLink + IB direct attach)
2. **HBM $1.44M 細類** — 對齊 wccftech 報導 (HBM4+LPDDR5X = $2M, 我們的 HBM 單獨 $1.44M 合理), 但 LPDDR5X Unit 19 沒給 $ 值
3. **GPU $3.96M 細類** — Unit 16 估 72 × $55K (Morgan Stanley est.), 合理
4. **CCL +265%** 偏高 — M6→M8 大幅升級, 但 ASP 差距可能沒這麼大

修正後保守版本估 (扣除 Optical 過度認列):**$7.5-9M / rack**, 與 Morgan Stanley $7.8M 一致範圍。

詳細 reconciliation 見 `analysis/reports/2026-06-01_vera_rubin_bom.md`。

---

## Pair Trade 思路

### Option A: LONG basket {2383 + 3037 + 2313 + 3533} (純 VR200 細類 alpha 集中)

- 2383 台光電 (CCL +265%) — VR200 M8 升級獨贏
- 3037 欣興 (ABF +82%, anchor 確認) — Rubin GPU 主供
- 2313 華通 (PCB +234%) — GPU board 24-26 層
- 3533 嘉澤 (Connector +200%) — SXM7 socket 寡占
- 預期持有 6-12 個月, 退場訊號 = VR200 量產延後

### Option B: LONG 2308 台達電 / Hedge SHORT 6669 緯穎

- 2308 台達電 = 800V HVDC sidecar reference (架構升級 sole supplier)
- 6669 緯穎 = ODM, 議價權弱, 純走量
- 對沖 macro 風險

### Option C: 對沖 2330 台積電 風險

- 2330 占 VR200 silicon ($4.2M = 32%) 主導
- 若 2330 已大漲, 改進 supplier proxy (2383 / 3037 / 2313) 彈性更大

---

## 退場訊號 / Risk events

| 事件 | Impact |
|---|---|
| **VR200 量產延後** (NVIDIA 季報 / GTC 公告) | 整族群 derate |
| **[[CPO]] 跳級, [[Murata]] 006003 量產** (2026 末 - 2027 H1) | 2383 台光電 (CCL M9 跳級?) + 8043/3090 008004 ASP cliff |
| **Vera CPU 良率 fail** | 整 platform 延後 |
| **中國 [[CCL]] 突破 M8** | 2383 derate |
| **NVIDIA 內製 ABF (Ibiden alone)** | 3037 受壓 |

---

## DB Query (內部使用)

```sql
-- 查看完整 12 細類對照
SELECT category,
  SUM(CASE WHEN platform='VR200' THEN total_value_usd END) AS vr200,
  SUM(CASE WHEN platform='GB300' THEN total_value_usd END) AS gb300,
  ROUND((SUM(CASE WHEN platform='VR200' THEN total_value_usd END) /
         NULLIF(SUM(CASE WHEN platform='GB300' THEN total_value_usd END), 0) - 1) * 100, 1) AS yoy_pct
FROM bom_components
WHERE platform IN ('VR200', 'GB300')
GROUP BY category ORDER BY yoy_pct DESC NULLS LAST;

-- 查單一 TW supplier 跨細類受惠
SELECT category, sub_category, total_value_usd, yoy_change_pct
FROM bom_components
WHERE supplier_tw_proxy ILIKE '%欣興%' AND platform='VR200';
```

---

## 觀察 catalyst (next 12 月)

> **6 月密集事件 (來自 [[../research/macro_calendar_2026-06]] YouTube 尼可拉斯楊Live精)**

| 時間 | 事件 | 對 thesis 影響 |
|---|---|---|
| **2026/6/1 (今天)** | **黃仁勳 [[Computex]] Taipei keynote** | **VR200 量產時程 / Rubin Ultra 預告 — 整個 BOM 數據 reality check** |
| **2026/6/3** | **[[Broadcom]] 財報** | AI 基建客戶 capex (custom ASIC vs NVIDIA 競爭) — 影響光通訊/NVLink supply chain |
| 2026/6/2-6/6 | [[Computex]] 2026 — VR200 量產時程確認 | 觸發短期動能 |
| **2026/6/9** | **[[Apple]] WWDC** | iPhone 17 + Apple Intelligence → 3711 [[日月光投控]] (Apple OSAT) + 2344 (NOR Flash) + 008004 PoP |
| **2026/6/10** | **美國 [[CPI]]** | 6月最重要單一數據, 影響 6/17 FOMC + risk-on/off |
| **2026/6/17-18** | **[[FOMC]] 利率決議** | 全球金融市場核心事件 — 影響 DXY/TWD + 整體 risk appetite |
| **2026/6/18** | **大型期權到期週高峰** | 機構避險 + 程式交易 → 波動放大,**Vera Rubin Tier 1 標的可能異常波動** |
| **2026/6/24** | **[[NVIDIA]] 股東大會 + [[Micron]] 財報 (同日!)** | **整月最重要 HBM4 cycle reality check** — 直接驗證 Unit 18 HBM4 +67% thesis + 2344 [[華邦電]] + 3711 [[日月光投控]] institutional alpha |
| 2026/6/27 | Russell 指數年度 rebalance | ETF 被迫換倉 (小型股機械式波動,影響中小型 Tier 2 標的) |
| 2026/8-9 | NVIDIA Q2 FY27 季報 — VR200 ramp 訊號 | beat → 加碼 basket |
| 2026/9 | iPhone 17 拆機 (008004 驗證) | 順便看 [[Murata]] 006003 訊號 |
| 2026/10/14-18 | [[CEATEC]] JAPAN — Murata 006003 公開 | ASP cliff timer 啟動 |
| 2026/11 | Q3 法說 (台廠 ODM/PCB/CCL) | VR200 訂單能見度真實揭露 |
| 2026/12-2027/H1 | VR200 量產出貨爬升 | Tier 1 basket 加碼窗 |
| 2027 H2 | Rubin Ultra (CPO 全面導入) | 階段切換, 重新評估 basket |

### Top 3 必看 6 月 catalyst (本月最關鍵)

1. **6/24 NVIDIA + Micron 同日** — HBM/AI 共振, 2x buying/selling 強度;直接 reality check 2344 ★★★★★ 評等
2. **6/17-18 FOMC** — 影響 [[Institutional_Alpha_2026-06]] 金融股 cluster 的外資 thesis (TWD+壽險 EV)
3. **6/1 (今天晚上) Computex** — VR200 量產時程 / Rubin Ultra 進度,本 PR #25 BoM 數據 reality check

---

**Source**: 12 unit slice research (`vault/research/vera_rubin_bom/{16-27}_*.md`) + Morgan Stanley public estimates + Tomshardware deep dive + SemiAnalysis GTC 2025

**DB**: `bom_components` table in `tmf_market_data` (84 rows × 13 cols, 12 categories × 2 platforms)

**Parquet**: `data/vera_rubin_bom.parquet` (merged) + `data/vera_rubin_bom/{16-27}_*.parquet` (per-unit)
