# LPPLS 台股泡沫偵測 — Phase 1 驗證研究 Design Spec

**日期:** 2026-08-27
**狀態:** 已與用戶確認設計方向
**定位:** 泡沫警戒燈（不做空、不出 trade directives）— 高檔警戒收割輔助，配合左側交易哲學

---

## 背景與目標

LPPLS (Log-Periodic Power Law Singularity) 模型假設泡沫由正回饋迴路驅動，價格從線性成長轉為超指數加速，波動以遞增頻率震盪逼近臨界奇點 tc（預測崩盤日）。原始參考文獻（用戶提供的 QuantConnect 研究）在美股 100 檔流動性 universe 上 Sharpe 0.503 vs SPY 0.4，但 max drawdown 51.7%、PSR 12.5% — 做空執行噪音極大。

本專案不複製做空策略，目標收斂為：**驗證 LPPLS 在台灣電子權值指數上是否具泡沫警戒力**，通過事前定義的準則才進 Phase 2（每日 routine）。

**核心決策（用戶已確認）：**
1. 先驗證再上線 — Phase 1 walk-forward 研究，通過才做 routine
2. 擬合標的 = 自建電子權值指數（`stock_daily_ohlcv` 399 天），TAIEX 184 天交叉驗證
3. OFI/IV/法人/融資 = confirmation 分層，不進擬合（模型保持純價格、可對照文獻）
4. 警戒燈定位，不做空

---

## 資料盤點（2026-08-27 實測）

| 表 | 範圍 | 用途 |
|---|---|---|
| `stock_daily_ohlcv` | 2025-01-02 → 2026-08-26，399 交易日，938 檔 | 指數建構主源 |
| `taiex_ema_daily` | 2025-11-20 → 2026-08-25，184 天，TAIEX close | proxy 交叉驗證 |
| `futures_ohlcv` (TXF 1D) | 2026-03-26 起 | 太短，不用於擬合 |
| `stock_ofi` | 2026-05-28 起，20 檔權值股＋14 族群聚合，盤中 | confirmation 第 4 層 |
| `iv_metrics` / `vix_daily` | 2026-05-28 起，~60 天 | confirmation 第 3 層 |
| `institutional_stock` | 2025-01-02 起，938 檔 | confirmation 第 2 層 |
| `margin_market_daily` | 2026-07-14 起，31 天 | confirmation 第 1 層 |

DB 連線沿用 `scripts/options_quant.py` 的 `DB_CONFIG`（tmf_market_data，read-only）。

---

## 架構：四個模組

### 1. 指數建構 (`scripts/lppls/index_builder.py`)

- 成分：OFI 追蹤的電子權值股（2330、2317、2454、2308、3711、2382、2379、2303、2357、3231）＋市值前段電子股補足至約 15-20 檔（市值取自 Pilot_Reports metadata 或 shares × price）
- 權重：市值權重 snapshot，Laspeyres 定基：`index_t = Σ wᵢ × (Pᵢ,t / Pᵢ,0)`
- 合格判定：與 TAIEX 184 天重疊區間**日報酬相關 > 0.95**；不合格則擴大成分股再驗
- 此指數同時作為台指期 proxy（TXF-TAIEX 基差極小，期貨日線歷史不足以直接擬合）

### 2. LPPLS 擬合核心 (`scripts/lppls/fitter.py`)

方程式：`ln p(t) = A + B(tc−t)^m + C1(tc−t)^m cos(ω ln(tc−t)) + C2(tc−t)^m sin(ω ln(tc−t))`

- 線性參數 (A, B, C1, C2)：加權 OLS normal equation `Z = (XᵀWX)⁻¹(XᵀWy)`，W 對角、近期日上權（指數衰減）
- 非線性參數 (tc, m, ω)：grid seeds → scipy Nelder-Mead 精修，選 SSE 最小者
- 物理約束（全部須過，否則棄擬合）：
  - `0 < m < 1`（超指數假設）
  - `6 ≤ ω ≤ 13`（Sornette 文獻標準泡沫頻帶）
  - `tc ∈ (t_last, t_last + 60 交易日)`
  - `B < 0`（正泡沫）
  - damping：`m·|B| ≥ ω·|C|`，`C = sqrt(C1²+C2²)`
- 訊號條件：tc 在 30 天內 + `R² ≥ 0.7`（門檻進 HPO）+ 約束全過
- 實作驗證：TDD 用合成 LPPLS 序列（已知參數生成＋噪音）測參數還原；另以 ETH `lppls` pip 套件對同序列 cross-check，tc 差異過大即警示

### 3. Walk-forward 驗證 (`scripts/lppls/walkforward.py`)

- Window 100 天（HPO 掃 70-140 step 10）、每 5 交易日 refit、399 天全程
- 事件集：指數滾動高點回落 ≥5% 的所有回檔（讓資料說話，不預設）
- **事前通過準則（寫死，不得事後放寬）：**
  1. ≥5% 回檔事件中，至少半數在事前 30 天內出現過 LPPLS 訊號
  2. False positive（訊號後 20 天內未跌 >3%）比率 < 50%
  3. 訊號日 20 天 forward return 分布劣於無訊號日（中位數比較＋rank test）
- 誠實警告：399 天內回檔事件預期僅 2-4 次，統計力天生有限；結果模糊就寫模糊（延續 study 系列誠實負結果傳統）

### 4. Confirmation 分層 (`scripts/lppls/confirmation.py`)

LPPLS 出訊號時計算，各層 z-score 化後計分（同向 +1，滿分 4）：

| 層 | 來源 | 泡沫確認邏輯 |
|---|---|---|
| 融資增速 | `margin_market_daily` | 散戶槓桿加速 = 正回饋實證 |
| 法人動向 | `institutional_stock` | 外資連買轉賣 = 高檔調節 |
| IV 結構 | `iv_metrics`/`vix_daily` | term slope 倒掛、VRP 壓縮、skew 陡化 |
| OFI 失衡 | `stock_ofi` | 價漲但買方 OFI 衰竭背離 |

4/4 = 強警戒、2-3 = 中性、≤1 或背離 = 降級。歷史短（31-90 天），Phase 1 僅對近期訊號回填、不進通過準則 — 作為 Phase 2 routine 的 dry-run。

---

## 產出

1. 計畫：`docs/plans/2026-08-27-lppls-tw-bubble-detection.md`（writing-plans 產出，TDD 步驟）
2. 研究報告：`analysis/lppls_study_2026-08-27.md`，含 Verification log（Golden Rule 0：分布性措辭先跑驗證）
3. 判定：
   - 通過 → Phase 2 設計（launchd routine：收盤後 refit + confirmation score + inbox `topic=lppls` + watchdog 納管）
   - 未通過 → 誠實負結果收檔，commit 報告

## 明確排除（YAGNI）

- 做空 / 任何 trade directives
- OFI 進擬合權重 W（實驗性、難驗證，已與用戶確認排除）
- 個股逐檔 LPPLS（Phase 1 不做；若指數版通過可另議）
- TXF 期貨序列直接擬合（歷史不足）

## 錯誤處理

- DB 缺日 / 停牌：成分股缺價當日以前值遞補（forward-fill），連缺 >5 日剔除該成分並記錄
- 擬合不收斂：記為 no-fit，不產訊號（不以劣質擬合充數）
- 非線性優化失敗：grid seed 最佳解 fallback，標記 `refined=False`
