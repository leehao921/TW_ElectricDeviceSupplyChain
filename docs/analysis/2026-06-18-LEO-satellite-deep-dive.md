# 低軌衛星 (LEO) 通訊技術 × 台灣供應鏈 Deep-Dive

**日期:** 2026-06-18
**Spec:** [docs/superpowers/specs/2026-06-18-leo-satellite-analysis-design.md](../superpowers/specs/2026-06-18-leo-satellite-analysis-design.md)
**機械式索引（reverse lookup）:** [themes/低軌衛星.md](../../themes/低軌衛星.md)
**Verification log:** [research-notes/00-verification-log.md](research-notes/00-verification-log.md)

---

## §0 TL;DR — 投資論點

低軌衛星 (LEO) 通訊系統由四節點構成：**用戶終端 ↔ 衛星 ↔ 星間光鏈路 (ISL) ↔ 地面站 (Gateway)**。每個節點需要五類核心元件：**[[Phased Array]] beamforming、Modem SoC（含 [[5G NTN]] / [[Direct-to-Cell]]）、RF 前端（PA/LNA/Filter）、[[Optical ISL]] TRx、高速 ADC/DAC + PLL**。

台灣供應鏈在 5 類元件中扮演角色如下：

| 元件類別 | TW 角色 | 結論 |
|---|---|---|
| Modem SoC + 5G NTN | **全球 leader** ([[聯發科]] [[MT6825]]) | 中性贏家，跨星座皆受惠 |
| Phased Array IC + 模組 | **fabless + foundry 雙鏈** ([[稜研科技]] + [[穩懋]]) | 小但完整 |
| GaN/GaAs PA | foundry 主導 ([[穩懋]]) + IDM ([[全訊]]) | 競爭力強，IDM 偏軍工 |
| RF 封裝、波導、濾波器 | 細分領域 leader ([[同欣電]]、[[昇達科]]、[[璟德]]) | 利基地位明確 |
| Optical ISL | **adjacent only**（[[矽光子]] cluster 偏 AI 資料中心） | 候選名單，無 confirmed LEO design-win |
| ADC/DAC + PLL | **結構性缺口** | TW 無 commercial 高速 RF ADC/DAC |

**核心論點**：台灣不是 LEO 端到端贏家，但 (a) [[聯發科]]在 [[5G NTN]] 是全球標準制定者；(b) [[昇達科]]、[[啟碁]] 等廠在用戶終端 / Gateway 段已拿到具體 design-win；(c) ADC/DAC 缺口為結構性弱項，需誠實揭露。

**最大尾端風險**：[[SpaceX]] 垂直整合（dishy 自製、payload 自研 ASIC）與 [[Direct-to-Cell]] 對傳統用戶終端 (UT) 市場的替代效應。

---

## §1 LEO 通訊技術 fundamentals

### §1.1 為何 [[低軌衛星]] 取代 [[GEO]]

地球同步軌道 (GEO) 衛星位於赤道上空 35,786 公里，單顆覆蓋約 1/3 地球表面，但**單向延遲 240–350 ms**（往返 ~600 ms），無法支援低延遲應用。LEO 衛星位於 340–1,200 公里高度，**單向延遲 5–30 ms**（接近地面光纖），可支援即時通訊與 [[5G]] / 6G 整合。

LEO 的關鍵權衡是**單顆覆蓋面積小** → 必須建構**大型星座**（constellation）才能達成全球覆蓋。[[SpaceX]] [[Starlink]] v1/v2 已部署 7,000+ 顆，[[Eutelsat]] [[OneWeb]] 約 650 顆，[[Project Kuiper]] 規劃 3,236 顆。星座越大，單顆衛星生產與發射的**單位成本**就越低（economies of scale），這正是 [[SpaceX]] Falcon 9 reusability 帶來的結構性優勢。

### §1.2 Space-Air-Ground 鏈路

LEO 通訊系統由四節點構成（沿訊號流向）：

1. **用戶終端 (User Terminal, UT / CPE)**：地面端的相位陣列天線 + 路由器，例如 [[Starlink]] Dishy。
2. **衛星 (Satellite payload)**：Phased Array 天線、PA/LNA、modem、payload processor。
3. **星間鏈路 (Inter-Satellite Link, ISL)**：[[Optical ISL]]（雷射）或 RF V-band 連接相鄰衛星，[[Starlink]] v2 採 100–200 Gbps 雷射。
4. **地面站 (Gateway)**：大型相位陣列或拋物面天線，連接星座與地面光纖骨幹。

訊號從用戶 → UT → 衛星 → ISL（跨多顆）→ Gateway → 地面 internet，反向亦然。每個節點都需要 RF 前端 + modem，但**頻段、功率密度、天線陣列規模**差異巨大，這形塑了不同層的供應鏈分工。

### §1.3 頻段配置

LEO 通訊主要使用四個頻段，由 [[ITU]] 與各國監管機關分配：

- **[[Ku-band]] (10.7–12.7 / 14.0–14.5 GHz)**：歷史最早商用，[[OneWeb]]、早期 VSAT 主流；穿透性中等。
- **[[Ka-band]] (17.8–20.2 / 27.5–30 GHz)**：[[Starlink]]、[[Project Kuiper]] 用戶段主軸；頻寬大、可支援數百 Mbps 單戶；對雨衰較敏感。
- **[[V-band]] (37.5–42 / 47.2–51.4 GHz)**：[[Starlink]] v2 Gateway 段、未來 multi-Gbps 鏈路；技術門檻最高。
- **S/PCS band (1.9 / 2.0 GHz)**：[[Direct-to-Cell]] 用戶段，重複使用既有 [[T-Mobile]]、[[AT&T]] 手機頻譜，讓未經改裝的智慧手機可直接連衛星。

### §1.4 五大 building blocks

整個 LEO 通訊系統可拆解為五類核心元件，本報告 §3 將逐一對應到國際 vendor 與 TW 玩家：

- **(a) [[Phased Array]] Beamforming** → §3.1
- **(b) Modem SoC（[[DVB-S2X]] / [[5G NTN]] / [[Direct-to-Cell]]）** → §3.4
- **(c) RF 前端：PA / LNA / Filter** → §3.2–3.3
- **(d) [[Optical ISL]] TRx** → §3.5
- **(e) 高速 ADC / DAC + Frequency Synthesizer (PLL)** → §3.6

---

## §2 四大星座技術 SKU 對比

四大星座代表四種不同的技術路線。理解每個星座的設計選擇，是理解 TW 供應鏈 design-win 分布的前提。

### Constellation Spec Matrix

| 規格 | [[Starlink]] v1 | [[Starlink]] v2 mini | [[Starlink]] v2 (full) | [[Project Kuiper]] | [[Eutelsat]] [[OneWeb]] | 台星 B5G ([[TASA]]) |
|---|---|---|---|---|---|---|
| 軌道高度 | 540–570 km | 530 km | 530 km | 590–630 km | 1,200 km | 600 km |
| 用戶端頻段 | Ku | Ka | Ka | Ka | Ku | Ka |
| Gateway 頻段 | Ka | Ka | Ka / V | Ka | Ka | Ka |
| Phased Array 世代 | 一代 | 二代 | 三代 (更大孔徑) | 二代 | 一代 | 一代/二代 |
| Optical ISL | 部分 | 是（~100 Gbps） | 是（~200 Gbps） | 規劃中 | 否 | 否 |
| Direct-to-Cell | 否 | 是（PCS） | 是 | 規劃中 | 否 | 否 |
| 已部署數 (2026 中) | 退役中 | 5,000+ | 1,000+ | 50+ | 650 | 0（規劃 2027 升空） |

**幾個重要觀察：**

- **[[Starlink]] v2 對 TW 廠最關鍵**：採用更高頻 (Ka + V band Gateway)、更大孔徑 Phased Array、[[Optical ISL]]、[[Direct-to-Cell]] 並行。技術門檻最高，但量也最大。
- **[[Project Kuiper]] 為 design-win 後進者**：2024–2025 已切入 TW 供應鏈（[[昇達科]] 取得衛星酬載 + UT + Gateway 三類元件訂單 *（per 2025 法說會 + TechNews 報導）*），2026 開始量產上線。
- **[[OneWeb]] 已被 [[Eutelsat]] 併購**：Ku-band 與 [[Starlink]] 形成差異化（穿透性、軍工）；TW 切入點集中在 Gateway 段（[[昇達科]]、[[中華電信]]）。
- **台星 B5G 為政策驅動**：[[TASA]] 主導的 Beyond 5G LEO satellite payload **由美商承建** — 揭示 TW 在 payload 系統整合仍有差距，但地面段（UT、Gateway、PCB、機構）TW 已能完整供應。

---

## §3 晶片層 supply chain matrix【核心章節】

### §3.1 [[Phased Array]] Beamformer IC

**功能**：在發射 (Tx) 或接收 (Rx) 路徑上提供每通道獨立的相位 (phase shifter) 與振幅 (variable gain amplifier) 控制，使數十至數千個天線單元的訊號相位即時對齊，達成電子掃描波束指向。LEO 用戶終端必須在毫秒級內追蹤掠空衛星，故 beam update rate 與通道密度為關鍵規格。

**國際主要 vendor 與 spec leadership**：

- **[[ADI]]** ADAR3000/3001：K/Ka band (17–31 GHz) payload-grade，4 beams × 16 channels，DC < 200 mW。
- **[[Anokiwave]]** AWMF-0132 (Rx, 17.7–20.2 GHz, NF 2.0 dB) + AWMF-0133 (Tx, 27.5–30 GHz)；Ku 對應 AWMF-0146/0147。明確定位 LEO/MEO/GEO 平板電子掃描天線。
- **[[Renesas]]** F5288：26.5–29.5 GHz 8-ch dual-pol TRX，SiGe BiCMOS，> +15.5 dBm linear output。
- **[[MaxLinear]]**：Ku/Ka SATCOM 電子掃描天線解決方案。

**TW 玩家角色**：

- **[[稜研科技]]** (7812)：fabless IC + 模組廠，BBox / BBoard 5G mmWave 模組整合 [[ADI]] ADMV4821 / ADMV4801 16-ch beamformer + ADMV1017 UDC。50 × 50 cm 可拼接天線模組對接同步衛星。**台廠中唯一具備 mmWave Phased Array 模組設計能力者**，由 [[英業達]] 為第二大股東提供 EMS，[[穩懋]] 為策略投資人提供 [[GaAs]] 代工。
- **[[穩懋]]** (3105)：[[GaAs]] HBT/pHEMT PA 與 LNA wafer foundry，供 [[ADI]]、[[Broadcom]]、[[Qorvo]]、[[Skyworks]] 等 IC 設計客戶。**全球最大化合物半導體 pure-play 代工廠**，市佔 > 70%。

### §3.2 [[GaN]] / [[GaAs]] Power Amplifier

**功能**：PA 位於 Tx 鏈最末端，決定 EIRP（等效全向輻射功率）。LEO payload 對體積、重量、功耗 (SWaP) 與熱管理極度敏感。

**[[GaN]] vs [[GaAs]] 技術權衡**：

| 指標 | [[GaN]] | [[GaAs]] |
|---|---|---|
| 功率密度 | 5–10 W/mm | 1–2 W/mm |
| 操作電壓 | 28–50 V | 8–12 V |
| C-band 效率 | ~48% | 25–30% |
| 熱導 (基板) | [[GaN-on-SiC]] ~490 W/m·K | ~140 W/m·K |
| LEO 應用分工 | 高頻 (Ka/V/E) payload、Gateway | Ku / 低 Ka 用戶終端 |

**國際主要 vendor**：

- **[[Qorvo]]**：[[GaN-on-SiC]] 0.25 μm 量產；C-band QPA2308 60 W、PAE > 47%。
- **[[Wolfspeed]]**：28 V [[GaN]] Ka MMIC；50 V CGHV40200PP 3 GHz / 250 W。
- **[[MACOM]]**：[[GaAs]] (Ka 27–31.5 GHz 2–6 W) + [[GaN-on-SiC]] (Ku) 雙線；2025 SATELLITE 展 125 W C-band [[GaN]] SSPA。
- **[[Filtronic]]**：2025 取得 [[SpaceX]] E-band [[GaN]] SSPA $62.5M 戰略訂單（Filtronic 史上最大單一訂單）+ 5 年供應承諾。Digitimes 報導合作名單含 TW 廠 [[穩懋]] 與 [[稜研科技]] *（市場傳聞，未經 IR/法說會證實）*。

**TW 玩家角色**：

- **[[全訊]]** (5222)：台灣唯一專精 [[GaAs]] / [[GaN]] 製程的 IDM（設計 + 晶圓 + 封測）。[[國家中山科學研究院 NCSIST]] 為最大客戶，歷史佔比達 8 成（天弓、雄風飛彈、雷達電子戰 PA）。商用切入 [[低軌衛星]] SAR HPA 與 [[5G]] 小基站；參與台灣太空三期計畫開發 [[GaN]] LEO payload PA。毛利長期 50%+。**注意：公開資料無 [[Starlink]] 直接供貨證據；正確定位為「軍工延伸 + LEO 地面站 mmWave PA」**。
- **[[穩懋]]** (3105)：[[GaAs]] HBT/pHEMT PA wafer foundry，間接服務 [[SpaceX]]、[[Project Kuiper]] 等星座（透過 IC 設計客戶）。6 吋 [[GaN-on-SiC]] 已量產，瞄準衛星 SSPA、雷達、毫米波，8 吋為長線。

### §3.3 LNA / Switch / Filter

**功能**：Rx 鏈中，[[LNA]] 為訊號首站，決定噪聲指數 (NF)；Switch 控制 Tx/Rx 切換；Filter 抑制頻外干擾。LEO 用戶終端 NF 直接影響 G/T 與 link budget。

**國際主要 vendor**：[[ADI]]、[[Qorvo]]、[[Skyworks]] 主導 [[GaAs]] pHEMT LNA die 與 SAW/BAW Filter；AWSC（台灣化合物半導體晶圓代工）為 [[SpaceX]] [[GaAs]] pHEMT LNA 詢價對象 *（市場傳聞）*。

**TW 玩家角色**：

- **[[同欣電]]** (6271)：全球前三大 [[CIS]] 封測廠 + 高頻陶瓷 / Hybrid IC 模組廠。承接太空級 Ku/Ka RF 收發模組後段構裝。市場推估每顆 [[Starlink]] 衛星約 6,000 顆 [[同欣電]] 封裝 Ku 模組 *（市場傳聞）*；2022 國巨董座陳泰銘公開確認與 [[SpaceX]] 合作。
- **[[璟德]]** (3152)：全球前三大 [[LTCC]] 高頻整合元件廠。LEO 應用：濾波器、天線、分工器已通過 [[Broadcom]]、[[聯發科]]、[[Qualcomm]] 三大基頻平台參考設計認證並出樣 LEO 終端。

### §3.4 Modem SoC + [[5G NTN]] + [[Direct-to-Cell]]

**功能**：modem SoC 處理 baseband / channel coding / Doppler 補償。LEO 場景特別考驗高 Doppler、頻繁 handover、以及（D2C 場景）未經改裝智慧手機的直連能力。

**LEO 三類 modem 分類**：
1. **LEO 用戶終端專屬 modem**（用於 dishy）：[[DVB-S2X]] 基底 + 客製化 stack；[[SpaceX]] 自研 ASIC。
2. **[[5G NTN]] modem**（用於 IoT / 手機備援連線）：[[3GPP Release 17]] / Release 18 NTN 標準。
3. **[[Direct-to-Cell]] modem**（智慧手機直連衛星）：在地面 5G modem 內加入 NTN 擴展。

**國際 vendor landscape**：

- **[[聯發科]]** ([[MT6825]])：全球**首款**商用 [[3GPP Release 17]] IoT-NTN 晶片組（2023 MWC 發表，CES 2024 Innovation Award）。L-band / S-band 雙向衛星訊息。
- **[[Qualcomm]]** ([[Snapdragon X80]] / X85)：首款內建 NB-NTN 旗艦 5G modem (MWC 2024 發表)，搭載 [[Samsung]] Galaxy S25。X85 為 2026 後續旗艦。
- **[[Broadcom]]**：較舊的 [[DVB-S2X]] satellite modem，LEO 切入不深。

**台灣是這個 block 的全球 leader**——[[聯發科]] HQ 在新竹，是真正意義上的「TW 內生的全球 standard-setter」，不是「TW 供應商服務外國 leader」。詳細個股 deep-dive 見 §5.7。

### §3.5 [[Optical ISL]] Transceivers

**功能**：星間雷射通訊，[[Starlink]] v2 mini 每對雷射 ~100 Gbps，v2 full 推估 ~200 Gbps，5,400 km 鏈路已 demo。LEO 大星座的「神經系統」。

**國際三大 vendor 結構**：

- **[[TESAT-Spacecom]]** ([[Airbus]] 子公司)：500K+ on-orbit 小時，Kepler ÆTHER 星座勝出。
- **[[Mynaric]]**：CONDOR Mk3 → [[Northrop Grumman]] SDA T1TL sole-source + Rocket Lab T2TL-Beta。
- **[[Coherent]]** (前 Lumentum / II-VI)：subsystem 級——pump lasers、isolators、doped fibers，不做整機。

**TW reality**：[[矽光子]] cluster（[[上詮]]、[[聯亞]]、[[華星光通]]、[[波若威]]）以 AI 資料中心 / [[CoWoS]] / [[CPO]] 為主軸，與 [[Optical ISL]] 為**相鄰技術生態**但**無公開 confirmed LEO design-win**。一個候選名字 [[萊德光電]] (7717) 定位 SLC passive components（pump combiner、fiber end cap、isolator）並參與星間鏈路相關元件，但具體衛星營收占比待 IR/法說會 primary 補證 *（候選，待證實）*。

[[昇達科]] (3491) 涵蓋的是 mmWave Inter-Satellite Link + TT&C 微波元件側，**非 Optical ISL**——兩個 ISL 路線（光 vs RF）需區分。

### §3.6 高速 ADC / DAC + PLL — TW 結構性缺口

**功能**：高速 ADC（> 10 GSPS）用於 direct-RF 取樣 Phased Array 數位 beamforming；DAC 用於 Tx 鏈；PLL/synthesizer 維持頻率穩定度。LEO Phased Array 數位 beamforming 是支援 thousands-of-channels 的關鍵。

**國際 vendor**：[[ADI]] (AD9213, AD9082)、[[TI]] (ADC32RF45)、[[Renesas]] 三家寡占。

**TW gap 揭露**：

- 台灣**無** commercial > 10 GSPS RF ADC/DAC。
- [[聯發科]] 在 modem SoC 內有 baseband ADC，但非 standalone RF ADC。
- [[ITRI]] 與 [[聯發科]] / [[中華電信]] 有 B5G NTN 研究合作，但**無 commercial converter 產品**。
- 證據：[[TASA]] 第一個 Beyond 5G LEO 衛星 payload **由美商承包**（Focus Taiwan 2025-04-01 報導）。

這是本報告**誠實點**——不要 paper over 為「[[聯發科]] 有 IP」或「[[ITRI]] 在做」。Gap 就是 gap，是 TW LEO 供應鏈未來 10 年的策略空間。

---

## §4 模組與系統層 TW 玩家

### §4.1 用戶終端 (User Terminal / CPE)

LEO 用戶終端是「天線 + RF 前端 + modem + 路由器 + 機殼 + 電源」的整機 ODM 產品，TW EMS / ODM 廠優勢明顯。

- **[[啟碁]]** (6285)：**全球最大 LEO UT ODM**，[[SpaceX]] [[Starlink]] dishy + router 主供，越南 Hà Nam 廠 3,000 人擴 2 倍。LEO 占 2025 全年營收 > 10%、絕對金額 > 120 億元 *（券商分析）*。
- **[[昇達科]]** (3491)：UT 內的 Ka / V band 波導與 OMT 元件。
- **[[台揚]]** (2314)：BUC / LNB 與 VSAT 整機。
- **[[譁裕]]** (3419)：天線陣列 + RF 模組。

### §4.2 Gateway 地面站

Gateway 是大型陣列天線 + 高功率 PA + 光纖回程的「衛星 access network 入口」。

- **[[耀登]]** (3138)：天線設計與整合。
- **[[攸泰科技]]** (6928)：天線整合 + UT；海事市場是主軸（[[Inmarsat]] GMDSS 8+ 年 design-win），衛星通訊 2024 占營收約 11%（per 公司 2024 業務分類）。
- **[[台揚]]** (2314)：BUC / Block Up Converter。
- **[[中華電信]]**：[[OneWeb]] 台灣 Gateway 運營商。

### §4.3 天線 / 波導 / 濾波器

- **[[昇達科]]** (3491)：台灣**唯一**掌握微波至毫米波（含 Ka/V band 矩形波導管）全頻段被動元件廠。橫跨「衛星酬載 + Gateway + UT」三層。[[SpaceX]] [[Starlink]] 為最大客戶；[[Amazon]] [[Project Kuiper]] 衛星酬載 + UT + Gateway 三類元件直接供貨（2025/9 TechNews + 2025/法說會）。2025 LEO 占營收約 59%（Q4 70%、Dec 74%），2026 全年挑戰 80%、年增 ≥150%（per 2026-01-22 法說會）。
- **[[詠業]]** (6792)：天線設計與小批量生產。
- **[[台嘉碩]]** (3221)：SAW filter。

### §4.4 PCB / 機構件 / 電源

- **[[台光電]]** (2383)：高頻 CCL；LEO 用戶終端 / Gateway 主板。
- **[[台燿]]** (6274)：高頻 CCL；[[Starlink]] V3 板材 design-in 。
- **[[群電]]** (6412)：電源管理。
- **[[燿華]]** (2367)：高層數高頻 PCB。

---

## §5 個股 deep-dive

### §5.1 [[啟碁]] (6285) — User Terminal 整機 ODM 龍頭

- **角色**：[[緯創]]集團子公司，自我定位「**全球最大 LEO UT 供應商**」。Dishy 天線、router（含 2 Gbps Wi-Fi 6 第四代）、地面 gateway 模組。核心競爭力：[[Phased Array]] 設計 + RF 前端整合。
- **Design-win**：[[SpaceX]] [[Starlink]] 已多年量產 dishy + router；[[Amazon]] [[Project Kuiper]] 切入地面端 *（市場傳聞）*；[[OneWeb]] 無明確 design-win。
- **營收占比**：2025 全年營收 1,102.5 億元，LEO 占 > 10%（絕對 > 120 億元）；2026 目標 40 億美元（1,255 億元），董事長謝宏波 2026-05-07 法說會說明。
- **2026-2027 看點與風險**：(+) 越南二廠擴產支撐 [[Starlink]] V4 dishy；CES 2026 展 [[Wi-Fi 8]]、OCS、PQC。(−) **雙重壓力測試**：[[SpaceX]] 垂直整合（dishy 自製）+ [[Direct-to-Cell]] 對 UT 市場結構性替代——這是本報告認為 [[啟碁]] 中期最大風險。

### §5.2 [[昇達科]] (3491) — Ka/V band 全頻被動元件唯一玩家

- **角色**：台灣**唯一**橫跨衛星酬載 + Gateway + UT 三層的微波至毫米波被動元件廠。產品含 Filter、Diplexer、多工器、OMT、追星天線、PA。
- **Design-win**：[[SpaceX]] [[Starlink]] 為最大客戶（地面站 + 衛星本體微波元件，Pilot_Report 已揭露）；[[Amazon]] [[Project Kuiper]] 三類元件直供（2025/9 TechNews、2025 天下雜誌）；[[Eutelsat]] [[OneWeb]] Pilot_Report 列下游客戶。
- **營收占比**：2025 全年 LEO 占 **59%**（Q4 70%、Dec 74%）；2026 全年挑戰 80%；2026 LEO 年增 ≥150%、獲利年增挑戰 150%（per 工商時報 2026-01-22 法說會報導）。
- **2026-2027 看點**：新品 TTSC / ISL / DFC 自 2024 Q4 出貨，毫米波延伸至 100 GHz+；越南租賃廠 7-8 成稼動 → 旁邊購地，2025 底發包，2027 完工。

### §5.3 [[全訊]] (5222) — 台灣唯一 [[GaN]] / [[GaAs]] IDM

- **角色**：fabless + IDM hybrid，設計 + 晶圓 + 封測整合。[[國家中山科學研究院 NCSIST]] 歷史佔比 ~80%（天弓、雄風飛彈 PA、雷達電子戰），向 ~70% 滑落（以色列/印度國防出口拉升至 ~30%）。
- **Design-win 路徑**：**defense-LEO SAR HPA**（法說會 confirmed）+ **28/39 GHz mmWave PA 用於 LEO 地面站**（法說會 confirmed）。**注意：無公開資料證實 [[Starlink]] / [[OneWeb]] 終端 PA design-win**——主報告不宣稱 [[全訊]] = [[Starlink]] supplier。
- **營收占比**：軍工 > 80%；非軍工（LEO + 5G PA）歷史單位數 %、2026 目標 15–20%；海外占 ~30%。
- **2026-2027 看點**：在手訂單 NT$12.7–13 億（約 1 年營收 locked-in）；2026 營收指引 NT$12 億，稅後 +~40% YoY；2025 CAPEX NT$1.86 億（2024 NT$0.59 億）→ 6-inch [[GaN-on-SiC]] 線擴產 *（推測）*。Dual-use synergy：同一線同時服務「[[台灣之盾]]」+ anti-UAV SSPA + 國防 SAR 衛星出口，3-tier 價差定價。

### §5.4 [[穩懋]] (3105) — 全球最大 [[GaAs]] PA 晶圓代工廠

- **角色**：全球 [[GaAs]] foundry 市佔 > 50% (部分產業報告 > 70%)。Process 涵蓋 [[GaAs]] (HBT/pHEMT/BiHEMT)、[[GaN-on-SiC]]、[[VCSEL]]。LEO 屬 Infrastructure 業務分類，2026 列為四大成長主軸之一（手機 PA / Wi-Fi 7 / AI 光通訊 / [[低軌衛星]]）。
- **Design-win**：[[Filtronic]] × [[SpaceX]] E-band [[GaN]] SSPA $62.5M 訂單（2025/8）合作名單，Digitimes 報導 [[穩懋]] 與 [[稜研科技]] 入列 *（市場傳聞，未經 IR/法說會證實）*。其他 IC 設計客戶（[[Broadcom]]、[[Qorvo]]、[[Skyworks]]、[[ADI]]）的 Phased Array beamformer / PA / LNA 多有外包至 [[穩懋]]。
- **營收占比**：2026 公司指引 Infrastructure 占總營收 30–35%；[[低軌衛星]] 預計達 Infrastructure 的 40% → 推算 LEO 約占總營收 12–14%。2026 Q1 合併營收 45.9 億 NTD，YoY +28%（2022 手機庫存調整以來最強 Q1）。
- **2026-2027 看點**：(1) 6 吋 [[GaN-on-SiC]] 量產→8 吋演進；(2) [[Direct-to-Cell]] [[GaAs]] PA + [[GaN]] 高頻雙軌受惠；(3) Mix shift——手機 PA 下行、Infrastructure 上行；(4) **揭露透明度低**——foundry 合約多受 IC 設計客戶 NDA 保護，公司法說以群組揭示。

### §5.5 [[稜研科技]] (7812) — TW 唯一 [[Phased Array]] 模組 fabless

- **角色**：fabless [[Phased Array]] 模組 + [[mmWave]] 量測系統純玩家。技術橫跨 [[Beamformer]] IC 整合、AESA 天線、BBox/UD Box 28/39 GHz 前端與系統對測。商業模式：(a) 高毛利 mmWave 儀器銷 35 國；(b) 模組系統切入 [[5G NTN]]、[[低軌衛星]] UT、HAPS、無人載具雷達、中東 [[Iron Dome]]。
- **Design-win**：[[Comtech]] ELEVATE multi-orbit terminal (2025 加拿大-台灣 EUREKA 框架，passive slotted-waveguide 版本功耗較 ESA 少 10%，2026 H1 場域對測)；中東 [[Iron Dome]] ≥ 8 年合約；HAPS 手機直連 2025 H1 出貨；印度 5G mmWave 全球最大公網案。**[[NVIDIA]] AI Aerial 直接合作未證實** *（市場傳聞）*。
- **營收占比**：儀器: 模組 2024 ≈ 9:1，2025 ≈ 7:3，2026 模組系統 ↑ 40%，2027 目標 50/50。LEO + Defense 推估佔 2027 模組營收 ≥ 60% *（推測）*。
- **2026-2027 看點**：2026 = 驗證 → 量產轉折年，管理層喊「明年轉虧為盈」；2024 營收 NT$143 M / 營業淨損 NT$181 M（毛損率 −126%）→ 估值風險高。

### §5.6 [[同欣電]] (6271) — 高頻陶瓷 / Hybrid IC 模組封裝

- **角色**：國巨集團成員，[[CIS]] 封測前三大廠 + 高頻陶瓷 / Hybrid IC 模組封裝利基廠。LEO 在 Ku/Ka RF 收發模組後段構裝。**不做天線整模**——定位是「封裝整合」。
- **Design-win**：[[SpaceX]] [[Starlink]] Ku 頻段 RF 收發模組（市場估計每顆衛星 ~6,000 顆）*（市場傳聞）*；2022 國巨董座陳泰銘公開確認 [[SpaceX]] 合作。客戶端 PA / LNA 來自 [[ADI]] / [[Qorvo]] / [[MACOM]] 航太級產品線 *（推測）*。
- **營收占比**：2025 Q3：[[CIS]] 52% / 電源 18% / Hybrid 23% / RF 11%；RF 內衛星 + 光通訊各半，衛星占公司總營收 ~5–6%；RF 模組 2025 年增 21.4%。
- **2026-2027 看點**：800G / 1.6T [[光收發模組]] 將超車衛星；陶瓷產線擴產瞄準 [[Starlink]] V3 + [[Project Kuiper]] / [[OneWeb]]；2027 營運倍增目標。

### §5.7 [[聯發科]] (2454) — [[5G NTN]] / D2C 跨星座**中性贏家**【核心個股】

- **角色**：全球 modem SoC leader，2025 全年營收 5,959.66 億元 (YoY +12.3%)。[[MT6825]] 為**全球首款**商用 [[3GPP Release 17]] IoT-NTN 晶片組（2023 MWC 發表、CES 2024 Innovation Award）。

- **Design-win 證據鏈（皆有原廠新聞稿）**：
  - **商用首發**：[[Motorola]] Defy 2 + CAT S75（2023 Q1 上市）為全球首批內建 [[3GPP]] NTN 雙向衛星簡訊 Android 手機。
  - **[[Skylo]] 認證**：[[MT6825]] 為 [[Skylo]] 衛星網路**首款獲認證**的 NTN 晶片組（2023）。
  - **[[Inmarsat]] L-band GEO**：完成全球首次 5G NB-IoT GEO 衛星資料連線實測。
  - **[[Eutelsat]] [[OneWeb]] LEO**：**2025/2/24** [[聯發科]] + [[Eutelsat]] + [[Airbus]] 全球**首次** 5G NR-NTN over [[OneWeb]] LEO 實網連線（[[3GPP Release 17]]，Ku-band，[[ITRI]] 提供 gNB）。
  - **Rel-19 升級**：**2025/11/3** [[ESA]] + [[聯發科]] + [[Eutelsat]] + [[Airbus]] + [[Sharp]] + [[ITRI]] + [[Rohde & Schwarz]] 全球**首次** Rel-19 NR-NTN over [[OneWeb]] LEO（Ku-band 50 MHz + conditional handover）。
  - **M90 5G-Advanced modem** (MWC 2025)：整合 R17/R18，內建 IoT-NTN + NR-NTN 雙模，2H25 工程樣本。

- **中性贏家 thesis**：多數 TW LEO 個股綁定特定星座（[[啟碁]] / [[華通]] 重壓 [[Starlink]] / [[Project Kuiper]] 終端；[[昇達科]] 重壓 Ka/Ku 地面段），星座輪替直接衝擊估值。**[[聯發科]] 不同**——
  1. [[3GPP]] NTN 是統一標準，[[MT6825]] + NR-NTN 可對接 [[Inmarsat]] GEO、[[Skylo]] 聚合網、[[OneWeb]] LEO，未來 [[Starlink]] [[Direct-to-Cell]] 若採 [[3GPP]] 標準也可對接。
  2. OEM 路徑：[[Samsung]]、[[小米]]、[[OPPO]]、[[vivo]]、[[Honor]] 已對齊 [[3GPP]] NTN，皆為 [[聯發科]] 天璣既有客戶。
  3. **不論哪個星座勝出，[[3GPP]] NTN 成為事實標準 → [[聯發科]] modem 必被需要。**

- **唯一非中性變數：[[Apple]] iPhone**——iPhone 14+ 緊急 SOS 採 [[Globalstar]] L-band 專有方案，晶片為 [[Qualcomm]] / [[Globalstar]] 客製化（非 [[聯發科]]）。2026 [[Amazon]] 收購 [[Globalstar]] 後由 [[Amazon Leo]] 接手（per MacRumors 2026/4 報導）。**[[聯發科]] 在 Apple 路徑無曝險也無上行**。

- **競爭**：[[Qualcomm]] [[Snapdragon X80]] (2024 MWC) 為首款內建 NB-NTN 旗艦 5G modem，搭載 [[Samsung]] Galaxy S25。分工：[[Qualcomm]] 主攻旗艦手機；[[聯發科]] 主攻中階 + IoT + 穿戴 + 車用廣譜，M90 對位旗艦。

- **營收占比**：NTN/D2C 對 2026 全年營收貢獻 < 1% *（推測，依產品線推論）*。法說會重心為 AI ASIC（2026 上修至 US$20 億、2027 數十億，目標市占 10–15%）+ 天璣旗艦。**NTN 屬「長期戰略佈局」**。

- **2026-2027 看點**：M90 modem 量產搭載天璣 SoC（2026 H2）；[[3GPP Release 18]] NTN 凍結 + 後 [[MT6825]] NR-NTN 量產；[[OneWeb]] / [[Starlink]] D2C / [[Amazon Leo]] 任一宣布 [[3GPP]] NTN 互通將是強多催化劑。

### §5.8 [[攸泰科技]] (6928) — 海事衛星 + 多軌 ESA roadmap

- **角色**：天線 + 用戶終端整合廠。[[大眾控]] (3701) 子公司。產品線 RuggON 工業手持 + 海事衛星終端 + 衛星通訊 + 客製化。
- **Design-win**：**[[Inmarsat]] GMDSS 海事終端 8+ 年 design-win**；[[ITRI]] + 經濟部產發署科專「多軌道衛星地面移動終端天線」（ESA roadmap）；衛星直連 D2C 訂閱服務 roadmap。[[OneWeb]] / [[Starlink]] / [[Project Kuiper]] 量產 UT 合約**公開資料未證實** *（市場傳聞）*。
- **營收占比**：2024 海事 62% / RuggON 16% / **衛星通訊 11%** / 客製化 11%（per 公司業務分類）。2025 H1 營收 11.47 億 / GM 25% / 稅後轉盈 +0.11 億。
- **2026-2027 看點**：ESA roadmap 進度；衛星直連訂閱業務 ramp。

---

## §6 2026-2027 Catalysts & Risks

**Catalysts**：

1. **[[Starlink]] V3 generational 升級**：更大 [[Phased Array]] 孔徑、Ka + V band Gateway、更高 ISL throughput。直接受惠：[[台燿]]（V3 板材）、[[昇達科]]（V band 波導）、[[穩懋]]（[[GaAs]] PA wafer）。
2. **[[Project Kuiper]] 2026-2027 正式商轉**：design-win 後進者，[[昇達科]] 已切入三類元件；新增 [[啟碁]] 切入機會 *（市場傳聞）*。
3. **台星 B5G 「鯢魚 1B」升空**：[[TASA]] 規格凍結 → TW 系統段 design-win。
4. **[[Direct-to-Cell]] 商用化**：[[聯發科]] [[MT6825]] / M90 modem 出貨放量；[[3GPP Release 19]] NR-NTN 標準化推進。

**Risks**：

1. **[[SpaceX]] 垂直整合**：dishy 自製比例提高、payload 自研 ASIC 擴大，擠壓 TW IC 設計與 ODM 空間。
2. **[[Direct-to-Cell]] 對 UT 市場結構性替代**：手機直連衛星壓縮傳統 dishy 終端需求，最大受衝擊個股為 [[啟碁]]、[[攸泰科技]]、[[台揚]]。
3. **頻譜監管延宕**：[[Direct-to-Cell]] PCS 頻段重複使用需各國個別核可，進度不一。
4. **中美科技脫鉤**：對台廠出貨美系星座（[[Starlink]]、[[Project Kuiper]]）的二次影響——若 [[China]] LEO 星座（[[千帆]]、[[國網]]）成形，TW 廠不會被允許參與。

---

## Appendix A — 完整 TW LEO 個股 mapping

對齊 [themes/低軌衛星.md](../../themes/低軌衛星.md) 列出的 42 家 TW 公司。

| Ticker | 公司 | 板塊 | 本報告章節 | 角色 |
|---|---|---|---|---|
| 6285 | [[啟碁]] | Communication Equipment | §4.1, §5.1 | UT 整機 ODM 龍頭 |
| 3491 | [[昇達科]] | Communication Equipment | §4.3, §5.2 | Ka/V 波導 + OMT |
| 5222 | [[全訊]] | Semi Equipment & Materials | §3.2, §5.3 | [[GaN]]/[[GaAs]] IDM (defense + LEO) |
| 3105 | [[穩懋]] | Semiconductors | §3.1, §3.2, §5.4 | [[GaAs]] PA foundry |
| 7812 | [[稜研科技]] | Communication Equipment | §3.1, §5.5 | [[Phased Array]] 模組 fabless |
| 6271 | [[同欣電]] | Semi Equipment & Materials | §3.3, §5.6 | 高頻 RF 封裝 |
| 2454 | [[聯發科]] | Semiconductors | §3.4, §5.7 | [[5G NTN]] 全球 leader |
| 6928 | [[攸泰科技]] | Computer Hardware | §4.2, §5.8 | 海事衛星 + ESA roadmap |
| 2485 | [[兆赫]] | Communication Equipment | §4.1 | UT 模組 |
| 2314 | [[台揚]] | Communication Equipment | §4.1, §4.2 | BUC/LNB + Gateway |
| 3419 | [[譁裕]] | Communication Equipment | §4.1 | UT 天線/RF |
| 3138 | [[耀登]] | Communication Equipment | §4.2 | Gateway 天線 |
| 3466 | [[德晉]] | Communication Equipment | (相關) | UT 模組 |
| 6152 | [[百一]] | Communication Equipment | (相關) | RF 連接器 |
| 6426 | [[統新]] | Communication Equipment | (相關) | 天線小批量 |
| 6134 | [[萬旭]] | Communication Equipment | (相關) | 連接器 |
| 3221 | [[台嘉碩]] | Communication Equipment | §4.3 | SAW filter |
| 3152 | [[璟德]] | Electronic Components | §3.3 | [[LTCC]] filter |
| 6792 | [[詠業]] | Electronic Components | §4.3 | 天線 |
| 6818 | [[連騰]] | Electronic Components | (中游) | RF 模組 |
| 5291 | [[邑昇]] | Electronic Components | (下游) | RF 連接器 |
| 2313 | [[華通]] | Electronic Components | (下游) | 高頻 PCB |
| 2367 | [[燿華]] | Electronic Components | §4.4 | 高頻 PCB |
| 2383 | [[台光電]] | Electronic Components | §4.4 | 高頻 CCL |
| 6274 | [[台燿]] | Electronic Components | §4.4 | 高頻 CCL |
| 6672 | [[騰輝電子-KY]] | Electronic Components | (相關) | 高頻 PCB |
| 6269 | [[台郡]] | Electronic Components | (相關) | FPC |
| 5457 | [[宣德]] | Electronic Components | (相關) | 連接器 |
| 3684 | [[榮昌]] | Electronic Components | (相關) | 連接器 |
| 4909 | [[新復興]] | Electronic Components | (相關) | 印刷電路板 |
| 2355 | [[敬鵬]] | Electronic Components | (相關) | PCB |
| 1582 | [[信錦]] | Electronic Components | (相關) | 機構件 |
| 3481 | [[群創]] | Electronic Components | (相關) | 面板 |
| 5243 | [[乙盛-KY]] | Electronic Components | (上游) | 機構件 |
| 6412 | [[群電]] | Electrical Equipment & Parts | §4.4 | 電源管理 |
| 6133 | [[金橋]] | Electrical Equipment & Parts | (相關) | 線材 |
| 1609 | [[大亞]] | Electrical Equipment & Parts | (相關) | 線材 |
| 3501 | [[維熹]] | Electrical Equipment & Parts | (相關) | 電源線材 |
| 2301 | [[光寶科]] | Computer Hardware | (相關) | 電源 |
| 3701 | [[大眾控]] | Computer Hardware | (相關) | [[攸泰科技]] 母公司 |
| 4916 | [[事欣科]] | Computer Hardware | (相關) | 連網裝置 |
| 2462 | [[良得電]] | Consumer Electronics | (相關) | 線材 |
| 3178 | [[公準]] | Semi Equipment & Materials | (相關) | 機構件 |
| 4590 | [[富田-創]] | Specialty Industrial Machinery | (相關) | 馬達 |
| 3499 | [[環天科]] | Scientific & Technical Instruments | (上游) | 衛星天線測量 |

**未在本報告深入但已 mapping 者**：38 家「(相關)」或非 §3-§5 重點 sub-block 的廠商，仍包含於完整供應鏈索引。

**[[萊德光電]] (7717)** 作為候選 [[Optical ISL]] 入點，**未在 themes 列入** — 待補進 themes/低軌衛星.md（建議方式：在其 Pilot_Report 中加入 `[[低軌衛星]]` wikilink，下一次 build_themes.py 即會自動納入）。

---

## Appendix B — Verification log

詳細 6 點 adversarial verification 紀錄見 [research-notes/00-verification-log.md](research-notes/00-verification-log.md)。摘要：

- 4/6 高 priority claim 完全 confirmed（[[聯發科]] 2025/02 + 2025/11 NR-NTN over [[OneWeb]] LEO、[[昇達科]] 2025/2026 LEO 占比區間、Amazon/Globalstar/Apple）
- 2/6 worker confabulation 攔截：
  - W06 「[[昇達科]] 2026 Q1 80.81%」→ 修正為「2026 全年挑戰 80%」（QoQ vs YoY 混淆）
  - W04 「[[萊德光電]] H1 2025 衛星 50%」→ 降級為「候選，待證實」
- 一個 URL 無法 verify（[[Filtronic]] 官網 403）：[[穩懋]] 在 [[Filtronic]]-[[SpaceX]] 合作名單維持「*市場傳聞*」標記

**Confidence marker 統計**：
- 高 confidence（無標記）：~70% 主張
- `*（市場傳聞，未經 IR/法說會證實）*`：~20%
- `*（推測，依產品線推論）*`：~10%

---

**報告結束。** 反向連結：[themes/低軌衛星.md](../../themes/低軌衛星.md)（機械式供應鏈索引）
