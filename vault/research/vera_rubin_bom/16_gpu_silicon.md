---
type: research
status: draft
last_updated: 2026-06-01
source_unit: 16
tags: [Vera_Rubin, VR200, BOM, GPU, TSMC, CoWoS]
---
# Unit 16: Vera Rubin VR200 — Rubin GPU silicon BOM

## TL;DR
- [[NVIDIA]] [[Vera Rubin]] [[VR200]] [[NVL72]] 機櫃單櫃配置 **72 顆 [[Rubin]] GPU package (= 144 顆 compute die)**，相較 [[GB300]] [[NVL72]] 同樣 72 顆 GPU package (72 顆 [[B300]] compute die)。
- 每顆 Rubin GPU package 售價約 **$55,000 USD** ([[Morgan Stanley]] 估算)，每櫃 GPU silicon 總值約 **$3.96M**，較 GB300 NVL72 的 $2.52M **+57% YoY**。
- 製程從 [[B300]] 的 [[TSMC]] [[N4P]] (4nm-class) 升級至 Rubin 的 [[TSMC]] [[N3P]] (3nm-class)，**一個 GW 等級 VR200 部署可吃掉 [[TSMC]] N3 總產能的一半以上**。
- 封裝從 [[CoWoS-L]] (B300, 約 3.3x reticle interposer) 升級到 Rubin 的 **4x reticle CoWoS-L interposer**，雙 reticle-size compute die + 兩顆 I/O die + 8 stack [[HBM4]]，封裝難度與面積大幅上升。
- 電晶體數從 [[Blackwell]] 的 208B 拉到 [[Rubin]] 的 **336B (+1.6x)**，FP4 算力達 50 PFLOPS/GPU。
- TW 主受惠: **[[2330]] [[台積電]]** (晶圓 + CoWoS)，**[[3711]] [[日月光投控]]** (advanced packaging outsourcing)，**[[2449]] [[京元電子]]** (Burn-in + Final Test + SLT)。

## Rubin GPU 規格 (die size, 製程, HBM4 介面)
| 項目 | [[Rubin]] R200 | [[B300]] [[Blackwell Ultra]] | 變化 |
|---|---|---|---|
| 製程 | [[TSMC]] [[N3P]] (3nm-class) | [[TSMC]] [[N4P]] (5nm-class) | 全節點縮減 |
| Compute die 配置 | 2x reticle-size die | 2x reticle-size die (~800mm² 各) | 持平 (面積) |
| Reticle size | 4x reticle [[CoWoS-L]] interposer | ~3.3x reticle [[CoWoS-L]] | +21% interposer 面積 |
| 電晶體 | 336B | 208B | **+1.6x** |
| Memory | 288GB [[HBM4]] @ 22 TB/s, 8 stack | 288GB [[HBM3e]] @ ~8 TB/s, 12-Hi 8 stack | 頻寬 +175% |
| SM count | 224 SM/GPU | (Blackwell ~160 SM/die) | 顯著拉高 |
| FP4 算力 | 50 PFLOPS/GPU | ~15 PFLOPS/GPU | **+233%** |
| [[NVLink]] | NVLink 6, 3.6 TB/s bi-dir | NVLink 5, 1.8 TB/s | +100% |

來源: [Tom's Hardware Vera Rubin in depth](https://www.tomshardware.com/pc-components/gpus/nvidias-vera-rubin-platform-in-depth-inside-nvidias-most-complex-ai-and-hpc-platform-to-date)、[awesomeagents R200](https://awesomeagents.ai/hardware/nvidia-rubin-r200/)、[tech-insider GTC 2026 分析](https://tech-insider.org/nvidia-gtc-2026-rubin-gpu-analysis/)。

## VR200 NVL72 GPU 用量 + cost
- **單櫃 GPU package 數: 72** (= 144 compute die，因 Rubin 為雙 die 設計；NVIDIA 在 GTC 2025 一度用 "NVL144" 計 die 數，後改回以 package 數命名)。
- **單顆 Rubin GPU 售價 ~ $55,000 USD** ([[Morgan Stanley]])。
- **單櫃 GPU silicon 總值 ≈ 72 × $55,000 = $3.96M** (Morgan Stanley 估算落在 ~$4M)。
- 整櫃 VR200 NVL72 BoM 約 **$7.8M USD**，GPU 占比 **~51%** (vs GB300 的 ~65%) — GPU 仍是最大單一成本，但其他項目 (HBM、PCB、MLCC、ABF、Power、Cooling) 占比同步上升。

來源: [Tom's Hardware $7.8M VR200 BoM](https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidias-memory-costs-soar-485-percent-latest-ai-systems-now-cost-usd7-8-million-to-build-memory-now-comprises-25-percent-of-the-total-cost-rubin-gpus-a-mere-usd50-000-apiece)、[wccftech HBM4 surge](https://wccftech.com/nvidia-vera-rubin-rack-hit-with-memory-price-surge-pushing-hbm4-lpddr5x-bill-to-2m-of-7-8m-total/)、[ChipBriefing 25% memory 拆解](https://chipbriefing.substack.com/p/daily-25-of-nvidia-rubin-cost-is)。

## CoWoS 封裝 ([[CoWoS-L]] 升級)
- Rubin 採 **[[CoWoS-L]] 4x reticle interposer** (B300 為 ~3.3x reticle)，需配合 [[局部矽橋]] (LSI, Local Silicon Interconnect) 銜接兩顆 compute die 與 8 stack [[HBM4]]。
- [[TSMC]] CoWoS 月產能 2026 拉至 **~120,000 wafers/month**，其中相當比例給 Rubin。
- 一座 GW 級 VR200 cluster (含網路、cooling、CPU 加總) 估算需吃掉 TSMC **N3 總產能的 50%+**，產能緊俏由 NVIDIA 包下大半，[[OpenAI]]、[[Microsoft]]、[[Meta]]、[[Amazon]] 等 hyperscaler 預下單已超 T 數量級美元 (見 trendforce / isaiahresearch 報告)。
- Rubin Ultra (2027) 仍維持 dual-die 結構，packaging 限制 (4x reticle 已逼近 CoWoS-L 上限) 是主要因素，預期由 [[CoPoS]] (panel-level) 接棒。

來源: [Isaiah Research VR200 N3 capacity](https://www.isaiahresearch.com/Insight/Detail/107)、[TrendForce Rubin Ultra dual-die](https://www.trendforce.com/news/2026/04/01/news-nvidias-rubin-ultra-seen-sticking-to-dual-die-design-on-packaging-constraints-tsmc-3nm-demand-intact/)、[Growin 先進封裝概念股](https://blog.growin.tv/advanced-packaging-stocks/)。

## Prior gen GB300 baseline 對照
| 維度 | GB300 NVL72 | VR200 NVL72 | YoY |
|---|---|---|---|
| GPU package 數 | 72 (B300) | 72 (Rubin) | 0% |
| GPU compute die 數 | 72 (B300 單封裝雙 die 但統算) | 144 (Rubin 雙 die × 72 package) | +100% (die 計) |
| GPU 製程 | [[TSMC]] [[N4P]] | [[TSMC]] [[N3P]] | 節點 1.5 代縮減 |
| 單顆 GPU 售價 | ~$35,000 | ~$55,000 | +57% |
| 單櫃 GPU 總值 | ~$2.52M | ~$3.96M | **+57%** |
| 單櫃 BoM 合計 | ~$4.0M | ~$7.8M | **+95%** |
| GPU BoM 占比 | ~65% | ~51% | -14pp |
| 封裝 | [[CoWoS-L]] ~3.3x reticle | [[CoWoS-L]] 4x reticle | 面積 +21% |

來源: [PCGamer Morgan Stanley $7.8M 拆解](https://www.pcgamer.com/hardware/a-single-nvidia-vera-rubin-rack-is-estimated-to-cost-usd7-803-148-with-over-usd2-million-of-that-figure-spent-on-memory-alone/)、[Bitget News Morgan Stanley summary](https://www.bitget.com/news/detail/12560605422208)。

## YoY 變化拆解 (GPU silicon line item)
- **價格 +57%** 來自三層:
  1. 製程 N4P → N3P，N3 wafer ASP 比 N4 高 ~25-30% (TSMC 對 leading-edge 持續調漲)。
  2. Interposer 從 3.3x → 4x reticle，CoWoS-L silicon interposer + LSI bridge 成本上升。
  3. NVIDIA 對 hyperscaler 的 ASP 拉高 (Rubin 算力 +233%，賣價只漲 57%，hyperscaler 仍視為 cost-per-token 大降)。
- **數量 0%** (72 GPU package/櫃不變)，但 **compute die 翻倍 (72 → 144)**，因此 TSMC N3 wafer 消耗量在 die count 基準上大增。
- **BoM 占比 -14pp** 是因為 HBM4 (+435%)、PCB (+233%)、MLCC (+182%) 增幅遠大於 GPU 本身，稀釋 GPU 占比 — 反而台股「非 GPU 受惠族群」相對 GB300 世代更有看點。

## TW 受惠 ticker 排序
| Rank | Ticker | 公司 | 角色 | 直接受惠 line item |
|---|---|---|---|---|
| 1 | **2330** | [[台積電]] | N3P wafer + CoWoS-L 封裝 | GPU silicon 全部 |
| 2 | **3711** | [[日月光投控]] | Advanced packaging outsourcing ([[FOCoS]]、[[FOCoS-Bridge]]、2.5D/3D IC) | CoWoS 外包 + final assembly |
| 3 | **2449** | [[京元電子]] | Burn-in + Final Test + SLT | Rubin GPU 測試 |
| 4 | **6147** | [[頎邦]] | Driver IC bumping + DDIC 為主，CoWoS 相關 bumping/probing | 間接 |
| 5 | **3037** | [[欣興]] | [[ABF 載板]] | 不在本 unit 但與 GPU package substrate 相關 |

排序邏輯: 直接做 wafer + 封裝的 [[2330]] 拿到最大餅 (Morgan Stanley 同樣將 [[台積電]] 列首選)、[[日月光投控]] 是 CoWoS 外包與 OSAT 龍頭、[[京元電子]] AI 測試占營收 75-77% 直接 leverage Rubin 測試需求。

來源: [經濟日報 大摩按讚台積電/日月光/京元電](https://money.udn.com/money/story/5607/8401632)、[CTEE 10 檔受惠股](https://www.ctee.com.tw/news/20260207700015-430201)、[財報狗 12 家台廠](https://statementdog.com/news/15498)。

## Parquet rows
- Row 1: VR200 / Rubin GPU / TSMC N3P / 72 unit × $55,000 = $3.96M / vs GB300 +57%
- Row 2: GB300 / B300 GPU / TSMC N4P / 72 unit × $35,000 = $2.52M / baseline

## Sources
- [Tom's Hardware — Vera Rubin platform in depth](https://www.tomshardware.com/pc-components/gpus/nvidias-vera-rubin-platform-in-depth-inside-nvidias-most-complex-ai-and-hpc-platform-to-date)
- [Tom's Hardware — Memory +485%, GPU $50K apiece, $7.8M rack](https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidias-memory-costs-soar-485-percent-latest-ai-systems-now-cost-usd7-8-million-to-build-memory-now-comprises-25-percent-of-the-total-cost-rubin-gpus-a-mere-usd50-000-apiece)
- [PCGamer — Morgan Stanley $7.8M Vera Rubin rack](https://www.pcgamer.com/hardware/a-single-nvidia-vera-rubin-rack-is-estimated-to-cost-usd7-803-148-with-over-usd2-million-of-that-figure-spent-on-memory-alone/)
- [wccftech — Memory 435% surge, HBM4 + LPDDR5X $2M](https://wccftech.com/nvidia-vera-rubin-rack-hit-with-memory-price-surge-pushing-hbm4-lpddr5x-bill-to-2m-of-7-8m-total/)
- [Bitget News — Morgan Stanley Rubin BoM 分析](https://www.bitget.com/news/detail/12560605422208)
- [Isaiah Research — VR200 N3 capacity + front-loading](https://www.isaiahresearch.com/Insight/Detail/107)
- [TrendForce — Rubin Ultra dual-die packaging constraint](https://www.trendforce.com/news/2026/04/01/news-nvidias-rubin-ultra-seen-sticking-to-dual-die-design-on-packaging-constraints-tsmc-3nm-demand-intact/)
- [tech-insider — Rubin 336B 電晶體 GTC 2026 解讀](https://tech-insider.org/nvidia-gtc-2026-rubin-gpu-analysis/)
- [awesomeagents — R200 spec sheet](https://awesomeagents.ai/hardware/nvidia-rubin-r200/)
- [ChipBriefing — 25% of Rubin cost is memory](https://chipbriefing.substack.com/p/daily-25-of-nvidia-rubin-cost-is)
- [經濟日報 — 大摩按讚台積電/日月光/京元電](https://money.udn.com/money/story/5607/8401632)
- [CTEE — H200+Vera Rubin 台股 10 檔受惠](https://www.ctee.com.tw/news/20260207700015-430201)
- [財報狗 — 2026 CES Rubin 量產 12 家台廠受惠](https://statementdog.com/news/15498)
- [Growin — 先進封裝概念股 CoWoS 攻略](https://blog.growin.tv/advanced-packaging-stocks/)
- [Tweaktown — B300 N4P + CoWoS-L 製程](https://www.tweaktown.com/news/104836/nvidias-beefed-up-b300-ai-chip-production-pulled-forward-tsmc-n4p-cowos-advanced-packaging/index.html)
- [wccftech — B300 12-Hi HBM3e + CoWoS-L](https://wccftech.com/nvidia-blackwell-ultra-ai-gpus-b300-feature-12-hi-hbm3e-tsmc-cowos-l/)
