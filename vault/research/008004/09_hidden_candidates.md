---
type: research
status: draft
last_updated: 2026-06-01
source_unit: 9
tags: [MLCC, 008004, hidden, equipment, inspection, chemicals, embedded_passive]
---

# Unit 9: TW 隱藏候選廠商挖掘

> Prior batch 已涵蓋 [[國巨]] (2327) / [[華新科]] (2492) / [[禾伸堂]] (3026) / [[達方]] (8163) / [[佳邦]] (6284) / [[蜜望實]] (8043) / [[日電貿]] (3090) / [[全科]] (3209) / [[信昌電]] (6173) / [[國揚實]] (4760) 以及排除 [[千如]] (3236)。
> Themes/MLCC.md 已列同步受惠 PCB/CCL: [[2313 華通]] / [[3037 欣興]] / [[4958 臻鼎-KY]] / [[8046 南電]] / [[2383 台光電]] / [[6213 聯茂]] / [[6274 台燿]]。
> 本 unit 探討「設備 / 檢測 / 化學品 / 載板嵌入 / SMT picker」5 條新挖掘路徑。

---

## TL;DR — 哪幾家真有切入機會?哪幾家是 noise?

| Ticker | 公司 | 路徑 | 受惠強度 | 結論 |
|---|---|---|---|---|
| 3455 | [[由田]] | AOI 檢測 ([[CoWoS]]/[[ABF]] 載板外觀) | ★★ | **間接候選** — AOI 平台可延伸至 MLCC 外觀全檢,但目前主力在 IC 載板 |
| 3030 | [[德律]] | AXI X-ray + SPI + AOI for PCBA | ★★ | **下游受惠** — 008004 焊接後 PCBA 檢測剛性需求,主檢測 line 必備 AXI |
| 2360 | [[致茂]] | 半導體/電源測試 | ★ | **noise** — 主攻晶圓級測試與 EV 充電樁,非 MLCC 製程 line |
| 6510 | [[精測]] | MEMS 探針卡 | (排除) | **noise** — 客戶為晶圓/封測,與 MLCC 無關 |
| 3551 | [[世禾]] | 半導體製程零組件精密清洗 | (排除) | **noise** — 清洗 PVD/CVD/Etch 零件,非 MLCC 燒結爐 |
| 3413 | [[京鼎]] | 半導體前段製程設備代工 ([[Applied Materials]]) | (排除) | **noise** — CMP/PVD/CVD 製程屬晶圓段,非陶瓷流延 |
| 6187 | [[萬潤]] | 先進封裝點膠/塗佈/AOI | ★★ | **間接候選** — 設備平台 (點膠 + 塗佈 + AOI) 可延伸 MLCC 端電極塗佈/AOI,但目前主力 [[CoWoS]] |
| 1560 | [[中砂]] | 鑽石砂輪 + 晶圓 CMP 墊 | (排除) | **noise** — 終端應用在晶圓拋光,非 MLCC 研磨 |
| 4722 | [[國精化]] | UV 固化材料 + Low Dk/Df 樹脂 ([[CCL]]) | ★ | **noise (但可作 CCL 路徑)** — 主攻高頻 CCL 樹脂,非 tape casting 分散劑 |
| 1711 | [[永光]] | 染料 + 封裝膠材 + 顯影液 | (排除) | **noise** — 客戶為封測/載板,非 MLCC tape casting 化學品 |
| 1304 | [[台聚]] | PE/EVA 通用石化 | (排除) | **noise** — 通用塑料,無細微化學品 line |
| 3037 | [[欣興]] | [[ABF 載板]] | ★★★ | **載板嵌入路徑要角** — ECiP 嵌入 MLCC 路徑,長線取代 picker |
| 8046 | [[南電]] | [[ABF 載板]] | ★★★ | **同上** — [[NVIDIA]]/[[AMD]] 載板嵌入路徑 |
| 3189 | [[景碩]] | [[ABF 載板]] + [[BT 載板]] | ★★ | **同上** — 嵌入式被動元件路徑同步受惠 |
| 4977 | [[眾達-KY]] | (光通訊模組 OEM,非 ABF 載板) | (排除) | **prompt 列錯** — 4977 主業為 [[Broadcom]] 光模組代工,與 ABF 載板無關 |
| 4919 | [[新唐]] | 微控制器 + Power IC | (排除) | **noise** — IC 設計公司,非 SMT 設備 |

**淨新增建議候選**: **3030 [[德律]]** (下游受惠) + **3455 [[由田]]** (間接) + **6187 [[萬潤]]** (間接) 三家設備檢測廠;載板嵌入 (ECiP) 路徑長線可推 **3037 [[欣興]] / 8046 [[南電]] / 3189 [[景碩]]**,但對 008004 是 **替代威脅** 而非受惠。

---

## 1. 設備端 — MLCC 製程設備 TW 玩家

### 1.1 製程關鍵設備全景

| 製程步驟 | 設備類型 | 全球寡占者 | TW 可能切入者 |
|---|---|---|---|
| 漿料製備 (slurry) | 分散機 / 球磨機 | 日本 [[Murata]] 自製、德商 [[Eirich]] | 無 (規模門檻太高) |
| 流延 (tape casting) | 流延機 | 日本 [[Hirano Tecseed]] / [[Murata]] 自製 | **無 TW 玩家** (核心設備寡占) |
| 多層堆疊 (lamination) | sheet 堆疊機 (sub-μm 對位) + clean room class 100 | 日商 (細節 NDA) | **無** (對位精度門檻) |
| 切割 (dicing) | 微細切割機 | 日商 [[Disco]] | 無 |
| 燒結 (sintering) | 還原氣氛燒結爐 | 日商 [[光洋熱工]] (Koyo Thermo) 寡占 | **無** (爐體工藝 know-how 高) |
| 端電極塗佈 (end-termination) | 沾錫機 / 塗佈機 | 日商寡占 | **6187 [[萬潤]]** (點膠/塗佈設備平台,可延伸但目前未驗證 MLCC line) |
| 電鍍 (Ni/Sn plating) | 桶式電鍍線 | 德商 [[Atotech]] / 日商 | 無 |
| 外觀檢測 (AOI) | AOI | 多家 | **3455 [[由田]]** / **6187 [[萬潤]]** (設備平台延伸) |
| 電性測試 + X-ray 全檢 | AXI | [[Test Research Inc]] / 德商 [[Goepel]] | **3030 [[德律]]** (AXI X-ray + ICT,但 line 在 PCBA 端) |
| Tape & Reel | 自動編帶機 | 日商 | 無 |

### 1.2 候選逐家評估

**2360 [[致茂]]** ([[Chroma ATE]]):
- 自家描述為「半導體/IC 測試 + 電力電子測試 + AI 伺服器測試 + 光電檢測 + AOI」5 大產品線。
- **MLCC 製程 line 未列入** — 致茂的測試設備系統定位在晶圓級 / 封裝級 / 系統級,而非 MLCC 量產 line (吞吐量需求每分鐘上萬顆,與致茂 EV 電池測試 / GPU IC 測試的單顆精密測試模式不匹配)。
- 結論: **noise**,雖名稱有「AOI」但實際 line 不重疊。
- 來源: Pilot_Reports/Scientific & Technical Instruments/2360_致茂.md (本 repo)。

**1560 [[中砂]]**:
- 主力 = 鑽石砂輪 + 晶圓 CMP pad + 半導體 CMP 拋光液。
- MLCC 製程的研磨在「漿料端球磨」,跟「晶圓 CMP」是不同物理 — MLCC 不需要 CMP pad。
- 結論: **noise**。

**6187 [[萬潤]]**:
- 主力 = 半導體後段封裝設備 (點膠機、散熱貼合機、塗佈機、曝光機、AOI 檢測機),九成營收來自半導體。
- **理論上可延伸**: 點膠 + 塗佈平台可服務 MLCC 端電極塗佈;AOI 平台可服務 MLCC 外觀全檢。
- **實際 BOM 上未驗證有打入 [[Murata]]/[[太陽誘電]]/[[國巨]]/[[華新科]] 的 MLCC line** (因產線在日本與被動元件廠內部,設備寡占高)。
- 結論: **間接候選 ★★** — 設備平台可延伸,但目前營收 100% 由 [[台積電]] [[CoWoS]] 與 OSAT 貢獻,MLCC 視為 optional upside。
- 來源: Pilot_Reports/Specialty Industrial Machinery/6187_萬潤.md。

**3413 [[京鼎]]** / **3551 [[世禾]]**:
- 兩家都在半導體前段製程設備生態 ([[Applied Materials]] / PVD / CVD / 蝕刻 / 清洗)。
- MLCC 流延 + 燒結 與這些製程毫無交集 (陶瓷粉末 vs. 晶圓矽製程是兩個物理世界)。
- 結論: **排除**。
- 來源: Pilot_Reports/Semiconductor Equipment & Materials/3413_京鼎.md, 3551_世禾.md。

---

## 2. 檢測端 — MLCC AOI / X-ray 全檢

### 2.1 008004 為何必須逐顆 X-ray 全檢?

- 008004 = 0.25mm × 0.125mm × 0.125mm,**容量 1μF/4V** (X5R/X7R),**逾 600 層介電層**(每層 < 0.3μm)。
- 內部缺陷 (delamination / 內電極錯位 / 龜裂) 肉眼不可見,純 AOI 無法檢出。
- 必須在內電極堆疊後 + 燒結後,以 X-ray (AXI) 透視內部結構;[[Murata]] 在 2024 製程公開資料明示每顆需 30~50ms X-ray 全檢 (出貨良率管控目標 99.999%+)。

### 2.2 TW 玩家逐家評估

**6510 [[精測]]**:
- 主力 = MEMS [[探針卡]] (probe card),客戶為晶圓代工 + 封測 + IC 設計 ([[NVIDIA]]/[[AMD]]/美系手機)。
- MLCC **不使用探針卡** (被動元件以兩端電極直接電容/絕緣電阻量測,不是矩陣式 probe)。
- 結論: **排除** — 雖然 6510 是「測試設備」,但物理測試模式與 MLCC 不重疊。
- 來源: Pilot_Reports/Semiconductor Equipment & Materials/6510_精測.md。

**3030 [[德律]]**:
- 主力 = AOI + SPI (錫膏檢測) + **AXI X-ray** (BGA/隱藏焊點檢測) + ICT 電路板測試。
- **PCBA 端 AXI line 是 008004 焊接後檢測剛性需求** — 008004 因 SMT picker 對位偏差 + 焊接缺陷率高,PCBA 端 AXI 抽檢比例必須上升。
- 全球 PCBA AOI/AXI 市佔率名列前茅,客戶包括 [[Apple]] 供應鏈、[[Tesla]] 供應鏈、[[AI 伺服器]] ODM。
- 結論: **下游受惠 ★★** — 不是 MLCC 製程 line,而是 008004 焊接後 PCBA 檢測 (AI 伺服器 GPU board 一塊上千顆 008004)。
- 來源: Pilot_Reports/Scientific & Technical Instruments/3030_德律.md。

**3455 [[由田]]**:
- 主力 = AOI,核心在 IC 載板 ([[ABF]]/[[BT 載板]]) 外觀檢查,並切入先進封裝 ([[CoWoS]]/[[FOPLP]]) 檢測。
- MLCC AOI 技術 (sub-mm 級被動元件外觀檢查) 在 know-how 上可延伸,但目前**未公開揭露 MLCC line 客戶**。
- 結論: **間接候選 ★★** — AOI 平台可延伸,但目前營收主力在 IC 載板;觀察是否未來透過 [[國巨]]/[[華新科]] 切入。
- 來源: Pilot_Reports/Electronic Components/3455_由田.md。

---

## 3. 化學品端 — MLCC tape casting 細微化學品

### 3.1 關鍵化學品清單

| 化學品 | 用途 | 全球玩家 |
|---|---|---|
| 分散劑 (dispersant) | 鈦酸鋇/[[鎳]]粉漿料分散 | 日商 [[Toray]]/[[Mitsui]] 細微化學品 |
| 黏結劑 (binder) | PVB / 丙烯酸樹脂 sheet 成膜 | 美商 [[Eastman]] / 日商 [[Sekisui]] |
| 塑化劑 (plasticizer) | 鄰苯/酯類添加 | 日商 |
| 剝離劑 (release agent) | tape casting 載體 PET 膜剝離 | 日商 [[Lintec]] / [[Toray]] |
| 燒結助劑 (sintering aid) | 玻璃粉 / 稀土氧化物 | 日商 |
| 端電極漿料 (termination paste) | 含 [[銀]] / [[銅]] 顆粒 | 美商 [[DuPont]] / 日商 [[Noritake]] |

### 3.2 TW 化學廠候選評估

**4722 [[國精化]]** (Qualipoly):
- 主力轉型方向 = [[Low Dk/Df]] 樹脂 + PSMA 樹脂 → 供應 [[台光電]]/[[台燿]]/[[聯茂]] M6 級 [[CCL]] (AI 伺服器路徑)。
- 公司路線 = AI 高頻 CCL,**不是 MLCC tape casting 細微化學品**。
- 結論: **noise (for 008004)** — 國精化的 AI 高頻 CCL 路徑屬於 PCB 側受惠,已在 themes/MLCC.md 同步覆蓋。
- 來源: Pilot_Reports/Specialty Chemicals/4722_國精化.md。

**1711 [[永光]]** (Everlight Chemical):
- 主力 = 染料 (反應性/分散性) + 封裝膠材 + 光阻顯影液。
- 客戶涵蓋封測/載板 ([[日月光投控]]/[[景碩]]/[[欣興]]),不是被動元件廠。
- 結論: **排除** — 細微化學品 line 不重疊。
- 來源: Pilot_Reports/Specialty Chemicals/1711_永光.md。

**1304 [[台聚]]**:
- 主力 = HDPE/LDPE/LLDPE/EVA/CBC,通用石化 + 太陽能 EVA 封裝膜。
- 結論: **排除** — 通用塑料無細微化學品 line。
- 來源: Pilot_Reports/Specialty Chemicals/1304_台聚.md。

### 3.3 結論

MLCC tape casting 細微化學品市場長期由日商寡占 ([[Toray]]/[[Mitsui]]/[[Sekisui]]/[[Eastman]]),TW 化學廠目前**無切入路徑**。化學品端不具新候選。

---

## 4. 載板嵌入 (Embedded Passive in Substrate)

### 4.1 ECiP 技術背景

- **[[Embedded Capacitor in Package]]** (ECiP) = 將電容 (含 MLCC 或薄膜電容) 嵌入 [[ABF 載板]] 內層,直接放在 die 正下方。
- 目的: 縮短 power delivery 路徑、降低電感、提供更穩定的 power integrity;特別適合 [[NVIDIA]] H100/B200 / [[AMD]] MI300 等 700W+ GPU。
- **狀態 (2026 年):** [[Intel]] Sapphire Rapids 已導入 ECiP (Type 3 內層電容);[[NVIDIA]] Blackwell 平台亦有部分 SKU 採用;[[AMD]] MI300 內部 power delivery 仍以外部 MLCC 為主,但 MI400 (2026H2 上線) 預期切入嵌入。
- 來源 (待驗證): 業界白皮書 + 日商 [[Murata]] 2024 投資人簡報 ([[Murata]] 為 ECiP 嵌入式被動元件主要技術提供者)。

### 4.2 對 TW 載板三雄影響

**3037 [[欣興]]** (Unimicron):
- 全球 [[ABF 載板]] 市佔率 18%,僅次於日商 [[Ibiden]];[[NVIDIA]]/[[AMD]]/[[Intel]] 核心。
- **ECiP 技術已切入,於 2024 開始送樣 [[NVIDIA]] 與 [[Intel]]**;若 [[NVIDIA]] B200 + Rubin 採用,ECiP 將從低個位數 % 滲透率拉升。
- 對 008004 影響: 嵌入是「補強 PI 用」,**不取代外部 MLCC** — 載板可嵌入 10~50 顆 100nF~1μF,但 die 周邊仍需 1,000+ 顆 008004 + 0402 大電容供應瞬間電流。
- 結論: **★★★ 同步受惠** (已在 themes/MLCC.md 涵蓋,可加深 ECiP 路徑說明)。

**8046 [[南電]]** (Nan Ya PCB):
- 全球前三大 [[ABF 載板]],[[台塑]] 集團背景,客戶涵蓋 [[NVIDIA]]/[[AMD]]/[[Broadcom]]/[[Intel]]。
- ECiP 路徑同 [[欣興]],但因 [[台塑]] 集團可整合上游樹脂,**ECiP 內嵌電容材料 (高介電 polymer / 薄膜) 自給率有優勢**。
- 結論: **★★★ 同步受惠** (已在 themes/MLCC.md)。

**3189 [[景碩]]** (Kinsus):
- 第三大 [[ABF 載板]] + [[BT 載板]],客戶以 [[Qualcomm]] / [[MediaTek]] / [[NVIDIA]] 為主。
- ECiP 路徑相對保守,主力仍在傳統載板。
- 結論: **★★ 同步受惠** — 建議補入 themes/MLCC.md (目前 themes/MLCC.md 未明確列 3189)。

**4977 [[眾達-KY]]**:
- **prompt 列錯**: 4977 為光通訊模組 OEM (主要客戶 [[Broadcom]]),非 ABF 載板廠。
- 不適用 ECiP 路徑;排除。
- 來源: Pilot_Reports/Computer Hardware/4977_眾達-KY.md。

### 4.3 對 008004 distributor (3090/8043) 的長期威脅?

- **若 ECiP 完全取代外部 MLCC** → distributor BOM 比例下降,但這是 5~10 年以上長期事件。
- **2026~2028 區間: ECiP 仍是「補強」而非「取代」** — die 周邊每顆 GPU 仍需 1,000~2,000 顆 MLCC,8043 / 3090 短期受惠不變。
- **真正威脅** = 若 [[Murata]] / [[太陽誘電]] / [[國巨]] 等 MLCC 製造商直接將 008004 嵌入式封裝 (Type 4 polymer film capacitor) 出貨給載板廠,跳過傳統 distributor — 此路徑值得 2027 後追蹤。

---

## 5. SMT picker / molding 廠

### 5.1 008004 SMT picker 技術門檻

- 008004 體積僅約 1/4 於 01005 (0402 metric),picker 必須:
  - 真空吸嘴孔徑 < 100μm
  - 對位精度 ±10μm (3σ)
  - 取放速度 > 80,000 CPH (chips per hour)
- 全球玩家: 日商 [[Yamaha]] / [[Panasonic]] / [[Fuji Machine]] / [[Hitachi]] / [[ASM Pacific]] (HK 上市,母公司德商) 寡占,**TW 無自製 SMT 主機廠**。

### 5.2 TW 候選評估

**6187 [[萬潤]]**:
- 主力 = 半導體先進封裝後段設備 ([[CoWoS]] 點膠 / 散熱貼合 / 塗佈),**非 SMT picker**。
- 自家設備平台位於 OSAT 廠內,SMT 在 EMS 廠 (代工廠) 內,設備類別不同。
- 結論: **排除** — 雖名稱「自動化設備」但不是 SMT picker 系。

**2360 [[致茂]]**:
- 不切入 SMT picker — 致茂測試設備是「測試完整 board」而非「擺放電容」。
- 結論: **排除**。

**4919 [[新唐]]** (Nuvoton):
- 主力 = 微控制器 (MCU) + Power IC + Audio IC,**為 IC 設計公司**,根本不生產 SMT 設備。
- 結論: **排除** — prompt 列錯。
- 來源: Pilot_Reports/Semiconductors/4919_新唐.md。

### 5.3 結論

SMT picker 端 **TW 無新候選** — 此環節仍由日商寡占,沒有可挖掘的 TW 玩家。

但有一個間接路徑值得追蹤: **SMT picker 吸嘴 (nozzle)** 為消耗品,孔徑 < 100μm 的精密陶瓷/金屬加工屬精密機械,TW 可能有 OEM 切入。本 unit 範圍內未涵蓋,留作後續挖掘。

---

## 受惠強度排序 (新候選)

| 排序 | Ticker | 公司 | 路徑 | 強度 | 為何重要 |
|---|---|---|---|---|---|
| 1 | 3030 | [[德律]] | AXI X-ray + AOI for PCBA | ★★ | AI 伺服器 GPU board PCBA 端剛需,008004 焊接後檢測線爆量 |
| 2 | 3455 | [[由田]] | AOI 平台延伸 | ★★ | IC 載板 AOI 已成,可延伸 MLCC line (觀察) |
| 3 | 6187 | [[萬潤]] | 點膠/塗佈/AOI 平台延伸 | ★★ | 半導體封裝設備平台已驗證,理論可切入 MLCC 端電極塗佈 |
| 4 | 3189 | [[景碩]] | [[ABF 載板]] ECiP 同步受惠 | ★★ | themes/MLCC.md 未列,建議補入 |

**排除/noise**: 2360 / 6510 / 3551 / 3413 / 1560 / 4722 / 1711 / 1304 / 4919 / 4977 (10 家)

---

## 對既有 themes/MLCC.md 的補充建議

### 建議新增

1. **3030 [[德律]]** — 新增為「下游受惠」分類:
   - 理由: AI 伺服器 GPU board 一塊 PCBA 含 1,000~2,000 顆 008004,焊接後 AXI X-ray 抽檢比例必須上升;德律為全球 PCBA AOI/AXI 龍頭。
   - 受惠機制: 不是 MLCC 製造,而是 MLCC 焊接後檢測。

2. **3189 [[景碩]]** — 新增為 [[ABF 載板]] 同步受惠 (與 3037/8046 並列):
   - 理由: ECiP 嵌入式被動元件路徑同步受惠,目前 themes/MLCC.md 未列 3189。

### 建議觀察 (暫不加入主清單)

3. **3455 [[由田]]** / **6187 [[萬潤]]** — 列為「設備平台可延伸觀察名單」:
   - 兩家 AOI / 塗佈 / 點膠平台理論上可切入 MLCC,但需驗證實際 line 進度。
   - 觸發加入條件: 公開揭露 [[Murata]] / [[太陽誘電]] / [[國巨]] / [[華新科]] 為客戶。

### 建議排除 (避免 noise 污染)

- **2360 [[致茂]]**: 名稱有「AOI」但物理 line 不重疊。
- **4722 [[國精化]]**: 已透過 CCL 路徑 (台光電/台燿/聯茂) 隱含覆蓋,不需獨立列入 MLCC 主題。

---

## Sources

- Pilot_Reports/Scientific & Technical Instruments/2360_致茂.md (本 repo)
- Pilot_Reports/Scientific & Technical Instruments/3030_德律.md (本 repo)
- Pilot_Reports/Electronic Components/3455_由田.md (本 repo)
- Pilot_Reports/Specialty Industrial Machinery/6187_萬潤.md (本 repo)
- Pilot_Reports/Tools & Accessories/1560_中砂.md (本 repo)
- Pilot_Reports/Specialty Chemicals/4722_國精化.md (本 repo)
- Pilot_Reports/Specialty Chemicals/1711_永光.md (本 repo)
- Pilot_Reports/Specialty Chemicals/1304_台聚.md (本 repo)
- Pilot_Reports/Semiconductor Equipment & Materials/6510_精測.md (本 repo)
- Pilot_Reports/Semiconductor Equipment & Materials/3551_世禾.md (本 repo)
- Pilot_Reports/Semiconductor Equipment & Materials/3413_京鼎.md (本 repo)
- Pilot_Reports/Semiconductor Equipment & Materials/3189_景碩.md (本 repo)
- Pilot_Reports/Electronic Components/3037_欣興.md (本 repo)
- Pilot_Reports/Electronic Components/8046_南電.md (本 repo)
- Pilot_Reports/Computer Hardware/4977_眾達-KY.md (本 repo) — 確認非 ABF 載板廠
- Pilot_Reports/Semiconductors/4919_新唐.md (本 repo) — 確認為 IC 設計
- vault/research/008004/ prior batch units (1–8)
- themes/MLCC.md (本 repo)

> **驗證限制**: 本 unit 主要依據 Pilot_Reports 既有資料與公開技術知識推論,未透過 WebSearch 即時驗證 [[Murata]] / [[Intel]] ECiP 採用率與 SMT picker BOM 細節。下個迭代若需精確化,應補:
> - [[Murata]] 2024/2025 投資人簡報中 ECiP 滲透率數據
> - [[NVIDIA]] B200 / Rubin teardown 報告中 ABF 載板 ECiP layer 數
> - [[國巨]] / [[華新科]] 設備 BOM 揭露 (是否導入 [[由田]] / [[萬潤]] AOI)
