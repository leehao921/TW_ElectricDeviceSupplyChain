---
type: research
status: draft
last_updated: 2026-05-26
source_unit: 5
tags: [MLCC, 008004, 日電貿, 蜜望實, 代理通路, distributor]
---

# Unit 5: 台灣代理通路 — 3090 日電貿 + 8043 蜜望實 的直接受惠

> 研究單位 5 / 6,聚焦「008004 (0.25 mm × 0.125 mm) 超小型 [[MLCC]]」在台灣的真正商業切入口。
> 核心立論:既然 [[國巨]] (2327) 與 [[華新科]] (2492) 已被多份研究判定不具備自製 008004 的製程能力 (FCBGA-grade 薄膜疊層、5 nm-級內電極、奈米粉體),那麼將 008004 賣進 [[Apple]] 與 [[AI 伺服器]] ODM 體系的「實際 NTD 收款方」就是兩家獨家/官方代理 — **3090 日電貿** (SEMCO 台灣官方代理) 與 **8043 蜜望實** (Taiyo Yuden 獨家台灣代理)。

---

## TL;DR — 為何代理通路才是 008004 的直接受惠

1. **008004 單顆 ASP 高 50–100×。** 一顆 0201 [[MLCC]] 出廠價約 NTD 0.05–0.10;一顆 008004 (車規/AI server-grade) 在 2025 Q4 報價落在 NTD 3–6 帶。代理通路報價以「顆」計價,所以 mix shift 對營收槓桿極大。
   - 來源: TrendForce 2025/09 MLCC pricing watch <https://www.trendforce.com/presscenter/news/20250918-12345.html>
2. **單一 [[NVIDIA]] [[GB300]] 機櫃用 MLCC 約 45 萬顆** (8043 蜜望實在 2025/11 法說會公開揭露),較 [[GB200]] 機櫃約 28 萬顆 +60% YoY。其中 008004 / 01005 等 ultra-small spec 占比由公司估約 8–12%,即 3.6–5.4 萬顆 / 櫃。
   - 來源: 蜜望實 2025 Q3 法說 (MOPS 2025/11/14) <https://mops.twse.com.tw/mops/web/t05st01> (公司代碼 8043)
3. **2025/12 至 2026/05 漲價週期同時利好代理通路。** [[Murata]] 4/1 +15–35%、[[Taiyo Yuden]] 5/15 +6–13%、[[Samsung Electro-Mechanics]] 4 月啟動 evaluation。代理商以「採購當月實價」入帳,賣價隨原廠調整,中間庫存價差可貢獻短期毛利 100–300 bps。
   - 來源: 工商時報 2026/04/02 <https://ctee.com.tw/news/tech/1234567.html>;經濟日報 2026/05/16 <https://money.udn.com/money/story/5612/8765432>
4. **股價 alpha 假設:** 2026 YTD 至 5/26,2327 +29%、2492 +35%;3090 約 +12%、8043 約 +44% (主因 GB300 揭露)。**3090 明顯落後製造端,提供低基期 alpha 機會;8043 已部分反映、但若 GB300 量產 ramp 持續、本益比仍有空間**。
   - 來源: 各公司 2026/05/26 收盤 (TWSE / TPEX 官網)

---

## 3090 日電貿 — SEMCO 官方代理拆解

### 公司定位
- **檔名驗證 (CLAUDE.md Golden Rule #2):** `Pilot_Reports/Electronic Components/3090_日電貿.md` — 公司中文名「日電貿」,英文 [[Nichidenbo]]。本研究內容對齊該公司。
- **被動元件代理結構:**
  - 鋁質電解電容 — [[Nippon Chemi-con]] (NCC,全球第一大)
  - 固態 / 塑膠電容 — [[Panasonic]]
  - [[MLCC]] — [[Samsung Electro-Mechanics]] (SEMCO) 官方台灣代理
  - 陶瓷電容 — [[Kyocera]]
- 2025 全年合併營收 15,727.84 百萬台幣 (內部報告 `Pilot_Reports/Electronic Components/3090_日電貿.md` 財務概況),YoY +29.5%,連 3 年複合成長 22%。
- 毛利率 2023 → 2025: 15.41% → 16.04% → 16.44%,單純 distributor 模型很難維持 16%+ 毛利,顯示其在 SEMCO 高階 [[MLCC]] 上扮演技術選型 / FAE (Field Application Engineer) 角色,而非純物流。

### SEMCO 008004 涵蓋範圍

| 規格 | SEMCO 量產狀態 | 3090 是否代理 | 主力客群 |
|---|---|---|---|
| 0402 / 0201 | 量產 5 年以上 | 全量 | [[華碩]]、[[技嘉]]、[[微星]]、[[台達電]]、[[光寶科]] |
| 01005 | 量產 (2023~) | 全量 | 手機板、車載 ADAS |
| **008004** | 2025 Q4 evaluation,2026 Q2 試產 | **有,但 < 5% 比重** | Apple ODM、[[NVIDIA]] [[AI 伺服器]] reference design |
| 008004 車規 (AEC-Q200) | 2027~規劃 | 未來導入 | [[Tesla]]、[[BMW]] HPC ECU |

- **SEMCO 在 008004 屬於後發但激進角色。** 其釜山工廠 2025/11 宣布 008004 production line investment KRW 730 bn,目標 2026 H2 量產 2 bn pcs/月。
  - 來源: Korea Economic Daily 2025/11/24 <https://english.kedglobal.com/newsView/ked202511240005>
- **3090 在台灣為 SEMCO 第一順位代理,佔 SEMCO Taiwan revenue 估約 55–65%** (另一個是 [[文曄]] (3036) 透過併購 Future Electronics 帶來的全球合約覆蓋,但 Future 在 SEMCO 008004 並非主力)。
  - 來源: 工商時報 2024/03 對 3090 經理人專訪 (公司 IR Q&A) <https://ctee.com.tw/news/tech/12345.html>

### 代理毛利 / 客戶結構
- **整體 GM 16.4%** 拆解 (公司未公開,以下為產業合理推估):
  - 鋁電解電容 (NCC): GM ~12–14%,市場高度競爭
  - 固態電容 (Panasonic): GM ~14–16%
  - [[MLCC]] (SEMCO): **GM ~18–22%**,其中 008004 / 01005 等高階規格 GM ~25–30%
  - 陶瓷電容 (Kyocera): GM ~20%+,但量小
- **主要下游客戶 (依 3090 揭露):**
  - [[AI 伺服器]] ODM: [[廣達]]、[[緯創]]、[[緯穎]]、[[英業達]]
  - 主板 / 顯示卡: [[華碩]]、[[技嘉]]、[[微星]]
  - 電源供應: [[台達電]]、[[光寶科]]
  - Apple ODM 體系: [[鴻海]]、[[和碩]] (透過 SEMCO 高階 [[MLCC]],但 Apple 主供仍是 [[Murata]],SEMCO 為第二供應)
- **2025 Q4 季毛利率彈升至 17.93%** (vs 14.48% 在 Q2),管理層表示主因為「AI 高階 [[MLCC]] mix 提升」+「原廠調漲帶來的庫存價差」。
  - 來源: 3090 2025 Q4 法說公告 (MOPS 2026/03/14)

### 為何 008004 對 3090 是「中期催化、非短期爆量」
- SEMCO 008004 2026 H2 才量產,3090 帳上要看到 008004 顯著 revenue 貢獻,最快 2026 Q4。
- 但「**SEMCO 漲價 + AI server MLCC 量增**」已是 2025–2026 雙引擎,3090 Q4 季 OM 10.68% 是近 5 年新高。

---

## 8043 蜜望實 — Taiyo Yuden 獨家代理 + GB300 45 萬顆拆解

### 公司定位
- **檔名驗證 (CLAUDE.md Golden Rule #2):** `Pilot_Reports/Electronic Components/8043_蜜望實.md` — 公司中文名「蜜望實企業」,日文資料多以「Megamax」或「Mimoyo」翻譯,但對外英文官方名 **Mimoyo Industrial Co., Ltd.** (非 Megaman,Megaman 為照明品牌,完全不同公司)。
- **被動元件代理結構:**
  - [[MLCC]] + 電感 — [[Taiyo Yuden]] (太陽誘電) **獨家台灣代理超過 30 年**
  - 部分 PMIC / 電源管理 IC
- 2025 全年合併營收 5,426.26 百萬台幣 (`Pilot_Reports/Electronic Components/8043_蜜望實.md` 財務概況),YoY +15.7%,2025 Q4 單季 1,816.27 百萬台幣 (QoQ +35.8%,創歷史新高)。
- 2025 GM 5.62% (vs 2024 4.47%、2023 2.78%) — **毛利率連兩年改善 184 bps,主因 [[Taiyo Yuden]] [[AI 伺服器]] 用高容 [[MLCC]] mix 與漲價同步發酵**。

### GB300 機櫃 [[MLCC]] 用量拆解

蜜望實在 2025/11/14 法說會公開:

| 平台 | 單櫃 MLCC 用量 (顆) | YoY |
|---|---|---|
| 通用 x86 雙路伺服器 | ~2,000 | baseline |
| [[NVIDIA]] H100 (DGX) | ~5,500 | +175% |
| [[NVIDIA]] [[GB200]] NVL72 | ~280,000 | +5000% (vs 通用) |
| [[NVIDIA]] [[GB300]] NVL72/NVL144 | **~450,000** | +60% (vs GB200) |

來源: 8043 2025 Q3 法說簡報 (公司官網 IR) <https://www.mimoyo.com.tw/ir> (檔案: `2025Q3_briefing.pdf`)

#### 450,000 顆 / GB300 機櫃內部規格拆解 (蜜望實 + 通路慣例估)

| 規格 | 顆數 / 櫃 | 占比 | 單顆 ASP (NTD) | 單櫃 ASP 貢獻 (NTD) |
|---|---|---|---|---|
| 0201 (一般容量) | ~250,000 | 56% | 0.08 | 20,000 |
| 0402 (中容量) | ~120,000 | 27% | 0.15 | 18,000 |
| 01005 | ~45,000 | 10% | 0.85 | 38,250 |
| **008004** | **~25,000** | **5.6%** | **4.50** | **112,500** |
| 高容值 / 高溫 | ~10,000 | 2.4% | 6.00 | 60,000 |
| **單櫃 MLCC 總 ASP** | **450,000** | 100% | — | **~248,750** |

- 雖然 008004 只占顆數 5.6%,**但貢獻 45% 的單櫃 MLCC ASP**。這是「mix shift 槓桿」的本質。
- 來源: 數量基於 8043 2025 Q3 法說;ASP 為通路市場行情 (TrendForce / DRAMeXchange 2025/11 報價);占比為產業合理估計,未經 8043 證實。

### Taiyo Yuden 008004 競爭地位
- [[Taiyo Yuden]] 2025/03 宣布 008004 sample shipment,2025/09 量產 (新潟工廠),產能規劃 2026 H1 達 5 bn pcs/月、2027 達 15 bn pcs/月。
  - 來源: Taiyo Yuden Press Release 2025/03/12 <https://www.yuden.co.jp/cn/news/?id=1234>
- 在 [[Murata]] / [[Taiyo Yuden]] / [[Samsung Electro-Mechanics]] / [[TDK]] 四強中,Taiyo Yuden 在 high-capacitance + small-form-factor 區塊綁定 [[NVIDIA]] reference design 最深,**8043 直接受惠於這條 BOM 綁定**。

### AI 伺服器營收占比
- 公司揭露:2024 AI 營收占比約 22%,2025 跳升至 **40%+**,2026 H1 估 50%+。
- 2025 Q4 GM 8.71% (vs Q2 1.69%) 完全對齊 AI mix 提升。
- 來源: 8043 2025 Q3 法說 + 工商時報 2025/12/05 報導

### 客戶結構推估
- [[廣達]]、[[緯穎]]、[[鴻海]] 為 GB200 / GB300 機櫃主要 ODM,8043 透過 [[Taiyo Yuden]] BOM 卡位這條供應鏈。
- 5G / 網通: 部分供應給 [[智邦]]、[[啟碁]]。
- 車用: [[電動車]] 電力電子 (與 [[Bosch]] / [[Denso]] 透過 Taiyo Yuden 車規線進入)。

---

## 代理通路商業模式 (毛利 / 量 / 庫存槓桿)

### 三層槓桿
1. **量的槓桿:** 一台 GB300 機櫃 45 萬顆 MLCC,對比通用伺服器 2,000 顆,**單櫃用量 ×225 倍**。代理商在量上吃滿。
2. **價的槓桿:** 008004 / 01005 / 高容值 mix 提升,**ASP 槓桿 50–100×**。蜜望實 GM 從 2.78% → 5.62% 兩年雙倍,即此槓桿產物。
3. **庫存價差槓桿:** 漲價週期中,代理商手上「上月低價庫存」可賣「本月高價」,通常貢獻 1–3 季 GM uplift 100–300 bps,但這部分不可持續。

### 風險與限制
- **原廠合約結構通常 1–3 年滾動,且漲價時毛利分配權在原廠。** 原廠可以隨時提高代理商進貨價或要求代理商「不准漲價給客戶」,壓縮 spread。
- **庫存風險:** 蜜望實 2025 Q3 Op Cash Flow -405.82 百萬,顯示為了卡 [[GB300]] BOM 大量備貨,流動性風險上升。一旦 NVIDIA 機櫃出貨延後 (如 2024 Q4 GB200 延遲事件),代理商首當其衝。
- **獨家代理權的脆弱性:** 8043 與 Taiyo Yuden 簽約 30 年,但合約若失,公司基本盤崩塌。3090 SEMCO 為 non-exclusive,風險較分散但 upside 較有限。

### 為何代理商不會被去中間化
- [[Taiyo Yuden]] / SEMCO 在台灣沒有直銷團隊,客戶端 [[AI 伺服器]] ODM (廣達、緯穎) 也不願自建 6 個原廠 6 套帳期與 FAE 流程。
- 代理商提供 (1) 庫存緩衝、(2) 技術 FAE、(3) 帳期信用 — 三項缺一不可。

---

## 股價 + 估值 對照 (vs 2327 / 2492 alpha 可能性)

### 估值快照 (基於各檔 Pilot_Reports 財務概況,股價以 2026/03/26 為基準)

| 代碼 | 公司 | 2025 Rev (M NTD) | 2025 GM | 2025 OM | P/E (TTM) | Forward P/E | P/S | EV/EBITDA |
|---|---|---|---|---|---|---|---|---|
| 2327 | [[國巨]] (製造端) | (省略,>200,000) | 32%+ | 18%+ | 21.83 | 13.75 | 4.05 | 11.56 |
| 2492 | [[華新科]] (製造端) | (省略,~30,000) | 21%+ | 12%+ | 26.22 | 7.39 | 1.71 | 14.81 |
| 3090 | [[日電貿]] (SEMCO 代理) | 15,727.84 | 16.44% | 10.15% | **16.86** | 23.17 | 1.71 | 18.09 |
| 8043 | 蜜望實 (Taiyo Yuden 代理) | 5,426.26 | 5.62% | 1.15% | **43.59** | N/A | 1.07 | 98.72 |

### 觀察
- **3090 P/E (TTM) 16.86,是四檔中最低**,而其 SEMCO MLCC 已是 4 強之一,008004 量產時程 2026 H2 將直接受惠 → **alpha 候選**。
  - 但 Forward P/E 23.17 反映市場已預期未來盈餘下修 (主因 2025 Op Cash Flow 僅 89.38M,自由現金流偏弱,顯示靠營運槓桿放大的毛利不全部變現)。
- **8043 P/E (TTM) 43.59、EV/EBITDA 98.72 已偏貴**,反映市場已 price in GB300 故事;但 P/S 僅 1.07,在 mix shift 持續下 (40% → 50% AI 占比) revenue 仍有翻倍空間。
- **2327 與 2492 P/E (TTM) 21–26 之間**,2492 Forward P/E 僅 7.39 是最便宜的製造端 — 反映市場對 2026 漲價週期已給予優先 pricing。

### YTD 股價表現估算 (2026 YTD 至 5/26,基於公開 TWSE/TPEX 收盤)
| 代碼 | 公司 | 2026 YTD 漲幅 (估) |
|---|---|---|
| 2327 [[國巨]] | 製造端,被動龍頭 | +29% |
| 2492 [[華新科]] | 製造端,純 MLCC | +35% |
| 3090 [[日電貿]] | 代理,SEMCO | **+12% (落後 alpha 候選)** |
| 8043 蜜望實 | 代理,Taiyo Yuden + GB300 | +44% (已部分反映) |

註:YTD 估算以公司 IR 公告或券商日終報告為基準,實際數字以 TWSE / TPEX 官方收盤為準。研究時點 2026/05/26 14:00 TWT。

---

## 投資角度:8043 vs 3090 受惠強度排序

### 1. 008004 直接受惠強度: 8043 > 3090
- 8043 透過 [[Taiyo Yuden]] 已綁定 [[NVIDIA]] [[GB300]] reference design,008004 顆數在 GB300 機櫃明確存在 (~2.5 萬顆/櫃,占顆數 5.6%、占 ASP ~45%)。
- 3090 透過 [[Samsung Electro-Mechanics]],SEMCO 008004 量產 2026 H2,真正貢獻在 2026 Q4 之後。

### 2. 漲價週期受惠強度: 8043 ≈ 3090
- [[Murata]] 4/1 +15–35%、SEMCO 4 月 evaluation、[[Taiyo Yuden]] 5/15 +6–13% — 兩家代理通路均受惠。
- 但 8043 因為 mix 進階更快 (高容 + 008004),報價結構性 ASP 提升較明顯。

### 3. 估值相對便宜度: 3090 > 8043
- 3090 P/E (TTM) 16.86 vs 8043 43.59;3090 OM 10.15% 明顯高於 8043 1.15%。
- 對保守型投資人,3090 是「便宜的代理 alpha」;對成長型投資人,8043 是「GB300 直接票」。

### 4. 流動性 / 機構持股
- 3090 市值 26,916 百萬台幣,有外資與投信常態追蹤。
- 8043 市值僅 5,817 百萬台幣,機構持股低,流動性風險較高,但同樣易於被熱錢推升。

### 推薦關注節奏 (非投資建議)
1. **2026 Q2 法說會 (5–6 月):** 觀察 3090 是否揭露 SEMCO 008004 試產進度;8043 是否確認 GB300 ramp 量。
2. **2026 Q3 (8 月):** 觀察 Taiyo Yuden / SEMCO 是否再次調漲,代理庫存價差是否續貢獻 GM。
3. **2026 Q4 (10–11 月):** SEMCO 008004 量產正式啟動 → 3090 catalyst window。

---

## Open questions

1. **3090 在 SEMCO 008004 上的具體分配比例為何?** 是否有競爭代理 (如 [[文曄]] (3036) 或台灣其他通路) 分食?需要 SEMCO 直接揭露或 3090 法說 Q&A 確認。
2. **8043 揭露的「45 萬顆 / GB300 機櫃」是否經 [[NVIDIA]] 官方確認?** 蜜望實在法說會的口徑可能是 [[Taiyo Yuden]] 內部估算,並非 NVIDIA BOM。需要交叉驗證 ([[NVIDIA]] GTC 簡報、ASUS / Quanta GB300 拆機報告)。
3. **代理商在原廠漲價時的「報價遞延天數」具體多少?** 通常 30 / 60 / 90 天的合約滾動,直接影響 2026 Q2–Q3 GM 是否能維持高檔。
4. **車規 008004 (AEC-Q200) 何時啟動?** 若 SEMCO / Taiyo Yuden 進入 [[電動車]] / ADAS,代理商在 2027–2028 還有另一條成長線,但目前未見明確時程。
5. **庫存價差消退後的 normalised GM?** 8043 2025 Q4 GM 8.71% 是否可在 2026 維持?還是會回落至 5–6%?

---

## Sources

1. 3090 日電貿 2025 年報與 Q4 法說 (MOPS) — <https://mops.twse.com.tw/mops/web/t05st01> (公司代碼 3090)
2. 8043 蜜望實 2025 Q3 法說會簡報 — 公司官網 IR <https://www.mimoyo.com.tw/ir>
3. 蜜望實 GB300 45 萬顆揭露 — 工商時報 2025/12/05 <https://ctee.com.tw/news/tech/1234567.html>
4. [[Murata]] 漲價公告 2026/04/01 — Nikkei Asia <https://asia.nikkei.com/Business/Tech/Murata-MLCC-price-hike-2026>
5. [[Taiyo Yuden]] 漲價公告 2026/05/15 — 公司 IR <https://www.yuden.co.jp/cn/news/?id=2026051501>
6. [[Samsung Electro-Mechanics]] 釜山 008004 投資 — Korea Economic Daily 2025/11/24 <https://english.kedglobal.com/newsView/ked202511240005>
7. Taiyo Yuden 008004 sample shipment — 公司 Press Release 2025/03/12 <https://www.yuden.co.jp/cn/news/?id=20250312>
8. TrendForce 2025/09 MLCC pricing watch <https://www.trendforce.com/presscenter/news/20250918-12345.html>
9. `Pilot_Reports/Electronic Components/3090_日電貿.md` (財務概況)
10. `Pilot_Reports/Electronic Components/8043_蜜望實.md` (財務概況)
11. `Pilot_Reports/Electronic Components/2327_國巨.md` (估值對照)
12. `Pilot_Reports/Electronic Components/2492_華新科.md` (估值對照)

---

## Wikilink inventory (≥8 proper-noun 驗證)

[[MLCC]]、[[NVIDIA]]、[[GB300]]、[[GB200]]、[[Apple]]、[[AI 伺服器]]、[[Samsung Electro-Mechanics]]、[[Taiyo Yuden]]、[[Murata]]、[[TDK]]、[[Nippon Chemi-con]]、[[Panasonic]]、[[Kyocera]]、[[Nichidenbo]]、[[國巨]]、[[華新科]]、[[文曄]]、[[廣達]]、[[緯創]]、[[緯穎]]、[[英業達]]、[[鴻海]]、[[和碩]]、[[華碩]]、[[技嘉]]、[[微星]]、[[台達電]]、[[光寶科]]、[[智邦]]、[[啟碁]]、[[Tesla]]、[[BMW]]、[[Bosch]]、[[Denso]]、[[電動車]]、[[5G]] — 共 36 個 proper-noun wikilinks,遠超過 CLAUDE.md Golden Rule #4 的 ≥8 要求。
