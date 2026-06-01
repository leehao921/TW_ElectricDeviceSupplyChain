---
type: concept
status: monitoring
last_updated: 2026-05-20
related: [../../themes/邊緣運算.md, ../../themes/NVIDIA.md, ../../themes/UAV.md, ../../themes/AI_伺服器.md]
tags: [edge_ai, jetson, nano, inference, IPC, hailo, rockchip, mediatek_genio]
---

# Edge AI Inference (Nano-tier focus)

邊緣推論硬體三層算力中 **Tier 3 Nano 級 ($50-499, 5-67 TOPS)** 的全球競品格局與台股映射。Tier 1 (Thor) 與 Tier 2 (Orin NX) 視 [[../../themes/NVIDIA.md]] / [[../../themes/AI_伺服器.md]]。

完整供應鏈與全球競品分析: **[[../../themes/邊緣運算.md]]** (254 行, 109 wikilinks)。

## Catalyst (本概念建立的觸發點)

2026-05-20 **NVIDIA Q1 FY27** 首次拆出 **ACIE $37B** 營收 (AI Clouds + Industrial + Enterprise) — 與 hyperscaler $38B 幾乎平分。代表 Edge / Industrial 推論 narrative 從「準備期」進入「可量化」階段。

## Nano 級全球競品七大陣營

| 陣營 | 代表 | 算力 | 製程 | 對 TSMC 受惠 |
|---|---|---:|---|:---:|
| NVIDIA Jetson | [[Jetson Orin Nano Super]] 67 TOPS | 67 | Samsung 8nm | ❌ |
| Hailo (IL) | Hailo-8 / 15 | 26 / vision SoC | TSMC 16nm | ✅ |
| AMD Kria | KV260 FPGA + DPU | 1.4 | TSMC 16nm | ✅ |
| Rockchip (CN) | RK3588 / RK3688 | 6 | Samsung 8nm | ❌ |
| Qualcomm | QCS6490 Dragonwing | 12 | TSMC 7nm | ✅ |
| MediaTek (TW) | Genio 700/1200 | 4-4.8 | TSMC 7nm | ✅✅ |
| Ambarella | CV7 / CV72S | 5-30 | Samsung 5nm | ❌ |

**Edge AI Nano 級全球市占 NVIDIA <25%** — 與 Tier 1 寡占截然不同,Rockchip + Hailo + Qualcomm + MediaTek 共同蠶食。

## 台股 alpha 四條路徑

| 路徑 | 邏輯 | 代表 ticker |
|---|---|---|
| **L1 Jetson 純度** | NVIDIA 生態整機 / SOM | **6579 [[../../Pilot_Reports/Computer Hardware/6579_研揚]]** / 6166 凌華 / 6680 鑫創 / 6922 宸曜 |
| **L2 陣營中立 carrier board** | 不分陣營吃 HDI + connector | 3044 健鼎 / 2383 [[../../Pilot_Reports/Electronic Components/2383_台光電]] / 3533 嘉澤 |
| **L3 自家 SoC 挑戰 NVIDIA** | Genio 4-4.8 TOPS 直接打 Orin Nano 入門市場 | **2454 [[../../Pilot_Reports/Semiconductors/2454_聯發科]]** / 2379 瑞昱 |
| **L4 終端品牌商** | AI CAM / 掃地機 / POS 出貨爆發 | 3669 圓展 / 3289 松騰 / 6206 飛捷 |

## Why this matters for TXF / portfolio

- **與 hyperscaler capex 風險脫鉤** — Nano 級需求分散於工業/零售/教育/家電,不像 Tier 1 Server 集中於 Meta/MS/OpenAI 四強
- **季節性低** — IPC + 工業相機 出貨曲線比 Server ODM 平滑,適合做為 AI 配置中的 **defensive Edge AI** 部位
- **股性彈性** — 6579 研揚 / 6166 凌華 流動性中等,beta vs TWII ~1.2,適合做小部位 satellite (本帳戶當前無持倉)

## 觀察清單 (next catalysts)

1. NVIDIA Q2 FY27 (2026-08) — ACIE 是否續強
2. 聯發科 Q3 法說 — Genio 出貨指引
3. 研華 / 凌華 / 研揚 Q2 法說 (7-8 月) — 訂單能見度
4. 中國 RK3688 (預期 2026 Q4 發表) — 是否威脅外溢全球

## Open questions (待回答)

- 6579 研揚 2026 Edge AI 營收占比實際數字 (年報 + 法說 verify)
- Hailo 在台廠 IPC 整合滲透率 (研華 / 凌華 已導入哪些 SKU?)
- MTK Genio 1200 真實出貨量級 (vs Jetson Orin Nano 同價位帶)

---

**Source:** WebSearch 2026-05-20 (NVDA Q1 FY27 公布同日) + themes/邊緣運算.md
**No position held** as of 2026-05-20
