# Discord 手機排版 (2026-10-06)

## 問題 (實測近 3 日 inbox → build_report_messages)
手機 Discord code block 一行約 40 等寬字,超出需左右捲動;一般文字會自動換行。
- markdown 表格被轉成等寬 code block: routine-synthesis 最寬 426、warrant-flow 132、
  etf-smart-money 117、news-pulse 88、foreign-structure 66、memory-cycle 54。
- txf-levels: 梯圖 ≤41 OK,但同一 code block 內的文字行達 73 (IV curve…)。
- `---` 不渲染 (原樣顯示);`#` 標題手機過大;Discord 只支援 #/##/###。

## 設計 (forwarder 層,producer 不動;只改排版不改內容)
MOBILE_W = 40 (顯示寬,CJK=2)。
1. 表格: 渲染寬 ≤ MOBILE_W → 維持 code block;否則「卡片」: 每列 `**首欄**`,其餘欄
   `▸ 表頭：值` 各一行 (空值略過),列間空行。不在 code block → 粗體/emoji 正常渲染、自動換行。
2. code block 內 > MOBILE_W 的行: 在空白處斷行,續行縮排 2 格;無空白可斷則保留原樣。
3. code block 外: `---`/`***`/`___` → `━━━━━━━━━━`;`# ` → `## `,`## ` → `### `,`###+` → `**粗體**`。
4. 套用於 msg 摘要與報告全文 (build_report_messages),在切段之前。

## 驗證
單元測試;以近 3 日真實 inbox 重算: code block 最寬行 ≤ 40 (無空白可斷者除外),送一則
routine-synthesis 樣本到 #guli 實機目視。

## 附: IV 期限表 (2026-10-07)
用戶回饋「IV 數據不夠明顯，看不出價格之間的差關係」: 原本只有 `curve 1007:18.2 / 1012:16.3 / …`。
用戶選定「表格+點數區間」: 新純函式 scripts/iv_term.py `iv_term_lines(curve, forwards, ref, now)`:
每到期一行 `MM/DD 天 IV 差 ±1σ 區間`;σ點 = F×IV×√(距 13:30 結算天數/365),區間以該到期 forward 為中心;
差 = 與前一到期的 vol-pt 差;內部到期比前後都低/高 ≥1.0 → ⚠ 凹陷/凸起;近 > 次 ≥1.0 → ⚠ 前端倒掛。
每行 ≤ 40 字寬。接入 gex_regime_monitor (#guyu 事件訊息) 與 ascii_dashboard.vol_section_lines
(dashboard / txf-levels)。h:agent:gex_regime 機器 feed 不變。
