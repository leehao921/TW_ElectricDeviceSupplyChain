# 自家 VIX 訊號效度驗證 — 對應台指期貨價格的量化研究

## Context

自家 VIX（TXO 近月 ATM IV 衍生，`vix_daily`/`iv_metrics`）比官方 VIXTWN（30 天 model-free）**更敏感**（近月期限 + 10 秒級原始數據）。用戶問：這個敏感度能否轉化為可用訊號？要求以庫內數據驗證訊號效度與對應的指數期貨價格反應。

關鍵樣本現實：日級 `vix_daily` 只有 54 天（統計力不足，僅作描述）；**盤中 `iv_metrics` 有 208 萬列（10 秒級、63 個交易日）× `ohlcv_1m` TXF 連續分鐘線** — 真正的驗證主戰場在盤中。

## 數據資產（全部在庫）

| 表 | 粒度/跨度 | 角色 |
|---|---|---|
| `iv_metrics` (TX) | 10 秒級，5/27–8/26 | 訊號源：atm_iv / near·far_month_iv / iv_term_slope / iv_skew_25d |
| `ohlcv_1m` (symbol='TXF') | 1 分鐘連續月 | 前瞻報酬標的（options_quant 既用 pattern）|
| `vix_daily` | 54 日 | 日級描述性 overlay |
| `futures_oi_daily` / `market_regime` | 日級 | 事件分層（外資空單水位 / regime）|

## 五個候選訊號與檢定設計

盤中皆先 10s→1m 重採樣、限日盤 08:45–13:45（夜盤/週末 IV 列排除，沿用 vix_daily 修復的 dow/sanity 過濾）。

| # | 訊號 | 事件定義 | 前瞻窗 |
|---|---|---|---|
| S1 | IV 急升 | Δ15m near_iv 的 z ≥ 2（基準=前 20 日同時段分布，排除當日）| TXF +15/30/60 分、至收盤 |
| S2 | 期限倒掛 | near > far 轉正（backwardation onset，恐慌結構）| 同上 |
| S3 | Skew 急變 | Δ15m iv_skew_25d z ≥ 2（put bid）| 同上 |
| S4 | VRP 極端 | 日級 IV−RV percentile <10 / >90（`fetch_vrp_history` 現成）| 次日 TXF 報酬 |
| S5 | 日級 VIX Δ1d 急升 | n=54 僅描述，不下結論 | T+1/T+5 |

**檢定**：每訊號報 (a) 事件數 n、(b) 事件後報酬中位/P25/P75 vs 無條件同時段基準、(c) 方向命中率、(d) 事件 de-cluster（30 分鐘內重複事件只計首次）。分層：外資期貨淨空單水位（futures_oi_daily z）× regime。

## 方法論護欄（Golden Rule 0）

- 全部 percentile/z 經 `percentile_verified()`（n<20 拒絕輸出形容詞）— options_quant.py:62 現成
- z-score 用 foreign_structure.py:195 的 `zscore()`（MIN_HISTORY/退化防護）
- RV 用 `realized_vol_annualized()`（options_quant.py:279，intraday-only 揭露照舊）
- 基準分布排除事件日自身（無 look-ahead）；63 天樣本的統計力限制在報告顯著標註
- **不輸出交易指令** — 產出為效度報告 + 閾值參數；驗證通過才另議接入 routine

## 實作

1. `docs/plans/2026-08-26-vix-signal-validation.md`（本計畫落 repo）
2. **`scripts/vix_signal_study.py`**（一次性研究腳本）：
   - 復用：options_quant 的 `_connect`/`realized_vol_annualized`/`percentile_verified`/`fetch_vrp_history`；foreign_structure 的 `zscore`
   - 新純函式（TDD）：`detect_events(series, z_th, decluster_min)`、`forward_returns(bars, event_times, horizons)`、`event_vs_baseline(events, uncond)`
   - `tests/test_vix_signal_study.py`：事件偵測/去叢集/前瞻報酬對齊（含跨收盤截斷）約 6-8 案例
3. 執行研究 → **`analysis/vix_signal_validation_20260826.md`**：五訊號效度表 + 分層表 + verification log + 誠實的統計力聲明
4. 結論分級：VALIDATED（n≥20 且命中率/效果量過門檻）/ WEAK / INSUFFICIENT — 只對 VALIDATED 提出（不實作）接入建議（如 ma-touch 型盤中 alert）

## 驗證

```bash
.venv/bin/python -m pytest tests/test_vix_signal_study.py -q   # 純函式全綠
.venv/bin/python scripts/vix_signal_study.py                    # 跑完整研究
# 報告落 analysis/ + 推 inbox topic=vix-study (report_path 全文轉 Discord)
# 抽查: S1 事件表任取 2 筆, 手動對 iv_metrics/ohlcv_1m 原始列驗證對齊正確
```

## 風險/限制（誠實面）

- 63 交易日僅含一次大波動事件（7 月崩跌）— 事件型訊號的樣本可能集中在單一 regime，報告將按月分段檢視穩定性
- TXF 連續月換月跳價：前瞻報酬跨結算日的事件標記排除
- 若全部訊號 INSUFFICIENT，這本身就是有價值的結論（防止拿 54 天日級數據過度交易）
