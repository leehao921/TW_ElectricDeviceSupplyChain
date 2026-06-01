# Vera Rubin VR200 AI 機架供應鏈

> [[NVIDIA]] 下一代 AI 機架平台 (2026 H2 量產),Rubin GPU + Vera CPU + HBM4。**單櫃 BOM ~$13.17M vs GB300 $8.10M = +62.6% YoY** (12 細類拆解, 本 vault batch 結果)。對照 [[Morgan Stanley]] 公開估計 VR200 機櫃 ~$7.8M。

**涵蓋公司數:** 35+ TW listed

**相關主題:** [[NVIDIA]] | [[AI 伺服器]] | [[CoWoS]] | [[HBM]] | [[MLCC]] | [[CCL]] | [[ABF 載板]] | [[液冷散熱]] | [[CPO]]

---

## 平台規格速覽

| 項目 | VR200 (NVL72/NVL144) | GB300 NVL72 (baseline) |
|---|---|---|
| GPU | Rubin (TSMC N3P + CoWoS-L 4x reticle) | B300 (TSMC N4P + CoWoS-L 3.3x reticle) |
| CPU | Vera (88 ARM Olympus cores, TSMC 3nm) | Grace (72 ARM Neoverse V2, TSMC 4NP) |
| Memory | HBM4 (288 GB/GPU, 22 TB/s) | HBM3e (288 GB/GPU, 8 TB/s) |
| NVLink | NVLink 6 (3.6 TB/s) | NVLink 5 (1.8 TB/s) |
| Power | **800V HVDC** (sidecar PSU) | 12V/48V SMR |
| Cooling | Closed-loop liquid (D2C, 2N CDU) | Closed-loop liquid (D2C, N+1 CDU) |
| 機架功耗 | 250 kW | 120 kW |
| 量產時程 | 2026 H2 | 已量產 (2025 Q4-) |

---

## 12 細類 BOM YoY 對照 (本 batch 計算結果)

| Rank | 細類 | VR200 USD | GB300 USD | YoY % | 主導 TW 受惠 |
|---|---|---:|---:|---:|---|
| 1 | **CCL 銅箔基板** | 38,400 | 10,520 | **+265%** | **2383 [[台光電]]** (M8 share 70-80%) > 6274 [[台燿]] > 6213 [[聯茂]] |
| 2 | **PCB + HDI 主板** | 390,400 | 117,000 | **+234%** | **2313 [[華通]]** (5/5) > 4958 [[臻鼎-KY]] > 3037 [[欣興]] |
| 3 | **Connector + Network** | 674,040 | 225,000 | **+200%** | **3533 [[嘉澤]]** (SXM7+UQD+224G) ≈ 3665 [[貿聯-KY]] > 6669 [[緯穎]] |
| 4 | **MLCC + 鉭電容** | 4,335 | 1,600 | **+171%** | T1: **8043 [[蜜望實]]** ≈ 3090 [[日電貿]];T2: 6173 [[信昌電]] (Mega Cap) |
| 5 | **CPU silicon** | 234,000 | 126,000 | **+86%** | **2330 [[TSMC]]** (唯一晶圓) |
| 6 | **ABF substrate** | 199,800 | 109,620 | **+82%** ([[Morgan Stanley]] anchor) | **3037 [[欣興]]** (Rubin GPU 主供) > 8046 [[南電]] > 3189 [[景碩]] |
| 7 | **HBM (memory)** | 1,440,000 | 864,000 | **+67%** | **1717 [[長興]]** (HBM underfill/EMC) + 3711 [[日月光投控]] + 2449 [[京元電子]] |
| 8 | **GPU silicon** | 3,960,000 | 2,520,000 | **+57%** | **2330 [[TSMC]]** + 3711 [[日月光投控]] + 2449 [[京元電子]] |
| 9 | **Optical pluggable** | 6,063,900 | 4,017,500 | **+51%** | 3163 [[波若威]] > 3081 [[聯亞]] > 4979 [[華星光]] |
| 10 | **Liquid cooling** | 120,780 | 107,675 | **+12%** ([[Morgan Stanley]] anchor) | **3324 [[雙鴻]]** > 3017 [[奇鋐]] > 3483 [[力致]] |
| 11 | Memory (DRAM/SSD) | — | — | — | DRAM 弱 TW (SK Hynix);**8299 [[群聯]]** (NAND controller) |
| 12 | Power HVDC | 46,845 | — (baseline 缺) | — | **2308 [[台達電]]** #1 (HVDC sidecar reference design) > 6173 [[信昌電]] |
| | **TOTAL** | **$13.17M** | **$8.10M** | **+62.6%** | |

> 注:對 [[Morgan Stanley]] 公開估計 VR200 機櫃 ~$7.8M, 本表 $13.17M 偏高,主因 Optical 細類 ($6.06M) 可能含 scale-out 整片網路 (不只單機架). MLCC 細類 $4,335 與 Morgan Stanley $4,300 anchor 精準對齊;ABF +82% / Cooling +12% 都是 anchor 對齊;CCL +265% 為 worker 自行推估 (M8 大幅升級), 信度中等. 詳見 `analysis/reports/2026-06-01_vera_rubin_bom.md`.

---

## 上游 (晶圓 + 封裝 + 材料) (10)

### 晶圓 + 先進封裝

- **2330 [[TSMC]]** — Rubin GPU N3P 晶圓 + Vera CPU N3P + [[CoWoS]]-L 4x reticle 封裝, 全球獨家供應
- **3711 [[日月光投控]]** — OSAT (HBM-on-CoWoS 終端組裝, 後段封裝外溢)
- **2449 [[京元電子]]** — Burn-in / FT / SLT, AI 營收占比 75-77%

### 基板載板

- **3037 [[欣興]]** — [[ABF 載板]] 全球 #2 (~18%), Rubin GPU 主供, 65% 資本支出投入 ABF 擴產
- **8046 [[南電]]** — ABF 載板 #3, 台塑集團, Rubin second source
- **3189 [[景碩]]** — ABF 第三家 (~7%), [[ECiP]] 嵌入式被動元件路徑同步

### 材料

- **2383 [[台光電]]** — M7/M8 [[CCL]] 龍頭, AI server OAM/UBB share 70-80%
- **6274 [[台燿]]** — M7 CCL 2nd source, [[NVSwitch]] 切入
- **6213 [[聯茂]]** — M6/M7 CCL, AI 切入中
- **1717 [[長興]]** — dry-film photoresist 全球 #1 + HBM4 underfill / EMC

---

## 中游 (PCB 製造 + 被動元件 + 連接器) (12)

### PCB 製造

- **2313 [[華通]]** — 高階 HDI + 軟硬結合板, Rubin GPU board (24-26 層 + Megtron 9), 5/5 受惠強度
- **4958 [[臻鼎-KY]]** — 全球 PCB #1, 厚銅板 (HVDC backplane)
- **3037 [[欣興]]** — HDI 主板 (與 ABF 不同產品線)
- **8046 [[南電]]** — HDI 旁支

### 被動元件 (代理通路為 TW alpha)

- **8043 [[蜜望實]]** — Taiyo Yuden 獨家代理, **GB300 一台 ~45 萬顆 MLCC** (本 vault 008004 prior batch 詳述)
- **3090 [[日電貿]]** — SEMCO 官方代理 + Nippon Chemi-con
- **6173 [[信昌電]]** — 自製 [[BaTiO₃]] 粉體 + Mega Cap 高壓 MLCC (PSU 1400-1800 顆/櫃 GB200, VR200 估 2200-2800), NP0 100nm 2027 Q3

### 連接器

- **3533 [[嘉澤]]** — Lotes, SXM7 socket + UQD + 224G PAM4 connector, 25%+ margin
- **3665 [[貿聯-KY]]** — NVLink copper backplane cable assembly
- **6669 [[緯穎]]** — NVL144 rack ODM
- **3017 [[奇鋐]]** — 機構件 + UQD bracket (與 cooling unit overlap)

---

## 下游 (散熱 + 機殼 + 光學) (8)

### 散熱 (3324 / 3017 / 3483 三雄)

- **3324 [[雙鴻]]** (Auras) — 散熱龍頭, [[NVIDIA]] MGX cooling reference, Vera Rubin reference design 入選
- **3017 [[奇鋐]]** (AVC) — GPU 冷板 + 風扇
- **3483 [[力致]]** (Forcecon) — 風扇 + 散熱模組

### 機殼 / 機構件

- **8210 [[勤誠]]** — 機殼 + 結構件
- **2354 [[鴻準]]** — CNC 件 + 機構件

### 光學 (CPO + pluggable)

- **3163 [[波若威]]** — CPO 光纖套件, NVIDIA 生態系
- **3081 [[聯亞]]** — InP 磊晶 (光通訊 雷射晶圓)
- **4979 [[華星光]]** — [[Marvell]] 800G/1.6T 模組代工, 量最大

---

## Power (HVDC + 800V 革新) (4)

- **2308 [[台達電]]** — 800V HVDC sidecar PSU **TW 唯一 reference design 供應** (H2 2026 樣品)
- **2301 [[光寶科]]** — PSU 第二供應
- **6173 [[信昌電]]** — Mega Cap (前述被動元件)
- **5285 [[啟碁]]** — 部分 PMIC

---

## 相關公司 (背景) (5)

- **6669 [[緯穎]]** (Wiwynn) — VR200 機櫃 ODM (Meta/Microsoft/AWS hyperscaler)
- **2382 [[廣達]]** — NVIDIA HGX/NVL72 reference design 主力 ODM
- **2317 [[鴻海]]** — 整機組裝
- **5483 [[中美晶]]** — wafer
- **3596 [[智易]]** — 網通 (背景, CPE focus 非 AI rack)

---

## 投資 takeaway

### Tier 1 直接受惠 (++ alpha)

| Ticker | 公司 | 路徑 | YoY 受惠強度 |
|---|---|---|---|
| **2330** | [[TSMC]] | GPU + CPU + CoWoS-L 寡占 | **+57% (GPU) + +86% (CPU)** |
| **2383** | [[台光電]] | M8 CCL 寡占, OAM/UBB 70-80% share | **+265%** (族群最強 YoY) |
| **3037** | [[欣興]] | Rubin GPU ABF 主供 | **+82%** (anchor) |
| **2313** | [[華通]] | GPU board HDI 主供, 5/5 強度 | **+234%** |
| **3533** | [[嘉澤]] | SXM7 + UQD + 224G connector | **+200%** |
| **3324** | [[雙鴻]] | Vera Rubin cooling reference | +12% (低 YoY 但量大) |
| **8043** | [[蜜望實]] | Taiyo Yuden MLCC 獨家代理 | +171% (MLCC 細類) |
| **3090** | [[日電貿]] | SEMCO 官方代理 | +171% (同上) |
| **2308** | [[台達電]] | 800V HVDC sidecar 唯一 TW reference | 新增 line item |

### Tier 2 間接 / 附屬受惠

- 6274 [[台燿]] (CCL #2), 6213 [[聯茂]] (CCL #3)
- 8046 [[南電]] (ABF #2), 3189 [[景碩]] (ABF #3)
- 4958 [[臻鼎-KY]] (PCB), 3711 [[日月光投控]] (HBM-on-CoWoS), 2449 [[京元電子]] (KGSD)
- 6173 [[信昌電]] (Mega Cap), 1717 [[長興]] (HBM underfill)
- 3081 [[聯亞]] (InP), 4979 [[華星光]] (Marvell 模組)

### 觀察 catalyst

- **2026 H2** — VR200 NVL72 試樣 / 量產時程確認 ([[Computex]] 2026/6/2-6/6)
- **2026/10/14-18** — [[CEATEC]] (Murata 006003 next-gen 公開)
- **2027** — Rubin Ultra Photonic ([[CPO]] 全面導入起點)

---

## Risks

- VR200 量產延後 → 整族群 derate
- [[Murata]] 006003 量產 (2026 末-2027 H1) → 008004 ASP cliff → 8043/3090 derate
- Vera CPU 良率 (88 ARM Olympus cores, custom 設計)
- [[CPO]] 跳級 M9 / 矽光子 取代 M8 CCL → 2383 台光電 risk

---

## Sources

- [Morgan Stanley VR200 BOM via Bitget News](https://www.bitget.com/news/detail/12560605422208)
- [Tomshardware VR200 deep dive](https://www.tomshardware.com/pc-components/gpus/nvidias-vera-rubin-platform-in-depth-inside-nvidias-most-complex-ai-and-hpc-platform-to-date)
- [SemiAnalysis NVIDIA GTC 2025 — Rubin / Vera](https://semianalysis.com/2025/03/19/nvidia-gtc-2025/)
- [Wccftech VR200 memory price surge](https://wccftech.com/nvidia-vera-rubin-rack-hit-with-memory-price-surge-pushing-hbm4-lpddr5x-bill-to-2m-of-7-8m-total/)
- 12 個 unit slice 在 `vault/research/vera_rubin_bom/`
- TimescaleDB query: `bom_components` table in `tmf_market_data` (84 rows across 12 categories × 2 platforms)
