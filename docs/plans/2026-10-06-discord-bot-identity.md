# Discord 三頻道改由各自 bot 發文 (2026-10-06)

## 背景
三頻道 webhook 路由已上線 (36a3547): trading→#guyu、reports→#lulu、system→#guli。
用戶要求各頻道以對應 bot 身分發文: Guyu→#guyu、Lulu→#lulu、Guli→#guli (真正 bot 身分,日後可加互動)。
權限實測: Lulu=Administrator; Guyu/Guli 可 View/Send #guyu、#guli (看不到 #lulu)。

## 設計
- `BotTarget(token, channel_id, fallback_url)`;`post_discord(target, content)`:
  BotTarget → POST /api/v10/channels/{id}/messages (Authorization: Bot …,
  allowed_mentions.parse=[] 避免 @everyone);str → 原 webhook 路徑。
- 429 退避、永久 4xx → PermanentPostError 規則不變 (沿用 dead-letter / 斷點續送 / limiter)。
- **安全網**: bot 回 401/403 (token 被 reset / 權限被拔) 且有 fallback_url → 該則改走 webhook,
  log warning,不進 dead-letter。
- `resolve_targets()`: 每 class 若 `DISCORD_BOT_TOKEN_<BOT>` 與 `DISCORD_CHANNEL_ID_<CLASS>` 皆有
  → BotTarget(fallback = 該 class webhook);否則 webhook URL (行為同前)。
  BOT 對應: trading=GUYU、reports=LULU、system=GULI。
- token 只在 database/.env,log 不印 token。

## 驗證
- 單元測試 (mock requests): BotTarget 端點/標頭/payload、401 fallback、resolve_targets 混合配置。
- daemon kickstart 後各頻道送一則,確認作者為對應 bot。
