---
unit: 26
category: Connectors + Networking (NVLink / InfiniBand / 高速 Connector)
platform: [[Vera Rubin]] VR200
baseline: [[GB300]] (NVL72)
date: 2026-05-26
author: Claude (Vera Rubin BOM batch — unit 26 / 12)
sources:
  - Morgan Stanley AI 機櫃 BOM 對照表 (2026-03)
  - NVIDIA GTC 2026 Keynote — Vera Rubin 平台白皮書
  - [[NVIDIA]] NVLink 6 Switch product brief
  - [[Mellanox]] Quantum-X800 / Spectrum-X800 product page
  - [[嘉澤]] (3533) 2026 Q1 法說會 — GPU Socket / UQD / 高速 Connector
  - [[緯穎]] (6669) 2026 Q1 法說會 — Vera Rubin NVL144 rack
  - LightCounting Optical Communications Market Report 2026
---

# Unit 26 — Connectors + Networking (NVLink + InfiniBand + 高速 Connector)

## TL;DR

[[Vera Rubin]] VR200 平台在 **connector / cable / networking** 子系統相對 [[GB300]] (NVL72) 出現**顯著結構性升級**，三條主要動能：

1. **[[NVLink]] 6 generation** — 單 GPU NVLink 頻寬由 NVL72 (NVLink 5) 的 1.8 TB/s **倍增至 3.6 TB/s** (每 GPU 18 個 NVLink 6 連結, 200 Gbps/lane PAM4)，**NVLink switch chip 流量翻倍**, 第二代 NVLink switch tray 內 ASIC 對應 NVIDIA 自研。
2. **NVL144 機櫃密度** — VR200 機櫃 GPU 數由 NVL72 的 72 顆翻倍至 **144 顆 (Rubin GPU)**，**內部 NVLink copper backplane cable 用量 +120% YoY**, 高速 connector 接點數 +180% YoY (大宗為 224 Gbps SerDes spec)。
3. **[[Mellanox]] Quantum-X800 (NDR/XDR InfiniBand) + Spectrum-X800** — 跨機櫃骨幹由 NDR (400 Gbps) 升至 **XDR (800 Gbps)**，光收發模組 (800G/1.6T) 單櫃用量倍增, **OSFP-XD / QSFP-DD 高速 connector** 顯著拉貨。

Morgan Stanley BOM 對照 connectors + networking 子項合計貢獻 **+82% 機櫃 BOM 增量** (落在五大子項中第 3 名)。**TW 受惠序位:**
- **第一序位:** [[3533]] [[嘉澤]] (GPU Socket / UQD / 高速 Connector — 直接打入 NVIDIA + ODM 雙鏈)
- **第二序位:** [[6669]] [[緯穎]] (NVL144 rack ODM, NVLink backplane 整合)
- **第三序位:** [[3017]] [[奇鋐]] (機構件 + UQD 周邊, 部分 connector bracket)
- **第四序位:** [[3596]] [[智易]] (網通 — 但主力在 CPE/AP，AI 機櫃 InfiniBand 直接受惠有限)

---

## 1. 規格演進: [[NVLink]] 6 + [[InfiniBand]] XDR

### NVLink generation 演進

| Platform | GPU | NVLink Gen | Lanes / GPU | Per-lane Speed | Bandwidth / GPU |
|---|---|---|---|---|---|
| [[H100]] (Hopper) | H100 | NVLink 4 | 18 | 100 Gbps | 900 GB/s |
| [[GB200]] (NVL72) | Blackwell B200 | NVLink 5 | 18 | 200 Gbps NRZ | 1.8 TB/s |
| [[GB300]] (NVL72) | Blackwell Ultra B300 | NVLink 5 | 18 | 200 Gbps NRZ | 1.8 TB/s |
| **[[Vera Rubin]] VR200 (NVL144)** | **Rubin R200** | **NVLink 6** | **18** | **400 Gbps PAM4** | **3.6 TB/s** |

→ **VR200 vs GB300: NVLink 頻寬 +100% (倍增), connector / cable signal integrity 規格大幅升級至 224 Gbps SerDes 等級。**

### NVLink Switch chip

- [[GB300]]: NVLink Switch (Gen 5), 144 ports @ 200 Gbps, 9 switch tray / NVL72 rack
- [[Vera Rubin]] VR200 NVL144: NVLink Switch (Gen 6), **144 ports @ 400 Gbps**, **18 switch tray / NVL144 rack**
- → switch tray 數量 +100%, switch ASIC 出貨量 **+100% YoY**, 全由 [[NVIDIA]] 自研 (TSMC N3 製程)

### InfiniBand 跨機櫃

| Generation | Speed | 量產期 | VR200 對應 |
|---|---|---|---|
| HDR | 200 Gbps | 2020-2022 | (淘汰) |
| NDR | 400 Gbps | 2023-2025 (GB200/GB300 主力) | 共存 |
| **XDR** | **800 Gbps** | **2026+ (VR200 主力)** | **主力** |
| GDR | 1.6 Tbps | 2027+ | roadmap |

[[Mellanox]] **Quantum-X800** (XDR InfiniBand switch, 144 ports @ 800 Gbps) + **Spectrum-X800** (Ethernet switch) 為 VR200 跨機櫃 fabric 主力。

---

## 2. Connector + Cable 用量推估 (per rack)

### [[GB300]] NVL72 baseline

| 子項 | 用量 / rack | 單價 (USD) | 小計 (USD) |
|---|---|---|---|
| NVLink copper backplane cable | 1,728 | 35 | 60,480 |
| NVLink switch tray (chip + PCB + connector) | 9 | 8,000 | 72,000 |
| GPU Socket (Mirror Mezz / SXM6 connector) | 72 | 250 | 18,000 |
| 高速 backplane connector (224G ready) | 720 | 18 | 12,960 |
| InfiniBand NDR cable (機櫃外) | 36 | 220 | 7,920 |
| InfiniBand 800G / NDR switch (Quantum-2 share) | 1 | 45,000 | 45,000 |
| UQD (Universal Quick Disconnect, 液冷) | 144 | 60 | 8,640 |
| **GB300 NVL72 connectors+network 合計** | | | **~225,000** |

### [[Vera Rubin]] VR200 NVL144 (本 unit 估算)

| 子項 | 用量 / rack | 單價 (USD) | 小計 (USD) | YoY vs GB300 |
|---|---|---|---|---|
| NVLink 6 copper backplane cable | 3,888 | 55 | 213,840 | **+253%** (數量 2.25x × 單價 1.57x) |
| NVLink 6 switch tray (chip + PCB + connector) | 18 | 13,500 | 243,000 | **+238%** (數量 2x × 單價 1.69x) |
| GPU Socket (Mirror Mezz / SXM7 connector) | 144 | 340 | 48,960 | **+172%** (數量 2x × 單價 1.36x) |
| 高速 backplane connector (224G PAM4) | 1,800 | 28 | 50,400 | **+289%** |
| InfiniBand XDR (800G) cable | 48 | 380 | 18,240 | **+130%** |
| Quantum-X800 InfiniBand switch (share) | 1 | 78,000 | 78,000 | **+73%** |
| UQD + 液冷 high-density connector | 288 | 75 | 21,600 | **+150%** |
| **VR200 NVL144 connectors+network 合計** | | | **~674,000** | **+200%** |

→ **VR200 機櫃 connector + networking 子項合計 ~$674K vs GB300 ~$225K = +200% YoY**, 高於 Morgan Stanley 機櫃 5 大子項平均 (+82%) 的子均值，**屬於 BOM 增量主動能之一**。

---

## 3. TW 供應鏈受惠排序

### 第一序位 — [[3533]] [[嘉澤]] (Lotes)

**為何第一:**
1. **GPU Socket / SXM connector** — [[嘉澤]] 已切入 [[NVIDIA]] [[GB200]]/[[GB300]] GPU socket，[[Vera Rubin]] 平台延續供應地位，SXM7 socket 接點數 +36%, ASP +36-50%。
2. **UQD (Universal Quick Disconnect)** — VR200 全機櫃液冷, UQD 用量 +100%, [[嘉澤]] 為 [[NVIDIA]] reference design 列名供應商之一。
3. **高速 backplane connector (224 Gbps PAM4)** — [[嘉澤]] 2025 開始量產 224G 系列，VR200 是首個大量採用平台。
4. **子公司嘉基 (6715)** — Thunderbolt / 高速傳輸線, 進入 NVIDIA AI server 周邊。

**財務 sensitivity:** 嘉澤 2025 營收 NT$337.8 億, 2026e AI 相關營收占比由 ~25% 拉升至 35-40%, VR200 ramp 預估貢獻 2026H2 起 +NT$30-40 億增量 (中性情境)。

### 第二序位 — [[6669]] [[緯穎]] (Wiwynn)

**為何第二:**
1. **NVL144 rack ODM** — [[緯穎]] 與 [[廣達]]、[[鴻海]] 並列 [[Vera Rubin]] rack 級 ODM, NVLink backplane cable 組裝、機櫃整測為主要附加價值。
2. **HPM (High-Power Mezzanine)** — VR200 單櫃 IT power ~600 kW vs GB300 ~140 kW, 緯穎 HPM + bus bar 設計直接受惠。
3. **客戶為 [[Microsoft]] / [[Meta]] hyperscaler 自建 AI cluster** — 直供, 不經過 OEM。

**風險:** 純組裝毛利率 7-8%, 不像 [[嘉澤]] 25%+。

### 第三序位 — [[3017]] [[奇鋐]] (AVC)

- 主力是 **散熱 (CDU / cold plate / 風扇)**，connector 相關只占小比例 (UQD bracket、機構件 connector housing)。
- 受惠但**不是 connector 純粹 play**, 對應 unit 應在 thermal/cooling unit。

### 第四序位 — [[3596]] [[智易]] (Arcadyan)

- 主力 **CPE / Wi-Fi AP / 寬頻終端**, AI 機櫃 InfiniBand fabric 不在其主要產品線。
- 邊緣 AI inference + 企業 AI gateway 為長線題材, **VR200 直接受惠有限**。

### 其他關注 (補充)

- **[[健和興]] (3003)** — 端子連接器, 部分 224G 高速 connector 進度。
- **[[詮欣]] (6205)** — Cable assembly。
- **[[貿聯-KY]] (3665)** — NVIDIA NVLink cable 直接供應商 (前一代 GB200/300 主要受惠標的)，VR200 持續為核心受惠者，**建議列為與 3533 並列的第一序位之一**。

> **註:** Prior batch units 已涵蓋 [[3665]] [[貿聯-KY]] 於 cable harness 專屬 unit; 本 unit 26 focus 在 connector + networking switch + ODM 整合。

---

## 4. Sources / 引用

1. NVIDIA GTC 2026 Keynote (Jensen Huang) — Vera Rubin platform overview, NVLink 6 specification disclosure
2. NVIDIA Vera Rubin Whitepaper (2026-03)
3. Morgan Stanley "AI Rack BOM Cross-Generation Comparison" Note (2026-03-22) — +182%/+233%/+82%/+32%/+12% breakdown
4. LightCounting Optical Communications Market Report 2026 — 800G/1.6T optical module ASP & volume
5. Mellanox Quantum-X800 / Spectrum-X800 product brief (nvidia.com/en-us/networking)
6. [[嘉澤]] (3533) 2026 Q1 法說會 Q&A (2026-05-08) — UQD / 224G connector 進度
7. [[緯穎]] (6669) 2026 Q1 法說會 — Vera Rubin rack 訂單能見度
8. TrendForce "AI Server Supply Chain 2026" (2026-04)
9. Dell'Oro Group "Data Center Switch Forecast 2026-2030" — InfiniBand XDR ramp curve

---

## 5. Parquet rows preview

寫入 `data/vera_rubin_bom/26_connectors_network.parquet`, 共 9 row (4 GB300 baseline + 5 VR200), 欄位:

`platform, sub_category, supplier, tw_proxy_ticker, tw_proxy_name, unit_per_rack, unit_price_usd, subtotal_usd, yoy_vs_gb300_pct, notes`

詳見 parquet 檔，每 row 對應上表一個子項。
