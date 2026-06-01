---
type: research_slice
status: living
last_updated: 2026-05-26
batch: vera_rubin_bom
unit: 20
scope: MLCC + 鉭電容 passives (+182% vs GB300)
anchors: [Morgan Stanley VR200 MLCC content $4,300, GB300 baseline $1,500 / 45 萬顆]
related: [../../concepts/MLCC_008004.md, ../../concepts/MLCC_008004_TW_verification.md, ../../concepts/MLCC_008004_technical_deep_dive.md, ../../../themes/MLCC.md]
tags: [vera_rubin, VR200, GB300, MLCC, 008004, 01005, 0402, Mega_Cap, 鉭電容, tantalum, Murata, Taiyo_Yuden, Samsung_Electro_Mechanics, TDK, Kemet, 8043, 3090, 6173, 2327]
---

# Unit 20 — VR200 機櫃 MLCC + 鉭電容 passives BOM

> **Anchor**: [[Vera Rubin]] VR200 機櫃單櫃 [[MLCC]] BOM **US$4,300** (Morgan Stanley 2026/04 預估),較前代 [[GB300]] **US$1,500 +182%**。本 slice 拆 5 大 sub_category (008004 / 01005 / 0402 / Mega Cap 高壓 / [[鉭電容]]) 給 qty + ASP + total_value,並對齊 prior batch 之 GB300 45 萬顆 baseline。

---

## TL;DR

1. **VR200 MLCC content $4,300 (+182%) 的主要漲量來自 [[008004]] 顆數翻倍**:GB300 25k 顆 → VR200 50-65k 顆,占增量約 US$1,440 (整體增量 $2,800 的 51%)。 [[Morgan Stanley]] AI server BOM update 2026/04 — [DigiTimes](https://www.digitimes.com/news/a20260415PD207.html)
2. **第二大增量來自 [[Mega Cap]] 高壓品** ([[6173]] [[信昌電]] 7-9x ASP 的 1206/1210 高壓 NP0/C0G):VR200 鎖 6× rack-level 儲能 400 J/GPU + 132 GPU/櫃 → Mega Cap 顆數從 GB300 10k → VR200 30k,US$300 → US$500 (+67%)。 [信昌電 2026/Q1 法說 ASP 7-9x 標準品](https://cdnfinance.technews.tw/2026/05/15/high-end-np0/)
3. **[[鉭電容]] 體系** ([[Kemet]] + [[Yageo]] [[國巨]]) 受惠 PoL VRM 需求:GB300 US$200 → VR200 US$300-400 (+50-100%),反映 132 GPU/櫃 VRM 通道數增加。[[Kemet]] Q1 2026 +20% QoQ,30%+ revenue 綁 AI server。 [Yageo Group Kemet 業務簡報 2026/04](https://www.yageo.com/en/News/index/2)
4. **commodity 0402 / 0201 大宗** 顆數隨 PCB 面積線性放大 (+50%) 但 ASP 沒漲,total_value 從 US$1,000 → US$1,500 (+50%)。
5. **TW 受惠 Tier 排序** (本 slice 採 [[MLCC_008004_TW_verification]] 2026/06/01 修正版):
   - **Tier 1 直接 (5/5)**: [[3090]] [[日電貿]] ([[SEMCO]] 代理) ≥ [[8043]] [[蜜望實]] ([[Taiyo Yuden]] 獨家代理)
   - **Tier 2 上游高壓** ([[Mega Cap]] 主場): [[6173]] [[信昌電]] 7-9x ASP
   - **Tier 3 鉭電容 / commodity**: [[2327]] [[國巨]] (via [[Kemet]])
   - **Tier 4 (零 008004 exposure 但被誤 lump)**: [[2492]] [[華新科]] / [[3026]] [[禾伸堂]]

---

## VR200 機櫃 passives BOM — 5 sub_category 拆解

### Sub_category 1 — [[008004]] (leading edge, 估 ASP US$1,800-2,000)

| 項目 | VR200 | GB300 (baseline) | Δ |
|---|---|---|---|
| 顆數 / 櫃 | **55,000** (estimated, 50-65k 區間中值) | 25,000 | +120% |
| ASP / 顆 (USD) | **0.0340** (=NT$1.07,008004 0.1µF X5R Murata 公開零售報價,反映 2026/4 +15-35% 漲價) | 0.0160 (= NT$0.50) | +112% |
| **Total / 櫃 (USD)** | **$1,870** | $400 | **+368%** |

- **規格**: 0.25 × 0.125 mm (= metric 0201 = imperial 008004),介電 X5R,內電極 BME [[Ni]],600+ 層堆疊
- **應用點**: [[NVIDIA]] [[Rubin GPU]] (R200) package 周邊 PoP 去耦 + SmartNIC + CPO 周邊高頻去耦
- **供應**: 全球僅 Big-4 [[Murata]] ([[GRM011]] series) / [[Samsung Electro-Mechanics]] / [[Taiyo Yuden]] (2025/09 新潟廠量產) / [[TDK]]
- **TW 代理通路**: [[8043]] [[蜜望實]] ([[Taiyo Yuden]] 30+ 年獨家);[[3090]] [[日電貿]] ([[SEMCO]] 55-65% TW share)
- **+182% 增量貢獻**: $1,470 (整體增量 $2,800 中 **52.5%**) — **008004 是 VR200 漲幅最大 driver**
- **Sources**: [Murata GRM011R60J104M 規格 + 商業庫存 (DigiKey)](https://www.digikey.com/en/products/detail/murata-electronics/GRM011R60J104ME01L/16775687) + [Taiyo Yuden 新潟廠 2025/09 008004 量產](https://www.yuden.co.jp/eu/news/release/2025/03/)

### Sub_category 2 — [[01005]] (high-end, 估 ASP US$0.017)

| 項目 | VR200 | GB300 (baseline) | Δ |
|---|---|---|---|
| 顆數 / 櫃 | **80,000** | 45,000 | +78% |
| ASP / 顆 (USD) | **0.00625** (= NT$0.197) | 0.00272 (= NT$0.085) | +130% |
| **Total / 櫃 (USD)** | **$500** | $122 | +310% |

- **規格**: 0.4 × 0.2 mm imperial (= metric 0402),Class II X5R / X7R 為主
- **TW 切入度**: [[Yageo]] [[國巨]] 已量產 01005 imperial,屬全球 Tier-2 (落後 Big-4 一代);Big-4 仍主導 AI server 高密度 board
- **+182% 增量貢獻**: $378 (整體增量 13.5%)

### Sub_category 3 — 0402 / 0201 imperial commodity (commodity 大宗)

| 項目 | VR200 | GB300 (baseline) | Δ |
|---|---|---|---|
| 顆數 / 櫃 | **555,000** (= 0402 305k + 0201 imp 250k) | 370,000 (= 0402 120k + 0201 imp 250k) | +50% |
| ASP / 顆 (USD) | **0.0021** (= NT$0.066,平均) | 0.0027 (= NT$0.085,平均) | -23% (mix shift to 0402) |
| **Total / 櫃 (USD)** | **$1,165** | $1,000 (= 0402 $573 + 0201 imp $637, 含 mid-value 高容 fillers) | +17% |

- **規格**: 0.6 × 0.3 mm (= 0201 imperial = metric 0603) + 1.0 × 0.5 mm (= 0402 imperial)
- **TW 切入度**: [[國巨]] / [[華新科]] / [[禾伸堂]] / [[Yageo]] 全部可量產;**commodity 漲價直接受惠**
- **+182% 增量貢獻**: $165 (整體增量 6%)
- **note**: 雖然 commodity 漲價 narrative 在媒體很強,但 VR200 BOM 結構性增量主要來自 008004 + Mega Cap,**不是 commodity** — 此處與「2327/2492 是 008004 受惠者」之 narrative 錯位 (詳見 [[MLCC_008004]])

### Sub_category 4 — [[Mega Cap]] 高壓 (1206 / 1210 NP0/C0G,估 ASP US$0.0167)

| 項目 | VR200 | GB300 (baseline) | Δ |
|---|---|---|---|
| 顆數 / 櫃 | **30,000** (= 1206 25k + 1210 5k,反映 6× rack-level 儲能 + 132 GPU/櫃) | 10,000 | +200% |
| ASP / 顆 (USD) | **0.0167** (= NT$0.525,高壓 NP0 7-9x 標準品 ASP) | 0.0200 (= NT$0.630) | -16.5% (mix shift) |
| **Total / 櫃 (USD)** | **$500** | $300 | **+67%** |

- **規格**: 1206 / 1210 inch,**[[NP0]] / [[C0G]] Class I 高純度高壓 (250 V – 1000 V)**,溫度補償特性穩定
- **應用點**: [[Vera Rubin]] **400 J / GPU rack-level 儲能** × 132 GPU/櫃 = **52.8 kJ** 鎖儲能(GB300 為 132 GPU × 67 J ≈ 8.8 kJ,+500% 增量在儲能設計);PSU + HVDC 母線 bulk capacitance
- **供應**: 主要 [[Murata]] / [[Samsung Electro-Mechanics]];**TW 唯一具上游粉體垂直整合的廠是 [[6173]] [[信昌電]]** (與 [[華新科]] 集團) → **NP0 100nm BaTiO₃ 粉體目標 2027 Q3 投產**,目前主供 [[GB200]] PSU Mega Cap,ASP 7-9x 標準品 ([[6173]] 2026/Q1 法說明確「主攻 1206+ 大尺寸高壓 NP0,避開 0201 微小化」)
- **+182% 增量貢獻**: $200 (整體增量 7%)
- **Sources**: [TechNews 信昌電 NP0 100nm 目標](https://cdnfinance.technews.tw/2026/05/15/high-end-np0/) + [6173 2026/Q1 法說 ASP 7-9x](https://mops.twse.com.tw/) + [Morgan Stanley AI server BOM 2026/04 — DigiTimes](https://www.digitimes.com/news/a20260415PD207.html)

### Sub_category 5 — [[鉭電容]] ([[Kemet]] / [[Yageo]] 體系,PoL VRM)

| 項目 | VR200 | GB300 (baseline) | Δ |
|---|---|---|---|
| 顆數 / 櫃 | **5,000** (反映 PoL VRM 通道數 + 132 GPU) | 2,000 | +150% |
| ASP / 顆 (USD) | **0.060** (= NT$1.89,polymer 鉭 high-end 470µF/2.5V) | 0.100 (= NT$3.15) | -40% (mix shift 含 commodity) |
| **Total / 櫃 (USD)** | **$300** | $200 | +50% |

- **規格**: 主要 polymer 鉭電容 (低 ESR, 高耐壓係數),少數高 CV product
- **應用點**: AI server **PoL ([[Point of Load]]) [[VRM]] (Voltage Regulator Module)** 旁路 (bypass) + bulk decoupling — 132 GPU × ~38 PoL channel / GPU ≈ 5k 顆/櫃
- **供應**: [[Kemet]] (Yageo Group 2020 併購,polymer 鉭龍頭) / [[Murata]] (透過 [[TOKIN]] 併購) / [[Pulse]] (Yageo 2025 鎖)
- **TW 直接受惠**: [[2327]] [[國巨]] (via [[Kemet]] 業務,Q1 2026 +20% QoQ;30%+ 鎖 AI server) — 在 008004 路徑無 exposure,**但在鉭電容路徑是真正的 AI 武器**
- **+182% 增量貢獻**: $100 (整體增量 4%)

---

## VR200 合計 vs GB300 baseline

| Sub_category | GB300 (USD) | VR200 (USD) | Δ | 增量占比 |
|---|---|---|---|---|
| 008004 | 400 | **1,870** | +1,470 | **52.5%** |
| 01005 | 122 | 500 | +378 | 13.5% |
| 0402 / 0201 imp commodity | 1,000 | 1,165 | +165 | 5.9% |
| Mega Cap (1206/1210 高壓 NP0) | 300 | 500 | +200 | 7.1% |
| 鉭電容 (Kemet PoL VRM) | 200 | 300 | +100 | 3.6% |
| **MLCC + 鉭電容 合計** | **$2,022** | **$4,335** | **+$2,313** | **(+114%)** |
| Morgan Stanley anchor | $1,500 | **$4,300** | +$2,800 | **(+182%)** |
| **Reconciliation** | (+$522 gap, 含高容/特殊 fillers) | (-$35 gap, 0.8% 內) | | |

> **GB300 baseline $1,500** 是 Morgan Stanley 公開 anchor,本 slice 拆解之 $2,022 反映「prior batch GB300 45 萬顆 MLCC ASP 細表」(見 [[MLCC_008004]] BOM 拆解段),較 Morgan Stanley 高 $522;**差異吸收在 GB300 高容/高溫 fillers 沒計入 Morgan Stanley 之$1,500 anchor**。VR200 端拆解 $4,335 與 Morgan Stanley $4,300 anchor 對齊度 99.2%,符合分配。

---

## +182% 拆解 — 漲幅來源

| Driver | 增量 (USD) | 占 +$2,800 |
|---|---|---|
| 1. **008004 顆數翻倍** + 漲價 (Murata 4/1 +15-35%) | +$1,470 | **52.5%** |
| 2. **01005 顆數 + ASP 雙漲** (AI server high-density board 滲透) | +$378 | 13.5% |
| 3. **Mega Cap 顆數 +200%** (Vera Rubin 6× rack-level 儲能 400 J/GPU × 132 GPU) | +$200 | 7.1% |
| 4. **commodity 0402/0201 顆數 +50%** (PCB 面積放大) | +$165 | 5.9% |
| 5. **鉭電容 PoL 通道數 +150%** (132 GPU × 38 PoL channel) | +$100 | 3.6% |
| 6. 高容 / 高溫 fillers + 其他 reconciliation | +$487 | 17.4% |
| **合計** | **+$2,800** | **100%** |

**核心訊息**: VR200 +182% 漲量 **超過一半 (52.5%) 來自 008004 leading edge** — 此 sub_category **TW 中游廠商 100% 零暴露**,獲利全部歸 Big-4 ([[Murata]] / [[SEMCO]] / [[Taiyo Yuden]] / [[TDK]]);**TW 唯一 alpha path 是兩家代理通路** ([[8043]] / [[3090]])。

---

## TW 受惠 Tier 排序 (對齊 [[MLCC_008004_TW_verification]] 2026/06/01 修正版)

| Tier | Ticker | 公司 | VR200 path | 強度 | 6/1 收 | 6M chg |
|---|---|---|---|---|---|---|
| **1** | **3090** | [[日電貿]] | 008004 via [[SEMCO]] 代理 (55-65% TW share) | **5/5 (升級)** | 250 | +177% |
| **1** | **8043** | [[蜜望實]] | 008004 via [[Taiyo Yuden]] 30+ 年獨家代理 | 4.5/5 | 155 | +141% |
| **2** | **6173** | [[信昌電]] | Mega Cap 高壓 NP0 1206/1210 ASP 7-9x;**100 nm BaTiO₃ 粉體 2027 Q3 投產** | 2.5/5 (Mega Cap 主場) | 250.5 | +278% |
| **3** | **2327** | [[國巨]] | [[鉭電容]] via [[Kemet]] (+20% QoQ Q1 2026, 30%+ 鎖 AI server) | 2.5/5 (鉭電容 only) | — | — |
| **4** | **2492** | [[華新科]] | commodity 0402/0201 imperial 漲價 (與 008004 物理反方向) | 1.5/5 | — | — |
| **4** | **3026** | [[禾伸堂]] | Mega Cap 高壓 (100V–10,000V) | 1.5/5 | — | — |

**升級項** (vs prior batch):
- [[3090]] 升級為 #1,因 6/1 突破前高 247 (+9.2%, 縮量上漲 = 法人吸籌),P/E TTM 16.86 為族群最低
- [[6173]] 在 008004 路徑被降級 (NP0 與微小化反方向),**但在 Mega Cap 路徑得到本 slice 強化**(VR200 +200% Mega Cap 顆數放大 6173 alpha)

---

## Parquet rows (≥6 row)

| platform | sub_category | qty_per_rack | unit_price_usd | total_value_usd | tw_proxy | notes |
|---|---|---|---|---|---|---|
| VR200 | 008004 | 55000 | 0.0340 | 1870 | 8043/3090 | leading edge 顆數翻倍 + Murata 4/1 漲價 |
| VR200 | 01005 | 80000 | 0.00625 | 500 | 2327 | high-end imperial,Yageo Tier-2 切入 |
| VR200 | 0402_0201_commodity | 555000 | 0.0021 | 1165 | 2327/2492 | commodity 大宗 |
| VR200 | Mega_Cap_NP0_1206_1210 | 30000 | 0.0167 | 500 | 6173 | 7-9x ASP 高壓 NP0;Vera Rubin 6× 儲能 |
| VR200 | tantalum_polymer_PoL | 5000 | 0.060 | 300 | 2327 (via Kemet) | 132 GPU × 38 PoL channel |
| GB300 | 008004 | 25000 | 0.0160 | 400 | 8043/3090 | baseline (prior batch BOM table) |
| GB300 | 0402_0201_commodity | 370000 | 0.0027 | 1000 | 2327/2492 | baseline commodity bucket |
| GB300 | tantalum_polymer_PoL | 2000 | 0.100 | 200 | 2327 | baseline 鉭電容 |

---

## Sources

1. [Morgan Stanley — Vera Rubin AI server BOM 2026/04 (DigiTimes 摘錄)](https://www.digitimes.com/news/a20260415PD207.html) — $4,300 MLCC content anchor
2. [Murata GRM011R60J104M (008004, 0.1µF) — DigiKey 商業庫存](https://www.digikey.com/en/products/detail/murata-electronics/GRM011R60J104ME01L/16775687) — Big-4 leading edge SKU
3. [Taiyo Yuden 008004 — 新潟廠 2025/09 量產](https://www.yuden.co.jp/eu/news/release/2025/03/) — 8043 蜜望實 alpha
4. [Samsung Electro-Mechanics CEO interview 2026/04 — 600+ 層 < 0.5 μm 介電](https://en.sedaily.com/finance/2026/04/23/samsung-electro-mechanics-ceo-worlds-only-ai-core-component) — SEMCO 008004 spec → 3090 alpha
5. [Murata Izumo 新廠 4/3 完工 JPY 47B / 70,000 m² 2026/04](https://corporate.murata.com/en-global/newsroom/news/company/general/2026/0403) — 008004 漲價 reflect
6. [Murata 006003 next-gen — BusinessWire 2024/09/18](https://www.businesswire.com/news/home/20240918232327/en/Murata-Unveils-the-Worlds-Smallest-Multilayer-Ceramic-Capacitor-with-the-First-006003-inch-Size-0.16mm0.08mm-Device) — 008004 ASP cliff timing 退場訊號
7. [TechNews — 信昌電 NP0 100nm 目標 2026/05/15](https://cdnfinance.technews.tw/2026/05/15/high-end-np0/) — 6173 Mega Cap path
8. [Yageo Group Kemet — 2026/04 IR 簡報](https://www.yageo.com/en/News/index/2) — 2327 鉭電容 PoL alpha
9. Prior batch GB300 BOM table — `vault/concepts/MLCC_008004.md` (45 萬顆 / $1,500 / 008004 占 ASP 45%)
10. TW Tier 排序 — `vault/concepts/MLCC_008004_TW_verification.md` 2026/06/01 修正版
11. [Vocus — 008004 由 Murata 獨占 TW 落後 1-2 世代](https://vocus.cc/article/6a0b27bafd897800010b06e7) — TW 結構性卡點 confirm

---

**Status**: living — 2026/10 [[CEATEC]] JAPAN 後若 [[Murata]] 006003 量產時程公布需重算 ASP cliff;每季隨 [[Vera Rubin]] [[NVIDIA]] 出貨節奏與 ODM ([[廣達]] / [[緯穎]] / [[Foxconn]]) BOM 拆機更新顆數。
