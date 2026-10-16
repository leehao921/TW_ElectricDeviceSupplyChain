# Discord 洗版修正 — forwarder 去重 + trail_daemon 移 #guli + 源頭節流

## Context
10/15 台積電事件窗口 3 則推播被淹沒: #guyu 24h 收 311 則,其中 trail_daemon 268 則,
244 則是同一樣板 `base/trend TMFJ6: 24h stress cap X->Y lot (equity …) — post-fill book must survive …`。
來源: `nautilus-shioaji/scripts/trail_daemon.py:5577` `_stress_capped_qty()` — 每個機器進場的閘門,
每次輪詢重算,cap 持續生效就每次 `publish_alert` (WARN)。與 09-22 governor alert storm 同型
(當時以存 hold 讓下一輪不重算/不重 WARN 修)。使用者選三項全做:

1. My-TW forwarder 去重 (安全網,所有來源受惠)
2. trail_daemon 路由改 #guli (系統) — #guyu 只留精選交易警報
3. nautilus 源頭節流 stress cap WARN

## 1. forwarder 去重 — `My-TW-Coverage/scripts/discord_forward.py`
- 新純函式 `dedupe_signature(fields) -> str|None`:
  - 有 `report_path` 的報告不去重 (每日一次、全文)。
  - `topic ∈ TEMPLATE_DEDUPE_TOPICS` (預設 trail_daemon/trail-daemon/placer_rejects/collector_health_watchdog/loop_execution_agent):
    以「數字→#、空白壓縮」後的樣板做簽章 (數字不計)。
  - 其他 topic: **完全相同**訊息才算重複 — 避免 iv-snapshot、gex-regime、event-window 這類「固定樣板、只換數字」被誤擋。
  - 簽章 = topic + sha1(正規化訊息)[:16]。
- `forward_entries` 在組訊息前查 Redis hash `discord:forward:dedupe` (field=簽章, value=JSON {sent_ts, suppressed}):
  - 60 分鐘 (`DEDUPE_WINDOW_S=3600`) 內已送 → 不送、suppressed+1、cursor 照前移、log `suppressed <id> topic=… sig=…`。
  - 超過窗口或首次 → 送出;若 suppressed>0,訊息首行尾加「(過去 60 分重複 N 次)」;重設 {sent_ts=now, suppressed=0}。
  - hash 清理: 每次寫入時順手刪除 sent_ts 超過 24h 的 field (避免無限成長)。
  - Redis 錯誤 → fail-open (照送),不擋推播。
- 不改 cursor / partial / dead-letter / limiter 既有語義;被抑制的 entry 視同「已處理」。

## 2. trail_daemon 移 #guli — 同檔路由表
- `TRADING_TOPICS` 移除 `trail_daemon`、`trail-daemon`;`TRADING_PREFIXES` 移除 `trail_`、`trail-` → route_topic 落到 system (#guli)。
- 其他 loop_*/margin_guard/position-watch/gex-regime/event-window/iv-snapshot 維持 #guyu。
- 更新相關測試期望 (既有測試若斷言 trail_daemon=trading 屬刻意變更)。
- 部署: `launchctl kickstart -k gui/$UID/com.lulala.discord-forward` (路由表只在啟動時載入)。

## 3. 源頭節流 — `nautilus-shioaji/scripts/trail_daemon.py` `_stress_capped_qty()`
- 只改 WARN 發送,不改 cap 計算與回傳值 (交易邏輯不動)。
- `capped < fire_qty` 時: 狀態字串 `f"{fire_qty}->{capped}"`;Redis key `h:trail:stress_warned:{label}:{code}`
  - 值不同 (狀態變化) 或 key 不存在 (TTL 60 分到期) → `publish_alert` + `r.set(key, state, ex=3600)`
  - 值相同 → 只寫 `logger.debug`,不發 WARN。
  - Redis 例外 → 照舊發 (fail-open)。
- 測試: nautilus `tests/unit/` 新增 `test_trail_stress_warn_throttle.py` (fake redis / MagicMock): 同狀態連續兩次只 publish 一次、狀態變化再發、cap 值回傳不變。沿用既有 `tests/unit/test_trail_governor_hold.py` 的 fake redis 寫法。
- 部署: trail daemon 是 live 交易程序 (`com.lulala.trail-daemon`),**需重啟才載入**。只在非交易時段 (13:45–15:00 或 05:00–08:45) 重啟,重啟前跟使用者確認;nautilus repo 在 `main` 跑 live,不切 branch,直接在 main commit;push 前確認。

## 關鍵檔案
- My-TW: `scripts/discord_forward.py`、`tests/test_discord_forward.py`、plan 存 `docs/plans/2026-10-16-discord-dedupe.md`
- nautilus: `scripts/trail_daemon.py` (`_stress_capped_qty`)、`tests/unit/test_trail_stress_warn_throttle.py`

## 流程 (TDD)
各純函式/行為先寫失敗測試: dedupe_signature (樣板 topic 忽略數字、一般 topic 需完全相同、報告不去重)、
窗口內抑制+計數、窗口後附「重複 N 次」、Redis 失敗照送、route_topic(trail_daemon)=system、
nautilus stress WARN 節流三案例。

## 驗證
1. My-TW 全套測試 + pre-commit;nautilus `pytest tests/unit/test_trail_stress_warn_throttle.py` + trail 相關單元測試。
2. **重播驗證**: 以 claude:inbox 近 24h 實際 entries 跑去重模擬 (不送),列出各頻道前後則數 — 預期 #guyu 311 → ~45、
   trail_daemon 268 → 約 20 (移 #guli)、iv-snapshot/gex-regime/event-window 則數不變。
3. forwarder kickstart 後觀察 30 分鐘 log: 出現 `suppressed …`、trail_daemon class=system。
4. trail daemon 於非交易時段重啟後,`h:trail:stress_warned:*` key 出現,inbox 中同樣板 stress cap 每小時 ≤1 則。
5. 記憶: 更新 reference_discord_forward_routine (去重規則、trail_daemon 改 #guli)。
