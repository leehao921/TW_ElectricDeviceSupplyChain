# news_pulse — Phase 2: 新聞標註 + 族群同步偵測 Implementation Plan

**上游 roadmap:** `docs/plans/2026-07-24-news-event-momentum.md`（Phase 2）
**資料現況（2026-07-29 實測）:** news_items 已累積 5 日 1,082 則（twse_mops 446 / tpex_mops 309 / cnyes 327）。cnyes 標題**無** `(2330-TW)` 代碼格式 → ticker 抽取靠公司名字典。

## 關鍵設計決定

1. **第一版全確定性標註，零 LLM 成本。** MOPS 已帶 ticker；cnyes 用公司名字典（來自 Pilot_Reports 檔名 926 家）+ 主題用 WIKILINKS.md 實體字串匹配。LLM 增強留 Phase 2.5（等確定性版跑穩、有 precision 基準可比）。
2. **寫入邊界:** trading-timescaledb **read-only**（golden rule）。標註結果與 pulse 歷史存本地 `data/news_pulse_history.json`（theme→date→count），不寫 DB。
3. **中文名匹配防誤報:** 2 字公司名（研華、大同、全新…）只在**標題**匹配且過 blocklist（大同/全新/東元/中興等常用詞名）；≥3 字名標題+摘要都匹配。純 ASCII 實體（AI、HBM）要求兩側非英數字元（防 "FAIR" 誤中 "AI"）。
4. **Golden Rule 0:** pulse z-score 需 60 日 baseline；MIN_HISTORY=20 前輸出 `insufficient-history(n=X)`，禁用分布形容詞（沿 options_quant 的 percentile_verified 模式）。資料 7/24 起算 → 約 9 月中才夠。
5. **cluster_confirm 價格源限制:** institutional_stock.close_price 只有 TWSE（OTC 全 0，已知 gap）→ OTC 成員只算 flow breadth 不算價格 breadth，報告揭露。
6. Python 3.9 相容（本 repo 慣例）。

## 模組結構（scripts/news_pulse.py，三層同 options_quant）

- **實體層（純函數，可測）**
  - `build_ticker_names(reports_dir)` → {name: ticker}（檔名解析）
  - `build_ticker_themes(reports_dir)` → {ticker: set(themes)}（報告內 wikilink 解析）+ 反向 {theme: set(tickers)}
  - `load_theme_entities(wikilinks_md)` → 實體集（排除超泛用 top-N 如 AI/PCB/5G? 不排除——保留但在報告分層顯示）
- **標註層（純函數）**
  - `extract_tickers(title, body, name_map)` — 2 字名 title-only + blocklist；≥3 字名全文；回 set
  - `extract_themes(title, body, entities)` — 中文子串匹配；ASCII 實體邊界檢查
  - `tag_items(items, ...)` → [{news_uid, tickers, themes, source_tier}]
- **Pulse 層（純函數）**
  - `theme_pulse(tagged, history, min_history=20)` — 當日 count、對 history 的 z（gated）、tier-1/tier-2 分列
  - `cluster_confirm(theme_tickers, price_5d, flow_5d)` — breadth：漲家數/成員數、外資買超家數/成員數
- **I/O 層:** 讀 news_items（psycopg2 read-only）、讀 institutional_stock 5D、append history JSON、產 `analysis/news_pulse_<date>.md`、XADD inbox topic=`news-pulse`

## 排程與整合

- launchd `com.lulala.news-pulse` Mon-Fri **20:35**（collector 20:05 之後；venv python 直跑——TCC 教訓）
- watchdog registry 加 `("news-pulse", "news-pulse", time(20,35), time(23,59))`（測試同步更新）
- `daily_synthesis_prompt.md` 步驟 1 加讀最新 `analysis/news_pulse_*.md`；判讀問題加「題材脈衝與族群同步」

## 測試（TDD）

fixture 用 tmp 報告檔。覆蓋：檔名解析、wikilink 解析、2 字名 title-only + blocklist、ASCII 邊界（AI≠FAIR）、MOPS ticker passthrough、pulse 計數、insufficient-history gate、breadth 純計算、report render 含 verification log。

## 驗收

1. 全 tests GREEN；2. live 跑一次產出當日報告（實際 news_items），inbox 有訊息；3. launchd 載入 + `launchctl kickstart` 真環境驗證；4. watchdog 測試 GREEN。
