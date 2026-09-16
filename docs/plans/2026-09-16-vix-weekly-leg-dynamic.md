# vix_daily.vix_w 週選腿修復 — 拆掉寫死的 product_code

## Context

**問題**：`vix_daily.vix_w`（週選 IV）與 `wm_spread`（週/月結構價差）長期為 NULL。追下去發現寫死的 `product_code = 'TX2'`（`vix_daily.py:137`）—— TAIFEX 週選 root 每週輪替（TX1/TX2/TX4/TXU/TXV/TXX/TXY），寫死任何一個常數都保證會過期。**這是本輪第 4 處同型缺陷**（前三處：collector 訂閱、`IV_WEEKLY_PRODUCT_1`、`options_subscriber.py:229`）。

**實測規模比「六個交易日」嚴重 5 倍**：68 個交易日中只有 **19 日**有 `vix_w`（28%）。TX2 只在 7/06–9/09 掛牌，其餘日子 SQL 問一個不存在的 root → 無條件 NULL。

```
 rows | first      | last       | has_vix_w | null_vix_w
   68 | 2026-05-27 | 2026-09-16 |        19 |         49
```

**兩個必須先講清楚的重新理解**（它們改變了這個欄位的意義）：

1. **`vix_w` 從來不是「最前週選」**。它追的是 TX2 這個 root，而 TX2 的 DTE 在取樣期間從 **0 走到 14**。程式碼註解寫的「最敏感腿（7/29 崩跌 38 vs 月選 31 倒掛實證）」—— 7/29 那天 TX2 的 **DTE = 14**。那個 +8.23 的倒掛是「14 天 vs 30 天」，不是「前週 vs 30 天」。

2. **2026-09-01 的「報價品質 artifact」其實是選錯腿**。那天 TX2（DTE=8，冷門後週）收盤最後一筆印 **12.69**，而 TX1（DTE=1）印 **22.92**，月選 cm30 是 22.03。`weekly_iv_ok` guard 是為了擋一個症狀而寫的，病因是讀錯合約。

**靜默的來源**：`weekly_iv_ok:157` 對 `vw=None` 直接 `return True`，不 log。所以「查無候選」這條路徑**完全沒有任何輸出**。`grep -c "rejected by quote-quality guard" ~/Library/Logs/margin-vix.log` → **0**。

**我先前的歸因是錯的，本計畫一併更正**：我曾在 `vault/log.md` 與 `ascii_dashboard.py` 的 `fmt_num` docstring 寫「9/9 起因 quote-quality guard 為 NULL」。只有 9/1 是 guard（且 guard 判斷本身是對症不對因）；9/10 之後全是 root 寫死。

**下游**：兩個 consumer 都在說謊而不是報錯。
- `sf_pairs_weekly.py:281` 用 `WHERE wm_spread IS NOT NULL ORDER BY date DESC LIMIT 1` —— 沒有任何新鮮度檢查，六個交易日以來一直把 **9/8 的 -6.26** 當今日值印在 sf-pairs 週一交易計畫的「週/月 IV 倒掛」gate 上。修好後今日真值是 **+1.40**，差 7.7 點。
- `margin_vix_daily.py:52` 用 `if cm30.get("vix_w") is not None:` 包住整行 —— NULL 時整行消失，讀報的人看不出少了一行。

**用戶已定調**：口徑 = **最近週選 DTE ≥ 1**（排除結算日）；回補範圍 = **全回補並記錄改寫**。

**專案規則**：`CLAUDE.md` 規定 `trading-timescaledb` 對 My-TW-Coverage 唯讀、資料缺口一律在 `database` repo 修。本計畫主體（Task 1–3）**就在 `database` repo**，符合該規則；My-TW-Coverage 只改兩個讀端（Task 4）。

---

## 先確認的事實（read-only，已跑過）

**DTE=0 系統性是垃圾** —— 結算日 ATM IV 崩到個位數：

| 日期 | root | DTE | atm_iv | 同日 cm30 |
|---|---|---|---|---|
| 9/11 | TXV | 0 | **5.21** | 26.7 |
| 9/09 | TX2 | 0 | **5.37**（n_ticks=4） | 25.4 |
| 9/02 | TX1 | 0 | **6.26** | 24.6 |
| 9/04 | TXU | 0 | 18.53 | 24.7 |

四筆 DTE=1 樣本則全部合理（22.9 / 23.2 / 24.9 / 26.1 對 cm30 比值 0.79–1.05）。這就是 DTE≥1 門檻的實證基礎。

**`atm_iv` vs `near_month_iv`**：實測兩欄在週選 root 上**數值完全相同**（每個週選 root 當下只掛一個到期，該 product 的 front 就是該列自己）。所以這不是阻斷性 bug，但仍改用 `atm_iv` —— 它是語意正確的欄位（描述該列自己的 expiry），`CM30_SRC_SQL:119` 已是這個寫法，且若哪天一個 root 掛到兩個 expiry，`near_month_iv` 會靜默錯配。

**回補上限是 23/68，不是 68/68。** 週選 IV 在 `iv_metrics` 裡 **2026-07-06 才開始有**，且長期只訂到 1–2 個 root；三個 root 同時在線是**今天 09:04 weekly-root 修復之後才有**的事：

| root | 有資料天數 | 起 | 迄 |
|---|---|---|---|
| TX2 | 22 | 2026-07-06 | 2026-09-09 |
| TX1 | 4 | 2026-08-28 | 2026-09-02 |
| TXV | 7 | 2026-09-03 | 2026-09-11 |
| TXU | 2 | 2026-09-03 | 2026-09-04 |
| TXX / TX4 / TXY | 各 1 | 2026-09-16 | 2026-09-16 |

5/27–7/03 的 28 個交易日**永遠不可能**有 `vix_w`。9/12、9/15 亦無任何週選列（weekly-root 故障期）。這是資料上限，不是本次修法的缺陷 —— **必須寫進 log，不可讓 28% → 34% 看起來像「修好了」。**

---

## 全回補的完整影響（已預跑，這就是要存檔的 diff）

覆蓋 **19 → 23** 日。其中 **18 日數值不變**，實際異動 **7 日**（3 改寫 + 4 新增）：

| 日期 | cm30 | 舊 vix_w | 舊 wm | 新選腿 | DTE | 新 vix_w | 新 wm | 性質 |
|---|---|---|---|---|---|---|---|---|
| 8/28 | 27.19 | 21.05 | -6.14 | TX1 | 5 | **20.15** | **-7.05** | 改寫（原取 TX2 DTE=12） |
| 8/31 | 23.93 | 20.74 | -3.18 | TX1 | 2 | **22.05** | **-1.88** | 改寫（原取 TX2 DTE=9） |
| 9/01 | 22.03 | — | — | TX1 | 1 | **22.92** | **+0.89** | 修掉 12.69 假訊號 |
| 9/03 | 26.28 | 20.73 | -5.55 | TXU | 1 | **26.06** | **-0.23** | 改寫（原取 TX2 DTE=6） |
| 9/09 | 25.43 | — | — | TXV | 2 | **24.82** | **-0.61** | 新增 |
| 9/10 | 27.51 | — | — | TXV | 1 | **24.92** | **-2.59** | 新增 |
| 9/16 | 27.69 | — | — | TXX | 2 | **29.09** | **+1.40** | 新增（今日真值） |
| 9/11 | 26.67 | — | — | （只有 DTE=0） | — | NULL | NULL | 維持 NULL，符合口徑 |

**對倒掛 gate（>+2）的影響比預期小 —— 兩個歷史校準錨點都沒被動到**：7/29 的 +8.23（TX2 DTE=14）與 8/5 的 +10.45（TX2 DTE=7）在新規則下仍是同一條腿、同一個值。異動的 7 日全落在 -7.1 ~ +1.4 區間，沒有任何一日跨過 +2。也就是說：**歷史上沒有任何一次倒掛警報會因這次回補而增減**，但今日 gate 從假的 -6.26 變成真的 +1.40。

---

## 缺陷表

| # | 缺陷 | 位置 | 後果 |
|---|---|---|---|
| **D1** | `product_code = 'TX2'` 寫死 | `vix_daily.py:137` | root 輪替即失效；68 日只 19 日有值 |
| **D2** | 無 DTE 門檻 | 同上（無此概念） | 選到 DTE=0 崩壞報價，或 DTE=14 被當「最敏感腿」 |
| **D3** | 查無候選時完全靜默 | `weekly_iv_ok:157` `return True` | 壞了兩個多月沒有任何一行 log |
| **D4** | INSERT fallback 算了 `vw`/`wm` 卻只寫 5 欄丟掉 | `vix_daily.py:201-207` | 事故缺口日即使有週選也永遠是 NULL |
| **D5** | 下游把 NULL 當「沒事」而非「壞了」 | `margin_vix_daily.py:52`；`sf_pairs_weekly.py:281` | 整行消失／拿六天前的值冒充今日 gate |

---

## Task 1 — 動態選腿（database repo, TDD）

**檔案**：修改 `scripts/collectors/vix_daily.py`；測試 `tests/test_vix_daily.py`

**約束**：`tests/conftest.py` 會 patch `psycopg2._psycopg._connect` 使其**拋例外**，除非 `TMF_ALLOW_REAL_DB=1`（起因是 2026-09-15 測試 fixture 的 `expiry='FG6'` 寫進了 production `iv_metrics`）。repo 內零個 DB-backed 測試。**所有新測試必須是純函式測試**，吃 plain tuple，照 `cm30_interpolate` / `weekly_iv_ok` 既有慣例。

### 1a. 換掉 `WEEKLY_IV_SQL`

```sql
WEEKLY_IV_SQL = """
  WITH ranked AS (
    SELECT time::date AS d, product_code, expiry, atm_iv * 100 AS iv_pct,
           row_number() OVER (PARTITION BY time::date, product_code, expiry
                              ORDER BY time DESC) AS rn,
           count(*)     OVER (PARTITION BY time::date, product_code, expiry) AS n_ticks
    FROM iv_metrics
    WHERE underlying = 'TX'
      AND product_code ~ '^TX[0-9A-Z]$' AND product_code <> 'TXO'  -- 週選 root, 每週輪替
      AND EXTRACT(dow FROM time) NOT IN (0, 6)
      AND time::time BETWEEN '13:00' AND '13:46'
      AND atm_iv BETWEEN 0.05 AND 1.5
      {date_filter})
  SELECT d, product_code AS root, iv_pct, n_ticks,
         (CASE WHEN expiry ~ '^[0-9]{{8}}$' THEN to_date(expiry, 'YYYYMMDD') END - d) AS dte
  FROM ranked WHERE rn = 1
  ORDER BY d, dte
"""
```

三個易錯點：
- **`{{8}}` 必須雙括號** —— 這個字串會過 `.format(date_filter=...)`，單括號會被當成 format 佔位符炸掉。
- **`CASE` 不可寫成 `AND expiry ~ ...`** —— Postgres 不保證 WHERE 子句求值順序，畸形 `expiry` 會讓 `to_date()` 直接 hard-error 整個查詢（`conftest.py` 記錄的 `FG6` 事故正是這種列真的進過 production）。用 `CASE` 讓畸形值變 NULL，交給純函式過濾。
- `row_number()` 取代 `DISTINCT ON`，順便白拿 `n_ticks`（9/09 TX2 只有 **4 筆** tick vs TXV 264 筆 —— 這正是需要審計欄位的理由）。

### 1b. 新增純函式 `pick_weekly_leg`

放在 `weekly_iv_ok` 上方，照 `cm30_interpolate` 的 tuple-in / tuple-out 慣例：

```python
MIN_WEEKLY_DTE = 1          # 排除結算日: DTE=0 的 ATM IV 會崩到 5-6 (9/11 5.21, 9/09 5.37, 9/02 6.26)

def pick_weekly_leg(legs, min_dte: int = MIN_WEEKLY_DTE):
    """從當日所有週選候選挑「最近且尚未結算」的那條腿。

    legs: [(root, dte, iv_pct, n_ticks), ...] —— 同一交易日的全部週選 root。
    回傳 (iv_pct, root, dte)；無可用候選回 (None, None, None)。
    同 DTE 平手時取 tick 數多者 (報價厚度 = 可信度)。
    """
```

過濾條件：`dte is not None and dte >= min_dte and iv_pct is not None`；排序鍵 `(dte, -n_ticks)`。

### 1c. `weekly_iv_ok` 加 `same_contract` kwarg

換腿日 DTE 會鋸齒（週四 DTE=1 → 週五 DTE=5），DTE=1 與 DTE=5 的 ATM IV 天生差 30–50%，`max_jump=0.30` 會在多數週五誤殺好資料。**實測必要性**：9/03 TXU(DTE=1) 26.06 → 9/04 TX2(DTE=5) 17.66 是 **-32.2%**，沒有這個 kwarg 就會被 null 掉。

```python
WEEKLY_LEVEL_BAND = (0.6, 1.8)   # vw/vix30 合理水平帶 (同時用於同約大跳動與換約日)

def weekly_iv_ok(vw, prev_vw, vix30, prev_vix30,
                 max_jump: float = 0.30, same_contract: bool = True) -> bool:
```

- `same_contract=False` → 跳過跳動檢查，只套 `WEEKLY_LEVEL_BAND`（DTE=0 的 0.19–0.25 比值仍會被擋下，作為 DTE 門檻的第二道防線）。
- 預設 `True` → **現有 5 個 guard 測試一字不改全數通過**。

呼叫端以 **expiry 而非 root** 判定同約（root 輪替但 expiry 穩定）：`d + timedelta(days=dte) == prev_expiry`。

### 1d. 測試（`tests/test_vix_daily.py` 新增）

| 測試 | 輸入 → 期望 |
|---|---|
| `test_pick_weekly_leg_takes_nearest_non_expiry` | `[("TXX",2,29.09,264),("TX4",7,20.60,264),("TXY",13,21.06,264)]` → `(29.09,"TXX",2)` |
| `test_pick_weekly_leg_skips_settlement_day` | `[("TXV",0,5.21,245)]` → `(None,None,None)`（9/11 實況） |
| `test_pick_weekly_leg_falls_through_to_next_week` | `[("TX1",0,6.26,270),("TX2",7,22.15,270)]` → `(22.15,"TX2",7)`（9/02 實況） |
| `test_pick_weekly_leg_2026_09_01_regression` | `[("TX1",1,22.92,271),("TX2",8,12.69,40)]` → `(22.92,"TX1",1)` — **本計畫的核心回歸** |
| `test_pick_weekly_leg_tiebreak_on_tick_count` | 同 DTE、tick 4 vs 264 → 取 264 那條 |
| `test_pick_weekly_leg_tolerates_null_dte` | `dte=None`（畸形 expiry 經 `CASE` 變 NULL）不得拋例外 |
| `test_pick_weekly_leg_empty` | `[]` → `(None,None,None)` |
| `test_weekly_guard_skips_jump_check_across_contracts` | 26.06→17.66 / cm30 24.65, `same_contract=False` → **True**（9/3→9/4 實況） |
| `test_weekly_guard_still_rejects_absurd_level_across_contracts` | 5.21 / cm30 26.67, `same_contract=False` → **False** |
| `test_weekly_guard_default_is_same_contract` | 不傳 kwarg 時行為與舊版一致 |

跑：`cd /Users/lulala/Documents/coding/database && .venv/bin/python -m pytest tests/test_vix_daily.py -v`

---

## Task 2 — 審計欄位、INSERT fallback、打破靜默（database repo）

**檔案**：`scripts/collectors/vix_daily.py`（`DDL:20-37`、`derive_cm30:167-213`）

### 2a. 三個審計欄位

沿用檔內既有的 `ADD COLUMN IF NOT EXISTS` 慣例（`DDL:31-36`）：

```sql
ALTER TABLE vix_daily ADD COLUMN IF NOT EXISTS vix_w_root  TEXT;
ALTER TABLE vix_daily ADD COLUMN IF NOT EXISTS vix_w_dte   INTEGER;
ALTER TABLE vix_daily ADD COLUMN IF NOT EXISTS vix_w_ticks INTEGER;
```

**不論 guard 是否拒收都要寫入 root/dte/ticks**，於是得到一個可查詢的不變量：

| `vix_w` | `vix_w_root` | 意義 |
|---|---|---|
| NULL | NOT NULL | 有候選但被拒 / 只有 DTE=0 → 可追查 |
| NULL | NULL | 當日根本沒有週選腿 → collector 問題 |
| NOT NULL | NOT NULL | 正常 |

### 2b. 修 D4 —— INSERT fallback 補回 6 欄

`:201-207` 目前算完 `vw`/`wm` 後只 INSERT 5 欄，把值丟掉。補上 `vix_w, wm_spread, vix_w_root, vix_w_dte, vix_w_ticks`，`ON CONFLICT DO UPDATE` 子句同步加上。

### 2c. 修 D3 —— 讓「查無候選」發得出聲音

- 新增 `missing_n` 計數器。
- 無候選 → `logger.warning("%s: 無可用週選腿 (候選 %s) — vix_w=NULL", d, legs or "無")`，把被排除的 `(root, dte)` 一起印出來，讓「只有 DTE=0」與「完全沒有週選列」在 log 上長得不一樣。
- roll-up 加欄位：`logger.info("... weekly: picked %d, guarded %d, missing %d", ...)`。
- **非 backfill 路徑**（每日 18:10 實跑）當 `missing_n == n` 且 `n > 0` → `logger.error(...)`，這是「又一次全線壞掉」的訊號。

### 2d. pandas 查表陷阱

`:173-174` 現在是 `.set_index("d")["vix_w"]` → 得到 **Series**，`weekly[d]` 是標籤查找。改成多欄後變 **DataFrame**，`weekly[d]` 會被當成**欄位名**查找並拋 `KeyError`。必須改用 `weekly.loc[d]`（並先 `if d in weekly.index`）。同時兩個 query 都要保留 `time::date AS d` 讓 dtype 一致 —— 否則 index 型別不合會**靜默地一列都對不上**。

---

## Task 3 — 全回補並存檔 diff（database repo）

用戶決策：**全回補並記錄改寫**。

**部署前提**：`docker-compose.yml:922` 是 `./scripts:/opt/tmf/scripts:ro`，而 `vix_daily.py` 是每次 `docker exec` 現拉現跑的一次性腳本（不是常駐 mounted-code process）。因此**改檔即生效、不需要 `docker restart`** —— `feedback_collector_restart_discipline` 在此不適用，理由要寫進 commit message 免得下次自己懷疑。

步驟：

1. **存 before 快照**
   ```bash
   docker exec trading-timescaledb psql -U tmf -d tmf_market_data -At -F, -c \
     "SELECT date, vix_w, wm_spread FROM vix_daily ORDER BY date" > /tmp/vix_w_before.csv
   ```
2. **跑回補**
   ```bash
   docker exec -e PYTHONPATH=/opt/tmf:/opt/tmf/src tmf-stock-daily-collector \
     python scripts/collectors/vix_daily.py --backfill
   ```
3. **存 after 快照**（同一條 SQL，加上 `vix_w_root, vix_w_dte, vix_w_ticks`）
4. **寫 diff 文件** `/Users/lulala/Documents/coding/database/docs/2026-09-16-vix_w-backfill-diff.md`，內容：口徑變更說明（TX2 寫死 → 最近週選 DTE≥1）、上面那張逐日 before/after 表、覆蓋率 19→23/68、**23/68 是資料上限的說明**（週選 IV 7/06 才開始、9/12+9/15 無週選列）、以及「倒掛 gate 的兩個歷史錨點 7/29 +8.23 與 8/5 +10.45 未受影響」這項結論。

**實跑結果必須與上面預跑的 23 列表格逐格比對**；任何一格對不上就是實作與設計脫節，停下來查，不要接受。

---

## Task 4 — 下游停止說謊（My-TW-Coverage）

### 4a. `scripts/margin_vix_daily.py:52-60`

把 `if cm30 and cm30.get("vix_w") is not None:` 的 early-skip 拆掉，改成**永遠輸出這一行**，NULL 時印 `週選IV n/a · 週/月結構: n/a`。缺值要看得見才會有人修。順手把選腿資訊掛上去：`週選IV(TXX D2) 29.1 · 週/月結構: ⚠️ 微倒掛 +1.4`。

複用本 repo `ascii_dashboard.py:103-118` 已存在的 `fmt_num(v, spec, na="n/a")` 與 `wm_label(wm, threshold=2.0)` —— 不要再寫一份格式化邏輯（上一輪的教訓就是 helper 存在卻沒被套滿）。

### 4b. `scripts/sf_pairs_weekly.py:281`

拿掉 `WHERE wm_spread IS NOT NULL`，改成取**最新一列**並同時取 `date`：陳舊（`date` 非最近交易日）或 NULL 時 gate 顯示 `– (週選資料缺, 日期 X)` 並**停用 🚨 判定**，而不是拿六天前的值冒充。對齊本輪已定調的「硬 gate：標 STALE 停用規則」原則。

---

## Task 5 — 更正錯誤歸因 + 記錄

- `vault/log.md`：append 本次條目（寫死 root 的第 4 次、19/68 實測、兩個重新理解、23/68 上限），並**明確更正**先前那條「9/9 起因 quote-quality guard 為 NULL」的錯誤歸因。依 `feedback_vault_maintenance`。
- `scripts/ascii_dashboard.py` 的 `fmt_num` docstring 與 `tests/test_ascii_dashboard.py:46` 的註解區塊：同一個錯誤歸因寫在那裡，一併改掉。
- `redis-cli XADD claude:inbox` topic=`margin-vix`：廣播口徑變更（TX2 → 最近週選 DTE≥1）＋今日 `wm_spread` 從假的 -6.26 更正為真的 +1.40，欄位格式照 `scripts/bb_inbox_alert.py`。
- commit 分兩 repo、依 conventional commits，WHY 寫「root 輪替 → 任何寫死常數必過期，這是第 4 處」。

---

## 復用清單

| 要做的事 | 已存在的東西 |
|---|---|
| 純函式測試慣例（吃 tuple、零 DB） | `vix_daily.py` `cm30_interpolate` + `tests/test_vix_daily.py` 9 個測試 |
| `atm_iv` 對應該列自己的 expiry | `CM30_SRC_SQL:119`（已是正確寫法） |
| 加欄位不破壞既有表 | `DDL:31-36` 的 `ADD COLUMN IF NOT EXISTS` idiom |
| 週選 root 的正則 | `options_iv_collector.py:372` `_TW_INDEX_OPT_CODE_RE` |
| None-safe 格式化 / 倒掛標籤 | `ascii_dashboard.py:103-118` `fmt_num` / `wm_label` |
| inbox 廣播欄位格式 | `scripts/bb_inbox_alert.py` |

---

## 驗證

1. **純函式測試**：`cd /Users/lulala/Documents/coding/database && .venv/bin/python -m pytest tests/test_vix_daily.py -v` → 舊 9 個 + 新 10 個全綠，且舊 5 個 guard 測試**未經修改**。
2. **本 repo 測試**：`.venv/bin/python -m pytest tests/ -q` → 維持 692 passed 基線（Task 4/5 不得打破）。
3. **回補 diff 逐格比對**：實跑結果 vs 本計畫預跑的 23 列表格，必須完全一致。
4. **不變量查詢**：
   ```sql
   SELECT date, vix_w, vix_w_root, vix_w_dte, vix_w_ticks, wm_spread
   FROM vix_daily WHERE date >= '2026-08-26' ORDER BY date;
   ```
   期望 9/16 = `29.09 / TXX / 2 / 264 / +1.40`；9/11 = `NULL / TXV / 0`（有候選但只有 DTE=0，可追查）；9/12、9/15 = root 亦為 NULL（無週選列）。
5. **下游即時驗證**：直接跑 `scripts/margin_vix_daily.py` 的 dry-run 路徑 → 週選行出現且帶 root/DTE；跑 `scripts/sf_pairs_weekly.py` → gate 顯示 `+1.4` 而非 `-6.26`。
6. **明日 18:10 live 驗收**（關鍵）：`com.lulala.margin-vix` 自動跑完後 `vix_daily` 當日 `vix_w_root` 是當週真實 root、`missing` 計數為 0、inbox 日報週選行有值。
7. **日誌可見性負向測試**：暫時把 `MIN_WEEKLY_DTE` 調到 99 跑一次非 backfill → 必須看到 `無可用週選腿` WARNING 與 `missing == n` 的 ERROR，確認靜默真的被打破後改回。

---

## 明確排除

- **回補 5/27–7/03 的 `vix_w`**：`iv_metrics` 該期間無任何週選列，物理上不存在，不做假資料。
- **9/12、9/15**：weekly-root 故障期無資料，永久缺漏。
- **`options_subscriber.py:229` 的 `IV_WEEKLY_PRODUCT_1="TX5"`**：同型第 5 處寫死，但該 subscriber 目前 `OPTIONS_SUBSCRIBER_WRITE_DB="false"` 不寫庫，無實害。已記錄為 shioaji-broker Phase-4 切換前的必修項，另案。
- **倒掛門檻 >+2 的重新校準**：本次回補未改動任何歷史倒掛事件（7/29 +8.23、8/5 +10.45 皆不變），門檻維持現值；若日後要重校準需另跑 `scripts/verify_flow_zscore.py` 走 Golden Rule 0 流程。
- `tests/test_ev_calculator_integration.py` 的既有 collection error（`ModuleNotFoundError: basis_enhanced_ev_calculator`）—— 先前就存在，不在本計畫。

---

## 實作後更正（2026-09-16，計畫執行完畢後補記）

計畫在執行中被實測推翻了三處。保留原文、在此更正，不回頭改寫歷史。

**1. `same_contract` 的「實測必要性」是錯的。**
Task 1c 寫「9/03 TXU(DTE=1) 26.06 → 9/04 TX2(DTE=5) 17.66 是 −32.2%，沒有這個 kwarg 就會被 null 掉」。寫測試時追實際邏輯才發現：那個 −32.2% 的跳動與同日 cm30 的下行（26.28 → 24.65）**同向**，方向檢定直接放行，接著水平帶 0.7166 也在 [0.6, 1.8] 內 → 兩種判定都回 `True`。**9/3→9/4 根本不需要這個 kwarg 來救。**

`same_contract` 仍然保留，但定位改為**前瞻性防護**：動態選腿讓 DTE 每週鋸齒（週四 D1 → 週五 D5），D1 與 D5 的 ATM IV 天生差 30–50%，若哪天換約剛好碰上「weekly 因期限結構走低、cm30 走高」，反向檢定就會誤殺好資料。這是本次改動**自己製造**的 hazard，一併堵掉。已改用真正有鑑別力的對抗測試（`test_roll_day_opposite_direction_is_not_rejected`，cm30 *上行*）驗證，並加 `test_real_2026_09_03_to_09_04_roll_passes_either_way` 明確記錄「9/3→9/4 不是它救的」，免得日後誤讀。

**2. `atm_iv` vs `near_month_iv` 的說法過度宣稱。**
唯讀查詢證實兩欄在週選 root 上**數值完全相同**（每個週選 root 當下只掛一個到期）。改用 `atm_iv` 是語意正確性與未來防護，不是阻斷性 bug。計畫「先確認的事實」段已修正，程式註解亦然。

**3. 計畫漏掉一個缺陷，驗證步驟 4 才把它逼出來。**
`pick_weekly_leg` 選不到腿時回 `(None, None, None, None)`，於是「只有 DTE=0」與「完全無週選列」在表上同形 —— Task 2a 宣稱的不變量（`vix_w NULL + root NOT NULL → 有候選但被拒`）實際是假的。補了純函式 `audit_leg`（TDD，5 個測試）：選腿失敗時仍記下最近候選。現在 9/11 = `NULL / TXV / 0 / 245`，與計畫驗證步驟 4 的期望一致。

**4. 驗證步驟 7（負向日誌測試）順手抓到第二個缺陷。**
`def pick_weekly_leg(legs, min_dte: int = MIN_WEEKLY_DTE)` 的預設值在 def 時凍結，事後改模組屬性無效，但 WARNING 的門檻字串是呼叫時才格式化 → log 印 `DTE>=99` 卻照樣選到腿。改用 `None` 哨兵，加測試 `test_module_constant_is_the_single_source_of_truth` 釘住。

**5. 日期更正。** 先前說「9/12 + 9/15 無週選列」—— 9/12 是**週六**，不是缺口。實際的近期缺漏是 9/11（只有 DTE=0）、9/14（`iv_metrics` 當日 TX 一列都沒有，連 `vix_daily` 都無該列）、9/15（有月選無週選）。

### 驗收結果

| 項目 | 結果 |
|---|---|
| database 純函式測試 | **28 passed**（舊 9 個 guard/cm30 測試一字未改） |
| My-TW-Coverage 測試 | **703 passed, 2 skipped**（基線 692 + 新增 11） |
| 回補 diff | 與計畫預跑的 7 列**逐格一致** |
| 回補冪等 | 連續兩次 `--backfill` 產出相同 |
| 審計不變量 | `invariant_violation = 0`、`dte_floor_violation = 0` |
| 靜默已打破 | WARNING 列出被排除的候選；全線缺腿升級 ERROR |
| 今日 gate | 假的 −6.26（9/08 舊值）→ 真的 **+1.40** |
