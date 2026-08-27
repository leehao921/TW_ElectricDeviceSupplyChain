# 地緣風險歸因研究 (Geo-Attribution Study) — Design Spec

**日期:** 2026-08-27
**狀態:** 用戶已核准設計方向
**前情:** LPPLS Phase 1 負結果（analysis/lppls_study_2026-08-27.md）— 台股 2025-26 回檔為事件驅動非內生泡沫。本研究為對照組：測「外生衝擊指標有無領先性」。

---

## 研究問題

7 次回檔（自建電子權值指數滾動高點回落 ≥5%）的驅動事件，各類地緣/宏觀指標**誰領先、誰同步、誰沉默**？答案決定未來 geo-risk composite 中每個指標的角色（警戒 vs 確認）。不預設任何指標能預警。

## 事件集（沿用 LPPLS 研究，由 index_builder 重生成保持一致）

| # | 前高日 | 觸發日 | 最大深度 | 待標註 catalyst（Phase B 查證） |
|---|---|---|---|---|
| 1 | 2025-01-07 | 2025-01-13 | -30.9% | ? |
| 2 | 2025-08-13 | 2025-08-20 | -5.1% | ? |
| 3 | 2025-11-03 | 2025-11-18 | -8.6% | ? |
| 4 | 2026-02-25 | 2026-03-04 | -13.4% | ?（用戶提示：美伊衝突/油價） |
| 5 | 2026-05-14 | 2026-05-19 | -6.4% | ? |
| 6 | 2026-06-03 | 2026-06-08 | -9.5% | ? |
| 7 | 2026-06-22 | 2026-06-24 | -20.2% | ? |

（2025 關稅因子由用戶提示，落在哪次事件由 Phase B 查證，不預設。）

## Phase A：資料回補

### A1. GDELT backfill（database repo，擴充現有 collector — 不重造）
- `scripts/collectors/intl_events_daily.py` 新增 `--backfill START END` CLI 模式：以 `startdatetime`/`enddatetime`（YYYYMMDDHHMMSS）取代 `timespan=60d`，每 query 兩次呼叫（timelinevolraw + timelinetone），~6 個月一 chunk、沿用 `GDELT_SLEEP_S=12s` 與現有 `_GDELT_UPSERT`（upsert 冪等，重疊無害）
- `config/intl_events.json` 新增 query key `"mideast_oil": "(Iran OR Hormuz) (oil OR conflict)"`
- 回補範圍 2024-12-01 → 2026-06-01（涵蓋事件 1 前 30 日至事件 7；之後與現行 60d 窗銜接）
- 回補對象：tariff、taiwan_strait、tsmc、semi_export、mideast_oil（ai_capex/memory 非本研究指標，順手回補亦可但非必要）

### A2. Brent（本 repo，一次性）
- 研究 script 內以 yfinance 拉 `BZ=F` 日線 2024-12 → 今，cache 至 `analysis/cache/brent_daily.csv`（避免重跑重抓）；不建 collector（先例：taiex_ema_daily 亦 yfinance；若日後 composite 上線再入 tmf stack）

### 覆蓋現實（誠實邊界）
| 指標 | 覆蓋 | 本輪角色 |
|---|---|---|
| GDELT 5 keys（回補後） | 7/7 | 主檢驗 |
| Brent 衝擊 | 7/7 | 主檢驗 |
| USDTWD/DXY（fx_daily，2023-08 起） | 7/7 | 主檢驗 |
| 外資賣超加速（institutional_stock，2025-01 起） | 7/7 | 主檢驗 |
| TXO IV/term_slope（vix_daily，2026-05-27 起） | 2/7 | 案例研究，不進判定 |
| 融資（2026-07 起）/ Kalshi（2026-07 起） | 0/7 | 不檢驗，報告註記留待累積 |

## Phase B：Catalyst 標註

- 每事件 web research 驅動因子，標 confidence marker（官方公告/主流報導/推測），引來源
- 分類：關稅/貿易、地緣軍事（台海、中東）、油價/通膨、Fed/宏觀、產業內生（庫存/財報）、混合

## Phase C：領先/同步檢驗

### 指標定義（皆 z-score 化，基準=事件前 250 交易日或可得歷史）
- GDELT per key：`article_count` 7 日和 z、`avg_tone` 7 日均 z（tone 更負=惡化，取 −tone）
- Brent：5 日報酬絕對值 z（漲跌皆是衝擊：斷供漲、需求崩跌）
- USDTWD：5 日貶值幅 z；DXY：5 日升幅 z
- 外資：成分股 `foreign_net×close_price` 5 日和的 z（負向=賣超加速）

### 每格判定（指標 × 事件，觀察窗 = 觸發日前 30 交易日 ~ 後 5 交易日）
- **領先**：z>2 首見於觸發日前 ≥3 交易日
- **同步**：z>2 首見於觸發日 ±2 交易日
- **落後/沉默**：z>2 僅見於觸發日 +3 之後 / 全程未達

### 誤報率
非事件期（排除各事件 [−30, +20] 窗）中該指標 z>2 的日子，後 20 交易日指數未跌 >3% 的比率。與 LPPLS 的 FP 定義一致，可直接對照（LPPLS FP=80%）。

### 事前判定準則（寫死，實跑前定案）
指標獲「警戒角色」資格：**≥50% 覆蓋事件中領先 ≥3 交易日，且誤報率 <60%**。
只同步不領先 → 「確認角色」。全沉默 → 剔除。
（誤報門檻 60% 寬於 LPPLS 的 50%：警戒角色容許較高誤報，因後續還有確認層把關；此為 composite 的分層設計前提。）

## 產出

`analysis/geo_attribution_study_<date>.md`：事件標註表（含來源與 confidence）、指標×事件矩陣（領先/同步/沉默 + 領先天數）、每指標誤報率與角色判定、composite 設計建議或負結果。Verification log 含產出指令與資料覆蓋聲明。

## 明確排除

- 不改 LPPLS 模型（外生項與內生假設矛盾；兩軌並行）
- 不建 geo-risk composite routine（本研究結論決定是否建、怎麼建）
- margin/Kalshi 本輪不檢驗（覆蓋 0 事件）
- 不做因果推論 — 領先性 ≠ 因果，報告明示此限制

## 錯誤處理

- GDELT backfill 429：chunk 間 sleep 12s，429 時 backoff 90s×3 沿用現有 `_get_json`；單 chunk 失敗記錄續跑，結束時列缺口
- yfinance BZ=F 缺日：交易日曆差異屬正常，以指數交易日為準左對齊 forward-fill ≤3 日
- 指標歷史不足 250 日：以可得歷史計 z 並在矩陣格標註（min 60 日，不足則該格記「資料不足」）
