# 多空訊號系統完整化 + 系統性驗證

## Context

訊號目錄（docs/signal_registry.md）已編目 9 多/8 空家族，但三個缺口使它不完整：(1) **空方部位分解缺借券（SBL）層** — 無法區分法人對沖 vs 散戶押跌（剛確立的判斷框架缺數據腿）；(2) **四個家族從未系統性驗證**（S3 乖離+P/B、S4 外資撤投信頂、L4 左側竭盡、L3/S6 外資結構州）— 現掛分級是個案軼事；(3) **無市場級每日掃描** — 訊號散在各 routine，沒有統一的「今日多方名單/空方名單」產出。本計畫補齊三者並用 18 個月多 regime 數據（2025-01 起，含 2025 牛市、2025-04 與 2026 兩次崩跌）驗證。

## Phase A — SBL 借券數據導入（空方第三層）

- **database repo `scripts/collectors/margin_daily.py` 擴充**：`ALTER TABLE margin_daily ADD COLUMN sbl_balance/sbl_sell BIGINT`
  - TWSE：rwd `TWT93U`（融券借券賣出餘額日報，**歷史可回填** — 實作時先探形狀，欄位映射防禦性寫）
  - TPEx：OpenAPI `tpex_margin_sbl`（快照 forward-only，沿用 warrant/margin 的 T-1 重收模式）
  - 回填與 margin 同跨度（7/14 起 30 日 + 前向）
- 空方分解自此可算：`借券(法人對沖/套利) vs 融券(散戶方向) vs 權證認售(噪音)` — 接進 S2v2 交叉（週報）

## Phase B — 四家族系統性驗證（共用 daily event harness）

新 `scripts/signal_backtest.py`（一次性研究，TDD 純函式）— 復用 vix_signal_study 的 event/forward/baseline/grade 模式改日頻，數據 2025-01 起（~400 交易日、938 檔）：

| 家族 | 事件定義 | 前瞻 | 現掛分級 → 驗證後 |
|---|---|---|---|
| S3 乖離+過熱 | 個股乖離 MA20 ≥ 自身 rolling 252 日 98pct（P/B 燈僅 50 檔池，主檢定用乖離、P/B 附註）| 5/20D | VALIDATED(軼事) → 正式檢定 |
| S4 外資撤投信頂 | 20D 外資流 z ≤ -1 且投信 z ≥ +1（z 基準=該股自身 120D）| 10/20D | 觀察 → 檢定 |
| L4 左側竭盡 | 距 252 日高 ≤ -20% 且前 20D 外資淨賣、當前 5D 轉正 | 10/20D | 觀察 → 檢定 |
| L3/S6 外資結構州 | futures_oi_daily(126 日) 重建逐日 hedged_accumulation/distribution_cover 分類 → 各州次日/5 日 TXF 報酬 | 1/5D | 觀察 → 檢定（n 小，誠實標註）|

護欄照舊：事件 de-cluster（同股 10 日內首次）、基準=同日全市場中位、n<20 INSUFFICIENT、按年度分段看 regime 穩定性、grade 門檻沿用（edge≥事件中位−基準 5bp×日數比例、hit dev≥10pp）。

## Phase C — 每日市場級訊號掃描 `signal_scan.py`（17:50）

- 產出**今日空方名單**：S2v2 投降型/陰跌型（margin×volr）、S3 乖離 98pct（+P/B RED 標記）、S4 撤頂結構、S1 即將解除且外資賣超的處置股
- **今日多方名單**：L1 即將解除且外資買超、L4 竭盡候選、L3 州標記（hedged_accumulation 日 → 名單頭部 banner）
- 標籤復用 `warrant_flow_rank.load_labels`（名稱/產業/題材）；每檔附觸發值；名單股自動進 T+5/T+20 追蹤（沿用 warrant tracker 模式 → 未來命中統計自我校驗）
- launchd `com.lulala.signal-scan` Mon-Fri 17:50 + watchdog（22 checks）+ inbox topic=`signal-scan`（report_path 全文）

## Phase D — 收斂

- Registry 分級按 backtest 結果更新（升/降級規則寫進報告）；ledger 週報加掃描名單 T+N 命中行
- `analysis/signal_validation_20260828.md` 總驗證報告（Verification log 完整）
- 兩 repo commit/push；memory 更新（signal-scan routine + SBL 欄位）

## 檔案

- database: `scripts/collectors/margin_daily.py`（SBL 擴充）
- My-TW: `scripts/signal_backtest.py` + `tests/test_signal_backtest.py`（新）、`scripts/signal_scan.py` + `tests/test_signal_scan.py`（新）、`scripts/signal_ledger.py`（加命中行）、`docs/signal_registry.md`（分級更新）、`scripts/routine_watchdog.py`（22 checks）、launchd plist
- 復用：`zscore`（foreign_structure.py）、`load_labels`（warrant_flow_rank.py）、`_nth_close_after` 模式（disposition_daily_fetch.py）、grade/event 模式（vix_signal_study.py）

## 驗證

```bash
pytest tests/ -q                                   # 全綠 (新增 ~12 案例)
docker exec ... margin_daily.py --date <d>          # SBL 欄有值 (TWSE+TPEx)
python scripts/signal_backtest.py                   # 四家族檢定報告 + 抽查 2 事件手算
python scripts/signal_scan.py                       # 今日多空名單 (名稱標籤/觸發值完整)
launchctl kickstart com.lulala.signal-scan          # exit 0 + Discord 收到
# 分段穩定性: 每家族 2025H1/2025H2/2026H1/2026H2 分段表 — 單段依賴即降級標註
```

## 風險

- TWT93U 端點形狀未探（Cloudflare 限流風險低 — TWSE rwd 系無此問題）；映射失敗 → SBL 先 TPEx-only + TWSE 補探
- L3/S6 僅 126 日（futures_oi 回填上限）— 結論最多 WEAK 級
- 名單型訊號的執行紀律（分批/失效線）不在本計畫 — 訊號歸訊號、執行歸 position-watch config
