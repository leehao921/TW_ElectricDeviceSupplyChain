# 事件窗口 IV 監控 — 事前定價幅度 + 事後延續/消化分類 + 自動記錄統計

## Context
10/14 20:30 美國 CPI 公布後 TXF 1 分鐘跌 ~240 點、90 分鐘內最大回落 607 點 (1.24%)。回看:
- **事前** IV 沒有方向訊號 (月選 21.4 持平,前 1 分鐘反而微降),但 10/16 週選已定價 **±484 點**事件幅度 (含台積電法說)。
- **事後** 1-15 分鐘有確認訊號: PCR 0.58→0.92 (20:31)、價跌 IV 升 (週選 28.4→30.5) → 延續到 48,338。

使用者要: (1) 總經事件進行事曆 (2) 事前 30 分推「週選定價 ±X 點」(3) 事後 5/15 分推「實際 vs 定價 + IV/PCR 反應分類 (延續/消化)」(4) 每次自動記錄,滿 ~20 次跑統計。

既有基礎 (重用,不重造):
- `nautilus-shioaji/nautilus_shioaji/agent/macro_calendar.py` — **官方來源手工維護**的 `EVENTS` (NFP/CPI/FOMC/台積電/權值法說/財政部進出口/選舉, bls.gov + federalreserve.gov), `at_taipei()`、`reaction_at()` (盤後事件 → 下一個開盤分鐘)。10/14 CPI 已在內。launchd `com.lulala.macro-event` 已負責 T-24h/T-2h 提醒與 surprise 記錄 → 本計畫**不重複提醒**,只做 IV 面。
- `My-TW-Coverage/scripts/event_calendar.py` + `data/event_calendar.csv` (MOPS 法說, key=date+symbol)。
- `scripts/iv_term.py`: `event_premium()`、`_event_lines()`、`trading_sessions()`、`load_holidays()`;`gex_regime_monitor.iv_curve()/latest_forwards()`。
- `scripts/discord_forward.py` 路由 (`TRADING_TOPICS`)、`scripts/skew_converge_study.summarize()` (n<20 護欄)。

## 設計

### 1. 總經事件併入行事曆 — `event_calendar.py sync-macro`
- 以 nautilus venv 子程序匯出 `macro_calendar.EVENTS` 為 JSON (`nautilus-shioaji/.venv/bin/python -c ...`,避免 My-TW venv 缺 nautilus 依賴),取 kind ∈ {NFP, CPI, FOMC, TW_EXPORT, US_MIDTERM, TW_ELECTION} (台積電/權值法說已由 MOPS 來),轉台北時間 upsert: `type=macro, impact=index, symbol=<kind>, source=nautilus:<id>`。
- 一處維護: 新增/修改總經日期仍改 nautilus `macro_calendar.py`;My-TW 每次 sync 同步。`sync` 指令同時跑 MOPS + macro。

### 2-3. 事件窗口 routine — 新 `scripts/event_window.py` (launchd `com.lulala.event-window`, StartInterval 60s)
每分鐘讀行事曆中 index 級 earnings/macro 事件,計算 `reaction` 時刻 (事件時刻若在 TAIFEX 盤中 = 本身;否則下一個開盤分鐘,用 `iv_term.load_holidays()` 排除假日;日盤 08:45-13:45、夜盤 15:00-05:00),依階段觸發一次 (Redis set `event_window:done:<event_key>` 防重):
- **pre (reaction − 30 分,或盤後事件取最後可交易分鐘前 30 分)**: 用 `iv_term` 新純函式 `implied_event_move(curve, forwards, ref, now, event, holidays)` → (到期, ±點, %, 該到期 ±1σ),推:
  `⏰ CPI 20:30 → 10/16 週選定價 ±484 點 (0.99%) · 同到期另含: 台積電法說` (同到期多事件時列出,避免歸因錯誤)。
- **+5 / +15 分 (以 reaction 為 0)**: 純函式 `measure_reaction(pre, post)` + `classify_reaction(...)`:
  - 輸入: TXF (ticks TXF 近月) 事件前 1 分鐘價 → 現價與區間;前月/最近週選 ATM IV、PCR、前月 skew 的「事件前 5 分鐘平均」vs 現值。
  - 分類 (門檻放 Config,原始值全記錄以便日後重設門檻):
    - **延續**: |價格移動| ≥ 0.3 × 定價幅度 且 週選 IV ↑ ≥ 0.5 vol-pt 且 PCR 與價格同向 (跌→PCR↑ / 漲→PCR↓)
    - **消化**: 週選 IV ↓ ≥ 0.5 vol-pt (IV crush)
    - **混合**: 其餘
  - 推: `📊 CPI +5分: 實際 -240 vs 定價 ±484 (0.50×) · 週選IV +0.9 · PCR +0.33 → 延續(跌)`。
- topic `event-window` → 加入 `TRADING_TOPICS` (#guyu);推完 kickstart forwarder 載入新路由。
- 行寬 ≤40 (手機,沿用 `_disp_width` 測試)。

### 4. 自動記錄 + 統計
- 每事件一列寫入 `data/event_window_log.csv` (git 追蹤): event_key, kind, name, reaction_at, implied_pts, implied_expiry, co_events, px_pre, px_5, px_15, px_60, iv_w_pre/5/15, iv_m_pre/5/15, pcr_pre/5/15, skew_pre/5/15, class_5, class_15, outcome_60, data_quality。
- **outcome** (+60 分時補填): 若 +5 分方向在 +60 分仍延續 (px_60 相對 px_5 同向 ≥ 0.1×定價幅度) → `continued`;反向超過 → `reversed`;其餘 `flat`。判定「延續→continued、消化→reversed」的命中率。
- **回填** `event_window.py backfill`: 以歷史 iv_metrics (2026-07-08 起) + ticks 重播過去事件 (CPI 7/14、8/12、9/11、10/14;NFP 7/2、8/7、9/4、10/2;FOMC 7–9 月;台積電 7/16、10/15;進出口 7/9、8/7、9/9、10/8 等,約 14 筆),立刻有樣本;10/05 前標 `data_quality=pre_fix` (IV 輸入舊成交價問題)。
- `scripts/event_window_study.py`: 依 class 分組算 outcome 命中率 vs 基準 (全部事件的 continued 比例),沿用 `summarize()` n<20 護欄、Verification log、無分布性形容詞;產 `analysis/event_window_study_<date>.md`。n ≥ 20 時登記 `docs/signal_registry.md` 候選。

## 關鍵檔案
- 修改: `My-TW-Coverage/scripts/event_calendar.py` (sync-macro)、`scripts/iv_term.py` (`implied_event_move` 由 `_event_lines` 抽出共用)、`scripts/discord_forward.py` (TRADING_TOPICS)
- 新增: `scripts/event_window.py`、`scripts/event_window_study.py`、`scripts/launchd/com.lulala.event-window.plist`、`data/event_window_log.csv`、tests `tests/test_event_window.py`、plan `docs/plans/2026-10-15-event-window-iv.md`
- 不改 nautilus (只讀其 `EVENTS`)。

## 流程 (TDD)
每個純函式先寫失敗測試: macro JSON → calendar rows、reaction 時刻 (盤中/盤後/假日/夜盤跨午夜)、implied_event_move (含同到期多事件)、measure/classify (10/14 CPI 實數做 fixture: 定價 484、-240、IV +0.9、PCR +0.33 → 延續)、outcome 判定、log upsert、study n<20 護欄。

## 驗證
1. 單元測試 + pre-commit 全套。
2. `event_window.py backfill` → log 約 14 列;10/14 CPI 列應為 class_5=延續、outcome=continued (實際延續到 48,338)。
3. `event_window_study.py` 產報告 (n≈14 → 「樣本不足,不下結論」)。
4. 下一個真實事件 (10/15 14:00 台積電 → reaction 15:00 夜盤開盤) 驗 pre/+5/+15 三則推播出現在 #guyu、log 自動寫入、+60 補 outcome;forwarder 路由 class=trading。
5. 記憶: reference memory + MEMORY.md 一行;routine-watchdog 是否納管待確認 (分鐘級 routine)。
