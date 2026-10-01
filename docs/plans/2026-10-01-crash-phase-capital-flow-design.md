# 大跌階段判別 + 資金流提醒 + 00406A 歸因追蹤 — 設計

**日期:** 2026-10-01 · **狀態:** 設計待用戶審閱
**範圍:** A (大跌階段判別) + C (資金流提醒) + 歸因追蹤 — **全部只推播提醒, 不下單**。
B (TMF agent 兩階段行為) 由用戶在 nautilus 另一 session 設計, 本設計只提供它可讀的狀態介面。

## 背景與用戶決策

資金架構 (用戶 2026-10-01 定調):
- **TMF agent** — 主動報酬引擎; 大跌採兩階段: ① 初跌破位減多/翻空+買 put → ② 恐慌回補空單、progressive-add 加碼多單 (B, 不在本範圍)
- **00891** — 核心累積部位, 低點用 agent 獲利 / 備用金加碼
- **00406A** — 每月現金流停泊區; 除息日新錢買 1 張 (既有 div_buy) **且** 股利發放日全數再投入 (兩者並存)
- **備用金** — agent 獲利提領後停在黃金 (00635U) 為主

做此設計的依據 (2026-10-01 實測):
- **0050 不適合當備用金:** 與 00891 日報酬相關 0.91; 00891 三次大回檔期間, 低點購買力倍數 0050 只有 1.07–1.28×, 黃金 1.24–1.76×, 現金 1.30–1.81×
- **期貨帳戶在低點時通常沒有可提領的錢:** 現況 5 口 TMF 多單、權益 20.7 萬、約 11.7× 槓桿 → 大盤 −8.6% 權益歸零; 委託紀錄 (7/30–10/01) 顯示空單是 1–2 口的頭部戰術單, 核心一直偏多
- **選擇權指標歷史太短:** vix_daily 僅 2026-05-27 起 (76 日), 無法回測 2022/2024/2025 → 判別分兩層 (核心層可回測 / 確認層前向累積)
- `h:regime:context` 目前沒有 `break_state` 欄位 (8/18 規劃未實作) → A 自行計算破位, 不依賴它
- **00406A 採掩護性買權 (名目本金 0–25%)**; 7/02–9/29 歸因: ETF −2.69% vs 持股籃子 −2.00% (差 −0.69pt), 上漲日抓到 94% / 下跌日 95%, beta 0.98 → 目前看不到超額報酬, 樣本僅 61 日

## 元件 1 — 大跌階段判別 `scripts/crash_phase.py`

launchd `com.lulala.crash-phase` Mon-Fri **18:30** (排在 margin-vix 18:10 寫入 vix_daily 之後)。

**狀態機:** `NORMAL → P1_BREAK → P2_PANIC → RECOVERY → NORMAL` (也允許 P1_BREAK → NORMAL, 即假破位)

| 狀態 | 核心層 (可回測) | 確認層 (前向累積) |
|---|---|---|
| P1_BREAK 初跌破位 | 加權指數距 60 日高 ≤ −5% **且** 收盤 < MA60 | vix_w ≤ 32 且 wm_spread ≤ +2 (保護還便宜) |
| P2_PANIC 恐慌 | 距 60 日高 ≤ −10% **且** RV20 ≥ 1.5 × RV20 的 120 日中位數 | wm_spread > +2 或 vix_w > 32 (playbook 門檻) |
| RECOVERY 回復 | 由 P2 收盤站回 MA20 **且** 全市場外資 5 日淨額 > 0 (賣壓竭盡) | — |
| NORMAL | 距 60 日高 > −3% **且** 收盤 ≥ MA60 | — |

- 進入狀態只看核心層; 確認層讀數寫入狀態並在訊息中顯示「確認 ✅ / 未確認 ⚠️ / 無資料」, 不阻擋轉換 (確認層歷史不足以當 gate)
- 輸出 Redis `h:agent:crash_phase`: `phase`, `since`, `prev_phase`, `dd_60d`, `ma20`, `ma60`, `rv20`, `rv20_med120`, `foreign_5d`, `vix_w`, `wm_spread`, `confirm`, `as_of` — **B 的讀取介面**
- 狀態 state 存 `data/crash_phase_state.json`; **僅狀態切換時**推 inbox topic=`crash-phase`
- 資料源: 加權指數日收盤 (yfinance `^TWII`, 失敗時 fallback `index_spot` 當日最後值), 外資 = `institutional_stock` 全市場 `SUM(foreign_net × close_price)`, 選擇權 = `vix_daily`
- 休市日 (tw_holidays) 不執行

**回測 (實作前置, 先校準門檻):** `scripts/crash_phase_backtest.py` 以 2021-05 起的加權指數 + 00891 重播, 標出每段狀態, 輸出 `analysis/crash_phase_backtest_<date>.md`:
- 每次進入 P2 的日期, 及 00891 後續 20/60 日報酬
- 每次進入 P1 後是否 (a) 進到 P2 (b) 假破位回 NORMAL, 及假破位次數
- **成功標準:** P2 進入後 00891 60 日報酬平均為正; 2022 長空頭內 P2 首次觸發不早於該段跌幅的一半; 假破位次數列出供判斷
- 門檻不達標 → 調整門檻並在報告記錄每次調整, 不靜默改

## 元件 2 — 資金流提醒 `scripts/capital_flow.py`

launchd `com.lulala.capital-flow` Mon-Fri **18:40**。推 inbox topic=`capital-flow`。

**(a) 期貨提領提醒** — 讀 `h:real_account:baseline` (`equity_twd`, `margin_used_twd`, `positions_json`)
- 安全水位 = 已用保證金 + Σ(口數 × 現價 × 10 × 10%) (撐過大盤 −10%; 用戶無偏好, 採推薦值)
- 可撐跌幅 = (權益 − 已用保證金) / Σ(口數 × 現價 × 10) — 部位為空時顯示「無部位」
- **每月第一個交易日**: 權益 − 安全水位 ≥ 10,000 → 提醒提領該差額到備用金 (00635U)
- **每日**: 可撐跌幅 < 10% → 訊息附 ⚠️ 槓桿警示 (資訊性, 不動作); 同一警示狀態只在首日與每週一重推
- `data/capital_flow_ledger.json` 手動記錄入金/出金, 用來算 agent 淨獲利 (equity_snapshots 無法分辨入金)
- baseline 過期 (`as_of` > 1 天) → 訊息標「期貨資料過期」, 不給提領建議

**(b) 00891 加碼提醒** — 觸發條件任一: crash_phase 進入 P2_PANIC, 或 00891 首次跌入 add1/add2/add3 帶
- 買低帶判斷 **import `etf_00891_watch` 的既有函式**, 不重寫門檻
- 建議動用比例: 每觸發一階 25% 備用金 (4 批), 同一階不重複提醒 (state 記錄已提醒的階)
- 訊息附: 當前 phase、確認層讀數、00891 距 ATH、P/B lights 中 00891 成分股 RED 權重 (資訊性)
- B 上線後若 `h:agent:crash_phase` 之外另有空單獲利欄位, 訊息附「空單回補獲利可一併提領」— 本期不實作, 留介面

**(c) 00406A 股利再投入提醒** — 股利發放日當天 08:30 前推送 (由 18:40 run 判斷「明日為發放日」時預告, 發放日早上由 div_buy 08:20 check 一併推)
- 發放日來源: TWSE ETF e添富配息表 (實作時確認 endpoint); 取不到 → 除息日 + 21 日估算並標「預估」
- 持有股數 = config 基礎張數 (`data/capital_flow_config.json`) + `data/div_buy_state.json` 已成交張數; **不登入 Shioaji** (同身分證 5 連線已滿)
- 訊息: 「入帳約 X 元 (扣二代健保若 ≥2 萬) → 盤中零股可買 Y 股 @ 參考價」

## 元件 3 — 00406A 歸因追蹤 (月報)

併入 `capital_flow.py`, **每月第一個交易日**輸出, 同時寫 `analysis/etf_attribution_<YYYY-MM>.md`:
- 上月及累積: 00406A 總報酬 vs 持股籃子 (依前一日 `etf_holdings_daily` 權重 × 成分股日報酬, 未揭露部分以 0 報酬計) → 差額 = 選擇權 + 進出時機 + 費用
- 上漲日 / 下跌日抓取比例 (capture ratio)、對籃子 beta、相關
- 對照: 00891 / 0050 / 加權指數同期總報酬
- 成分股單日 |報酬| > 35% 視為分割/除權假跳空, 排除並在報告列出 (如 6669 9/02)
- 累積滿 6 個月前, 報告頂端固定標示「樣本不足, 不下結論」

## 錯誤處理

- 任一資料源失敗 → 該段落標「資料缺」, 其他段落照常推; 整體失敗推 🚨 並 exit 非 0 (routine-watchdog 可見)
- 所有 state 檔寫入採 tmp + rename
- 兩個 routine 納入 routine-watchdog 監控清單

## 測試

TDD, `tests/test_crash_phase.py` / `tests/test_capital_flow.py` 測純函式:
- 狀態轉換 (含假破位、P2 不可跳過 P1 以外的回退路徑、RECOVERY 需外資條件)
- 安全水位 / 可撐跌幅計算 (含無部位、多空混合 positions_json)
- 加碼階梯只提醒一次、每月提領只在首個交易日
- 零股股數 (二代健保門檻、整數股)
- 歸因: 籃子報酬計算、假跳空排除、capture ratio

## 不做 (YAGNI)

- 任何下單 (A/C 只提醒; B 由用戶另行設計)
- 黃金 / 銅的進出時機判斷 (備用金固定以 00635U 為主)
- 即時盤中判別 (日頻足夠; 盤中由 agent 自己的系統處理)
- 00929 追蹤 (用戶架構未納入)
