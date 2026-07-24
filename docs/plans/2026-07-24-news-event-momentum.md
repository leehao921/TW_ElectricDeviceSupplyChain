# 新聞輿情 × 事件動能層 — Roadmap Plan

**Status:** Design approved-pending（2026-07-24 brainstorm，觸發：用戶分享 IPC 族群動能貼文 + 要求加入國際新聞/預測市場事件動能）
**定位:** 為系統補「敘事層」。現有系統覆蓋價量（BB）、籌碼（三大法人/ETF）、估值（P/B）、選擇權（IV/GEX）——缺事件催化與題材確認。中長期（週級）策略依據 = 事件動能 × 動能 × 量價。

## 0. 已驗證事實（2026-07-24 實測）

| 源 | 狀態 | 備註 |
|---|---|---|
| GDELT 2.0 DOC API | ✅ 可用 | 免費，**限 1 req / 5s**，15 分鐘更新，volume+tone |
| Kalshi API | ✅ HTTP 200 | 美國合規預測市場，market data 免 auth；Fed/CPI/關稅/選舉 |
| Manifold API | ✅ HTTP 200 | play-money，覆蓋廣（AI/科技事件），訊號品質次之 |
| Polymarket | ❌ 台灣 ISP 封鎖 | DNS 污染（假 IP 182.173.0.181）+ TLS 攔截。替代：aggregator（如 adj.news）或 proxy（法規考量，暫不做） |
| MOPS 重大訊息 | 待建 | 第一手結構化，最高信度源 |
| 鉅亨 cnyes RSS | 待建 | 媒體二手源 |

## 1. 核心設計原則

1. **Wikilink graph 為實體骨幹**：LLM 標註新聞時 themes/tickers **限定從 WIKILINKS.md 的 2,421 實體選**，不自由生成（防幻覺）。事件 → `[[NVIDIA]]`/`[[Edge AI]]` → 族群成員 → breadth 檢查，全程查表。
2. **族群同步性 = 確認訊號**：一檔漲是雜訊，同題材 N 檔同步 + 新聞脈衝 + 法人同步進場才是敘事啟動。籌碼驗證是我們對貼文作者的優勢——他只能看價格同步。
3. **Channel-check 加權**（CLAUDE.md 框架）：MOPS（公司自己說）> 媒體 > 社群輿情。每則標 source_tier。
4. **事件動能是 regime/tilt 輸入，不是選股器**：Fed/關稅/地緣機率變化 → 整體曝險傾斜與 long/short 對偶（誰受惠→對偶誰被擠壓），個股層由籌碼+價量決定。
5. **成本紀律**：批次 LLM 標註用便宜模型；Claude 只做每日/每週判讀（7/20 撞過週上限的教訓）。

## 2. 訊號定義（草案，Phase 2/4 細化）

- `news_pulse(theme) = z(當日該 theme 新聞則數 vs 60 日)` — TW（cnyes/MOPS）與國際（GDELT query 組）分開算
- `event_momentum(event) = Δprob_7d / Δprob_30d`（Kalshi/Manifold 選定 market 的機率位移）
- `cluster_confirm(theme) = 族群成員 5 日漲幅 breadth × 外資/投信 5D flow breadth`
- 週級綜合：`theme_score = w1·news_pulse + w2·event_momentum(mapped events) + w3·cluster_confirm`，帶結構性 vs 庫存週期標記
- Golden Rule 0：任何分布性形容詞先過 percentile 驗證（沿用 verify_flow_zscore 模式）

## 3. Phases

### Phase 1 — TW 新聞 collector（database repo，tmf-* 模式）
MOPS 重大訊息 + cnyes RSS → Postgres `news_items(ts, source, source_tier, title, body, url, raw_tickers)`。每小時抓。TDD。

### Phase 2 — LLM 標註 + 族群同步偵測（My-TW-Coverage）
每日批次標 `tickers[]/themes[](限 wikilink 實體)/catalyst_type/sentiment/source_tier` → `news_tags` 表。族群同步偵測器（news_pulse × cluster_confirm）→ daily_synthesis 加「今日題材脈衝」節。

### Phase 3 — 國際事件層（database repo collector + My-TW-Coverage 分析）
- GDELT query 組（TSMC/semiconductor/tariff/export control/AI capex/Taiwan strait），日更 volume+tone
- Kalshi + Manifold 選定 markets 快照 collector（日更機率）；event → theme 映射表（人工維護 + LLM 建議）
- Polymarket 暫緩（封鎖）；若日後需要走 aggregator 再評估

### Phase 4 — 中長期策略整合
週級「事件動能 × 族群動能 × 籌碼」報告（long/short 對偶名單）；BB Buy × 題材確認分級回測（目標：把 12% 命中率的 breakout 池分層）；regime tilt 建議（僅環境判定，不出買賣指令）。

## 4. 明確不做（YAGNI）
- 即時新聞逐則推播（週期是中長期，日批次夠）
- PTT/社群輿情（信度最低，Phase 4 之後再議）
- Polymarket proxy 繞封鎖（法規考量，用戶未決定前不動）
- 自建 NER/embedding pipeline（wikilink 查表 + LLM 批次已夠）
