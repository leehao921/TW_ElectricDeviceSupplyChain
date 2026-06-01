---
type: concept
status: monitoring
last_updated: 2026-06-01
related: [../../themes/MLCC.md, ./MLCC_008004_TW_verification.md, ./FOPLP.md]
tags: [institutional_alpha, 法人, 外資, 投信, 跨產業, 潛力股, 2344, 3711, 1605, 1303, 2317]
---

# Institutional Alpha — 2026-06 法人/外資跨產業潛力股拆解

> 從 trading-timescaledb `institutional_stock` table 撈出 5/16-5/29 法人前 30 大買超, 分群成 6 個 cluster, **每 cluster 派 agent 深度研究「法人為何買」**。本頁是 Top 5 真潛力股 + 警戒清單 + cluster 邏輯彙整。底層研究見 `vault/research/institutional_alpha/{28-33}_*.md`。

---

## TL;DR — Top 5 真潛力股 (cross-cluster 排序)

| Rank | Ticker | 公司 | Cluster | 為什麼是 #1? | ★ |
|---|---|---|---|---|---:|
| **1** | **2344** | [[華邦電]] | semi/memory | **唯一雙引擎 +153K** (外資 +100K + 投信 +54K), Q4 GM **41.86%** (vs 22.66% 前季), **NOR Flash 是 Vera Rubin BOM 隱形瓶頸**, 利基 DRAM 供給退縮, 4 條 thesis 全 align | ★★★★★ |
| **2** | **3711** | [[日月光投控]] | HBM 周邊封裝 | Q1 2026 **OpM 10.10% 創單季高** + Net Income 年化 **+41.4%** + **PEG ~1.4** (三檔最便宜), Apple iPhone 17 + AI 雙引擎, CapEx 1,658 億押先進封裝 | ★★★★★ |
| **3** | **1605** | [[華新]] | HVDC grid 補充 | **隱性 008004 alpha** — 集團持股 [[華新科]] 2492 + [[信昌電]] 6173 (買 1605 = 隱性 long AI 被動元件 sleeve);P/B **0.85 sum-of-parts mispricing**;雙引擎 (AI 250kW grid + 離岸風電海纜) | ★★★★ |
| **4** | **1303** | [[南亞]] | 傳產 (但實為 AI 下游) | **3 層 thesis 堆疊**: 集團 SOTP ([[台塑集團]] 1301/1303/1326/8046) + AI BoM 下游 ([[銅箔基板]] / [[玻纖布]] / 電子材料) + 化工觸底, 法人 +106K 證實向下游延伸不是真正「離開 AI」 | ★★★★ |
| **5** | **2317** | [[鴻海]] | ODM 法人輪動 | 外資 **+213K** 第一名 (個股), 低 P/B 多引擎 (Apple iPhone + [[NVIDIA]] GB300/Rubin + EV + [[Foxconn AI]] 整合);Vera Rubin BOM 已涵蓋, 但法人 conviction 確認 thesis 持續 | ★★★★ |

---

## 警戒清單 (法人結構不健康 / 已透支)

| Ticker | 公司 | 警訊 | 結論 |
|---|---|---|---|
| **6147** | [[頎邦]] | 外資 -22K 賣有 3 層財報基礎: Net Margin **-7.39pp** + CapEx **5.46x** + P/E **89.33** | 投信 +34K 是「外資 well done → 投信末期切入」, 不追 |
| **2449** | [[京元電子]] | 結構故事最強但**法人 2 週 -9.5M 外資 -12.1M 投信雙殺未止** | hold, 等回檔 |
| **6282** | [[康舒]] | vs 2308 catch-up 但 **TTM P/E 319 透支** (Q4 OM 3.90% 拐點剛確認) | 估值滿載 |
| **2382** | [[廣達]] | 外資 -94K 撤 / 投信 +82K 接 — **末段接刀模式** | 避開 |
| **2356** | [[英業達]] | 外資 -14K / 投信 +50K — 同上但較緩 | 避開 |
| **2327** | [[國巨]] | (已在 008004 batch 驗證) 外資 -32K / 投信 +28K, 真正 AI 武器是 Kemet 鉭電容不是 micro-MLCC | 避開 (008004 結論延伸) |
| **2481** | [[強茂]] | (已在 HVDC 潛力股分析) 外資 -23K / 投信 +20K, 末段接刀 | 避開 |

---

## 6 Cluster 邏輯彙整

### Cluster 28 — 半導體晶圓 + 記憶體 4 強

法人為何進場:
- **記憶體 cycle 反轉** (DDR4 退場 → 利基 DRAM/NOR Flash 受惠)
- **HBM ramp 帶動 8" wafer 漲價週期**
- **2344 雙引擎 thesis 最強** — Vera Rubin BoM 隱形瓶頸 (NOR Flash 為 Boot ROM)

排序: **2344 (★★★★★) > 5347 ≈ 2408 ≈ 6770 (★★★★)**

### Cluster 29 — AI server ODM 法人輪動

法人為何分歧 = **「估值修復 vs AI 純度 momentum」**:
- 外資 picks (2317/2324): 大型流動性 + 低 P/B (仁寶 P/B 1.22 最便宜) + 多引擎
- 投信 picks (2382/2356): AI 伺服器純度 (廣達 ~40% / 英業達 45%) + Computex 6/2-6/6 front-run

**2324 仁寶兩派對立差 401,343 張** — 估值修復 vs AI 純度不足解讀完全相反

排序: 2317 > 3231 > 2324 (估值博弈) > 2356 > 2382 (高估值警戒)

### Cluster 30 — HVDC + grid 補充

法人 flow 已從 **HVDC Tier 1 國家隊 (2308/1519/1503/1513)** 外溢到 **Tier 2-3 邊緣標的** — sector rotation 後期訊號

**1605 華新 是 conviction high** 因為 cross-reference 008004 集團:買 1605 = 隱性 long 2492+6173 AI 被動元件 sleeve

### Cluster 31 — HBM 周邊封裝

排序: **3711 日月光 #1 > 2449 京元電子 #2 hold > 6147 頎邦 警戒**

修正: 2449 「AI 營收 75-77%」prompt 錯誤,vault 已 verified 為 **FY2025 >25% / FY2026 指引 >30%**

### Cluster 32 — 金融股法人大輪動

| 流向 | 主買 | Macro 邏輯 |
|---|---|---|
| **外資** | 2881/2882/2891 | **TWD 升值 + 壽險 EV 修復 + ETF 權值 rebalance (MSCI/FTSE)** |
| **投信** | 2887/2880/2886 | **殖利率 4-6% + 公股穩配 + 除權息季前換股** |
| Mixed | 2885 | 證券 cycle (ETF AUM 多 vs TWSE 量縮對沖) |

排序: 2881 ≈ 2882 > 2891 > 2886 > 2880 > 2887 > 2885

### Cluster 33 — 傳產 (其實 2/4 仍是 AI 下游)

**Critical insight: 4 檔中 2 檔 (1303 南亞, 2027 大成鋼) 其實是 AI thesis 向下游延伸 (CCL/玻纖布/機架/鋼板), 並非真正「離開 AI」**, 只有 2609/1216 是真實 sector 多元化

- 1303 南亞 ✅✅✅ — 集團 SOTP + AI BoM
- 2027 大成鋼 ✅✅ — Trump 50% 鋼鋁關稅護城河 + AI 機架
- 2609 陽明 ✅ swing — P/B 0.58 週期低點
- 1216 統一 ✅ — 純防禦 (投信獨買, 外資未參與)

**Macro narrative**: Computex 2026 (6/2-6/6) 為 catalyst peak, **5/16-5/29 是 pre-event 加碼期, 不是後 rotation**。法人 reallocation 動機更像是 (a) 風險平價 sector 平衡 + (b) TWD 升值 / DXY β -1.47 FX hedge。

---

## 跨 cluster 三大共通主題

### 主題 1 — 「估值修復 vs Momentum 接力」貫穿多 cluster

| Cluster | 外資 (估值修復) | 投信 (Momentum 接力) |
|---|---|---|
| ODM | 2317 鴻海, 2324 仁寶 | 2382 廣達, 2356 英業達 |
| HBM 周邊 | (沒參與, 整體都已 priced) | 6147 頎邦 (賭 HBM-side bumping turnaround) |
| 金融股 | 2881 富邦金, 2882 國泰金 | 2887 台新金, 2880 華南金 |

### 主題 2 — 「雙引擎」最強信號

5/16-5/29 雙引擎 (外資 + 投信都買, 總 > 50K 張) 的個股:
1. **2344 華邦電** (+153K) — **最強信號, Top 1**
2. **2317 鴻海** (+219K)
3. **2891 中信金** (+81K, 但外資主導)
4. **5347 世界先進** (+116K)
5. **3231 緯創** (+78K)

### 主題 3 — 「隱性 alpha」cross-reference

法人 5/16-5/29 進場的標的, 跟既有 vault concept 有強連結:
- 1605 華新 → 集團持股 2492 + 6173 (008004 vault)
- 1303 南亞 → 集團持股 8046 南電 (Vera Rubin ABF Tier 2)
- 2344 華邦電 → NOR Flash 為 Vera Rubin BOM 隱形 (Boot ROM)
- 3711 日月光 → HBM-on-CoWoS final assembly (Vera Rubin Tier 2)

---

## 投資組合建議

### Option A: 純「雙引擎 + 真潛力」basket (LONG-only)

等權 5 檔: **2344 + 3711 + 1605 + 1303 + 2317** (Top 5)
- 預期持有: 3-6 個月 (至 Q3 法說會)
- 退場訊號: 任 2 檔出現「外資連 3 日轉賣 + 跌破月線」

### Option B: 雙引擎 + Macro 對沖

- LONG: 2344 + 3711 (純 AI 雙引擎)
- HEDGE: 1216 統一 (傳產防禦類, 投信獨買, 外資未參與 → DXY 升值對沖)
- 避開: 警戒清單全部

### Option C: 隱性 alpha 集中 (進階)

- LONG: 1605 華新 (集團 008004 sleeve) + 1303 南亞 (集團 ABF sleeve)
- 等同於用 0.85 P/B 買 2492 + 6173 + 8046 等已大漲標的的衍生 exposure

---

## Catalyst 觀察 (next 6 週)

| 時間 | Event | 哪個 cluster 受影響 |
|---|---|---|
| **2026/6/2-6/6** | [[Computex]] 2026 | ODM (2317/2382), 半導體 (2344/2408) — pre-event 加碼已 priced |
| **2026/6/10 前** | 5 月營收公告 | 所有 cluster |
| **2026/6/10** | 3090 處置股結束 (008004 vault catalyst) | MLCC chain knock-on |
| **2026/6/13** | FOMC 6 月例會 | 金融股 cluster (外資 thesis) |
| **2026/7-8** | Q1 2026 法說會 | 所有 cluster reality check |
| **2026/8/15 前** | 中華電 / 公股金控 Q2 季報 | 金融股 cluster |
| **2026/10/14-18** | [[CEATEC]] 日本 (Murata 006003 next-gen) | 半導體 008004 chain |

---

## Open Questions (待 next iteration 驗證)

1. **6770 力積電 +390K 是 ETF rebalance 還是真實 alpha?** 需區分 0050/0056 持倉變化 vs 主動 picks
2. **2344 華邦電 NOR Flash 在 Vera Rubin BOM 真實量?** 應加入 bom_components table (本 batch 未涵蓋)
3. **1605 集團持股實質 lookthrough exposure?** 需算 1605 持有 2492 + 6173 比例 × 個別市值
4. **2382 廣達投信 +82K 是新進場 or vertical buy 加碼?** 影響「末段接刀」判定強度
5. **金融股 ETF rebalance vs MSCI review 時點**: 5/16-5/29 哪段是被動 flow vs 主動 alpha?
6. **2609 陽明 紅海危機 source 驗證**: 美國關稅 / 中國出貨潮 即時 data

---

## DB Query (內部使用)

```sql
-- 查看最新 5 個交易日法人 net buyer (跨 5 ticker)
SELECT date, symbol,
  ROUND(foreign_net::numeric/1000) AS f,
  ROUND(trust_net::numeric/1000) AS t,
  ROUND(total_net::numeric/1000) AS tot,
  close_price
FROM institutional_stock
WHERE symbol IN ('2344','3711','1605','1303','2317')
  AND date >= CURRENT_DATE - INTERVAL '5 day'
ORDER BY symbol, date;

-- 查看雙引擎 (外資+投信都買) 信號最強的個股
SELECT symbol,
  ROUND(SUM(foreign_net)::numeric/1000) AS f_tot,
  ROUND(SUM(trust_net)::numeric/1000) AS t_tot
FROM institutional_stock
WHERE date >= '2026-05-16' AND date <= '2026-05-29'
GROUP BY symbol
HAVING SUM(foreign_net) > 50000000 AND SUM(trust_net) > 30000000
ORDER BY SUM(foreign_net) + SUM(trust_net) DESC;
```

---

**Source**: 6 unit slice research (Unit 28-33 in `vault/research/institutional_alpha/`) + trading-timescaledb 5/16-5/29 institutional_stock query + Pilot_Reports 財務概況 + vault prior batch (Vera_Rubin_BOM + MLCC_008004 + FOPLP).

**Status**: monitoring — 6/10 後重新撈一次 5/30-6/9 法人變化驗證 thesis 持續性。
