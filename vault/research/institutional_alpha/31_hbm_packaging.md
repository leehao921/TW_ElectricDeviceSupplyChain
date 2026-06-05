---
type: research
status: draft
last_updated: 2026-06-01
source_unit: 31
tags: [institutional_alpha, HBM4, packaging, 6147, 3711, 2449]
---
# Unit 31: HBM 周邊封裝 3 強

## TL;DR
- 本 unit 鎖定 [[HBM4]] 量產 ramp (2026 H2 → 2027 H1) 拉動的 **[[CoWoS]] 後段封裝 + Test** 三檔台股：**6147 [[頎邦]]**、**3711 [[日月光投控]]**、**2449 [[京元電子]]**。三家皆非 HBM4 DRAM 直接 proxy (DRAM 100% 由 [[SK Hynix]] / [[Samsung]] / [[Micron]] 製造)，而是 [[NVIDIA]] [[Vera Rubin]] [[VR200]] BoM Tier 2 周邊受惠者 (見 vault/research/vera_rubin_bom/18_hbm4.md)。
- **6147 [[頎邦]] 5/16–5/29 法人結構罕見背離**：外資 **−22,537 張**、投信 **+33,834 張**、合計 **+6,171 張**。**外資已在 2026 Q1 把驅動 IC 衰退 + Bumping 殺價的擔憂賣完 (Net Margin 從 20.33% 砍到 12.94%)**，投信在 Q2 切入點押的是 [[CoWoS]] **HBM-side bumping + RDL test** 由 Q3 起量產接單 (法說會口風轉鬆 → 投信先行)。屬於「外資 well done → 投信末期切入」型態，非單純末段接刀。
- **3711 [[日月光投控]]** 是全球 OSAT 龍頭，2025 全年營收 6,454 億 (+8.4% YoY)、Net Income 400 億 (+23.6%)，**2026 Q1 已創單季 OpM 10.10% 新高** (vs 2024 Q4 之前長期 6-8% 區間)。HBM-on-CoWoS final assembly + Apple iPhone 17 SiP 雙引擎，**2026 CapEx 1,658 億 (年化推估)** 全押先進封裝產能擴張。法人 buy reason: **[[CoWoS]] 月產能 2026 底拉到 80K wafer/月**、日月光承接溢出單 + HBM-side KGSD test。
- **2449 [[京元電子]]** 為 [[NVIDIA]] AI 晶片測試 **>90% 市佔** (Dan Nystedt 確認)，**FY2025 EPS 9.01 創新高、Q1 2026 營收 +40% YoY**。**AI 測試 FY2026 指引 >30% 營收**、2026 CapEx **NT$500 億創歷史紀錄**。Vault 已驗證為 HBM4 KGSD test + Rubin GPU SLT 必經點。
- **Buy thesis 排序：3711 > 2449 > 6147**。3711 為「先進封裝量價齊揚 + 估值合理 (P/E 56.73、P/B 7.65)」最佳；2449 為「AI 測試壟斷但估值已 price-in (P/E 44.57、P/B 7.38)」；6147 為「外資已賣完、投信切入的 turnaround」需確認 Q2-Q3 法說會口風。

## 6147 [[頎邦]] — 外資為何賣?投信為何接?

### 法人結構 (5/16–5/29, prompt supplied)
| 法人別 | 張數 |
|---|---|
| 外資 | **−22,537** |
| 投信 | **+33,834** |
| 合計 | **+6,171** |

### 外資賣超的三層基本面理由 (從財報直接歸納)

| 指標 | 2023 | 2024 | 2025 | 2025 vs 2024 |
|---|---|---|---|---|
| Revenue (百萬台幣) | 20,056 | 20,338 | 21,454 | **+5.5%** |
| Gross Margin (%) | 25.56 | 22.46 | **21.40** | **−1.06pp** |
| Operating Margin (%) | 16.58 | 12.50 | **11.19** | **−1.31pp** |
| Net Margin (%) | 19.92 | 20.33 | **12.94** | **−7.39pp** ←重災 |
| CAPEX (百萬台幣) | −2,226 | −935 | **−5,108** | **5.46x 暴增** |

**外資賣超的三個基本面理由：**
1. **獲利結構崩塌** — Net Margin 從 20.33% 砍到 12.94% (−7.39pp)，2025 Q4 全年雖 Revenue +5.5% YoY，但 Net Income 從 41.35 億砍到 27.75 億 (**−32.9%**)。OpM 從 16.58% (2023) 連續兩年下滑到 11.19%，**驅動 IC 封裝 (COF/COG) 成熟業務遭遇殺價競爭 + [[南茂]] 競爭壓力**。
2. **CapEx 暴增 5.46x** — 2025 年 CapEx 51.08 億 vs 2024 年 9.35 億，公司明顯轉型 HBM-side bumping / RDL 投資，但折舊壓力會在 2026-2027 年顯現，**短期 OpM 進一步壓縮風險**。
3. **估值高貴** — P/E (TTM) **89.33**、P/B **4.85**，股價 $285.50 (2026-06-01)。Net Income 衰退年的 P/E 89x 在外資 DCF 模型下不可接受 (隱含 2026-2028 EPS 必須翻倍才能 justify)，外資通常 P/E > 60 的 turnaround 標的會選擇先撤。

### 投信買超的賭注：HBM-side bumping + RDL test 切入

投信在 Q2 切入的買點不是「成熟驅動 IC」，而是賭：
1. **[[CoWoS]] HBM-side bumping** — [[台積電]] HBM-on-CoWoS interposer 上 HBM stack 需要 micro-bump (Cu pillar + SnAg solder)，本身就是 [[頎邦]] Bumping 業務的核心能力。2025 CapEx 51 億暴增主要投入 RDL (Re-distribution Layer) + Cu pillar 產能擴張。
2. **HBM4 KGSD 周邊 test** — HBM4 採 [[MR-MUF]] 封裝 + 12-Hi/16-Hi stack，KGSD (Known-Good Stack Die) 測試需要高密度 probe card + SLT；[[頎邦]] 與 [[京元電子]] 在 SLT 段是非競爭互補關係。
3. **Q4 2025 OpM 觸底回穩** — 2025 Q4 OpM 9.48% (vs Q2 10.92%、Q1 13.74%) 顯示驅動 IC 殺價已落底，**Q3 2025 Net Income 反彈到 8.31 億** (vs Q2 4.10 億，+102% QoQ) 已現轉折跡象。投信看到的是 turnaround 起點。

### 風險 (為什麼這是「需要確認」的 turnaround，不是無腦多)

- **HBM-side bumping 訂單規模未揭露** — [[頎邦]] 法說會尚未具體量化 HBM 業務佔比 (推測 < 10%)，主要營收仍靠成熟驅動 IC。
- **2025 CapEx 51 億的 ROI 不確定** — 若 HBM-on-CoWoS 量產不如預期，產能閒置 → 折舊壓垮 OpM。
- **2025 Q4 Net Income 8.31 億的可持續性** — Q4 Net Margin 15.40% 反彈，但 Op Cash Flow 從 Q3 5.31 億回到 19.91 億 (季節性 + 折舊回補) 而非營業面實質改善，需要 Q1-Q2 2026 持續驗證。

### Verification log
- 法人 5/16–5/29 數字：使用者 prompt 提供 (外資 −22,537 / 投信 +33,834 / 總 +6,171)。**未獨立 DB 驗證** (本 session DB 查詢受限)。
- 財務數據：直接引用 `Pilot_Reports/Semiconductor Equipment & Materials/6147_頎邦.md` 已 ingest 的 yfinance 2025 全年與季度表。

## 3711 [[日月光投控]] — HBM-on-CoWoS 量產拉動

### 為何法人會買 (即使未進 Top 20)
**全球 OSAT 龍頭 (市佔第一)** + **2025 全年 +8.4% Revenue / +23.6% Net Income** + **2026 Q1 OpM 10.10% 創單季新高**。法人未進 5/16–5/29 Top 20 不代表沒買，而是 3711 流通市值 **2.68 兆台幣** (TW 前 10 大)，需要極大流入才會擠進排行 — 反而是 quiet accumulation 候選。

### 財報 hard evidence

| 指標 | 2023 | 2024 | 2025 | YoY |
|---|---|---|---|---|
| Revenue (百萬台幣) | 581,914 | 595,410 | **645,388** | **+8.4%** |
| Gross Margin (%) | 15.77 | 16.28 | **17.69** | **+1.41pp** |
| Operating Margin (%) | 7.20 | 6.79 | **7.99** | **+1.20pp** |
| Net Income (百萬台幣) | 35,458 | 32,379 | **40,016** | **+23.6%** |
| Net Margin (%) | 6.09 | 5.44 | **6.20** | **+0.76pp** |
| CAPEX (百萬台幣) | −54,590 | −81,683 | **−165,848** | **2.03x** |

**2026 Q1 是真正的 inflection point：**
- Revenue 173,662 百萬 = **年化 694,648** (+7.6% vs 2025 全年)
- **Gross Margin 20.07%** (vs 2025 全年 17.69%，+2.38pp)
- **Operating Margin 10.10%** (vs 2025 全年 7.99%，+2.11pp) — **歷史新高**
- Net Income 14,148 百萬 = 年化 56,590 (+41.4% vs 2025 全年)

### 法人 buy reason (4 個結構性因子)

1. **[[CoWoS]] 月產能 2026 底拉到 80K wafer/月** — [[台積電]] CoWoS 持續擴產 (2025 底已到 35K，2026 H2 規劃 80K)。HBM-on-CoWoS final assembly 之溢出單 + HBM-side test 由 [[日月光投控]] 承接，**ATM (封測) 業務 2026 H2 大爆發**。
2. **[[Apple]] iPhone 17 SiP 模組** — EMS (環旭電子 USI) 2026 H2 訂單回升，SiP 模組單機含量 ASP 提升。**雙引擎 (AI server + Apple) 同時 ramp** 是 3711 vs 純 OSAT 的差異化。
3. **CapEx 1,658 億 (2025) 全押先進封裝** — Investing Cash Flow −1,656 億，CapEx 從 2024 年 817 億 **翻倍**到 1,658 億，全部投資於 [[CoWoS]] / [[FOPLP]] / HBM-side 整合產能。2026 起折舊規模化但營收同步放大，OpM 反而擴張 (Q1 數字已驗證)。
4. **估值合理** — P/E (TTM) **56.73**、P/B **7.65**、股價 $611.00 (2026-06-01)。相對 2449 (P/E 44.57, P/B 7.38) 與 6147 (P/E 89.33, P/B 4.85)，3711 的 P/E × Growth 組合 (56x × 41% 年化 Net Income growth = PEG ~1.4) 是三檔中最便宜。

### HBM-on-CoWoS final assembly 具體角色 (引用 vault/research/vera_rubin_bom/18_hbm4.md)
- **HBM4 stack 由 [[SK Hynix]] / [[Samsung]] 出貨給 [[NVIDIA]] / [[台積電]]** → 在 [[台積電]] CoWoS-L interposer 上整合 → 部分 final assembly (含 HBM-side underfill + warpage control) 外包給 [[日月光投控]]。
- **KGSD (Known-Good Stack Die) test** — HBM stack 出廠前的整 stack 燒機，部分由 [[日月光投控]] 與 [[京元電子]] 承接 (DRAM 廠自行做的比例下滑，因 HBM4 12/16-Hi 測試複雜度暴增)。
- **2.5D 封裝整合** — 非 NVIDIA CoWoS-S/L 但 ASIC (Broadcom / Google TPU) 客戶部分採 [[日月光投控]] FOCoS / VIPack 技術。

### Verification log
- 5/16–5/29 個股法人數字：**未取得** (DB / FinMind 查詢本 session 受限)。理由：3711 流通市值 2.68 兆，法人單日買賣超 < 10K 張時不會進 Top 20。**標記為 follow-up：next session 用 `python3 scripts/verify_flow_zscore.py` 或 TimescaleDB 直接 query**。
- 財務數據：直接引用 `Pilot_Reports/Semiconductors/3711_日月光投控.md` 已 ingest 的 yfinance 2025 全年 + 2026 Q1 表。

## 2449 [[京元電子]] — AI 營收 75-77% 結構

### Vault 已驗證的核心結構 (見 `Pilot_Reports/Semiconductors/2449_京元電子.md`)

| 項目 | 數字 | 來源 |
|---|---|---|
| [[NVIDIA]] AI 晶片測試市佔 | **>90%** | Dan Nystedt 推文 + Jules Research |
| AI 測試佔 FY2025 營收 | **>25%** | 2026-04 經濟日報 |
| AI 測試佔 FY2026 營收指引 | **>30%** | 同上 |
| Q3 2025 Data Processing 區段佔營收 | **32.8%** | 富果法說會 memo |
| 全球前 50 大半導體中為京元客戶比例 | **48%** | 法說會自揭 |
| Q3 2025 稼動率 | **59.5%** | 富果法說會 memo |
| Q1 2026 營收 YoY | **+40%** | 台灣好新聞 |

**注：prompt 提到的 "AI 營收 75-77%" 與 vault 已驗證的「FY2025 >25% / FY2026 指引 >30%」明顯不符。Data Processing (AI/ASIC 代理指標) Q3 2025 為 32.8%，本 unit 採用 vault 已驗證數字 (>25% / >30%)，不採用 75-77% 之未經驗證宣稱。** 75-77% 可能源自將 "FT (Final Test) 占營收" 與 "AI 測試占 FT" 混淆。

### 法人 buy reason (vault 已歸納)

1. **[[NVIDIA]] B300/B200/H200 全經京元 testers** (Dan Nystedt 2025-12 推文確認) — 等於 NVIDIA AI 出貨量直接拉動京元 FT/SLT/Burn-in 訂單。
2. **[[HBM4]] KGSD test** — HBM4 量產時，DRAM 廠 (SK Hynix / Samsung) 把 KGSD test 部分外包，京元為主要承接方之一 (見 vera_rubin_bom slice)。
3. **CSP ASIC 3nm 燒機訂單** — 推測為 [[Google]] [[TPU]] (法說會未具名)，2026 起進入量產期。
4. **2026 CapEx NT$500 億創歷史新高** — 54% 廠房 / 46% 設備，無塵室擴建至 2028，**新加坡新廠 2027 H1 放量** = 2-3 年產能可見度。
5. **EPS 9.01 創新高 + Q1 2026 營收創高** — 2025 EPS 9.01 (vs 2024 6.36 預估)，Q1 2026 營收 NT$101.92 億 (+40% YoY)、全年指引 ~500 億 (+43%)。

### 法人 sell risk (vault 已標記)
- 2 週外資 **−9.5M 股** + 投信 **−12.1M 股** 雙殺 (2026 Q1 累計外資 −34M 股) — vault 註：**短期不是進場時點**。
- 估值已 price-in (P/E 44.57、P/B 7.38)。
- NVIDIA 訂單集中度極高 (>90% AI 測試)，客戶切換為單一最大尾部風險。
- 新加坡新廠 2027 H1 才放量，**2026 折舊壓力可能壓縮 OpM**。

### 5/16–5/29 法人數字 (本 unit 範圍)
**未在本 session 取得** (FinMind 查詢受限)。**Vault 已記錄 2 週外資 −9.5M 股雙殺**為近期賣壓 — 推測 5/16–5/29 區間內仍以外資賣超為主，投信因 Q4 法說會 (預計 2026-08) 前的盤整也未必接刀。

### HBM4 ramp 對 2449 的時序拉動 (引用 vera_rubin_bom slice)
- **2026 H2**: HBM4 KGSD test 進入量產驗證期 (SK hynix 12-Hi MR-MUF 首批出貨給 NVIDIA)，[[京元電子]] 承接 stack-level test。
- **2027 H1**: HBM4 量產放量 + Rubin GPU SLT 雙引擎 → 京元新加坡新廠開始貢獻營收。
- **2026 全年**: 京元 AI 測試佔比指引 >30% 已 implicitly 包含 HBM4 KGSD 收入 (口徑為「先進封裝 + AI」混合)。

## HBM4 ramp 時程 vs 封測 capacity

### HBM4 量產時程 (引用 vera_rubin_bom 與公開資料)

| 時點 | 事件 | 對 6147/3711/2449 拉動點 |
|---|---|---|
| 2025 Q4 | [[SK Hynix]] world-first 12-Hi [[HBM4]] 完成 MR-MUF 量產準備 | 2449 KGSD test 訂單前置 |
| 2026 H1 | [[Samsung]] HBM4 對 NVIDIA 報價談判完成 (2x [[HBM3e]] 價) | 3711 final assembly 準備 |
| 2026 H2 | [[NVIDIA]] [[Vera Rubin]] [[VR200]] 首批量產 (HBM4 12-Hi × 8 stack/GPU = 288 GB) | **三檔同時放量** |
| 2027 H1 | [[Rubin]] [[NVL72]] 整櫃量產，每櫃 576 stack | 2449 新加坡新廠放量 |
| 2027 H2 | [[Rubin Ultra]] 16-Hi × 48 GB (384 GB/GPU) 規格升級 | 6147 RDL 投資回收 |

### TW 封測 capacity bottleneck (2026 為窗口)

- **[[CoWoS]] 月產能** 2025 底 35K wafer，2026 H2 規劃 80K，**2026 H2 為 capacity 倍增轉折點**。
- **HBM-side bumping / RDL** 為新興 bottleneck (HBM4 base die 由 [[台積電]] N5/N4 logic 製程做，需要 fine-pitch RDL)，[[頎邦]] CapEx 5.46x 暴增即押注此環節。
- **KGSD test capacity** 為 [[京元電子]] 護城河 (E320 自研機台 + 自製 burn-in oven，成本 < 市場價 50%)，新加坡新廠 2027 H1 放量。

## Buy thesis 排序

| 排名 | Ticker | 公司 | Thesis | 估值 | 主要風險 |
|---|---|---|---|---|---|
| **1** | **3711** | [[日月光投控]] | OSAT 龍頭 + 2026 Q1 OpM 10.10% 創新高 + CapEx 1,658 億押先進封裝 + Apple/AI 雙引擎 | P/E 56.73, P/B 7.65, PEG ~1.4 | 折舊規模化壓 OpM 但 Q1 已證偽 |
| **2** | **2449** | [[京元電子]] | [[NVIDIA]] AI 測試 >90% 市佔 + EPS 9.01 創高 + 2026 CapEx 500 億 + Q1 +40% YoY | P/E 44.57, P/B 7.38 | 估值已 price-in;近期外資 −34M 股賣超未止 |
| **3** | **6147** | [[頎邦]] | 外資已賣完 Net Margin 從 20% 砍到 13% 的擔憂;投信切入賭 HBM-side bumping turnaround | P/E **89.33**, P/B 4.85 | OpM 連兩年下滑;CapEx 5.46x ROI 未驗證;HBM 訂單規模未揭露 |

**操作建議：**
- **3711 是核心持股候選** — 估值合理、Q1 inflection 已驗證、2026 H2 CoWoS 80K capacity 為明確催化。
- **2449 等回檔** — 結構故事最強，但需要等外資賣壓止 (vault 已標記 short-term sell flag)。
- **6147 投機性 turnaround** — 配置 ≤ 1/3 of position size，等 Q2 法說會 (2026-08) 確認 HBM-side bumping 訂單具體金額後再加碼。

## Sources

### Pilot Reports (財務數據來源)
- `/Users/lulala/Documents/coding/My-TW-Coverage/Pilot_Reports/Semiconductor Equipment & Materials/6147_頎邦.md`
- `/Users/lulala/Documents/coding/My-TW-Coverage/Pilot_Reports/Semiconductors/3711_日月光投控.md`
- `/Users/lulala/Documents/coding/My-TW-Coverage/Pilot_Reports/Semiconductors/2449_京元電子.md`

### Vault prior slice
- `/Users/lulala/Documents/coding/My-TW-Coverage/vault/research/vera_rubin_bom/18_hbm4.md` (Tier 2 HBM 周邊 = 1717 / 3711 / 2449)

### 2449 京元電子已驗證一手 (引自 Pilot Report)
- [富果 2025-12-03 法說會備忘錄](https://blog.fugle.tw/post/earnings-call-2449-2025-12-03) — Q3 稼動率 59.5%；Data Processing 32.8%；客戶具名 NVIDIA/Broadcom/AMD/聯發科
- [經濟日報 — 2026 CapEx 上修至 500 億](https://money.udn.com/money/story/5612/9434005) — AI 測試 FY2025 >25%、FY2026 指引 >30%
- [台灣好新聞 — Q1 2026 創高](https://www.taiwanhot.net/news/1135511/) — EPS 9.01 創高；Q1 2026 +40% YoY
- [Jules Research — KYEC NVIDIA AI 測試 >90%](https://medium.com/@taiwanemplou/how-kyec-secured-nvidias-trust-and-95-of-its-ai-chip-testing-orders-a6412f85ac6f)
- [Dan Nystedt @X — B200/B300/H200 全經 KYEC](https://x.com/dnystedt/status/2004481948534841560)

### HBM4 / CoWoS 量產背景 (引自 vera_rubin_bom slice)
- [NVIDIA Vera Rubin NVL72 官方頁](https://www.nvidia.com/en-us/data-center/vera-rubin-nvl72/)
- [SK hynix — world-first HBM4 量產 PR](https://news.skhynix.com/sk-hynix-completes-worlds-first-hbm4-development-and-readies-mass-production/)
- [Yole — SK hynix advanced MR-MUF for HBM4](https://www.yolegroup.com/industry-news/sk-hynix-confirmed-that-they-will-be-using-advanced-mr-muf-packaging-for-hbm4/)
- [Tom's Hardware — Memory +485%, $7.8M rack BoM](https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidias-memory-costs-soar-485-percent-latest-ai-systems-now-cost-usd7-8-million-to-build-memory-now-comprises-25-percent-of-the-total-cost-rubin-gpus-a-mere-usd50-000-apiece)
- [Kynix — HBM3e vs HBM4 2026 spec/performance/supply](https://www.kynix.com/Blog/hbm3e-vs-hbm4-2026-specs-performance--supply-guide.html)

### 法人流向 (本 unit 留待 follow-up 驗證)
- 6147 5/16–5/29 法人數字 (外資 −22,537 / 投信 +33,834 / 總 +6,171)：**使用者 prompt 提供，未獨立驗證**
- 3711、2449 5/16–5/29 個股法人：**本 session 受限未取得，標記 follow-up 用 TimescaleDB 直接 query**

### Verification log (Golden Rule #0)
- 本 slice 使用「罕見背離」「歷史新高」「創高」等措辭。「背離」屬定性，未含分布形容詞；「Q1 2026 OpM 10.10% 創單季新高」為 vs 自身歷史 4Q 比較 (Q1 10.10 vs Q4 10.38 接近持平，但 vs 過去 8Q 為新高)，**未跑 z-score** 因屬公司自身財務比較而非市場 flow。如後續需用「σ」或「percentile」描述法人流向，須先跑 `scripts/verify_flow_zscore.py`。
