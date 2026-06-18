# LEO 衛星通訊技術 × 台灣供應鏈 Deep-Dive — Design Spec

**Date:** 2026-06-18
**Status:** Draft, pending implementation plan
**Author:** felix0921 + Claude (brainstorming session)
**Project:** TW Electronic Device Supply Chain (My-TW-Coverage)

---

## 1. 目的與範疇

### 1.1 問題陳述

專案目前在低軌衛星（LEO satellite）主題已有 `themes/低軌衛星.md` 自動產出的供應鏈索引（涵蓋 42 家 TW 上市櫃公司），但這份索引是 `build_themes.py` 從各 ticker 報告 wikilink 反向統計而來，**只有「誰」沒有「為什麼」與「在哪一層」**。讀者無法從中得知：

- LEO 通訊系統實際上由哪些技術 block 組成？
- 每個 block 的國際 vendor 是誰？TW 廠商扮演什麼角色？
- 四大全球星座（Starlink / Kuiper / OneWeb / 台星 B5G）的技術選擇有何差異？這對 TW 供應鏈意味著什麼？
- 哪些 TW 公司是「中性贏家」（跨星座 design-win）、哪些只押注單一星座、哪些只是市場傳聞？

本 spec 設計一份 deep-dive 報告以填補這個 gap，產出策展型敘事（curated narrative）並與既有自動化索引互補。

### 1.2 In scope

- LEO 衛星通訊系統技術原理（鏈路架構、頻段、五大 building blocks）
- 四大星座技術 SKU 對比（Starlink v1/v2、Kuiper、OneWeb/Eutelsat、台星 B5G）
- 晶片層級 supply chain matrix：每個 building block 對應到國際 vendor + TW 玩家
- 模組／系統層 TW 廠商 design-win 分布（UT、Gateway、天線/波導、PCB/機構/電源）
- 8 家代表性 TW 個股 deep-dive
- 2026-2027 catalysts 與風險

### 1.3 Out of scope

- 衛星 payload 本體（衛星 bus、太陽能板、推進系統）— 屬航太主題，非電子供應鏈
- 軍規衛星通訊（DoD SATCOM）— 規格保密、非公開 supply chain
- 地面站光纖回程（fiber backhaul）— 屬電信回傳基礎建設
- 監管政策深度分析（FCC/NCC 賽局）— 本報告僅在 catalysts 段落點到
- 量化估值 / 目標價 — 本報告為產業 mapping，不做個股估值

### 1.4 Success criteria

完成後本報告需滿足：

1. **完整性**：所有 `themes/低軌衛星.md` 列出的 42 家 TW 公司，要嘛在本報告被 mapping 到具體技術 block，要嘛在 Appendix 註明排除原因。
2. **可追溯性**：每個技術規格主張可追到 FCC filing / ITU notification / 官方白皮書；每個 TW design-win 主張至少 2 個獨立 source 支持（IR/法說會優先）。
3. **差異化價值**：晶片層 mapping（§3）必須提供「`themes/低軌衛星.md` 看不到的洞察」— 例如 D2C 中性贏家、ADC/DAC gap、Optical ISL 的 TW 光通配套關聯。
4. **更新性**：報告結構允許之後逐章節 patch（新星座升空、新 design-win 公告），不需要全文重寫。

---

## 2. 檔案架構

### 2.1 產出檔案清單

| 路徑 | 性質 | 維護方式 |
|---|---|---|
| `docs/analysis/2026-06-18-LEO-satellite-deep-dive.md` | 主報告，策展敘事 | 手寫，重大事件時 patch |
| `themes/低軌衛星.md` | 供應鏈索引 | `build_themes.py` 自動產出，不手改 |
| `scripts/build_themes.py` | 索引產生器 | 新增 ~8 行 patch 以渲染 `analysis_doc` 連結 |

### 2.2 `build_themes.py` 變更規格

在 `THEME_DEFINITIONS["低軌衛星"]` 新增 optional 欄位：

```python
"低軌衛星": {
    "name": "低軌衛星 LEO Satellite",
    "desc": "低軌道衛星通訊供應鏈，天線、地面站、射頻模組",
    "related": [...],
    "analysis_doc": "docs/analysis/2026-06-18-LEO-satellite-deep-dive.md",  # NEW
},
```

在主題 markdown 生成函式（`build_themes.py` 約 line 220 附近）的「涵蓋公司數」前面插入：

```python
if theme_def.get("analysis_doc"):
    rel_path = f"../{theme_def['analysis_doc']}"
    lines.append(f"> 📖 **深度分析:** [LEO 衛星通訊技術 × 台灣供應鏈 deep-dive]({rel_path})")
    lines.append("")
```

向後相容：其他主題未設 `analysis_doc` 時行為不變；本機制可日後沿用至 CoWoS / 矽光子 / HBM 等主題的 deep-dive。

### 2.3 主報告反向 link

主報告 (`docs/analysis/2026-06-18-LEO-satellite-deep-dive.md`) 在頭部 metadata 區塊提供反向連結回 `themes/低軌衛星.md`，讓讀者可在「策展敘事」與「機械索引」之間雙向流動。

---

## 3. 主報告章節骨架

**目標篇幅：5500-6000 字（Traditional Chinese）**

### §0 — TL;DR & 投資 thesis（~300 字）

- 一句話 thesis（2 句話內）
- LEO 衛星通訊供應鏈鳥瞰圖（ASCII 或表格形式）：上游晶片 → 中游模組 → 下游系統
- 三個 key takeaway bullet

### §1 — LEO 通訊技術 fundamentals（~900 字）

- §1.1 為何 LEO 取代 GEO：延遲（~30ms vs ~600ms）、capacity-per-region、deploy economics
- §1.2 Space-Air-Ground 鏈路：Gateway ↔ Sat ↔ ISL ↔ User Terminal 四節點
- §1.3 頻段配置：Ka (17/28 GHz) / Ku (12/14 GHz) / V (40/50 GHz) / S (D2C) 分工與 ITU 監管限制
- §1.4 五大 building blocks（與 §3 編號嚴格對應）：
  - (a) Phased Array Beamforming → §3.1
  - (b) Modem SoC（DVB-S2X / 5G NTN / D2C）→ §3.4
  - (c) RF Front-End（PA/LNA/Filter）→ §3.2-3.3
  - (d) Optical ISL（terabit 級星間光通）→ §3.5
  - (e) ADC/DAC + Frequency Synthesizer → §3.6

### §2 — 四大星座技術 SKU 對比（~700 字）

技術規格 matrix（表格）：

| 規格 | Starlink v1 | Starlink v2 mini/v2 | Kuiper | OneWeb | 台星 B5G |
|---|---|---|---|---|---|
| 軌道高度 | | | | | |
| 用戶端頻段 | | | | | |
| Gateway 頻段 | | | | | |
| Phased Array 世代 | | | | | |
| Optical ISL | | | | | |
| D2C 支援 | | | | | |

對每個星座，討論「技術選擇為何如此」+ 對 TW 供應鏈的意涵（哪些 TW 廠商在這個星座有 design-win 機會）。

### §3 — 晶片層 supply chain matrix【核心章節】（~1700 字）

每個 sub-section 結構：
- **功能**：這個 block 在 LEO 系統中做什麼
- **國際 vendor 與 spec leadership**
- **TW 玩家與角色**（IC 設計、wafer foundry、封測、模組）
- **Design-win 證據**（引用 Pilot_Reports / IR / 法說會）

子章節：
- §3.1 Beamformer IC → ADI / MaxLinear / Anokiwave / Renesas vs 7812 稜研、3105 穩懋（GaAs PA 配套）
- §3.2 GaN / GaAs PA → Qorvo / Skyworks / MACOM vs 5222 全訊、3105 穩懋
- §3.3 LNA / Switch → ADI / Qorvo vs 6271 同欣電（封裝）、3152 璟德
- §3.4 Modem SoC + 5G NTN → 國際主要 modem 玩家為 [[聯發科]] (MT6825 5G NTN)、Qualcomm (X80)、Broadcom；台灣本身就是這個 block 的全球 leader（[[聯發科]] HQ 在新竹）— **核心個股、跨星座中性贏家**
- §3.5 Optical ISL TRx → Coherent / Lumentum / II-VI vs 3363 上詮、3081 聯亞、4979 華星光通（連結到 [[矽光子]] 主題）
- §3.6 ADC/DAC + PLL → ADI / TI / Renesas 主導，**標明 TW in-house gap**

### §4 — 模組與系統層 TW 玩家（~900 字）

- §4.1 User Terminal (UT/CPE)：6285 啟碁、3491 昇達科、2314 台揚、3419 譁裕
- §4.2 Gateway 地面站：3138 耀登、6928 攸泰科技、2314 台揚
- §4.3 天線 / 波導 / 濾波器：3491 昇達科、6792 詠業、3221 台嘉碩
- §4.4 PCB / 機構件 / 電源：2383 台光電、6274 台燿、6412 群電、2367 燿華

每節 100-200 字，連結到 §3 對應晶片 block。

### §5 — 8 家代表性 TW 個股 deep-dive（~1200 字）

每家 ~150 字，固定結構：
- **角色**：在 LEO 鏈中扮演什麼層級
- **Design-win**：已知對應星座或客戶
- **營收占比估算**：LEO 業務占比（若可估）
- **2026-2027 看點**：產能、新案、風險

清單：
- 5.1 6285 啟碁（UT module + 系統整合）
- 5.2 3491 昇達科（Ka/V 波導 + 雙工器）
- 5.3 5222 全訊（GaN PA，軍工 + LEO）
- 5.4 3105 穩懋（GaAs PA wafer foundry）
- 5.5 7812 稜研科技（Phased Array IC + 終端）
- 5.6 6271 同欣電（高頻 RF 封裝）
- 5.7 2454 聯發科（5G NTN / Direct-to-Cell，跨星座中性贏家）
- 5.8 6928 攸泰科技（Antenna + UT integration）

### §6 — 2026-2027 Catalysts & Risks（~400 字）

**Catalysts**：
- Starlink V3 generational 升級（更大 phased array、更高 throughput）
- Kuiper 正式商轉（2026-2027 目標）
- 台星「鯢魚 1B」升空與 TASA B5G 規格凍結
- D2C 商用化擴大（MediaTek 5G NTN 出貨放量）

**Risks**：
- SpaceX 自製比例提高，擠壓 TW IC 設計房空間
- Starlink Direct-to-Cell 蠶食傳統 UT 市場（影響 6285 / 2314）
- 頻譜監管延宕（特別是 D2C 頻段）
- 中美科技脫鉤對台廠出貨美系星座的二次影響

### 附錄 A：完整 TW LEO 個股 mapping table

40+ tickers 與 `themes/低軌衛星.md` 對齊；任何 themes 有但本報告未深入提及者，列出排除原因。

### 附錄 B：Verification log

詳見 §4 研究方法論。

---

## 4. 研究方法論

### 4.1 Phase 1 — Foundation research（`deep-research` skill）

跑 3 個 focused deep-research calls，每個 args 約 200 字題目，要求**結構化輸出**（claim + source + confidence），不要長 prose：

**Call 1 — 星座技術規格 fact-check**
- 目標：四大星座的軌道高度、頻段、Phased Array 世代、Optical ISL 是否有、D2C roadmap
- Source 限定：FCC filings、ITU notifications、官方白皮書、IEEE / Spacenews

**Call 2 — 晶片層 vendor landscape**
- 目標：Beamformer / PA / Modem / Optical ISL TRx / ADC 各 block 的國際主要 vendor + spec leadership
- Source：vendor datasheets、EDN/AnandTech teardowns、Mobile Experts / Northern Sky Research analyst notes

**Call 3 — TW design-win evidence**
- 目標：對每個我打算寫進報告的 TW ticker，搜「[Ticker] LEO 衛星」「[Company] Starlink supplier」「[Company] phased array」
- Source 必須包含：法說會逐字稿 / 年報 主要客戶段 / IR 公告 / 媒體報導（後者降權，僅 cross-confirm 用）

### 4.2 Phase 2 — Project-local cross-reference

```bash
# 補洞: 用 discover 看是否漏掉 TW 公司
python scripts/discover.py "Phased Array" --smart
python scripts/discover.py "Beamformer"
python scripts/discover.py "Ka band"
python scripts/discover.py "光收發"
python scripts/discover.py "5G NTN"

# 對齊驗證: themes/低軌衛星.md 的 42 家 vs deep-dive
diff <(grep -oE '[0-9]{4}' themes/低軌衛星.md | sort -u) \
     <(grep -oE '[0-9]{4}' docs/analysis/2026-06-18-LEO-satellite-deep-dive.md | sort -u)
```

任何 themes 有但 deep-dive 沒提的 ticker → 要嘛納入要嘛在附錄 A 註明排除原因。

### 4.3 Phase 3 — Per-ticker evidence chain

§5 的 8 家個股，每家必須有：
- ✅ 從 `Pilot_Reports/{Sector}/{Ticker}_{name}.md` 引用既有 `[[低軌衛星]]` 段落（若已有）
- ✅ 至少 2 個獨立來源支持「LEO 業務存在」的主張
- ❌ 若只有 1 個媒體報導、無 IR/法說會證實 → 降級為「市場傳聞」並以 `*（市場傳聞，未經 IR/法說會證實）*` 斜體標記附在該句末尾

**Confidence marker 慣例**（用於 §3、§5 所有 TW design-win 主張）：
- 無標記 = 已有 IR/法說會/年報明確證實
- `*（市場傳聞，未經 IR/法說會證實）*` = 僅有媒體報導，無公司一手來源
- `*（推測，依產品線推論）*` = 無外部來源，純依公司既有產品線合理推論

### 4.4 Phase 4 — Verification log

附錄 B 結構：

| Claim category | Source format |
|---|---|
| 星座技術規格 | FCC filing # / ITU notification ID / 官方文件 URL + 日期 |
| 晶片 vendor spec | Datasheet revision + 日期 |
| TW design-win | Pilot_Reports 內部引用 + 外部 2 source（IR/法說會優先） |
| 個股財務數字 | 直接引用 `Pilot_Reports/.../XXXX_*.md` 的 `## 財務概況` 區段（不重算） |

### 4.5 量化主張規則

依 CLAUDE.md Golden Rule 0：本報告若出現「最高/最大/最快/最罕見」等比較級／分布形容詞，必須先驗證再寫，並把驗證 evidence 寫入 Verification log。預期本報告主要是定性 mapping，量化主張集中在 §2 規格表（純規格事實，非分布主張）與 §5 個股看點。

---

## 5. 與專案規範對齊

### 5.1 Wikilinks（CLAUDE.md Golden Rule 1）

本報告全文使用 `[[...]]` 包覆所有 specific proper nouns：
- 公司：`[[台積電]]`、`[[聯發科]]`、`[[Apple]]`、`[[SpaceX]]`、`[[Qualcomm]]`（TW 公司用中文，外商用英文，per 專案慣例）
- 技術：`[[Phased Array]]`、`[[CoWoS]]`、`[[矽光子]]`、`[[5G NTN]]`、`[[Direct-to-Cell]]`
- 材料：`[[GaN]]`、`[[GaAs]]`、`[[磷化銦]]`
- 應用：`[[低軌衛星]]`、`[[AI 伺服器]]`、`[[資料中心]]`

通用詞如「大廠」「供應商」「客戶」「廠商」一律以 plain text 出現，禁止包 `[[...]]`。

### 5.2 Ticker-Company identity（CLAUDE.md Golden Rule 2）

§5 個股 deep-dive 寫作前，每家公司必須先 read `Pilot_Reports/{Sector}/{Ticker}_*.md` 確認檔名 ↔ 公司一致，絕不從 ticker number 推斷公司名。

### 5.3 不動財務區（CLAUDE.md Golden Rule 5）

§5 個股段落引用財務時，**只引用既有 Pilot_Reports 的 `## 財務概況` 區段內容**，不在 deep-dive 中重新計算或重新呈現財務表格。

### 5.4 Traditional Chinese（CLAUDE.md Golden Rule 6）

主報告全文 Traditional Chinese 撰寫（除技術英文縮寫如 LEO、Ka-band、Phased Array、UT、ISL 等專有名詞）。

---

## 6. 風險與緩解

| 風險 | 緩解 |
|---|---|
| Deep-research 找不到關鍵 TW design-win 證據 | §5 對應公司降級為「市場傳聞」標記；報告誠實標示 evidence quality |
| `build_themes.py` patch 影響其他主題渲染 | Patch 為純 additive、有 `if theme_def.get("analysis_doc")` guard，其他主題不變 |
| 報告寫到一半發現 themes 已過時 | 寫作前先跑 `python scripts/build_themes.py 低軌衛星` 重建索引 |
| 個股 deep-dive 與 Pilot_Reports 內容矛盾 | 以 Pilot_Reports 為 ground truth；若 deep-dive 研究發現新事證，更新 Pilot_Reports 並 commit |
| Token 預算超支 | 3 個 deep-research call 預估 50-80k output；超過時優先保 Call 3（TW design-win），Call 1-2 可用既有公開資料替代 |

---

## 7. Out of scope（重申）

- 不做估值 / 目標價
- 不做衛星 payload（bus、推進、太陽能）
- 不做監管政策深度分析
- 不重算財務數字
- 不修改既有 Pilot_Reports（除非 deep-research 發現需更新的事證）

---

## 8. Definition of Done

- [ ] `docs/analysis/2026-06-18-LEO-satellite-deep-dive.md` 完成，5500-6000 字
- [ ] `scripts/build_themes.py` patch 完成；`python scripts/build_themes.py 低軌衛星` 跑過，`themes/低軌衛星.md` 頂部出現 📖 深度分析連結
- [ ] 報告含至少 8 個 `[[...]]` 個股 wikilink、所有國際 vendor 與技術 block 均 wikilinked
- [ ] 附錄 A 覆蓋率：themes 42 家 → 報告全部 mapping 或註明排除原因
- [ ] 附錄 B Verification log 完整：每個技術主張可追、每個 design-win 有 ≥2 source
- [ ] 報告反向 link 回 `themes/低軌衛星.md`
- [ ] Commit message 含 spec 路徑引用

---

## 9. 下一步

本 spec approved 後，invoke `superpowers:writing-plans` skill 產出 step-by-step implementation plan，包含：

1. Foundation research（3 個 deep-research calls 的具體 args 與 schema）
2. Project-local cross-reference 執行順序
3. 報告章節寫作順序（建議 §1 → §3 → §4 → §5 → §2 → §6 → §0 → 附錄）
4. `build_themes.py` patch 與測試
5. Verification log 整理與 commit policy
