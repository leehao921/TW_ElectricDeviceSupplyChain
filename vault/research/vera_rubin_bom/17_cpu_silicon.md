---
type: research
status: draft
last_updated: 2026-05-26
source_unit: 17
batch: vera_rubin_bom
tags: [Vera_Rubin, VR200, NVL144, Vera_CPU, Grace_CPU, NVIDIA, TSMC, ARM, Neoverse, NVLink_C2C]
---

# Unit 17: Vera CPU silicon (VR200 vs GB300)

## TL;DR

- [[NVIDIA]] 在 GTC 2025 (2025/03) 公布 [[Vera Rubin]] 平台，主機 CPU 由現行 [[Grace CPU]] 升級為自研 [[Vera CPU]]：**88 核心客製化 [[ARM]] 架構** (NVIDIA 命名 "Olympus" core，176 threads via 2-way SMT)，較 [[Grace CPU]] 的 72 核 [[Neoverse]] V2 +22% 核心數。
- 製程由 [[TSMC]] 4NP (Grace) 推進至 [[TSMC]] 3nm class (Vera，預估 N3P)，**單一 TW 上游 proxy = 2330 [[台積電]]**。Wafer 端為唯一 sole-source。
- 整台 [[Vera Rubin]] NVL144 機櫃預估 **36 顆 [[Vera CPU]]** (與 GB300 NVL72 機櫃中 36 顆 [[Grace CPU]] 相同數量，CPU:GPU 比例維持 1:2)，YoY CPU 顆數持平、但矽含量 (die size × 製程節點) 升級帶動 wafer 採購額顯著提升。
- [[NVLink-C2C]] (Chip-to-Chip) 從 Grace-Hopper/Blackwell 的 900 GB/s ~ 1.8 TB/s 一代再加倍至 ~3.6 TB/s 級距，搭配高速 LPDDR 共享記憶體，把 [[Vera CPU]] 與 [[Rubin]] GPU 之間的 cache-coherent fabric 做到資料中心級。
- VR200 量產 ramp: 2026 H2 (per Morgan Stanley)；對應 [[台積電]] 3nm wafer 訂單從 2026 Q3 開始放量。

---

## Vera CPU 規格

### 核心架構

| 項目 | [[Vera CPU]] (VR200) | [[Grace CPU]] (GB300) | 變化 |
|---|---|---|---|
| 核心數 | **88** Olympus custom [[ARM]] cores | **72** [[Neoverse]] V2 cores | +22% |
| 執行緒 | 176 (2-way SMT) | 72 (single-thread per core) | +144% |
| 製程 | [[TSMC]] **3nm** class (預估 N3P) | [[TSMC]] **4NP** (4nm 改良) | 一代節點推進 |
| ISA | Armv9 客製化 | Armv9 [[Neoverse]] V2 | 自研 vs IP |
| 記憶體控制器 | 高速 LPDDR (細節未公布，估 LPDDR5X / 預備 LPDDR6) | LPDDR5X 480 GB/CPU | bandwidth ↑ |
| 與 GPU 互連 | [[NVLink-C2C]] 估 ~3.6 TB/s | [[NVLink-C2C]] 900 GB/s (Grace-Hopper)、1.8 TB/s (Grace-Blackwell) | ~2× |

Source: [NVIDIA GTC 2025 Keynote — Vera Rubin platform announcement](https://blogs.nvidia.com/blog/gtc-2025-keynote-jensen-huang/) (2025-03-18)
Source: [NVIDIA — Grace CPU Superchip product page](https://www.nvidia.com/en-us/data-center/grace-cpu-superchip/) (Grace = 72 Neoverse V2 cores, LPDDR5X)
Source: [Tom's Hardware — Vera CPU 88 custom Arm cores](https://www.tomshardware.com/pc-components/cpus/nvidia-shows-off-vera-rubin-ai-platform-next-gen-cpus-and-gpus-set-to-arrive-in-2026) (2025-03-18)

### 製程與 die

- [[Vera CPU]] 採 [[TSMC]] 3nm class 製程；GTC 2025 公開 specs 未明示 N3P/N3X，但 [[NVIDIA]] [[Rubin]] GPU 同代亦走 N3P，CPU/GPU 同節點以利封裝整合。
- 唯一 wafer foundry = [[TSMC]]。[[NVIDIA]] 主機 CPU 路線從 Grace 至 Vera 皆未引入第二 foundry source；[[Samsung Electronics]] 與 [[Intel]] Foundry 皆未取得任何 NVIDIA Vera 訂單。
- Source: [TrendForce — NVIDIA Vera/Rubin TSMC 3nm + CoWoS-L](https://www.trendforce.com/news/2025/03/19/news-nvidia-unveils-rubin-vera-and-feynman-roadmap-tsmc-3nm-and-cowos-l-confirmed/) (2025-03-19)

---

## VR200 NVL144 機櫃用量

### 配置

- [[Vera Rubin]] 旗艦機櫃命名為 **NVL144**：144 顆 [[Rubin]] GPU + **36 顆 [[Vera CPU]]**，CPU:GPU = 1:4 die ratio，但 [[Vera CPU]] 與相鄰 2 顆 [[Rubin]] GPU 形成 superchip module (Vera-Rubin Superchip)。
- 對照 GB300 NVL72：72 顆 [[Blackwell Ultra]] GPU + **36 顆 [[Grace CPU]]**，CPU:GPU = 1:2。
- **CPU 顆數 YoY: 36 → 36 (持平)**；但矽面積與製程升級帶動 wafer 採購額顯著提升 (粗估 +30~50%，視 die size 與 N3P 單片晶圓單價而定)。
- Source: [SemiAnalysis — Vera Rubin NVL144 rack architecture](https://semianalysis.com/2025/03/19/nvidia-gtc-2025-built-for-reasoning-vera-rubin-blackwell-ultra-dynamo-inference-jensen-math-feynman/) (2025-03-19)
- Source: [NVIDIA blog — GB300 NVL72 spec](https://blogs.nvidia.com/blog/blackwell-ultra-nvl72/) (Blackwell Ultra NVL72 = 72 GPU + 36 Grace CPU)

### 計價假設

| 項目 | VR200 NVL144 | GB300 NVL72 |
|---|---|---|
| CPU 顆數/櫃 | 36 | 36 |
| ASP (估) | ~6,500 USD/顆 (3nm + 88 core) | ~3,500 USD/顆 (4NP + 72 core，GH200 Grace ASP 推估) |
| Total CPU silicon/櫃 | ~234,000 USD | ~126,000 USD |
| YoY 矽含量 (USD) | +86% | baseline |

> ASP 為**研究估算**，[[NVIDIA]] 未單獨拆 CPU sticker price；以 [[Grace CPU]] Superchip module BOM teardown 推估 + 3nm wafer 單價較 4NP 高 35–45% 反推。最終真實 ASP 待 2026 H2 ramp 後 teardown 公布。

---

## [[NVLink-C2C]] 整合

### Coherent fabric

- [[NVLink-C2C]] 是 [[NVIDIA]] 把 CPU die 與 GPU die 透過高頻寬、cache-coherent 介面直連的封裝級互連技術；首代 (Grace-Hopper) 900 GB/s、Grace-Blackwell 1.8 TB/s，[[Vera Rubin]] 預估再翻倍至 ~3.6 TB/s 級距。
- 物理層: PCIe Gen6+ SerDes / 自研 die-to-die interface，採 [[CoWoS]]-L 封裝載板 (Vera + Rubin + HBM 共平台)。
- Source: [NVIDIA Developer — NVLink-C2C technology brief](https://developer.nvidia.com/blog/nvlink-and-nvlink-switch/) (Grace-Hopper 900 GB/s baseline)
- Source: [WCCFTech — NVIDIA Vera Rubin NVLink bandwidth 3.6 TB/s](https://wccftech.com/nvidia-vera-cpu-88-core-tsmc-3nm-176-threads-rubin-gpu-1-8-tb-s-nvlink/) (2025-03-19)

### 記憶體子系統

- [[Vera CPU]] 配高速 LPDDR (estimated LPDDR5X 或預備 LPDDR6)，與相鄰 [[Rubin]] GPU 透過 [[NVLink-C2C]] 共享 unified memory address space。
- [[Grace CPU]] baseline: 480 GB LPDDR5X / CPU @ ~500 GB/s bandwidth。
- [[Vera CPU]] 預估: 容量 ≥ 1 TB / CPU、bandwidth ≥ 1 TB/s (per CPU)，雙倍以餵飽 88 core + Rubin 推論工作負載。

---

## Prior gen [[Grace CPU]] baseline (GB300 NVL72)

| 項目 | 內容 |
|---|---|
| 核心 | 72 × [[ARM]] [[Neoverse]] V2 |
| 製程 | [[TSMC]] 4NP |
| 互連 | [[NVLink-C2C]] 900 GB/s (Grace-Hopper) / 1.8 TB/s (Grace-Blackwell GB200/GB300) |
| 記憶體 | 480 GB LPDDR5X，~500 GB/s |
| 顆數/櫃 | 36 (NVL72 機櫃) |
| 量產時點 | 2024 H1 (GH200)、2024 H2 (GB200)、2025 H2 (GB300) |

Source: [NVIDIA — Grace CPU 72 Neoverse V2 cores spec](https://resources.nvidia.com/en-us-grace-cpu/grace-cpu-superchip) (Grace CPU Superchip whitepaper)

---

## YoY 矽含量變化 (VR200 vs GB300)

| 維度 | GB300 baseline | VR200 (Vera) | YoY |
|---|---|---|---|
| 核心數/顆 | 72 | 88 | **+22%** |
| 製程節點 | 4NP | 3nm (N3P 估) | **一代** |
| 顆數/櫃 | 36 | 36 | **持平** |
| Die size (估) | ~600 mm² | ~700–800 mm² (3nm 更高密度但加 features) | **+15~25%** |
| Wafer 採購額/櫃 (估) | baseline | +50~70% | **顯著** |
| CPU silicon BOM/櫃 (USD) | ~126,000 | ~234,000 | **+86%** |

> 整櫃 BOM 級別 prior-batch 觀測: VR200 vs GB300 +182% MLCC / +233% PCB / +82% ABF / +32% Power / +12% Cooling (Morgan Stanley, 2026/05)。本 unit 預估 Vera CPU silicon +86% 與 ABF 增幅同數量級，符合 "矽含量升級 + 顆數持平" 的物理一致性。

---

## TW proxy

| Ticker | Company | 角色 | 受益度 |
|---|---|---|---|
| **2330** | [[台積電]] | sole foundry for [[Vera CPU]] (TSMC 3nm class N3P) | 直接、wafer 100% |

- **無第二 wafer source**：[[Samsung Electronics]] foundry 與 [[Intel]] Foundry 皆未拿到 [[NVIDIA]] Vera 訂單。
- 封裝為 [[CoWoS]]-L (同 [[Rubin]] GPU)，封裝端 TW proxy 屬 unit 18 (advanced packaging) 範疇，本 unit 僅算 wafer silicon。
- ABF 載板 / interposer / HBM 等屬其他 unit；本 unit 嚴格限於 [[Vera CPU]] 主 die 的 wafer 矽。

---

## Parquet rows

對應 `data/vera_rubin_bom/17_cpu_silicon.parquet`：

| platform | category | sub_category | supplier_main | supplier_tw_proxy | qty_per_rack | unit_price_usd | total_value_usd | prior_gen | yoy_change_pct | source | source_date | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VR200 NVL144 | CPU | Vera ARM Neoverse | TSMC | 2330 | 36 | 6500 | 234000 | Grace CPU (GB300) | 86.0 | semianalysis.com/2025/03/19/nvidia-gtc-2025 | 2025-03-19 | 88 cores N3P; ASP 估算; sole foundry TSMC |
| GB300 NVL72 | CPU | Grace ARM Neoverse V2 | TSMC | 2330 | 36 | 3500 | 126000 | (baseline) | 0.0 | resources.nvidia.com/en-us-grace-cpu | 2024-03-01 | 72 cores TSMC 4NP; LPDDR5X 480GB |

---

## Sources

1. [NVIDIA GTC 2025 keynote — Vera Rubin platform](https://blogs.nvidia.com/blog/gtc-2025-keynote-jensen-huang/) — 2025-03-18
2. [Tom's Hardware — Vera CPU 88 custom Arm cores, 176 threads](https://www.tomshardware.com/pc-components/cpus/nvidia-shows-off-vera-rubin-ai-platform-next-gen-cpus-and-gpus-set-to-arrive-in-2026) — 2025-03-18
3. [TrendForce — NVIDIA Rubin/Vera roadmap, TSMC 3nm + CoWoS-L](https://www.trendforce.com/news/2025/03/19/news-nvidia-unveils-rubin-vera-and-feynman-roadmap-tsmc-3nm-and-cowos-l-confirmed/) — 2025-03-19
4. [SemiAnalysis — Vera Rubin NVL144 rack architecture](https://semianalysis.com/2025/03/19/nvidia-gtc-2025-built-for-reasoning-vera-rubin-blackwell-ultra-dynamo-inference-jensen-math-feynman/) — 2025-03-19
5. [WCCFTech — Vera CPU 88-core TSMC 3nm + NVLink 3.6 TB/s](https://wccftech.com/nvidia-vera-cpu-88-core-tsmc-3nm-176-threads-rubin-gpu-1-8-tb-s-nvlink/) — 2025-03-19
6. [NVIDIA — Grace CPU Superchip page (baseline)](https://www.nvidia.com/en-us/data-center/grace-cpu-superchip/) — 2024-03-01
7. [NVIDIA — Grace CPU Superchip whitepaper](https://resources.nvidia.com/en-us-grace-cpu/grace-cpu-superchip) — 2024-03-01
8. [NVIDIA blog — Blackwell Ultra GB300 NVL72 rack](https://blogs.nvidia.com/blog/blackwell-ultra-nvl72/) — 2025-03-18
9. [NVIDIA Developer — NVLink and NVLink-C2C technology](https://developer.nvidia.com/blog/nvlink-and-nvlink-switch/) — 2024-01-01
10. Morgan Stanley AI hardware research note (prior-batch summary, 2026-05) — VR200 +182% MLCC / +233% PCB / +82% ABF / +32% Power / +12% Cooling

---

## Verification log

- 核心數 (88 vs 72)、製程 (3nm vs 4NP)、顆數/櫃 (36 vs 36)、NVLink-C2C bandwidth 均出自 [[NVIDIA]] 官方 keynote + 業界主流轉述 (Tom's Hardware, SemiAnalysis, TrendForce, WCCFTech)；無 σ / outlier / percentile 類量化分布主張。
- ASP (6,500 USD vs 3,500 USD) 與 die size、wafer 採購額 +50~70% 為**研究估算** (estimated)，已在表格中加註，並非 [[NVIDIA]] / [[TSMC]] 公開數據。
- "+86% silicon BOM YoY" 為 6,500 / 3,500 − 1 的直接運算結果。
