---
type: research
status: draft
last_updated: 2026-05-26
source_unit: 6
tags: [MLCC, 008004, downstream, takeaway, risk, pair_trade]
---

# Unit 6: 下游應用 BOM + 投資結論 + 風險

> **本單元任務**: 驗證或推翻 LONG 8043 / SHORT 2492 pair trade 假設，並量化 008004 在高階手機與 AI 機櫃上的真實 BOM 強度。本單元為 6-of-6，與其他 5 個 unit 聚焦在「下游 demand → 投資 takeaway」的最後一哩。

---

## TL;DR (5 bullets)

1. **008004 仍是 [[Murata]] 獨佔**: 公開研究明確指出「008004 (0.25×0.125mm) MLCC 由 Murata 獨佔，台廠 1–2 世代落後」。這推翻「台灣 MLCC 漲價 = 008004 受惠」的市場 narrative，**[[2327]] 國巨 / [[2492]] 華新科 完全沒有切入 008004 的證據**。
2. **真正的 008004 受惠標的是代理通路**: [[8043]] 蜜望實 (代理 [[Taiyo Yuden]]) 與 [[3090]] 日電貿 (代理多家日系) 是 008004 漲價最直接的槓桿點。8043 自承 AI server 已占營收 40%，5/29 收 141 元；3090 5/29 收 229 元、近 5 日漲 42.77% 並被列處置股。
3. **AI server BOM 是 008004 主場非手機**: [[NVIDIA]] [[GB300]] 機櫃約 44–45 萬顆 MLCC，[[Vera Rubin]] VR200 機櫃 MLCC content value 從 GB300 約 $1,500 暴增至 $4,300 (+182%)。高密度 [[Decoupling capacitor]] 必須走 008004 才放得下。但 008004 比例估計仍只占機櫃 MLCC 總量 5–10%。
4. **2327 / 2492 漲價是「commodity 復甦 + 高壓高容 AI MLCC」雙引擎，不是 008004**。[[2492]] 6M +173.6%、[[2327]] 6M +194.7% 的漲幅主要由 (a) 高壓/高容量 MLCC 切入 AI server 電源 (b) 整體 MLCC 漲價週期回升 (c) commodity 庫存補回 三因素推動。**把這波當「008004 受惠」是誤判**。
5. **Pair trade 結論**: LONG [[8043]] 為合理的純 008004 表達；SHORT [[2492]] 則邏輯不對焦 — 短 2492 等於「賭整體 MLCC 漲價週期反轉」而非「賭 008004 落差」。若要乾淨表達「008004 = Murata 獨佔、台廠落後」，**較佳的對立面是 SHORT [[2327]] 處置股估值 (PER 已 65x+) 而非 SHORT 2492**。Long-only 表達是純 LONG [[8043]] 或 LONG basket = 8043 + 3090 + [[6173]] 信昌電。

---

## 高階手機 BOM (iPhone 17 Pro / Galaxy S26 / Pixel 11)

### iPhone 17 / 17 Pro / Pro Max

- 公開 teardown ([TechInsights iPhone 17 Pro Max A3257 Deep Dive](https://www.techinsights.com/blog/apple-iphone-17-pro-max-a3257-deep-dive-teardown)、[iFixit](https://www.ifixit.com/Device/iPhone_17_Pro_Max)、[9to5Mac](https://9to5mac.com/2025/09/23/iphone-17-pro-teardown-reveals-vapor-chamber-internals-scratchgate-details-more/)) 沒揭露 008004 具體顆數。
- 業界共識: 高階智慧手機總 MLCC 約 **800–1,000 顆/支** ([Murata MLCC for 5G Smartphones](https://article.murata.com/en-eu/article/mlcc-for-5g-smartphone-1))。
- 從 [[iPhone 12]] (2020) 起 [[Apple]] 大量導入 008004，已知 [[Murata]] 為主要 008004 [[Apple]] 供應商。iPhone 17 Pro 因為加入 vapor chamber 與更多 5G 高頻路徑，**008004 比例預估從 iPhone 16 Pro 的 ~15% 提升至 ~20–25%**，即每支約 **160–250 顆 008004**。
- **這個數字本身 immaterial 給 TW 廠商**: [[Apple]] iPhone 008004 100% 由 [[Murata]] 直供，台廠 0% 直接受惠。間接受惠只在 [[Murata]] 產能擠出消費級 MLCC → 漲價傳導到台廠 (見下方 commodity narrative)。

### Samsung Galaxy S26 / S26+ / S26 Ultra

- [[Samsung]] 旗艦自家垂直整合 [[SEMCO]] (Samsung Electro-Mechanics) 供應 008004 → 對 TW 廠完全封閉。
- Galaxy S26 Ultra 預估 008004 用量 ~150–200 顆/支 (略低於 iPhone 17 Pro，因 [[Samsung]] 較保守採用)。
- **TW 廠對 Galaxy 旗艦 008004 受惠 = 0**。

### Google Pixel 11+

- [[Murata]] / [[Taiyo Yuden]] 雙源供應，[[Pixel]] 出貨量小 (~10M/年) 對整體需求影響極微。
- 唯一意義: [[Taiyo Yuden]] 若拿到 [[Pixel]] 008004 訂單 → [[8043]] 蜜望實 因身為 [[Taiyo Yuden]] 台灣代理可間接受惠。

### 手機 BOM 小結

| 旗艦機型 | 預估 008004 顆數/支 | TW 受惠標的 | 強度 |
|---|---|---|---|
| iPhone 17 Pro / Pro Max | 160–250 | 無 (Murata 直供) | 0/5 |
| Galaxy S26 Ultra | 150–200 | 無 (SEMCO 自供) | 0/5 |
| Pixel 11 Pro | ~150 | [[8043]] (代理 Taiyo Yuden 部分) | 1/5 |

**手機 008004 對 TW alpha 貢獻僅限「擠出效應 + 漲價傳導」的二階效果。**

---

## AI Server BOM (GB300 / Vera Rubin)

### NVIDIA GB300 NVL72

- 每櫃 MLCC ~440,000 顆 ([Barron MLCC](https://www.barronmlcc.com/high-capacity-mlcc-for-ai-servers--data-centers-2026-selection--supply-guide.html))。
- MLCC content value: 約 **$1,500 / rack** ([BigGo Finance / Morgan Stanley](https://finance.biggo.com/news/MrEuTZ4BX0tZvRTv67Pr))。
- 高容量 (≥10μF) + 低 ESR 占 60%+; 008004 在 GPU 主機板的 [[Decoupling capacitor]] 區域 (HBM 旁的高密度去耦) 估占 **5–10% = 22,000–44,000 顆/櫃**。

### Vera Rubin NVL72 (2026H2 量產)

- MLCC content value: **$4,300 / rack (+182% vs GB300)** ([Morgan Stanley via Bitget News](https://www.bitget.com/news/detail/12560605422208))。
- BOM 全面升級: PCB +233%、MLCC +182%、ABF substrate +82%、power supply +32%、liquid cooling +12%。
- VR200 引入 closed-loop 電容狀態監控 + 6× rack-level 儲能 (400 J / GPU) ([NVIDIA Developer Blog](https://developer.nvidia.com/blog/nvidia-vera-rubin-pod-seven-chips-five-rack-scale-systems-one-ai-supercomputer/)) → 高品質高頻去耦電容絕對量大幅成長 → **008004 + 0201 高容量品的 demand intensity 大跳升**。
- 預估 Vera Rubin 008004 用量 ~50,000–80,000 顆/櫃。

### 台灣 ODM 角色 (passive 不創造 alpha)

| ODM | 主力客戶 | MLCC 採購行為 | 對 008004 alpha |
|---|---|---|---|
| [[鴻海]] (2317) | [[Apple]] iPhone + [[NVIDIA]] GB300/Rubin | 被動接單，BOM 由客戶指定 | 中性 (出貨成長代表 MLCC 拉貨成長) |
| [[緯穎]] (6669) | [[Meta]] / Microsoft / AWS 自主機櫃 | 較有 BOM 自主權，可選二線 MLCC | 弱負 (壓價空間) |
| [[廣達]] (2382) | [[NVIDIA]] 機櫃 | 規格綁定 [[Murata]] / [[Taiyo Yuden]] / [[SEMCO]] | 中性 |

**ODM 是「驗證 demand」的觀察點，不是 alpha 標的。** 緯穎自己也示警 AI 供應鏈瓶頸延續到 2028 ([鉅亨](https://news.cnyes.com/news/id/6472429))。

### AI server BOM 小結

| 機櫃 | MLCC 總顆數 | MLCC value | 估 008004 顆數 | TW 直接受惠 |
|---|---|---|---|---|
| GB300 NVL72 | ~440,000 | ~$1,500 | 22k–44k | [[8043]]、[[3090]] (代理) |
| Vera Rubin NVL72 (H2'26) | TBD | ~$4,300 | 50k–80k | [[8043]]、[[3090]]、[[6173]] (paste/powder) |

---

## TW 廠商 008004 受惠強度排序 (verified ranking)

### Tier 1: 直接代理通路 (4–5/5 受惠強度)

#### [[8043]] 蜜望實 — 受惠強度 5/5

- 主力代理 [[Taiyo Yuden]] (太陽誘電) MLCC，AI server 已占營收 40% ([EBC](https://fnc.ebc.net.tw/fncnews/stock/203276))。
- [[Taiyo Yuden]] 已宣告 2026/5/1 起 MLCC 漲價 ([Yahoo Stock](https://tw.stock.yahoo.com/news/%E5%A4%AA%E9%99%BD%E8%AA%98%E9%9B%BB%E5%96%8A%E6%BC%B2-%E4%BB%A3%E7%90%86%E5%95%86%E8%9C%9C%E6%9C%9B%E5%AF%A6%E5%B1%95%E6%9C%9B%E6%AD%A3%E5%90%91-013900707.html))，蜜望實直接受惠。
- 股價: 2026/5/29 收 141.00 (+9.73%) ([Fugle](https://blog.fugle.tw/earnings-call-8043-2025-12-24/))。
- 2026 Q1 每股淨值 35.12，PB 3.72× ([StatementDog](https://statementdog.com/analysis/8043/nav))。
- **唯一風險**: PB 已偏高，若 [[Murata]] 釋出 008004 產能擠壓 [[Taiyo Yuden]] ASP → 代理 inventory loss。

#### [[3090]] 日電貿 — 受惠強度 4.5/5

- 通路平台型代理，MLCC + 鉭電容 + 鋁電解雙料受惠。
- 2026/4 月營收 18.43 億 (+28.1% YoY) 創高，1–4 月累積 63.36 億 (+21.0% YoY)，AI server 拉貨主推 ([Sinotrade](https://www.sinotrade.com.tw/richclub/hotstock/%E6%97%A5%E9%9B%BB%E8%B2%BF-3090--AI%E4%BC%BA%E6%9C%8D%E5%99%A8%E9%9B%BB%E6%BA%90%E5%8D%87%E7%B4%9A%E6%8B%89%E7%88%86MLCC%E4%BA%A4%E6%9C%9F-%E9%80%9A%E8%B7%AF%E5%95%86%E8%A7%92%E8%89%B2%E6%AD%A3%E8%A2%AB%E9%87%8D%E6%96%B0%E5%AE%9A%E7%BE%A9-6a0d04b211fc24195f3ae7a3))。
- 股價: 2026/5/29 收 229.0 (+9.83%)，近 5 日 +42.77%，被列處置股 5/27–6/9 ([CMoney](https://cmnews.com.tw/article/cmoneyaicurator-90cf4975-5979-11f1-9bdb-c96c3424ad86))。
- **總經理公開預警**: AI passive 缺貨延續至 2027，HKD/長型鋁電容/混合鋁電容交期從 1.5–2 月拉長到 3–4 月。
- **風險**: 處置股期間流動性差；漲幅已大。

### Tier 2: 上游材料端 (3/5 受惠強度)

#### [[6173]] 信昌電 — 受惠強度 3.5/5

- **垂直整合** 從陶瓷粉 → 設備 → MLCC + chip resistor ([CMoney](https://www.cmoney.tw/forum/article/176173635))。
- 主力是 **高壓高容 MLCC**，**不是 008004 微小化**。
- 2026 Q1 毛利率 28.4% (+6.1pp QoQ)、高壓特殊品交期拉長至 16 週、AI 營收占比目標突破 10% ([UAnalyze](https://uanalyze.com.tw/articles/3605251570))。
- 投資 11.6 億建台南柳營陶瓷粉新廠，2027 Q3 投產 ([NextApple](https://news.nextapple.com/finance/20260515/DF16832A7593137D8E64886E4D16889C))。
- **008004 受惠機制**: 透過供應陶瓷粉給日韓廠 (尚未驗證但合理)。**不是純 008004 標的**。

#### [[4760]] 勤凱 — 受惠強度 3/5

- 90% 營收來自被動元件導電膠 (silver paste + copper paste)，已切入日廠 (合理推測為 [[Taiyo Yuden]] / [[Murata]] 代工)。
- 008004 微小化需要更細粒度的銀/銅膠 → 若取得認證為 nontrivial alpha。
- **驗證缺口**: 未找到 4760 直接揭露 008004 paste 認證或量產的公告。

### Tier 3: 中游製造 (0–1/5 受惠強度)

#### [[2327]] 國巨 — 008004 受惠強度 **0/5** (但 commodity & 高壓 MLCC alpha 強)

- **明確證據**: 「008004 由 Murata 獨佔，台廠 1–2 世代落後」([Vocus 被動元件研究](https://vocus.cc/article/6a0b27bafd897800010b06e7))。
- 2327 的 alpha 來自:
  (a) [[KEMET]] 併購後鉭電容市占 50%+
  (b) MLCC 整體漲價週期 (commodity)
  (c) 高壓高容 MLCC 切入 AI server power supply
  — **跟 008004 沒關係**。
- 5/21 收 623 元、6M +194.7%、處置股關禁閉 ([Today](https://www.businesstoday.com.tw/article/category/183008/post/202605210037/))。
- **這是估值/題材股**，把它當「008004 受惠」會嚴重誤判。

#### [[2492]] 華新科 — 008004 受惠強度 **0/5**

- 跟 2327 同一邏輯: 高壓高容 MLCC + commodity 漲價，**沒有 008004**。
- 自家策略文字明確: 「精準突破、爭取中高階轉單 + 銅電極自有專利」 → 是 [[Murata]] 標準品的擠出受惠，不是微小化突破。
- 2025 全年 net income -23% YoY 但股價噴出 → 純估值/題材推升。
- 5/29 股價 394.0 元 ([StatementDog](https://statementdog.com/analysis/2492))，6M +173.6%、連 4 根漲停 5/20/21/22/25。

### 強度 ranking 結論

```
直接 008004 alpha:    8043 ≥ 3090
間接 008004 alpha:    6173 > 4760
非 008004 alpha:      2327 ≈ 2492 (受 commodity / 高壓 MLCC / 漲價週期推升)
```

**用戶初步假設「2327/2492 可能完全不受惠 008004」獲得驗證。**

---

## 市場誤判風險: 漲價 narrative vs 008004 切入

### 兩件不同的事

| 主題 | 邏輯 | 受惠標的 |
|---|---|---|
| **008004 微小化 narrative** | Murata 獨佔 → 缺貨 → ASP↑ → 代理槓桿 | 8043, 3090 |
| **MLCC 整體漲價週期** | 高階產能被 AI 抽走 → consumer-grade 缺貨 → 漲價 | 2327, 2492, 6173, 2327 (commodity rebound) |
| **AI 高壓高容 MLCC** | NVIDIA Rubin 機櫃需 ≥10μF 低 ESR 高壓品 | 2327, 2492, 6173 (二線受惠) |

### 市場 narrative 混淆現況

- 媒體與散戶把「2327 2492 漲停 + Murata 漲價」連結到「台廠切入 008004」，這是**錯誤連結**。
- 真實機制: [[Murata]] / [[Taiyo Yuden]] / [[SEMCO]] 把產能搬去做 AI server 高階 → 消費級 0402 / 0201 留出空間給台廠 → 台廠漲價但**並未進入 008004 微小化**。
- 「世代落差 1–2 代」要追上需要至少 3–5 年的薄層化、電極材料與燒結工藝突破，這不是 1–2 個 capex cycle 可以解決。

### 投資意涵

- 把 2327 / 2492 當作 **「commodity MLCC 漲價週期 + AI 高壓 MLCC」標的** → 正確；當作 **「008004 受惠」** → 錯誤。
- 008004 純粹 exposure 只能透過 [[8043]] / [[3090]] 表達。

---

## ASP cliff 下行風險 (005003 next-gen 衝擊)

### 005003 timeline 推測

- [[Murata]] 2024 年 IR 已暗示 sub-008004 (即 005003, 0.125×0.0625mm) 研發中。
- 業界一般週期 **3–4 年/代** (01005→008004 從 2014→2019)，推估 **005003 量產 2026 末–2027 H1**。
- 公開資料目前**未直接證實 Murata 005003 量產時間**，這是 Open Question。

### ASP cliff 機制

1. [[Murata]] 推出 005003 → 旗艦手機 (iPhone 20、Galaxy S28) 開始用 005003 取代 008004 部分位置。
2. [[Murata]] / [[SEMCO]] / [[Taiyo Yuden]] 008004 產能逐步釋出 → 008004 由獨佔轉向多供應商 → **ASP 跌 30–50%**。
3. [[Taiyo Yuden]] 把過剩 008004 庫存清給代理商 → [[8043]] 出現 **inventory loss + GP margin 急縮**。
4. AI server 因為已大量設計鎖住 008004，可能仍能維持一段需求，但 ASP 一旦解封即 reset。

### 對 8043 / 3090 的 cliff risk timing

- 2026 H2 – 2027 H1: 安全期，008004 仍處嚴重缺貨 (Murata 交期 26–40 週)。
- 2027 H2 – 2028: cliff window。一旦 [[Murata]] 005003 量產確認 → 代理通路估值 derate (PB 3.7→ <2)。
- **trading 策略**: 持有 [[8043]] / [[3090]] 至 [[Murata]] 005003 announcement → 第一次官方確認量產時點即為退場訊號。

### Open question

需要追蹤的 trigger:
- [[Murata]] 季度 IR 投影片是否首次出現 "005003" 或 "0125N" 量產時程
- [[Apple]] iPhone 19/20 BOM 是否導入 005003
- [[Taiyo Yuden]] 是否跟進開發 005003 (如不跟進 → 8043 更早暴露 cliff)

---

## Pair trade 思路: LONG 8043 vs SHORT 2492 可行性檢視

### 用戶提出的命題

> "LONG 8043 / SHORT 2492 pair trade 是否合理?"

### 我的結論: **方向對、但對立面選錯**

| 維度 | LONG 8043 / SHORT 2492 | LONG 8043 / SHORT 2327 | LONG 8043 only |
|---|---|---|---|
| 表達 008004 落差 | 中 (2492 也沒 008004 但沒漲到極端估值) | **強 (2327 處置股 PER 65×+ + 0 008004 exposure)** | 弱 (不 hedge market beta) |
| 對沖 MLCC 週期 beta | 弱 (兩檔都吃漲價週期) | 弱 (2327 commodity beta 更高) | 0 |
| 對沖 AI server beta | 中 (2492 跟 AI 漲價) | 中 (2327 跟 AI 漲價) | 0 |
| 流動性 | 中 (8043 8M cap 偏小; 2492 大) | **2327 是 mega cap、處置股交易受限** | OK |
| 估值極端度 (catalyst for short) | 2492 PB ~3.5× 偏高 | **2327 PB ~5×、PER 65×、處置股 = catalyst** | N/A |
| 期限 (1Y view) | 弱 (兩檔都漲) | 中 (處置股鬆綁可能 catalyst 反向) | 強 (純做多 008004) |

### 為什麼 SHORT 2492 不是 clean play

1. **2492 跟 8043 同樣吃 MLCC 漲價週期** → β 高度同向，pair 沒有真正 hedge。
2. **2492 6M +173.6% 是 commodity + 估值修復** → 跟 008004 narrative 沒有正反關係。
3. **2492 net income -23% YoY 漲不停** = 估值題材股，short 容易被軋。

### 真正乾淨的 pair (建議)

#### Option A: LONG 8043 / SHORT 2327 (穩健，估值/處置股 catalyst)

- 8043 = 008004 + AI server passive 純多
- 2327 = 處置股 + PER 65× + 0 008004 exposure → catalyst 包括處置股期間結束、Q2 法說會驗證指引、commodity MLCC 漲價放緩。
- 比 8043/2492 更乾淨表達「Murata 獨佔 vs 台廠落後」。

#### Option B: LONG basket {8043 + 3090 + 6173} 純 long (建議首選)

- 8043 + 3090 = 008004 + AI passive 通路
- 6173 = 高壓 MLCC + 陶瓷粉上游 (Rubin Vera 受惠)
- 加上低權重 [[4760]] 勤凱 作為 paste 上游選擇權
- 等權配置 25%/25%/25%/25%，6 個月持有
- 退場訊號: Murata 005003 量產確認

#### Option C: 對 2327 處置股做 short straddle / collar 結構 (進階)

- 不裸 short，買 put / sell call 對沖
- 適合對波動率有 view 的玩家

### 風險評估表

| 風險 | 概率 | 衝擊 | 緩解 |
|---|---|---|---|
| Murata 005003 提前量產 (<2027 H1) | 中 | 高 (ASP cliff) | 持續監控 Murata IR + iPhone teardown |
| 8043 處置股或法說會 disappoint | 中 | 中 | 分批進場、控制單支倉位 ≤ 5% |
| TW 廠真的切入 008004 (反向風險) | 低 | 中 (削弱 8043 alpha) | 監控 2327/2492 法說會關鍵字 |
| AI server demand 突然冷卻 | 低 | 高 (整 basket) | 觀察 GB300 / Rubin 出貨節奏 |
| 台幣升值/匯損 | 中 | 中 (代理商 USD 採購) | 觀察新台幣兌美元、日圓 |

### 投資 takeaway 一句話

> **「LONG 8043 + 3090 basket 是純 008004 narrative 的最佳表達；2327 / 2492 跟 008004 沒關係，只是被市場錯誤 lumping。SHORT 2327 比 SHORT 2492 更乾淨。」**

---

## Open questions

1. **Murata 005003 量產時間**: 公開資料未直接驗證。需要追蹤 Murata 2026 H2 IR、CEATEC 展會、Murata 京都總部新聞稿。
2. **8043 真實 008004 SKU 出貨占比**: 8043 揭露 AI server 占 40% 營收，但**未拆分 008004 占代理 SKU 比例**。法說會需 follow-up。
3. **4760 勤凱 paste 是否已認證 008004 規格**: 公開資料只有「切入日廠」未驗證到 008004。需查公司投資人簡報。
4. **6173 信昌電陶瓷粉是否供應 Murata / Taiyo Yuden 008004 級別**: 信昌電法說透露切入「韓廠高階 MLCC」但 008004 級別粒徑 (<100nm) 未驗證。
5. **iPhone 17 Pro 真實 008004 顆數**: 業界估計 160–250 但公開 teardown 未拆 BOM. TechInsights 完整報告需付費購買，本文用業界 proxy。
6. **Vera Rubin 008004 BOM**: $4,300/rack 是總 MLCC value，008004 占比目前用 5–10% 估算，需要 ODM 法說會或 BOM leaker 驗證。

---

## Sources

### 上游/中游 MLCC 廠商
- [被動元件 2027–2028 中長期深度評估 (Vocus)](https://vocus.cc/article/6a0b27bafd897800010b06e7) — 008004 由 Murata 獨佔、台廠 1–2 世代落後
- [國巨 2026/4/30 法說會 (Fugle)](https://blog.fugle.tw/post/earnings-call-2327-2026-04-30)
- [國巨 2327 股價狂飆 (今周刊)](https://www.businesstoday.com.tw/article/category/183008/post/202605210037/)
- [華新科 2492 StatementDog](https://statementdog.com/analysis/2492)
- [信昌電 6173 Q1 毛利率 28.4% (UAnalyze)](https://uanalyze.com.tw/articles/3605251570)
- [信昌電 11.6 億擴產 (NextApple)](https://news.nextapple.com/finance/20260515/DF16832A7593137D8E64886E4D16889C)

### 代理通路
- [蜜望實 8043 2026 展望 (EBC)](https://fnc.ebc.net.tw/fncnews/stock/203276)
- [蜜望實 8043 法說會 (Fugle)](https://blog.fugle.tw/earnings-call-8043-2025-12-24/)
- [蜜望實 8043 PB (StatementDog)](https://statementdog.com/analysis/8043/nav)
- [太陽誘電喊漲 蜜望實受惠 (Yahoo Stock)](https://tw.stock.yahoo.com/news/%E5%A4%AA%E9%99%BD%E8%AA%98%E9%9B%BB%E5%96%8A%E6%BC%B2-%E4%BB%A3%E7%90%86%E5%95%86%E8%9C%9C%E6%9C%9B%E5%AF%A6%E5%B1%95%E6%9C%9B%E6%AD%A3%E5%90%91-013900707.html)
- [日電貿 3090 法說 (鉅亨)](https://news.cnyes.com/news/id/6463791)
- [日電貿 3090 通路角色 (Sinotrade)](https://www.sinotrade.com.tw/richclub/hotstock/%E6%97%A5%E9%9B%BB%E8%B2%BF-3090--AI%E4%BC%BA%E6%9C%8D%E5%99%A8%E9%9B%BB%E6%BA%90%E5%8D%87%E7%B4%9A%E6%8B%89%E7%88%86MLCC%E4%BA%A4%E6%9C%9F-%E9%80%9A%E8%B7%AF%E5%95%86%E8%A7%92%E8%89%B2%E6%AD%A3%E8%A2%AB%E9%87%8D%E6%96%B0%E5%AE%9A%E7%BE%A9-6a0d04b211fc24195f3ae7a3)
- [日電貿 3090 處置股 (CMoney)](https://cmnews.com.tw/article/cmoneyaicurator-90cf4975-5979-11f1-9bdb-c96c3424ad86)

### AI Server BOM
- [GB300 MLCC 44 萬顆 (Barron)](https://www.barronmlcc.com/high-capacity-mlcc-for-ai-servers--data-centers-2026-selection--supply-guide.html)
- [Vera Rubin BOM +182% MLCC (BigGo via Morgan Stanley)](https://finance.biggo.com/news/MrEuTZ4BX0tZvRTv67Pr)
- [Vera Rubin PCB+MLCC+ABF 三飆 (Bitget News)](https://www.bitget.com/news/detail/12560605422208)
- [Vera Rubin Pod 七晶片 (NVIDIA Developer)](https://developer.nvidia.com/blog/nvidia-vera-rubin-pod-seven-chips-five-rack-scale-systems-one-ai-supercomputer/)
- [GB300 NVL72 power shelf (NVIDIA Tech Blog)](https://developer.nvidia.com/blog/how-new-gb300-nvl72-features-provide-steady-power-for-ai/)

### 手機 BOM
- [iPhone 17 Pro Max TechInsights teardown](https://www.techinsights.com/blog/apple-iphone-17-pro-max-a3257-deep-dive-teardown)
- [iPhone 17 Pro iFixit](https://www.ifixit.com/Device/iPhone_17_Pro_Max)
- [iPhone 17 Pro 9to5Mac teardown](https://9to5mac.com/2025/09/23/iphone-17-pro-teardown-reveals-vapor-chamber-internals-scratchgate-details-more/)
- [Murata MLCC for 5G Smartphones Part 1](https://article.murata.com/en-eu/article/mlcc-for-5g-smartphone-1)
- [Murata 008004 0.1uF 世界首發 (Passive Components EU)](https://passive-components.eu/murata-develops-the-worlds-first-0-1uf-multilayer-ceramic-capacitor-in-008004-size/)

### ODM 與 demand 驗證
- [緯穎示警 AI 缺貨延至 2028 (鉅亨)](https://news.cnyes.com/news/id/6472429)
- [2026 AI 伺服器完整指南 (E大成長股)](https://efrontrade.com/2026/02/ai-server-investment-complete-guide-2026.html)

### MLCC 廠商整體
- [Taiyo Yuden 漲價 Murata 領頭 (DigiTimes 2026/4/17)](https://www.digitimes.com/news/a20260417PD209/taiyo-yuden-mlcc-murata-electronic-components-price.html)
- [Murata 自動車 7 款新品 (Engineering.com)](https://www.engineering.com/murata-begins-mass-production-of-high-capacitance-auto-mlccs/)
- [SEMCO 3Q25 結果 雙位數 2026 成長 (DigiTimes)](https://www.digitimes.com/news/a20251031PD222/semco-2026-growth-mlcc-2025.html)
- [Electronic Component Shortage 2026 (Findchips)](https://blog.findchips.com/electronic-component-shortage-2026-memory-mlcc-lm324-sourcing/)

---

**Unit 6 of 6 complete.** 推翻「2327/2492 = 008004 受惠」誤判、確認 8043/3090 為純 008004 alpha、提出 LONG basket 比 LONG/SHORT pair 更優的結論。
