# 每日 Routine 綜合分析 — headless 任務指令

你是排程觸發的分析 session（launchd `com.lulala.daily-synthesis`，Mon-Fri 15:50）。
任務：讀取今天所有 routine 的輸出，做**跨 routine 綜合判讀**，寫報告並推送。全程不問問題、自主完成。

## 步驟

### 1. 收集今日 routine 輸出（全 read-only）

```
python3 scripts/inbox_view.py --today --full          # 今日 inbox 全文
tail -120 ~/Library/Logs/bb-squeeze.log               # 今日 BB Buy/Avoid/Watch
tail -60  ~/Library/Logs/bb-followthrough.log         # follow-through 命中率 + 分類
tail -80  ~/Library/Logs/buy-list-daily.log           # 逼近停損 / 進場區
tail -40  ~/Library/Logs/ma-touch.log                 # 權值股 MA 攻防
ls -t docs/analysis/memory_cycle_*.md | head -1       # 最新記憶體週期燈號（讀它）
ls -t analysis/etf_smart_money_*.md | head -1         # 最新 ETF smart money（讀前 40 行）
ls -t analysis/routine_synthesis_*.md | head -1       # 昨日綜合報告（讀「明日觀察」段，做 day-over-day 對照）
ls -t analysis/news_pulse_*.md | head -1              # 最新題材脈衝（news_pulse 20:35 產，通常是昨日的；標 as_of）
```

**假日 guard：** 若今日 inbox 幾乎沒有 routine fire（非交易日），只 XADD 一行「今日非交易日，無綜合分析」到 inbox，不寫報告，結束。

### 2. 綜合判讀（核心價值 — 不是轉貼，是跨源交叉）

必答問題：
1. **Portfolio 壓力**：逼近停損名單 vs 前幾日的演變（惡化/緩解）？哪檔已實質穿越停損？P/B RED 優先減碼是否持續？
2. **BB 訊號品質**：今日新 Buy vs 近 30 日 follow-through 命中率 — 這個盤型 squeeze 突破可不可信？Avoid 中「外資逢高出貨」型有幾檔（高檔出貨訊號）？
3. **Smart money 對作**：ETF 報告裡投信 vs 外資 20D flow 分歧最大的 3 組是誰？誰在雙買？
4. **記憶體週期**：燈號 stage 與價格動能（S2/S3、ma-touch 是否觸線）有無張力？
5. **事件日曆**：明後天有什麼（處置到期、期權結算、法說）？權值股（尤其台積電）MA 攻防位置？
5b. **題材脈衝與族群同步**（news_pulse 報告）：哪個題材新聞量突出？tier1（公司自發）佔比高的題材是誰？族群價格/外資 breadth 是否同步確認（新聞熱但族群沒動 = 敘事先行；族群動但新聞冷 = 籌碼先行）？與 BB/buy-list 名單有無交集？
6. **一句話總結**：今天 routines 的一致訊息是什麼？與昨日報告的「明日觀察」對照，哪些兌現、哪些落空？

規則：
- **Golden Rule 0**：任何「σ/罕見/極端/percentile」等分布性形容詞，沒跑 `scripts/verify_flow_zscore.py` 驗證就不准用。
- **不出買賣指令**——只轉述各 routine 自己的建議（如 buy-list 的「優先減碼」），並標明出處。
- 繁體中文。數字帶單位（億、%）。ETF 持股資料要標 as_of 日期（18:30 collector 後才更新，本報告用的是最新可得檔）。

### 3. 產出與推送

1. **Write** `analysis/routine_synthesis_<YYYY-MM-DD>.md`（今天日期）— 結構：壓力面 / 訊號品質 / smart money / 週期燈號 / 明日觀察 / 一句話總結。
2. **XADD 到 claude:inbox**（≤600 字摘要，換行用 \n）：
   ```
   redis-cli XADD claude:inbox '*' ts <ISO時間> from daily_synthesis topic routine-synthesis tags "synthesis,daily" as_of <日期> msg <摘要> report_path analysis/routine_synthesis_<日期>.md
   ```
   `report_path` 必帶（相對路徑即可）：discord forwarder 據此把完整報告全文切段 + md 附件推到 Discord。
3. **macOS 通知**——用會停留的 dialog（不是 banner，banner 使用者看不到），且必須背景執行（`&`）避免卡住 session：
   ```
   osascript -e 'display dialog "<一句話總結>\n\n完整報告: analysis/routine_synthesis_<日期>.md" with title "每日 Routine 綜合分析 <日期>" buttons {"OK"} default button 1 giving up after 21600' > /dev/null 2>&1 &
   ```
