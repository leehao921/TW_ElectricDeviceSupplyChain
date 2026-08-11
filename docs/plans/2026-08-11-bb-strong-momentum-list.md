# BB 巡檢加入「強勢名單」(隔日沖池) — 2026-08-11

## Why

2026-08-11 用戶提供他人當日當沖名單 (2409/3704/4931/4979/4991/6213/6274),實測發現全部是 **8/10 漲停股** — 隔日振幅 5–10% 幾乎保證,是典型隔日沖池。現有 BB squeeze 找的是波動壓縮 (swing 進場點),結構上抓不到已爆發的強勢股 (7 檔 0 檔曾入 BB follow-through history)。用戶要求 BB 每日巡檢同時輸出強勢名單。

## What

在 `scripts/bb_inbox_alert.py` 加一段 **零額外查詢** 的強勢股 screen:

- **資料源**: 複用 `run_bb_scan_headless()` 已抓好的 `ohlcv_map` (BBScanResult 增帶 `ohlcv_map` 欄位)
- **條件**: 當日漲幅 ≥ **9.0%** (漲停附近) 且 成交值 ≥ **10 億** (close×volume)
- **處置股不剔除但標記 🚫** — 處置股通常停止現股當沖資格,顯示但警示 (source: `data/disposition_current.json` key `active`)
- **輸出**: inbox 訊息新增 `🔥 強勢` 段,依成交值排序,cap 10 檔;header 計數同步加

## How

1. `extract_strong_momentum(ohlcv_map, *, name_map, disposition, as_of, ...)` — 純函數,和 `compute_squeeze_signal` 相同的 as_of 切片邏輯
2. `load_disposition_set()` — 容錯讀 disposition_current.json
3. `build_inbox_message(..., strong=...)` 渲染新段
4. `main()` 串接;強勢名單**不進** consolidation state (那是 squeeze 追蹤,語意不同)

## Tests (TDD)

`tests/test_bb_inbox_alert.py` 新增:
- ret/turnover 門檻過濾 + 成交值排序
- 處置股標記 (不剔除)
- as_of 切片 (未來 bar 不入計算)
- message 渲染含 🔥 段與 🚫 標記

## Verify

`python3 scripts/bb_inbox_alert.py --dry-run` 實跑,確認 8/10 那批漲停股型態的名單會被抓到。
