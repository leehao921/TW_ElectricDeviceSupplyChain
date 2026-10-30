# FinDKG (ICAIF '24) vs My-TW-Coverage 架構差異分析 (2026-10-30)

論文: Li & Sanna Passino, *FinDKG: Dynamic Knowledge Graphs with Large Language Models for Detecting Global Trends in Financial Markets*, ICAIF '24, doi 10.1145/3677052.3698603

## 1. 論文管線 (一句話一層)
1. **抽取 (ICKG):** GPT-4 對 5,000 篇新聞產 KG 標註 → 品質過濾 (>5 組/篇) → 蒸餾微調 Mistral-7B (8×A100 約 10 小時)
2. **資料 (FinDKG):** WSJ 40 萬篇 (1999–2023) → 五元組 (主體, 類型, 關係, 客體, 類型) + 發布日 = 時間戳；**固定 15 種關係、12 種實體類型**；Sentence-BERT 做實體消歧
3. **趨勢偵測:** 每週日組一張「近 1 個月」快照圖 → degree / betweenness / eigenvector / PageRank 四種中心性 → **滾動 1 年 z-score**
4. **學習 (KGTransformer):** 把實體類型放進注意力 (HGT 式 μ[類型, 關係, 類型]) 的時序 GNN；FinDKG 上 MRR / Hits 比 EvoKG 高約 10%；沒有類型資訊時與基準持平
5. **應用:** 預測 (AI, Impact, ?, t+1) → S&P 500 曝險分數 → 月調倉主題組合；2022/06–2023/12 年化 39.6%、Sharpe 1.81 (QQQ 1.32)

**論文的弱點 (採用前要打折):**
- 樣本外只有 18 個月，且剛好包住 ChatGPT 行情；只測 AI 一個主題
- 沒計交易成本
- 標註模型 GPT-4 與 Mistral 的預訓練資料涵蓋評估期 → 有「模型已知道結果」的洩漏風險
- 四種中心性的趨勢偵測只用 COVID 一個案例「看圖說故事」，沒有預測力檢定

## 2. 我們現在的實際狀態 (2026-10-30 實測)
| 元件 | 狀態 |
|---|---|
| 926 份 Pilot_Reports | 研究級供應鏈圖；實體 = wikilink (WIKILINKS.md 620 行)；**邊沒有型別** (只靠所在段落: 上游/下游/客戶/供應商)；**邊沒有時間** (只有 git 修改日) |
| news_items (trading-timescaledb) | 17,024 筆，2026-07-22 起：MOPS 重訊 11,565 (有 ticker)、cnyes 5,459 (無 ticker) |
| news_pulse.py (20:35) | 字典比對 (零 LLM) → 題材「提及次數」日 z-score + 族群廣度；**沒有關係、沒有圖** |
| Graphiti / FalkorDB (:6381) | 3,896 節點 / 5,731 邊，但內容是個人 Obsidian vault (會議/專案) 200 個 episode；group_id=`default`，**不存在 `tw-electronics` group**；關係名大小寫混用 (works_at / WORKS_AT)；有 bi-temporal (147 條邊已失效標記) |
| tw_electronics Postgres (:5433) | 基本是空的 (news_items 3 筆，其餘 0) |
| 訊號層 | 價格/籌碼/選擇權量化 + signal_registry T+5/T+20 自我校驗；**沒有任何「圖 → 訊號」路徑** |

> CLAUDE.md 寫的「Graphiti group_id=tw-electronics、FalkorDB :6380、Postgres tw_electronics」與實況不符，需更正。

## 3. 逐層差異
| 層 | FinDKG | 我們 | 誰占優 |
|---|---|---|---|
| 資料源 | WSJ 24 年、英文、全球總經 | MOPS+鉅亨 3 個月、中文、台股個股 | 論文 (歷史長度)；我們 (台股粒度) |
| 事實抽取 | LLM 抽五元組，每篇都有 | 研究報告由研究產生 (精準但少更新)；新聞只做字典比對，不抽關係 | 論文 |
| Schema | 固定 15 關係 / 12 類型 | 報告:無型別；Graphiti:自由生長、已飄移 | 論文 |
| 時間 | 每個事實都有時間戳 | 報告邊無時間；Graphiti 有但沒裝台股資料 | 論文 (實作)；Graphiti (設計) |
| 實體消歧 | Sentence-BERT | wikilink 字串一致 (中英別名未統一的風險未盤點) | 論文 |
| 關係內容 | 新聞通用 (Impact / Relate To / Invests In) | **供應鏈專用** (誰供給誰、哪個材料/製程) | **我們** |
| 趨勢指標 | 圖中心性 z-score | 提及次數 z-score | 論文 |
| 學習模型 | KGTransformer 連結預測 | 無 | 論文 (但效益待證) |
| 驗證紀律 | 單一主題 18 個月回測 | signal registry 滾動命中、Rule 0 量化驗證 | **我們** |

**核心差異:** FinDKG 是「時間軸很長、但關係很淺」的新聞圖；我們是「關係很深 (供應鏈)、但沒有時間軸」的研究圖。兩者互補 —— 論文最缺的「誰供給誰」我們有；我們最缺的「這條關係什麼時候出現、最近被提到幾次」論文示範了怎麼做。

## 4. 建議路線 (照投入報酬排序)
**P1 — 把 926 份報告轉成有型別、有時間的邊 (零 LLM、最便宜)**
- 解析既有分段 → (公司, 關係, 實體, as_of=該段最後 commit 日)
- 關係固定一組台股供應鏈 schema，例如: 供應給 / 客戶為 / 採用技術 / 使用材料 / 競爭 / 屬於族群
- 存 Postgres (tw_electronics 本來就空著)，不放進已飄移的 Graphiti default 圖

**P2 — 新聞 → 四元組 (取代字典比對)**
- 用固定 schema 的 LLM 抽取，關係加上事件型: 擴產 / 打入供應鏈 / 量產 / 漲價 / 減產 / 投資 / 合作 / 受惠 / 受害
- 不必學論文微調 7B: 每天約 200 篇，直接用 Haiku 級 API 比自己蒸餾便宜
- 實體對到 ticker + wikilink 字典；對不到的進待審佇列，不自動新增

**P3 — 題材中心性 z-score + 沿供應鏈傳導 (我們獨有的優勢)**
- 照論文: 每週滾動 1 個月快照，算題材實體 (CoWoS / CPO / 矽光子…) 的 PageRank / degree z-score
- 論文做不到的: 題材升溫時，沿 P1 的供應鏈邊找 1–2 跳內的公司，排出「誰受惠」與「誰被擠壓」名單，直接回答 CLAUDE.md 的五個核心提問與 long/short 配對

**P4 — 用 signal registry 驗證，不先信論文的 Sharpe**
- 題材籃子 T+5 / T+20 相對族群報酬，照 Rule 0 驗證
- 新聞歷史只有 3 個月 → 先回補 MOPS 重訊歷史 (官方可查)，累積到 ≥12 個月才下結論

**P5 — KGTransformer: 暫不做**
- 前提是 P2 已累積 ≥1 年四元組；論文的增益是連結預測 MRR +10%，對交易的增量未被證明
- P3 的供應鏈傳導很可能已拿走大部分價值

## 5. 下一步需決定
1. P1 的關係 schema (建議先 6 種) 是否同意
2. 邊存 Postgres tw_electronics，還是修好 Graphiti 另開 `tw-electronics` group
3. 是否先回補 MOPS 重訊歷史 (P4 的前提)
