---
type: research
status: draft
last_updated: 2026-06-01
source_unit: 10
tags: [MLCC, 008004, verification, 2327, 2492, patents, R&D]
---

# Unit 10: 2327/2492 隱藏 R&D pipeline (專利 + 論文 + 客戶訊號)

> 接續 Unit 2 結論「[[Yageo]] / [[Walsin Technology]] 對 008004 (= imperial 008004 = 0.25 × 0.125 mm) 公開零量產，落後 Big-4 約 1-2 個世代 / 4-6 年」。本 unit 專責反證 — 是否存在非公開的 R&D pipeline 訊號 (專利、學術論文、客戶 JDP、馬來西亞高階設備採購、[[Kemet]] 整合)？

## TL;DR — 有沒有隱藏訊號?

**整體判定: 沒有顯著的隱藏 R&D pipeline 訊號指向 008004。隱藏 R&D 強度評分 = 1/5 (低)。**

關鍵驗證:

1. **專利線 (5 年公開檢索)**: Google Patents / USPTO 以 assignee "[[Yageo]]" / "[[Walsin Technology]]" + 多層陶瓷電容 / 介電 / [[鈦酸鋇]] 搜尋, 2021-2026 年間**沒有任何一件 claim 明確涵蓋 sub-0.4 mm 級別 (即 01005 以下) 或介電層 < 0.5 µm 的專利**。同期 [[Murata]] 名下 (assignee Murata Manufacturing) 一年內 (2024/3-2025/11) 在多層陶瓷電容類別發布**至少 3 件新申請與授權**, 規模量級差 (Source: Google Patents, Justia Patents)。

2. **學術論文線**: [[IEEE]] [[ECTC]] 2022-2025 論文集中, Yageo / Walsin 作者均**未發表任何 sub-0.4mm 或介電厚度 < 0.5 µm 的 MLCC 微小化論文**。對比 [[Murata]] 2025 年 7 月已發表 0402 800 層 / [[Samsung Electro-Mechanics]] 2025 年發表 1005 LiDAR 車規 — 台廠在學術 / 技術 conference 端**完全沒有現身**。

3. **客戶 JDP 訊號**: [[Yageo]] **確認在 Apple 200 家主要供應商名單內** (Kaohsiung + Suzhou + Dongguan 共 3 廠), 但 design-in 規格只到 0402 / 01005 級, **沒有 008004 對 [[Apple]] 的 design-win 揭露**。[[Walsin Technology]] 沒有出現在 Apple 公開 supplier list (FY2023, FY2024)。[[Tesla]] / [[BYD]] / [[NVIDIA]] 對 2 家的合作公告皆鎖定**大尺寸高壓車用 + AI 伺服器電源迴路**, 與 008004 微小化技術節點無關。

4. **馬來西亞 [[Walsin Technology]] 新廠**: 公開設備招標 / 採購完全**沒提及 [[Hirano Tecseed]] (高階流延機, 量產 Big-4 用) 或 [[光洋熱工]] high-end 燒結爐**。對外定位明確是「car-grade + 工業海外樞紐」, capex 流向中大尺寸高功率產線, 與 008004 路線不符。

5. **[[Kemet]] 整合**: [[Kemet]] 主業是鉭電容 / 高分子電容 / film / 電解電容, **沒有 micro-MLCC 技術可移轉到 [[Yageo]] MLCC 本體**。2026 Q1 法說 [[Yageo]] 自己揭露 Kemet 鉭電容 +20% QoQ 創新高, 30%+ 綁 [[AI 伺服器]] — 訊號完全在鉭電容 (AI server PoL VRM 電源迴路) 而非 micro-MLCC。

6. **法說會 hints**: 2026 Q1 法說 (4/15) [[Yageo]] 對外溝通的「高階轉型 + AI 紅利」**全程未提 008004 或 sub-0.4 mm 微小化**, 主軸是 (a) 鉭電容 (Kemet 體系) (b) [[AI 伺服器]] 高壓高容 0402 (c) 車規。[[Walsin Technology]] 2025 年報「精準突破、中高階轉單」對應的是**0402 高容 + 車規 0201** 升級, 而非更小尺寸跳躍。

**結論**: 隱藏 R&D pipeline 訊號 = 1/5。Unit 2 主結論 (台廠對 008004 零 exposure, 落後 1-2 世代) **得到本 unit 加強驗證**。漲價題材傳導不到 008004 技術節點的判斷成立。

---

## 1. 專利搜尋 (5 年, 2021-2026)

### 1.1 [[Yageo]] (assignee 視角)

**Google Patents / USPTO / Justia Patents 搜尋結果 (2021/1/1 - 2026/6/1)**:

| 來源 | 檢索條件 | 命中 |
|---|---|---|
| Google Patents | assignee:"Yageo" + multilayer ceramic capacitor | 0 件直接命中 sub-0.4 mm |
| Justia Patents | Yageo Corporation, capacitor class 361/306 | 主要為 chip resistor / current sensing resistor / 微小電阻層相關 |
| USPTO 直接檢索 | Yageo 多層陶瓷電容介電組成 | 無 5 年內 ultra-miniature 申請 |

**已驗證的近期 [[Yageo]] 專利方向**:
- 2025 年初 [[Yageo]] 取得「電流感測電阻製造方法」與「微電阻層」相關專利 — **屬電阻領域 (Chip Resistor, Yageo 全球第一主業), 不涉 MLCC 微小化**。
- 2024 年 10 月 [[Yageo]] 於 PSMA Capacitor Technical Forum (Power Sources Manufacturers Association) 發表 webinar, 內容圍繞 X7R / [[鈦酸鋇]]核殼結構 / MLCC 製造流程 — 屬於**通用介電知識傳達**, 未公布 008004 specific R&D。

**Negative finding**: 全球 MLCC sub-0.4 mm 專利申請密度最高的是 [[Murata Manufacturing]], 一年內 (2024/3-2025/11) 至少 3 件 (US12,482,604 於 2025/11/25 核准, US20240282522A1 申請於 2024/4/30, WO2024247128A1 公布於 2024/12/5) — Yageo 名下**零件可對比**。

### 1.2 [[Walsin Technology]] (assignee 視角)

| 來源 | 檢索條件 | 命中 |
|---|---|---|
| Google Patents | assignee:"Walsin Technology" 2021-2026 | 0 件 sub-0.4 mm MLCC 直接命中 |
| TIPO 中華民國專利檢索系統 | 華新科技股份有限公司 多層陶瓷電容 | 主要為產品結構 / 端電極改良, 未見奈米級介電配方專利 |

**驗證結果**: [[Walsin Technology]] 在 USPTO / TIPO 公開資料庫中, 5 年內**沒有任何一件 MLCC sub-0.4 mm 或奈米級 [[鈦酸鋇]] 介電配方專利**, 規模上完全落後 [[Murata]] / [[Samsung Electro-Mechanics]] / [[Taiyo Yuden]] / [[TDK]]。

### 1.3 [[Sinoceramics]] (信昌電 6173) — 上游粉體

Unit 2 已確認 [[Walsin Technology]] 主要 [[鈦酸鋇]] 粉體來源是 [[Sinoceramics]] (200 nm 級), 不足以支撐 008004 (< 100 nm 奈米化粉體要求)。本 unit 補上一點: [[Sinoceramics]] 在 TIPO 與 USPTO 同期亦**沒有 < 100 nm 奈米化 [[鈦酸鋇]] 配方專利**, 證實**台廠粉體端到電容端整條鏈在 sub-0.4 mm 維度欠缺自主 IP**。

### 1.4 與 [[Murata]] / [[Samsung Electro-Mechanics]] 對比

| Assignee | 2024-2025 MLCC 微小化相關專利 | Sub-0.4 mm claim 涵蓋 |
|---|---|---|
| [[Murata]] Manufacturing | ≥ 3 件 (US12,482,604、US20240282522A1、WO2024247128A1) | 多件直接 claim 008004 / 005003 級結構與介電組成 |
| [[Samsung Electro-Mechanics]] | 多件 (LiDAR 1005、800V EV 高壓) | 主要 sub-1 mm 但車規導向 |
| [[Taiyo Yuden]] | 多件 | sub-0.5 mm 部分 |
| [[TDK]] | 多件 | sub-0.5 mm 部分 |
| [[Yageo]] (2327) | 0 件 (sub-0.4 mm 維度) | 無 |
| [[Walsin Technology]] (2492) | 0 件 | 無 |

**判定**: 專利端**證據不利於「台廠有隱藏 008004 pipeline」的假說**。

---

## 2. 學術論文 ([[IEEE]] [[ECTC]] / [[CIPS]] / [[IEEE EPTC]])

### 2.1 [[IEEE]] [[ECTC]] (Electronic Components and Technology Conference) 2022-2025

- 2022-2025 論文集 (IEEE Xplore) 檢索 "Yageo" + "Walsin" 作者隸屬: **0 篇關於 sub-0.4 mm 多層陶瓷電容的 first-author 或 co-author 論文**。
- 同期 [[Murata]] 在 [[ECTC]] 持續發表 sub-micron 介電 / 高層數堆疊 / 燒結均勻性論文。

### 2.2 [[CIPS]] / [[IEEE EPTC]] (新加坡) / 中華民國電子材料學會

- [[CIPS]] (International Conference on Integrated Power Systems): Yageo / Walsin 對外發表內容集中在**車規 [[MLCC]] 應用案例**, **未觸及 008004 技術節點**。
- 中華民國電子材料學會 2024 / 2025 年會: [[Yageo]] / [[Sinoceramics]] 偶有奈米陶瓷材料應用報告, **但 [[鈦酸鋇]] 粒徑公開值仍在 150-200 nm 等級**, 距 Murata < 50 nm (2025 年新發布的 0201 metric, 0.22 µF / 6.3V) 仍有顯著落差。

### 2.3 技術 maturity 信號

**Murata 2025 年 7 月發表 800 層 0402 metal-cap 47 µF** — 這顯示 [[Murata]] 主力研究火力正在 sub-1 mm 高層數高容上, 同時保持 008004 的世代 lead。[[Yageo]] / [[Walsin Technology]] 在學術會議的 **R&D 火力 signature 顯然集中在大尺寸高壓 (車規 + AI 電源) 而非微小化**。

---

## 3. 客戶 JDP 訊號 ([[Apple]] / [[Tesla]] / [[NVIDIA]] supplier list)

### 3.1 [[Apple]] 供應商名單

- **[[Yageo]] (2327) 在 Apple 200 家主要供應商名單內**, FY2023 揭露 Apple 供應鏈名單時, [[Yageo]] 同時揭露 3 個生產基地: Kaohsiung 廠 (TW) + Suzhou 廠 (CN) + Dongguan 廠 (CN)。
- 但 Apple 公開資料**未具體揭露 Yageo 供貨產品的尺寸 / 技術節點**, 業界經驗值 Apple 對 [[Yageo]] 主要 design-in 是 0402 / 01005 級, 用於 iPhone PCB 一般電源迴路 — **不是 008004 (Murata 在 008004 仍是 iPhone PoP 模組唯一 design-in)**。
- **[[Walsin Technology]] (2492) 不在 Apple 公開 supplier list 內** (FY2023, FY2024 皆沒命中), 顯示 Apple 高階 micro-MLCC 業務根本沒分到 2492 手中。

### 3.2 [[Tesla]] / [[BYD]] 車廠供應商

- [[Walsin Technology]] 提供 AEC-Q200 認證的 MT 系列 MLCC (尺寸 0201 imperial 至 1210 imperial, 容值 0.1pF 至 2.2µF, 電壓 10V 至 1000V), **完全集中在 0201 以上**。
- [[Yageo]] 車規系列同樣集中在 0201 以上 (Class I C0G + Class II X7R)。
- 對 [[Tesla]] / [[BYD]] / Tier-1 的 design-in 內容完全是**車身電源高壓 + ADAS / 車規高溫高可靠**, 與 008004 無關。

### 3.3 [[NVIDIA]] AI 伺服器 partner list

- 2026 Q1 [[Yageo]] 法說會明確表態 [[AI 伺服器]] 用 MLCC 主要是「高壓高容 0402 / 大尺寸 (1210+) + 鉭電容」, 集中在 PoL VRM (Point of Load Voltage Regulator Module) 與電源 backplane。
- [[NVIDIA]] [[GB200]] NVL36 / NVL72 用 MLCC 234k / 441k 顆主要為**中大尺寸高壓 (0402-1210 imperial 等級)**, 008004 在 AI 伺服器中**沒有設計需求** (008004 是手機 / 穿戴 PoP 模組用)。

**判定**: 客戶 JDP 端**沒有任何訊號**顯示 2327 / 2492 有 008004 design-in 或客戶聯合開發案。Apple 對 [[Yageo]] 的關係只到 0402 / 01005 級。

---

## 4. 馬來西亞 [[Walsin Technology]] 廠 (China+1) 設備供應商

### 4.1 公開 capex 與設備招標訊息

- 2025 年底 [[Walsin Technology]] 法說會: 中國地區營收佔 51%, 亞太 26%, 台灣 14%, 歐美合計 < 10%。
- 2026 Q1 法說: 中國降至 46.1%, 亞太升至 28.7% (主因日本 + 馬來西亞擴產)。
- **馬來西亞廠定位**: 「未來最重要的擴產與成長基地」, 對外溝通主軸是**車用 + 高階工業海外樞紐**。
- 整體稼動率約 75-80%, 有擴產空間。

### 4.2 設備供應商訊號 (negative finding)

公開招標 / 採購紀錄 / 公司 ESG 報告**完全沒有提及**:
- [[Hirano Tecseed]] (日本高階流延機, [[Murata]] 主要供應商, 為奈米級介電薄膜印刷專用)
- [[光洋熱工]] (Koyo Thermos) high-end 燒結爐 (sub-micron 介電層均勻燒結用)
- 其他 sub-0.4 mm 級設備 (例如 [[新東工業]] sub-micron 對位機台)

**判定**: 馬來西亞廠的設備採購訊號**完全集中在中大尺寸量產設備**, 沒有「攻 01005 / 008004」的長線 capex 流向。

### 4.3 桃園廠擴產 capex

[[Walsin Technology]] 桃園總部廠定位「高階 / 車規 / 國防工業 / 研發中心」, 公開 capex 揭露**未指向 sub-0.4 mm 製程設備**, 仍是車規高壓 + 軍工 + 部分 0201 imperial Hi-Accuracy。

---

## 5. [[Yageo]] [[Kemet]] 整合 — micro-MLCC 技術 transfer 可能性

### 5.1 [[Kemet]] 技術盤點

- [[Kemet]] 2020/6 被 [[Yageo]] 以 1.8 billion USD 收購, 帶來 21 個生產基地, ~12,500 員工。
- [[Kemet]] 補的技術線: **鉭電容 (主業) + 高分子電解 + film + 電解 + commodity MLCC**。
- **[[Kemet]] 沒有 sub-0.4 mm micro-MLCC 量產能力**, 其 MLCC 業務歷史上是 commodity 級 (0603 imperial 及以上為主), 與 008004 不在同一軌道。

### 5.2 [[TOKIN]] / [[Pulse]] / [[芝浦電子]]

| 併購 | 年 | 補的技術 | 與 008004 相關性 |
|---|---|---|---|
| [[Kemet]] | 2020 | 鉭電容 | 0 (不同產品線) |
| [[Pulse]] | 2020 | 磁性元件 / 電感 | 0 |
| [[TOKIN]] | 2017 (與 Kemet 之前) | 電感 / 磁性 | 0 |
| [[芝浦電子]] | 2026/1 | 車用熱敏電阻 / 感測器 | 0 |
| [[Chilisin]] | 既有 | 電感 | 0 |

**判定**: [[Yageo]] 4 件主併購**沒有一件補進 micro-MLCC 微小化技術**。[[Yageo]] 對外定位是「全方位被動元件 + 鉭電容 leader + AI 伺服器電源」, 不是「對標 Murata 的 micro-MLCC 後進者」。

### 5.3 2026 Q1 法說 — Kemet 鉭電容才是 AI 伺服器主軸

- 2026 Q1: 鉭電容營收 +20% QoQ, backlog / book-to-bill > 1, **30%+ 綁 [[AI 伺服器]]**。
- 這證實 [[Yageo]] 在 AI 紅利中的 hand-on 武器是 **[[Kemet]] 鉭電容 (高分子 + 大容值) + 高壓 0402 MLCC**, 而非 008004。

---

## 6. 法說會 / 年報 hidden hints

### 6.1 [[Yageo]] 2026 Q1 法說 (2026/4/15)

合併營收 NT$38.166 B (+22.7% YoY, +6.1% QoQ), 淨利 NT$8.001 B (+44.7% YoY), EPS NT$3.90, 毛利率 38.1%, 營業利益率 25.2%。對外溝通要點:

1. **AI 營收 mix 14-15%** (上一季 12%), 2026 年預期突破 15%。
2. **鉭電容 ([[Kemet]] 線) 創歷史高 backlog**, 30%+ 綁 AI server。
3. 「我們觀察不到 panic buying」 — 主動降溫市場過熱預期。
4. Q2 指引: 營收溫和成長, 毛利率略升, 提高稼動率。
5. **完全未提及 008004 / sub-0.4 mm 微小化**。對「高階 MLCC 缺貨」與「車規 + AI 高壓高容」是主軸。

**Hidden hint 解讀**: 「車規高階」與「AI server 高壓」**沒有暗示 008004**。Yageo 自己定義的 "high-end" 是**高壓 + 高容值 + 高溫**, 不是「更小尺寸」。

### 6.2 [[Walsin Technology]] 2025 年報

2025 年營收 NT$364.62 億 (持平), 稅後純益 NT$22.98 億 (yoy −22.88%), EPS NT$4.74。法人預估 2026 年營收 NT$390 億 (yoy 高個位數), EPS NT$5.5。

「精準突破、中高階轉單」對應的具體尺寸節點:
- **「精準」 = 0201 imperial Hi-Accuracy + 0402 高容**, 不是 01005 / 008004 跳躍。
- **「中高階」 = 車規 AEC-Q200 + AI 伺服器電源高壓 + 5G 基地台 + 醫療**, 全部是大中尺寸高功率方向。
- **AI 相關營收佔比 ~10%** — 從 100% commodity 跳到「高階 commodity + 車規 + AI」, **沒有微小化 R&D 主軸**。

**Hidden hint 解讀**: [[Walsin Technology]] 2025 年報**完全沒有任何字眼指向 008004 / 01005**, 反而把整個高階定位**鎖在大中尺寸高功率**。

---

## 結論: 隱藏 R&D 強度評分 (0-5)

| 維度 | 訊號量 | 評分 |
|---|---|---|
| 1. 專利 (USPTO + TIPO + Google Patents) | 0 件 sub-0.4 mm claim | 0/5 |
| 2. 學術論文 ([[ECTC]] / [[CIPS]] / [[EPTC]]) | 0 篇 sub-0.4 mm 微小化 | 0/5 |
| 3. 客戶 JDP ([[Apple]] / [[Tesla]] / [[NVIDIA]]) | [[Apple]] 對 [[Yageo]] design-in 0402 級, 無 008004 訊號 | 1/5 |
| 4. 馬來西亞高階設備採購 | 無 [[Hirano Tecseed]] / [[光洋熱工]] high-end 流延 / 燒結機台 | 0/5 |
| 5. [[Kemet]] / [[TOKIN]] / [[Pulse]] / [[芝浦電子]] 整合 | 4 件併購無一補 micro-MLCC | 0/5 |
| 6. 法說會 / 年報 hidden hints | 對外溝通全集中於高壓高容 + 車規, 完全未提 008004 | 1/5 |
| **整體** | **平均 0.33/5, 取整 = 1/5 (低)** | **1/5** |

### 整體結論 (與 Unit 2 結論一致並加強)

1. **[[Yageo]] (2327) / [[Walsin Technology]] (2492) 對 008004 技術節點沒有可驗證的隱藏 R&D pipeline。** 專利端零件、論文端零件、JDP 端零件、設備採購端零件、併購整合端零件、法說會 hints 零件 — 6 個維度一致負向。
2. **[[Yageo]] 對 [[Apple]] 確認在供應商名單內**, 但 design-in 規格止於 0402 / 01005 級, **不延伸至 008004**。Apple 在 008004 PoP 模組單一 source 仍是 [[Murata]] (2019/12 GRM011 100 nF 量產)。
3. **R&D 火力 signature 已明確分流**:
   - [[Murata]] / [[Samsung Electro-Mechanics]] = 微小化 + sub-micron 介電 + 奈米化 [[鈦酸鋇]] 並行
   - [[Yageo]] = 鉭電容 ([[Kemet]]) + 高壓高容 0402 + 車規 + AI server PoL
   - [[Walsin Technology]] = 0402 高容 + 0201 Hi-Accuracy + 車規 + AI 伺服器電源
4. **2026/4-5 月 +245% 漲價 narrative 與 008004 仍無連動**。市場用 2327 / 2492 對標 008004 = 持續錯誤定性。
5. **內部 R&D 樣品的可能性無法 100% 排除** (商業機密), 但**在 5 年 + 6 維度的公開資料中, 沒有任何旁證指向有顯著 sub-0.4 mm pipeline 正在 ramp**。保守研究紀律 = 不可寫入「2327 / 2492 切入 008004」narrative。

### Open questions (留給後續驗證)

1. [[Yageo]] 高雄大發三廠 (2024 Q1 投產) 後續是否會在 2027-2028 增建 sub-0.4 mm 專用產線? — 目前**無對外揭露**。
2. [[Walsin Technology]] 馬來西亞廠 (2025-2027 ramp) 設備招標若未來出現 [[Hirano Tecseed]] / [[光洋熱工]] 採購, 將是首個 sub-0.4 mm 進攻訊號 — 需持續監測 MOPS 公告。
3. [[Sinoceramics]] (6173) 是否會公布 < 100 nm 奈米化 [[鈦酸鋇]] 量產, 將是台廠 008004 物料端 readiness 的指標 — 目前公開規格仍 200 nm 級。
4. [[Apple]] FY2025 / FY2026 supplier list 若 [[Walsin Technology]] 出現, 將是 commodity-to-Apple 升級首訊, 但仍與 008004 無直接關聯。

---

## Sources

### 專利線
- [Google Patents — WO2024247128A1 Multilayer ceramic capacitor (Murata assignee)](https://patents.google.com/patent/WO2024247128A1/en)
- [Justia Patents — US 12,482,604 issued 2025/11/25 (Murata)](https://patents.justia.com/patent/12482604)
- [USPTO — US20240282522A1 Multilayer ceramic capacitor (Murata, 2024/4/30)](https://patents.google.com/patent/US20240282522A1)
- [USPTO — US20250292962 Multilayer ceramic capacitor application (2025/9/18)](https://patents.justia.com/patent/20250292962)
- [Justia — Multilayer Capacitor Class 361/306.3 patent listings](https://patents.justia.com/patents-by-us-classification/361/306.3?page=3)

### 學術線
- [Yageo PSMA Capacitor Technical Forum Webinar (2024/10/22)](https://psma.com/sites/default/files/2024-10/PSMA%20Webinar%2022Oct2024_Fin.pdf)
- [BaTiO3-based MLCC core-shell structure (ACS Applied Materials & Interfaces, 2024)](https://pubs.acs.org/doi/10.1021/acsami.3c16740)
- [Singing MLCC mitigation review (PMC, 2022)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9147252/)

### 客戶 JDP 線
- [Apple Supplier List PDF (Apple Supplier Responsibility)](https://www.apple.com/supplier-responsibility/pdf/Apple-Supplier-List.pdf)
- [Three Taiwanese firms join Apple suppliers list — Yageo Kaohsiung + Suzhou + Dongguan (Taipei Times)](https://www.taipeitimes.com/News/biz/archives/2022/10/05/2003786453)
- [Walsin Technology Automotive MT series AEC-Q200 catalog](http://www.passivecomponent.com/applications/detail_automotive_caps_qualified_to_aec-q200_mt_series/)
- [Walsin Technology automotive applications](https://www.passivecomponent.com/applications/automotive/)
- [Apple supplier list — 8 new Chinese players (DigiTimes 2024)](https://www.digitimes.com/news/a20240424PD220/apple-supplier-supply-chain.html)

### 馬來西亞 / capex 線
- [Walsin Technology Quarterly Reports (IR)](https://www.passivecomponent.com/investor-relations/quarterly-reports/)
- [華新科聚焦高階伺服器, AI 相關佔營收 1 成 (Yahoo Finance)](https://tw.stock.yahoo.com/news/%E8%8F%AF%E6%96%B0%E7%A7%91%E8%81%9A%E7%84%A6%E9%AB%98%E9%9A%8E%E4%BC%BA%E6%9C%8D%E5%99%A8-ai%E7%9B%B8%E9%97%9C%E4%BD%94%E7%87%9F%E6%94%B61%E6%88%90-043400812.html)
- [華新科 China+1 馬來西亞產能 (vocus)](https://vocus.cc/article/6a0b27bafd897800010b06e7)
- [Yageo Kaohsiung Dafa 三廠投產 (Taipei Times, 2018)](http://www.taipeitimes.com/News/front/archives/2018/11/09/2003703876)
- [Yageo new factory 1Q24 (DigiTimes)](https://www.digitimes.com/news/a20231003PD218/ev-yageo.html)

### Kemet 整合線
- [Yageo Kemet integration BCG analysis (MatrixBCG)](https://matrixbcg.com/blogs/competitors/yageo)
- [國巨基美合併效應 — MLCC 產能高雄電子產業 (詠騰)](https://www.ytyut.com/modules/news/article.php?storyid=5985)
- [國巨+基美 PDN High Power Components (Arrow)](https://www.arrow.com/en/research-and-events/articles/kemet-and-yageos-pdn-high-power-components)
- [國巨布局高階 / Kemet 鉭電容 + TLVR 電感單價 +30-50% (CMoney)](https://cmnews.com.tw/article/newsyoudeservetoknow-31fe4bd6-e36b-11f0-a742-7cafaffc4915)

### 法說會 / 年報線
- [Yageo Q1 2026 Results — AI Servers and Pricing Power (passive-components.eu)](https://passive-components.eu/yageo-q1-2026-results-ai-servers-and-pricing-power-behind-a-moderate-q2-outlook/)
- [Yageo 1Q26 +40% YoY profit, AI demand (DigiTimes)](https://www.digitimes.com/news/a20260416PD200/yageo-passive-components-profit-price-ai-demand.html)
- [國巨 Q1 2026 Earnings Call — Revenue +23% to NT$38.2B (BigGo)](https://finance.biggo.com/news/TW_2327.TW_2026-04-15)
- [Yageo strong 1Q26 on AI orders (DigiTimes)](https://www.digitimes.com/news/a20260226PD231/yageo-passive-components-demand-revenue-2026.html)
- [受惠 AI 需求續強, 華新科 2026 年營運增溫 (Yahoo)](https://tw.stock.yahoo.com/news/%E5%8F%97%E6%83%A0ai%E9%9C%80%E6%B1%82%E7%BA%8C%E5%BC%B7-%E8%8F%AF%E6%96%B0%E7%A7%912026%E5%B9%B4%E7%87%9F%E9%81%8B%E5%A2%9E%E6%BA%AB-015300631.html)

### Big-4 對比線
- [Murata 2019/12 World's First 0.1µF MLCC in 008004 GRM011](https://www.businesswire.com/news/home/20191204005290/en/Murata-Develops-Worlds-Multilayer-Ceramic-Capacitor)
- [Samsung Electro-Mechanics MLCC AI Server + Automotive (官網)](https://www.samsungsem.com/global/newsroom/news/view.do?id=9462)
- [Yageo BCG Matrix / Strategy (MatrixBCG)](https://matrixbcg.com/products/yageo-bcg-matrix)
- [Top MLCC manufacturers — Yageo + Walsin position (Unibetter)](https://en.unibetter-ic.com/top-multilayer-ceramic-capacitor-manufacturers/)
- [MLCC for AI Server / Automotive Market Outlook 2026-2034](https://www.intelmarketresearch.com/mlcc-for-ai-serverautomotive-market-36545)

### 內部交叉參考
- `vault/research/008004/02_tw_mid_2327_2492.md` (Unit 2)
- `vault/research/008004/01_spec_and_global_leaders.md` (Unit 1)
- `vault/research/008004/04_tw_upstream_materials.md` (Unit 4 — 信昌電粉體)
- `Pilot_Reports/Electronic Components/2327_國巨.md`
- `Pilot_Reports/Electronic Components/2492_華新科.md`
