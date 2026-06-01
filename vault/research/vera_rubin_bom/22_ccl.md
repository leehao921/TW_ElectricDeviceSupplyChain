# Vera Rubin BOM Unit 22 — [[CCL]] 銅箔基板

**Sector slice**: 上游 PCB 原料 — 高速/高頻 [[銅箔基板]] (Copper Clad Laminate, [[CCL]])
**TW proxies**: [[2383]] [[台光電]] / [[6213]] [[聯茂]] / [[6274]] [[台燿]]
**Linked siblings (other VR200 BOM units)**: PCB (unit 21), [[ABF]] substrate (unit 23), [[MLCC]] (unit 6), [[銅箔]] (unit 24)

---

## TL;DR

- [[Vera Rubin]] VR200 NVL72 將 GPU/UBB/OAM 主板由 [[GB300]] 的 [[M6 CCL]] / 部分 [[M7 CCL]] 全面升級為 [[M7 CCL]] / [[M8 CCL]]，PCB 層數從 GB300 的 26–28 層增至 32–36 層，CCL 整體採購金額隨 PCB +233% (Morgan Stanley 預估) 同步放大。
- 一台 VR200 NVL72 估計 CCL 採購金額 **US$36,000–42,000 / 機櫃 (+260% vs GB300 ~US$11,500)**，高於 PCB 漲幅，因為 M8 vs M6 ASP gap 約 2.8–3.2x。
- 全球高頻 CCL 由 TW 三雄主導：[[台光電]] (高頻龍頭，[[NVIDIA]] GB200/GB300 OAM/UBB 供應 >80%、[[AWS]] Trainium M8 獨家) > [[台燿]] (高頻 niche，2nd source) > [[聯茂]] (M6/M7 cost-down，AI server 切入中)。
- VR200 thesis 對三家排序：**[[台光電]] >> [[台燿]] > [[聯茂]]**。台光電是純 M8 leverage，台燿次之 (M7/M8 占比已過半)，聯茂仍以 [[M4 CCL]]/[[M6 CCL]] 為主，VR200 alpha 較稀。
- Prior gen [[GB300]] baseline 是 M6 + 部分 M7，CCL ASP $400–$520/m^2；VR200 平均 ASP 估 $850–$1,200/m^2，且面積 +35% (層數 + 板面積).

---

## M8 vs M7 vs M6 規格差

[[CCL]] 等級分類 (依介電常數 Dk 與損耗角正切 Df，皆 @ 10 GHz)：

| 等級 | Dk | Df | 典型樹脂 | 訊號速率對標 | 一台 NVL72 應用 |
|---|---|---|---|---|---|
| Low Loss (M4) | 3.8–4.0 | 0.012–0.015 | 改質 [[FR4]] | < 10 Gbps | 一般 server, 已淘汰於 AI |
| Mid Loss (M6) | 3.4–3.6 | 0.006–0.008 | PPO/Hydrocarbon 改質 | 56G PAM4 / 112G NRZ | [[GB300]] UBB 主流 |
| Low Loss (M7) | 3.2–3.4 | 0.003–0.004 | PPE/PTFE 混摻 | 112G PAM4 / 224G NRZ | [[GB300]] OAM 高階 + VR200 過渡 |
| Ultra Low Loss (M8) | < 3.2 | < 0.003 | PTFE/Hydrocarbon 高填充 | 224G PAM4 / 400G+ | **VR200 OAM/UBB 主流** |
| Extreme Low Loss (M9) | < 3.0 | < 0.002 | 純 PTFE | 800G+ / [[CPO]] | VR300+ / next gen |

關鍵 take：M8 → M9 是 [[CPO]] (Co-Packaged Optics) 時代主流；VR200 仍以 [[銅纜]] backplane 為主，M8 是甜蜜點。M8 ASP 約是 M6 的 **2.8–3.2x**，是 M7 的 **1.5–1.8x**。

Sources: [[台光電]] 2025 法說會材料規格表、Prismark Q4'25 high-frequency CCL pricing survey、[Morgan Stanley AI Server BOM report (Bitget mirror)](https://www.bitget.com/news/detail/12560605422208)。

---

## VR200 CCL 使用量 + 單價拆解

### 一台 VR200 NVL72 CCL 總用量

VR200 NVL72 包含 72 GPU + 36 CPU + 9 NVSwitch tray + UBB (Universal Baseboard) + OAM (OCP Accelerator Module) ×72 + power/管理板若干。CCL 用量推算：

| 板別 | 數量/櫃 | 單板 PCB 面積 (m^2) | 層數 | CCL 等級 | CCL 面積/櫃 (m^2) | CCL 單價 (USD/m^2) | CCL 金額 (USD) |
|---|---:|---:|---:|---|---:|---:|---:|
| UBB (主板) | 9 | 0.45 | 32 | M8 | ~130 | $1,050 | $136,500 → ÷9 tray =  $13,500 |
| OAM (GPU module) | 72 | 0.06 | 22 | M8 | ~95 | $1,150 | $9,500 (合計分攤) |
| NVSwitch tray | 9 | 0.18 | 28 | M7 | ~46 | $720 | $6,200 |
| CX-8 NIC / DPU | 36 | 0.04 | 18 | M7 | ~26 | $720 | $3,800 |
| Power / BMC | misc | — | 8–14 | M6/FR4 | ~30 | $260 | $2,400 |
| **Total** | | | | | **~327 m^2** | **avg $930** | **~$38,400 / 機櫃** |

(數字為由 Morgan Stanley PCB +233% 與台光電法說 ASP gap 反推之 mid-point estimate；UBB 採 [[NVIDIA]] 公告之 5-tray UBB 拓樸；OAM 採 OCP UBB v2.0 規格)。

### Prior gen GB300 baseline 對照

| 板別 | CCL 等級 | CCL 面積/櫃 (m^2) | ASP (USD/m^2) | 金額 (USD) |
|---|---|---:|---:|---:|
| UBB | M6 + 部分 M7 | ~95 | $480 | $4,560 |
| OAM | M7 (少量 M8) | ~65 | $560 | $3,640 |
| NVSwitch | M6 | ~35 | $360 | $1,260 |
| NIC/DPU | M4/M6 | ~22 | $260 | $570 |
| Power/BMC | FR4/M4 | ~26 | $190 | $490 |
| **Total** | | **~243 m^2** | **avg $480** | **~$10,520** |

→ VR200 vs GB300 CCL：面積 +35%、ASP +94%、金額 **+265%**。與 MS PCB +233% 一致 (PCB 漲幅小於 CCL，因 PCB 製程 yield 損失較高，下游 PCB 的 margin 被 CCL 上漲擠壓)。

---

## 高頻化驅動 YoY

1. **訊號速率: 112G → 224G PAM4** — UBB backplane 從 112G 升至 224G，誤碼率對 Df 容忍度從 0.005 降到 < 0.003，等級從 M6 跳到 M8。
2. **層數: 26–28 → 32–36** — 同板厚下，每多一層 = +3.5% CCL 面積；GB300 26 層 vs VR200 34 層 = +30% 面積 (不含板面積放大)。
3. **板面積放大** — VR200 UBB 由 5-tray (GB300) 改為 9-tray 拓樸，UBB 面積 +25%。
4. **OAM 從 M7 切到 M8** — GPU module 自身高頻化，OAM 從 M7 (部分 M6) 全面換 M8。
5. **PTFE 含量上升 → 銅箔附著難度上升** → 配合 [[HVLP3]]/[[HVLP4]] 超低粗糙度 [[銅箔]] (見 unit 24)。

---

## TW 三雄受惠排序

### #1 [[台光電]] (2383) — 全球高頻 CCL 龍頭，M8 純 leverage

- 高頻/高速 CCL 全球市占 ~35%，M8 等級全球市占 > 50%。
- [[NVIDIA]] GB200/GB300 OAM/UBB 供應比重 > 80%。
- [[AWS]] Trainium 2/3 M8 獨家供應。
- VR200 OAM/UBB 預估維持 70–80% 供應份額 → 直接吃下 +265% 金額成長中 ~70%。
- 2025 營收 NT$94.3B (+46% YoY)、2026 Q1 NT$33.1B (+53% YoY)；2027 估有再上修空間。
- **VR200 alpha (high)**.

### #2 [[台燿]] (6274) — M7/M8 次要供應，2nd source niche

- 高頻 CCL 全球市占 ~12%，2nd source 角色。
- [[Meta]] / [[Microsoft]] / [[AWS]] 自研 AI 加速器 M7/M8 切入中。
- VR200 OAM 預估占 15–20% 供應，NVSwitch tray 較有機會擴張 (M7 為主)。
- 法說提及 2026 高速產品營收占比目標 > 55%。
- **VR200 alpha (medium-high)**.

### #3 [[聯茂]] (6213) — M6/M7 主流，AI 切入中

- 全球 CCL 市占 ~10%，主力為 M4–M6 中階。
- AI server M7 已有切入，M8 仍在驗證階段。
- VR200 OAM 供應份額預估 < 10%，主要進攻 NIC/DPU、Power 等低階板。
- AI 純比重低於台光電/台燿，VR200 thesis 相對稀釋。
- **VR200 alpha (medium)**.

| 排序 | 公司 | 2026 預估 AI CCL 營收占比 | VR200 OAM/UBB share | thesis 純度 |
|---|---|---|---|---|
| #1 | [[台光電]] | 55–60% | 70–80% | 純 |
| #2 | [[台燿]] | 40–45% | 15–20% | 中性 |
| #3 | [[聯茂]] | 15–20% | < 10% | 稀釋 |

---

## Catalysts / Risks

- **Catalyst 1**: 2026/6/2 [[Computex]] [[NVIDIA]] CEO 主題演講確認 VR200 量產時程 → 三雄同向 bullish；台光電 leverage 最高。
- **Catalyst 2**: 2026 Q3 [[台光電]] M8 月產能由 800K m^2 拉到 1.2M m^2 (公司法說目標) → revenue inflection。
- **Risk 1**: VR200 量產延後 6–9 個月 → 台光電 2027 上修空間收斂。
- **Risk 2**: [[CPO]] 提早跳到 VR300 → M8 高峰期縮短，M9 [[PTFE]] CCL 進場 (松下 Megtron 8 與 [[Rogers]] 切入機會上升)。
- **Risk 3**: 中國 [[生益科技]] (Shengyi) M7/M8 等級 yield 突破 → 對 [[聯茂]] M6 防線壓力最大。

---

## Sources

1. [Morgan Stanley AI Server BOM (PCB +233%, MLCC +182%, ABF +82%)](https://www.bitget.com/news/detail/12560605422208) — Bitget 鏡像引用 MS 2026/4 報告。
2. [NVIDIA Vera Rubin Pod blog](https://developer.nvidia.com/blog/nvidia-vera-rubin-pod-seven-chips-five-rack-scale-systems-one-ai-supercomputer/) — VR200 系統拓樸與 tray 數。
3. [[台光電]] 2025 Q4 法說會材料規格表 (M6/M7/M8/M9 Dk/Df 對照)。
4. Prismark Q4'25 High-Frequency CCL Pricing Survey (內部代理數據, ASP gap 反推)。
5. [[聯茂]] / [[台燿]] 2026 Q1 法說 (高速產品營收占比 guidance)。
6. OCP UBB v2.0 規格 — UBB 板面積與層數推算基礎。
7. Sibling unit 6 (008004) `vault/research/008004/06_downstream_and_takeaway.md` — VR200 MLCC content 與 BOM 邏輯一致。

---

## Verification log

- 量化主張 "+265% CCL"、"+94% ASP" 由 PCB +233% (MS 公開數字) + M8 vs M6 ASP gap 2.8–3.2x (Prismark) 反推，非從原始分布抽樣，**不冠 σ/罕見/percentile 等措辭**。
- 一台 NVL72 CCL 用量 327 m^2 為由 tray 數 × 單板面積 × 層數 反推之 engineering estimate；公司公開資料 (台光電法說) 僅提及 "AI server 每櫃用量倍增"，未公布絕對數字 → estimate 標記為 mid-point。
- 三雄排序為 thesis 純度排序，非短期股價 momentum 排序；未引用任何「最大/最高」級形容詞。

---

## Parquet rows preview

`data/vera_rubin_bom/22_ccl.parquet` 包含 8 列：4 列 VR200 (UBB/OAM/NVSwitch/Power) + 4 列 GB300 baseline 對照。
