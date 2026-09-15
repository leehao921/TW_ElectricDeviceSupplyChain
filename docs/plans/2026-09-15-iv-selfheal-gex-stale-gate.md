# IV collector 自癒修復 + GEX 陳舊資料硬 gate — 實作計畫

## Context

**事故**：2026-09-14（週一）options-IV collector 全天死亡，`iv_metrics` / `iv_strikes` 產生 **75.8 小時資料空洞**（9/11 夜盤後 → 9/16 09:00 容器重啟），且**沒有任何自動偵測、沒有任何自動復原**。週二早上是靠一次無關的容器重啟才恢復。

**根因鏈**：Shioaji `SessionNotEstablished` → `list(TXO/TX2/TX1/TXU/TXV)` 全失敗 → fallback 走 `_rebuild_contracts_via_cache()` → `/root/.shioaji` 是**未掛載的容器暫存層、沒有任何 parquet** → `Resolved 0 expiries` 每 5 分鐘重複一整個交易日 → 零訂閱 → 零寫入。整條自癒路徑結構上不可能生效。

**下游污染**：`ascii_dashboard.compute_gex` 的 96h IV lookback（2026-09-07 為修週一 `flip=UNKNOWN` 而加）把「缺資料」轉成更糟的「**靜默陳舊**」——週一與週二 08:40 都把**上週五的 flip=46500 當成當日值發佈**，期間 spot 從 46070 走到 45577。`data/gex_history.json` 因此留下兩筆 `iv_asof` 完全相同（`2026-09-11 20:59:55`）卻 net 不同的幽靈觀測（9/14 net=32.3億、9/15 net=62.0億）；`h:agent:txf_levels:latest` 今晨仍掛著 `flip_asof=2026-09-11`、`gamma_regime=BELOW_FLIP`。

**額外發現（用戶原本不知道）**：`com.lulala.dashboard`（08:30）**已連續 crash 四個交易日**（9/10 起 exit 1）。`vix_daily.vix_w` / `wm_spread` 自 9/9 起因 quote-quality guard 合法為 NULL，而 `vol_section_lines` 用 `f"{None:+.1f}"` 直接 `TypeError`。同一個例外也讓 08:40 level map **靜默掉了波動率＋法人兩個區塊**（兩者共用同一個 try）。

**目標**：(1) 讓 collector 在 0-expiry 時真的自己重啟；(2) 讓監控讀對欄位、真的能發現死掉；(3) 讓 GEX consumer 對陳舊 IV **硬 gate（標 STALE、停用規則）**而不是照發；(4) 修掉四天無人知的 dashboard crash。

**已確認不可逆**：9/14 的 tick 級 IV 無法事後回補，`vix_daily` 9/14 永久缺漏。本計畫不做回補。

---

## 五個缺陷（根因表）

| # | 缺陷 | 位置 | 後果 |
|---|---|---|---|
| **D1** | `/root/.shioaji` 未掛載 volume，contract cache 隨容器消滅 | `database/docker-compose.yml` options-iv-collector volumes 段（~520-585） | cache fallback 結構上永遠失敗，冷啟即死 |
| **D2** | `_resolve_expiries` 把「0 expiries」當正常返回 | `options_iv_collector.py:583-590` | status 保持 OK；tick-starvation watchdog 因無訂閱可餓而永不觸發 |
| **D3** | watchdog 與 healthcheck 都讀 `last_write_ts`（5 秒 liveness 心跳）而非 `last_db_write_ts`（真實寫入訊號） | `collector_health_watchdog.py:102`；`docker-compose.yml` healthcheck ~602 | 程式活著但零寫入 → 監控全綠。collector 自己在 `:1522-1525` 已註記該讀哪個欄位，consumer 沒跟上 |
| **D4** | consumer 無條件接受 96h lookback 的陳舊 IV | `txf_level_map.py:1001`、`:1192-1193`；`ascii_dashboard.py:81` | 連兩天把上週五 flip 當今日值發佈，`flip_asof` 有曝光但無人 gate |
| **D5** | `:+.1f` 套在 None 上 | `ascii_dashboard.py:115-116`；`txf_level_map.py:1048-1062` 單一 try 包住兩區塊 | 08:30 dashboard 整支 exit 1（4 天）；08:40 map 靜默掉 VIX＋法人 |

---

## Task 1 — 掛載 Shioaji contract cache（database repo）

**檔案**：`/Users/lulala/Documents/coding/database/docker-compose.yml`

- 新增 named volume `shioaji_cache`（top-level `volumes:` 段）。
- 掛到**每一個會做 Shioaji login 的容器**的 `/root/.shioaji`：options-iv-collector、futures tick collector、stock-ofi-collector、broker（4 sessions 終態）。
- 目的：讓 `_rebuild_contracts_via_cache()`（`options_iv_collector.py:410-462`，會 glob `~/.shioaji/contracts-*-OPT-*.parquet`）在正常登入時累積 parquet，冷啟才有東西可退。

**驗證**：容器重啟一輪後 `docker exec tmf-options-iv-collector ls /root/.shioaji/` 看到 `contracts-*-OPT-*.parquet`；`docker volume inspect` 確認 volume 存在且非 anonymous。

**注意**：此 task 需 `docker compose up -d` 重建容器 → 依 `feedback_collector_restart_discipline`，commit 不等於部署完成，必須跟著重啟＋看 log 驗證。

---

## Task 2 — 0-expiry 視為 FAILED 並自動重啟（database repo, TDD）

**檔案**：
- 修改：`src/tmf/data/pipeline/options_iv_collector.py`（`_resolve_expiries` 尾段 `:583-590`）
- 測試：該 repo `tests/` 下對應 options_iv 測試檔（無則新建 `tests/test_options_iv_selfheal.py`）

**設計**：把判斷抽成**純函數**便於測試（DB/Shioaji 耦合不進測試）：

```python
def should_exit_on_empty(resolved: int, in_session: bool, streak: int, max_fails: int) -> tuple[bool, int]:
    """回傳 (是否應 exit, 更新後的 streak)。
    resolved>0 → streak 歸零。
    非交易時段 → streak 不累加（收盤後 0 expiries 是正常的）。
    """
```

- 交易時段內連續 `WATCHDOG_MAX_FAILS`（現值 3，即 ~15 分鐘）次 0-expiry → `sys.exit(1)`，由 `restart: unless-stopped` 接手重啟 → 重新登入 Shioaji。
- **復用既有 pattern**：`options_iv_collector.py:1601-1604` 已有一模一樣的 `sys.exit(1)` 自癒寫法（tick starvation），照抄其 log 格式與 exit code。
- 交易時段判斷復用 `collector_health_watchdog.py:65-73` 的 `_taifex_open()` 邏輯（日盤 08:45-13:45 ＋ 夜盤 15:00-05:00 跨午夜）。若該 repo 內已有等價 helper 優先用既有的。
- 成功解析時把 status 寫回 `OK`，失敗時寫 `DEGRADED`/`FAILED` 進 `h:health:options_iv`。

**測試案例**：resolved>0 歸零、盤中連 3 次 → exit、盤中 2 次不 exit、非盤中 10 次不 exit、exit 後 streak 重置語意。

---

## Task 3 — 監控讀對欄位（兩 repo）

**檔案**：
- `/Users/lulala/Documents/coding/nautilus-shioaji/scripts/collector_health_watchdog.py:101-103`
- `/Users/lulala/Documents/coding/database/docker-compose.yml` healthcheck（options-iv ~596-616；stock-ofi 同段落）

**改動**：
1. watchdog 與 healthcheck 一律優先讀 `last_db_write_ts`，**缺欄位時才 fallback 到 `last_write_ts`**（向後相容尚未更新的 collector）。
2. healthcheck 加**交易時段 gate**：options-iv 與 stock-ofi 的 120s 門檻只在盤中生效，收盤後不判 UNHEALTHY。這修掉今天觀察到的 `tmf-stock-ofi-collector` 收盤後必紅的假陽性（9/15 資料實際 60,300 列完全正常）。
3. `last_db_write_ts` 的門檻要比心跳寬（IV 寫入節奏非 5 秒）——取 `STALE_THRESHOLD_SEC`（現 180）或視實際寫入間隔調整，log 要印出讀到哪個欄位以便日後 debug。

**注意**：`institutional` 不在 `SESSION_BOUND_COLLECTORS`（`:60-62`），今天 16:07 那筆「institutional heartbeat stale」也是假陽性；本 task 順手評估是否納入 session gate（資料實際 16,737 列正常）。

---

## Task 4 — GEX 陳舊硬 gate（My-TW-Coverage, TDD）

**檔案**：
- 修改：`scripts/txf_level_map.py`（`_get_gex` 663-703、call site 1001、`build_struct_fields` 1192-1193）
- 測試：`tests/test_txf_level_map.py`

**核心：陳舊判定必須是「日曆感知」而非固定秒數。** 週一 08:40 最新合法 IV 就是上週五夜盤（~51.6h 齡，對比週二中位 3.7h），`age > 24h` 會每週一誤報。

```python
def gex_staleness(iv_asof: datetime, as_of: date) -> tuple[bool, float]:
    """iv_asof 必須落在「前一個交易日」的日盤或夜盤區間內，否則 STALE。
    回傳 (is_stale, age_hours)。
    """
```

已用兩個真實案例驗證此述詞：
- 週二 08:40，iv_asof=週五 20:59 UTC → **STALE** ✓（正確抓到本次事故）
- 週一 08:40，iv_asof=週五 20:59 UTC（＝週六 04:59 TPE，落在週五夜盤內）→ **FRESH** ✓（不誤報）

**不要復用 `txf_level_map.py:996` 的 `t1 = today - timedelta(days=1)`** — 那是天真日曆 T-1，正是本述詞必須自己算交易日的原因。

**行為（用戶決策：硬 gate）**：
- payload 新增 `gex_stale`（0/1）、`gex_age_hours`。
- STALE 時 `gamma_regime="STALE"`，**但 flip / gex_total / gex_gross 欄位保留**（供人工判讀，不供規則使用）。
- `data/gex_history.json` 該筆記錄標 `iv_stale: true`，日後同 DTE 百分位取樣必須排除。
- ASCII 輸出加一行明示警告（例：`⚠ GEX 資料陳舊 (IV 齡 XX.Xh) — flip 規則停用`）。

**測試**：上述兩案例、邊界（iv_asof 剛好落在前一交易日夜盤起訖）、`iv_asof=None`、連假情境。

---

## Task 5 — None-safe 格式化＋拆開共用 try（My-TW-Coverage, TDD）

**檔案**：
- 修改：`scripts/ascii_dashboard.py` `vol_section_lines`（103-134，崩點在 115-116）
- 修改：`scripts/txf_level_map.py:1048-1062`
- 測試：`tests/test_ascii_dashboard.py`（無則新建）

1. `vol_section_lines` 所有 `:+.1f` / `:.1f` 欄位改走 None-safe 格式化 helper，None 印 `n/a`；倒掛判斷 `wm and wm > 2` 的 None 分支明確輸出 `n/a` 而非 `正常`（現在 None 會被當正常，語意錯誤）。
2. `txf_level_map.py:1048-1062` 把包住 `vol_section_lines` 與 `inst_section_lines` 的**單一 try 拆成兩個獨立 try** — 一邊掛掉不該連帶消滅另一邊，且 except 要 log 出 traceback 而非靜默吞掉（本次事故就是靜默吞了四天）。

**天然回歸 fixture**：`vix_daily` 目前 9/9 起 `vix_w`/`wm_spread` 就是 NULL，直接跑真資料即可驗證。

---

## Task 6 — 善後：資料標記、廣播、記錄

- `data/gex_history.json`：把 9/14、9/15 兩筆手動標 `"iv_stale": true`（兩筆 `iv_asof` 皆為 `2026-09-11 20:59:55`，同 IV 不同 spot，為幽靈觀測）。
- `redis-cli XADD claude:inbox` topic=`coordination`：向 nautilus consumer 廣播新欄位 schema（`gex_stale` / `gex_age_hours` / `gamma_regime="STALE"`），明確指引「`gamma_regime=="STALE"` 時所有 gamma 規則停用，flip 值僅供人看」；並聲明 9/14、9/15 兩日 GEX 讀值作廢。欄位格式照 `scripts/bb_inbox_alert.py`。
- `vault/log.md` append 事故條目（時間線＋五缺陷＋修法），依 `feedback_vault_maintenance`。

---

## 復用清單

| 要做的事 | 已存在的東西 |
|---|---|
| 自癒重啟 | `options_iv_collector.py:1601-1604` 的 `sys.exit(1)` + `restart: unless-stopped` |
| 交易時段判斷 | `collector_health_watchdog.py:65-73` `_taifex_open()` |
| 正確健康訊號欄位 | `options_iv_collector.py:1517-1530`（含 1522-1525 的說明註解） |
| state file 冪等讀寫 | `scripts/geo_composite_daily.py` `_load_state`/`_save_state` |
| inbox 廣播欄位格式 | `scripts/bb_inbox_alert.py` |
| 測試結構慣例 | `tests/test_txf_level_map.py` |

---

## 驗證

1. **兩 repo 測試全綠**：本 repo `.venv/bin/python -m pytest tests/ -q`；database repo 同法跑新增的 self-heal 測試。
2. **Dashboard 不再 crash**：直接跑 `scripts/ascii_dashboard.py`（現行 `vix_daily` NULL 即天然 fixture）→ exit 0，波動率區塊出現 `n/a` 而非崩潰。
3. **Level map `--dry-run`**：JSON 合法，含 `gex_stale=1`、`gex_age_hours≈96`、`gamma_regime="STALE"`、警告行出現（因為此刻 IV 確實陳舊，這是**當下就能看到 gate 生效**的證據）。
4. **自癒實測**：以模擬 0-expiry（暫時指向不存在的 product code 或注入 stub）跑 3 個 cycle → 容器 `sys.exit(1)` 且 `docker ps` 顯示自動重啟、uptime 歸零。
5. **Cache volume**：正常登入一輪後 parquet 落在新 volume，且容器重建後仍在。
6. **監控欄位**：`redis-cli HGETALL h:health:options_iv` 有 `last_db_write_ts`；watchdog log 印出讀到該欄位；收盤後 `docker ps` 的 options-iv / stock-ofi 不再 UNHEALTHY。
7. **明晨 08:40 live**（關鍵驗收）：IV collector 正常寫入 → `gex_stale=0`、`gamma_regime` 回到 `BELOW_FLIP`/`ABOVE_FLIP`、`flip_asof` 為昨日、VIX＋法人區塊回到 08:40 推播中。
8. Commits 依 conventional 慣例分 task；vault＋inbox 廣播完成。

---

## 明確排除（不在本計畫）

- **回補 9/14 IV**：tick 級 IV 無法事後重建，`vix_daily` 9/14 永久缺漏。
- `gex_pct`（同 DTE 百分位）：需 ≥20 個乾淨交易日樣本，另案。
- 先前盤點出的其他缺口：GDELT 恢復、MOPS twse/tpex gap、warrant_flow 9/11+9/14 約 -40%、taiex_ema T-2 落後。
