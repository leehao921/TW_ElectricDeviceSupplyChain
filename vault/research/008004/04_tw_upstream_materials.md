---
type: research
status: draft
last_updated: 2026-05-26
source_unit: 4
tags: [MLCC, 008004, 鈦酸鋇, BaTiO3, 上游材料, paste, 信昌電, 勤凱]
---

# Unit 4: 台灣上游材料 — 鈦酸鋇 nano 粉 + 鎳/銀/銅 漿料

## TL;DR

- **[[008004]] (0.25 mm × 0.125 mm) 對上游材料的核心約束是粒徑** — 介電層 < 1 μm，要求 [[鈦酸鋇]] 粒徑 ≤ 100 nm、內電極鎳粉 50-80 nm、外電極銅/銀粉同等級。台灣材料端目前在這個粒徑等級「沒有量產出貨給 Big-4 [[008004]] BOM」的明確證據。
- **鈦酸鋇 nano-grade 仍由日商寡占** — [[Sakai 化學]] (堺化學) 約 18-20% 全球市占、[[Nippon Chemical]] (日本化學工業)、[[Fuji Titanium]] (富士鈦工業)、[[Toho Titanium]] (東邦鈦工業) 四家供應 [[Murata]]、[[TDK]]、[[Taiyo Yuden]] 的高階 ≤ 100 nm 粉體，前五大合計約 48% 全球供給。[[Ferro]] 仍在前十大但已非 nano-grade 主流。
- **6173 [[信昌電]] 正在追趕但仍落後** — 自製介電瓷粉從傳統 600-800 nm 朝 200 nm 推進，2027 年 Q3 六甲新廠投產後目標「挑戰日系 100 nm 等級」。目前實際出貨等級對應大尺寸/高壓 [[MLCC]] (1206 以上)，而非 [[008004]]。
- **3236 [[千如]] 不是鈦酸鋇 player** — 公司核心為電感、變壓器、磁芯，陶瓷材料是散熱片用孔洞化陶瓷與磁性 ferrite，與 [[008004]] 介電粉體無交集。
- **4760 [[勤凱]] 是 [[008004]] 端電極漿料的台廠最強候選** — 銀漿/銅漿主供 [[電感]]、[[電阻]]、[[MLCC]] 客戶；2020 年 Q4 打進首家韓系 MLCC、2021 年認證第二家、已送樣日系龍頭並通過初步認證；2026 年明確規劃「銅漿正式進軍日本被動元件市場」。但目前公開資訊未驗證已切入 [[008004]] BOM (Big-4 對端電極粒徑均勻度要求極端，是潛在 catch-up 機會點)。
- **保護塗層 [[聚醯亞胺]]** — TW 上市公司中 [[達邁]] (3645)、[[長興]] (1717) 有 PI 樹脂能力，但 [[008004]] 表面塗層用量極小、未見明確切入點。
- **投資結論:** 上游材料端的 [[008004]] 受惠純度低,排序為 4760 [[勤凱]] (端電極漿料,catch-up 中) > 6173 [[信昌電]] (鈦酸鋇 catch-up,但短期供大尺寸/高壓而非 [[008004]]) >> 3236 [[千如]] (基本無關)。日商 [[Sakai 化學]]、[[Shoei Chemical]] (昭榮化學) 仍是真正受惠者。

---

## 為何 008004 對材料端要求極端

[[Murata]] 在 2014 年首次量產 [[008004]] (尺寸 0.25 mm × 0.125 mm × 0.125 mm,10 nF),2020 年量產 0.1 μF 版本 (GRM011R60J104M),挂裝面積較 01005 縮小約 50%、體積縮小約 80%。[[Kyocera]]、[[Taiyo Yuden]] 隨後跟進。

物理約束推導 (參考 [Vacancy engineering BaTiO3 文獻](https://www.sciencedirect.com/science/article/abs/pii/S0032591024005989) 與 [BaTiO3 size dependence](https://www.sciencedirect.com/science/article/abs/pii/S0169433224018245)):

1. **介電層厚度 < 1 μm** (在 [[008004]] 此尺寸,介電層往往降至 0.5-0.7 μm 區間)
2. **每層至少需 4-5 顆晶粒** 才能避免短路 → 粒徑必須 < 150 nm,理想 ≤ 100 nm
3. **內電極 (Ni) 厚度同步降至 < 0.5 μm** → 鎳粉粒徑 50-80 nm、球形度高、分散均勻
4. **端電極 (Cu/Ag) 銜接面積極小** → 銅/銀粉粒徑均勻度要求極高 (避免端電極剝離)

任何粒徑 > 200 nm 的粉體都做不出 [[008004]] — 這是物理硬約束,不是商業偏好。

Sources:
- [Murata 008004 launch — Microfarads](https://www.microfarads.com/times-articles/67-murata-008004-mlcc)
- [Murata 0402 47µF mass production 2025](https://www.murata.com/en-us/news/capacitor/ceramiccapacitor/2025/0710)
- [Kyocera 008004 development](https://passive-components.eu/kyocera-develops-some-of-worlds-smallest-008004-multilayer-ceramic-capacitors-for-mobile-devices/)

---

## 鈦酸鋇 (BaTiO₃) nano-grade 粉體

### 日商寡占現況

全球 [[鈦酸鋇]] for MLCC 市場 2025 年規模約 5 億美元,2034 年預估 12 億美元 (CAGR ~10%)。前五大供應商占約 48% 全球供給,且絕大多數 nano-grade (≤ 200 nm) 集中於日商:

| 供應商 | 市占估計 | 強項粒徑 | [[008004]] 暴露 |
|---|---|---|---|
| [[Sakai 化學]] (堺化學工業) | 18-20% | 100-200 nm 主流,有 50-80 nm 樣品 | 主要供 [[Murata]]、[[Taiyo Yuden]] |
| [[Nippon Chemical]] (日本化學工業) | ~10% | 100-200 nm | 供 [[TDK]]、[[Murata]] |
| [[Fuji Titanium]] (富士鈦工業) | ~8% | 150-300 nm | 供 [[Taiyo Yuden]]、中階 MLCC |
| [[Toho Titanium]] (東邦鈦工業) | ~6% | 200-400 nm | 中階 MLCC、垂直整合矽鋼 |
| [[Ferro]] (美商,現屬 [[Prince International]]) | ~5% | 200-500 nm,nano 不是強項 | 中階/車用 MLCC |
| [[Shandong Sinocera]] (山東國瓷) | ~5-8% | 200-500 nm,逐步推進 < 200 nm | 中國 MLCC 廠 (風華、三環),非 Big-4 主流 |

日商寡占的根因:**水熱法 (hydrothermal) + 草酸鹽法 (oxalate) 製程** 是 nano-grade BaTiO₃ 的關鍵 know-how,日商累積數十年配方且專利保護綿密;固相法 (1500°C × 24h 燒結) 做不出 ≤ 100 nm 粉體,中國/台灣多數玩家仍倚賴固相法或改良固相法。

Sources:
- [Barium Titanate Powder For MLCC Market — Verified Market Reports](https://www.verifiedmarketreports.com/product/barium-titanate-powder-for-mlcc-market/)
- [Electronic Grade BaTiO3 Powder Market](https://www.globalgrowthinsights.com/market-reports/electronic-grade-barium-titanate-batio3-powder-market-120150)
- [Vacancy engineering BaTiO3 solid-state — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0032591024005989)

### 6173 信昌電 自製粉體等級評估

驗證 6173 = [[信昌電]] (信昌電子陶瓷股份有限公司,華新科集團子公司)。本檔在台股研究中是「台灣唯一具備從上游介電陶瓷粉末、中游製程設備到下游被動元件 MLCC 垂直整合」的標的,定位獨特。

**2026 年 5 月法說會與擴產公告要點** (來自 [TechNews 報導](https://cdnfinance.technews.tw/2026/05/15/high-end-np0/) 與 [優分析法說會整理](https://uanalyze.com.tw/articles/3605251570)):

1. **粒徑技術路線:** 介電瓷粉從傳統 **600-800 nm** 朝 **200 nm 以下** 推進,新廠目標「**挑戰日系大廠水準的 100 nm 極細粉末**」。
2. **新廠投產時間:** 2025 年 7 月董事會通過砸 11.6 億元於台南六甲擴建瓷粉新廠,**預計 2027 年 Q3 量產**,屆時整體產能較 2026 提升約 50%。
3. **產品定位:** 公司明確自承「**Japanese manufacturers' dominance in miniaturized applications (0201 specifications) for mobile markets, with 信昌電 positioning itself in larger-format components (1206+)**」 — 等於坦承短期內 [[008004]] 不是主戰場。
4. **核心應用是高階 NP0:** [[AI 伺服器]] PSU 內 LLC resonant circuit 用 NP0 (C0G) 電容取代薄膜電容,一顆薄膜可被 10-20 顆 NP0 取代;且 [[NVIDIA]] [[Rubin]] 架構 PSU 功率需求是前代的 3-4 倍,推升高壓高功率 MLCC 用量。
5. **2025 全年財務:** 營收 4,055 百萬,Gross Margin 24.27%,Operating Margin 16.79% (Q1 2026 法說會提及 Gross Margin 衝上 28.4%,特殊品交期拉長至 16 週)。

**[[008004]] 受惠強度評估: 弱。** 信昌電的高階粉體 catch-up 還在 200 nm 區間,2027 年才挑戰 100 nm。即使 2027 年達標,Big-4 ([[Murata]]、[[Samsung Electro-Mechanics]]、[[Taiyo Yuden]]、[[TDK]]) 的 [[008004]] BOM 換料認證週期通常 18-24 個月,因此 **2029 年前不太可能切入**。但中長期是真實的「日系替代」題材。

Sources:
- [信昌電 NP0 報導 — TechNews](https://cdnfinance.technews.tw/2026/05/15/high-end-np0/)
- [信昌電法說會 Q1 2026 — 優分析](https://uanalyze.com.tw/articles/3605251570)
- [信昌電 11.6 億擴產 — 壹蘋新聞](https://news.nextapple.com/finance/20260515/DF16832A7593137D8E64886E4D16889C)
- [信昌電 2026-05-21 法說會 — 散戶鬥嘴鼓](https://poorstock.com/earningcall/6173)

### 3236 千如 切入點

驗證 3236 = [[千如]] (千如電機,英文名 ABC Taiwan Electronics)。

**核心業務:** 電感 (SMD 功率電感)、變壓器 (高頻/脈衝)、濾波器 (EMI/共模)、精密金屬沖壓零件、孔洞化結構陶瓷散熱片、LED 照明。客戶包含 [[Bosch]]、[[Continental]]、[[Denso]] (車用 Tier 1) 與 [[廣達]]、[[緯創]] ([[AI 伺服器]])。

**陶瓷材料的真實面貌:** 千如的「陶瓷」是
- **孔洞化結構陶瓷散熱片** (用於 LED 照明散熱) — 與 [[MLCC]] 介電粉體無關
- **鐵氧體磁芯 (ferrite)** — 軟磁材料,非鈦酸鋇

**搜尋驗證:** 多次以「千如 + 鈦酸鋇 / BaTiO3 / 陶瓷粉 / MLCC 介電」交叉檢索均無相關公開資料,公司財報與法說會也未提及鈦酸鋇粉體業務。

**[[008004]] 受惠強度: 零。** 應該從本研究範圍剔除 (或僅作為「易被誤認」的對照)。

Sources:
- [千如 3236 公司簡介 — 鉅亨網](https://www.cnyes.com/twstock/intro/3236.htm)
- [千如做什麼 — nStock](https://www.nstock.tw/%E5%8D%83%E5%A6%82%E5%81%9A%E4%BB%80%E9%BA%BC.html)

---

## 內電極 + 端電極漿料

### 4760 勤凱 silver/copper paste

驗證 4760 = [[勤凱]] (勤凱科技,Conduant Technology)。

**業務結構:** 主力為導電漿料 — 銀漿 (Ag)、銀鈀漿 (Ag-Pd)、銅漿 (Cu)、Cu + Metal Epoxy 端電極漿。應用於 [[MLCC]] 端電極、[[電阻]] 電極、[[電感]] 導電層。

**客戶切入歷史 (公開揭露):**
- **2020 Q4:** 打進首家韓系 [[MLCC]] 廠認證 (合理推測為 [[Samsung Electro-Mechanics]] 或 Samhwa Capacitor)
- **2021:** 第二家韓系被動元件廠認證通過
- **2021-2024:** 送樣日系 [[MLCC]] 龍頭 (合理推測為 [[Murata]] 或 [[Taiyo Yuden]]),通過初步認證階段
- **2026 規劃:** 公司明確宣示「**銀漿正式切入 IC 封裝、銅漿進軍日本被動元件市場**」 — 等同坦承 2026 才是日系突破年

**2026 Q1 業績與業務動能:**
- EPS NT$ 2.55 (YoY +32.78%,單季歷史高)
- Gross Margin 19.74%
- 銅漿月增 20%+ 拉貨力道、客戶出現「**罕見長單鎖料**」現象 (過去鮮見)
- 銅漿出貨量今年估成長 30%
- 1 月營收首破 2 億 (2.09 億)
- 全年營收估雙位數成長

**[[008004]] 受惠強度: 中等偏弱,但是台廠最強候選。** 勤凱目前公開資料未驗證已切入 [[008004]] BOM,但有三個正向因子:
1. 銅漿 + Cu + Metal Epoxy 是 [[008004]] 端電極的關鍵材料
2. 2026 才剛突破日系認證,意味之前都是供 [[國巨]]、[[華新科]]、[[禾伸堂]] 等台廠 (這些公司沒有 [[008004]] 產線)
3. AI 伺服器高功率 MLCC + 電動車 MLCC 漲價潮拉動全段位毛利率,即使切不進 [[008004]] 也賺得到 0402/0201 升級的錢

**反向風險:** Big-4 [[008004]] 內外電極漿料的真正 incumbent 是 [[Shoei Chemical]] (昭榮化學) 與 [[Daiken Chemical]] (大研化學),勤凱要切進去需要 18-24 個月認證 + 客製化粒徑控制,2026 之內可能性低。

Sources:
- [勤凱 2026 Q1 EPS 2.55 — TechNews](https://finance.technews.tw/2026/05/25/copper-paste-for-hauling-goods/)
- [勤凱客戶長單 — 鉅亨網](https://news.cnyes.com/news/id/6469971)
- [勤凱打進日韓 — 理財周刊](https://www.moneyweekly.com.tw/ArticleData/Info/%E7%90%86%E8%B2%A1%E5%91%A8%E5%88%8A/72657)
- [勤凱 1 月營收破 2 億 — 經濟日報](https://money.udn.com/money/story/5612/9304026)
- [勤凱法說會 2025/11 — vocus](https://vocus.cc/article/691ffe60fd89780001aa25b6)

### 鎳漿料 (日商主導)

[[008004]] 內電極鎳漿是日系 MLCC 廠最嚴密保護的 BOM 環節。市場結構:

| 鎳漿供應商 | 角色 | 粒徑等級 |
|---|---|---|
| [[Shoei Chemical]] (昭榮化學) | 全球領先,化學還原法,與 [[Murata]] 緊密合作 (toll refining) | 50-200 nm,有 < 80 nm 細粉 |
| [[Daiken Chemical]] (大研化學) | 第二大,供 [[TDK]]、[[Taiyo Yuden]] | 100-300 nm |
| [[JFE Mineral]] (JFE 鑛業) | 鎳粉原料 + 漿料,垂直整合 | 80-500 nm |
| [[Toho Titanium]] (東邦鈦工業) | 鈦原料兼鎳粉 | 200-500 nm |
| [[Sumitomo Metal Mining]] (住友金屬鑛山) | 大粒徑為主,nano 級較少 | 300-1000 nm |
| [[Murata]] | 部分自製內製,Vertically integrated | 不外售 |
| [[Shandong Sinocera]] / [[Fenghua]] / [[Zhaorong]] | 中國本土,中低階為主 | 200-500 nm |

鎳粉的關鍵物性是「球形度 + 粒徑分布窄 (D90/D10 < 2)」,因為 [[008004]] 內電極 < 0.5 μm 厚,任何 outlier 大顆粒都會穿透相鄰介電層導致短路。台灣**目前無一家上市公司具備量產 < 100 nm 鎳粉/鎳漿能力**。

**台灣在鎳漿端 [[008004]] 受惠強度: 零。**

Sources:
- [Nickel Paste MLCC market — Valuates](https://reports.valuates.com/market-reports/QYRE-Auto-30T12178/global-mlcc-nickel-inner-electrode-paste)
- [Nickel powder MLCC patent US20190084040A1 — Google Patents](https://patents.google.com/patent/US20190084040A1/en)
- [Nickel Powder for MLCC 2031 — Valuates](https://reports.valuates.com/market-reports/QYRE-Auto-9H11589/global-nickel-powder-for-mlcc-internal-electrodes)

---

## 保護塗層 ([[聚醯亞胺]]) 端

[[MLCC]] 在後段封裝可能用 [[聚醯亞胺]] (PI) 或環氧樹脂作保護層,但 [[008004]] 體積極小、PI 用量是奈克級;且日系 MLCC 廠的 PI 多用 [[UBE]] (宇部興產) 或 [[Mitsubishi Gas Chemical]] (三菱瓦斯化學) 內製。

台廠有 PI 樹脂能力的 [[達邁]] (3645)、[[長興]] (1717,長興材料) 主力是 [[FPC]]、[[COF]]、半導體 [[光阻液]] 應用,**未見公開資料指出有切入 [[008004]] MLCC 保護塗層**。

**結論: [[008004]] 保護塗層端對 TW 上市公司近乎沒有暴露。**

---

## TW vs 日商技術差距與 catch-up 可能性

| 材料環節 | TW catch-up 進度 | 差距 (年) | catch-up 卡點 |
|---|---|---|---|
| 鈦酸鋇 nano-grade (≤ 100 nm) | [[信昌電]] 2027 量產目標 | 5-7 年 | 水熱法/草酸鹽法 know-how + 專利;煅燒爐純度控制 |
| 鎳漿料 (內電極) | 無台廠玩家 | 8-10 年 | 化學還原法 know-how + Big-4 toll refining 綁定 |
| 銅/銀漿料 (端電極) | [[勤凱]] 已認證日韓系,銅漿 2026 進日本 | 2-3 年 | 粒徑均勻度 (D90/D10 控制) + Big-4 認證週期 |
| 保護塗層 PI | 達邁/長興有能力,但無切入 | 不適用 | 用量太小,沒有經濟誘因 |
| 端電極 underplating (Ni-Sn) | 國內被動元件廠多自製 | n/a | 用量少 |

**結構性結論:**
- 鈦酸鋇 nano + 鎳漿料是**日系真寡占**,有專利護城河 + 化學工程 know-how,TW 短期難以撼動
- 銅/銀漿料是**最有機會 catch-up 的環節**,因為大顆粒銅銀漿是大宗品,TW 廠 (勤凱) 在粒徑均勻度只需追上 Big-4 規格即可
- 即使 catch-up,**[[008004]] BOM 切換週期 18-24 個月**,所以 2026-2027 不太可能看到 TW 上游材料在 [[008004]] 出貨營收 — 但中階尺寸 (0402、0201) 與大尺寸高壓 ([[AI 伺服器]] PSU 用) 是真實成長題材

---

## 投資角度: 上游材料端 008004 受惠強度排序

| 排名 | 公司 | 受惠強度 | 觸發時間 | 核心邏輯 |
|---|---|---|---|---|
| 1 | 4760 [[勤凱]] | 中等偏弱 (短期); 中高 (2027+) | 2026-2027 | 銅漿/銀漿 catch-up,日本被動元件廠認證 2026 突破 |
| 2 | 6173 [[信昌電]] | 弱 (短期 [[008004]] 不是主戰場); 中 (2029+) | 2027 Q3 新廠投產後 | 100 nm 鈦酸鋇粉 catch-up,日系替代題材 |
| 3 | 3645 [[達邁]] / 1717 [[長興]] | 極弱 (基本無交集) | n/a | PI 用量極小、無切入證據 |
| 4 | 3236 [[千如]] | 零 | n/a | 業務與鈦酸鋇/MLCC 介電粉體無關 |

**真正受惠者 (非台股):**
- [[Sakai 化學]] (4978.T 堺化學工業) — 鈦酸鋇龍頭
- [[Shoei Chemical]] (4970.T 昭榮化學) — 鎳漿龍頭
- [[Murata]] (6981.T) — 自製 BaTiO3 + 自製鎳漿 + [[008004]] 量產領先,垂直整合最深的玩家

**台股相對配置建議 (上游材料端):**
- 想吃 [[008004]] 純題材 → 沒有純正受惠標的,需配置日股 [[Sakai 化學]]、[[Shoei Chemical]]
- 想吃 [[MLCC]] 升級 + AI 伺服器高壓 MLCC 題材 → [[信昌電]] (6173) 是最直接、最具垂直整合優勢的標的
- 想吃漿料 catch-up + 日韓認證進展 → [[勤凱]] (4760),但須監控 2026 法說會的日本客戶實際出貨進度

---

## Open questions

1. **[[勤凱]] 銅漿粒徑等級是多少?** 公開資料未揭露 D50/D90,無法判斷是否符合 [[008004]] 規格 (端電極 Cu paste 通常需 D50 < 500 nm)。建議下次法說會直接問。
2. **[[信昌電]] 六甲新廠的 100 nm 目標是 H50 (X7R) 還是 NP0 (C0G)?** 兩者製程不同,NP0 更難。
3. **[[Sakai 化學]] 2024-2025 是否有對 [[Murata]] [[008004]] 0.1 μF 大幅擴產?** 若日方擴產帶動上游 ↑,TW 材料端是否有 spillover (例如分擔 0402 訂單)?
4. **[[國巨]] (2327)、[[華新科]] (2492)、[[禾伸堂]] (3026) 是否有任何 [[008004]] R&D 動作?** 若 TW 中游 MLCC 廠不做 [[008004]],則 [[勤凱]]、[[信昌電]] 對 [[008004]] 的暴露就只能透過日系客戶。
5. **[[千如]] 是否有可能透過散熱片/磁芯材料間接受惠?** 不直接相關,但 [[AI 伺服器]] 整體 [[MLCC]] 升級可能拉動其電感業務 (這是另外的故事,不在本 unit 範圍)。

---

## Sources

- [Murata 008004 launch — Microfarads](https://www.microfarads.com/times-articles/67-murata-008004-mlcc)
- [Murata 0402 47µF 2025-07 — Murata](https://www.murata.com/en-us/news/capacitor/ceramiccapacitor/2025/0710)
- [Kyocera 008004 — Passive Components](https://passive-components.eu/kyocera-develops-some-of-worlds-smallest-008004-multilayer-ceramic-capacitors-for-mobile-devices/)
- [信昌電 NP0 100nm 目標 — TechNews](https://cdnfinance.technews.tw/2026/05/15/high-end-np0/)
- [信昌電法說會 — 優分析](https://uanalyze.com.tw/articles/3605251570)
- [信昌電擴產 11.6 億 — 壹蘋新聞](https://news.nextapple.com/finance/20260515/DF16832A7593137D8E64886E4D16889C)
- [信昌電 法說會 2026-05-21 — 散戶鬥嘴鼓](https://poorstock.com/earningcall/6173)
- [勤凱 Q1 2026 EPS 2.55 — TechNews](https://finance.technews.tw/2026/05/25/copper-paste-for-hauling-goods/)
- [勤凱 客戶長單 — 鉅亨](https://news.cnyes.com/news/id/6469971)
- [勤凱 打進日韓認證 — 理財周刊](https://www.moneyweekly.com.tw/ArticleData/Info/%E7%90%86%E8%B2%A1%E5%91%A8%E5%88%8A/72657)
- [勤凱 1 月營收破 2 億 — 經濟日報](https://money.udn.com/money/story/5612/9304026)
- [勤凱法說會 2025/11 — vocus](https://vocus.cc/article/691ffe60fd89780001aa25b6)
- [Barium Titanate Powder For MLCC Market — Verified Market Reports](https://www.verifiedmarketreports.com/product/barium-titanate-powder-for-mlcc-market/)
- [Electronic Grade BaTiO3 Powder Market — Global Growth Insights](https://www.globalgrowthinsights.com/market-reports/electronic-grade-barium-titanate-batio3-powder-market-120150)
- [BaTiO3 size dependence dielectric — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0169433224018245)
- [Vacancy engineering BaTiO3 — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0032591024005989)
- [MLCC Nickel Inner Electrode Paste Market — Valuates](https://reports.valuates.com/market-reports/QYRE-Auto-30T12178/global-mlcc-nickel-inner-electrode-paste)
- [Nickel Powder MLCC patent US20190084040A1 — Google Patents](https://patents.google.com/patent/US20190084040A1/en)
- [千如 3236 公司簡介 — 鉅亨](https://www.cnyes.com/twstock/intro/3236.htm)
- [千如做什麼 — nStock](https://www.nstock.tw/%E5%8D%83%E5%A6%82%E5%81%9A%E4%BB%80%E9%BA%BC.html)
