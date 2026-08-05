# 外資結構背離指標 + 量能 regime gate + 處置解除 backtest

**日期**: 2026-08-05
**來源**: 陳鳳馨文章分析（vault/log.md 2026-08-05）— 用戶核准 alpha #1/#4 上線、#3 backtest。

## A. `scripts/foreign_structure.py` — 外資結構背離（alpha #1）

外資「現貨淨買 5D z」vs「TXF 淨 OI z」背離分類，日更推 Discord。

- 數據：`institutional_stock` sum(foreign_net) by date（2025-01 起）＋ `futures_oi_daily` 外資 TXF net_oi（2026-05-15 起，55 日）
- z：對 120D baseline（排除當日），MIN_HISTORY=20 不足輸出 insufficient-history（Golden Rule 0 同 news_pulse 慣例），std<1e-9 退化 guard
- 分類：spot_z≥+0.5 且 fut_z≤−0.5 → `hedged_accumulation`（偏多背離）；spot_z≤−0.5 且 fut_z≥+0.5 → `distribution_cover`（偏空背離，對偶 short 結構）；同向 → aligned_bull/bear；其餘 neutral
- 產出：`analysis/foreign_structure_<date>.md`（分類 + 近 10 日表 + verification log）+ inbox topic=`foreign-structure` 帶 report_path
- 排程：launchd 16:30 Mon-Fri（法人/OI 資料落地後）；watchdog 註冊

## B. `scripts/market_regime.py` — 量能 regime gate（alpha #4）

- 源：TWSE openapi FMTQIK（當月+上月日資料；TradeValue + TAIEX 收盤一站取得）
- 規則：5D 均成交值 <1.0 兆 → `low_volume`；TAIEX 收盤 < regime line（39,385 = 7/29 低點，存 state 可調）→ `broken`；否則 `normal`
- Cache `data/market_regime.json`（as_of 當日即用，否則 refetch）— 模組供他 script 呼叫，**不加新 launchd**
- 接線：`bb_inbox_alert.py` 與 `buy_list_daily_alert.py` digest 前置 regime banner；low_volume 時 BB Buy 段標「(量縮降權)」— **保留訊號本體**（followthrough 命中率數據不中斷，可按 regime 分段統計）

## C. `scripts/disposition_backtest.py` — 處置解除回補（alpha #3，一次性可重跑）

- TWSE `announcement/punish` 歷史查詢 2025-01-01 起（季度分段抓，禮貌間隔）；只留 4 位數股票代號（濾權證）；解析處置期間 ROC 日期
- Join `institutional_stock`（TWSE only，OTC 無 close — 揭露）：處置前 5D 外資淨買、解除日、解除後 +5/+10D 報酬與外資回補
- 產出：`analysis/disposition_backtest_<date>.md` — 全樣本 vs「處置前外資買超」分組的解除後報酬統計
- 不排程；為下一輪動能行情備妥訊號依據

## 驗證
各 script pytest（純函式）→ live 跑一輪 → A 進 launchd kickstart → commit。
