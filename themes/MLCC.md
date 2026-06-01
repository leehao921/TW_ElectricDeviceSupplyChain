# MLCC 積層陶瓷電容供應鏈

> [[MLCC]] (Multilayer Ceramic Capacitor) 全球與台灣供應鏈。被動元件三大類中體積最大、技術門檻最高的子類別,從 commodity 0402 一路到 leading-edge **008004** (0.25 × 0.125 mm) 共 8 個世代規格。**008004 全球僅 Big-4 ([[Murata]] / [[Samsung Electro-Mechanics]] / [[Taiyo Yuden]] / [[TDK]]) 量產,台廠零直接 exposure**;但 commodity 漲價、AI 伺服器高壓/高容 MLCC、AI 電源 Mega Cap 三條子題材都有受惠標的。

**涵蓋公司數:** 17 (TW listed)

**相關主題:** [[AI 伺服器]] | [[電動車]] | [[Vera Rubin]] | [[GB300]] | [[CoWoS]] | [[HBM]] | [[5G]] | [[ABF 載板]]

---

## 規格世代與命名陷阱

| Imperial | Metric (近似) | 尺寸 | 量產商業狀態 |
|---|---|---|---|
| 0402 | 1005 | 1.0 × 0.5 mm | mainstream commodity,多家可做 |
| 0201 | 0603 | 0.6 × 0.3 mm | high-volume,含 [[國巨]]、[[華新科]] |
| 01005 | 0402 | 0.4 × 0.2 mm | high-end,[[國巨]] 已量產 |
| **008004** | **0201** | **0.25 × 0.125 mm** | **leading edge — 僅 Big-4 量產** |
| 006003 | 自有命名 | 0.16 × 0.08 mm | [[Murata]] 2024/09 唯一發表 (下世代) |

> **命名陷阱**: imperial "008004" = metric "0201" = 0.25×0.125 mm (leading edge);imperial "0201" = metric "0603" = 0.6×0.3 mm (commodity)。**TW 媒體常把兩者混淆**。任何提到「0201」的新聞要先驗證 imperial / metric。

---

## 上游 (5)

### 介電瓷粉 / 鈦酸鋇 (BaTiO₃)

008004 物理約束:介電層厚度 < 1 μm,每層至少含 4-5 顆晶粒 → [[鈦酸鋇]] 粒徑須 ≤ 100 nm。**日商寡占** ([[Sakai 化學]] 18-20% + [[Nippon Chemical]] 15% + [[Fuji Titanium]] + [[Toho Titanium]] + [[Ferro]] 前五大占 ~48%)。

- **6173 [[信昌電]]** (Semiconductor Equipment & Materials) — 台灣**唯一**自製 [[BaTiO₃]] 粉體;目標從 200 nm → 100 nm,2027 Q3 六甲新廠 (11.6 億 capex) 投產,挑戰日系。短期粉體用於 1206+ 大尺寸與高壓 MLCC,**不切 008004**。
- **3236 [[千如]]** (Electronic Components) — 公司核心為電感/變壓器/磁芯,所謂「陶瓷」為散熱用孔洞化陶瓷,與 [[MLCC]] 介電粉體無交集 → **不應列為 MLCC 標的**。

### 內 / 外電極漿料 (Ni paste / Cu / Ag paste)

- **4760 [[勤凱]]** (Semiconductor Equipment & Materials) — 銀漿 + 銅漿,2020 Q4 打進首家韓系 MLCC,2021-2024 送樣日系認證,**2026 正式銅漿進軍日本被動元件市場** (Q1 EPS 2.55 創單季新高);理論上是 008004 端電極最強 catch-up 候選,但 008004 BOM 預計 2027+ 才可能切入。

### 設備與襯托基板 — 日商主導

[[Murata]] 大量自製設備 (流延機、堆疊機、燒結爐)。台灣**無上市設備 player**。

---

## 中游 (4) — MLCC 製造

### Commodity + 高壓高容 ($10B+ 市值雙雄)

- **2327 [[國巨]]** (Electronic Components) — 全球 [[MLCC]] 市占約 13-15% (第 5),併 [[Kemet]] 後鉭電容市占 50%+。最小 footprint **01005 imperial**,**無 008004 量產或公開 R&D 證據**。2026 漲價週期 + AI 伺服器高壓 MLCC 主受惠者,但**與 008004 微小化主題無關**。
- **2492 [[華新科]]** (Electronic Components) — 全球 [[MLCC]] 市占 ~14% (第 4)。最小 footprint **0201 imperial** (比 2327 還落後一個檔位);AI 伺服器電源高壓 MLCC + 車規認證為主軸。2025 net income −23% YoY,股價 +173% 純題材推升。**對 008004 exposure = 0**。

### 利基 — 高壓 / 高容 (與 008004 物理反方向)

- **3026 [[禾伸堂]]** (Electronic Components) — Holy Stone。**100V – 10,000V 高壓 + 大容值利基**,瞄準 [[NVIDIA]] [[Vera Rubin]] AI 電源、HVDC、車用電子;2026/2027 各擴產 30%。與微小化 008004 **物理反方向**,exposure = 0。副業 [[碳化矽]] / [[AMB 基板]]。
- **6173 [[信昌電]]** (Semiconductor Equipment & Materials) — 華新科集團子公司,**台灣唯一垂直整合**「粉體→製程→元件」一條龍。Q1 2026 GM 衝上 28.4%,特殊高壓品交期 16 週,[[NVIDIA]] [[GB200]] PSU Mega Cap 單顆 ASP 7-9 倍標準品。**也是大尺寸/高壓主場,不是 008004**。

---

## 下游 (4) — 應用整合

### AI 伺服器 (主場)

- **[[NVIDIA]] [[GB300]] NVL72** — 一台機櫃 ~45 萬顆 MLCC,單櫃 MLCC content ~$1,500
- **[[NVIDIA]] [[Vera Rubin]] VR200** (2026 H2 量產) — 單櫃 MLCC content **$4,300 (+182% vs GB300)**,引入 6× rack-level 儲能 + closed-loop 電容狀態監控

### 高階智慧手機 (Murata 直供主導)

- **[[Apple]] iPhone 17 Pro / Pro Max** — 800-1000 顆 MLCC/支,估 160-250 顆是 008004 ([[Murata]] 直供, [[Apple]] 主供應商)
- **[[Samsung]] Galaxy S26 Ultra** — [[SEMCO]] 自家垂直整合
- **[[Google]] Pixel 11** — [[Murata]] / [[Taiyo Yuden]] 雙源

### TW 終端組裝 (被動接單,不創造 alpha)

- **2317 [[鴻海]]** — Apple iPhone 主力 + NVIDIA GB300/Rubin
- **6669 [[緯穎]]** — Meta / MS / AWS 自主機櫃 (示警 AI 缺貨延至 2028)
- **2382 [[廣達]]** — NVIDIA 機櫃 ODM

### 高階智慧手機 / 穿戴用 PoP / 5G mmWave 模組

[[Apple]] iPhone PoP (Package-on-Package) RF front-end 是 008004 第一個量產應用場景;穿戴 [[AirPods]] / [[Apple Watch]] 也在升級。TW 廠商無直接設計切入。

---

## 代理通路 (2) — 008004 真正的台灣直接受惠

> **核心 insight**: 既然 TW 中游不做 008004,實際把 008004 賣給 [[Apple]] ODM + [[NVIDIA]] 機櫃 ODM 的「實際收款方」就是兩家獨家/官方代理。

- **3090 [[日電貿]]** (Electronic Components) — [[Samsung Electro-Mechanics]] 官方台灣代理 (估 55-65% SEMCO TW revenue) + [[Nippon Chemi-con]] + [[Panasonic]] + [[Kyocera]] 代理。2026 1-4 月累積營收 63.36 億 (+21% YoY),處置股 5/27-6/9。**P/E TTM 16.86 是 MLCC 族群最便宜**,catalyst window 為 SEMCO 008004 2026 H2 量產。
- **8043 [[蜜望實]]** (Electronic Components) — [[Taiyo Yuden]] 獨家台灣代理 30+ 年。2025 GM **從 2.78% → 4.47% → 5.62%** 兩年雙倍,Q4 2025 GM 8.71%。AI 營收占比 22% → 40%+,2026 H1 估 50%+。揭露 **GB300 一台 ~45 萬顆 MLCC**;估算 008004 占顆數 5.6% 但占單櫃 MLCC ASP **45%** (NT$112.5K/NT$248.75K)。P/E 43.59 偏貴,但 P/S 1.07 + GB300 ramp 仍有空間。Q3 2025 OCF −405.82M 為備貨警訊。

---

## 相關公司 (2)

- **8163 [[達方]]** (Electronic Components) — 鍵盤 + 自用 MLCC + 電感 + EMI 元件,被動元件副業
- **5345 [[馥鴻]]** (Electronic Components) — 已轉型 real estate,dilute,僅作對照

---

## 全球競品結構 (Big-4 為主)

| 廠商 | 整體 MLCC 市占 | AI server 高階 MLCC | 008004 status | 2026 漲價 |
|---|---|---|---|---|
| **[[Murata]]** | >40% | (Murata + SEMCO 合計 >80%) | 2014 首發、2019 量產 Apple/Huawei 5G;**2024/09 推出 006003 next-gen** | **+15-35%** (4/1) |
| **[[Samsung Electro-Mechanics]]** | ~18% | | Ultra-Compact 008004 High-Q 商品化;600+ 層、<0.5μm 介電 | +5-10% (4 月評估) |
| **[[Taiyo Yuden]]** | ~13% | minor | 產品線內已列 008004 | **+6-13%** (5 月) |
| **[[TDK]]** | ~10% | minor | 公開資訊少 | 未公告 |
| 2327 [[國巨]] (TW) | ~13% | minor | 最小 01005 imperial | 跟進 |
| 中國廠 (風華/三環) | ~10% | minimal | 標準品為主 | n/a |

---

## 投資 takeaway

### 受惠強度排序 (008004 主題)

```
Tier 1 (直接 5/5): 8043 蜜望實  >  3090 日電貿  
Tier 2 (間接 3/5): 6173 信昌電  >  4760 勤凱
Tier 3 (零暴露,但被市場 lump): 2327 國巨 ≈ 2492 華新科 ≈ 3026 禾伸堂
```

### 三個子題材對照

| 主題 | 邏輯 | 受惠標的 |
|---|---|---|
| **008004 微小化** | Murata 獨占 → 缺貨 → ASP↑ → 代理槓桿 | **8043, 3090** |
| **MLCC commodity 漲價週期** | 高階產能被 AI 抽走 → 消費級漲價 | 2327, 2492 |
| **AI 高壓 / Mega Cap MLCC** | Vera Rubin 機櫃 PSU 大尺寸高壓品 | 2327, 2492, **6173, 3026** |

---

## 風險

- **006003 next-gen ASP cliff**: Murata 2024/09 CEATEC 已發表 006003 (0.16 × 0.08 mm, 體積比 008004 小 75%);量產時程估 2026 末 – 2027 H1 → 008004 ASP 跌價、代理 inventory loss → **8043 / 3090 估值 derate window**
- **NVIDIA ramp 延遲風險**: 8043 Q3 2025 OCF −405.82M 為了 GB300 BOM 備貨,若機櫃出貨延後即首當其衝
- **市場誤判**: 把 2327/2492 當「008004 受惠」是錯誤連結 — 真實機制是 Big-4 產能搬去做高階,擠出 commodity 留給台廠

---

## Sources

- [Murata 008004 launch — Microfarads](https://www.microfarads.com/times-articles/67-murata-008004-mlcc)
- [Murata 006003 next-gen — BusinessWire 2024/09/18](https://www.businesswire.com/news/home/20240918232327/en/Murata-Unveils-the-Worlds-Smallest-Multilayer-Ceramic-Capacitor-with-the-First-006003-inch-Size-0.16mm0.08mm-Device)
- [Samsung Electro-Mechanics CEO Ultra-Compact 008004 600+ layers](https://en.sedaily.com/finance/2026/04/23/samsung-electro-mechanics-ceo-worlds-only-ai-core-component)
- [TrendForce 2026/03/17 — Murata April 1 +15-35%](https://www.trendforce.com/news/2026/03/17/news-mlcc-giant-murata-reportedly-confirms-april-1-price-hike-on-key-components/)
- [Digitimes 2026/04/17 — Taiyo Yuden +6-13%](https://www.digitimes.com/news/a20260417PD209/taiyo-yuden-mlcc-murata-electronic-components-price.html)
- [Digitimes 2026/04/29 — SEMCO +5-10%](https://www.digitimes.com/news/a20260429VL222/semco-price-mlcc-demand-murata.html)
- [Bitget News — Vera Rubin VR200 MLCC $4,300 (+182% vs GB300)](https://www.bitget.com/news/detail/12560605422208)
- [Vocus — 被動元件 2027-2028 中長期評估 (008004 Murata 獨占,台廠 1-2 世代落後)](https://vocus.cc/article/6a0b27bafd897800010b06e7)
- [TechNews — 信昌電 NP0 100nm 目標](https://cdnfinance.technews.tw/2026/05/15/high-end-np0/)
- [TechNews — 勤凱 Q1 2026 EPS 2.55 創高](https://finance.technews.tw/2026/05/25/copper-paste-for-hauling-goods/)
- [Sinotrade — 日電貿 4月營收 +28.1% 通路角色](https://www.sinotrade.com.tw/richclub/hotstock/%E6%97%A5%E9%9B%BB%E8%B2%BF-3090--AI%E4%BC%BA%E6%9C%8D%E5%99%A8%E9%9B%BB%E6%BA%90%E5%8D%87%E7%B4%9A%E6%8B%89%E7%88%86MLCC%E4%BA%A4%E6%9C%9F-%E9%80%9A%E8%B7%AF%E5%95%86%E8%A7%92%E8%89%B2%E6%AD%A3%E8%A2%AB%E9%87%8D%E6%96%B0%E5%AE%9A%E7%BE%A9-6a0d04b211fc24195f3ae7a3)
- [EBC — 蜜望實 AI 營收 40%](https://fnc.ebc.net.tw/fncnews/stock/203276)
- [Chemical Research Insight — Sakai 化學 25-30% / Nippon Chemical 15% nano-grade BaTiO₃](https://chemicalresearchinsight.com/2025/06/10/top-10-companies-in-the-global-mlcc-dielectric-materials-market-2025-innovation-leaders-driving-capacitor-technologies/)

**Detailed unit research:** `vault/research/008004/01-06_*.md` (6 slices)
