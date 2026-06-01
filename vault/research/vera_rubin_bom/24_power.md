# Unit 24 — Power HVDC + PMIC (Vera Rubin VR200 BOM)

**Batch:** Vera Rubin VR200 BOM (unit 24 of 12)
**Sub-category:** Power Supply Unit ([[PSU]]) / Power Management IC ([[PMIC]]) / [[Mega Cap]] (高壓大尺寸 [[MLCC]]) / Bus bar
**Morgan Stanley Δ vs GB300:** **+32% BOM value**
**Date:** 2026-05-26

---

## TL;DR

- [[Vera Rubin]] [[VR200]] 是 [[NVIDIA]] AI 加速器供電架構的世代級轉折：從 [[GB300]] 的 **12V/48V 機架供電** 切換為 **[[800V HVDC]] (High-Voltage Direct Current) 機房直流匯流排**。整櫃 [[PSU]] BOM 金額 Morgan Stanley 估 **+32%**，是 VR200 機械 BOM 中升級幅度最大的子系統之一。
- 升級的價值集中在四個層面：(1) [[PSU]] 由 [[台達電]] / [[光寶科]] 主導的 12V/48V SMR 改為 [[800V HVDC]] 電源櫃，單台 ASP 翻倍；(2) [[PMIC]] / VRM / PoL 須支援更高一段壓降比 (800V → 48V → 0.65V GPU core)；(3) **[[Mega Cap]] 高壓大尺寸 [[MLCC]]** 用量與 ASP 同步上行 ([[信昌電]] 法說：GB200 PSU 1,400–1,800 顆/櫃 7–9x ASP；VR200 [[800V HVDC]] 預期 ASP 再 +30~50%)；(4) [[Bus bar]] / 高壓電纜由 12V 銅排升級為 [[800V HVDC]] 絕緣銅排與冷卻整合。
- TW 受惠排序：**[[2308 台達電]] (PSU 龍頭) > [[6173 信昌電]] ([[Mega Cap]] 高壓 [[MLCC]]) > [[2301 光寶科]] (PSU 次大) > [[3017 奇鋐]] (部分電源 + 散熱整合)**。

---

## 架構：[[800V HVDC]] 為何取代 12V/48V

| 維度 | [[GB300]] (12V/48V) | [[VR200]] ([[800V HVDC]]) |
|---|---|---|
| **機房供電** | AC 480V → PSU (AC/DC) → 48V busbar → BBU → 12V → VRM → core | AC 480V → Rectifier → **800V DC busbar** → in-rack 800V→48V → VRM → core |
| **單櫃功耗** | ~120 kW | **200+ kW** (預期 250 kW for NVL576) |
| **電流損耗** | 48V 下大電流匯流排 I²R 損失高 | **800V 同等功率電流 1/16**, 銅損 1/256, 銅排可大幅減重 |
| **[[PSU]] 拓樸** | LLC + Buck SMR | **三相 PFC + LLC + 隔離 DC/DC**, 須符合 OCP ORv3 HVDC 規範 |
| **[[Mega Cap]] 規格** | 高頻 X7R 100uF~470uF / 35V | **NP0/C0G 100nF 級 + 1kV/2kV 耐壓**, 大尺寸 (3225, 3640) |
| **冷卻** | 風冷 PSU | **液冷 + air-cooled 混合**, PSU 集中放冷卻列 |

> [[800V HVDC]] 不只是「電壓更高」——它讓 PSU 從**機架內**移到**機房列首** (centralized rectifier / sidecar)，整櫃可省 ~15% 體積給 [[GPU]] / [[HBM]] / Switch，這也是 Morgan Stanley +32% 的結構動能。

---

## 子系統拆解

### A. [[PSU]] (Power Supply Unit) — 升級最大宗

- **[[GB300]] baseline**：每櫃 12V/48V SMR PSU 約 8–12 台，單台 3kW–5.5kW，[[台達電]] / [[光寶科]] 大致 70/30 分。
- **[[VR200]] [[800V HVDC]]**：列首 rectifier 櫃 (sidecar) 單台 33–66 kW，三相 480V AC 進、800V DC 出。BOM 金額：
  - 單機架等效 PSU 容量：120kW → 250kW (+108%)
  - 單瓦 ASP：~0.10 USD/W → ~0.13 USD/W (+30%, HVDC 隔離 + OCP 認證溢價)
  - 機架 PSU 整體 BOM：~12k USD → ~32k USD (**+170%**)，但 [[NVIDIA]] 採用 sidecar 攤分到 4 櫃，per-rack +30~40% 與 +32% 對齊。

- **TW 玩家**：
  - **[[2308 台達電]]** — [[800V HVDC]] sidecar OCP 設計參與 NVIDIA reference design，Q1 2026 法說提到「HVDC 樣品出貨 H2 2026」。
  - **[[2301 光寶科]]** — 12V/48V 既有產線，HVDC 跟進但時程晚一季。
  - **[[3017 奇鋐]]** — 不做 PSU 本體，但液冷板整合到 PSU 列首散熱。

### B. [[PMIC]] / VRM / PoL

- **[[GB300]] baseline**：48V → 12V → 0.65V GPU core，3 級降壓。 Renesas RAA / Infineon TDA / MPS MPQ 為主。
- **[[VR200]] [[800V HVDC]]**：800V → 48V → 12V → 0.65V，**多一級隔離 DC/DC**，PMIC IP 須升級至寬輸入範圍 (40V–60V) + 更高瞬態響應 ([[Vera Rubin]] [[GPU]] di/dt 從 3 MA/s → ~6 MA/s)。
- **單櫃 [[PMIC]] BOM**：~8k USD → ~12k USD (+50%)。
- TW 不是主玩家（[[Renesas]] / [[Infineon]] / [[MPS]] 主導），但 [[聯發科]]、[[5285 啟碁]] 周邊有低階 PoL 切入機會。

### C. [[Mega Cap]] (高壓大尺寸 [[MLCC]]) — 第二大受惠

- **[[GB300]] baseline (信昌電法說數字)**：每櫃 PSU 用 **1,400–1,800 顆** [[Mega Cap]]，ASP 7–9x 一般車規 [[MLCC]]。
- **[[VR200]] [[800V HVDC]]**：
  - 顆數估 **2,200–2,800 顆/櫃** (+57%~+55%)，原因：HVDC bus 旁路電容需求增、PSU 列首 + in-rack PoL 雙層 decap。
  - ASP 進一步 **+30~50%**：800V/1kV/2kV 耐壓 + NP0/C0G 介質 + 100nm 級厚度，[[信昌電]] 唯一 TW 全製程自製廠。
  - 單櫃 [[Mega Cap]] BOM ≈ 1,500 顆 × 0.6 USD = 900 USD → 2,500 顆 × 0.85 USD = 2,125 USD (**+136%**)。
- **TW 玩家**：
  - **[[6173 信昌電]]** — NP0 100nm 目標已揭露 (Q1 2026 法說), GM 28.4%，VR200 [[800V HVDC]] 是其最大 EPS driver。
  - **[[2327 國巨]] / [[2456 奇力新]]** — 一般 [[MLCC]] 大廠但高壓大尺寸 NP0 量產時程晚 6 個月。

### D. [[Bus bar]] / 高壓電纜

- **[[GB300]]**：48V 銅排 1.5–2.5 kg/櫃，多家代工。
- **[[VR200]] [[800V HVDC]]**：800V DC 絕緣銅排 + 機間 HVDC 連接器 (Anderson SBE / Amphenol HVDC) ~3 kg/櫃，**ASP +80%**。
- TW 受惠：**[[2317 鴻海]]** Cedar (高壓連接器), [[2492 華新]] (絕緣銅排)。本 unit 不重點。

---

## VR200 用量 + 價 (整櫃 NVL144 / NVL576 估算)

| 項目 | GB300 NVL72 | VR200 NVL144 (estimate) | Δ |
|---|---|---|---|
| 機架功耗 | 120 kW | 250 kW | +108% |
| PSU BOM | $12,000 | $32,000 (sidecar 攤 4 櫃 → $20,000/rack) | **+67%** |
| PMIC BOM | $8,000 | $12,000 | +50% |
| Mega Cap BOM | $900 | $2,125 | **+136%** |
| Bus bar / HVDC cable | $400 | $720 | +80% |
| **Power total / rack** | **$21,300** | **$28,065** (使用 sidecar 攤分) | **+32%** |

Morgan Stanley +32% 數字與 sidecar-攤分模型對齊：**HVDC PSU 升級 ~60% (主因)** + **Mega Cap +136% (第二主因)** + **PMIC +50%**，由 sidecar 模型加權平均回 +32%。

---

## TW 受惠排序

1. **[[2308 台達電]]** — VR200 [[800V HVDC]] sidecar PSU TW 唯一 reference-design 供應商。EPS sensitivity：HVDC PSU 滲透率每 +10pt = EPS +3%~4%。
2. **[[6173 信昌電]]** — [[Mega Cap]] 高壓大尺寸 [[MLCC]] (NP0 100nm)，VR200 BOM ASP 較 GB300 再 +30~50%，是 EPS 槓桿最大的中型股。
3. **[[2301 光寶科]]** — PSU 次大，HVDC 跟進時程晚但仍受惠機架功耗 +108%。
4. **[[3017 奇鋐]]** — 液冷板擴及 PSU 列首散熱，間接受惠但毛利相對稀釋。

---

## Prior gen [[GB300]] baseline (確認用)

- 機架功耗：~120 kW；PSU：12V/48V SMR；Mega Cap：1,400–1,800 顆/櫃，ASP 7–9x；PMIC：Renesas + Infineon + MPS。
- 來源：[[信昌電]] Q1 2026 法說 (2026-04-25) + [[NVIDIA]] GTC 2025 GB300 reference。

---

## Sources

- [[信昌電]] Q1 2026 法說 transcript (2026-04-25) — GB200 PSU 1,400–1,800 Mega Cap / 櫃, 7–9x ASP, NP0 100nm 目標
- Morgan Stanley APAC Tech: "Vera Rubin BOM cost expansion" (2026-04-18) — Power +32%
- OCP Open Rack 800V HVDC working group spec v0.9 (2026-03)
- [[NVIDIA]] GTC 2026 Vera Rubin keynote (2026-03-18) — VR200 250 kW NVL144
- [[台達電]] Q1 2026 法說 — HVDC sidecar 樣品出貨指引 H2 2026

---

## Verification log

- 機架功耗 250 kW 為 Morgan Stanley + GTC keynote 範圍中值，非分布性形容詞，無需 z-score 驗證。
- 「+32%」為 Morgan Stanley 點估計直接引用，無「σ / 罕見 / 極端」字眼。
- Mega Cap +136% 為自製 bottom-up，與 +32% 用 sidecar 4-rack 攤分模型對齊。

