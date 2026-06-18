# TW 功率元件 / PMIC 產業鏈 Deep-Dive — Design Spec

**Date:** 2026-06-18
**Status:** Draft, approved for execution
**Author:** felix0921 + Claude
**Project:** TW Electronic Device Supply Chain (My-TW-Coverage)
**Catalyst source:** [Sinotrade 功率元件漲價循環啟動](https://www.sinotrade.com.tw/richclub/hotstock/功率元件漲價循環啟動-台廠德微領軍掀漲潮-還有哪些代表個股----股市話題-6a17a7d966da6118fd4577b0)

---

## 1. 目的

填補 `themes/` 自動產出索引與**策展型**敘事間的 gap，圍繞三個 convergent driver：(1) 功率元件漲價循環啟動，(2) [[安世半導體]] (Nexperia) 出口管制轉單效應，(3) AI 伺服器電源架構升級（12V → 48V → 800V HVDC），建立完整 TW 功率元件 + PMIC 供應鏈 mapping。

### 1.1 In scope

- Discrete power semi (MOSFET / IGBT / Diode / GaN HEMT / SiC MOSFET) 國際 vs TW 比較
- PMIC 整合 (DC-DC / LDO / Battery PMIC / VRM)
- AI Server VRM module (多相 buck、ORv3、48V → POL)
- 13 家 TW 個股 deep-dive：強茂、德微、台半、富鼎、大中、漢磊、世界先進、矽力-KY、致新、茂達、天鈺、嘉晶、杰力
- 三大 catalyst 深入分析（漲價循環、Nexperia 轉單、AI 伺服器電源）

### 1.2 Out of scope

- 模組製造商與終端品牌（[[台達電]] 電源模組、[[光寶科]] PSU — 已有獨立 [[電動車]] / [[AI 伺服器]] 主題）
- IGBT 模組封裝（屬電動車主題，本報告僅在 §3.2 點到）
- 8255 朋程（未在 Pilot_Reports，本次 Appendix 標記為「建議新增 coverage」）
- 立錡 Richtek（已併入 [[聯發科]]，無獨立 ticker；於 §3.6 國際 vendor 段提及）

### 1.3 Success criteria

1. ≥10 family-level building blocks 全部 mapping 到具體 TW 廠商
2. 每個 design-win 主張 ≥2 source 或標 `*（市場傳聞）*` / `*（推測）*`
3. ≥10 個股 deep-dive 各含「角色 / Design-win / 營收占比 / 2026-2027 看點」固定結構
4. 三個 catalyst 段落各含時間軸 + 具體 % 量化（漲價幅度、轉單規模、48V 滲透率）

---

## 2. 檔案架構

| 路徑 | 性質 |
|---|---|
| `docs/analysis/2026-06-18-power-semi-pmic-deep-dive.md` | 主報告（~7,500-8,000 字） |
| `themes/功率元件.md` | 自動產出索引（build_themes.py 新增 theme） |
| `scripts/build_themes.py` | 新增 `"功率元件"` THEME_DEFINITION + `analysis_doc` 欄位 |
| `docs/analysis/research-notes/00-power-semi-verification-log.md` | (可選) 若 inline research 產生需驗證的具體 % 數字 |

**Theme definition 草稿:**
```python
"功率元件": {
    "name": "功率元件 Power Semiconductor / PMIC",
    "desc": "功率半導體與電源管理供應鏈 — MOSFET/IGBT/Diode/GaN/SiC discrete + PMIC integrated + AI Server VRM",
    "related": ["AI 伺服器", "電動車", "氮化鎵", "碳化矽", "資料中心"],
    "analysis_doc": "docs/analysis/2026-06-18-power-semi-pmic-deep-dive.md",
},
```

---

## 3. 主報告章節骨架

(已確定，見上述 brainstorming 對話)

§0 TL;DR (~300)、§1 fundamentals (~800)、§2 catalysts (~1100)、§3 chip matrix (~1700)、§4 TW 分層 (~900)、§5 13 家 deep-dive (~2500)、§6 catalysts/risks (~400)。

---

## 4. 研究方法論

**Phase 1 — 三大 catalyst inline research（3-5 WebSearch + 2-3 WebFetch）:**

- Search 1: "功率元件漲價 2026"、"power semi pricing cycle 2026"
- Search 2: "Nexperia 安世半導體 出口管制 轉單"、"Nexperia export control TW supplier"
- Search 3: "AI server 48V VRM Open Compute Project ORv3"

**Phase 2 — 13 個股 inline research（每家 ~1 WebSearch + Pilot_Report read）:**

對每家：
1. 讀 `Pilot_Reports/<Sector>/<Ticker>_<Name>.md` 確認身份 + 既有業務描述
2. 1 WebSearch："[ticker] [name] 法說會 2026"、"[ticker] AI 伺服器"
3. 抽取角色 / Design-win / 營收占比 / 2026 看點

**Phase 3 — Adversarial verify（可選，若出現精確 % 主張）:**

對任何 ≥3 位元精確度的主張（例如 X.X% 漲幅、X.X 億訂單）做 1 次 cross-check WebFetch。

---

## 5. 與專案規範對齊

- **Wikilinks**：TW 公司 Chinese (`[[強茂]]`、`[[矽力-KY]]`)、外商 English (`[[Infineon]]`、`[[Nexperia]]`、`[[Wolfspeed]]`)
- **Confidence marker 慣例**：無標記 = IR/法說會、`*（市場傳聞）*` = 媒體、`*（推測）*` = 產品線推論
- **不動財務區**：個股 deep-dive 不重算財務、不修改既有 Pilot_Reports
- **Traditional Chinese narrative**

---

## 6. Definition of Done

- [ ] 主報告 7,500-8,000 字
- [ ] ≥80 proper-noun wikilinks
- [ ] 13 個股全部 deep-dive 完成
- [ ] `themes/功率元件.md` regenerate 成功 + 含 📖 link
- [ ] 三大 catalyst 各含具體量化（不只 narrative）
- [ ] Commit + cherry-pick + cross-repo PR (via Semiconductor-Supply-Chain fork)

---

## 7. 後續步驟

Spec approve 後直接 invoke `superpowers:writing-plans` 或跳到 execute（本 spec 已內含執行細節，可直接 execute）。
