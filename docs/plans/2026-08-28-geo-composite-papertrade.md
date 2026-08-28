# Geo-Composite Paper-Trade 儀表 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** 把地緣歸因研究 v2 §4.4 的雙軸 composite 做成每日 paper-trade 巡檢：計分、記錄、靜默推播、自動對帳；累積 ≥2 個新 ≥5% 回檔事件後結算是否轉正式 routine。

**設計依據:** `analysis/geo_attribution_study_2026-08-28.md` §4.4（用戶已核准）。定位=環境警戒儀表，**paper-trade 期間警報不構成行動建議**。

**Architecture:** 復用 `scripts/geo_attr/`（indicators/loaders/leadlag 的 forward_return 語意）與 `scripts/lppls/`（index_builder、confirmation 的 margin scorer）。新增 `scripts/geo_composite_daily.py`（axis 評估 pure functions＋state＋inbox）與 launchd `com.lulala.geo-composite` Mon-Fri 18:20（margin-vix 18:10 後，當日 GDELT/法人/融資/IV 最齊）。

---

## 規格

### 雙軸定義（v2 報告 §4.4，寫死為 pre-registered config）

**事件強度軸** — 任一通道觸發即軸觸發：
- `regulation` 通道: `gdelt_semi_export_vol` z>2 **或** `gdelt_tariff_tone` z>2
- `rates` 通道: `ust10y_surge` z>2
- `oil` 通道: `brent_shock` z>2 **且** `gdelt_mideast_oil_vol` z>2（雙確認 — 兩者單獨 FAR 皆高）

**脆弱度軸** — 任一成分觸發即軸觸發：
- `iv`: vix_daily 最新 `term_slope` > 0（倒掛）或 `vrp_30d` < 0
- `foreign`: `foreign_sell` z>2
- `margin`: 融資 5 日增速 z>1（復用 `scripts/lppls/confirmation.py` 的 `score_margin`＋`load_margin`）

**警報 = 兩軸同時觸發**。單軸=黃燈，無=綠燈。

### 每日輸出

1. `data/geo_composite_state.json`：append 當日紀錄 `{date, light(綠/黃/紅), strength:{regulation,rates,oil,triggered}, fragility:{iv,foreign,margin,triggered}, z值明細, alerts_pending:[...]}`
2. inbox 推播（topic=`geo-composite`，欄位格式照 bb_inbox_alert.py）：一行狀態；紅燈標 `🚨 PAPER-TRADE 警報（非行動建議）`
3. **自動對帳**：state 中每筆滿 20 交易日未結的紅燈警報 → 以自建電子權值指數算 fwd20 min return，`< -3%` 記 hit 否則 false；結果寫回 state 並在當日推播附註（`對帳: X hit / Y false`）

### 結算條件（寫死）

自上線日起累積 ≥2 個新的 ≥5% 回檔事件後人工結算：紅燈是否於事件前 30 日內出現、live FAR 多少 → 決定轉正式 routine 或收檔。

### Cache 時效修正（live 前置需求）

`loaders.load_yf`：cache 最新日期 < 今日−1（日曆日）→ 重抓覆寫；否則直讀。研究情境不變（當日內重跑仍走 cache）。

---

## Tasks

### Task 1: loaders cache 時效 + composite 核心（TDD）

**Files:** Modify `scripts/geo_attr/loaders.py`；Create `scripts/geo_composite_daily.py`、`tests/test_geo_composite.py`

- [ ] 測試先行：
  - `load_yf` stale-cache 重抓（monkeypatch yfinance；fresh cache 直讀不觸網）
  - `evaluate_strength(zs: dict) -> dict`：regulation/rates/oil 通道邏輯（含 oil 雙確認）逐一觸發/不觸發
  - `evaluate_fragility(iv_inverted, vrp_neg, foreign_z, margin_score) -> dict`
  - `light(strength, fragility)`：紅/黃/綠三態
  - `settle_alerts(state, index_s, asof)`：滿 20 交易日對帳 hit/false 精確值（手算 fixture）；未滿者不動
- [ ] 實作：pure functions 與 I/O（state 讀寫、inbox XADD via redis-cli subprocess 照 bb_inbox_alert.py 慣例、z 計算復用 geo_attr_study.build_indicator_zoo 抽共用或按名取值）
- [ ] `python scripts/geo_composite_daily.py --dry-run`：印當日雙軸與燈號、不寫 state 不推播
- [ ] Commit

### Task 2: launchd 註冊 + live 驗證（controller 親自，涉 TCC）

- [ ] plist `com.lulala.geo-composite` Mon-Fri 18:20，照 margin-vix 現行模板（venv python 直跑，非 bash wrapper — TCC 教訓）
- [ ] `launchctl bootstrap` 註冊、`kickstart` 實跑一次，驗證 state 檔與 inbox 訊息
- [ ] watchdog 納管（`routine_watchdog` checks 20→21）＋ memory 檔記錄 routine
- [ ] Commit＋vault/log append
