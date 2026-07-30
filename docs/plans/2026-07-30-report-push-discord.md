# 排程報告全文推送 Discord + news_pulse 大盤新聞段

## Context

用戶要求：每天的 BB 分析、BB 追蹤分析、大盤新聞整理 — 所有排程內容都要推送 Discord，**以報告為主**。

現況缺口：`discord_forward.py`（昨上線）只轉發 inbox 短訊。bb-squeeze / bb-followthrough 的 inbox msg 本來就是完整報告 ✅；但 news-pulse / daily-synthesis / etf-smart-money / memory-cycle 只推一行摘要，完整報告（6–12KB md）留在 `analysis/` 沒到 Discord ❌。「大盤/總經新聞整理」則完全不存在。

用戶已定案：(1) 報告推送形式 = **附件 + 全文切段兩者都要**；(2) 大盤新聞 = **併入 news_pulse 20:35 晚報**，不加新排程。

## 設計

### A. discord_forward.py 擴充 — inbox 新欄位 `report_path`

有 `report_path` 的 entry：送摘要 → 報告全文切段（≤1900/段+頁碼）→ 最後一則以 multipart 帶 .md 附件。

新純函式：
- `resolve_report_path(raw)` — 相對路徑以 repo root 解析；resolve 後必須在 repo 內且為 `.md`，否則 None（防 stream 注入任意路徑外洩檔案）
- `build_report_messages(fields, report_text) -> [(content, attach_bool)]` — 含**containment 去重**：msg 已包含於報告全文（bb-followthrough 情境 msg==全文）→ 跳過全文切段只補附件；全文 > `MAX_REPORT_CHUNKS=15` 段 → 以「(全文過長，見附件)」取代切段
- `post_discord(url, content, attachment=None)` — 有附件走 `files={"files[0]":...} + payload_json`；429 退避共用
- `load_report(raw)` — 讀失敗回 None → **fallback 只送摘要，cursor 照常前移**（不卡死）

`run_once` 改為訊息數預算制：`MAX_MSGS_PER_RUN=25`（12KB 報告 ≈ 8 則，一輪約 3 份報告；超出留下輪，cursor 不前移）；單 entry 不跨輪拆送；首 entry 即超預算仍照送（防永久卡住）；multipart 失敗降級純文字兜底。`POST_SLEEP` 1s → 2s（webhook 30/min）。

舊格式 entry（無 report_path）行為完全不變 — 部署順序安全。

### B. news_pulse.py 新增「大盤與總經」段

- `fetch_news` SELECT 補 `announce_date`，tag_items passthrough date/title
- 常數 `MACRO_KEYWORDS`（加權指數/台股/台指期/外資買超/匯率/新台幣/央行/Fed/聯準會/FOMC/利率/降息/升息/關稅/CPI/通膨/非農/GDP/道瓊/納斯達克/標普/費半/美股/日經…）、`MACRO_TOP_N=10`
- `extract_macro_headlines(tagged)`：cnyes tier2 + **標題**含關鍵詞 + `tickers` 為空（個股新聞留給題材脈衝，天然不重複）→ 去重 → date desc → top 10
- `render_macro_section(macro)`：`## 大盤與總經` + `- MM/DD 標題` 列表；獨立 filter **不是 theme** — 不進 z baseline/history/THEME_BLOCKLIST
- 接線：`md = render_report(...) + render_macro_section(...) + render_intl_section(...)`（render_report 零改動）；inbox 摘要尾端加 `; 大盤/總經 N 則`
- `push_inbox` 加 `report_path` 欄位（傳報告輸出路徑 `out`）

### C. 各 routine XADD 加 report_path（最小 diff）

| 檔案 | Diff |
|---|---|
| `scripts/etf_smart_money.py` | `push_to_inbox` 簽名加參數，fields 加 report_path（--notify 路徑） |
| `scripts/memory_cycle_monitor.py` | main 已有 `report_path` 變數，傳進 `push_inbox` 即可 |
| `scripts/bb_inbox_alert.py` | **條件式**：`analysis/smart_money_<date>.md` 存在才附（該檔非每日產出，多數日子行為同今日） |
| `scripts/daily_synthesis_prompt.md` | XADD 指示加 `report_path analysis/routine_synthesis_<日期>.md` |

### D. bb_followthrough_track.py 補 md 報告檔（建議做，已納入）

digest 本身已是 md，寫 `analysis/bb_followthrough_<date>.md` 零轉換成本 + archive 價值（daily_synthesis 可改讀檔）。XADD 加 report_path；containment 去重保證不三重推送（結果 = 摘要切段 + 附件）。dry-run 不寫檔。

## 檔案清單

- `scripts/discord_forward.py` + `tests/test_discord_forward.py`（主要改動）
- `scripts/news_pulse.py` + `tests/test_news_pulse.py`
- `scripts/etf_smart_money.py`、`scripts/memory_cycle_monitor.py`、`scripts/bb_inbox_alert.py`、`scripts/bb_followthrough_track.py`（各 ~5 行）+ 各自測試 1-2 案例
- `scripts/daily_synthesis_prompt.md`
- `docs/plans/2026-07-30-report-push-discord.md`（plan 落 repo）

## TDD 順序

1. `resolve_report_path` / `build_report_messages`（含去重、超長 cap、路徑穿越防護）紅→綠
2. `post_discord` multipart（mock requests）紅→綠
3. `run_once` 預算/fallback（fake redis）紅→綠
4. news_pulse `extract_macro_headlines` / `render_macro_section` 紅→綠 → 接線
5. 四 routine report_path 小 diff + 測試；prompt.md
6. bb_followthrough 寫檔 + 測試
7. pre-commit 全 tests

## 驗證

```bash
# news_pulse 手動跑 → 報告有大盤段、inbox 有 report_path
.venv/bin/python scripts/news_pulse.py && grep -A12 "大盤與總經" analysis/news_pulse_$(date +%F).md

# forwarder 端到端：合成 entry 指向現成 12KB 報告 → Discord 應見 摘要+7段全文+附件
redis-cli XADD claude:inbox '*' topic test-report msg "測試摘要" report_path analysis/routine_synthesis_2026-07-29.md
.venv/bin/python scripts/discord_forward.py -v

# fallback：bogus 路徑 → 只送摘要、cursor 前移
# launchd 實測：launchctl kickstart -k gui/$(id -u)/com.lulala.discord-forward
# 隔日觀察全排程日 (08:35→20:35) Discord 輸出
```

## 風險

- 429 退避後仍失敗 → cursor 不前移 → 下輪整份重送（at-least-once，Discord 端偶重複可接受）
- 大盤關鍵詞首週會有雜訊/漏抓 — 常數易迭代，人工看報告調整
- 單輪最長 ~50s（25 則 × 2s sleep），遠在 300s 週期內
