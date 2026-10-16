# 強勢股整理回測 (Martin pullback) — 日線掃描 + 回測

日期: 2026-10-16
狀態: v1 完成 — WEAK, 未進 routine

## 目的

把 Martin 的四步回調買法 (強勢股 → 整理轉強 → 支撐疊合第一次回測 → 分鐘圖突破前K高) 落成
可回測的日線訊號,先驗證台股有沒有 edge,有才進 routine。

## 範圍 (v1)

| 步驟 | v1 做法 | 資料 |
|---|---|---|
| 1a 強勢 | 21/63/126 日報酬任一 ≥30% 且該期間全池排名前 25%;20D 平均成交值 ≥ 0.5 億 | stock_daily_ohlcv |
| 1b 整理轉強 | 沿用 BB squeeze 定義 (BBW ≤ 自身 60 根 30 分位, 前 7 日 ≥4 日) + 低點墊高 (近 10 根最低 > 前 20 根最低) + close > EMA9/21 且兩者 5 日不下彎;頭頭低+底底低+壓在下彎 EMA21 下 → 剔除 | 同上 |
| 1c 題材同步 | 同一題材 (build_theme_map) ≥3 檔通過 1a+1b → 標註 | Pilot_Reports themes |
| 2 支撐疊合 | 候選位: EMA21、EMA50、AVWAP (錨=近 40 根最高點)、前期 swing high (k=5)、未補向上缺口下緣;≥3 個落在 1.5% 帶內、且位於收盤下方 → zone | 同上 |
| 2 第一次回測 | 收盤站上 zone 後至今沒有任何 low ≤ zone_top;今日 low 觸 zone (≤ top×1.005) 且收盤守 zone_low | 同上 |
| 2 分鐘觸發 | **v1 用日線代理**: T+1 high > T high 才進場,價 = max(open, T high) | — |
| 3 停損 | T 日低點;回測同時報 停損距離 ≤3% 子集 (Martin 規格) 與 ≤8% 全集 | — |
| 4 出場 | 3R 出一半,其餘收盤跌破 EMA9 出,最長 30 日;跳空跌破停損以開盤價出 | — |

不做 (v2+): 1/5 分鐘真觸發 (需 Shioaji kbars)、R 部位計算器、launchd routine。

## 成本

公定來回 0.585% (手續費 0.1425%×2 + 證交稅 0.3%),以 R 扣除: cost_R = 0.585% × entry / (entry − stop)。

## 驗證標準

- 交易層: n、勝率、平均 R、中位 R、期望值 (扣成本),按半年分段看 regime 穩定性。
- 事件層: 沿用 `signal_backtest.event_stats/grade_daily` (T+5/T+20 對同日市場中位超額),
  與 signal_registry 其他家族同口徑。
- 期望值 ≤ 0 或 grade = NO-EDGE → 不進 routine,報告寫明。

## 檔案

- `scripts/strong_pullback.py` — 純函式 + `scan` (今日名單) + `backtest` CLI
- `tests/test_strong_pullback.py`
- 結果: `analysis/strong_pullback_backtest_2026-10-16.md`

## 已知限制

- 日 K 自 2025-01-02 起;126 日報酬 + 指標暖機後,可回測區間約 2025-07 起。
- universe = stock_daily_ohlcv 955 檔 (電子涵蓋),不含非電子題材股。
- 日線代理觸發會比分鐘圖觸發的停損更寬,R 分布偏保守。

## 結果 (2026-10-16)

- Martin 原規格 (1.5% 帶 / 3 位疊合 / step1 須在前一日成立) 只有 5 個事件 → 放寬為 2.5% / 2 位 / 觀察名單 10 日。
- 預設參數: 76 事件 → 51 未觸發 → 25 成交;T+20 超額中位 +2.53%、beat 54% → **WEAK**。
- 日線代理停損中位 6.2% (原法 2.5–3%) → 交易層 R 不具代表性;edge 若存在,在分鐘圖的緊停損。
- 決策: 不進 launchd routine;scan CLI 供手動觀察;v2 = Shioaji 1 分 K 觸發重驗。
