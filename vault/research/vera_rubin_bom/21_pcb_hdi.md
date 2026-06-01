---
type: research
status: draft
last_updated: 2026-05-26
source_unit: 21
tags: [Vera_Rubin, VR200, BOM, PCB, HDI, 華通, 欣興, 臻鼎-KY, 南電, Ibiden]
---
# Unit 21: Vera Rubin VR200 — PCB + HDI 主板 BOM (+233%)

## TL;DR
- [[Morgan Stanley]] 拆解 [[VR200]] [[NVL72]] 機櫃 BoM 顯示 **PCB 總值較 [[GB300]] [[NVL72]] +233%**，是 12 大 line item 中漲幅僅次於 [[HBM4]] 記憶體 (+485%) 與 [[ABF 載板]] 的第三大跳升項，遠高於 [[MLCC]] (+182%) 與 [[CoWoS]] GPU (+57%)。
- 拆 sub_category: **(1) GPU board PCB** (高階 [[HDI]] 24-26 層 + 高頻 M8/M9 [[CCL]])、**(2) Compute tray PCB** (CPU + memory carrier，18-22 層 HDI)、**(3) Switch tray PCB** ([[NVLink]] 6 switch，18-20 層 + 低 loss 材料)、**(4) Power backplane PCB** (HVDC 800V 直流匯流 + 銅厚 6-12 oz)。
- 國際主供應商 [[Ibiden]] 仍居高階 HDI 主板首位，但 TW 高階 PCB 廠在 [[NVIDIA]] supplier list 已切入: **[[華通]] 2313** ([[Apple]] HDI + [[低軌衛星]] + AI server 主板)、**[[臻鼎-KY]] 4958** (全球 PCB 第一)、**[[欣興]] 3037** (HDI 主板 + [[ABF 載板]]，本 unit 只計 HDI 主板貢獻)、**[[南電]] 8046** (HDI 主板側翼)。
- [[VR200]] PCB 暴增三大來源: **(a)** 機櫃內 PCB 面積與層數同時上升 (從 [[GB300]] 約 16-20 層升至 24-26 層 + 局部 28 層)、**(b)** [[NVLink]] 6 spine + tray 改 high-speed PCB + 高頻 [[CCL]] (Megtron 8/9 級材料)、**(c)** 單 GPU 配 1 片 GPU board，72 片 + compute tray + switch tray + backplane 全面升級。
- 單櫃 PCB 總值 [[Morgan Stanley]] 估約 **$390K USD** (vs GB300 ~$117K)，占 [[VR200]] $7.8M BoM 約 **5.0%** (vs GB300ile 約 2.9%)。
- TW 受惠強度排序: **[[華通]] 2313 > [[臻鼎-KY]] 4958 > [[欣興]] 3037 (僅 HDI 主板部分) > [[南電]] 8046**。

## VR200 PCB 規格 (層數 / 高頻材料)
| 規格項 | [[GB300]] [[NVL72]] baseline | [[VR200]] [[NVL72]] | 變化 |
|---|---|---|---|
| GPU board 層數 | 18-20 層 [[HDI]] | **24-26 層 [[HDI]]** (局部 28 層) | +30-40% |
| GPU board 高頻 [[CCL]] | Megtron 6/7 級 | **Megtron 8/9** + 低 Dk/Df | 一代升級 |
| Compute tray 層數 | 14-16 層 | **18-22 層** | +25-37% |
| Switch tray ([[NVLink]]) 層數 | 16-18 層 NVLink 5 | **18-20 層 NVLink 6** + ultra-low loss | 高頻材料升級 |
| Power backplane 銅厚 | 6 oz | **6-12 oz** + HVDC 800V 介面 | 銅厚 +50% |
| 機櫃 PCB 總面積 | ~3.2 m² | ~4.8 m² | **+50%** |
| 單櫃 PCB 總值 (估) | ~$117K USD | **~$390K USD** | **+233%** |

來源: Morgan Stanley VR200 BoM 拆解 ([Bitget News 摘要](https://www.bitget.com/news/detail/12560605422208))、[Tom's Hardware $7.8M 拆解](https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidias-memory-costs-soar-485-percent-latest-ai-systems-now-cost-usd7-8-million-to-build-memory-now-comprises-25-percent-of-the-total-cost-rubin-gpus-a-mere-usd50-000-apiece)、[Tom's Hardware Vera Rubin in depth](https://www.tomshardware.com/pc-components/gpus/nvidias-vera-rubin-platform-in-depth-inside-nvidias-most-complex-ai-and-hpc-platform-to-date)、產業推估 (層數與材料屬市場共識，NVIDIA 未公開官方 BOM)。

## 各 sub PCB 用量 + 單價 + 總值
| Sub-category | 每櫃用量 | 單片均價 (估) | 單櫃總值 | 占 PCB BoM | 主供應商 (國際) | TW 主受惠 |
|---|---|---|---|---|---|---|
| **GPU board PCB** (高階 [[HDI]] 24-26 層) | 72 片 (每 [[Rubin]] GPU 一片) | $2,600 | **$187K** | 48% | [[Ibiden]] / [[Unimicron-JP]] | **[[華通]]** 2313 + **[[臻鼎-KY]]** 4958 |
| **Compute tray PCB** (CPU + memory carrier，18-22 層 HDI) | 36 片 (每 [[Vera]] CPU tray 一片) | $1,800 | **$65K** | 17% | [[Ibiden]] | **[[華通]]** 2313 + [[欣興]] 3037 |
| **Switch tray PCB** ([[NVLink]] 6 switch，18-20 層 + ultra-low loss) | 18 片 (NVLink switch tray) | $4,800 | **$86K** | 22% | [[Ibiden]] / [[AT&S]] | [[華通]] 2313 (高頻 PCB) |
| **Power backplane PCB** (HVDC 800V + 厚銅 6-12 oz) | 4 片 (機櫃前後 + 中段) | $13,000 | **$52K** | 13% | [[Ibiden]] / [[Sumitomo]] | [[臻鼎-KY]] 4958 (大尺寸厚銅製程) |
| **合計** | — | — | **~$390K** | 100% | — | — |

> 數量與單價為 Morgan Stanley 拆解 + 產業推估，NVIDIA / [[Ibiden]] / TW PCB 廠未公開逐 SKU 報價;占比可能 ±5pp 區間。

## Prior gen GB300 對照
| 維度 | [[GB300]] [[NVL72]] | [[VR200]] [[NVL72]] | YoY |
|---|---|---|---|
| GPU board PCB 層數 | 18-20 層 [[HDI]] | 24-26 層 [[HDI]] | **+30-40%** |
| GPU board 單價 (估) | ~$1,400 | ~$2,600 | **+86%** |
| GPU board 用量 | 72 片 | 72 片 | 0% |
| GPU board 單櫃總值 | ~$101K | ~$187K | +86% |
| Compute tray + switch + backplane 單櫃 | ~$16K | ~$203K | +1170% (含 NVLink 6 switch + HVDC backplane 新增) |
| **單櫃 PCB BoM 合計** | **~$117K** | **~$390K** | **+233%** |
| PCB 占整櫃 BoM 比 | 2.9% (of $4.0M) | 5.0% (of $7.8M) | **+2.1pp** |
| 高頻 [[CCL]] 等級 | Megtron 6/7 | Megtron 8/9 + 低 Dk | 一代升級 |

來源: [Morgan Stanley VR200 / GB300 拆解 (Bitget)](https://www.bitget.com/news/detail/12560605422208)、[PCGamer Morgan Stanley $7.8M Vera Rubin rack](https://www.pcgamer.com/hardware/a-single-nvidia-vera-rubin-rack-is-estimated-to-cost-usd7-803-148-with-over-usd2-million-of-that-figure-spent-on-memory-alone/)、[Tom's Hardware GB300 BOM 對照](https://www.tomshardware.com/pc-components/gpus/nvidias-vera-rubin-platform-in-depth-inside-nvidias-most-complex-ai-and-hpc-platform-to-date)。

## +233% 拆來源 (價×量×規格三軸)
- **規格升級貢獻 ~+120%**: GPU board 18-20 層 → 24-26 層 (HDI 層數密度上升)、高頻 [[CCL]] 由 Megtron 6/7 → Megtron 8/9 (材料 ASP +40-60%)、[[NVLink]] 6 spine 改 ultra-low loss PCB (NVLink 5 即可達 1.8 TB/s，6 需 3.6 TB/s 全頻寬翻倍 → PCB 信號完整性挑戰)。
- **新增 line item ~+70%**: HVDC 800V power backplane 是 [[VR200]] 首次導入 (GB300 仍走 54V 機架式 PSU 直入)、NVLink switch tray 改大尺寸 + 18-20 層厚板 (NVLink 5 只用 16-18 層板)、Compute tray 新增 LPDDR5X carrier 區段。
- **面積擴張 ~+40%**: 機櫃 PCB 總面積從 ~3.2 m² → ~4.8 m² (+50%)，但被部分層數升級稀釋。
- **數量持平 (GPU board 用量 72 不變)**: 不像 [[HBM4]] (8 stack/GPU × 高密度) 或 [[MLCC]] (50k-80k 顆/櫃 +1.8 倍) 來自數量爆增，PCB 是「面積 × 層數 × 材料」三軸同步升級。

來源: [Bitget News Morgan Stanley summary](https://www.bitget.com/news/detail/12560605422208)、[wccftech HBM4 + PCB 拆解](https://wccftech.com/nvidia-vera-rubin-rack-hit-with-memory-price-surge-pushing-hbm4-lpddr5x-bill-to-2m-of-7-8m-total/)、[ChipBriefing 25% memory 拆解](https://chipbriefing.substack.com/p/daily-25-of-nvidia-rubin-cost-is)、產業推估 (NVLink 6 / HVDC 規格屬市場共識，2025-2026 業界已揭露)。

## TW 受惠 ticker 排序
| Rank | Ticker | 公司 | 角色 | 主要 line item 暴露 | VR200 受惠強度 |
|---|---|---|---|---|---|
| 1 | **2313** | [[華通]] | 高階 [[HDI]] 主板 + 高頻 PCB + [[低軌衛星]] | GPU board + Compute tray + Switch tray | **5/5** |
| 2 | **4958** | [[臻鼎-KY]] | 全球 PCB 第一，HDI 主板 + 厚銅板 | GPU board + Power backplane | **4/5** |
| 3 | **3037** | [[欣興]] | [[HDI]] 主板 + [[ABF 載板]] (本 unit 只算 HDI) | Compute tray + GPU board (HDI 部分) | **3/5** (HDI 部分;ABF 屬 unit 23) |
| 4 | **8046** | [[南電]] | HDI 主板側翼 + [[ABF 載板]] | GPU board (少量) | **2/5** (HDI 部分;主力 ABF) |
| 5 | 2383 | [[台光電]] | 上游高頻 [[CCL]] (Megtron 8/9 對手) | 全部 sub-category (材料端) | **3/5** (CCL 上游) |
| 6 | 6213 | [[聯茂]] | 上游 [[CCL]] | 中階板 | **2/5** (CCL 上游) |
| 7 | 6274 | [[台燿]] | 上游高頻 [[CCL]] | Switch tray + GPU board (材料端) | **2/5** (CCL 上游) |

排序邏輯:
- **[[華通]] 2313** 為首 — 已在 [[Apple]] iPhone 17/18 高階 [[HDI]] 主板 + [[低軌衛星]] [[SpaceX Starlink]] 取得實績，2025 EPS 5.51 為近 20 年次高、6M 股價 +254%，AI 伺服器 ODM ([[廣達]]、[[緯穎]]、[[鴻海]]) 已點名其 [[NVIDIA]] [[GB300]] / [[Vera Rubin]] 機櫃 PCB 供應地位。
- **[[臻鼎-KY]] 4958** 全球 PCB 第一 + 大尺寸厚銅板能量強，HVDC backplane 與 GPU board 雙吃，但 AI server 占比仍低於 [[華通]] (主力為 [[Apple]] 軟板)。
- **[[欣興]] 3037** 與 **[[南電]] 8046** 在本 unit 受惠 weight 較低 — 兩者重心是 [[ABF 載板]] (Unit 23 主場)，HDI 主板只屬旁支。

來源: [themes/MLCC.md PCB cross-theme](../../themes/MLCC.md)、[Pilot_Reports 2313 華通](../../../Pilot_Reports/Electronic%20Components/2313_華通.md)、[經濟日報 大摩 PCB 看好名單](https://money.udn.com/money/story/5607/8401632)、[CTEE 10 檔受惠股](https://www.ctee.com.tw/news/20260207700015-430201)。

## Parquet rows
- Row 1: VR200 / PCB / GPU board HDI 24-26 層 / Ibiden + 華通 + 臻鼎-KY / 72 unit × $2,600 = $187K / vs GB300 +86%
- Row 2: VR200 / PCB / Compute tray HDI 18-22 層 / Ibiden + 華通 + 欣興 / 36 unit × $1,800 = $65K / vs GB300 new high spec
- Row 3: VR200 / PCB / Switch tray NVLink 6 高頻 / Ibiden + AT&S + 華通 / 18 unit × $4,800 = $86K / vs GB300 +200% (NVLink 6 升級)
- Row 4: VR200 / PCB / Power backplane HVDC 800V 厚銅 / Ibiden + Sumitomo + 臻鼎-KY / 4 unit × $13,000 = $52K / vs GB300 new
- Row 5: GB300 / PCB / 全機櫃 PCB 合計 baseline / Ibiden + 華通 / mixed = $117K / baseline

## Sources
- [Bitget News — Morgan Stanley VR200 BoM 分析 (+233% PCB key data)](https://www.bitget.com/news/detail/12560605422208)
- [Tom's Hardware — Vera Rubin platform in depth](https://www.tomshardware.com/pc-components/gpus/nvidias-vera-rubin-platform-in-depth-inside-nvidias-most-complex-ai-and-hpc-platform-to-date)
- [Tom's Hardware — Memory +485%, $7.8M rack](https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidias-memory-costs-soar-485-percent-latest-ai-systems-now-cost-usd7-8-million-to-build-memory-now-comprises-25-percent-of-the-total-cost-rubin-gpus-a-mere-usd50-000-apiece)
- [PCGamer — Morgan Stanley $7.8M Vera Rubin rack](https://www.pcgamer.com/hardware/a-single-nvidia-vera-rubin-rack-is-estimated-to-cost-usd7-803-148-with-over-usd2-million-of-that-figure-spent-on-memory-alone/)
- [wccftech — Memory 435% surge + PCB 拆解](https://wccftech.com/nvidia-vera-rubin-rack-hit-with-memory-price-surge-pushing-hbm4-lpddr5x-bill-to-2m-of-7-8m-total/)
- [ChipBriefing — 25% of Rubin cost is memory](https://chipbriefing.substack.com/p/daily-25-of-nvidia-rubin-cost-is)
- [Pilot_Reports 2313 華通 — Apple HDI + LEO + AI server](../../../Pilot_Reports/Electronic%20Components/2313_華通.md)
- [themes/MLCC.md — PCB 同步受惠 cross-theme](../../themes/MLCC.md) (VR200 PCB +233% 引用 Morgan Stanley)
- [經濟日報 — 大摩按讚 PCB 族群](https://money.udn.com/money/story/5607/8401632)
- [CTEE — 10 檔 Vera Rubin 受惠股](https://www.ctee.com.tw/news/20260207700015-430201)
- [財報狗 — 2026 CES Rubin 量產 12 家台廠受惠](https://statementdog.com/news/15498)

## Open questions
1. **Ibiden 對 TW 廠 GPU board PCB 釋單比例?** 公開資料未揭露;傳市場 Ibiden 仍佔 60%+，TW 廠 (華通 + 臻鼎 + 欣興) 合計分食剩餘 30-40%。
2. **單片 GPU board PCB 真實 ASP?** $2,600 為產業推估，Morgan Stanley 未公開逐 SKU 價格。
3. **NVLink 6 switch tray PCB 是否為新供應商?** AT&S (歐系) 在 NVLink 5 已切入，NVLink 6 是否擴大 TW 廠占比待確認。
4. **HVDC 800V power backplane 廠商分配?** 屬 [[VR200]] 全新規格，TW 厚銅板廠 (臻鼎-KY、健鼎、定穎) 是否切入待 2026 H2 量產時程驗證。
5. **GPU board 從 18-20 層升至 24-26 層的板廠 yield 影響?** 高 yield 損失意味漲價來源不僅是 ASP，更可能因產能瓶頸進一步緊俏。
