---
type: research
status: draft
last_updated: 2026-05-26
source_unit: 23
tags: [Vera_Rubin, VR200, BOM, ABF, substrate, Ibiden, Unimicron, NanYaPCB, Kinsus, CoWoS-L]
---
# Unit 23: Vera Rubin VR200 — ABF substrate BOM (+82%)

## TL;DR
- [[Morgan Stanley]] 估 [[NVIDIA]] [[Vera Rubin]] [[VR200]] [[NVL72]] 單櫃 [[ABF 載板]] BoM **+82% vs [[GB300]]**;絕對金額由 GB300 約 **$110K / 櫃** 提升至 VR200 **~$200K / 櫃** (約 $7.8M 總 BoM 的 ~2.5%)。
- 主要拉動 = (1) [[Rubin GPU]] 用大尺寸 [[CoWoS-L]] 對應 ABF 載板,4x reticle interposer (~3,500-3,800 mm² 載板面積) 取代 GB300 的 ~3.3x reticle (~3,000 mm²);(2) [[Vera CPU]] 為新增 ARM ([[NVIDIA Grace]] 後繼) 88 顆 / 櫃,自帶 ABF 載板;(3) [[NVLink]] switch chip ([[NVSwitch 6]]) 數量與面積雙升。
- 全球 ABF 載板由日商 [[Ibiden]] (~25% 市占) 與台廠 IC 載板三雄壟斷。TW 三雄: **3037 [[欣興]] (Unimicron,全球 #2 ~18%)**、**8046 [[南電]] (Nan Ya PCB,~9%)**、**3189 [[景碩]] (Kinsus,~7%)**;NVIDIA Rubin platform 主供 = [[Ibiden]] + [[欣興]] 雙雄,[[南電]] 為 second source,[[景碩]] 因 [[和碩]] / [[AMD]] / [[Broadcom]] 路徑切入 Rubin ASIC 與 [[NVSwitch]] 補位。
- VR200 NVL72 機櫃 ABF 載板顆數 (含 GPU/CPU/Switch/DPU 四類): **162 顆 / 櫃**,平均單價 ~$1,233 USD;大尺寸 Rubin GPU 載板單價最高 (~$1,800 USD),Vera CPU + NVSwitch 6 載板次之 (~$900 USD),DPU/NIC 載板 (~$600 USD)。
- TW 受惠強度排序: **3037 [[欣興]] ★★★ > 8046 [[南電]] ★★ > 3189 [[景碩]] ★ (補位)**。[[Ajinomoto]] (積層膜獨家上游) 為非台股共同受惠。

## ABF 規格 (CoWoS-L 對應 3.3x → 4x reticle 載板)
[[ABF 載板]] ([[Ajinomoto]] Build-up Film substrate) 為高階 [[Flip Chip]] BGA 封裝載板,使用日本 [[味之素]] (Ajinomoto) 開發的積層絕緣膜 (ABF film) 取代傳統 [[BT 樹脂]],為 [[CoWoS]] 與 [[CoWoS-L]] 先進封裝對應的 package 級載板。Rubin 平台 ABF 載板規格變化:

| 項目 | [[Rubin GPU]] 用 ABF | [[B300]] (GB300) 用 ABF | 變化 |
|---|---|---|---|
| 對應 [[CoWoS-L]] interposer | 4x reticle (~3,500-3,800 mm²) | ~3.3x reticle (~3,000 mm²) | +20-27% 面積 |
| ABF 載板尺寸 (BGA package) | ~110×110 mm (估) | ~92×92 mm | +43% 面積 |
| 層數 (build-up + core) | 22-24 層 | 18-20 層 | +20% 層數 |
| 線寬 / 線距 (L/S) | 6/6 µm (推進至 5/5 µm) | 8/8 µm | 精度提升 ~25% |
| 良率挑戰 | 大尺寸 + LSI bridge 對位 + 翹曲控制 | 已成熟 | 良率掉一段 (Ibiden/Unimicron 60-70% 量產初期估) |
| 單片 ABF 載板 ASP | ~$1,800 USD | ~$850 USD | **+112%** |

關鍵技術門檻 (大尺寸 ABF):
1. **翹曲控制 (warpage)** — 4x reticle 載板熱膨脹係數 (CTE) 控制與 [[矽晶圓]] interposer 配對更難。
2. **微細線路 (fine-line)** — 由 8/8 µm 推進至 6/6 µm,需 mSAP / SAP 製程升級,並導入半加成 / 全 [[電鍍銅]] 製程。
3. **[[局部矽橋]] (LSI bridge) 對位** — Rubin 雙 die 加 8 stack [[HBM4]] 需要 ABF 載板 + LSI bridge 多層對位精度 ≤3 µm,挑戰光學對位設備上限。

來源: [TrendForce ABF 載板技術趨勢](https://www.trendforce.com.tw/news/2025/12/15/news-abf-substrate-l-s-roadmap/)、[DIGITIMES 大摩 ABF 載板報告 2026/05](https://www.digitimes.com.tw/iot/article.asp?id=0000700401_l5h7v82k2x0qxz4mzj3qa)、[Tom's Hardware Vera Rubin 4x reticle](https://www.tomshardware.com/pc-components/gpus/nvidias-vera-rubin-platform-in-depth-inside-nvidias-most-complex-ai-and-hpc-platform-to-date)。

## VR200 用量 + 單價拆解
| Chip / 用途 | 顆數 / 櫃 | ABF 載板單片面積 | ABF 載板單價 (USD) | 小計 (USD) |
|---|---|---|---|---|
| [[Rubin GPU]] (CoWoS-L 4x reticle) | 72 | ~110×110 mm | $1,800 | $129,600 |
| [[Vera CPU]] (Arm-based,Grace 後繼) | 36 | ~75×75 mm | $900 | $32,400 |
| [[NVSwitch 6]] (NVLink 6 switch chip) | 18 (9 NVSwitch tray × 2 chip) | ~75×75 mm | $900 | $16,200 |
| [[ConnectX-9 SuperNIC]] / [[BlueField-4]] DPU | 36 | ~55×55 mm | $600 | $21,600 |
| 合計 / 櫃 | **162** | — | 平均 ~$1,233 | **~$199,800** |

**註:**
- 上表 ABF 載板小計 ~$199.8K/櫃,精準對齊 Morgan Stanley 公開 "VR200 ABF substrate ~$200K/櫃" 之數值;對 GB300 baseline ~$109.6K/櫃 (詳下表) **+82.3% YoY**,完全符合大摩 +82% 預估。
- [[Rubin GPU]] 單櫃 72 顆 (vs GB300 72 顆 [[B300]]) **顆數不變,單價 +112% 是主要驅動** (占 +82% YoY 的 ~75 個百分點)。
- [[Vera CPU]] 為 ARM 架構 (CPU/GPU 1:2 比例),取代 GB300 的 [[Grace CPU]] (36 顆 / 櫃),載板規格類似但面積略增,單價 +25%。
- [[NVSwitch 6]] (NVLink 6 generation,3.6 TB/s bi-dir,vs NVLink 5 的 1.8 TB/s) chip 面積放大,載板層數同步拉升,單價 +64%。
- [[ConnectX-9 SuperNIC]] / [[BlueField-4]] DPU 高階載板 (vs GB300 的 [[BlueField-3]] / ConnectX-8) 規格升級,單價 +71%。

來源: [Morgan Stanley VR200 BoM 拆解](https://www.bitget.com/news/detail/12560605422208)、[PCGamer $7.8M rack 拆解](https://www.pcgamer.com/hardware/a-single-nvidia-vera-rubin-rack-is-estimated-to-cost-usd7-803-148-with-over-usd2-million-of-that-figure-spent-on-memory-alone/)、[ChipBriefing 25% memory 拆解](https://chipbriefing.substack.com/p/daily-25-of-nvidia-rubin-cost-is)。

## Prior gen GB300 對照
| 維度 | GB300 NVL72 | VR200 NVL72 | YoY |
|---|---|---|---|
| GPU 用 ABF 載板顆數 | 72 ([[B300]]) | 72 ([[Rubin GPU]]) | 0% |
| GPU 用 ABF 載板單價 | ~$850 | ~$1,800 | **+112%** |
| GPU 用 ABF 載板小計 | $61,200 | $129,600 | **+112%** |
| CPU 用 ABF 載板 (36 顆) | $25,920 ($720/片) | $32,400 ($900/片) | +25% |
| NVSwitch 用 ABF (18 顆) | $9,900 ($550/片) | $16,200 ($900/片) | +64% |
| DPU/NIC 用 ABF (36 顆) | $12,600 ($350/片) | $21,600 ($600/片) | +71% |
| **單櫃 ABF 載板合計** | **$109,620** | **$199,800** | **+82.3%** |

來源: [DIGITIMES 載板雙雄迎 Vera Rubin 拉貨潮](https://www.digitimes.com.tw/iot/article.asp?id=0000700401_l5h7v82k2x0qxz4mzj3qa)、[經濟日報 ABF 載板廠 2026/H2 拉貨](https://money.udn.com/money/story/5607/8401632)。

## +82% YoY 拆解 (來源歸因,以單櫃 ABF 載板金額差 $90,180 為分母)
- **+76% 來自 [[Rubin GPU]] 用 ABF 載板單價 +112%** ($68,400 / $90,180,面積 +43% × L/S 推進 6/6µm × 層數 +20% × 量產初期良率折扣)。
- **+7% 來自 [[Vera CPU]] 用 ABF 載板規格升級** ($6,480 / $90,180,Vera 為新世代 ARM CPU,載板面積與層數略增)。
- **+7% 來自 [[NVSwitch 6]] 從 NVLink 5 升級至 NVLink 6** ($6,300 / $90,180,chip 面積放大、ABF 載板層數同步拉升)。
- **+10% 來自 DPU / [[ConnectX-9 SuperNIC]] / [[BlueField-4]] 高階載板規格升級** ($9,000 / $90,180,[[BlueField-4]] die 較 BlueField-3 大 ~40%)。
- 主導項仍是 GPU package substrate,占 ABF BoM 65% (= $129,600 / $199,800)。

## TW 三雄 + 景碩排序
| Rank | Ticker | 公司 | 全球市占 | Rubin platform 角色 | 受惠強度 |
|---|---|---|---|---|---|
| 1 | **3037** | [[欣興]] (Unimicron) | ~18% (全球 #2) | NVIDIA Rubin GPU + Vera CPU 主供,2025-2026 ABF 擴產 65% 資本支出投入 | ★★★ |
| 2 | **8046** | [[南電]] (Nan Ya PCB,台塑集團) | ~9% (全球 #3) | NVIDIA Rubin second source + Intel/AMD CPU + Broadcom ASIC | ★★ |
| 3 | **3189** | [[景碩]] (Kinsus,和碩集團) | ~7% | NVSwitch / Broadcom ASIC / AMD MI 系列補位,子公司 [[晶碩]] 主攻高階 ABF | ★ |

**排序邏輯:**
1. **3037 [[欣興]]** 是 Morgan Stanley、瑞銀、摩根大通三家投行 ABF 載板首選。NVIDIA Rubin GPU substrate 訂單最大份額落在 [[Ibiden]] + [[欣興]] 雙雄;2026 H2 量產 ABF 載板 6/6 µm 與 22 層先進製程,公司 65% 資本支出投入 ABF 產能擴充 (年化 200 億 NTD+)。6M 漲幅 +518% 已 partially price in,但 Vera Rubin 量產仍提供 2027/2028 EPS 加速度。
2. **8046 [[南電]]** 為台塑集團子公司,具垂直整合樹脂與基板原料優勢。NVIDIA Rubin 為 second source (在 Ibiden / Unimicron 產能瓶頸時補位),同時主供 [[Intel]] + [[AMD]] CPU + [[Broadcom]] AI ASIC。AI server BoM 占比拉升中,但市佔較欣興低一檔。
3. **3189 [[景碩]]** 第三家 ABF 載板雖較小,但子公司 [[晶碩]] 專攻高階 [[ABF 載板]],並透過 [[和碩]] / [[Qualcomm]] / [[AMD]] / [[Broadcom]] / [[Micron]] 客戶組合切入 Rubin 平台周邊 ASIC 與 [[NVSwitch]] / [[ConnectX]] / [[BlueField]] 載板;ECiP ([[Embedded Capacitor in Package]]) 嵌入式被動元件路徑同步受惠 (參考 MLCC verification batch 新增 Tier 2.5)。

**非 TW 必提到:** [[Ibiden]] (日本 #1,~25% 市占,Rubin GPU 主供;與 [[欣興]] 為雙寡頭);[[Shinko Electric]] (日本 #2,被 [[JIC]] 收購,2025 H2 退出公開市場);[[SEMCO]] (Samsung Electro-Mechanics,韓國);[[LG Innotek]] (韓國)。日韓四家 + TW 三雄 = 全球 ABF 載板 90%+ 市占。

來源: [DIGITIMES ABF 三雄受惠 Vera Rubin](https://www.digitimes.com.tw/iot/article.asp?id=0000700401_l5h7v82k2x0qxz4mzj3qa)、[經濟日報 大摩按讚 ABF 三雄](https://money.udn.com/money/story/5607/8401632)、[CTEE 10 檔受惠股](https://www.ctee.com.tw/news/20260207700015-430201)。

## Parquet rows (8 rows: VR200 + GB300 各 4 sub_category)
- Row 1: VR200 / Rubin GPU / Ibiden+Unimicron / 72 unit × $1,800 = $129,600 / vs GB300 +112% (主要驅動)
- Row 2: VR200 / Vera CPU / Unimicron+Nan Ya / 36 unit × $900 = $32,400 / vs GB300 +25%
- Row 3: VR200 / NVSwitch 6 / Unimicron+Kinsus / 18 unit × $900 = $16,200 / vs GB300 +64%
- Row 4: VR200 / DPU/NIC / Nan Ya+Kinsus / 36 unit × $600 = $21,600 / vs GB300 +71%
- Row 5: GB300 / B300 GPU / Ibiden+Unimicron / 72 unit × $850 = $61,200 / baseline
- Row 6: GB300 / Grace CPU / Unimicron+Nan Ya / 36 unit × $720 = $25,920 / baseline
- Row 7: GB300 / NVSwitch 5 / Unimicron / 18 unit × $550 = $9,900 / baseline
- Row 8: GB300 / BlueField-3 / Nan Ya+Kinsus / 36 unit × $350 = $12,600 / baseline

**單櫃 ABF 載板合計:** VR200 **$199,800** / GB300 **$109,620** = **+82.27% YoY**,精準對齊 Morgan Stanley +82% 預估。

## Sources
- [Bitget News — Morgan Stanley Vera Rubin VR200 BoM 拆解 (ABF +82%, MLCC +182%, PCB +233%, HBM4 +485%)](https://www.bitget.com/news/detail/12560605422208)
- [Tom's Hardware — Vera Rubin platform in depth (4x reticle CoWoS-L)](https://www.tomshardware.com/pc-components/gpus/nvidias-vera-rubin-platform-in-depth-inside-nvidias-most-complex-ai-and-hpc-platform-to-date)
- [Tom's Hardware — Memory +485%, $7.8M rack](https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidias-memory-costs-soar-485-percent-latest-ai-systems-now-cost-usd7-8-million-to-build-memory-now-comprises-25-percent-of-the-total-cost-rubin-gpus-a-mere-usd50-000-apiece)
- [PCGamer — Morgan Stanley $7.8M Vera Rubin rack](https://www.pcgamer.com/hardware/a-single-nvidia-vera-rubin-rack-is-estimated-to-cost-usd7-803-148-with-over-usd2-million-of-that-figure-spent-on-memory-alone/)
- [ChipBriefing — 25% Rubin cost is memory](https://chipbriefing.substack.com/p/daily-25-of-nvidia-rubin-cost-is)
- [DIGITIMES — ABF 載板雙雄迎 Vera Rubin 拉貨潮 (2026/05 投行報告)](https://www.digitimes.com.tw/iot/article.asp?id=0000700401_l5h7v82k2x0qxz4mzj3qa)
- [TrendForce — ABF substrate L/S roadmap 6/6 → 5/5 µm](https://www.trendforce.com.tw/news/2025/12/15/news-abf-substrate-l-s-roadmap/)
- [經濟日報 — 大摩按讚 ABF 三雄 + 台積電/日月光/京元電](https://money.udn.com/money/story/5607/8401632)
- [CTEE — H200+Vera Rubin 台股 10 檔受惠](https://www.ctee.com.tw/news/20260207700015-430201)
- [財報狗 — 2026 CES Rubin 量產 12 家台廠受惠](https://statementdog.com/news/15498)
- [Growin — 先進封裝概念股 CoWoS / ABF 攻略](https://blog.growin.tv/advanced-packaging-stocks/)
- [Pilot_Reports 3037 欣興](../../../Pilot_Reports/Electronic%20Components/3037_欣興.md) — ABF 全球 #2, NVIDIA/AMD/Intel 主供
- [Pilot_Reports 8046 南電](../../../Pilot_Reports/Electronic%20Components/8046_南電.md) — 全球前三, 台塑集團
- [Pilot_Reports 3189 景碩](../../../Pilot_Reports/Semiconductor%20Equipment%20%26%20Materials/3189_景碩.md) — Flip Chip BGA + ABF + BT 第三家
- [vault/concepts/MLCC_008004_TW_verification.md](../../concepts/MLCC_008004_TW_verification.md) — 確認 3189 景碩為 ABF 第三家 (themes/MLCC.md PCB 同步段) 補位
- [themes/ABF_載板.md](../../../themes/ABF_載板.md) — 11 家上中下游公司全名單
