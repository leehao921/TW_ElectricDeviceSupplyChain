# Vault Log

Append-only chronological record of vault events. Format: `## [YYYY-MM-DD HH:MM TWT] {event_type} | {summary}`

Event types: `ingest` (new source) · `query` (notable Q&A) · `lint` (health check) · `sync` (Redis → vault) · `update` (page edit) · `bootstrap` (initial population)

---

## [2026-05-15 16:00 TWT] bootstrap | Initial vault populated — 13 pages across user/projects/concepts/trading/meta

Pages created:
- meta/schema.md
- user/profile.md, preferences.md, tools.md
- projects/active.md, pending.md, completed.md
- concepts/TXF.md, DXY.md, covariance_panel.md, FOPLP.md
- trading/positions.md, playbooks.md
- log.md (this file), index.md

Source migration:
- 6 existing memory files (`reference_*`, `feedback_*`) → distilled into preferences.md
- Recent session findings (Asia panel covariance, 5/13–5/15 analyses) → concepts/TXF.md + DXY.md + covariance_panel.md
- Current positions (00763U @ 31.47) → trading/positions.md
- Trigger-based rules (DXY > 100, USD/TWD > 31.80) → trading/playbooks.md

## [2026-05-15 15:59 TWT] sync | claude:inbox stream initialized

First message: `TXF_boot — claude_msg.py 上線測試 (5/15 算出 TXF-DXY 60d β = -1.47)`. Redis port 6379, container `trading-redis`, stream `claude:inbox`. Cursor file at `~/.claude/projects/-Users-lulala-Documents-coding-My-TW-Coverage/.claude_msg_cursor`.

## [2026-05-15 16:05 TWT] sync | claude:inbox 3 msgs + signal_alerts 0 rows → vault/inbox/2026-W20.md

## [2026-05-15 16:08 TWT] lint | 1 orphans, 0 stale, 3 contradictions, 1 missing-from-index, 0 stale-in-index

## [2026-05-15 16:09 TWT] lint | 0 orphans, 0 stale, 1 contradictions, 0 missing-from-index, 0 stale-in-index

## [2026-05-16 12:15 TWT] ingest | themes/UAV.md created — 28 companies, 7 national team members, supply chain mapped. User search "自強建設" disambiguated to 自強工程顧問 (private, 3D GIS / 圖資 platform niche).

## [2026-05-20 22:30 TWT] ingest | themes/邊緣運算.md created (254 lines, 109 wikilinks) + concepts/edge_ai_inference.md (Nano-tier focus). Catalyst: NVDA Q1 FY27 公布 ACIE $37B 拆分,Edge / Industrial 推論 narrative 啟動. Seven competitor camps analyzed (NVIDIA Jetson Orin Nano Super / Hailo / AMD Kria / Rockchip RK3588 / Qualcomm QCS6490 / MediaTek Genio / Ambarella). NVDA Nano-tier 全球市占 <25%. TW alpha L1-L4 mapped: 6579 研揚 (純度最高) / 2454 聯發科 Genio (自家 SoC 挑戰) / 3044 健鼎 (carrier board 通吃) / 3289 松騰 (終端).

## [2026-05-21 10:23 TWT] lint | 0 orphans, 0 stale, 1 contradictions, 0 missing-from-index, 0 stale-in-index

## [2026-05-26 22:00 TWT] ingest | 008004 MLCC batch research (6 parallel worktrees) → themes/MLCC.md + vault/concepts/MLCC_008004.md

6 unit slices in `vault/research/008004/`:
1. spec + Big-4 量產現況 (Murata 2014 首發 / 2024/09 推出 **006003** next-gen, 非 005003)
2. 2327/2492 對 008004 真實 exposure (公開資料 0;最小 footprint 國巨 01005 imp / 華新科 0201 imp)
3. 3026/6173 利基 (兩家完全反方向 — 高壓/大尺寸 vs 008004 微小化)
4. 上游材料 (鈦酸鋇 nano 日商寡占, 6173 200nm→100nm 2027 才到位, 4760 銅漿 2026 進日本)
5. 3090/8043 代理通路 (8043 GB300 一台 45 萬顆 MLCC, 008004 占顆數 5.6% 但 ASP 占 45%)
6. 下游 BOM + Pair trade (LONG 8043/SHORT 2327 比 SHORT 2492 更乾淨;Vera Rubin VR200 MLCC $4,300/rack +182%)

Catalyst: 2327 +194.7% / 2492 +173.6% 過去 6 個月,99.9 percentile 3Y,5/14-5/25 連 4 根漲停 → 市場把 commodity 漲價 + AI server BOM + 008004 微小化錯誤掛勾。本研究釐清 TW 中游廠零 008004 直接 exposure,真正受惠是代理通路 (8043 蜜望實 + 3090 日電貿) 與材料 catch-up (6173 信昌電 + 4760 勤凱)。剔除 3236 千如 — 業務與 MLCC 介電粉體零相關。

## [2026-06-01 09:29 TWT] lint | 1 orphans, 0 stale, 1 contradictions, 1 missing-from-index, 0 stale-in-index (pre-aggregation snapshot)

## [2026-06-01 09:30 TWT] lint | 0 orphans, 0 stale, 1 contradictions, 0 missing-from-index, 0 stale-in-index

## [2026-06-01 14:00 TWT] ingest | 008004 第二輪深度驗證 batch (5 parallel worktrees) + 2 個新概念頁 + slice 01 補 Murata GRM011 SKU

5 個新 unit slice 在 `vault/research/008004/`:
7. 8043/3090 代理通路深度驗證 (305 行) — **Murata 4/1 漲價不利於 8043** (非 8043 principal);8043 008004 占 rev 6-9% (非 5.6%);Q3 OCF -405.82M = 70% A/R + 30% inventory, Q4 已收斂;3090 alpha 已 reversed 反超 8043 (+52% vs +37% 5/19-6/1)
8. 6173/4760 上游材料深度驗證 (276 行) — **6173 100nm 目標是 NP0/C0G (Class I), 不是 X7R**;6173 明確避開 0201 微小化, 主攻 1206+ 大尺寸高壓 NP0;**TW 零 Ni paste/nano-Ni 玩家** (科揚 只代理 MMS), 35-50% MLCC 成本卡死 TW 008004 整合;4760 日本仍在 cultivation
9. TW 隱藏候選 (291 行) — **新增 3030 德律 ★★★ (AXI X-ray AI server GPU PCBA 焊接後檢測, 一塊上千顆 008004)**;**新增 3189 景碩 (ABF 載板第三家, ECiP)**;觀察 3455 由田 + 6187 萬潤;ticker 修正 4977 眾達-KY 非 ABF (光通訊模組 OEM);排除 9 家 noise
10. 2327/2492 R&D pipeline (285 行) — **隱藏 R&D 強度 = 1/5 (極低)**, 跨 6 維度一致負向:專利 0 件 sub-0.4mm claim (vs Murata ≥ 3 件 US12,482,604/US20240282522A1/WO2024247128A1);0 篇 ECTC/CIPS 論文;Yageo Apple supplier list 但 design-in 止於 0402/01005;馬廠無 Hirano Tecseed/光洋熱工 high-end 設備訊號;Kemet 鉭電容才是 Yageo AI 武器
11. Catalyst calendar (372 行) — Top 3: **(1) 6/10 處置股結束 (2) 10/14-18 CEATEC (Murata 006003) (3) 11/14 前 Q3 法說 (8043 AI 占比 50%)**;25 個 catalyst rows;5 個 risk events;2026/12-2027/H1 = ASP cliff window

2 個新概念頁 (vault/concepts/):
- MLCC_008004_technical_deep_dive.md — 永久技術 reference (350+ 行, 10 段):規格命名陷阱 + 技術門檻 4 維度 + Murata GRM011 SKU 詳表 + Big-4 對照 + ASP 倍數 + 應用 4 類 + 漲價 + 006003 + TW 排序 + 檔案索引
- MLCC_008004_TW_verification.md — 6/1 驗證補丁:修正 Tier 排序 (3090 升 #1, 6173/4760 降);新增 3030/3189;TW Ni paste 0 玩家 critical finding;隱藏 R&D = 1/5;修正版 pair trade (LONG basket {3090+8043+3030}, SHORT 2327 比 2492 更乾淨)

Slice 01 補 Murata GRM011 SKU 詳表 (GRM011R60J104M 0.1µF 6.3V X5R / GRM011R61A101KE01L 100pF / C0G 1pF-0.1µF / X5R 100pF-0.1µF) + Izumo 新廠 JPY 47B 4/3 完工。

## [2026-06-01 11:29 TWT] lint | 11 orphans, 0 stale, 1 contradictions, 11 missing-from-index, 0 stale-in-index

## [2026-06-01 11:29 TWT] lint | 0 orphans, 0 stale, 1 contradictions, 0 missing-from-index, 0 stale-in-index

## [2026-06-01 17:30 TWT] ingest | Institutional Alpha batch (6 parallel workers) — 法人/外資跨產業潛力股 + 為什麼買

**6 個 unit slice (~1500 行):**
- 28 半導體晶圓+記憶體 — 2344 華邦電 ★★★★★ 雙引擎冠軍 (Q4 GM 41.86%, NOR Flash Vera Rubin 隱形瓶頸); 6770/5347/2408 ★★★★
- 29 AI server ODM — 外資 vs 投信「估值修復 vs AI 純度」分歧; 2324 仁寶兩派對立差 401K 張; 排序 2317 > 3231 > 2324 > 2356 > 2382
- 30 HVDC + grid — 1605 華新 conviction high (隱性 008004 sleeve, 集團持 2492+6173); 6282 康舒 P/E 319 透支警戒
- 31 HBM 周邊 — 3711 日月光 #1 (Q1 OpM 10.10% 創高 + PEG 1.4); 2449 hold; 6147 警戒
- 32 金融股 — 外資 TWD+壽險EV+ETF (2881/2882/2891); 投信 殖利率+公股 (2887/2880/2886); 2885 mixed
- 33 傳產 — 1303 南亞 ✅✅✅ (集團 SOTP + CCL/玻纖布) + 2027 大成鋼 (Trump 50% 關稅); 2609/1216 防禦

**Top 5 真潛力股**: 2344 華邦電 / 3711 日月光 / 1605 華新 / 1303 南亞 / 2317 鴻海
**警戒清單**: 6147 / 2449 / 6282 / 2382 / 2356 / 2481

## [2026-07-08 13:40 TWT] signal + incident | 台指期 OFI 開盤三時點背離 + stock_ofi collector 開盤 crash-loop

**訊號 (→ playbooks.md 新增 candidate):** 2026-07-08 TXF 開盤三窗 Trade-OFI (主買−主賣口, `ticks.tick_type`): W1 08:45 −39 (−1.0%) → W2 09:00 −183 (−6.6%, 價 45800-45960 高檔背離) → W3 09:25 −569 (−29.3%, 價 45785→45500)。開 45606→衝 45960→收 45500。**OFI 在 09:00 現貨開盤領先價格轉弱 ~25min。** 權值股僅 08:45 有 OFI: [[台積電]]+0.47 撐、AI 伺服器 [[廣達]]−0.23/[[緯創]]−0.18/[[台達電]]−0.12 被賣 → 窄多方 (與昨日 ETF smart money「投信買 Computer Hardware 動能連日收斂」同向)。

**Incident — stock_ofi 09:00/09:25 空窗根因:** collector 08:46 開盤後只收到 ~5min 真實 bidask (08:46:30–08:51), 隨即 bidask starvation → 容器 crash-loop, **RestartCount=16**, 直到 10:11 台北 (broker 回收 dead session) 才站穩, 資料 10:15 才恢復。**非 hard_session_reset 自癒** (該 fix 已部署於 /opt/tmf/.../stock_ofi_collector.py, grep✓, 但它是 in-process 復原、不會 bump RestartCount)。今日是 Docker restart-policy 硬磨 16 次過開盤。7-06 log 顯示 DEGRADED snapshot polling 曾成功保命 (active=20/20 DEGRADED), 今日卻整個 exit → 研判開盤 re-login 撞 451。**[更正 2026-07-08]** 實測共用同一把 key (尾碼 `...WAiprv`) 並各自 login shioaji 的是 **4 個 collector**（非先前誤稱的 5）: `tmf-tick-collector`(SHIOAJI_API_KEY)、`tmf-stock-ofi-collector`(**API_KEY**)、`tmf-futures-ohlcv-collector`(SHIOAJI_API_KEY)、`tmf-options-iv-collector`(SHIOAJI_API_KEY); 其餘 collector 走 TAIFEX/TWSE 公開 API 不 login。shioaji per-process, 4 容器=4 條獨立 session 佔同一把 key; dead session 沒 logout → slot 未釋放 → 重啟新 login 超並發上限撞 451。**每把 key 確切並發上限數字未證實**（先前「~5」為推測), 僅確定「有上限且死 session 回收前佔額度」。**空窗不可回補** (逐筆微結構無法事後 replay; `ticks` 只收期貨不收個股)。

**根治方向 (未執行):** (a) stock_ofi 專屬獨立 API key (分離 quota, 開盤 451 免競爭); (b) login 451 改 in-process 60s backoff retry 取代 sys.exit → 避免 Docker crash-loop churn; (c) 確保 exit path 優先留在 DEGRADED snapshot 模式。

## [2026-08-05 TWT] 事件複盤驗證 | 6-7 月「萬箭齊發」→ 財報週 V 轉,KOL 敘事 vs 本地數據

用戶轉來 KOL 貼文複盤 6/23→7/29 崩跌與 MSFT/AWS 財報週反轉。本地驗證 (TXF futures_ohlcv + institutional_stock):**期指 6/23 高 51,411 → 7/29 低 39,442 = -23.3%**,較「跌快兩成」更深;個股 7/20 後 vs 6 月峰值:**85 檔腰斬 (≤-50%)、458 檔 ≤-35%、1,067 檔 ≤-20% (universe 2,344)** — 指數跌幅被權值護盤低估、中小半導體重災說法成立。反轉催化 = [[Microsoft]] 獲利季增 + [[Amazon]] AWS 422 億美元;巨頭雲端 AI 營收單季合計破千億美元 → 「AI 推論商業模式成立」結構性 thesis。外資 7/31 全市場 +612 億首日回補、[[台積電]] 單檔 +334 億 (見 routine_synthesis_2026-08-03)。**不可驗主張 (打折):** CDS「單日最大漲幅」(無數據源,分布性形容詞未驗證)、四大基金護盤細節、韓國總統府炒股定性。**Data gap 發現: asia_index_daily 停更於 2026-05-15** (yfinance collector 斷,TWII/KS11 全缺 6-8 月) → 需在 database repo 修。

## [2026-08-05 TWT] 驗證 | 「AI 推論商業模式成立」數字查核 (web 一手來源) + asia_index_daily 修復

前篇 KOL 敘事的財報主張逐項查核 (公司 IR/CNBC 一手):**AWS $42.2B ✓** (YoY +37%,18 季最快);**[[Microsoft]] 獲利季增 ✓** ($31.8B→$35.8B,+12.6%) 但「先前三季停滯 ~$13B」**不成立** (實際 $27.7/38.5/31.8B,受 [[OpenAI]] 投資損益波動);**「AI 營收 1063 億」= 口徑錯置** — 精確等於 Intelligent Cloud ($39.3B) + AWS ($42.2B) + Google Cloud ($24.8B) **雲端部門營收**加總,三家皆無 AI 專項披露,[[Amazon]] 僅口頭披露 AI run rate >$25B/年;[[Meta]] 無 AI 營收項 ✓ (capex $31.1B 翻倍、FCF 剩 $0.78B)。市場反應:7/30 Nasdaq +2.8%、SOX +8.19%、MSFT +15.5% (單日市值 +$450B 紀錄);[[Alphabet]] 實際 7/22 已公布 (非財報週內)。**CDS 主張升級為成立**:[[NVIDIA]] 5yr CDS 7/27 單日 +14bp 創 82bp 歷史高、[[Oracle]] 203-215bp 為 2008 以來最高 (S&P 降至 BBB−),驅動 = 循環融資疑慮 (NVIDIA 對 OpenAI/CoreWeave 入股擔保 >$540B)。**結論:推論需求真實 (雲端營收/獲利率齊升) 但「1063 億=AI 營收」是敘事誇飾;信用市場與股市對 AI 循環融資的定價分歧是下一個觀察軸。**

基礎設施:asia_index_daily 孤兒表已修 (database repo 58214ec) — 13 檔亞洲指數 collector 20:45 TPE + backfill 5/16-8/5 + staleness 告警;TWII 現貨實測 6/23 高 48,219 → 7/29 低 39,385 = **-18.3%** (期指 -23.3%)。

## [2026-08-05 TWT] alpha 工具上線 | 外資結構背離 + 量能 regime gate + 處置解除 backtest

陳鳳馨文章三條 alpha 落地。**#1 foreign_structure** (launchd 16:30): 外資現貨 5D 淨買「金額」z vs TXF 淨 OI z → hedged_accumulation/distribution_cover;實測 8/4 = `neutral` (現貨 -237 億 z=+0.28 帶內、期貨 z=-1.37 深空)。**單位陷阱: institutional_stock.foreign_net 是股數,金額須 ×close_price** (7/31 驗證 = +612 億 ✓)。**#4 market_regime**: FMTQIK 5D 均量 <1 兆 → low_volume 降權 banner、TAIEX < 39,385 → broken;已接 bb-squeeze + buy-list;實測 8/5 = normal (1.04 兆/44,612)。**#3 處置解除 backtest (n=492, 2025-01 起)**: 全樣本 +5D mean +0.61% median -1.73% 無 edge;**分組有 edge — 處置前外資買超 (n=314) +10D mean +3.59% win 51% vs 賣超 (n=178) -1.73% win 40%**,spread 5.3pp;short 端 (賣超組解除後續跌) 比 long 端更一致 (long 靠右尾)。**更正: 早前誤報處置 0 檔** (parse 錯 key) — 實際 23 檔處置中,符合買超 profile: [[南電]] +22.9 億 (8/18 解除)、[[禾伸堂]] +16.0 億 (8/14)、[[3532 台勝科]] +14.2 億 (8/13);賣超 profile: 泰宗 -0.8 億。無交易指令,環境標註。

## [2026-08-11 TWT] incident+fix | DDR 報價手動月更失效 3 個月 → DRAMeXchange 日更自動化

用戶問 memory-cycle 為何沒自動更新報價,追查揭露兩層:(1) S1 P/B 凍在 8/8 = 外接碟事故下游 (pb-lights cache fast-path 靜默回放);(2) **S2 DDR 報價自 6/25 起一直是模板佔位值** ($2.85→3.45,「+10.6%」是假的),實際 [[DDR4]] 8Gb 現貨已 **$42.50** — 手動月更機制部署後從未被真值覆蓋,超級週期整段漲勢 monitor 沒看到 (燈號方向碰巧同為 🟢 未釀錯判)。修復: `scripts/ddr_price_daily.py` 每日 08:20 抓 DRAMeXchange 首頁現貨表 (實測可達,session avg),自動維護 yaml 月均 series;TrendForce 週報實價 seed 5-7 月 (32.8/35.67/40.03,agent 逐週查證高信度);[[DDR5]] 合約絕對價確認無免費源 → 指數基準 Q1=100/Q2=145 (+45% TrendForce 中值)。今日實價: DDR4 $42.50 (+4.4%)、DDR5 現貨 $51.93 (**+25.8% 單日**,超級週期未歇)。S2 現算真數據: MoM +6.2% 🟢 / QoQ +45% 🟢。教訓進 memory: **inputs 檔部署 ≠ 有人在餵,要驗證真值覆蓋**。

## 2026-08-11 — 實際庫存入庫追蹤
- 用戶提供券商 App 庫存截圖 (15 檔, 現值 164.9 萬, 未實現 +11.7 萬 / +7.7%)
- 寫入 data/portfolio_holdings.json + 重寫 vault/trading/positions.md (00763U 移 defunct 待確認)
- buy_list_state.json: 2603/7895 加入 watch_list, 新增 4 條持股 watchpoints (2408 近 tp2 505、權證到期日待查、3006/2455 處置中)

## 2026-08-11 — OHLCV collector DNS stale incident + BB 強勢名單上線
- tmf-stock-daily-collector (up 5wk) 解析不到重啟過的 trading-timescaledb → 8/10+8/11 OHLCV 全缺,今日 14:30 BB 巡檢實為 8/7 舊訊號
- 修復: docker restart + 手動補 8/10..8/11 (917/924);重跑推送修正版 (2 Buy/3 Avoid/11 強勢)
- BB 巡檢新增 🔥 強勢名單 (漲停≥9%+成交值≥10億,隔日沖池),處置股標🚫,OHLCV 落後時警示資料日

## [2026-08-13 17:45 TWT] update | trading-timescaledb 損毀修復 + 8/12-8/13 routine 全斷補跑

- 起因: 8/11 ~21:00 Mac 重開機 → Docker Desktop engine 掛死 → 8/13 中午 watchdog "Docker.raw disk-surgery" 期間 backend crash-loop,Postgres 多次 unclean shutdown
- 損毀範圍: 17 damaged chunks (truncated/missing files) + 12 ghost chunks (catalog 有、pg_class 無) + pg_class/timescale catalog 索引 + 88 條 dangling pg_depend + institutional_stock_pkey + futures chunk btree
- 修復: REINDEX SYSTEM/catalog/table、drop 損毀 chunks、catalog 手術 (compression refs + ghost rows)、3 caggs (tick_rate_1m/iv_metrics_1m/iv_regime_1m) refresh、futures 1T/1D 重複清除 (8,790 rows)
- 資料回補: stock_daily_ohlcv 8/5-8/13 (6,440 rows, 921/day)、institutional_stock 8/12 (1,812)、etf_holdings_daily 8/5-8/11 全救回 (2,436, 零損失)、news_items 救回 67 筆、futures_ohlcv 8/12 補齊
- **永久損失**: ticks 8/3 全日 (11 chunks 檔案消失,tick 無法回補)、TXF/TMF/MXF 8/11 分鐘 bar (Shioaji kbar 該日回傳空,CDF 正常;過幾天可重試 backfill --start 2026-08-11)
- Redis 拓撲已變 (database repo 5e00f50): master = homebrew redis :6379 (host),trading-redis 容器降為 replica 發布 :6380 → **與 FalkorDB :6380 衝突**,knowledge_manager-falkordb-1 起不來 (tw-electronics MCP 因此斷線),待決定 falkordb 換 port
- 容器清理: tmf-cross-basis-publisher (module .retired,停用+restart=no)、tmf-redis-timescale-sync (被 redis-bar-sync 取代的 orphan,停用)、redis-bar-sync compose YAML 摺行 bug 使 CLI args 被吃掉 (line 1002-1006,現以 defaults 運作)
- Routine 補跑: disposition fetch + BB scan 8/13 (2 Buy: 2364 倫飛/6603 富強鑫 · 18 強勢: 奇鋐 337億/國巨 308億...) + bb-followthrough 已推 inbox
- **2408 南亞科 8/13 收 514 (+6.53%) 突破 tp2=505** → 已推 inbox buy-list alert
- 終驗: pg_amcheck 全庫掃描 (heap+btree, 49GB) EXIT=0 零錯誤 (17:5x 第三輪;第二輪抓到 bgw_job_stat_history 檔案消失→TRUNCATE、intraday_alpha_history 雙索引損毀→REINDEX)
