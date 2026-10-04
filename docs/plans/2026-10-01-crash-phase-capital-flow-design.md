# 大跌階段判別 + 資金流提醒 + 00406A 歸因追蹤 — 設計

**日期:** 2026-10-01 (初稿) · 2026-10-04 (審閱修訂) · **狀態:** 修訂版待用戶審閱
**範圍:** 全部只推播提醒, 不下單。B (TMF agent 兩階段行為) 由用戶在 nautilus 另一 session 設計, 本設計只提供它可讀的狀態介面。

## 背景與用戶決策

資金架構 (用戶 2026-10-01 定調, 2026-10-04 修訂):
- **TMF agent** — 主動報酬引擎; 大跌兩階段: ① 初跌破位減多/翻空+買 put → ② 恐慌回補空單、progressive-add 加碼多單 (B, 不在本範圍)
- **Shannon 核心** — 00891 / 黃金 00635U / 長榮 2603 / 華航 2610 = **60 / 20 / 10 / 10**, 權重偏離 ±5pt 才再平衡 (2026-10-04 用戶選定, 取代初稿的「回檔帶動用 25% 備用金」)
- **00406A** — 每月現金流; 除息日新錢買 1 張 (既有 div_buy) **且** 股利發放日全數再投入
- **agent 獲利** — 提領後投入 Shannon 核心中「低於目標權重最多」的資產

設計依據 (2026-10-01 ~ 10-04 實測):
- 「只在大跌時買」回測輸給定期定額 (00891 2021-26: IRR 36–41% vs 43.9%; 0050 2015-26: 20.7–22.7% vs 26.9%) — 錢閒置錯過上漲
- Shannon 回測 (2021/05-2026/10, ±5% 區間): 60/20/10/10 年化 26.3% / 波動 21% / MDD −38%, 惡魔溢酬 +3.3%/年; 單持 00891 為 28.9% / 27% / −45%。±5% 區間 5 年約 14 次再平衡, 70/30 版本的買點落在 2022-10-11 (−43%) 與 2025-04-09 (−31%) 兩次大底附近
- 2026 年長榮 vs 華航相關 0.40 → **0.01** (油價方向相反), 00891 vs 長榮 0.16, 00891 vs 黃金升至 0.35
- **期貨帳戶部位會是多空混合**: 2026-10-04 實測 TMFJ6 空 5 + TMFK6 多 2 (淨空 3, 跨月價差), 權益 24.3 萬 — 風險計算必須用淨部位、雙向壓力測試
- 選擇權指標 (vix_daily) 自 2026-05-27 起, 無法回測 2022/2024/2025 → 判別分兩層 (核心層可回測 / 確認層前向累積)
- `h:regime:context` 無 `break_state` 欄位 → A 自行計算破位
- 00406A 採掩護性買權 (名目 0–25%); 7/02–9/29 歸因: ETF −2.69% vs 持股籃子 −2.00% (差 −0.69pt), beta 0.98, 樣本 61 日

## 共用約定

- **交易日曆:** 讀 database repo `src/tmf/data/pipeline/tw_holidays.py` (TWSE 權威清單, `CALENDAR_VALID_UNTIL = 2026-12-31`), 以檔案路徑載入單一模組 (不 import `tmf` 套件)。**不用** My-TW `data/tw_market_holidays.txt` (只填了 2 天, 見文末附註)。日曆過期 → 訊息標 ⚠️「假日日曆過期」並照星期制運作
- **價格:** `institutional_stock.close_price` (00891 / 00635U / 2603 / 2610 / 00406A 均有, 至 2026-10-02)
- **推播:** `claude:inbox` (欄位格式照 bb_inbox_alert.py), Discord forwarder 自動轉發
- **state 檔:** tmp + rename 寫入
- **期貨帳戶:** `h:real_account:baseline` 的 `as_of` 判斷新鮮度 (**不要用 `updated_at`, 它停在 2026-06-24**)

## 元件 1 — 大跌階段判別 `scripts/crash_phase.py`

launchd `com.lulala.crash-phase` Mon-Fri **18:30** (margin-vix 18:10 寫入 vix_daily 之後); 休市日不執行。

**指標 (每日收盤):** `dd60` = 加權指數收盤 / 近 60 日最高收盤 − 1; `MA20`, `MA60`; `RV20` = 近 20 日日報酬年化標準差, `RV_med` = RV20 近 120 日中位數; `F5` = 全市場外資 5 日淨額 (`SUM(foreign_net × close_price)`)

**條件:**
- `BREAK` = dd60 ≤ −5% 且 收盤 < MA60
- `PANIC` = dd60 ≤ −10% 且 RV20 ≥ 1.5 × RV_med
- `CALM` = dd60 > −3% 且 收盤 ≥ MA60
- `EXHAUST` = 收盤 > MA20 且 F5 > 0

**轉換表 (每日依序檢查, 第一個成立者生效; 都不成立 → 維持原狀態):**

| 目前狀態 | 條件 | 轉到 |
|---|---|---|
| NORMAL | PANIC | P2_PANIC (允許跳過 P1: 單日重挫) |
| NORMAL | BREAK | P1_BREAK |
| P1_BREAK | PANIC | P2_PANIC |
| P1_BREAK | CALM | NORMAL (假破位, 計入假破位次數) |
| P2_PANIC | EXHAUST | RECOVERY |
| RECOVERY | PANIC 且 收盤創本輪新低 | P2_PANIC (二次探底) |
| RECOVERY | CALM | NORMAL |

- P1 無逾時: 只要沒回到 CALM 也沒到 PANIC 就維持 P1 (緩跌盤整屬 P1)
- RECOVERY 在 CALM 之前不回 P1 (回升途中的震盪不重新計破位)
- **確認層** (不阻擋轉換, 只顯示): P1 時 vix_w ≤ 32 且 wm_spread ≤ +2 → 「保護還便宜 ✅」; P2 時 wm_spread > +2 或 vix_w > 32 → 「恐慌確認 ✅」; 資料缺 → 「無資料」
- **輸出** Redis `h:agent:crash_phase` (B 的讀取介面): `phase`, `since`, `prev_phase`, `dd60`, `ma20`, `ma60`, `rv20`, `rv_med`, `f5`, `vix_w`, `wm_spread`, `confirm`, `low_since_p2`, `false_breaks`, `as_of`
- state `data/crash_phase_state.json`; **僅轉換時**推 inbox topic=`crash-phase`
- 資料源: `^TWII` 日收盤 (yfinance), 失敗 fallback `index_spot` 當日最後一筆

**回測 (實作前置, 校準門檻):** `scripts/crash_phase_backtest.py` 以 2021-05 起加權指數 + 00891 重播轉換表, 輸出 `analysis/crash_phase_backtest_<date>.md`:
- 每次進入 P2 的日期與 00891 後 20/60 日報酬; 每次 P1 的結局 (→P2 / 假破位) 與假破位次數
- **成功標準:** P2 進入後 00891 60 日報酬平均為正; 2022 空頭內 P2 首次觸發時, 00891 已跌超過該段最大跌幅的一半
- 不達標 → 調整門檻, 每次調整記錄在報告, 不靜默改

## 元件 2 — 資金流提醒 `scripts/capital_flow.py`

launchd `com.lulala.capital-flow` Mon-Fri **18:40**。推 inbox topic=`capital-flow`。

### (a) 期貨風險與提領

讀 `h:real_account:baseline` (`equity_twd`, `margin_used_twd`, `positions_json`, `as_of`)。

- **乘數表:** TMF 10、MXF (小台) 50、TXF (大台) 200 元/點; 代碼前綴比對。positions 內有不認得的代碼 (含選擇權) → 該行標「部位含無法估算商品」, 不給提領建議
- **淨名目** N = Σ(多單口數 − 空單口數) × 現價 × 乘數 (帶正負號); 總名目 G = Σ|口數| × 現價 × 乘數
- **雙向壓力測試:** loss_up = max(0, −N × 10%), loss_dn = max(0, N × 10%), worst = max(loss_up, loss_dn)
- **維持保證金** M = margin_used × 0.77 (TAIFEX 維持/原始比例近似, config 可調, 訊息標「近似」)
- **兩個距離** (淨名目為 0 時顯示「已對沖」):
  - 追繳距離 = (權益 − M) / |N|
  - 歸零距離 = 權益 / |N|
  - 方向標示: N > 0 → 「大盤跌 X%」; N < 0 → 「大盤漲 X%」
- **安全水位** = M + worst; **可提領** = 權益 − 安全水位
- **每月第一個交易日**: 可提領 ≥ 10,000 → 提醒提領, 並指定投入 Shannon 核心中低於目標最多的資產 (見 2b)
- **凱利槓桿警示 (每日):** 目前槓桿 = |N| / 權益; 保守凱利 = 0.10 / σ², σ = 加權指數近 60 日年化實現波動, 0.10 = 假設超額報酬 (config); 比值 > 1 → 「⚠️ 高於凱利」, > 2 → 「🚨 超過 2 倍凱利, 長期複利為負」。訊息註明「靜態估算, agent 動態調倉時僅供參考」
- 每日警示 (追繳距離 < 5% 或 槓桿 > 2 倍凱利) 同狀態只在首日與每週一重推
- `data/capital_flow_ledger.json` 手動記錄入金/出金 → 計算 agent 淨獲利 (equity_snapshots 分不出入金)
- baseline `as_of` 超過 1 天 → 標「期貨資料過期」, 不給提領建議

### (b) Shannon 核心再平衡

**核心帳本** `data/shannon_core.json` (手動維護, 與短線部位分開):
```json
{"targets": {"00891": 0.60, "00635U": 0.20, "2603": 0.10, "2610": 0.10},
 "band": 0.05,
 "holdings": {"00891": 14220, "00635U": 6000, "2603": 0, "2610": 0},
 "note": "核心部位只靠再平衡調整; 短線 2603/2610 部位仍由 position_triggers 管理, 不計入此處"}
```
- 每日計算各資產市值權重 w_i = 股數 × 收盤 / 核心總值
- **建倉期** (首次所有 |w_i − target_i| ≤ band 之前): 不建議賣出任何資產; 每次有新資金 (agent 提領、手動入金) 時, 提醒依「與目標的金額缺口」由大到小分配。訊息附各資產缺口金額。長榮 P/B 燈號若為 RED 則附註「估值高檔, 可分批」
- **維持期**: 任一 |w_i − target_i| > band → 推「🔄 再平衡」, 列出恢復目標權重的買賣清單 (股數取整, 零股可); 同一次偏離只推一次, 權重全部回到區間內後重新 arm
- 新資金一律先補最低於目標的資產 (以買代賣, 省手續費與證交稅)
- 訊息附: crash_phase 目前狀態、00891 距 ATH (資訊性)

### (c) 已移出

00406A 股利發放日再投入提醒 → 改由既有 **div_buy** 負責 (見元件 4), capital_flow 不處理。

## 元件 3 — 00406A 歸因追蹤 (月報)

併入 `capital_flow.py`, **每月第一個交易日**輸出, 同時寫 `analysis/etf_attribution_<YYYY-MM>.md`:
- 上月及累積: 00406A 總報酬 vs 持股籃子 (前一日 `etf_holdings_daily` 權重 × 成分股日報酬, 未揭露部分以 0 報酬計) → 差額 = 選擇權 + 進出時機 + 費用
- 上漲日 / 下跌日抓取比例、對籃子 beta、相關
- 對照: 00891 / 0050 / 加權指數同期總報酬
- 成分股單日 |報酬| > 35% 視為分割/除權假跳空, 排除並列出 (如 6669 9/02)
- 累積滿 6 個月前, 報告頂端固定標示「樣本不足, 不下結論」

## 元件 4 — 00406A 股利發放日再投入 (擴充 div_buy)

- `div_buy check` (既有 08:20) 增加: 今天是 00406A 股利發放日 → 推「入帳約 X 元 → 盤中零股可買 Y 股 @ 前收」
- **發放日來源:** TWSE ETF e添富配息清單頁 (`/zh/ETFortune/dividendList`), 表格為伺服器端 HTML, 含「收益分配發放日」欄; 預設頁不含 00406A, 需帶查詢參數。**實作第一步確認參數; 確認不到就採 fallback** = TWT48U 除息日 + 21 日曆日, 訊息標「預估發放日」
- 持有股數 = `data/div_buy_config.json` 新增 `base_shares` (2026-09-30 Shioaji 實測 2,000) + `div_buy_state.json` 已成交張數 × 1,000 + 已提醒再投入的零股 (用戶回報後手動加, 不登入 Shioaji)
- 金額 = 股數 × 每股配息; 單筆 ≥ 20,000 → 扣二代健保 2.11% 後計算

## 錯誤處理

- 任一資料源失敗 → 該段落標「資料缺」, 其他段落照常推; 整體失敗推 🚨 並 exit 非 0
- crash-phase / capital-flow 兩個 routine 納入 routine-watchdog

## 測試 (TDD)

`tests/test_crash_phase.py`:
- 轉換表每一列 (含 NORMAL→P2 直跳、假破位計數、RECOVERY→P2 二次探底需創新低、RECOVERY 不回 P1)、確認層讀數分類、資料缺
`tests/test_capital_flow.py`:
- 乘數表與未知代碼; 淨名目 / 雙向壓力 (純多、純空、多空混合如 空 5 + 多 2、完全對沖)
- 追繳 / 歸零距離與方向標示; 安全水位與可提領; 每月首個交易日判斷 (用假日日曆)
- 凱利比值分級
- Shannon: 權重計算、建倉期不建議賣出、缺口分配排序、維持期偏離觸發與重新 arm、股數取整
- 歸因: 籃子報酬、假跳空排除、capture ratio
`tests/test_div_buy.py` (擴充): 發放日判斷 (HTML 解析 fixture + fallback 預估)、股數合計、二代健保門檻

## 不做 (YAGNI)

- 任何下單 (B 由用戶另行設計; div_buy 下單維持原本「用戶 confirm」流程)
- 00406A 配息可持續性檢查 (用戶 2026-10-04 未選)
- 即時盤中判別 (日頻足夠)
- 00929 追蹤

## 附註 — 範圍外但審閱時發現

My-TW `data/tw_market_holidays.txt` 只有 2026-01-01 與 05-01 兩天, 缺中秋 9/25、教師節 9/28、國慶 10/09 等; routine-watchdog 依此判斷交易日, 假日可能誤判漏跑而補跑或告警。建議另案改讀 database `tw_holidays.py`。
