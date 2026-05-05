# 低軌衛星產業鏈 + 昇達科 (3491) + Zero-Error Systems + Radiation Hardening by Design

**日期：** 2026-04-30
**來源：** 本專案 Pilot_Reports (49 檔涉及 [[低軌衛星]]/[[SpaceX]]/[[Starlink]]/[[Kuiper]]/[[OneWeb]]) + 公開網路資料 (ZES 官網、Spirit Electronics、CB Insights)

---

## 一、低軌衛星 (LEO) 產業鏈總覽

低軌衛星不是單一行業，而是把**通訊、半導體、PCB、機構、天線**揉在一起的高頻次系統題目。它分三段：**太空段** (衛星本體)、**地面段** (Gateway 地面站 + 用戶終端 CPE)、**服務段** (營運商)。台灣電子供應鏈幾乎完全集中在太空段元件 + 地面段終端。

### A. 上游 — 材料與被動元件

| 角色 | 代表台廠 | 在做什麼 |
|---|---|---|
| 高頻 PCB 板材 (PTFE / 低 Dk Df) | [[台光電]] (2383)、[[台燿]] (6274)、[[騰輝電子-KY]] (6672) | 衛星本體 + 地面站射頻板的基板 |
| 高頻 PCB 製造 | [[華通]] (2313)、[[燿華]] (2367)、[[敬鵬]] (2355)、[[榮昌]] (3684)、[[連騰]] (6818) | 載板、天線板、Tx/Rx 模組板 |
| 軟板 (FPC) | [[台郡]] (6269) | 終端機構內走線 |
| 連接器 / 線材 | [[宣德]] (5457)、[[連展投控]] (3710)、[[萬旭]] (6134)、[[邑昇]] (5291) | RF 連接器、終端線束 |
| 高頻陶瓷 / [[MLCC]] | [[璟德]] (3152)、[[詠業]] (6792)、[[台嘉碩]] (3221) | 高頻濾波器、振盪器 |

### B. 中游 — 射頻 (RF) / 微波 / 毫米波元件

這層是台廠最具差異化、也是 [[昇達科]] 的主場：

| 角色 | 代表台廠 |
|---|---|
| **微波 / 毫米波被動元件** ([[Filter]]、[[Diplexer]]、追星天線) | **[[昇達科]] (3491)** ← 台灣唯一專注此領域的領導廠 |
| GaAs 化合物半導體晶圓 ([[PA]]、[[LNA]]) | [[穩懋]] (3105) |
| GaN 高功率元件 / RF MMIC | [[全訊]] (5222) |
| 微波模組封測 | [[同欣電]] (6271) |
| 相控陣列 / Phased Array 天線 | [[稜研科技]] (7812)、[[耀登]] (3138)、[[譁裕]] (3419) |
| RF 結構件 / 衛星機構 | [[公準]] (3178)、[[新復興]] (4909) |

### C. 中游 — 用戶終端 (UT / CPE) 與地面站

這是 **Starlink Dish** 那個碟形天線那塊的供應鏈：

| 角色 | 代表台廠 |
|---|---|
| Starlink CPE / VSAT 終端代工 | [[啟碁]] (6285)、[[攸泰科技]] (6928)、[[兆赫]] (2485)、[[大眾控]] (3701) |
| 終端電源供應器 | [[光寶科]] (2301)、[[群電]] (6412)、[[維熹]] (3501)、[[良得電]] (2462)、[[隴華]] (2424) |
| 機構 / 結構 | [[信錦]] (1582)、[[乙盛-KY]] (5243)、[[富田-創]] (4590) |
| 通訊用銅線 / 線纜 | [[大亞]] (1609)、[[金橋]] (6133) |

### D. 下游 — 全球三大營運商

- [[SpaceX]] 之 [[Starlink]]：已部署超過 7,000 顆衛星，目前商業化最成熟。
- [[Amazon]] 之 [[Kuiper]] (Project Kuiper)：2024–2026 集中發射，正在拉貨爬坡。
- [[Eutelsat OneWeb]]：第一代部署完成，第二代規劃中。

旁支：應用於 [[5G]] / 4G 微波回傳網路 (Microwave Backhaul) 的 [[Ericsson]]、[[Nokia]]、[[Ceragon]]，與 LEO 共用很多 RF 元件供應鏈。

---

## 二、昇達科 (3491) — 「台灣唯一微波/毫米波被動元件廠」

### 業務定位
- 1999 年成立，台灣唯一專注**微波 / 毫米波通訊元件**之領導廠商。
- 主力產品：**微波濾波器 ([[Filter]])**、**雙工器 ([[Diplexer]])**、**多工器 (Multiplexer)**、**追星天線 (Tracking Antenna)**。
- 技術頻段：微波至毫米波**全頻段** (覆蓋 Ku、Ka、V-band 等衛星常用頻段)。
- **低軌衛星營收佔比已突破 80%** ← 這是它變成純衛星題的關鍵數據。

### 客戶結構 (出處：`Pilot_Reports/Communication Equipment/3491_昇達科.md`)
1. **[[SpaceX]] / [[Starlink]]** — 最大客戶，供應**地面站 + 衛星本體**雙端的微波元件。
2. **[[Amazon]] / [[Kuiper]]** — 簽訂 **四年合約**，多數產品具**獨家供應**資格。這是市場最看重的訂單能見度。
3. **[[Eutelsat OneWeb]]** — 第三大 LEO 客戶。
4. **電信設備商** — [[Ericsson]]、[[Nokia]]、[[Ceragon]] 的 [[5G]] 微波回傳網路。

### 上游與競爭格局
- **上游 (供應商):** 台灣航太級 CNC 精密金屬件廠 (做 RF 諧振腔體、諧振桿)、特種高頻 PCB 板材廠、特殊抗環境表面處理材料。
- **競爭同業:** [[Smiths Microwave]] (英)、[[Filtronic]] (英)，全球 LEO 微波被動元件市場高度寡占。

### 為什麼它是「純題」(從財報看)
| 期間 | 營收 (百萬台幣) | 毛利率 | 營益率 |
|---|---:|---:|---:|
| 2023 | 1,585 | 40.4% | 12.8% |
| 2024 | 2,335 | 51.3% | 26.7% |
| 2025 | 2,452 | 51.1% | 23.4% |
| 2025 Q4 (單季) | **834** | **58.6%** | **27.6%** |

- 2024 年單一年度營收年增 **+47%**、毛利率從 40% 拉到 51%、營益率從 13% 拉到 27% — 這是 Kuiper 與 Starlink 同步拉貨後的營運槓桿。
- 2025 全年營收續增 +5%，且 Q4 單季毛利率衝到 58.6%、營益率 27.6%，反映高毛利的衛星本體訂單比重上升。
- 2025 全年 CAPEX 高達 **−816 百萬台幣** (上一年 −548)，加上融資現金流 +400 百萬，看得到**正在大幅擴產**以承接後續 Kuiper / Starlink 需求 — 這是訂單能見度高才會做的決策。

### 估值水位 (僅供脈絡)
股價 NT$1,410 (2026-03-26) 對應 **Forward P/E 43.4×**、P/S 39.6×、EV/EBITDA 138× — 已經反映高度的成長預期，屬於**衛星純題的估值溢價區**。任何 Kuiper 或 Starlink 的拉貨節奏遞延都會放大本益比壓縮。

### 關鍵風險點
1. **客戶集中度高**：[[SpaceX]] + [[Amazon]] 兩家合計很可能佔營收絕大部分；若 [[Kuiper]] 商轉時程遞延，季度數字會明顯波動。
2. **獨家合約期限**：Kuiper 是「四年合約」— 合約到期重議價或競爭者切入是長期風險 (主要威脅是 [[Smiths Microwave]] 與 [[Filtronic]])。
3. **CAPEX 紀律**：2025 已經砸 815M，產能去化得靠 Kuiper 真的拉貨上來；若需求曲線比預期平緩，會壓抑短期毛利。
4. **毫米波技術擴散**：穩懋 / 全訊 在化合物半導體往 RF 元件整合，長期可能侵蝕被動元件的價值佔比。

### 一句話總結
> **昇達科 = 台灣 LEO 衛星射頻被動元件純題 + Kuiper 獨家合約 + 自己擴產對賭未來四年訂單。** 看訂單就看它，但估值已經 price in 多數樂觀情境，後續股價跟 [[Kuiper]] 發射節奏、Starlink Gen3 規格定案高度連動。

---

## 三、Zero-Error Systems (ZES) — 產品搜尋結果

**地理註記**：常被誤認為「美國公司」，實際是**新加坡半導體新創**，2019 年從南洋理工大學 (NTU) 衍生 (spin-off)。在美國的能見度來自 **Spirit Electronics** (亞利桑那州，國防/航太通路商) 於 2024 年 10 月簽下的北美獨家代理協議；以及 **Airbus Ventures**、**Dart Family Office** 領投的 7.5M 美元 Series A。

策略：不做整片輻射加固 (rad-hard) 晶圓，而是用**保護 IC + 板卡模組**讓便宜的商規 COTS 元件能上太空。

### 產品線 — 全部聚焦「太空輻射容忍 (Radiation-Tolerant) 與 COTS 元件保護」

#### A. 保護用單晶片 IC (Radiation-Hardened Protection ICs)

| 產品 | 功能 | 用在哪 |
|---|---|---|
| **LDAP-IC** (Latch-up Detection And Protection) | 偵測單事件閂鎖 (Single-Event Latch-up, SEL)，瞬間斷電復位 | 保護 COTS FPGA / MCU / SoC 在太空輻射下不被 SEL 燒毀 |
| **Smart-LCL** (Latch-up Current Limiter) | 即時限流，防 SEL 演變成永久損壞 | 衛星電源軌的下游負載保護 |
| **TMR Voter-IC** (Triple Modular Redundancy Voter) | 三模冗餘投票表決，過濾單事件翻轉 (SEU) | 任務關鍵的記憶體 / 邏輯運算保護 |

#### B. 電源管理 IC (Power Management)

| 產品 | 功能 |
|---|---|
| **Point-of-Load (PoL) DC-DC** (rad-tolerant) | 供應太空板卡內各模組所需的低壓軌，內建 SEL/SEU 防護 |

#### C. ZSOM™ 系列 — 模組級產品 (公司目前主推的旗艦)

| 產品 | 規格 |
|---|---|
| **ZSOM™-F01** | 業界**首款**用 COTS FPGA ([[Xilinx]] **Zynq UltraScale+ ZU3EG**) 做的輻射容忍 System-on-Module。整合 ZES 自家 LDAP-IC + Smart-LCL + PoL，等於把保護電路 + COTS FPGA 打包成一塊可直接焊到衛星板卡的模組。發表於 2024–2025。 |
| **ZSOM™ MCU 版** | 使用 [[ARM]] **Cortex-M0+** 作為控制核心的 SOM，瞄準小衛星 (CubeSat / SmallSat) 的次系統控制器市場。 |

ZSOM 訴求點：傳統 rad-hard FPGA (例如 Xilinx 的 Versal AI Edge Space-grade 或 Microchip 的 RT PolarFire) 一顆動輒數萬美元、交期 18+ 月；ZSOM 用商規 COTS FPGA 加上保護電路，以**價格低約 1 個量級、交期短**為賣點。

#### D. 開發 / 認證服務

ZES 也對外提供 SEL / SEU 測試實驗服務 (用迴旋加速器做重離子輻照測試)，幫客戶驗證自己的 COTS 元件有沒有過 LET 門檻。

### 應用市場
- **小衛星與 [[低軌衛星]] 星系** (主要藍海，搭上 [[Starlink]] / [[Kuiper]] / [[OneWeb]] 與各國 SmallSat 浪潮)
- 太空酬載 (payload)、CubeSat 主機板
- 高可靠軍工航太控制系統 (透過 Spirit Electronics 進入北美國防市場)

### 與本專案台廠 LEO 鏈的關係

ZES 不在台灣供應鏈內，但它解決的問題跟 [[穩懋]] / [[全訊]] / [[同欣電]] 處在不同層 ——
- **穩懋 / 全訊**：化合物半導體 ([[GaAs]] / [[GaN]]) RF 元件 — 訊號路徑
- **ZES**：**控制平面** + **電源平面**的 COTS 保護 IC + SoM — 數位/控制路徑

如果想找台股對標：台灣目前**沒有**直接競品 (做太空 rad-tolerant 保護 IC 的廠)，最相近的是做太空電源、SoM、衛星 OBC 的廠商，例如 [[攸泰科技]] (6928) 之衛星終端 / [[稜研科技]] (7812) 之相控陣列 — 但這些都是衛星「應用層」而非保護 IC 層。ZES 比較像「太空版的 [[TI]] / [[ADI]] 子題」，台股目前沒有切入這塊。

---

## 四、Radiation Hardening by Design (RHBD)

**Radiation Hardening by Design (RHBD)** 是一種設計方法論，指**用標準商用半導體製程 (commercial CMOS / bulk Si) 做出能抵抗太空輻射的 IC**，依賴的是**電路、佈局 (layout) 與系統架構**，而**不是**特殊製程或材料。它與另一條路線 RHBP (Radiation Hardening by Process) 對立。

### A. 為什麼需要硬化 — 三大太空輻射效應

| 效應 | 全名 | 後果 |
|---|---|---|
| **TID** | Total Ionizing Dose | 累積輻射劑量改變電晶體閾值電壓 → 漏電上升、最後 IC 失效 |
| **SEE** | Single Event Effect | 單顆高能粒子打中 → 即時故障，分三類 (見下) |
| **DD** | Displacement Damage | 晶格缺陷累積 → 載子壽命下降，常見於光電元件、太陽能電池 |

**SEE 三子類**：
- **SEU** (Single Event Upset) — 翻一個位元 (記憶體 / 暫存器);
- **SET** (Single Event Transient) — 邏輯路徑上瞬間電流毛刺;
- **SEL** (Single Event Latch-up) — 寄生 SCR 觸發 → 短路、可能燒毀晶片;
- **SEFI / SEGR / SEB** — 功能中斷 / 閘極破壞 / 燒毀 (高壓 MOSFET / IGBT)。

RHBD 的目標就是用設計手段壓制這四種失效模式。

### B. RHBD vs RHBP — 兩條路的取捨

| 維度 | **RHBD** (Hardening by Design) | **RHBP** (Hardening by Process) |
|---|---|---|
| 製程 | 用標準商用 (TSMC / GF / 三星 / Intel) 28nm、22FDX、16nm FinFET 等 | 專用 SOI、Sapphire (SOS)、磊晶層加厚等特殊製程 |
| 成本 | 蹭主流 foundry 的 wafer，便宜很多 | 專線開模，數量級更貴 |
| 設計工作 | **重** — 需要在電路、佈局、架構三層都改 | **輕** — 用現成 PDK 即可 |
| 上市時間 | 較快 (跟得上摩爾定律) | 慢，先進製程通常落後 2-3 代 |
| 代表廠 | [[BAE Systems]]、[[Cobham Gaisler]]、[[Microchip]] (RT PolarFire)、[[Xilinx Versal AI Edge Space-grade]]、[[Zero-Error Systems]] (COTS+保護) | [[Honeywell]] HX5000 系列、舊的 Sandia / NRL 製程 |

> 註：這也解釋了為什麼 [[Zero-Error Systems]] 的策略選 RHBD 路線 + 用 [[Xilinx]] 標準 COTS FPGA + 自家保護 IC 包成 ZSOM ——他們把 RHBD 做到「模組化」這一層。

### C. RHBD 三層設計手段

#### C-1. 電路層 (Circuit-Level)

| 技術 | 對抗的效應 | 概念 |
|---|---|---|
| **DICE** (Dual Interlocked Cell) | SEU | 用 2 對交叉鎖存取代單一鎖存器，必須兩個節點同時翻轉才會 upset，機率 ≈ 0 |
| **TMR** (Triple Modular Redundancy) | SEU / SET | 三套同邏輯 + 多數投票表決電路 (Voter)。ZES 的 TMR Voter-IC 就是這個 |
| **EDAC / Hamming / BCH / Reed-Solomon** | SEU 在記憶體 | 編碼糾錯，1 bit / 2 bit 自我修復 |
| **時間冗餘 (Temporal Redundancy)** | SET | 同一邏輯三個不同時間點取樣 + 投票，比 TMR 省面積但慢 |
| **保護環 (Guard Ring)** | SEL | 在 PMOS 與 NMOS 之間插入 N+/P+ 環 → 截斷寄生 SCR 觸發路徑 |
| **電流限流器** | SEL | 監測異常電流並切電源 (ZES 的 Smart-LCL 就是商品化版本) |

#### C-2. 佈局層 (Layout-Level)

| 技術 | 對抗 | 概念 |
|---|---|---|
| **ELT** (Enclosed Layout Transistor) | TID | 把 NMOS 的閘極做成環狀 (ring-gate)，消除 STI (Shallow Trench Isolation) 邊緣漏電路徑 — TID 主要的失效來源 |
| **Body Tie / Substrate Contact 加密** | SEL | 縮短寄生 BJT 的基極阻抗，讓 SEL 更難觸發 |
| **節點間距加大 / Charge-Sharing 防護** | Multi-bit Upset | 把同一字元的位元在物理上拉開，避免一顆粒子同時翻多 bit |

#### C-3. 架構層 (Architecture-Level)

- **Lockstep CPU**：兩或三顆 CPU 跑同一指令流，比對結果不一致就 reset (常見於汽車 ASIL-D 與航太)
- **Scrubbing**：定期掃描 SRAM / Configuration RAM，偵測 EDAC 標記並修復 — FPGA 上必備 (Xilinx 的 SEM IP)
- **Watchdog + Auto-Reset**：對抗 SEFI，硬體看門狗在功能掛掉時強制重啟
- **Voltage / Frequency Margining**：低於額定壓 / 頻運行，留 TID 累積後仍可工作的餘裕

### D. RHBD 在低軌衛星 (LEO) 的角色

LEO 軌道輻射通量遠低於 GEO 或深空，但仍有：
- 南大西洋異常區 (SAA) 通過時的高粒子通量
- 內輻射帶邊緣 + 銀河宇宙射線 (GCR)
- 太陽質子事件 (SPE) 突發

LEO 又對成本敏感 (一個星系數千顆衛星)，所以 RHBD + COTS 變成主流選擇：
- [[SpaceX]] 的 [[Starlink]] 衛星明確走「COTS + 自有冗餘」(類 RHBD 思路)
- [[Amazon]] 的 [[Kuiper]] 同方向
- [[Eutelsat OneWeb]] 較傳統，仍用一定比例的 RHBP rad-hard 元件

這就是 [[Zero-Error Systems]] 的市場縫隙：賣**保護 IC + COTS 模組**給走 RHBD 路線的小衛星整合商，繞開傳統 rad-hard 廠的高價長交期。

### E. 台股對應 — 沒有純 RHBD IC 廠

台廠目前在 LEO 鏈內**沒有**直接做 RHBD IC 的公司。最相近的是：
- **[[穩懋]] (3105)** / **[[全訊]] (5222)** — 化合物半導體 RF 元件，本身對輻射相對不敏感 ([[GaAs]] / [[GaN]] 的 TID 容忍度遠高於 Si CMOS)，是繞開 RHBD 議題的另一條路
- **[[同欣電]] (6271)** — 高可靠封測，也是太空鏈裡保護 die-level 可靠度的另一層
- **[[昇達科]] (3491)** — 機構與被動元件，無 IC RHBD 議題

如果要找 RHBD 投資標的，台股目前主要靠**間接題**：誰拿到 [[Starlink]] / [[Kuiper]] 的板卡或元件訂單，誰就吃到 LEO 走 RHBD-COTS 路線的紅利。直接做 RHBD 設計 IP 的廠仍集中在美國 ([[BAE Systems]]、[[Microchip]]、[[Xilinx]] 子部門)、新加坡 ([[Zero-Error Systems]])、歐洲 ([[Cobham Gaisler]] — 瑞典)。

---

## 五、Sources

- 本專案 `Pilot_Reports/Communication Equipment/3491_昇達科.md` (財務數據與客戶結構)
- 本專案 49 檔 LEO 相關 Pilot_Reports (sector breakdown via grep `\[\[低軌衛星\]\]|\[\[SpaceX\]\]|\[\[Starlink\]\]|\[\[OneWeb\]\]|\[\[Kuiper\]\]`)
- [Zero-Error Systems — official site](https://zero-errorsystems.com/)
- [About Us — Zero-Error Systems](https://zero-errorsystems.com/about-us/)
- [ZES Launches Industry's First COTS FPGA-Based Radiation-Tolerant SOM for Space](https://zero-errorsystems.com/zero-error-systems-launches-industrys-first-cots-fpga-based-radiation-tolerant-system-on-module-for-space-applications/)
- [ZES Debuts Radiation Tolerant System-on-Module for Space](https://zero-errorsystems.com/zes-debuts-radiation-tolerant-system-onmodule-for-space/)
- [Zero-Error Systems on Spirit Electronics (US distributor)](https://spiritelectronics.com/linecard/zero-errorsystems/)
- [Zero-Error Systems (ZES) Pte Ltd — LinkedIn](https://sg.linkedin.com/company/zero-error-systems-zes)
- [Zero-Error Systems — CB Insights profile](https://www.cbinsights.com/company/zero-error-systems)
