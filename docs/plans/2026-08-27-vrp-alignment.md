# VIX/VRP 三層錯位修復 — 30 天常數期限 IV × 對齊 RV

## Context

用戶確認 VRP 讀數「IV 25.9 vs RV 12.1」存在三層時間錯位：(1) 方向錯位（天生，不修）；(2) **長度錯位** — IV 期限隨到期日每日收縮（21→1 天）且 RV 僅用 45 分鐘窗估年化；(3) **成分錯位** — RV intraday-only vs IV 含隔夜。本計畫建 CBOE 式 **30 天常數期限 IV（vix_30d）** 與 **含隔夜的 21 交易日 RV（rv_21d）**，產生同尺度的 **vrp_30d**，把 (2)(3) 修掉。

關鍵探索發現（options_iv_collector.py:1028-1121）：iv_metrics 的 `near_month_iv/far_month_iv` = **最近兩個到期**（far 常為週選、非次月）— 不可用於 CM30。正確原料是**逐到期列**：`product_code='TXO'`（三個近月月選）的 per-expiry `atm_iv` + `expiry` 欄，T = expiry − date 自算。

## 設計

**vix_30d（CBOE 式變異數-時間內插）**：
- 每日收盤窗（13:00–13:46）取每個 TXO 月選到期的最後一筆 atm_iv
- 選 T1 ≤ 30 < T2 的兩個月選（無法包夾時取最近兩個、權重 clamp [0,1] 並計數揭露）
- σ30 = sqrt( [w·T1·σ1² + (1−w)·T2·σ2²] / 30 )，w = (T2−30)/(T2−T1)，×100 慣例刻度

**rv_21d（含隔夜）**：`ohlcv_1m_txf`（8/27 修復的連續視圖）每日最後 close → 21 交易日 close-to-close log 報酬 std × √252 × 100 — 跨日報酬天然含隔夜/週末 variance

**vrp_30d = vix_30d − rv_21d** — 兩腿同為 ~30 天尺度、同含隔夜。

## 實作

1. **database repo `scripts/collectors/vix_daily.py`**（擴充現有 collector）：
   - `ALTER TABLE vix_daily ADD COLUMN IF NOT EXISTS vix_30d/rv_21d/vrp_30d DOUBLE PRECISION`
   - 新純函式 `cm30_interpolate(pairs: [(T_days, iv)], target=30) -> (vix30, clamped: bool)`（python 端做包夾/clamp 邏輯）
   - `derive_cm30(conn, backfill)`: 逐日查 TXO 月選 per-expiry 收盤窗 atm_iv → 內插 → UPSERT；rv_21d 由 ohlcv_1m_txf 日收盤 rolling 算；沿用既有 incremental（近 5 日）/--backfill 模式
   - **database repo `tests/test_vix_daily.py`**（新）：cm30 內插數學（包夾權重/變異數-時間/clamp）、rv rolling、邊界（單一到期/缺日）約 6 案例
2. **My-TW `scripts/margin_vix_daily.py`**：日報加一行 `VIX30 xx.x · RV21 xx.x · VRP30 +x.x (pct nn)` — percentile 經 n≥20 guard（復用 options_quant `percentile_verified` 模式）；tests 補 render 案例
3. 全歷史 backfill（iv_metrics 5/27 起；rv 需 ohlcv_1m_txf 4/24 起 ✓ 無 warm-up 缺口）
4. 不動 options_quant 的窗內 VRP（它的 percentile 設計在窗內自洽、用途不同）；記 follow-up：S4 訊號研究待 vrp_30d 累積後重跑

## 驗證

```bash
cd database && .venv/bin/python -m pytest tests/test_vix_daily.py -q
docker exec ... python scripts/collectors/vix_daily.py --backfill   # 全歷史 derive
# 抽查: 任取 2 日, 手算 T1/T2/權重/σ30 對照庫值; vix_30d vs 舊 vix (近月) 應在結算週前後分歧最大
.venv/bin/python scripts/margin_vix_daily.py                        # 日報含 VIX30 行
# vrp_30d 全序列 sanity: 應大多為正 (保費), 7 月崩跌期間收窄/翻負
```

## 風險/限制

- 方向錯位（層 1）天生不可修 — vrp_30d 仍是「預期 vs 剛發生」
- 月選只有 3 個近月 → T2 上限 ~63 天，30 天包夾在結算日前後 1-2 天可能失敗 → clamp 並在列上標記（報告揭露 clamp 天數占比）
- vix_daily 既有 `vix`（近月）欄保留 — 敏感度儀表與 CM30 序列並存，各司其職
