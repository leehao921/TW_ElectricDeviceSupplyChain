---
type: research
status: draft
last_updated: 2026-05-26
source_unit: 1
tags: [MLCC, 008004, spec, Murata, Taiyo_Yuden, SEMCO, TDK]
---

# Unit 1: 008004 規格 + 技術門檻 + Big-4 全球量產現況

## TL;DR

- **008004 = imperial 008004 = metric 0201 = 0.25mm × 0.125mm**，是目前商業量產中**最小**的多層陶瓷電容 (MLCC) 規格；與「imperial 0201 = metric 0603 = 0.6mm × 0.3mm」完全不同 size，**TW 媒體報導時極易混淆**。
- [[Murata]] 2014 年世界首發 008004，2019 年首次大規模量產供應 [[Apple]] 與 [[華為]] 5G 旗艦機，2024/09 進一步推出更小的 006003 (0.16mm × 0.08mm)，008004 已從「leading edge」滑向「mainstream high-end」。
- **Big-4 全球量產陣容**: [[Murata]] (世界首發)、[[Samsung Electro-Mechanics]] (Ultra-Compact 008004 High-Q 已商品化)、[[Taiyo Yuden]] (產品線內已列 008004)、[[TDK]]。AI 伺服器高階 MLCC 中，[[Murata]] 與 [[Samsung Electro-Mechanics]] 合計市占超過 80%。
- **2026 漲價時間軸**: [[Murata]] 4/1 漲 15–35% (AI 伺服器/車規/RF 微波)、[[Taiyo Yuden]] 5 月漲 6–13%、[[Samsung Electro-Mechanics]] 4 月起評估 5–10% 漲幅。主因白銀價格飆升與 [[NVIDIA]] AI 伺服器把高階 MLCC 產能稼動率推上 80%+。
- **Taiwan 公開資料中 ZERO 廠商揭露具備 008004 量產能力**；2327 國巨/2492 華新科 2026 4–5 月飆漲皆建立在「commodity MLCC + AI server 高用量」敘事，而非真正的 008004 規格突破。

---

## 規格定義與命名混淆

### 物理尺寸 (Imperial 008004 = Metric 0201)

| 命名 | Length | Width | Thickness | 對應系統 |
|---|---|---|---|---|
| **008004** (imperial) | 0.25 mm (±0.013) | 0.125 mm (±0.013) | ~0.125 mm | EIA inch code |
| **0201** (metric) | 0.20 mm | 0.10 mm | ~0.10 mm | JIS metric code，同樣指 008004-class |

[Source: passive-components.eu — MLCC Case Sizes Standards Explained](https://passive-components.eu/mlcc-case-sizes-standards-explained/)

### 命名混淆風險 (CRITICAL)

> "Imperial code for 0201 refers to a component that is 0.02 × 0.01 inches, while metric code for 0201 refers to a component that is 0.2 × 0.1 mm. These are completely different sizes." — [olimex blog, 2016](https://olimex.wordpress.com/2016/02/15/smt-component-sizes-and-metric-imperial-confusion/)

- **imperial 0201 = 0.02 × 0.01 inch ≈ 0.6 × 0.3 mm = metric 0603**: 屬於主流中高階規格 (smartphone 主板大量使用)，**並非超微型**。
- **metric 0201 = 0.2 × 0.1 mm ≈ imperial 008004**: 才是本研究探討的「超微型」。
- TW 新聞稿、券商報告經常把 [[Murata]]「0201 量產」直接翻成「0201 MLCC」，造成讀者誤把 0603-class commodity 當成 008004-class leading edge。
- **驗證原則 (本 vault 強制要求)**: 任何提及 "0201" 的新聞，必須先確認系 imperial 0201 (= 0603 commodity) 還是 metric 0201 (= 008004 leading edge)，否則該數據不得寫入 themes/MLCC.md。

### 同代規格家族對照

| Imperial | Metric (近似) | 尺寸 | 量產商業狀態 |
|---|---|---|---|
| 0402 | 1005 | 1.0 × 0.5 mm | mainstream commodity，多家可做 |
| 0201 | 0603 | 0.6 × 0.3 mm | high-volume，包含 [[Yageo]]、[[華新科]]、[[國巨]] |
| 01005 | 0402 | 0.4 × 0.2 mm | high-end，少數中小廠開始切入 |
| **008004** | **0201** | **0.25 × 0.125 mm** | **leading edge — 僅 Big-4 量產** |
| **006003** | **0.16 × 0.08 mm** (Murata 2024 自有命名) | 0.16 × 0.08 mm | [[Murata]] 2024/09 唯一發表 |

---

## 技術門檻 (為何只有 4 家能做)

### 1. 介電層厚度 < 0.5 μm

> "Samsung Electro-Mechanics produces MLCCs with over 600 stacked layers, while dielectric thicknesses have shrunk below 0.5 micrometers." — [Samsung Electro-Mechanics, AI Core Components, 2026](https://en.sedaily.com/finance/2026/04/23/samsung-electro-mechanics-ceo-worlds-only-ai-core-component)

- 學術論文亦驗證: "Ultra-thin multilayer ceramics capacitors (MLCCs) with layer thickness less than 1 μm are in urgent demand" — [ScienceDirect: High-dielectric-constant nanograin BaTiO3](https://www.sciencedirect.com/science/article/pii/S2772834X22000082)
- 厚度 < 1 μm 後，介電層內必須**至少含 4–5 層 [[鈦酸鋇]] 晶粒**才能維持絕緣可靠度，否則漏電流暴增、可靠度崩盤。

### 2. 層數 > 600 層 (假設 008004 規格)

- [[Samsung Electro-Mechanics]] 公開揭露 600+ 層堆疊能力為「state-of-the-art」。[[Murata]] 雖未公開層數，但 008004 0.1 μF 達成 (2026/04 發表 GRM011R60J104M) 意味同等級堆疊密度。
- 每片陶瓷生坯 (green sheet) 厚度需 < 1 μm，且 600 層必須完全對齊；任一層偏移即整顆報廢。

### 3. nano-grade [[鈦酸鋇]] 粒徑 50–100 nm

- 文獻顯示 008004 規格要求 [[鈦酸鋇]] 粒徑下探 50–120 nm，並保證在燒結後仍維持 tetragonal 相 — [ScienceDirect: Size dependent dielectric properties in BaTiO3 nanopowders for application of MLCC](https://www.sciencedirect.com/science/article/abs/pii/S0169433224018245)
- 全球能穩定供應 sub-100 nm [[鈦酸鋇]] 粉體的廠商**極度集中**:
  - [[Sakai 化學]] (Sakai Chemical Industry): 全球 MLCC 介電粉體市占 ~25–30%，sub-100 nm 業界龍頭。
  - [[Nippon Chemical]] (Nippon Chemical Industrial): 全球市占約 15%。
  - [[Fuji Titanium]] / [[Toho Titanium]]: 補位供應。
  - Source: [Chemical Research Insight — Top 10 MLCC Dielectric Materials Companies](https://chemicalresearchinsight.com/2025/06/10/top-10-companies-in-the-global-mlcc-dielectric-materials-market-2025-innovation-leaders-driving-capacitor-technologies/)
- **戰略意義**: 即使 [[Murata]] / [[Samsung Electro-Mechanics]] 想擴 008004 產能，仍受制於日本上游兩家粉體廠的擴產節奏 — 這也是本次漲價 cycle 結構性緊張的核心。

### 4. Ni 內電極極細線寬

- 008004 採 BME (Base Metal Electrode) [[Ni]] 內電極，線寬縮至 sub-μm 級。
- Ni 漿料 (Ni paste) 印刷+燒結後不得斷裂、不得氧化，需要高度 controlled atmosphere 燒結爐 (reducing atmosphere)。
- 良率關鍵: 內電極與介電層共燒收縮係數匹配。Big-4 累積數十年 know-how，新進入者極難追趕。

### 5. 設備與檢測門檻

- **多層 sheet 疊合機**: 必須在 clean room class 100 環境，且具備 sub-μm 對位精度。
- **AOI / X-ray 全檢**: 600 層內部結構必須逐顆檢測，CapEx 極高。
- **業界共識**: 008004 級 MLCC 整條 line 良率 < 80% 為常態 (vs. 0402 commodity > 95%)，這是 ASP 高昂的根本原因。

---

## Big-4 量產現況對照表

| 廠商 | 008004 status | 006003 status | 公開揭露 | 2026 產能動作 |
|---|---|---|---|---|
| **[[Murata]]** | 2014 首發、2019 量產 (Apple/Huawei 5G)；2026/04 推出 008004 0.1μF (GRM011R60J104M) | **2024/09 世界首發** 0.16×0.08mm，CEATEC 2024 展出 | [Murata press 2026/04](https://www.murata.com/en-us/news/capacitor/ceramiccapacitor/2024/0919) | Izumo 新廠 2026/04/03 完工，總投資 JPY 47B (~EUR 254.6M)，10 樓 ~70,000 m² |
| **[[Samsung Electro-Mechanics]]** | "Ultra-Compact 008004 inch High-Q MLCC" 商品化；600+ 層、<0.5μm 介電層技術 | 未公告 | [SEMCO 2026/04 CEO](https://en.sedaily.com/finance/2026/04/23/samsung-electro-mechanics-ceo-worlds-only-ai-core-component) | Philippines Calamba 廠 2026 初擴 AI server MLCC；Vietnam 投資 USD 1.2B 擴 embedded substrate line |
| **[[Taiyo Yuden]]** | 產品線內含 008004 (Newark 商業庫存可查)；無單獨 008004 milestone press | 未公告 | [Newark 008004 listing](https://www.newark.com/c/passive-components/capacitors/ceramic-capacitors/smd-mlcc-multilayer-ceramic-capacitors?capacitance=2pf&capacitor-case-package=008004-0201-metric-) | 2025/08 Tamamura 廠量產 22μF 0402 嵌入式 (AI server)；overall utilization ~85%，BB ratio > 1 |
| **[[TDK]]** | 公開資訊較少；學術文獻提及 TDK 0.25×0.125mm 量產 | 未公告 | [Newark 008004 listing](https://www.newark.com/c/passive-components/capacitors/ceramic-capacitors/smd-mlcc-multilayer-ceramic-capacitors) | 未公告專屬 008004 擴產 |

### 全球市占 (高階 MLCC)

| 指標 | [[Murata]] | [[Samsung Electro-Mechanics]] | [[Taiyo Yuden]] | [[TDK]] | [[Yageo]] | 中國廠 |
|---|---|---|---|---|---|---|
| 整體 MLCC | >40% | ~18% | ~13% | ~10% | ~13% | ~10% |
| 高階 (premium) MLCC | ~26% | ~18% | top-5 | top-5 | n/a | n/a |
| **AI server MLCC** | **Murata + SEMCO 合計 > 80%** | | minor | minor | minor | minor |

Sources:
- [Cytech Systems — Top MLCC Manufacturers](https://www.cytechsystems.com/news/top-mlcc-manufacturers)
- [Intel Market Research — MLCC for AI Server](https://www.intelmarketresearch.com/mlcc-for-ai-serverautomotive-market-36545)
- [Passive Components — China MLCC Makers Reach 10%](https://passive-components.eu/chinas-mlcc-makers-reach-10-market-share/)

---

## 2026 漲價時間軸

### 4/1 [[Murata]] 漲 15–35%

- **適用品項**: AI server 高電容 MLCC、車規 MLCC、RF/microwave MLCC。consumer-grade 0402/0603 commodity 並未全面漲價。
- **主因 (Murata 官方說法)**: 白銀 (Silver) 價格飆升 — 應用涵蓋太陽能、EV、半導體、AI 裝置、醫療設備。
- **次因 (analyst 觀察)**: FY2024 (2025/03 結束) 營業利益率掉到 13.1%，相比 peak 接近腰斬，需要 reprice 找回 margin。
- **需求面驅動**: [[NVIDIA]] AI 伺服器一台用 10–20 倍於 smartphone 的 MLCC 數量；高階產能稼動率 >80%。
- Sources:
  - [TrendForce 2026/03/17 — Murata Confirms April 1 Price Hike](https://www.trendforce.com/news/2026/03/17/news-mlcc-giant-murata-reportedly-confirms-april-1-price-hike-on-key-components/)
  - [BigGo Finance — Global MLCC Leader Murata Raises Prices](https://finance.biggo.com/news/Vh4P-5wBq7sy_YQMmKWR)
  - [BlockBeats — Murata 35% Increase Explained](https://m.theblockbeats.info/en/news/61594)

### 5 月 [[Taiyo Yuden]] 漲 6–13%

- 中國市場為首波，後續 rollout 全球。涵蓋 MLCC、inductor、電解電容。
- Source: [Digitimes 2026/04/17](https://www.digitimes.com/news/a20260417PD209/taiyo-yuden-mlcc-murata-electronic-components-price.html)

### 4 月起 [[Samsung Electro-Mechanics]] 漲 5–10%

- 內部已達成共識，類比 [[Taiyo Yuden]] 漲幅區間 (6–13%)，向 distributor 發出通知。
- Source: [Digitimes 2026/04/29 — SEMCO Price Hike 5–10%](https://www.digitimes.com/news/a20260429VL222/semco-price-mlcc-demand-murata.html)

### 漲價結構意義 (給 TW supply chain 的 read-across)

- **真正漲價的是高階 MLCC** (AI server、車規、RF) — 008004 是其中最高階子集。
- Commodity 0402/0603 並未跟漲；下游消費電子 OEM 仍 squeezing TW 中小廠。
- 因此 2327 國巨/2492 華新科 2026 4–5 月 +175% 行情中，「跟漲」假設若建立在 commodity 為主的產品組合上，可能被 over-priced。本 unit 提供的 spec gap 即為 deconstruct 該行情的核心 lens。

---

## 005003 / 006003 next-gen 預告

- **[[Murata]] 2024/09 已發表 006003 (0.16 × 0.08 mm)**: 體積比 008004 再縮小 75%，於 CEATEC JAPAN 2024 (2024/10/15) 展出。為「Murata 自定命名」(non-EIA standard)，呼應 imperial 0.006 × 0.003 inch。
- Source: [BusinessWire 2024/09/18](https://www.businesswire.com/news/home/20240918232327/en/Murata-Unveils-the-Worlds-Smallest-Multilayer-Ceramic-Capacitor-with-the-First-006003-inch-Size-0.16mm0.08mm-Device)
- **"005003" 尚未有公開 Murata 發表**: 本 unit 蒐尋未發現 005003 規格的官方 roadmap；可能為市場推測 / unverified。若需引用，務必標 "unverified"。
- **對 008004 的衝擊**:
  - 006003 量產初期 yield 仍低，2026 主要應用仍將是 smartphone 高階模組 (RF front-end, PA module)，AI server 因 board area 寬鬆暫不會 migrate 到 006003。
  - 008004 在 AI server / 高階 smartphone / 車規高密度 ECU 仍是 **2026–2028 主力規格**；不會被 006003 quickly cannibalize。
  - 但 [[Murata]] 公開 006003 即意味著其 008004 的製程已成熟、可往下世代邁進，鞏固了 leadership gap。

---

## ASP 對比 (估算)

> 本節無公開 1:1 ASP 對照 (Big-4 並不揭露單顆 ASP，distributor 通路報價亦會混合 spec)。以下為**業界口耳相傳的相對倍數**，建議標為「unverified industry estimate」並由 Unit 5/6 補強。

| Spec | 估算 ASP / 顆 (USD) | 倍數 (相對 0402) |
|---|---|---|
| 0402 (commodity, 1.0 × 0.5 mm) | $0.002–0.005 | 1× |
| 0201 (imperial 0201 = 0603, 0.6 × 0.3 mm) | $0.005–0.012 | 2–3× |
| 01005 (0.4 × 0.2 mm) | $0.015–0.030 | 6–8× |
| **008004 (metric 0201, 0.25 × 0.125 mm)** | **$0.040–0.100** | **15–30×** |
| 006003 (0.16 × 0.08 mm) | sample stage | n/a |

- ASP 倍數的核心驅動: 良率 (008004 良率 < 80% vs commodity > 95%)、設備折舊 (新製程線 CapEx 動輒數百 mUSD)、nano [[鈦酸鋇]] 粉體成本。
- **Verification needed**: Unit 6 應透過 distributor 報價 (Digi-Key / Mouser / Newark) 比對 [[Murata]] GRM011 vs GRM155 系列實際標價，建立 audit trail。

---

## Open questions

1. **[[TDK]] 008004 量產 status 不透明**: 學術文獻有提及，但 TDK 自有 press release 罕見。是否 TDK 已退出 008004 競賽、專注 0201/01005?
2. **[[Yageo]] / [[華新科]] / [[國巨]] 是否真有 008004 量產 line**？目前公開資料皆為 "miniaturization" 泛指，未見明確 008004 milestone。Unit 2/3 必須驗證 (否則 2327/2492 行情邏輯空洞)。
3. **[[Sakai 化學]] 與 [[Nippon Chemical]] 的 sub-100 nm [[鈦酸鋇]] 粉體擴產時間表**: 若上游粉體已 fully booked，Big-4 即使有設備也無料可投。本 unit 未取得 2026 擴產數字，需 Unit 4 補強。
4. **GB300 / [[Vera Rubin]] 機架中 008004 占比**: 業界估 GB300 每台 ~45 萬顆 MLCC，但 spec mix (008004 vs 0402 vs 0603) 未公開。VR200 機架 MLCC BoM 由 $1,500 → $4,300 (+182%) 是否由 008004 比重提高驅動？
5. **005003 規格是否真實存在 roadmap**: 本 unit 無法驗證；可能為 TW 媒體混淆 006003 (Murata 命名) 與 005003。建議 dedupe。

---

## Sources

- [Murata Develops the World's Smallest 0.1µF MLCC](https://eepower.com/new-industry-products/murata-develops-the-worlds-smallest-0-1c2b5f-multilayer-ceramic-capacitor/) — 2026 announcement, 008004 size 100nF。
- [Murata World-First 008004 Temperature Compensation 100pF MLCC Class I](https://passive-components.eu/murata-world-first-008004-size-temperature-compensation-type-100pf-mlcc/) — 規格定義來源。
- [Murata Launches 008004 Size MLCC (microfarads.com)](https://www.microfarads.com/times-articles/67-murata-008004-mlcc) — 2014 / 2019 量產時序背景。
- [Murata Unveils 006003 Size (0.16 × 0.08 mm) MLCC, BusinessWire 2024/09/18](https://www.businesswire.com/news/home/20240918232327/en/Murata-Unveils-the-Worlds-Smallest-Multilayer-Ceramic-Capacitor-with-the-First-006003-inch-Size-0.16mm0.08mm-Device) — 次世代規格首發。
- [Murata Izumo New Building Completion, evertiq 2026/04/07](https://evertiq.com/design/2026-04-07-murata-completes-new-mlcc-production-building-in-japan) — JPY 47B, 70,000 m², 2026/04/03 完工。
- [Samsung Electro-Mechanics CEO — AI Core Components, Seoul Economic Daily 2026/04/23](https://en.sedaily.com/finance/2026/04/23/samsung-electro-mechanics-ceo-worlds-only-ai-core-component) — 600+ 層、<0.5μm 介電。
- [SEMCO 2026 MLCC Calamba Expansion, Digitimes 2025/12/02](https://www.digitimes.com/news/a20251202PD205/semco-mlcc-production-ai-server-2026.html)
- [SEMCO Embedded Substrate Vietnam, Digitimes 2026/04/14](https://www.digitimes.com/news/a20260414PD221/semco-mlcc-embedded-substrate-packaging.html)
- [Taiyo Yuden 22μF 0402 Embedded MLCC for AI Servers, prnewswire](https://www.prnewswire.com/news-releases/taiyo-yuden-commercializes-1005m-size-embeddable-multilayer-ceramic-capacitor-with-22-f-capacitance-for-ai-servers-302600362.html) — Tamamura 廠 2025/08 量產。
- [TrendForce 2026/03/17 — Murata April 1 Price Hike Confirmed](https://www.trendforce.com/news/2026/03/17/news-mlcc-giant-murata-reportedly-confirms-april-1-price-hike-on-key-components/) — 15–35% range。
- [Digitimes 2026/04/17 — Taiyo Yuden Price Hike, Murata Leads, Samsung Follows](https://www.digitimes.com/news/a20260417PD209/taiyo-yuden-mlcc-murata-electronic-components-price.html)
- [Digitimes 2026/04/29 — SEMCO Considers 5–10% MLCC Price Hike](https://www.digitimes.com/news/a20260429VL222/semco-price-mlcc-demand-murata.html)
- [BlockBeats — Murata 35% Increase A Capacitor That Gives AI Empire a Cold](https://m.theblockbeats.info/en/news/61594) — 漲價結構與 AI 需求 narrative。
- [BigGo Finance — Silver Price Drives MLCC Costs](https://finance.biggo.com/news/Vh4P-5wBq7sy_YQMmKWR) — 原物料邏輯。
- [Passive Components — MLCC Case Sizes Standards](https://passive-components.eu/mlcc-case-sizes-standards-explained/) — Imperial vs metric 命名定義。
- [olimex blog — SMT Imperial/Metric Confusion](https://olimex.wordpress.com/2016/02/15/smt-component-sizes-and-metric-imperial-confusion/) — 0201 命名衝突詳述。
- [Chemical Research Insight — Top 10 MLCC Dielectric Materials Companies 2025](https://chemicalresearchinsight.com/2025/06/10/top-10-companies-in-the-global-mlcc-dielectric-materials-market-2025-innovation-leaders-driving-capacitor-technologies/) — Sakai 化學 25–30% 市占、Nippon Chemical 15%。
- [ScienceDirect — High-dielectric-constant nanograin BaTiO3 for ultra-thin MLCC](https://www.sciencedirect.com/science/article/pii/S2772834X22000082) — < 1 μm 介電層學術依據。
- [ScienceDirect — Size dependent dielectric properties in BaTiO3 nanopowders for MLCC](https://www.sciencedirect.com/science/article/abs/pii/S0169433224018245) — nano 粒徑要求。
- [Intel Market Research — MLCC for AI Server / Automotive 2026–2034](https://www.intelmarketresearch.com/mlcc-for-ai-serverautomotive-market-36545) — Murata + SEMCO >80% AI server 高階 MLCC 市占。
- [Cytech Systems — Top MLCC Manufacturers](https://www.cytechsystems.com/news/top-mlcc-manufacturers) — 整體市占結構。
- [Bitget News — NVIDIA Vera Rubin Pricing, VR200 MLCC $4,300 vs GB300 $1,500](https://www.bitget.com/news/detail/12560605422943) — AI server MLCC BoM 跳升 182%。
- [NVIDIA Developer Blog — Vera Rubin Platform](https://developer.nvidia.com/blog/inside-the-nvidia-rubin-platform-six-new-chips-one-ai-supercomputer/) — VR200 規格。
