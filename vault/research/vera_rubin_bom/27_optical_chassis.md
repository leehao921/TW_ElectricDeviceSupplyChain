# Vera Rubin VR200 — Unit 27: Optical / CPO / 矽光子 + 機殼結構件 BOM

**Batch:** Vera Rubin VR200 BOM 拆解 (unit 27 of 27)
**Scope:** 光收發模組、[[CPO]] 共同封裝光學、[[矽光子]] PIC、機殼 sheet metal 與機構件
**Prior gen baseline:** GB300 NVL72 機櫃 — 800G pluggable optics + 標準 19" 機殼
**Date:** 2026-05-26

---

## TL;DR

1. **[[CPO]] 在 [[Vera Rubin]] VR200 仍為「部分導入」而非全面取代 pluggable。** 真正完整導入 CPO 的是 **Rubin Ultra (Photonic)** 平台 (預計 2027 量產);VR200 機櫃 (2026H2 出貨) 預估仍以 [[800G]]/[[1.6T]] pluggable [[光收發模組]]為主力 backbone,僅在特定 NVLink/scale-up 連線開始嘗試 CPO 試樣。
2. **每櫃光學連線數量級放大。** GB300 NVL72 一櫃約需 ~5,000 條 800G 光連線(含 NVLink + scale-out InfiniBand/Ethernet);VR200 推估 1,000-1,400 顆 GPU 級節點,光纖數量約 1.5-2x GB300,單價亦從 800G ASP $700-800 → 1.6T ASP $1,200-1,500。
3. **機殼/機構件用量平穩,結構複雜度上升。** VR200 機櫃因液冷 manifold、Bus Bar、CPO 光纖匯流增加,sheet metal、CNC 機構件、rail/bracket 用量單櫃較 GB300 +15-20%。
4. **台廠最受惠排序:** [[波若威]] (CPO 光纖套件,NVIDIA 生態系合作夥伴) > [[聯亞]] (InP 磊晶,矽光子上游) > [[華星光]] ([[Marvell]] 光模組代工) > [[勤誠]] (機殼) > [[鴻準]] (機構件) > [[光環]] ([[VCSEL]],受惠較間接)。
5. **YoY 動能:** Optical 量增 + 單價升,單櫃光學 BOM 價值 +60-80%;機殼基本盤穩,單價隨複雜度 +15%。

---

## 1. Sub-category 拆解

### 1.1 [[光收發模組]] (Pluggable Optical Transceiver)

**規格:**
- VR200 baseline: [[800G]] OSFP / OSFP-XD,雙 4x200G PAM4 lane。
- 高階配置: [[1.6T]] 2x800G OSFP-XD,使用 200G/lane SerDes。
- 光源: [[EML]] (Externally Modulated Laser,DFB+EAM) 為主流,[[VCSEL]] 用於 short-reach AOC。
- 距離: 多模 (SR8,~100m) 用於同機架;單模 (DR8/FR8,500m-2km) 用於跨機房 scale-out。

**用量估算 (per VR200 rack, 推估):**
- Scale-up NVLink 光連線: ~3,000-4,000 條 (若 NVLink switch 仍走光纖)
- Scale-out InfiniBand/Ethernet: ~2,000-2,500 條 800G
- 總光模組數: ~5,500-6,500 顆/櫃
- 光模組單價: 800G ~$750, 1.6T ~$1,400 → 單櫃光學 BOM ~$5-7M USD

**台廠 exposure:**
- [[華星光]] (4979): [[Marvell]] 800G/1.6T DSP-based 光模組代工夥伴,終端供 [[Meta]]/[[Microsoft]]/[[Amazon]]。
- 國際對手: [[Innolight]] 中際旭創、[[Eoptolink]] 新易盛、[[Coherent]]、[[Lumentum]]。

### 1.2 [[CPO]] 共同封裝光學 (Co-Packaged Optics)

**[[Vera Rubin]] VR200 vs Rubin Ultra (Photonic):**
- VR200 (2026H2): CPO 為「partial / 試樣」階段,主要仍 pluggable。[[NVIDIA]] 已在 GTC 2026 公布 Quantum-X Photonic switch 與 Spectrum-X Photonic switch 走 CPO,但 GPU compute tray 仍以 pluggable 為主。
- Rubin Ultra (2027): CPO 全面導入,GPU、Switch、NVLink 皆共封裝光引擎,目標 5-10x 能耗降低。
- VR200 出貨期間 CPO 滲透率推估 < 15%,主要在 switch 層。

**CPO 關鍵零組件:**
- **光引擎 (Optical Engine):** [[Marvell]]、[[Ayar Labs]]、[[Broadcom]] 提供 silicon photonics 引擎。
- **[[矽光子]] PIC (Photonic IC):** [[TSMC]] 在 [[CoWoS]] 平台上整合 SiPh PIC + ASIC,N6/N5 photonic flow。
- **光纖套件 (Fiber Harness):** [[波若威]] (3163) 為 [[NVIDIA]] CPO 生態系合作夥伴,CPO 光纖套件 2026 量產。
- **外部雷射光源 (ELS, External Light Source):** [[聯亞]] (3081) [[InP]] [[磊晶]]片供應、雷射二極體,為 CPO 上游價值密度最高一環。

### 1.3 [[矽光子]] SiPh PIC

**製程整合:**
- [[TSMC]] N6/N5 + Photonic interposer,整合於 [[CoWoS]] 平台 (SoIC + 光波導)。
- 上游 [[磷化銦]] InP 雷射光源外接 (聯亞、Lumentum);[[矽晶圓]] 上 grating coupler、modulator、photodetector。
- VR200 期 SiPh 主要進入 Quantum-X / Spectrum-X switch ASIC,GPU side 觀望。

**台廠 SiPh exposure:**
- [[台積電]]: SiPh PIC 製造平台 (unit 1 covered)。
- [[聯亞]] (3081): [[InP]] [[磊晶]]片供應給 CPO ELS 模組。
- [[光環]] (3234): [[VCSEL]] for short-reach,SiPh PIC 整合較間接,主要受惠 [[資料中心]]光通訊大方向。

### 1.4 機殼 / Sheet Metal / 機架

**結構件清單 (per VR200 rack):**
- 機架主體 sheet metal (front/rear panel、side panel、top/bottom cover)
- 機架 rail (server tray slide rail)
- Cable management arm、光纖匯流盒
- 散熱孔陣列 (front bezel,需配合液冷 manifold 佈線)
- Bus Bar 機構支撐架 (大電流匯流條銅排,unit 25/26 已涵蓋)

**用量 vs GB300:**
- 單櫃 sheet metal 用量 +10-15% (因液冷 + 光纖匯流增加)
- CNC 機構件 (鋁擠型、機構支架) +20% (CPO 光纖整合區、Bus Bar 區複雜度提升)
- 結構件單價 +15% (公差要求提高、特殊鍍層需求)

**台廠 exposure:**
- [[勤誠]] (8210): 伺服器機殼龍頭,[[NVIDIA]] GB200/GB300/VR200 機殼直接供應商之一。
- [[鴻準]] (2354): 鴻海集團精密機構件,VR200 散熱模組外殼、CNC 加工件。

### 1.5 機架前面板 / 散熱孔

- VR200 因 1U/2U compute tray 與 NVLink switch tray 高密度堆疊,前面板散熱孔陣列需與液冷 cold plate 配合 (空氣散熱僅輔助)。
- 機架後方光纖出線區複雜度顯著上升,光纖配線盒 (Fiber Patch Panel) 需求 +50% (大量 800G/1.6T MPO/LC 接頭整合)。

---

## 2. Prior gen GB300 baseline 對照

| 項目 | GB300 NVL72 (2025H2) | VR200 (2026H2) | YoY |
|---|---|---|---|
| GPU/櫃 | 72 顆 (B300) | ~144 顆 (R200,推估) | +100% |
| Scale-up 光連線數 | ~3,500 條 800G | ~3,500-4,000 條 800G/1.6T 混合 | +10-15% |
| Scale-out 光連線數 | ~1,500 條 800G | ~2,000-2,500 條 800G/1.6T | +35-65% |
| 光模組單價 | 800G $700-800 | 800G $650 + 1.6T $1,200-1,500 mix | +60-80% (BOM 值) |
| [[CPO]] 滲透率 | 0% (試樣) | < 15% (switch only) | partial |
| 機殼 sheet metal | baseline | +10-15% kg/櫃 | +10-15% |
| CNC 機構件 | baseline | +20% 件數 | +20% |

---

## 3. YoY 動能

**Optical (大幅成長):**
- 量: 機櫃出貨數 (VR200 vs GB300) NVIDIA 訂單 +50%,光模組總數 +60-80%。
- 價: 800G → 1.6T 滲透率提升,blended ASP +30-40%。
- 整體單櫃光學 BOM 價值 +60-80%。

**[[CPO]] (試樣 → 試量產):**
- VR200 CPO 滲透率 < 15% (僅 switch),Rubin Ultra (2027) 才是 CPO 真正爆發點。
- [[波若威]] 2026H2 CPO 光纖套件量產,YoY 從 0 → meaningful contribution。

**機殼 (平穩成長):**
- 量平穩 (跟 NVIDIA 出貨節奏),價 +15% (複雜度)。
- [[勤誠]]、[[鴻準]] 單機殼營收 +15-20%,總營收看出貨櫃數。

---

## 4. TW 受惠排序

| 排名 | 公司 | Ticker | 角色 | VR200 受惠度 | 備註 |
|---|---|---|---|---|---|
| 1 | [[波若威]] | 3163 | [[CPO]] 光纖套件 | 高 (但量小,2026H2 量產) | [[NVIDIA]] CPO 生態系合作夥伴,Rubin Ultra 才是大放量 |
| 2 | [[聯亞]] | 3081 | [[InP]] [[磊晶]]、雷射光源 | 高 | 矽光子/CPO 最上游關鍵材料,EML/CPO ELS 都用 |
| 3 | [[華星光]] | 4979 | [[Marvell]] 800G/1.6T 光模組代工 | 高 (量大) | VR200 pluggable optics 主力受惠 |
| 4 | [[勤誠]] | 8210 | 伺服器機殼 | 中 | [[NVIDIA]] 機架機殼供應商,單櫃 ASP +15% |
| 5 | [[鴻準]] | 2354 | CNC 機構件、散熱模組外殼 | 中 | 鴻海集團整合,液冷模組機構件 +20% |
| 6 | [[光環]] | 3234 | [[VCSEL]] / 光偵測器 | 中低 | 短距 AOC、3D 感測為主,CPO 整合較間接 |

**註:** [[3454]] 晶睿 為 Vivotek 監控攝影機,**不屬於資料中心光通訊**,排除於 VR200 BOM 受惠名單外 (校正原 brief 誤判)。

---

## 5. Parquet rows 摘要

詳見 `data/vera_rubin_bom/27_optical_chassis.parquet`,共 11 列 (VR200 + GB300 baseline 對照 + TW supplier breakdown)。

---

## 6. Sources

- [[NVIDIA]] GTC 2026 keynote — Rubin / Rubin Ultra / Quantum-X Photonic / Spectrum-X Photonic 公開資料
- [[波若威]] 3163 法說會 (2025 Q4 / 2026 Q1) — CPO 光纖套件 NVIDIA 生態系合作、2026H2 量產時程
- [[聯亞]] 3081 法說會 — InP 磊晶在 CPO 外部雷射光源 (ELS) 之應用、矽光子上游定位
- [[華星光]] 4979 法說會 — Marvell 800G/1.6T 光模組代工進展
- [[勤誠]] 8210 — NVIDIA AI 機架機殼出貨節奏
- LightCounting / Dell'Oro 光收發模組市場報告 (800G→1.6T 滲透曲線)
- TrendForce 矽光子 / CPO 滲透率預估 (2026-2027)
- Pilot_Reports/Communication Equipment/3163_波若威.md (本專案 ground truth)
- Pilot_Reports/Semiconductor Equipment & Materials/3081_聯亞.md
- Pilot_Reports/Semiconductors/4979_華星光.md
- Pilot_Reports/Semiconductors/3234_光環.md
- Pilot_Reports/Computer Hardware/8210_勤誠.md
- Pilot_Reports/Electronics & Computer Distribution/2354_鴻準.md

---

## Verification log

本報告涉及量化主張包含:
- 「VR200 光連線數 ~5,500-6,500 顆/櫃」「YoY +60-80%」屬於**產業推估**,基於 GB300 公開數字 + NVIDIA GPU 數量倍增推導,非分布性 outlier 主張,未觸發 `verify_flow_zscore.py` 規則。
- 「CPO 滲透率 < 15% in VR200」明確標示為「推估」,引用 NVIDIA GTC 2026 Rubin Ultra 才完整 CPO 的官方時程。
- 未使用 σ / 罕見 / 極端 / outlier / percentile 等分布形容詞 → 符合 Golden Rule #0。

---

**Ticker→公司名 verification (Golden Rule #2):**
- 3163 = 波若威 ✓ (Pilot_Reports/Communication Equipment/3163_波若威.md)
- 3081 = 聯亞 ✓ (Pilot_Reports/Semiconductor Equipment & Materials/3081_聯亞.md)
- 4979 = 華星光 ✓ (Pilot_Reports/Semiconductors/4979_華星光.md)
- 3234 = 光環 ✓ (Pilot_Reports/Semiconductors/3234_光環.md)
- 8210 = 勤誠 ✓ (Pilot_Reports/Computer Hardware/8210_勤誠.md)
- 2354 = 鴻準 ✓ (Pilot_Reports/Electronics & Computer Distribution/2354_鴻準.md)
- **3454 = 晶睿 (Vivotek, 監控攝影機) — 與光通訊無關,原 brief 誤判,已校正並排除**
- 3661 = 世芯-KY ✓ (ASIC,屬其他 unit 範圍,本 unit 僅以 Marvell ASIC 客戶關係提及)
