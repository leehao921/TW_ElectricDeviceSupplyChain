# 功率元件 / PMIC 產業鏈 × 台灣供應鏈 Deep-Dive

**日期:** 2026-06-18
**Spec:** [docs/superpowers/specs/2026-06-18-power-semi-pmic-design.md](../superpowers/specs/2026-06-18-power-semi-pmic-design.md)
**機械式索引:** [themes/功率元件.md](../../themes/功率元件.md)
**Catalyst 起源:** [Sinotrade 豐雲學堂 — 功率元件漲價循環啟動](https://www.sinotrade.com.tw/richclub/hotstock/功率元件漲價循環啟動-台廠德微領軍掀漲潮-還有哪些代表個股----股市話題-6a17a7d966da6118fd4577b0)

---

## §0 TL;DR — 三大 driver 鳥瞰

2026 年功率元件 / PMIC 板塊正面臨**三股力量同時匯流**：

1. **漲價循環啟動**：[[Infineon]] 自 2026/4/1 帶頭漲 5–15%，[[TI]] 7/1 跟進涵蓋 PMIC + MOSFET，台廠 [[德微]] 漲 5–10%、[[茂達]] 漲 0–15%、[[強茂]] 啟動「55 計畫」目標 2030 [[MOSFET]] 年營收 5 億美元。
2. **[[Nexperia]] (安世半導體) 出口管制轉單**：荷蘭政府 2025/10/13 接管 [[Wingtech]] 中資控股的 [[Nexperia]]，中國反制禁出口（佔歐洲產能 ~70%），引發車用晶片缺貨；2026/3 [[Digitimes]] 證實訂單分流至**台灣 12 吋產線**。[[Nexperia]] 主力產品 ([[MOSFET]] / Schottky / Logic / ESD) **與 TW [[強茂]] / [[德微]] / [[台半]] / [[富鼎]] 完全重疊**。
3. **AI 伺服器電源架構升級**：[[Open Compute Project ORv3]] 48V → ORv4 ±400VDC (800kW) → [[NVIDIA]] 800V HVDC（2026Q4–2027Q1 Phase 1–2）。Rack 內仍 50V → sub-1V 多級降壓，**單機架 PMIC + MOSFET 數量倍增**。

**核心 thesis**：TW 在這三層的角色分明 ——
- **Discrete IDM**（[[強茂]] / [[台半]] / [[富鼎]] / [[德微]]）= 接 [[Nexperia]] 轉單 + 漲價直接受惠
- **PMIC 整合 IC 設計**（[[矽力-KY]] / [[致新]] / [[茂達]]）= AI 伺服器 50V → sub-1V 多級降壓 ASP 倍增
- **化合物半導體 foundry / epitaxy**（[[漢磊]] / [[嘉晶]] / [[世界先進]]）= 800V HVDC [[GaN]] / [[SiC]] 結構性需求

| 元件類別 | TW 角色 | 結論 |
|---|---|---|
| Discrete MOSFET / Diode / [[IGBT]] | 全球第 6 ([[強茂]]) + 利基 IDM 多家 | 漲價 + [[Nexperia]] 轉單雙加持 |
| [[PMIC]] 整合 | [[矽力-KY]] 龍頭，市值 1,891 億 | AI 伺服器多級降壓帶量 |
| [[GaN]] / [[SiC]] foundry | [[漢磊]] 6 吋 + [[嘉晶]] epi | 結構性需求，但 [[漢磊]] 仍虧損中 |
| 8 吋 BCD foundry | [[世界先進]] 龍頭 | 穩定 cash cow，[[NXP]] VSMC 12 吋 2027 量產 |
| 高速 RF ADC/DAC | 結構性缺口 | 與 LEO 主題共通 |

---

## §1 Power Semi 技術 fundamentals

### §1.1 Discrete vs Integrated PMIC vs Power Module

功率半導體可分為三大類，各自服務電源轉換鏈不同層級：

- **Discrete power semi**：單一功率元件，如 [[MOSFET]]、[[IGBT]]、整流二極體、Schottky 二極體。負責高電流 / 高電壓開關與整流。
- **Integrated PMIC**（電源管理 IC）：將控制器 + driver + 部分 power FET 整合於單晶片。常見子類：DC-DC 轉換器、[[LDO]] 穩壓器、battery PMIC、[[VRM]] 控制器。
- **Power Module**：將多個功率元件 + 控制 + 散熱結構封裝於單一模組，常見於 [[電動車]] [[IGBT]] 模組、AI 伺服器 [[VRM]] 多相 buck 模組。

三類之間並非替代，而是**配套**：AI 伺服器一台同時需要 discrete [[MOSFET]]（高壓段）+ PMIC（中壓段）+ power module（POL 段）。

### §1.2 五大 building blocks

| Block | 功能 | 國際 spec leader | 主要 substrate |
|---|---|---|---|
| **[[MOSFET]]** | 中低壓開關（12V–400V） | [[Infineon]]、[[onsemi]]、[[STM]]、[[Vishay]]、[[Nexperia]] | 矽 / [[GaN]] |
| **[[IGBT]]** | 高壓高功率開關（650V–6500V） | [[Infineon]] (含 [[Hitachi Energy]])、[[Mitsubishi]]、[[Fuji Electric]] | 矽 |
| **Schottky / 整流 Diode** | 整流、電源續流 | [[Vishay]]、[[onsemi]]、[[Nexperia]] | 矽 / [[SiC]] |
| **[[GaN]] HEMT** | 高頻高效率開關 | [[Navitas]]、[[Power Integrations]]、[[Infineon]]、[[EPC]] | [[GaN-on-Si]] / [[GaN-on-SiC]] |
| **[[SiC]] MOSFET** | 高壓高效率開關（電動車、HVDC） | [[Wolfspeed]]、[[STM]]、[[Infineon]]、[[onsemi]] | [[SiC]] |

### §1.3 PMIC 分類

- **DC-DC converter**：buck（降壓）/ boost（升壓）/ buck-boost。AI 伺服器 [[VRM]] 多相 buck 為主力。
- **[[LDO]]**：低噪低壓差線性穩壓，適合敏感類比 / RF rail。
- **Battery PMIC**：[[電動車]] BMS、伺服器 [[BBU]]、攜帶電子充放電管理。
- **[[VRM]] controller**：CPU/GPU 多相 buck 控制器，配 Dr. [[MOSFET]] / power stage。國際領導 [[MPS]] (Monolithic Power Systems)、[[Renesas]] (Intersil)、[[Infineon]]。

### §1.4 AI 伺服器電源架構演進

```
[電網]
  ↓ AC/DC PSU （[[台達電]]、[[光寶科]]）
[12V busbar (ORv2)] → [48V busbar (ORv3 主流)] → [±400VDC (ORv4 HPR V4)] → [800V HVDC (NVIDIA 2026Q4-2027Q1)]
  ↓ DC-DC sidecar （discrete [[MOSFET]] + [[GaN]]）
[50V rack-level busbar (NVIDIA 800V 維持 50V 進架內)]
  ↓ POL (point of load) 多相 buck （PMIC + Dr. [[MOSFET]]）
[sub-1V GPU/CPU core rail]
```

**關鍵觀察**：即便導入 800V HVDC，**rack 內維持 50V → sub-1V 多級降壓**——每一級轉換都需要 discrete + PMIC 配合，**單機架元件數量隨 GPU 功耗倍增**而擴張。NVIDIA 估算 1 MW 機架 54V 系統需 200+ kg 銅；800V HVDC 銅線**減 45%**，但補上的是更高密度 [[GaN]] / [[SiC]] 元件。

---

## §2 三大 Catalyst 深入分析

### §2.1 漲價循環啟動

**時間軸**：
- **2026/4/1**：[[Infineon]] 全球功率元件漲 5–15%（第一槍）
- **2026/5/13**：TW 媒體點名 [[強茂]]、[[德微]] 開始醞釀
- **2026/5/28**：工商時報 — 功率元件掀漲價潮，台鏈受惠
- **2026/6**：[[德微]] 確定漲 5–10%、[[強茂]] / [[台半]] 跟進
- **2026/7/1**：[[TI]] 第二波，涵蓋 PMIC + [[MOSFET]]；[[茂達]] 同步漲 0–15%

**驅動因素**：
1. **晶片通膨**：折舊（先進製程設備）、原物料（[[銅]]、[[銀]]、樹脂）、能源成本累積推升。
2. **庫存去化終結**：2023–2024 庫存週期結束，2026 進入補貨期。
3. **AI 需求倍增**：資料中心功耗從 100 kW/rack → 1 MW/rack，[[MOSFET]] 與 PMIC 單機架用量倍增。

**TW 廠回應**：[[強茂]] 啟動「55 計畫」目標 2030 年 [[MOSFET]] 年營收 5 億美元（vs 2025 整體營收約 4.3 億美元，意味 [[MOSFET]] 單品翻倍以上）。[[德微]] AI 伺服器 PSU 已切入美系大廠，AI 營收占比達 25%。

### §2.2 [[Nexperia]] 出口管制轉單

**事件時間軸**：
- **2025/10/13**：荷蘭政府引用 Trade Act 接管 [[Wingtech]] 中資控股的 [[Nexperia]]，理由「防止技術外流中國」（[[Wingtech]] 受中國 SASAC 持股約 30%）。
- **2025/10–11**：中國反制，禁止 [[Nexperia]] 出口**中國境內封裝的產品**（佔歐洲產能 ~70%），引發歐美車用晶片緊缺。
- **2025/11/19**：荷蘭政府宣布暫停治理控制，但供應仍「drip-feed」限制。
- **2026/3/17**：[[Digitimes]] 報導 [[Nexperia]] 中國分裂送單到**台灣 12 吋產線**。
- **2026/5/27**：[[Polar Semiconductor]] + [[Nexperia]] 美國代工合作（[[MOSFET]] 美國本土化）。
- **2026/5**：[[Wingtech]] 提起 $1.2 億美元訴訟。

**轉單規模**：[[Nexperia]] 2022 年產量 1,000 億顆、營收 21 億美元、員工 14,000 人，主要產品為 [[MOSFET]] / Schottky / Logic / ESD。即便 5–10% 訂單分流，對台廠是相當可觀的增量。

**TW 廠受益排序**（推測）：
1. **[[強茂]] (2481)**：產品 overlap 最高（[[MOSFET]]、[[整流器]]、TVS），國際 IDM 規模，能承接歐洲 Tier 1 替代訂單。
2. **[[台半]] (5425)**：已是 [[Bosch]]、[[Continental]]、[[Valeo]] Tier 1，[[Nexperia]] 過去同為這些客戶供應商。
3. **[[德微]] (3675)**：二極體與 Schottky 強項，[[Nexperia]] Schottky 線重疊高。
4. **[[富鼎]] (8261)**：[[MOSFET]] fabless 設計，[[國巨]] / [[鴻海]] 集團通路加持。

**風險**：[[Polar Semiconductor]] 美國代工合作意味 [[Nexperia]] 試圖**繞過中國產能**而非放棄市場——轉單窗口可能僅 6–18 個月，需觀察 [[Nexperia]] 美國產能 ramp-up 速度。

### §2.3 AI 伺服器電源架構升級

**架構演進**：

| 世代 | 規格 | 機架功率 | 主要元件變化 |
|---|---|---|---|
| ORv2 | 12V busbar | <30 kW | 傳統 silicon [[MOSFET]] |
| ORv3 | 48V busbar | 30–190 kW | 多相 buck、48V [[GaN]] 開始導入 |
| ORv3 HPR | 50V sidecar | 300 kW | [[GaN]] 滲透提升 |
| ORv4 HPR V4 | ±400VDC | 800 kW | [[SiC]] for high-voltage stage |
| [[NVIDIA]] 800V HVDC | 800VDC | 1 MW+ | [[SiC]] MOSFET + [[GaN]] DCDC 配套 |

**關鍵設計選擇**：即便 [[NVIDIA]] 800V HVDC 在機架入口將 AC → 800VDC，**機架內仍維持 50V busbar**（300 kW 內），再透過 PMIC + Dr. [[MOSFET]] 多級降壓到 sub-1V GPU rail。意思是：
- **HVDC 入口段**：[[SiC]] [[MOSFET]] 用於 AC/DC + DC/DC 降壓（[[Wolfspeed]]、[[Infineon]] 主導）
- **48V/50V → 12V**：[[GaN]] HEMT（[[Navitas]] + [[NVIDIA]] 已公告合作）
- **12V → sub-1V**：高頻多相 buck PMIC + Dr. [[MOSFET]]（[[MPS]]、[[矽力-KY]]、[[茂達]]、[[致新]]、[[大中]]）

**TW 受惠路徑**：
- **[[大中]] (6435)**：Dr. [[MOSFET]] + 風扇驅動 IC 直接打入 AI 伺服器，2026 周漲 27% 創三年半新高。
- **[[矽力-KY]] (6415)**：高密度 PMIC，AI 伺服器機櫃電源切入。
- **[[強茂]] (2481)**：伺服器 PSU 模組元件，[[鴻海]] 最佳供應商。
- **[[德微]] (3675)**：AI PSU 二極體與整流橋。
- **[[漢磊]] (3707) + [[嘉晶]] (3016)**：[[SiC]] / [[GaN]] foundry，HVDC 上游材料。

---

## §3 產品分類 × 國際 vs TW 矩陣【核心章節】

### §3.1 [[MOSFET]]

**國際 spec leadership**：
- **[[Infineon]]**：OptiMOS 系列，全球市佔 ~25% 為龍頭。
- **[[onsemi]]**：T9 SuperJunction 高壓 + 中低壓 trench。
- **[[STM]]**：MDmesh K6/M6 高壓 SuperJunction。
- **[[Vishay]]**、**[[Nexperia]]**：中低壓利基。

**TW 玩家**：
- **[[強茂]] (2481)**：IDM 設計 + 6 吋晶圓 + 封測，「55 計畫」目標 2030 [[MOSFET]] $500M。
- **[[台半]] (5425)**：IDM + 部分 fabless（高階 [[MOSFET]] 與 [[聯電]] 合作）；車用 Tier 1 主供。
- **[[富鼎]] (8261)**：台灣首家 6 吋 DMOS 整合 IC 設計，產品涵蓋 600V–1200V [[SiC]] [[MOSFET]]。
- **[[大中]] (6435)**：中低壓 [[MOSFET]] + HV IC + Dr. [[MOSFET]]，AI PC 與 AI 伺服器專供。
- **[[杰力]] (5299)**：中低壓 [[MOSFET]]，[[華碩]] 集團、PC/NB 主板電源。

### §3.2 [[IGBT]]

**國際 spec leadership**：[[Infineon]] 併 [[Hitachi Energy]] 後市佔超 30%；[[Mitsubishi]]、[[Fuji Electric]] 為日系強權；[[onsemi]]、[[STM]] 補位。

**TW 玩家**：本土 [[IGBT]] 純玩家少，因 [[IGBT]] 模組製造門檻高（散熱、可靠性）。**[[強茂]] (2481)** 切入消費 / 工控 [[IGBT]] 元件；**[[富鼎]] (8261)** 設計 [[IGBT]] 模組。**[[電動車]] 高功率 [[IGBT]] 模組仍由國際 IDM 把持**——這是 TW 的結構性缺口之一。

### §3.3 Schottky / 整流 Diode

**國際 spec leadership**：[[Vishay]]、[[onsemi]]、[[Nexperia]]、[[Diodes Inc.]] 為四大主流。

**TW 玩家**：
- **[[強茂]] (2481)**：全球第六大整流器元件廠，TW 龍頭。
- **[[德微]] (3675)**：二極體專家，[[Diodes Inc.]] 達爾集團子公司——母公司渠道與本土 IDM 雙向受益。
- **[[台半]] (5425)**：整流器 IDM 老將，車用 Tier 1。
- **[[杰力]] (5299)**：中低壓二極體配合 [[MOSFET]]。

### §3.4 [[GaN]] HEMT

**國際 spec leadership**：[[Navitas Semiconductor]] 為 AI 伺服器 [[GaN]] DCDC 領頭羊（[[NVIDIA]] 800V HVDC 已選用），[[Power Integrations]]、[[Infineon]] (CoolGaN)、[[EPC]] 並列。

**TW 玩家**：
- **[[漢磊]] (3707)**：6 吋 [[GaN]] foundry，為 [[Navitas]] 與國際 fabless 代工。**核心戰略 asset**——若 AI [[GaN]] 滲透加速，[[漢磊]] 從 2025 -3.30% GM 虧損反轉。
- **[[嘉晶]] (3016)**：台灣唯一量產 6 吋 [[GaN]] epitaxy，[[漢磊投控]] 集團整合。
- **[[台積電]]**：8 吋 [[GaN-on-Si]] 為 [[Navitas]] 代工，與 [[漢磊]] 形成 8 吋 vs 6 吋分工。

### §3.5 [[SiC]] MOSFET

**國際 spec leadership**：[[Wolfspeed]] (純玩家)、[[STM]] (車用領先)、[[Infineon]] CoolSiC、[[onsemi]] EliteSiC。

**TW 玩家**：
- **[[漢磊]] (3707)**：6 吋 [[SiC]] foundry，與 [[嘉晶]] (3016) epitaxy 一站式。
- **[[嘉晶]] (3016)**：台灣唯一量產 4 吋 / 6 吋 [[SiC]] epitaxy。
- **[[強茂]] (2481)**：[[SiC]] discrete 元件已導入 [[電動車]] / [[綠能]]。
- **[[富鼎]] (8261)**：600V–1200V [[SiC]] [[MOSFET]] 設計完成。
- **[[台半]] (5425)**：車用 Tier 1 通路推進 [[SiC]]。
- **TW 缺口**：8 吋 [[SiC]] 大尺寸晶圓量產仍落後 [[Wolfspeed]] / [[STM]] 至少 1–2 年。

### §3.6 PMIC 整合（DC-DC / [[LDO]] / Battery）

**國際 spec leadership**：[[TI]] (全球第一)、[[ADI]] (含 Maxim)、[[Renesas]] (含 Intersil)、[[MPS]] (Monolithic Power Systems，AI 伺服器 [[VRM]] 黑馬)、[[Infineon]] (含 Cypress)。

**TW 玩家**：
- **[[矽力-KY]] (6415)**：開曼總部，**TW PMIC 龍頭**，市值 1,891 億 NT$，2025 Revenue 188 億，GM 51.62%（接近國際大廠）。產品定位「小封裝、高壓、大電流」，受惠中國國產替代政策；AI 伺服器機櫃電源、[[電動車]] BMS 為成長主軸。
- **[[致新]] (8081)**：台灣前三大類比 IC，NB / 伺服器 PMIC 強項，[[Lenovo]] / [[Dell]] / [[HP]] 主供。
- **[[茂達]] (6138)**：DC-DC / [[LDO]] / [[MOSFET]] driver / LED driver；PMIC 占 55%、散熱 IC 25%、driver 20%；2026/7 漲 0–15%；Q1 EPS YoY +42%。
- **[[天鈺]] (4961)**：面板 PMIC + display driver，[[鴻海]] 系；2026/5 法人吸貨 +3,108 張（PMIC 板塊吸貨最強），TTM P/E 20.1（板塊最便宜）。

### §3.7 AI Server [[VRM]] Module

**國際 spec leadership**：[[MPS]] 為高密度多相 buck 領頭羊；[[Infineon]] (XDPP1100 + Dr. [[MOSFET]])、[[onsemi]]、[[Vicor]] (48V → 12V 高密度模組)。

**TW 玩家**：
- **[[大中]] (6435)**：Dr. [[MOSFET]] + 風扇驅動 IC + BBU 電池管理；2026 周漲 27%；茂達集團整合。
- **[[強茂]] (2481)**：[[MOSFET]] + 整流 element 供伺服器 PSU。
- **[[矽力-KY]] (6415)**：多相 buck controller。
- **[[聯華電子]]、[[世界先進]] (5347)**：foundry 提供 [[BCD]] 製程。

---

## §4 TW 供應鏈分層

### §4.1 Wafer Foundry

- **[[世界先進]] (5347)**：8 吋特殊製程龍頭，[[BCD]] / [[SOI]] / 高壓 / [[MEMS]]，2025 Revenue 486 億，[[台積電]] 持股 28%。與 [[NXP]] 合資 [[VSMC]] 新加坡 12 吋 2027 投產——**這是 TW 邁向 12 吋 power BCD 的關鍵突破**。
- **[[漢磊]] (3707)**：6 吋 [[SiC]] / [[GaN]] 化合物半導體 foundry，[[Infineon]]、[[onsemi]]、[[Navitas]] 為客戶；2025 GM -3.30%、淨損 7.57 億——**正在燒錢求量產規模**。
- **[[台積電]]**：[[GaN-on-Si]] 8 吋為 [[Navitas]] 代工，但不是 power semi 主業。

### §4.2 Epitaxy

- **[[嘉晶]] (3016)**：台灣唯一量產 4 吋 / 6 吋 [[SiC]] epitaxy + 6 吋 [[GaN]] epitaxy，[[漢磊投控]] 旗下。2025 GM 7.88% 偏低，反映 [[Wolfspeed]] 等國際大廠規模成本壓力。

### §4.3 IDM (Design + Manufacturing)

- **[[強茂]] (2481)**、**[[台半]] (5425)**、**[[德微]] (3675)** 為主要 IDM，皆有自己的 6 吋 / 8 吋晶圓廠 + 封測線。**這是台廠最能直接吃 [[Nexperia]] 轉單的層**。

### §4.4 Fabless IC 設計

- **Discrete**：**[[富鼎]] (8261)**、**[[大中]] (6435)**、**[[杰力]] (5299)**。
- **PMIC**：**[[矽力-KY]] (6415)**、**[[致新]] (8081)**、**[[茂達]] (6138)**、**[[天鈺]] (4961)**。

### §4.5 封測

- **[[菱生]] (2369)** 為功率元件封測利基；[[日月光投控]] / [[超豐]] 為大眾封測代表。封測層 TW 強項明確，但本報告不深入。

---

## §5 13 家個股 deep-dive

### §5.1 [[強茂]] (2481) — TW Discrete IDM 龍頭

- **角色**：全球第六大[[整流器]]廠，IDM 涵蓋 [[MOSFET]] / Schottky / [[SiC]] / [[IGBT]] / TVS。
- **Design-win**：[[鴻海]] 最佳供應商獎（伺服器 PSU）、車用 Tier 1（占營收 ~30%，目標 40%）、AI 伺服器電源模組。
- **營收**：2025 全年 130.94 億 NT$（YoY +4.4%）、GM 31.26%（連 3 年提升）、Net Margin 9.10%。Q4'25 GM 32.67% 為近年高。
- **2026-2027 看點 + 風險**：「55 計畫」2030 [[MOSFET]] 年營收 $500M（vs 2025 整體 ~4.3 億美元）→ 隱含 [[MOSFET]] 單品翻倍。受惠：(1) [[Nexperia]] 轉單（重疊最高）、(2) 國際漲價跟進、(3) AI 伺服器 PSU 倍增。風險：[[消費性電子]] 占比仍高（~30%），週期回落直接衝擊。

### §5.2 [[德微]] (3675) — Diodes 集團二極體專家

- **角色**：[[Diodes Inc.]] 達爾集團子公司，二極體 / Schottky / 高階整流器專業 IDM。
- **Design-win**：美系 AI 伺服器 PSU（AI 占比達 ~25%）、[[台達電]] / [[光寶科]] 等 PSU 廠、車用 Tier 1（透過母公司）。
- **營收**：2025 全年 26.36 億 NT$（YoY -9.9%、受庫存週期影響）、GM 34.70%（已止跌）、Q4'25 GM 36.51%。**已宣布漲價 5–10%**。
- **2026-2027 看點 + 風險**：(+) AI PSU 訂單放量、漲價 + 轉單雙重利多、母公司 [[Diodes Inc.]] 通路加持；(−) 2025 Q2 虧損 47.73M 顯示成本端尚未完全消化；殖利率僅 1.19%、TTM P/E 118.79 估值偏貴。

### §5.3 [[台半]] (5425) — 車用 Tier 1 IDM 老將

- **角色**：1979 年成立，IDM 整流器 / [[MOSFET]] / TVS / PMIC，子公司 [[鼎翰]] (3611) 條碼機獲利穩定。
- **Design-win**：[[Bosch]]、[[Continental]]、[[Valeo]]、[[BYD]]、[[CATL]] 車用 Tier 1。
- **營收**：2025 全年 179.54 億 NT$（YoY +21%、跑贏同業）、GM 29.46%、OPM 8.29%。Q2'25 Net Margin 僅 0.87%——子公司或一次性費用拖累。
- **2026-2027 看點 + 風險**：(+) 車用 Tier 1 客戶基礎扎實，[[Nexperia]] 轉單最直接受惠；(+) 高階 [[MOSFET]] 與 [[聯電]] 合作擴產；(−) Net Margin 偏低（2.84%），子公司營運是否穩定為關鍵變數。

### §5.4 [[富鼎]] (8261, APEC) — 6 吋 DMOS fabless 隱形冠軍

- **角色**：台灣首家成功整合 6 吋 DMOS 製程的 IC 設計公司，產品全系列 [[MOSFET]] + [[IGBT]] + 完成 600V-1200V [[SiC]] [[MOSFET]] 開發。[[國巨]] / [[鴻海]] 集團入股。
- **Design-win**：交換式電源供應器、PC、伺服器散熱風扇、馬達驅動。
- **營收**：2025 全年 31.04 億 NT$（YoY +6.4%）、**GM 37.39% 為 5 家文章公司最高**、**OPM 25.25% 也最高**、Net Margin 21.87%。Q1'26 GM 38.07%、OPM 25.66% 續強。
- **2026-2027 看點 + 風險**：(+) [[國巨]] / [[鴻海]] 集團通路加持轉單最快；(+) [[SiC]] 設計上線後跟進 AI 伺服器 800V HVDC；(+) fabless 模式毛利彈性最大；(−) 設計公司無自有產能，[[Nexperia]] 轉單若擴大，foundry 產能緊張可能限制 ramp。

### §5.5 [[大中]] (6435, Sinopower) — AI 伺服器 Dr.MOS 黑馬

- **角色**：[[茂達電子]] 集團子公司，產品中低壓 [[MOSFET]] + HV IC + [[IGBT]] 模組。
- **Design-win**：[[台達電]]、[[鴻海]]、[[廣達]]（AI 伺服器散熱 + [[BBU]] 電池備援）。AI PC + AI 伺服器 Dr. [[MOSFET]] + 風扇驅動 IC 強勁需求。
- **營收**：2025 全年 34.01 億 NT$（YoY +25.2%）、GM 22.45%、OPM 10.98%、Net Margin 10.42%。Q4'25 GM 衝至 27.37%。**2026/5 週漲 27% 創 3.5 年新高**。
- **2026-2027 看點 + 風險**：(+) AI 伺服器多相 buck 配套 Dr. [[MOSFET]] 用量倍增；(+) BBU 電池管理在 NVIDIA 規範下加大；(−) 與 [[茂達]] 集團整合度高，獨立性弱；(−) 漲 27% 後估值已不便宜。

### §5.6 [[漢磊]] (3707) — 6 吋 SiC / GaN 化合物半導體 foundry

- **角色**：6 吋 [[SiC]] / [[GaN]] 純玩家 foundry，全球第一家 Sub-micron Bipolar/BiCMOS 代工廠轉型而來。
- **Design-win**：[[Infineon]]、[[onsemi]]（部分委外）、[[Rohm]]、[[Navitas]]、[[GaN Systems]]。
- **營收**：2025 全年 57.66 億 NT$（YoY -0.9%）、**GM -3.30% 虧損中**、淨損 7.57 億。Q4'25 GM 仍 -1.01% 但已大幅收斂（Q1'25 -5.67%）。CAPEX 2024 / 2025 連續 14 億+ → 6 吋產能擴張。
- **2026-2027 看點 + 風險**：(+) [[Navitas]] × [[NVIDIA]] 800V HVDC GaN 訂單 2027 量產，[[漢磊]] 為 supply candidate；(+) [[電動車]] [[SiC]] [[MOSFET]] 滲透率提升；(−) 連兩年虧損，[[Wolfspeed]] 等 8 吋國際大廠成本優勢威脅；(−) 8 吋轉型時程未明。

### §5.7 [[世界先進]] (5347) — 8 吋特殊製程 foundry 龍頭

- **角色**：8 吋特殊製程龍頭（[[BCD]] / [[SOI]] / 高壓 / 分離式 / 類比 / [[MEMS]]），[[台積電]] 持股 28%。
- **Design-win**：全球 PMIC + 車用 IC 設計大廠（[[ADI]]、[[onsemi]]、[[NXP]]、[[Infineon]] 等部分產品委外）。
- **營收**：2025 全年 485.91 億 NT$（YoY +10.3%）、GM 28.10%、OPM 16.00%、Net Margin 16.27%、市值 3,186 億。為 13 家中**規模最大、最賺錢**。
- **2026-2027 看點 + 風險**：(+) [[NXP]] 合資 [[VSMC]] 新加坡 12 吋 2027 投產——TW 邁向 12 吋 power BCD；(+) AI 伺服器 PMIC 需求帶動 8 吋產能滿載；(+) 漲價傳導至 foundry 端；(−) 12 吋 CAPEX 2025 已 640 億，自由現金流壓力。

### §5.8 [[矽力-KY]] (6415) — TW PMIC 龍頭，AI 伺服器中性贏家

- **角色**：總部開曼，**TW PMIC 絕對龍頭**，市值 1,891 億 NT$。定位「小封裝、高壓、大電流」高效能電源解決方案。
- **Design-win**：[[Samsung]]、[[Sony]]、華為、車廠 Tier 1、美系雲端巨擘（如 [[AWS]]）。**中國國產替代受惠最大標的**。
- **營收**：2025 全年 188.12 億 NT$（YoY +1.9%）、GM 51.62%（全 13 家最高、接近國際大廠）、OPM 11.48%、Net Margin 13.17%。Q4'25 Revenue 53.92 億、Net Margin 15.01% 為近年高。
- **2026-2027 看點 + 風險**：(+) AI 伺服器機櫃電源（[[AWS]] 主供）；(+) [[電動車]] BMS；(+) 中國半導體國產替代延續；(−) TTM P/E 76.88、殖利率 0.45% 估值極高；(−) 高 R&D 強度（27% of revenue）壓抑 OPM。

### §5.9 [[致新]] (8081, GMT) — NB / Server PMIC 老牌

- **角色**：台灣前三大類比 IC 設計，NB / 伺服器 / 工作站 PMIC 為主。
- **Design-win**：[[Lenovo]]、[[Dell]]、[[HP]] NB 主供。
- **營收**：2025 全年 86.66 億 NT$（YoY +5.0%）、GM 38.98%、OPM 19.36%、Net Margin 17.57%。**TTM P/E 16.70 與 PMIC 板塊相比偏便宜**，殖利率 5.45%。
- **2026-2027 看點 + 風險**：(+) NB 換機潮 + AI PC PMIC 升級；(+) 估值與股息題材吸引法人；(−) Q1'26 EPS 8.02 但 YoY +16% 低於 [[茂達]] +42%——成長動能稍弱；(−) 客戶集中於消費 NB，AI 伺服器切入較慢。

### §5.10 [[茂達]] (6138, Anpec) — PMIC + 散熱 IC 動能股

- **角色**：DC-DC / [[LDO]] / [[MOSFET]] driver / LED driver / 散熱風扇 IC。PMIC 占 55%、散熱 IC 25%、driver 20%。
- **Design-win**：筆電 / 伺服器 PMIC + AI PC 雙風扇設計帶動散熱 IC + PMIC 雙產品。
- **營收**：Q1'26 EPS 3.68 元（YoY +42%、QoQ -2%）、Q1 GM 38.4% 續攀。**2026 YTD 漲 49.9%**、年化波動度 56%。**2026/7 漲價 0–15%**。
- **2026-2027 看點 + 風險**：(+) 7/1 漲價直接傳導；(+) AI PC + AI 伺服器散熱 + PMIC 雙產品線；(+) 法人持續吸貨（YTD +376 張、6 月 +321 張）；(−) [[大中]] (6435) 為集團子公司，整合度高；(−) 伺服器占比仍低個位數，AI 故事主要靠 AI PC。

### §5.11 [[天鈺]] (4961, Fitipower) — 面板 PMIC 防禦股

- **角色**：[[鴻海]] 系，產品 TFT-LCD / [[AMOLED]] driver + [[TDDI]] + 面板 PMIC。
- **Design-win**：[[友達光電]]、[[群創光電]]、中國面板廠。
- **營收**：Q1'26 EPS 1.86（YoY -43% 但 QoQ +18% 觸底回升）。**2026/5 法人吸貨 +3,108 張（PMIC 板塊最強）**。TTM P/E 20.1（板塊最便宜）、P/B 1.14、殖利率 4.60%。
- **2026-2027 看點 + 風險**：(+) 面板循環底位回升；(+) [[鴻海]] iPhone OLED 想像空間；(+) 估值便宜、低 β（44% 板塊最低）；(−) AI 伺服器無 design-win；(−) 顯示業務週期波動大。

### §5.12 [[嘉晶]] (3016) — TW 唯一量產 SiC / GaN epitaxy

- **角色**：[[漢磊投控]] 旗下，台灣唯一量產 4 吋 / 6 吋 [[SiC]] epitaxy + 6 吋 [[GaN]] epitaxy 廠。
- **Design-win**：國際功率 IDM 大廠（[[SiC]] epi 已獲認證）。
- **營收**：2025 全年 38.92 億 NT$（YoY -5.3%）、GM 7.88%（偏低）、Net 持續壓力——反映 [[Wolfspeed]] 等大廠規模成本壓制利基廠商。
- **2026-2027 看點 + 風險**：(+) AI 伺服器 800V HVDC [[SiC]] [[GaN]] 結構性需求；(+) [[漢磊]] 集團整合；(−) 國際 epi 廠規模優勢；(−) TTM P/E 298.78 估值極端。

### §5.13 [[杰力]] (5299, Excelliance MOS) — [[華碩]] 系利基 MOSFET fabless

- **角色**：[[華碩]] 集團子公司，中低壓 [[MOSFET]] + PMIC fabless。
- **Design-win**：[[華碩]] (ASUS)、[[微星]]、[[技嘉]] 主板；[[廣達]]、[[仁寶]]、[[緯創]] EMS。
- **營收**：2025 全年 14.83 億 NT$（YoY -12.3%）、GM 34.78%（提升中）、OPM 13.51%。市值 53.7 億——**最小 cap**。
- **2026-2027 看點 + 風險**：(+) [[朋程]] (8255) 私募加強車用佈局；(+) [[漢磊]] / [[世界先進]] 代工就近；(−) 規模最小、[[華碩]] 依賴度高；(−) 商用 PC 拓展速度為關鍵。

---

## §6 2026-2027 Catalysts & Risks

**Catalysts**：
1. **[[Nexperia]] 轉單持續放量**（2026 Q2–Q4）：荷蘭 / 中國談判進度若膠著，TW IDM ([[強茂]] / [[台半]] / [[德微]]) 訂單能見度延伸到 H2 2026。
2. **[[TI]] 7/1 漲價跟進**：PMIC + [[MOSFET]] 第二波，[[茂達]] / [[致新]] / [[矽力-KY]] 跟漲確認。
3. **[[NVIDIA]] 800V HVDC 量產 (2026Q4–2027Q1)**：[[Navitas]] × [[漢磊]] 6 吋 [[GaN]] 訂單 ramp、[[嘉晶]] [[SiC]] epi 加單。
4. **[[NXP]] × [[世界先進]] [[VSMC]] 12 吋投產 (2027)**：TW 12 吋 power BCD 突破。
5. **AI PC 換機潮**：[[大中]] Dr.MOS、[[茂達]] PMIC + 散熱 IC、[[致新]] NB PMIC 三家受益。

**Risks**：
1. **[[Nexperia]] 美國產能 ramp 加速**（[[Polar Semiconductor]] 合作 2026/5/27 已啟動）：TW 轉單窗口若縮短至 6 個月，2026 H2 訂單能見度不確定性升高。
2. **AI 伺服器架構若回落 48V 主流**（800V HVDC 部署延後）：[[漢磊]] / [[嘉晶]] [[GaN]] / [[SiC]] 量產時程被推遲。
3. **庫存週期反轉**：若全球 PC + 工控需求未如預期回溫，2026 H2 [[強茂]] / [[台半]] 庫存壓力再現。
4. **[[中國]] 國產替代加速**：[[矽力-KY]] 中國市佔率提升的同時，**TW 同業（[[致新]] / [[茂達]]）出口中國訂單可能被 [[矽力]] / 中國本土廠擠壓**。
5. **車用半導體去庫存延長**：[[Bosch]] / [[Continental]] 2026 訂單下修，[[台半]] / [[強茂]] 車用占比受壓。

---

## Appendix A — 完整 TW 功率元件 / PMIC 個股 mapping

| Ticker | 公司 | 板塊 | 本報告章節 | 角色 |
|---|---|---|---|---|
| 2481 | [[強茂]] | Semi Equipment & Materials | §3.1, §5.1 | Discrete IDM 龍頭 (全球第六大整流器) |
| 3675 | [[德微]] | Electronic Components | §3.3, §5.2 | 二極體 IDM ([[Diodes Inc.]] 子公司) |
| 5425 | [[台半]] | Semiconductors | §3.1, §3.3, §5.3 | 車用 Tier 1 IDM |
| 8261 | [[富鼎]] | Semiconductors | §3.1, §5.4 | 6 吋 DMOS fabless 高 GM |
| 6435 | [[大中]] | Semiconductors | §3.1, §3.7, §5.5 | AI 伺服器 Dr.MOS 黑馬 ([[茂達]] 集團) |
| 3707 | [[漢磊]] | Semiconductors | §3.4, §3.5, §5.6 | 6 吋 [[SiC]] / [[GaN]] foundry |
| 5347 | [[世界先進]] | Semiconductors | §3.6, §4.1, §5.7 | 8 吋 [[BCD]] foundry 龍頭 |
| 6415 | [[矽力-KY]] | Semiconductors | §3.6, §3.7, §5.8 | TW PMIC 龍頭 |
| 8081 | [[致新]] | Semiconductors | §3.6, §5.9 | NB / Server PMIC |
| 6138 | [[茂達]] | Semiconductors | §3.6, §5.10 | PMIC + 散熱 IC 動能股 |
| 4961 | [[天鈺]] | Semiconductors | §3.6, §5.11 | 面板 PMIC 防禦股 ([[鴻海]] 系) |
| 3016 | [[嘉晶]] | Semi Equipment & Materials | §3.4, §3.5, §5.12 | [[SiC]] / [[GaN]] epitaxy 唯一玩家 |
| 5299 | [[杰力]] | Semiconductors | §3.1, §5.13 | [[華碩]] 系利基 MOSFET fabless |
| 2369 | [[菱生]] | Semi Equipment & Materials | §4.5 | 功率元件封測利基 |
| 3611 | [[鼎翰]] | (台半 5425 子公司) | §5.3 | 條碼機，非 power semi 業務 |
| 3611 | [[統懋]] | Semiconductors | §3.3 (附錄) | Schottky 利基玩家 |
| 8255 | [[朋程]] | (尚未在 Pilot_Reports) | (建議新增) | 車用整流器、[[杰力]] 私募 |

**未在 themes 但建議新增 coverage**：8255 [[朋程]]（車用整流器專業廠，與 [[杰力]] 有私募投資關係，本報告 §5.13 提及但無深入）。

---

## Appendix B — Verification log

| Claim | Source | Confidence |
|---|---|---|
| [[Infineon]] 2026/4/1 漲 5–15% | 工商時報 + 數位時代 + Smart 自學網（3 source confirmed） | High |
| [[TI]] 2026/7/1 漲 PMIC + MOSFET | Pocketstock + 數位時代（2 source） | High |
| [[德微]] 漲 5–10%；[[強茂]] 55 計畫 | Sinotrade 豐雲學堂 + Smart 自學網 | High |
| [[Wingtech]] 中資 SASAC ~30% / 荷蘭 2025/10/13 接管 / 中國禁出口 ~70% / 2025/11/19 暫停 | [[Wikipedia]] Nexperia entry（Dutch government press + Chinese MOFCOM official）| High |
| [[Nexperia]] × [[Polar Semiconductor]] 美國代工 2026/5/27 | Nexperia 官方 + Business Wire | High |
| [[Wingtech]] $1.2B 訴訟 2026/5 | Wikipedia Nexperia entry | High |
| [[Nexperia]] 中國分裂送單到台灣 12" | Digitimes 2026-03-17 | Medium |
| NVIDIA 800V HVDC 2026Q4–2027Q1 Phase 1–2 | SemiAnalysis + Szsanyi blog | High |
| Rack 內仍 50V busbar（即使外部 800V） | SemiAnalysis Inside 800VDC Revolution | High |
| 800V HVDC 銅線減 45% / 1MW 機架 54V 需 200kg+ | The Register + NuttyCLD substack | High |
| ORv3 HPR V3 50V sidecar 300 kW / V4 ±400VDC 800 kW | Open Compute Project + Molex | High |
| 各個股財務數字 | Pilot_Reports 各 ticker 既有 `## 財務概況` 區段（不重算） | High |

**Adversarial verify 結果**：
- ✅ 所有 catalyst 量化主張至少 2 個 source
- ✅ [[Nexperia]] 事件時間軸完整可追
- ⚠️ Digitimes 2026/3 「Nexperia 12" 訂單分流到 TW」為單一 source，標記 medium confidence
- ⚠️ [[漢磊]] 接 [[Navitas]] × [[NVIDIA]] 800V HVDC 為**產業推測**，無 [[Navitas]] / [[漢磊]] 官方確認 → 為 *（推測）*

**Confidence marker 統計**：
- 高 confidence（無標記）：~75%
- `*（市場傳聞）*`：~15%
- `*（推測）*`：~10%

---

**報告結束。** 反向連結：[themes/功率元件.md](../../themes/功率元件.md)（機械式供應鏈索引）
