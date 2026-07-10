# TXO 選擇權盤中量化分析模組 — Design Spec

**Status:** Approved design (brainstormed 2026-07-09; trigger: 當日開盤 3 小時高波動)
**產出物:** `scripts/options_quant.py`(單腳本)+ `analysis/options_quant_<date>.md` 報告
**定位:** 可重複跑的分析工具。純讀取(trading-timescaledb read-only),不下單、不出買賣指令。

## 1. CLI 與資料流

```
python scripts/options_quant.py --date 2026-07-09 --window 09:00-12:00
```

- `--date` 預設今天(TW);`--window` 預設 `09:00-13:30`;`HH:MM-HH:MM` 格式
- 資料來源(全 read-only,psycopg 連 `trading-timescaledb:5432/tmf_market_data`,user tmf):
  - `iv_strikes` — 逐檔 strike IV + greeks(delta/gamma/theta/vega),~10s cadence
  - `iv_metrics`(原始 10s 表)— ATM IV / skew_25d / rr_25d / pcr_volume / iv_term_slope / underlying_price。註:1m 聚合表缺 skew/pcr 欄,統一讀原始表(窗口資料量 ~1,260 筆/到期,無負擔),pandas 內 resample 到 1m
  - `option_oi_daily` — TAIFEX 盤後結算 OI(settle_date 鍵,T+1)
  - `ohlcv_1m`(bucket, symbol='TXF', OHLCV)— TXF 1 分鐘 bar,RV 計算用(已驗證存在且新鮮)
- 產出:`analysis/options_quant_<date>.md` + stdout 摘要

## 2. 架構

單腳本、三層:

1. **Data-access 層** — `fetch_*` 函數:DB → pandas DataFrame,唯一碰 I/O 的層
2. **分析層(四個純函數)** — 各吃 DataFrame、回 `{"metrics": dict, "verdict": str, "verification": list[str]}`,無 I/O、可獨立單元測試:
   - `analyze_gex(strikes_df, oi_df, spot) -> Section`
   - `analyze_iv_rv(atm_iv_series, txf_bars, history_df) -> Section`
   - `analyze_term_skew(metrics_df, history_df) -> Section`
   - `analyze_flow(metrics_df, oi_today, oi_prev) -> Section`
3. **報告層** — 合成 vol 環境標籤、渲染 markdown

**Front expiry 解析(四角度共用):** tenor 最短且窗口內有資料的到期。結算週 TX2 不掛牌時自然落到 TXO 近月 — 無特例分支。

## 3. 四個角度的量化定義

### 3.1 GEX / Dealer Gamma
- `GEX(K) = gamma(K) × OI(K) × 50(乘數) × spot² × 0.01`,call 正、put 負(naive dealer-positioning 慣例,報告內註明假設)
- OI 用**前一結算日** `option_oi_daily`(T+1 近似,報告註明)
- gamma 取窗口末端最近一筆 `iv_strikes` 快照
- 產出:總 GEX(億 NTD/1% move)、**gamma flip 價位**(strike 由低到高累積 GEX 的過零點)、現價 vs flip → `磁吸區`(spot 在正 GEX 區)或 `放大區`(負 GEX 區)、GEX 前 5 大集中履約價

### 3.2 IV vs RV(Variance Risk Premium)
- RV:窗口內 TXF 1m log-return 的年化實現波動(√(Σr²/n) × √(252×窗口 bar 數/日) 標準化);同時給 Parkinson(high-low)版
- IV:窗口內 **TXO 月選 front** ATM IV 的均值與首尾值(與 60 日歷史同 product,like-for-like;避免非結算週 TX2 週選 vs 月選歷史的偏置。GEX 不涉 percentile,照用 nearest live expiry)
- **VRP = IV_mean − RV**(vol points)
- Percentile:對近 60 個交易日**同窗口**的 VRP 分布排名。**量化形容詞(貴/便宜/極端)只有在 percentile 驗證後才可出現在 verdict,verification list 記錄樣本 n 與計算式** — 落實 Golden Rule 0
- 產出:RV、IV、VRP、percentile、verdict(如 "VRP +4.2 vol pts,60 日同窗 percentile 78 → 選擇權相對已實現波動偏貴")

### 3.3 Term / Skew 盤中動態
- 逐分鐘序列:front ATM IV、skew_25d、rr_25d、近-遠 term slope(`iv_metrics_1m`)
- 產出:各指標窗口內 Δ(首→尾)與路徑極值、對近 60 日同窗 Δ 分布的 percentile、轉折偵測(單調性破壞點,如 skew 在窗口中段急陡 = 下檔避險搶購時點)

### 3.4 PCR / OI 資金流
- 窗口內 PCR(volume)逐分鐘路徑 + 均值
- OI 增減:前一結算日 → 最新結算日,per-strike ΔOI 的 top ±5(建倉/平倉集中處),call/put 分列
- 價平 ±3 檔成交量集中度(該區間量 / 全鏈量)

## 4. 合成 vol 環境標籤(規則制)

| 標籤 | 規則 |
|---|---|
| `expansion-risk` | 總 GEX < 0 且 VRP percentile < 30 |
| `premium-rich-pinning` | 總 GEX > 0 且 VRP percentile > 70 |
| `hedging-bid` | skew Δ percentile > 80(下檔避險急升) |
| `neutral-carry` | 其餘 |

多標籤可並存(除 neutral-carry 為 fallback)。標籤定義表附在每份報告尾部。**不出買賣指令**(判定環境,不判定行動)。

## 5. 錯誤處理

- 結算週:front expiry 解析自然 fallback(§2),無特例
- 資料缺口:窗口內若有 > 5 分鐘無資料,該 section 標 `DATA GAP hh:mm–hh:mm`,指標照算但 verdict 加註
- Percentile 歷史樣本 < 60 日:照算,標實際 n;< 20 日:percentile 欄輸出 `insufficient-history(n=X)`,verdict 禁用分布性形容詞
- DB 連線失敗:明確報錯 exit 1,不產半份報告
- 前一結算日 OI 缺(假日後等):往前找最近 settle_date,報告註明日期

## 6. 測試

- 分析層四個純函數:合成 DataFrame 單元測試(GEX flip 過零點正確性、VRP 與 percentile 數值、標籤規則每條至少一個 case、轉折偵測)
- Data-access 層 mock;報告層驗證 markdown 含必要 section 與 verification log
- 不需 live DB;TDD(RED-GREEN-REFACTOR)

## 7. 未來擴充(本期不做,YAGNI)

- launchd 每日排程 + inbox notify(跑順之後)
- §3.3 轉折偵測(單調性破壞點)、rr_25d 路徑分析 — 首版僅出 Δ 與極值(2026-07-10 實作時降範圍)
- §3.4 價平 ±3 檔量能集中度 — 同上,首版未實作
- Parkinson RV 變體(首版僅 close-to-close,已於報告 verification 揭露 intraday-only)
- 盤中即時模式(讀 Redis h:iv:latest)
- 跨日事件研究(GEX 標籤 vs 次日已實現波動的回測)
