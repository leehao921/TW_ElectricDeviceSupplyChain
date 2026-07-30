# Discord 推送系統 — claude:inbox → Discord webhook forwarder

**日期**: 2026-07-30
**需求**: 用戶要求「做一個推送系統能推送到 discord 的 bot，目前 database 有 grafana 的推送，可以直接使用」。
**背景**: 先前通知通道為 macOS sticky dialog（15:50 daily synthesis）+ claude:inbox Redis stream。用戶手機/離機時看不到。database repo Grafana alerting 已設 Discord Incoming Webhook（`DISCORD_WEBHOOK_URL` 於 `database/.env`，gitignored）— 本系統直接複用同一 webhook（同一頻道收 Grafana 告警 + routine 推送）。

## 設計決策

1. **單一整合點 = claude:inbox forwarder**，不逐一改 10+ 支 routine。
   所有 routine（bb-squeeze、ma-touch、buy-list、news-pulse、daily-synthesis、disposition、watchdog…）都已寫 inbox，forwarder 消費 stream 即涵蓋全部，未來新 routine 自動納入。
2. **Webhook 而非 bot token** — Incoming Webhook 在 Discord 顯示即為 bot 發文，無需 bot 帳號/gateway 常駐；與 Grafana 同通道。單向推送符合需求（用戶要「推送給我」，非雙向指令）。
3. **Cursor-based、冪等** — Redis key `discord:forward:last_id` 記錄已轉發的 stream ID。首跑不回灌 579 筆歷史：cursor 初始化為當前最新 ID（只送「安裝完成」測試訊息）。每輪 `XRANGE (last_id, +]`，逐筆送出後前移 cursor（送失敗不前移 → 下輪重試，at-least-once）。
4. **Topic 過濾（blocklist）** — `wakegate` 每 ~15 分鐘發 INFO 價位 ping，會洗版。預設 blocklist = `{wakegate}`，其餘全轉發。用 blocklist 而非 allowlist：新 routine 不會被靜默漏掉。
5. **Discord 格式限制** — content ≤2000 字元：>1900 切多則（找換行斷點），每則加 `(1/3)` 頁碼。訊息格式 `**[topic]** severity emoji + msg`。webhook rate limit ~30/min：每則間 sleep 1s，單輪上限 25 則（超出留給下輪，cursor 保證不丟）。
6. **排程** — launchd `com.lulala.discord-forward` 每 300s（StartInterval，全週；inbox 無新訊息時 no-op 秒退）。venv python 直跑（TCC 教訓：不可經 /bin/bash）。
7. **Webhook URL 來源** — env `DISCORD_WEBHOOK_URL` 優先，fallback 解析 `../database/.env`（唯一真源，不複製 secret 到本 repo）。

## 檔案

| 檔案 | 內容 |
|---|---|
| `scripts/discord_forward.py` | 純函式：`parse_env_file`, `format_entry`, `chunk_message`, `should_forward`；I/O：`read_new_entries`(XRANGE), `post_discord`(requests, 429 退避), `main` |
| `tests/test_discord_forward.py` | TDD：env 解析、過濾、格式化、切段、cursor 前移邏輯 |
| `scripts/launchd/com.lulala.discord-forward.plist` | 300s interval, venv python |
| `scripts/routine_watchdog.py` | 不註冊（forwarder 非日報 routine；失敗下輪自癒） |

## 驗證

1. `pytest tests/test_discord_forward.py` 全綠
2. 手動 `--test` 送一則測試訊息 → Discord 頻道收到
3. `launchctl kickstart` 實際 launchd context 跑一輪（TCC 驗證）
4. 發一則 inbox 測試訊息 → 5 分內出現在 Discord
