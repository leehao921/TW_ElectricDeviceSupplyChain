---
type: concept
status: monitoring
last_updated: 2026-06-01
related: [./MLCC_008004.md, ./MLCC_008004_technical_deep_dive.md, ../../themes/MLCC.md]
tags: [MLCC, 008004, TW_verification, 8043, 3090, 6173, 4760, 2327, 2492, 3030, 3189, catalyst, R&D, hidden_candidates]
---

# MLCC 008004 — TW 機會廠商驗證 (2026-06-01)

> 第二輪深度驗證 (Unit 7-11, 5 個 slice 共 1,500+ 行) 對 prior batch (Unit 1-6) 留下的 5 個 open questions 逐一拆解,並挖掘 2 個新維度 (隱藏候選 + catalyst calendar)。本頁是**對 [[MLCC_008004]] trader decision page 的修正補丁**,所有具體 trader decisions 仍在主頁。

---

## TL;DR — 5 個 open questions 驗證結果

| Open Q | Prior batch 主張 | Unit 7-11 驗證 | 修正 |
|---|---|---|---|
| 1. 8043 008004 占 revenue | 5.6% (顆數比) | **6-9% (全公司 rev, 中性);GP 占 30-40%** | 分母不同需區分 — 顆數比 ≠ 公司 rev 比 |
| 2. 8043 Q3 OCF -405.82M | 「GB300 BOM 大量備貨警訊」 | **70% A/R + 30% inventory + 130M A/P 回補**, Q4 已收斂 | 警訊降級 |
| 3. 3090 SEMCO TW share vs 文曄 | 55-65% | **不變** — 文曄 Future TW < 20 人, 未搶單 | 確認 |
| 4. 3090 處置股期間量價 | (預測) | 量縮 70%, 5/28 −9.7% T+1, 5/29 V 反, **6/1 突破 247 (+9.2%)**, 法人吸籌 (縮量上漲) | 處置股 thesis 中立, 但 alpha 已 reversed |
| 5. 6173 100nm 目標 X7R or NP0 | (未定) | **NP0 / C0G (Class I 高純度)** — TechNews + 法說雙重佐證 | NP0 比 X7R 難 2-3x, 主攻 1206+ 大尺寸高壓, **與 008004 反方向確認** |

---

## 6 個維度驗證 2327/2492 隱藏 R&D = 1/5 (極低)

從 Unit 10 跨 6 維度檢索:

| 維度 | 結果 | 評分 |
|---|---|---|
| 1. 專利 (USPTO + TIPO + Google Patents 5 年) | [[Yageo]] / [[Walsin Technology]] **0 件 sub-0.4 mm claim**;同期 [[Murata]] ≥ 3 件 (US12,482,604 / US20240282522A1 / WO2024247128A1) | 0/5 |
| 2. 學術論文 ([[ECTC]] / [[CIPS]] / [[EPTC]]) | Yageo / Walsin **0 篇微小化論文**;Murata 2025/7 發 800 層 0402, BaTiO₃ 晶粒 <50 nm | 0/5 |
| 3. 客戶 JDP ([[Apple]] / [[Tesla]] / [[NVIDIA]]) | [[Yageo]] 確認在 Apple supplier list (Kaohsiung + Suzhou + Dongguan 3 廠) 但 **design-in 止於 0402 / 01005**;[[Walsin Technology]] 不在 Apple list | 1/5 |
| 4. 馬來西亞華新科廠 capex | **無 [[Hirano Tecseed]] / [[光洋熱工]] high-end 設備採購訊號**;capex 流向車規 + 工業 | 0/5 |
| 5. [[Kemet]] / [[TOKIN]] / [[Pulse]] / [[芝浦電子]] 整合 | 4 件併購**無一補 micro-MLCC**;[[Kemet]] 鉭電容才是 Yageo AI 武器 (Q1 2026 +20% QoQ, 30%+ 綁 AI server) | 0/5 |
| 6. 法說會 / 年報 hidden hints | 「高階」= 高壓 + 高容 + 車規, **全程未提 008004 / sub-0.4 mm** | 1/5 |
| **整體** | **平均 0.33/5, 取整 = 1/5 (極低)** | **1/5** |

**結論強化**: prior batch 「TW 中游廠 zero 008004 exposure, 落後 1-2 世代 / 4-6 年」**得到 6 維度一致負向加強驗證**。市場用 2327 / 2492 對標 008004 = **持續錯誤**。

---

## 修正版 TW 受惠強度排序

### Tier 1 直接受惠 (代理通路)

| Ticker | 公司 | 受惠強度 | 6/1 收 | 6M chg | 5/19-6/1 chg | 修正項 (vs prior batch) |
|---|---|---|---|---|---|---|
| **3090** | [[日電貿]] | **5/5 (升級)** | 250 | +177% | **+52%** | alpha 已 catch-up 反超 8043;法人主導吸籌;處置股期間縮量上漲;P/E TTM 47.71 vs Pilot_Report |
| **8043** | [[蜜望實]] | 4.5/5 (降級) | 155 | +141% | +37% | **Murata 4/1 漲價不直接受惠** (非 8043 principal);Taiyo Yuden 5/15 +6-13% → 8043 Q2 GM +120-180 bps;Q3 OCF -405.82M 警訊降級 |

### Tier 2 間接受惠 (上游材料)

| Ticker | 公司 | 受惠強度 | 6/1 收 | 6M chg | 法人 (5/19-5/29) | 修正項 |
|---|---|---|---|---|---|---|
| **6173** | [[信昌電]] | 2.5/5 (降級) | 250.5 | +278% | +1,283 張 (純散戶) | **100nm 目標是 NP0 (不是 X7R)**;**主攻 1206+ 大尺寸高壓 NP0**,法說明確「避開 0201 微小化」→ 與 008004 物理反方向 |
| **4760** | [[勤凱]] | 2.5/5 | 447 | +163% | +212 張 (法人轉賣) | 「+20%」是全年 YoY 不是月增;客戶 70%+ 台灣 ([[國巨]] 50% silver + [[奇力新]] 60-70%);日本「初步認證」未具名 (業界 hint [[Murata]]);**規格未公開 — 無 008004 證據** |

### Tier 3 零暴露但被市場誤 lump

| Ticker | 公司 | 法人 (5/19-5/29) | 修正項 |
|---|---|---|---|
| **2327** | [[國巨]] | -750 (**外資 -26,983 大撤**, 投信 +21,241 硬接) | 隱藏 R&D = 0;真正 AI 武器是 [[Kemet]] 鉭電容 (+20% QoQ);commodity MLCC 漲價週期受惠 |
| **2492** | [[華新科]] | +22,150 (**外資 +17,607 強買**) | 隱藏 R&D = 0;高壓 + 高容 + 車規,**全程無 008004 字眼**;馬廠定位車用電阻 |
| **3026** | [[禾伸堂]] | n/a | 100V-10,000V 高壓利基, **與 008004 物理反方向** (Unit 3 已確認) |

---

## 新候選廠商 (Unit 9 挖掘)

### 新增 Tier 1.5 (下游受惠)

| Ticker | 公司 | 路徑 | 強度 | 受惠機制 |
|---|---|---|---|---|
| **3030** | [[德律]] | AXI X-ray + AOI for PCBA | ★★★ | **AI 伺服器 GPU board 一塊 PCBA 含 1,000-2,000 顆 008004**, 焊接後 AXI X-ray 抽檢比例必須上升;全球 PCBA AOI/AXI 龍頭,客戶包括 [[Apple]] 供應鏈、[[Tesla]] 供應鏈、AI 伺服器 ODM |

### 新增 Tier 2.5 (ABF 載板 ECiP 同步)

| Ticker | 公司 | 路徑 | 強度 | 修正 |
|---|---|---|---|---|
| **3189** | [[景碩]] | [[ABF 載板]] + [[BT 載板]] | ★★ | 第三家 ABF 載板 (themes/MLCC.md 已列 3037/8046, 但漏 3189);ECiP ([[Embedded Capacitor in Package]]) 嵌入式被動元件路徑同步受惠 |

### 觀察名單 (設備平台延伸)

| Ticker | 公司 | 條件 | 強度 |
|---|---|---|---|
| **3455** | [[由田]] | AOI 平台目前主力 IC 載板,若揭露 [[Murata]] / [[國巨]] 客戶 = 觸發加入 | ★★ |
| **6187** | [[萬潤]] | 點膠/塗佈/AOI 平台,若揭露 [[太陽誘電]] / [[國巨]] 客戶 = 觸發加入 | ★★ |

### Ticker 修正 (重要)

- **4977 [[眾達-KY]]**: prompt 之前列為「ABF 載板第三家」**錯誤**。實際業務為**光通訊模組 OEM ([[Broadcom]] 客戶)**,與 ABF 載板無關 → 從 MLCC theme 移除

### 排除 (noise) — 9 家

2360 [[致茂]] / 6510 [[精測]] / 3551 [[世禾]] / 3413 [[京鼎]] / 1560 [[中砂]] / 4722 [[國精化]] (已透過 CCL 路徑覆蓋) / 1711 [[永光]] / 1304 [[台聚]] / 4919 [[新唐]] (IC 設計)

---

## TW 完整 supply chain 卡點圖 (Unit 8 critical finding)

```
008004 BME 製程 BoM 結構性卡點:

層級             | TW 可達 | TW 卡點 | 日商寡占
----------------|---------|---------|--------
鈦酸鋇 nano 粉   | 6173 200nm→100nm 2027 | 30-50% MLCC 成本 | Sakai/Nippon Chemical 寡占
Ni 漿料 (內電極) | **零** | **35-50% MLCC 成本** | Shoei Chemical (Murata toll refining)
Cu/Ag 漿料 (端電極) | 4760 (送樣 Murata 初認證) | 5-10% MLCC 成本 | Shoei/Daiken/Noritake
設備 (流延/燒結) | 零 | 設備折舊 | Hirano Tecseed/光洋熱工 寡占
製造 (TW 中游)   | 國巨/華新科 最小 01005 imp | leading edge 缺席 | Murata/SEMCO/Taiyo Yuden
```

**結論**: 即使 6173 + 4760 + 2327 + 2492 100% 整合, 仍須向 [[Shoei Chemical]] / [[MMS]] (日本三井金屬) 採購 Ni — **TW 切 008004 結構性卡死,不可繞過**。這是 prior batch 沒有充分強調的 critical finding。

---

## Catalyst Calendar (Unit 11 摘要 — next 6-12 個月)

### Top 3 關鍵 catalyst

| 日期 | Event | Impact | Position |
|---|---|---|---|
| **2026/6/10** | **3090 處置股結束首日** | technical, 3 情境 (爆量上攻/下殺/縮量) | 開盤觀察, 不追高 |
| **2026/10/14-18** | **[[CEATEC]] JAPAN 2026** | **Murata 006003 量產時程公開最可能場合** | 情境 A (2027 H2 以後) 加碼;情境 B (2027 H1) 減 [[8043]]/[[3090]] 至 50%;情境 C (未公開) 持有 |
| **2026/11/14 前** | Q3 法說 — **[[8043]] AI 占比突破 50% 驗證** | 核心 reality check | Bull case → 加碼 |

### 完整時間表 (摘 unit 11)

| 月份 | 主要事件 | 觀察點 |
|---|---|---|
| 2026/6 | Computex (6/2-6/6) + 處置股結束 (6/10) + 5 月營收公告 + Apple WWDC (6/8-12 預估) | [[Vera Rubin]] 時程確認 + 8043/3090 5 月 YoY |
| 2026/7-8 | Q1 法說密集期 + Murata FY27 Q1 季報 + 暑期備料 | Murata IR 是否揭露 006003 + SEMCO 釜山進度 |
| 2026/9 | iPhone 17 發表 (9/9-9/16) + 拆機 (9/22-30) + Murata 中期 IR | **iPhone 17 008004 顆數 / 廠牌驗證 (核心)** |
| **2026/10** | **CEATEC JAPAN 2026 (核心)** + Murata FY27 H1 季報 + 008004 ASP 是否續漲 | Murata 006003 量產時程 |
| 2026/11 | Q3 法說 (核心) + SEMCO 釜山 008004 量產目標 + 投信季報 + 美國感恩節 | 8043 AI 占比 / 2327/2492 漲價見頂訊號 |
| **2026/12-2027/3** | **Murata 006003 量產正式公告 = ASP cliff 開啟** | 8043/3090 減碼至 30-50% |

### Risk events (5 大外生衝擊)

1. **[[NVIDIA]] [[Vera Rubin]] VR200 延後** → AI 伺服器 thesis 延後,[[Vera Rubin]] 延 > 12 月 → 減碼 30%
2. **中國 RK BaTiO₃ 突破** → 直接挑戰 [[6173]] 上游粉體 thesis (但 Lead time 18-24 月,中期風險低)
3. **Murata 訊息缺漏** (006003 不公開) → ASP cliff 時點不可預測,風險加大
4. **TWSE 政策** (處置股加嚴) → 短線 technical 衝擊,thesis 不變
5. **全球宏觀景氣降溫** → commodity MLCC 漲價見頂 → 加碼 short basket (2492)

---

## 修正版 Pair Trade 建議 (vs 既有 MLCC_008004.md)

### Option A: LONG basket {**3090 + 8043 + 3030**} (最強 conviction — 升級)

- **3090** 升級為 #1 (法人主導 + 處置股後仍升 + P/E TTM 16-21x 仍是 MLCC 族群最低)
- **8043** 維持 #2 (Taiyo Yuden 漲價直接受惠 + AI 占比 40%→50%)
- **3030 [[德律]] 新增 #3** (AXI X-ray AI server PCBA 焊接後檢測剛需,被市場 underprice)

### Option B: LONG 3090 / SHORT 2327 (對沖 pair)

- 2327 隱藏 R&D = 1/5 + 外資 -26,983 張大撤 + 投信末段硬接 + Kemet 鉭電容才是真正 AI 武器 (not micro-MLCC)
- 3090 法人主導 + 處置股後突破 + P/E 比 2327 高但成長性更強

### 移除 (修正)

- **6173** 從 long basket 移除 (純散戶 + NP0/C0G 方向與 008004 反方向,只能間接受惠 [[Murata]] / [[SEMCO]] 大尺寸 NP0 採購)
- **4760** 從 long basket 移除 (法人轉賣 + 日本仍在 cultivation + 規格未公開, 008004 BOM 切入估 2027+ 之後)
- 「SHORT 2492」改為 **SHORT 2327** (2327 處置股 + PER 65× + commodity beta 更純)

### 退場訊號 (鎖死)

- **[[Murata]] 006003 量產正式公告** → 008004 ASP cliff
- 估時間: 2026 末 – 2027 H1 (CEATEC 2026/10 為公開最可能時機)
- 對應 long basket 倉位減至 30-50%

---

## 對既有 [[MLCC_008004]] 主頁的修正項列表

| 段落 | 修正 |
|---|---|
| **Big-4 對照表** | 維持 |
| **TW 受惠強度排序** | **改為 3090 ≥ 8043 > 3030 > 3189 > 6173 ≈ 4760** (3090 升 1, 4760/6173 降, 新增 3030/3189) |
| **GB300 BOM 拆解** | 維持 (008004 占顆數 5.6% / ASP 45% 是單櫃內 BoM, 非 8043 公司 rev 比) |
| **Pair Trade** | 改 LONG basket {3090 + 8043 + 3030};SHORT 2327 (不是 2492) |
| **退場訊號** | 維持 (006003 量產) |
| **Open questions** | 更新 — 8043 SKU 占 rev 已部分答 (6-9%);6173 X7R/NP0 已答 (NP0);新增「3090 處置股 6/10 後 follow-through」 |

---

## 既有 trader decision page 還沒解的 open questions

1. **6/1 後 3090 漲到 247 (處置股期間突破前高)**, 6/10 解禁後是否會獲利了結 → unit 11 給 3 情境
2. **4760 銅漿 D50/D90** 仍未揭露 — 不影響 thesis (4760 在 008004 已 deprioritize)
3. **馬廠華新科設備供應商** — 仍未公開,需 IR call;若採購 [[Hirano Tecseed]] / [[光洋熱工]] = 攻 008004 首訊
4. **Murata 006003 量產時程** — CEATEC 2026/10 為公開最可能場合;3 情境對應 position

---

**Sources**: 5 unit slice research (Unit 7-11 in `vault/research/008004/07-11_*.md`) + prior batch (Unit 1-6) + 6/1 即時收盤 yfinance + 三大法人 trading-timescaledb (5/19-5/29) + Pilot_Reports 財務概況

**Status**: monitoring — 隨 6/10 / 7-8 月 Q1 法說 / 9 月 iPhone 17 拆機 / 10 月 CEATEC / 11 月 Q3 法說 / 12 月-2027 H1 006003 量產更新
