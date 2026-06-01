---
type: concept
status: living
last_updated: 2026-06-01
related: [./MLCC_008004.md, ../../themes/MLCC.md, ./edge_ai_inference.md]
tags: [MLCC, 008004, technical_reference, spec, Murata, Samsung_Electro_Mechanics, Taiyo_Yuden, TDK, 鈦酸鋇, 006003, GRM011]
---

# 008004 MLCC — 技術 Deep Dive (永久 reference)

> **角色定位**: 本頁是 008004 規格 / SKU / 材料 / 技術 的**永久技術 reference**。trader decision (受惠強度排序 / pair trade / catalyst 等) 看 [[MLCC_008004]] 主頁。族群供應鏈圖看 [[../../themes/MLCC.md]]。

---

## 1. 規格定義 + 命名陷阱

### 物理尺寸

| 命名 | Length | Width | Thickness | 命名系統 |
|---|---|---|---|---|
| **008004** (imperial) | 0.25 mm (±0.013) | 0.125 mm (±0.013) | ~0.125 mm | EIA inch (0.010" × 0.005") |
| **0201** (metric) | 0.20 mm | 0.10 mm | ~0.10 mm | IEC/EN — 等同 008004 family |

008004 比 01005 (0.4×0.2mm) **掛裝面積縮小 ~50%、體積縮小 ~80%**;體積比 0402 縮小 ~98%。

### 命名陷阱 (CRITICAL — 寫入報告前必驗)

> "Imperial code for 0201 refers to a component that is 0.02 × 0.01 inches, while metric code for 0201 refers to a component that is 0.2 × 0.1 mm. These are completely different sizes." — [olimex blog 2016](https://olimex.wordpress.com/2016/02/15/smt-component-sizes-and-metric-imperial-confusion/)

| 命名 | 實際尺寸 | 等級 |
|---|---|---|
| **imperial 0201** | 0.6 × 0.3 mm (= metric 0603) | commodity, 多家可做 |
| **metric 0201** | 0.2 × 0.1 mm (= imperial 008004) | leading edge, 僅 Big-4 量產 |

TW 媒體報導 [[國巨]] / [[華新科]] 「0201 量產」**99% 指 imperial 0201 (= commodity 0603)**,不是 metric 0201 (= 008004 leading edge)。本 vault 強制規則:任何提到 "0201" 必須先 disambiguate, 否則該數據不得寫入。

### 同代規格家族對照

| Imperial | Metric (近似) | 尺寸 | 量產商業狀態 |
|---|---|---|---|
| 0402 | 1005 | 1.0 × 0.5 mm | commodity, 多家可做 |
| 0201 imperial | 0603 | 0.6 × 0.3 mm | high-volume, 含 [[Yageo]] / [[華新科]] / [[國巨]] |
| 01005 | 0402 | 0.4 × 0.2 mm | high-end, 少數中小廠開始切入 (含 [[Yageo]]) |
| **008004** | **0201 metric** | **0.25 × 0.125 mm** | **leading edge — 僅 Big-4 量產** |
| 006003 | (Murata 自有命名) | 0.16 × 0.08 mm | [[Murata]] 2024/09 CEATEC 唯一發表, 量產時程 2026 末-2027 H1 |

---

## 2. 技術門檻 — 為什麼只有 4 家能做

### 2.1 介電層厚度 < 0.5 μm

- [[Samsung Electro-Mechanics]] 公開揭露 **「600+ 層堆疊 + 介電層 < 0.5 μm」** 為 state-of-the-art [SEMCO CEO 2026/04 inteview](https://en.sedaily.com/finance/2026/04/23/samsung-electro-mechanics-ceo-worlds-only-ai-core-component)
- 學術:"Ultra-thin multilayer ceramics capacitors (MLCCs) with layer thickness less than 1 μm are in urgent demand" — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2772834X22000082)
- 物理:厚度 < 1 μm 後,每層介電必須含 **4-5 顆 [[鈦酸鋇]] 晶粒**才能維持絕緣可靠度,否則漏電流暴增、可靠度崩盤

### 2.2 層數 > 600 層

- [[Samsung Electro-Mechanics]] 公開揭露 600+ 層為 state-of-the-art
- [[Murata]] 雖未公開層數,但 008004 0.1 µF 達成 (GRM011R60J104M) 意味同等級堆疊密度
- 每片陶瓷生坯 (green sheet) 厚度需 < 1 μm,且 600 層必須完全對齊;任一層偏移即整顆報廢

### 2.3 [[鈦酸鋇]] (BaTiO₃) 粒徑 50-100 nm

- 008004 規格要求 BaTiO₃ 粒徑下探 50-120 nm,並保證在燒結後仍維持 tetragonal 相 — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0169433224018245)
- 全球能穩定供應 sub-100 nm BaTiO₃ 的廠商**極度集中**:
  - **[[Sakai 化學]]** (堺化學工業): 全球 MLCC 介電粉體市占 ~18-30%,sub-100 nm 業界龍頭
  - **[[Nippon Chemical]]** (日本化學工業): 全球 ~15%
  - **[[Fuji Titanium]]** (富士鈦工業) / **[[Toho Titanium]]** (東邦鈦工業): 補位
  - **[[Ferro]]** (美商, 現屬 [[Prince International]]): 中階, nano 不是強項
  - 前五大合計 ~48% 全球供給
- 製程 know-how: **水熱法 (hydrothermal) + 草酸鹽法 (oxalate)** 是 nano-grade BaTiO₃ 關鍵 know-how, 日商累積數十年配方且專利保護綿密
- TW 唯一玩家 **6173 [[信昌電]]** 目標 200 nm → 100 nm, 2027 Q3 六甲新廠 (11.6 億 capex) 投產

### 2.4 內電極鎳線寬 < 0.5 μm

- 008004 採 BME (Base Metal Electrode) [[Ni]] 內電極, 線寬縮至 sub-μm 級
- Ni 漿料 (Ni paste) 印刷+燒結後不得斷裂、不得氧化, 需 controlled atmosphere 燒結爐
- 鎳粉粒徑 50-80 nm, 球形度高, 分散均勻 (D90/D10 < 2)
- 寡占供應商:
  - **[[Shoei Chemical]]** (昭榮化學) — 全球領先, 化學還原法, 與 [[Murata]] toll refining 緊密合作 (50-200 nm, 有 < 80 nm 細粉)
  - **[[Daiken Chemical]]** (大研化學) — 供 [[TDK]] / [[Taiyo Yuden]] (100-300 nm)
  - **[[JFE]] Mineral** — 鎳粉原料 + 漿料, 垂直整合
- TW 目前**無一家上市公司**具備量產 < 100 nm 鎳粉 / 鎳漿能力

### 2.5 設備與檢測門檻 (補)

- 多層 sheet 疊合機:**clean room class 100** + sub-μm 對位精度
- AOI / X-ray 全檢:600 層內部結構必須逐顆檢測, CapEx 動輒數百 mUSD/line
- 業界共識:008004 級 line 良率 < 80% 為常態 (vs 0402 commodity > 95%)
- 設備寡占:[[Hirano Tecseed]] 流延機、[[光洋熱工]] 燒結爐

---

## 3. Murata GRM011 量產 SKU 詳表

從 DigiKey / Mouser / TME 商業庫存可確認的 [[Murata]] GRM011 series (008004 inch = 0.25 × 0.125 mm) 公開 part number:

| Part Number | 容值 | 耐壓 | 介電 | 公差 | 用途 |
|---|---|---|---|---|---|
| **GRM011R60J104M** | **0.1 µF** | 6.3V | X5R | ±20% | **世界首發 0.1 µF in 008004**, 2019/12 量產, 5G 智慧手機 PoP 模組去耦核心 |
| **GRM011R60J104ME01L** | 0.1 µF | 6.3V | X5R | ±20% | DigiKey/Mouser 商業庫存 part code |
| GRM011R61A101KE01L | 100 pF | 10V | X5R | ±10% | 通用去耦, TME 商業庫存 |
| GRM011 C0G (Class I) | 1 pF – 0.1 µF | 4-6.3V | C0G (NP0) | ±5% | RF / 高 Q / 高頻去耦, 溫度補償 |
| GRM011 X5R (Class II) | 100 pF – 0.1 µF | 4-10V | X5R | ±10-20% | 一般去耦 |

**2026/04** [[Murata]] 推出 008004 0.1 µF GRM011R60J104M 量產量, 搭配 **Izumo 新廠 JPY 47B (~EUR 254.6M)、70,000 m²** 於 4/3 完工。

---

## 4. Big-4 全球量產對照

| 廠商 | 008004 status | 006003 (next-gen) | 2026 漲價 | TW 代理 |
|---|---|---|---|---|
| **[[Murata]]** | 2014 ferrite bead 首發, 2019 量產 0.1µF (Apple/Huawei 5G), 2026/04 升級 GRM011 0.1µF | **2024/09 CEATEC 首發** 0.16×0.08mm, 量產 2026 末-2027 H1 | **+15-35%** (4/1) | (直銷) |
| **[[Samsung Electro-Mechanics]]** | "Ultra-Compact 008004 inch High-Q MLCC" 商品化, **600+ 層、<0.5μm 介電** | 未公告 | +5-10% (4 月評估) | **3090 [[日電貿]]** |
| **[[Taiyo Yuden]]** | 產品線內已列 008004 (Newark 商業庫存); 2025/03 sample shipment, 2025/09 新潟廠量產 | 未公告 | **+6-13%** (5 月) | **8043 [[蜜望實]]** (獨家 30+ 年) |
| **[[TDK]]** | 學術文獻提及, 商業 SKU 較少公開 | 未公告 | 未公告 | (零售為主) |

**全球市占**:[[Murata]] >40% 整體 MLCC / 高階 ~26%;**Murata + SEMCO 合計 AI server 高階 MLCC 市占 > 80%**。

---

## 5. ASP 倍數估算

| Spec | ASP/顆 (USD est) | 倍數 (相對 0402) |
|---|---:|---:|
| 0402 (commodity, 1.0 × 0.5 mm) | $0.002–0.005 | 1× |
| 0201 imperial (= 0603, 0.6 × 0.3 mm) | $0.005–0.012 | 2-3× |
| 01005 (0.4 × 0.2 mm) | $0.015–0.030 | 6-8× |
| **008004** | **$0.040–0.100** | **15-30×** |
| 006003 (next-gen) | sample stage | n/a |

ASP 倍數驅動: 良率 (< 80% vs commodity > 95%) + 設備折舊 + nano BaTiO₃ 粉體成本 + 內電極 Ni 細粉成本。

---

## 6. 應用場景 — 為什麼非 008004 不可

### 6.1 智慧型手機 PoP (主場)

- [[Apple]] iPhone 12 (2020) 首次大量採用, **iPhone 17 Pro 估 160-250 顆/支** (占總 MLCC ~20-25%)
- 用途: 5G mmWave PA 模組去耦、AP 與 PMIC 之間高密度去耦、RF front-end
- 替代不可能: 0201 (0.6×0.3mm) PCB 空間擺不下 600+ MHz 高頻去耦陣列
- [[Samsung]] Galaxy S26 Ultra 估 150-200 顆/支, SEMCO 自家垂直整合
- [[Google]] Pixel 11 估 ~150 顆/支, Murata / Taiyo Yuden 雙源

### 6.2 AI 伺服器 GPU 主機板

- [[NVIDIA]] [[GB300]] NVL72 ~45 萬顆 MLCC/櫃, MLCC content ~$1,500/櫃
- 008004 估占顆數 **5.6%** (~25,000 顆/櫃) 但占 ASP **45%** (NT$112.5K / NT$248.75K 單櫃 MLCC)
- 用途: HBM 旁高密度去耦 (HBM 旁 PCB 空間極限)
- [[Vera Rubin]] VR200 機櫃 MLCC content **$4,300/櫃 (+182% vs GB300)** [Morgan Stanley via Bitget](https://www.bitget.com/news/detail/12560605422208)
- 估 Vera Rubin 008004 用量 ~50,000-80,000 顆/櫃

### 6.3 5G mmWave 模組

- 28/39 GHz 高頻路徑必須緊靠 IC 擺放高 Q 因子電容
- C0G (NP0) 介電在 008004 為唯一可行尺寸

### 6.4 Apple Vision Pro / AR/VR 穿戴 + 軍用 / 醫療植入

- 空間極限, 008004 + 006003 雙占
- 助聽器 / 醫療植入 (peacemaker, ICD)
- 軍用緊湊型電子模組

---

## 7. 2026 漲價時間軸

| 日期 | 廠商 | 漲幅 | 適用品項 |
|---|---|---|---|
| **2026/4/1** | **[[Murata]]** | **+15-35%** | AI server 高電容、車規、RF/microwave |
| 2026/4 月底 | [[Taiyo Yuden]] 宣布 | +6-13% | 中低容值消費 + 車用 |
| **2026/5/1** | **[[Taiyo Yuden]] 生效** | +6-13% | 同上 |
| 2026/4 起 | [[Samsung Electro-Mechanics]] | +5-10% | 通知 distributor |
| 2026/5 月 | [[國巨]] (TW) | "價格結構調整" | commodity 跟進 |

**Murata 官方主因**: 白銀 (Silver) 價格飆升 (太陽能 + EV + 半導體 + AI + 醫療共爭) + AI server 把高階產能稼動率推上 80%+。
**次因 (analyst)**: Murata FY2024 (2025/03) 營業利益率掉到 13.1%, 接近 peak 腰斬, 需 reprice 找回 margin。

---

## 8. 006003 — Murata 下一代殺手鐧 (DEDUP 注意)

- **[[Murata]] 2024/09/18 BusinessWire** 發表 **006003** (0.16 × 0.08 mm) — [press release](https://www.businesswire.com/news/home/20240918232327/en/Murata-Unveils-the-Worlds-Smallest-Multilayer-Ceramic-Capacitor-with-the-First-006003-inch-Size-0.16mm0.08mm-Device)
- 體積比 008004 再縮小 **75%**
- **CEATEC JAPAN 2024** (2024/10/15) 公開展出
- Murata 自有命名 (non-EIA standard, 呼應 0.006 × 0.003 inch)
- ⚠️ **不要寫成 005003** — TW 媒體常把 006003 跟臆測中的 005003 混用, 本 vault 強制以 **006003** 為準

### 對 008004 的衝擊 (ASP cliff window)

- 量產初期 yield 仍低, 2026 主要應用仍將是 smartphone 高階模組 (RF front-end, PA module), AI server 因 board area 寬鬆暫不 migrate
- 008004 在 AI server / 高階 smartphone / 車規高密度 ECU 仍是 **2026-2028 主力規格**, 不會被 006003 快速 cannibalize
- 但 [[Murata]] 公開 006003 即意味其 008004 製程已成熟、可往下世代邁進, 鞏固 leadership gap
- **量產正式公告 (估 2026 末-2027 H1) = 008004 ASP cliff window 開啟**, 是 TW 代理通路 (8043/3090) 退場訊號

---

## 9. TW 受惠強度排序 (摘自 [[MLCC_008004]])

```
Tier 1 直接 5/5: 8043 [[蜜望實]] (Taiyo Yuden 獨家代理) ≥ 3090 [[日電貿]] (SEMCO 官方代理)
Tier 2 間接 3/5: 6173 [[信昌電]] (粉體 100nm 2027 才到) > 4760 [[勤凱]] (Cu paste 2026 進日本)
Tier 3 零暴露但被誤 lump: 2327 [[國巨]] ≈ 2492 [[華新科]] ≈ 3026 [[禾伸堂]]
```

詳細排序邏輯、6/1 三大法人結構修正、pair trade 建議, 看 [[MLCC_008004]] trader decision page。

---

## 10. 研究檔案索引

| 維度 | 檔案 |
|---|---|
| 規格 + Big-4 全球 (含本頁 SKU 表來源) | `../research/008004/01_spec_and_global_leaders.md` |
| TW 中游真實 exposure | `../research/008004/02_tw_mid_2327_2492.md` |
| TW 利基 (3026/6173) | `../research/008004/03_tw_niche_3026_6173.md` |
| TW 上游材料端 | `../research/008004/04_tw_upstream_materials.md` |
| TW 代理通路 | `../research/008004/05_tw_distributors_3090_8043.md` |
| 下游 BOM + Pair trade + 風險 | `../research/008004/06_downstream_and_takeaway.md` |
| (NEW) 代理通路深度驗證 | `../research/008004/07_distributors_deep.md` |
| (NEW) 上游材料深度驗證 | `../research/008004/08_upstream_deep.md` |
| (NEW) TW 隱藏候選 | `../research/008004/09_hidden_candidates.md` |
| (NEW) 2327/2492 R&D pipeline | `../research/008004/10_rd_pipeline.md` |
| (NEW) Catalyst calendar | `../research/008004/11_catalyst_calendar.md` |
| **族群供應鏈圖** | `../../themes/MLCC.md` |
| **Trader decision page** | `./MLCC_008004.md` |

---

**Source**: 6 unit slice research (PR #23) + 今日 web search (Murata GRM011 SKU + Big-4 update + 漲價時間軸) + 第二輪 5 unit verification batch (in progress 2026-06-01)

**Status**: living — 隨 Big-4 漲價 / 006003 量產進度 / TW 隱藏候選驗證結果而更新
