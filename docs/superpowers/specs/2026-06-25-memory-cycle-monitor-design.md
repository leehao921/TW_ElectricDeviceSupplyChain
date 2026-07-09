# Memory Cycle Monitor — Design Spec

**Date:** 2026-06-25
**Owner:** felix0921
**Status:** Draft (awaiting user review)
**Targets:** 南亞科 (2408), 華邦電 (2344) — 純商品 DRAM beta sell-signal monitor
**Output of:** `scripts/memory_cycle_monitor.py`

---

## 1. Background and Motivation

兩家標的(2408、2344)沒有 HBM,純粹吃 HBM 排擠標準 DRAM 產能造成的 spillover 漲價超級循環。增量毛利率近 100% → 上去多甜、下來多狠,所以**第一個賣出訊號**比「賣在最高點」重要。

人工盯 DRAMeXchange / TrendForce / MU 法說會在多空轉折期會漏訊號。這支腳本把 5 個 leading signals 中 cost/signal 比最高的 3 個自動化,把人工 work 壓到「每月更新一次 YAML」。

**這份 spec 對應的母 framework** 已記錄在前次對話的 brainstorming output:三層 sell signals(產業面 → 技術面 → 估值溢價)、三段式 trim、兩檔差異。本支腳本只實作其中可自動化的 leading + 估值層。

---

## 2. Goals / Non-Goals

### Goals
- 每次手動執行,3 秒內產出當下燈號(綠/黃/紅)+ 三段 trim stage 推進狀態
- 輸出兩份成果:`docs/analysis/memory_cycle_YYYY-MM-DD.md`(人看 / commit) + Redis hash `h:agent:memory_cycle`(/loop agent 讀)
- 每月更新工作量 ≤ 5 個數字(DDR4 月報價、DDR5 季報價、MU guidance)
- 不依賴爬蟲;不依賴付費 API;不需要排程

### Non-Goals (v1)
- 不做月 KD / 量價背離技術指標(下一版加,屬「同步層」)
- 不做 EPS revision tracking(無免費資料源)
- 不做 SOX / KLAC 設備股交叉確認(留待 v2)
- 不做歷史回測;不做訊號發送(Slack / Email);不做排程
- 不嘗試自動爬 TrendForce / DIGITIMES — 經 brainstorming 確認太脆弱

---

## 3. Architecture

```
data/memory_cycle_inputs.yaml     ◀── 使用者每月編輯(~5 個數字)
        │
        ▼
┌─────────────────────────────────┐
│ scripts/memory_cycle_monitor.py │
│                                 │
│  - load_inputs(yaml)            │
│  - fetch_pb(yfinance) → S1      │
│  - calc_ddr_momentum() → S2     │
│  - fetch_proxies(yfinance) → S3 │
│  - aggregate_lights()           │
│  - render_markdown()            │
│  - publish_redis()              │
└─────────────────────────────────┘
        │
        ├─▶ docs/analysis/memory_cycle_YYYY-MM-DD.md
        └─▶ Redis h:agent:memory_cycle  (HSET fields per §7)
```

**Code layout:** single file `scripts/memory_cycle_monitor.py`, ~300 LOC, modular functions; shared helpers go in `scripts/utils.py` only if reused elsewhere.

**No new dependencies beyond what `update_financials.py` already uses** (`yfinance`, `pyyaml`, `redis-py`). The `redis-py` connection reuses the project's standard Redis config (same host/port that the `redis-trading` MCP points at).

---

## 4. Signals Computed in v1

### S1 — Valuation Premium (兩檔 P/B)

> **Superseded (2026-07-09, sub-project B Component 2):** S1 no longer uses yfinance `priceToBook`
> with absolute 1.8/2.5 thresholds. It now reads engine-A percentile lights (85/70 bands) from
> Redis hash `h:agent:pb_lights`. See docs/superpowers/plans/2026-07-09-pb-percentile-engine.md
> and /Users/lulala/.claude/plans/memoized-drifting-sky.md.

| Ticker | Yellow (begin trim) | Red (extreme, must sell) |
|---|---|---|
| 南亞科 2408.TW | P/B > 1.8x | P/B > 2.5x |
| 華邦電 2344.TW | P/B > 1.5x | P/B > 2.0x |

- **Source:** `yfinance.Ticker(symbol).info["priceToBook"]`
- **Fallback if `priceToBook` missing:** compute from `marketCap / bookValue * sharesOutstanding` (rare for TW tickers but possible)
- **Light:** worst of the two tickers determines S1 light

### S2 — DRAM Price Momentum (manual YAML)

Two sub-signals; the **worse** of the two determines S2 light.

**S2a — DDR4 8Gb 現貨價 MoM:**
| Light | Condition |
|---|---|
| 🟢 | 最新月 MoM ≥ 0% |
| 🟡 | 最新月 MoM < 0%(首次負 MoM) |
| 🔴 | 連續 2 個月 MoM < 0% |

**S2b — DDR5 16Gb 合約價 QoQ(雙閾值):**

需要 3 季資料才能計算「衰減」。若 YAML 只有 2 季,則僅套用絕對閾值,且「衰減」欄位顯示 `N/A`。

| Light | Condition(3 季資料齊全) | Condition(僅 2 季) |
|---|---|---|
| 🟢 | QoQ ≥ +10% AND 衰減 < 50% | QoQ ≥ +10% |
| 🟡 | QoQ < +10% OR 衰減 > 50% | QoQ in [+5%, +10%) |
| 🔴 | QoQ < +5%,或負 QoQ | QoQ < +5%,或負 QoQ |

> 「相對前一季衰減 > 50%」= 例如前一季 +20%、本季 +10% → 衰減 50%、觸發黃燈;前一季 +20%、本季 +9% → 衰減 55%、觸發黃燈。這抓得到「動能轉折」的早期。

### S3 — MU + Hynix 跨市場領先訊號

兩個輔助源,組合燈號:

**S3 主訊號 — MU 月線:**
- 取 MU 過去 13 個月的月 K 線(`yfinance.Ticker("MU").history(period="13mo", interval="1mo")`)
- 「月線轉弱」定義:**最新已收盤月份的 close < 前 3 個月(不含最新月)最低 close**。換言之,index = -1 為最新,比對 indices [-4, -3, -2]

**S3 輔助訊號 — Hynix `000660.KS` 月線:**
- 同上邏輯,只看方向(轉弱 / 未轉弱),不看絕對值。KRW 計價的方向訊號不受匯率影響

**S3 燈號(完整 truth table):**
| MU 月線 | Hynix 月線 | TW 月線(2408 或 2344 任一) | 燈號 | 說明 |
|---|---|---|---|---|
| 未轉弱 | (don't care) | (don't care) | 🟢 | 主訊號未觸發 |
| 轉弱 | 未轉弱 | (don't care) | 🟡 | 單頭警示 |
| 轉弱 | 轉弱 | 未轉弱 | 🔴 | 雙頭領先確認,TW 仍有先賣窗口 |
| 轉弱 | 轉弱 | 轉弱 | 🟡 | 領先窗口已關;TW 已同步跌,S3 不再領先 |

### S4 — 燈號彙總 + Trim Stage

**Overall light:**
- 🔴 = 任一 S1/S2/S3 為 🔴
- 🟡 = 否則,任一為 🟡
- 🟢 = 三者皆 🟢

**Trim stage(對應三段式 trim 的進度):**

每個訊號獨立貢獻一個 candidate stage;最終 stage = `max(所有 candidate)`,再與 state file 中的 historical max 取 max。

| 訊號狀態 | Candidate stage |
|---|---|
| S1 黃 或 S2 黃 (不分哪個) | 1 |
| S3 黃 (任一原因) | 2 |
| 任一 S1/S2/S3 紅 | 3 |
| 全綠 | 0 |

| Final stage | Action |
|---|---|
| 0 | HOLD;等下次更新 |
| 1 | 第一段 trim 30% |
| 2 | 第二段 trim 40%(累計 70%) |
| 3 | 第三段 trim 30%(累計 100%,止損 / 全砍) |

> Stage 推進是**單向**的:腳本維護 `data/memory_cycle_state.json` 記住歷史最高 stage,即使訊號短暫回綠也不會自動倒退。倒退需手動編輯 state file。

---

## 5. `data/memory_cycle_inputs.yaml` Format

```yaml
# 每月 TrendForce / DRAMeXchange 月報 + MU 季報出來後手動更新
# Source 標註是為了未來回溯時的審計
last_updated: 2026-06-25
notes: "Source: TrendForce 2026/06 monthly + MU FY26Q3 call 2026/06/24"

ddr4_8gb_spot_usd:
  - {month: "2026-04", price: 2.85}
  - {month: "2026-05", price: 3.12}
  - {month: "2026-06", price: 3.45}    # 最新

ddr5_16gb_contract_usd:
  - {quarter: "2026Q1", price: 4.20}
  - {quarter: "2026Q2", price: 5.10}   # 最新

# MU 法說最新 guidance(供報告人類段落引用,v1 不參與燈號計算)
mu_next_quarter_gm_guide: 0.86         # 86%
mu_next_quarter_rev_qoq: 0.20          # +20%
```

**Schema rules:**
- 至少 2 筆才能算 MoM;至少 2 筆才能算 QoQ。少於 2 筆 → 該子訊號設為 `N/A`,不參與燈號彙總
- DDR4 列表至少保留最近 4 個月(可算「連續 2 個月負 MoM」)
- DDR5 列表至少保留最近 3 季(可算「相對前一季衰減」)
- 超出範圍的舊資料可保留作 audit,腳本只取尾巴 N 筆

**State file:** `data/memory_cycle_state.json`(腳本維護,記憶 historical max stage)
```json
{"max_stage_seen": 1, "max_stage_first_seen_at": "2026-07-15"}
```

---

## 6. Markdown Report Skeleton

`docs/analysis/memory_cycle_YYYY-MM-DD.md`:

```markdown
# 記憶體週期燈號 — 2026-06-25

**總燈號:** 🟢 全綠   **Trim 進度:** 0 / 3   **下次更新建議:** 2026-07-25 前後
**下一段觸發:** S2a DDR4 首次負 MoM,或 S1 任一檔 P/B 進入警戒區

---

## S1 — 兩檔估值溢價
| 標的 | P/B | 警戒 | 極端 | 燈號 |
|---|---|---|---|---|
| 南亞科 2408 | 1.42 | >1.8 | >2.5 | 🟢 |
| 華邦電 2344 | 1.12 | >1.5 | >2.0 | 🟢 |

## S2 — DRAM 報價動能
- **S2a DDR4 8Gb 現貨 MoM:** +10.6%(3.45 vs 3.12) 🟢
- **S2b DDR5 16Gb 合約 QoQ:** +21.4%(5.10 vs 4.20);較前季 QoQ +N/A 衰減 N/A(僅有 2 季資料) 🟢

> 註:範例假設 YAML 只填 2 季 → 算得出 QoQ 但算不出「相對前季衰減」,故顯示 N/A 而不報黃燈。當第 3 季資料填入後,衰減欄位開始有值。

## S3 — 跨市場領先訊號
| Source | 月線狀態 | 燈號 |
|---|---|---|
| MU | 站上前 3 月低 | 🟢 |
| Hynix 000660.KS | 站上前 3 月低 | 🟢 |
| 2408 / 2344 | 站上前 3 月低 | 🟢 |

## Verification log
- Data source: `data/memory_cycle_inputs.yaml` last_updated 2026-06-25
- yfinance pulled at: 2026-06-25T08:15:00+08:00
- Historical max stage seen: 0(state file unchanged)

## Action
**HOLD** — 訊號全綠,等下次月報。下次手動更新 YAML 建議:2026-07-25 前後。
```

**Note on 量化主張驗證**(per CLAUDE.md Golden Rule 0):此報告所有數字都來自 YAML 或 yfinance,不包含「σ / 罕見 / 極端」分布性主張,故毋需呼叫 `verify_flow_zscore.py`。任何之後在報告中添加分布主張(例如「P/B 突破歷史 99 percentile」)必須先跑驗證腳本。

---

## 7. Redis Hash `h:agent:memory_cycle`

```
HSET h:agent:memory_cycle
  updated_at         "2026-06-25T08:15:00+08:00"
  overall_light      "GREEN"
  trim_stage         "0"
  max_stage_seen     "0"
  next_trigger       "S2a DDR4 首次負 MoM"

  s1_pb_2408         "1.42"
  s1_pb_2344         "1.12"
  s1_light           "GREEN"

  s2a_ddr4_mom_pct   "10.6"
  s2b_ddr5_qoq_pct   "21.4"
  s2b_ddr5_decay_pct "N/A"
  s2_light           "GREEN"

  s3_mu_monthly      "GREEN"
  s3_hynix_monthly   "GREEN"
  s3_tw_monthly      "GREEN"
  s3_light           "GREEN"

  report_path        "docs/analysis/memory_cycle_2026-06-25.md"
```

**TTL:** None(覆寫式更新)。

**Consumers:** future /loop agents 可讀此 hash 判斷是否該主動 trim 持倉;當前 v1 不接 /loop。

---

## 8. CLI Interface

```bash
# 主用法:讀 YAML + yfinance → 寫 Markdown + 推 Redis
python scripts/memory_cycle_monitor.py

# Dry-run:列在 stdout,不寫檔、不推 Redis
python scripts/memory_cycle_monitor.py --dry-run

# 離線模式:不推 Redis(例如外網不可達),仍寫 Markdown
python scripts/memory_cycle_monitor.py --no-redis

# 指定不同 YAML 路徑(測試用)
python scripts/memory_cycle_monitor.py --inputs path/to/test.yaml
```

**Exit codes:**
- `0` — success
- `1` — YAML 解析失敗 / 必要欄位缺失
- `2` — yfinance 拉資料完全失敗(網路問題)
- `3` — Redis 寫入失敗(`--no-redis` 時不會觸發)

---

## 9. Testing Strategy (TDD)

**File:** `tests/test_memory_cycle_monitor.py`

### Unit tests(必跑)
1. **YAML 解析:**
   - Happy path: 完整 YAML
   - Missing `ddr4_8gb_spot_usd` → 該子訊號為 N/A,但不 crash
   - 月份順序錯亂 → 按時間排序後處理
   - 少於 2 筆 → MoM/QoQ = N/A
2. **S1 P/B 燈號(邊界):**
   - 2408 P/B = 1.79 → 綠;P/B = 1.80 → 黃;P/B = 2.50 → 黃;P/B = 2.51 → 紅
   - 2344 P/B = 1.49 → 綠;P/B = 1.50 → 黃;P/B = 2.00 → 黃;P/B = 2.01 → 紅
   - 一檔黃 + 一檔綠 → S1 黃
3. **S2a DDR4 MoM 邏輯:**
   - 一個負月 → 黃
   - 連續 2 個負月 → 紅
   - 中間隔一個正月 → 燈號 reset(只看「連續」)
4. **S2b DDR5 QoQ 雙閾值:**
   - +21% → +10%(衰減 52%) → 黃
   - +21% → +12%(衰減 43%) → 綠
   - +5% absolute → 黃(<+10%)
   - +4% absolute → 紅(<+5%)
   - -1% → 紅
5. **S3 月線轉弱判定:**
   - Mock 13 個月的 close 序列,最新一根 < 前 3 月最低 → 轉弱
   - 邊界:= 前 3 月最低 → 未轉弱(取嚴格 <)
6. **S3 燈號組合矩陣:**
   - MU 弱 + Hynix 弱 + TW 強 → 紅
   - MU 弱 + Hynix 強 + TW 強 → 黃
   - MU 強 → 綠(不看 Hynix)
   - MU 弱 + Hynix 弱 + TW 也弱 → 黃(領先窗口已關)
7. **Trim stage 單調推進:**
   - state file max_stage_seen=2、本次計算出 stage=1 → 顯示 stage=2(取 max)
   - state file 不存在 → 建立,初始 max=當前 stage

### 不測
- yfinance 真實呼叫(用 fixture mock)
- Redis 真實連線(用 fakeredis 或 mock)
- Markdown 文字內容(只測核心數字 + 燈號,不測排版)

### Integration test(可選)
- 一個 `tests/fixtures/memory_cycle_full.yaml` + mocked yfinance → 跑完整流程 → 驗證 Markdown 包含預期 token + Redis hash 包含預期 fields

---

## 10. Implementation Order(供 writing-plans 參考)

依風險高→低排序;每步 TDD(RED-GREEN-REFACTOR):

1. **YAML loader + schema validation**(最先,因為一切下游都依賴)
2. **S2a DDR4 MoM 計算 + 燈號**(純函數,最容易測)
3. **S2b DDR5 QoQ 雙閾值**(純函數)
4. **S1 P/B 抓取 + 燈號**(加入 yfinance,先 mock)
5. **S3 月線轉弱 + 燈號組合**(同 4)
6. **Aggregate lights + Trim stage 單調推進**(state file I/O)
7. **Markdown renderer**(jinja2 或純 f-string)
8. **Redis publisher**(用 redis-py + env-var 設定)
9. **CLI argparse + exit codes**
10. **Integration test 跑通**
11. **Run dry-run on real data, eyeball Markdown, commit**

---

## 11. Open Questions(已解決,留紀錄)

- ✅ Data sourcing:Hybrid(yfinance + manual YAML)
- ✅ Output channel:Markdown + Redis hash
- ✅ Scope:Lean MVP(4 signals,不含技術面 / EPS revision)
- ✅ S2b DDR5 threshold:雙閾值(+5% red、衰減 >50% yellow)
- ✅ S3 Hynix:加入當輔助確認,主訊號仍是 MU
- ⏸️ 排程(cron/launchd)→ 不在 v1 範圍,日後再加
- ⏸️ /loop agent 整合 → 不在 v1 範圍,Redis hash 已預留欄位

---

## 12. Success Criteria

- [ ] 腳本可在 3 秒內完成 dry-run
- [ ] 所有 unit tests pass
- [ ] 用今天日期實跑一次,Markdown 報告產出在 `docs/analysis/memory_cycle_2026-06-25.md`
- [ ] Redis hash `h:agent:memory_cycle` 可由 `redis-cli HGETALL` 看到全部 fields
- [ ] 報告人工 review:燈號顯示「全綠」、Action 段落寫「HOLD」、下次更新建議日期合理
- [ ] commit message 用 `feat(monitor): add memory cycle sell-signal monitor`

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `yfinance` 拉 TW 股 P/B 偶爾回傳 None | Fallback 從 marketCap + bookValue 算;再失敗則 S1 = N/A 而不 crash |
| YAML 忘記更新導致 stale | Markdown 報告顯著顯示 `last_updated` 日期 + 「下次更新建議」日期 |
| Redis 連不上 | `--no-redis` flag 可跳過;exit code 3 警示 |
| 用戶誤改 state file 導致 stage 倒退 | 設計上允許(手動 override),不防禦 |
| TrendForce 報價單位 / 規格變更 | YAML 結構固定,只接受 USD per chip;若 source 改規格 by 用戶判斷重設 baseline |

---

*(End of spec — next step:user review → writing-plans skill for implementation plan.)*
