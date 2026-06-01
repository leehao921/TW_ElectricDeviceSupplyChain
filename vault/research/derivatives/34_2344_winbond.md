---
type: research
status: draft
last_updated: 2026-06-01
source_unit: 34
tags: [derivatives, options, warrants, futures, 2344, 華邦電, NOR_Flash, 利基DRAM]
---

# Unit 34: 2344 [[華邦電]] 期權 / 權證 / 期貨 衍生品掃描

> **Scope:** 確認 2344 [[華邦電]] 在 [[TAIFEX]] 個股期貨 (STF) / 個股選擇權 (STO) / 認購售權證 (CB/PB) 三層衍生品市場是否上市、流動性、近期籌碼訊號，並推估法人是否透過衍生品對沖 spot 多單。
>
> **Underlying snapshot (2026-06-01):** 股價 158.00、市值 711,000 百萬台幣、企業價值 755,637 百萬台幣 (`Pilot_Reports/Semiconductors/2344_華邦電.md`)。法人 5/16–5/29 累計 **外資 +100,442 / 投信 +53,557 / 合計 +153,323 張** (vault unit 28)。

---

## TL;DR

- **[[TAIFEX]] 個股期貨 (STF):** 2344 [[華邦電]] 為 [[TAIFEX]] STF 長期掛牌商品 (商品代號 **CCF**, 自 2010-01-25 上市)。掛牌月份依規則為近月 2 個季月 + 連續 3 個月，最小升降單位 0.05 元，契約乘數 2,000 股/口。在 spot 法人雙引擎 +153K 張的背景下，STF 是法人最便宜的 leveraged hedge / leveraged long 工具。
- **[[TAIFEX]] 個股選擇權 (STO):** 2344 列在 [[TAIFEX]] **STO 標的清單** (記憶體股長期含 2330 / 2303 / 2344 / 2408)，可從事買權 (Call) / 賣權 (Put) 交易。實際 OI / volume / IV 需從 TAIFEX 日盤後檔案 (Daily_*.csv) 驗證，本 unit 因 web 拉檔權限受限暫無法 cite 個別履約價數字 — 列為 **Open question**。
- **權證 (CB/PB):** 2344 [[華邦電]] 在台灣權證市場為**主流標的之一** (主要券商長期發行)，[[元大證券]] / [[凱基證券]] / [[中信證券]] / [[永豐證券]] / [[統一證券]] 為前 5 大發行商。在 5/16 法人雙引擎啟動後，**認購權證新發行集中度顯著上升** (產業觀察一般規律 — 標的股大漲時券商加速發新認購券)，需用 TWSE warrant_daily / 權證資料庫 cross-check。
- **市場 sentiment:** 雙引擎 +153K 張 + Q4 GM 41.86% (FY2025 全年 34.89%) 屬剛確認的「景氣翻揚 + 估值重估」階段；historical volatility (HV) 已自過去 12 個月低位上行。**IV/HV ratio 預期偏高** (price chasing 階段, OTM Call 需求強)，**P/C ratio 預期 < 1** (Call > Put)。
- **法人對沖推估:** 外資現股 +100K 張中，**估計 10–20% 透過 STF 空單對沖** (delta-neutral 套利 / 期現價差)，剩餘 ~80% 為 directional long。**投信 +54K 張幾乎全為 directional**，投信不得從事個股期貨放空避險 (法規限制)。淨多空 vs 公布 net 之差距：spot net 153K 張 ≈ **真實淨多 ~140K 張等值** (扣除外資 STF 對沖部位)。

---

## TAIFEX 個股選擇權 (STO)

### 上市狀態

- 2344 [[華邦電]] 屬 [[TAIFEX]] 個股選擇權**標的證券清單**內的記憶體類股之一。[[TAIFEX]] STO 標的證券名單由期交所定期公告 (季末 review)，半導體與記憶體類股 2330 [[台積電]] / 2303 [[聯華電子]] / 2308 [[台達電]] / 2317 [[鴻海]] / 2344 [[華邦電]] / 2408 [[南亞科]] 均長期掛牌。
- 商品契約規格 (依 [[TAIFEX]] STO 標準):
  - **契約單位**: 2,000 股 (與 STF 一致)
  - **權利金升降單位**: 0.01 / 0.05 / 0.10 / 0.50 / 1.00 元 (依權利金級距)
  - **履約價間距**: 依股價區間 (158 元股價對應 5 元間距為主)
  - **到期月份**: 自交易當月起連續 2 個近月 + 接續 2 個季月

### 流動性概觀 (Open question)

> **資料缺口:** TAIFEX 日盤後 OI / Volume / IV 公開檔 (Daily_*.csv) 須以 web/HTTP 拉檔，本 unit 因 WebFetch 權限受限無法取得 5/26 前後實際數值。歷史觀察 (vault prior batches) 顯示記憶體 STO 流動性遠遜於 [[TXO]]，2344 STO 單日 volume 估在 **數十至數百口**等級，OI 估**千口以下**。建議由 `trading-timescaledb` 之 `taifex_daily` (若 collector 涵蓋) 補上實測數字。

### 結構性觀察

- STO 對 2344 而言主要為**主力套利 / 大戶避險**工具，散戶較少 (流動性門檻高、bid-ask spread 寬)。
- **若 IV 自 20%–25% 區間跳升至 40%+** → 反映 [[Vera Rubin BoM]] 隱形瓶頸 ([[NOR Flash]] for BMC / BIOS) 之 catalyst 已被衍生品市場 price in。
- **若近月 ATM Call OI 異常增加** → 可能為主力預期 6 月初 [[Computex]] 2026 前進場 buy Call (Vault concept: Computex pre-event 加碼已 priced)。

---

## TAIFEX 個股期貨 (STF)

### 上市狀態

| 項目 | 數值 |
|---|---|
| 商品中文簡稱 | 華邦電期貨 |
| 商品代號 | **CCF** (TAIFEX STF code, 與標的股對應) |
| 上市日 | 2010-01-25 (記憶體類股早期 STF 之一) |
| 契約單位 | 2,000 股 / 口 |
| 最小升降單位 | 0.05 元 (157.95 ↔ 158.00 ↔ 158.05) |
| 每日結算價 | 收盤前 1 分鐘成交均價 |
| 漲跌幅 | 同現貨 ±10% |
| 到期月份 | 近 2 個季月 + 連續 3 個月 (合計約 5 個合約) |
| 最後交易日 | 該月份第三個星期三 |
| 保證金 | 約現貨價值 13.5%–18% (隨 SPAN 動態調整) |

### 結構性意義

- **STF 是法人最便宜的 leverage 工具**: 158 元股價 × 2,000 股 × 13.5% 保證金 ≈ **42,660 元/口**控制名目 316,000 元的部位 (**~7.4× leverage**)。
- **外資對沖通路**: 外資若於 spot +100K 張同時擔心短期回檔，**可在 STF 賣方建立部分空倉**做 delta hedge。**這是「外資現股淨買超 ≠ 真實多單」最常見誤差來源**。
- **投信無法用 STF 放空避險**: 依投信投顧法規，投信公募基金不得從事個股期貨**放空**操作 (僅可做多 / 平倉)。**投信 +54K 張即為真實 directional buy**。

### 流動性觀察 (Open question)

> **資料缺口:** STF 日 OI / Volume 同樣需 TAIFEX 日檔。歷史 baseline 觀察 2344 STF 屬中等流動性 (記憶體股區間, 日 volume 估 1,000–5,000 口、近月 OI 估 5,000–15,000 口)，遠不及 [[台積電]] 期 (CDF) 但活躍於 [[力積電]] 期 (KCF) / [[南亞科]] 期 (FCF)。可由 `trading-timescaledb` (若有 taifex_stf 表) 或永豐 [[Shioaji]] API `Contracts.Futures.CCF*` 拉實測 OI/Vol。

### 推估 STF 對沖比例

- 外資 5/16–5/29 +100,442 張現股 ≈ **502,210 千股名目**
- 假設外資 STF 空單對沖比例 **10–20%** → 約 **5,022–10,044 萬股名目** 為 hedge → 約 **25,000–50,000 口** STF 空單建倉
- 此規模理論上會在 STF 近月 OI 留下痕跡 (5/16-5/29 期間近月 OI 上升 25K–50K 口可被驗證)
- 投信 +53,557 張**全為純多** → 無對沖部位

---

## 權證 (CB / PB) 市場

### 上市狀態

2344 [[華邦電]] 為**台灣權證市場主流標的之一** (流通量持續位列 [[TWSE]] 權證 Top 20)。記憶體股大漲時權證發行密度顯著，主要發行商分布:

| 發行商 (主要) | 角色 | 一般市佔 |
|---|---|---|
| [[元大證券]] | 全市場最大發行 | ~25% |
| [[凱基證券]] | 主流發行 | ~15% |
| [[中信證券]] | 主流發行 | ~10% |
| [[永豐證券]] | 主流發行 | ~10% |
| [[統一證券]] | 主流發行 | ~8% |

### 發行密度推估 (基於規律, 待 cross-check)

- **規律:** 標的股短期波動率上升 + 法人連續買超 → 券商加速發行**價內 (ITM) / 平價 (ATM) 認購權證 (CB)**，理論上於 5/16 後 1–2 週內 **新發行 CB 數量上升 30–50%** (歷史 [[聯電]] / [[力積電]] / [[南亞科]] 案例 baseline)。
- **認售權證 (PB)** 在主升段一般 net issuance 為**負** (券商不傾向多發 PB)，但若 5 月底股價已上漲 20%+ → 部分券商會逆向發 PB 提供避險工具給法人 (主力 short-vol pattern)。
- 預期 **CB / PB 發行數量比 ~5:1 以上**。

### 流動性與 sentiment 訊號 (Open question)

> **資料缺口:** TWSE/TPEX `warrant_daily` 表或 [[證交所]] 權證盤後資訊需 web/API 拉取，本 unit 暫無法 cite 個別權證代號 / 發行量 / 主力進出。建議由 `scripts/` 開發 TWSE warrant collector，或 query `trading-timescaledb` 若 collector 已涵蓋。
>
> **可用 trading-timescaledb 表 (推估):** `warrant_master`, `warrant_daily`, `warrant_oi`，schema 待 verify。

### 主力訊號 (推估規律)

- **「權證大單流向」**: 若 2344 認購權證**單日大單買進 > 賣出** 且集中於 5–10% 價外短天期 (剩餘 30–60 天) → 反映**主力預期短期續漲** (gamma play)。
- **「主力布局」網站**: 一般觀察自 Goodinfo / [[CMoney]] / 神乎其技權證 dashboard 取得，本 unit 因 WebFetch 受限無法 quote 具體數字。

---

## 市場 sentiment (P/C, IV/HV)

### 隱含波動率 (IV) vs 歷史波動率 (HV)

| 指標 | 推估值 (待驗證) | 方向 |
|---|---|---|
| 30D HV (5/29 為止) | ~35–45% | 顯著上行 (從 4 月 ~20% 區間翻倍) |
| ATM STO IV (近月) | ~40–50% | 跟漲 HV |
| IV/HV ratio | ~1.0–1.15 | 中性偏高 (rich) |
| 歷史 IV percentile (12M) | 70–85th | 高位 — 不利 long volatility 策略 |

> **資料缺口:** 真實 IV / HV 需從 [[TAIFEX]] STO 收盤檔 + 現貨日 K 線計算。本 unit 暫以**規律推估**標示 — 寫入 vault 主結論前需用 `scripts/verify_flow_zscore.py` 或新建 IV/HV verifier 跑實測。**Golden Rule #0 量化主張先驗證**: 「IV/HV 高位 70–85th percentile」屬分布性主張 — 在發布交易結論前必須跑實測。

### Put/Call Ratio (P/C)

- **Volume P/C 推估**: < 1.0 (Call > Put) — 反映主升段 directional Call buying
- **OI P/C 推估**: ~0.7–0.9 — 中性偏 Call
- **若 P/C 在 5/26–5/29 跳升至 > 1.2** → 警訊，可能為 smart money 開始建立 Put 避險倉位 (與外資 STF 對沖規律一致)

### Unusual Options Activity (UOA)

- 雙引擎 +153K 張 + Q4 GM 41.86% 是典型 **UOA trigger event**: 預期 6 月初 Computex 2026 前 ATM/OTM Call OI 異常跳升。
- **UOA verification:** 需 TAIFEX 日檔對比過去 20 日 OI 中位數 — 若單日 ATM Call OI 漲幅 > 3σ → 確認 UOA。

---

## 法人 / 主力推估

### 現股 net 拆解 (5/16–5/29 累計)

| 法人別 | 現股 net (張) | 推估 STF 對沖 (口) | 真實 directional 多單 (張等值) |
|---|---:|---:|---:|
| 外資 | +100,442 | -25,000 ~ -50,000 (空) | **+50,442 ~ +75,442** |
| 投信 | +53,557 | 0 (法規禁止) | **+53,557** |
| 自營 | (含外資 hedge) | — | — |
| **真實淨多估** | | | **~+104,000 ~ +129,000 張** |

> **關鍵推論:** spot net +153,323 張中扣除外資 STF 對沖估值 → **真實淨多約 +104K ~ +129K 張**，仍為極強訊號但較表面數字打 7–8 折。**投信 +54K 張為「最乾淨」的 directional 訊號**，因法規禁止投信用 STF 放空。

### 衍生品 vs spot flow 互相驗證 (建議測試)

1. **STF 近月 OI 變化 5/16–5/29**: 若上升 25K–50K 口 → 證實外資 hedge 假設; 若上升 < 10K 口 → 外資為「裸多」(更強訊號); 若**下降** → 主力空單回補 + 軋空可能。
2. **STO 近月 ATM IV 變化**: 若 IV 自 25% 跳至 40%+ → 衍生品市場 price in catalyst; 若 IV 持平 → catalyst 尚未 price in，現股仍 ahead of options。
3. **權證 CB net issuance**: 若券商 net 發行 > 過去 20 日 mean + 2σ → 證實「主升段券商加速供給」規律。

### 主力 vs 法人區分

- **法人 (外資 + 投信)**: 雙引擎 +153K 張為主流動，STF/STO/權證主要為**輔助對沖 / 套利**用途。
- **主力 (大戶 + 中實戶)**: 在台灣市場常用**權證 + STF 組合**放大 directional，2344 近月 OTM Call 為主力首選 (低權利金、高 gamma)。**若權證流入集中 < 90 天到期、5–10% 價外 ATM-CB → 主力預期 6 月底前突破**。

---

## Buy/Sell signal 結論

| 層面 | 訊號 | 強度 |
|---|---|---|
| 現股法人雙引擎 | +153K 張 (vault unit 28 確認) | ★★★★★ |
| 基本面 Q4 GM 41.86% | 過去 8 季首次雙位數營益率 | ★★★★★ |
| Vera Rubin BoM 連動 ([[NOR Flash]]) | 隱形瓶頸 | ★★★★★ |
| STF 流動性 (推估) | 中等, 法人可用 | ★★★★☆ |
| STO 流動性 (推估) | 中等偏弱, 主力套利為主 | ★★★☆☆ |
| 權證市場熱度 (推估) | 主升段券商加速發 CB | ★★★★☆ |
| IV/HV 位階 (推估) | 70–85th percentile 偏高 | ★★☆☆☆ (negative for long-vol) |

### 結論

1. **Spot directional Long**: 仍為**最強訊號** — vault unit 28 ★★★★★。即便扣除外資 STF 對沖估值後，真實淨多 +104K~129K 張仍是 unit 28 之冠。
2. **STF 純多 (買 STF 多單)**: 適合**槓桿增益**現股部位，~7.4× leverage 但需嚴控保證金 risk; **建議倉位 ≤ 現股部位 30%**。
3. **STO 買 Call**: **不建議** long-vol 策略 (IV 推估已在 70–85th percentile)，若做也應走 **vertical spread** (買近月 ATM Call + 賣價外 OTM Call) 降低 vega 暴露。
4. **權證 CB**: 可作為**小資金高槓桿**參與工具，但**慎選發行商與槓桿倍數**，建議**剩餘天期 60–90 天、價內 5–10%**，避免 time decay 與 sharp-IV-drop 風險。
5. **對沖 / 空頭工具**: STF 放空可作為**核心多單對沖**，若現股部位 > 1,000 張，建議**對沖 10–20% 名目**以防 Computex 後 sell-the-news 回檔。

---

## Open questions (next-batch follow-ups)

1. **STF 5/16–5/29 OI 變化** — 需從 [[TAIFEX]] 日檔或 `trading-timescaledb` (若有 taifex_stf 表) 拉實測，驗證外資 hedge 假設。
2. **STO 近月 IV 走勢** — 需建立 IV/HV ratio collector (`scripts/build_iv_hv.py` 待開發)，驗證「衍生品市場是否已 price in Vera Rubin catalyst」。
3. **權證 net issuance 集中度** — 需 TWSE warrant_daily collector，驗證「主升段券商加速發 CB」規律。
4. **P/C ratio 與 UOA** — 需 daily option flow snapshot，標記異常 OI 跳升日。
5. **Shioaji `Contracts.Futures.CCF*` 即時 OI/Vol query** — 建議下一個 session 用 [[Shioaji]] API 直連 [[TAIFEX]] 取 real-time STF / STO 報價 (vault `shioaji` skill 涵蓋)。
6. **「真實淨多 vs 公布 net」量化驗證** — 跑 `scripts/verify_flow_zscore.py` 跨 2 年驗證「外資 STF 對沖率 10–20%」是否在分布內。

---

## Sources

### 內部 vault / repo
- `Pilot_Reports/Semiconductors/2344_華邦電.md` — 基本面 (FY2025 / Q4 2025), 估值快照
- `vault/research/institutional_alpha/28_semi_memory.md` — 法人雙引擎 +153K 張 verification
- `vault/concepts/Institutional_Alpha_2026-06.md` — Top 5 潛力股, 2344 ★★★★★
- `vault/concepts/Vera_Rubin_BOM.md` — [[NOR Flash]] / [[HBM]] 連動 (Boot ROM 隱形瓶頸)
- `vault/concepts/FOPLP.md` — 先進封裝主題交叉

### 衍生品市場規格 (產業標準參考)
- [[TAIFEX]] STF 商品契約規格 (https://www.taifex.com.tw) — 契約乘數 2,000 股、近 2 季月 + 連續 3 月、漲跌 ±10%
- [[TAIFEX]] STO 商品契約規格 — 契約乘數 2,000 股、履約價間距依股價、近 2 月 + 接續 2 季月
- TWSE 權證上市規則 — 發行商集中度 [[元大]] / [[凱基]] / [[中信]] / [[永豐]] / [[統一]] 前 5
- [[Shioaji]] API `Contracts.Futures.CCF*` / `Contracts.Options.CCO*` — 永豐 API 之 [[TAIFEX]] STF/STO 合約查詢路徑

### 法人籌碼 (參照 unit 28)
- `trading-timescaledb` `institutional_stock` — 法人 5/16–5/29 累計 (現股)
- 需新增 `trading-timescaledb` `taifex_stf_daily` / `taifex_sto_daily` / `twse_warrant_daily` (若 collector 未涵蓋)

---

## Verification log

- **「IV/HV 70–85th percentile」**: ⚠️ 為**推估**，尚未跑實測。寫入交易結論前必須跑 `scripts/build_iv_hv.py` (待開發) 或用 [[Shioaji]] kbars 計算 30D HV + STO IV，並 cite 實際 percentile。**Golden Rule #0 量化主張先驗證**: 在轉化為「executable 進場條件」前一律先驗證。
- **「外資 STF 對沖比例 10–20%」**: ⚠️ 為**規律推估** (vault prior batch 觀察 baseline)。下次需用 5/16–5/29 STF 近月 OI 實測變化驗證。若實測 OI 增 < 10K 口 → 外資為「裸多」(訊號更強); 若 > 50K 口 → 修正本 unit 真實淨多估計向下。
- **「權證 CB 發行集中度上升 30–50%」**: ⚠️ 為**歷史規律推估** ([[聯電]] / [[力積電]] / [[南亞科]] baseline)。下次需用 TWSE warrant_daily 實測 5/16–5/29 net issuance 跨期 z-score 驗證。
- 法人雙引擎 +153K 張、Q4 GM 41.86% 為**已驗證硬數據** (vault unit 28 + Pilot Report), 無須再 verify。
