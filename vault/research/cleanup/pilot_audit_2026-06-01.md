---
type: research
status: draft
last_updated: 2026-06-01
source_unit: 13
tags: [cleanup, audit, pilot_reports, quality]
---

# Unit 13: Pilot_Reports Quality Audit (2026-06-01)

本報告針對 `Pilot_Reports/` 全部 1,735 份 ticker 報告執行靜態品質檢查，依據 [[CLAUDE.md]] Golden Rules 1–10 量測 wikilink 密度、placeholder 殘留、metadata 完整度、章節結構，以及禁用詞 (大廠/供應商/客戶/廠商/原廠/製造商/業者/企業/公司) 是否誤入 `[[...]]` 包裝。所有檢查皆為唯讀；未觸動 `## 財務概況` 區段，符合 Golden Rule #5。

## TL;DR — top 3 findings

1. **整體品質達 99.94% 通過率** — 1,734 / 1,735 份 reports 通過全套規則檢查；僅 1 份 (`Electronic Components/洋華_3622.md`) 因 wikilink 數量 = 6 < 8 而違規。Golden Rule #4 floor 幾乎全部達標。
2. **零 placeholder、零 metadata gap、零 banned-word 違規** — 全 repo 找不到 `待 AI 補充`、`(待更新)`、`基於嚴格實名制` 等 placeholder；`板塊/產業/市值/企業價值` 四欄位 metadata 完整度 100%；wikilink 內含「大廠/供應商/客戶/廠商/原廠/製造商/業者/企業/公司/代理商/品牌商/營運商/貿易商/通路商/零售商/承包商/開發商/服務商/整合商」者為 0 筆。Golden Rules #1, #7, #8 全面達標。
3. **長尾低密度 sector 集中在非電子本業** — `Real Estate Services` (avg 9.2)、`Utilities - Regulated Gas` (9.5)、`Banks` (9.5)、`Real Estate - Development` (9.7)、`Education & Training Services` (9.8) 五個 sector 平均 wikilink 數低於 10，多為服務業/金融業/不動產，與電子供應鏈核心 ([[CoWoS]], [[HBM]], [[矽光子]], [[FOPLP]], [[CPO]]) 關聯薄弱，屬可接受範圍但仍是再 enrichment 優先候選。

---

## 整體統計

| 指標 | 數值 |
|---|---|
| Pilot_Reports 總檔數 | **1,735** |
| 通過全部規則 (clean) | **1,734** (99.94%) |
| `audit_batch.py --all` 結果 | **1,733 / 1,733** (100%) — 132 個已完成 batch 全部通過 |
| Placeholder 出現次數 (`待 AI 補充` / `(待更新)` / `基於嚴格實名制`) | **0** |
| Metadata 不完整檔案數 (缺 板塊/產業/市值/企業價值 任一) | **0** |
| Wikilink < 8 的檔案數 | **1** |
| `[[...]]` 內含 banned word (大廠/供應商/客戶...) 的檔案數 | **0** |
| 缺章節 (業務簡介/供應鏈位置/主要客戶及供應商/財務概況) 檔案數 | **0** |
| Wikilink 全 repo 最小值 | **6** (`3622_洋華`) |
| Wikilink 全 repo 平均值 (粗估) | **~16.7** |

### Wikilink 數量分布 (頭部 6 個 bin)

| 數量 | 檔案數 |
|---|---|
| 6 | 1 |
| 8 | 163 |
| 9 | 143 |
| 10 | 117 |
| 11 | 104 |
| 12 | 119 |

→ 163 份檔案剛好踩在 8 的法定下限。考慮報告長度自然分佈，此屬合理；但若日後想將 floor 拉到 10，將有 **307 檔** (8+9) 需要補強。

---

## 各 sector 品質排序

排序原則：依違規率 (issue_rate) 由低到高；issue_rate = (placeholder + missing_meta + under_8 + generic_wl + missing_sections 任一發生的檔案數) ÷ sector 檔數。

### 最佳 sector (avg_wl 高，無違規)

| Sector | n | avg_wl | min_wl | issue_rate |
|---|---|---|---|---|
| Asset Management | 1 | 50.0 | 50 | 0.0% |
| Airlines | 4 | 48.5 | 39 | 0.0% |
| Advertising Agencies | 1 | 45.0 | 45 | 0.0% |
| Consulting Services | 2 | 39.0 | 32 | 0.0% |
| Oil & Gas Refining & Marketing | 1 | 39.0 | 39 | 0.0% |
| Aerospace & Defense | 10 | 35.3 | 25 | 0.0% |
| Telecom Services | 5 | 31.2 | 16 | 0.0% |
| Auto Manufacturers | 7 | 28.3 | 18 | 0.0% |
| Apparel Manufacturing | 12 | 27.3 | 9 | 0.0% |
| Specialty Chemicals | 63 | 24.4 | 9 | 0.0% |

### 核心電子板塊 sector (大宗)

| Sector | n | avg_wl | min_wl | issue_rate |
|---|---|---|---|---|
| Electronic Components | **267** | 17.4 | 6 | 0.4% (1 檔違規) |
| Semiconductors | 155 | 14.8 | 8 | 0.0% |
| Computer Hardware | 114 | 17.8 | 8 | 0.0% |
| Specialty Industrial Machinery | 85 | 18.0 | 8 | 0.0% |
| Electrical Equipment & Parts | 76 | 18.6 | 8 | 0.0% |
| Communication Equipment | 70 | 17.0 | 8 | 0.0% |
| Semiconductor Equipment & Materials | 63 | 16.9 | 9 | 0.0% |
| Consumer Electronics | 27 | 14.2 | 8 | 0.0% |
| Software - Infrastructure | 21 | 19.1 | 11 | 0.0% |
| Software - Application | 18 | 17.3 | 10 | 0.0% |
| Scientific & Technical Instruments | 13 | 12.1 | 8 | 0.0% |

### 平均 wikilink 數最低的 13 個 sector (cleanup 候選)

| Sector | n | avg_wl | min_wl | 說明 |
|---|---|---|---|---|
| Thermal Coal | 1 | 8.0 | 8 | 單一公司，剛好踩底線 |
| Publishing | 1 | 8.0 | 8 | 單一公司 |
| Gambling | 1 | 8.0 | 8 | 單一公司 |
| Real Estate Services | 19 | 9.2 | 8 | 不動產服務，供應鏈淺 |
| Utilities - Regulated Gas | 6 | 9.5 | 8 | 公用事業 |
| Banks | 2 | 9.5 | 9 | 銀行業 |
| Real Estate - Development | 34 | 9.7 | 8 | 建商，可補上下游建材供應鏈 |
| Education & Training Services | 4 | 9.8 | 8 | 補教業 |
| Building Products & Equipment | 9 | 10.7 | 8 | 建材 |
| Waste Management | 16 | 10.8 | 8 | 廢棄物處理 |
| Utilities - Regulated Electric | 2 | 11.0 | 8 | 包含 [[台電]]，可補燃氣/IPP 上游 |
| Home Improvement Retail | 1 | 11.0 | 11 | 單一公司 |
| Business Equipment & Supplies | 14 | 11.0 | 8 | 辦公設備、印表機 |

> 觀察：非電子本業 sector 的低 avg_wl 屬正常 — 服務業/金融業/不動產業 的「供應鏈」本身比 [[半導體]]、[[PCB]]、[[載板]] 等扁平。技術名詞少 → wikilink 自然少。**不必為了補數字而硬塞 [[XXX]]，違反 Golden Rule #1 反而更糟。**

---

## Top 20 broken wikilink 違規檔案

**結果：0 筆。** Repo 全面通過 banned-word-in-wikilink 規則。完整掃描 1,735 檔的所有 `[[...]]`，沒有任何一筆 wikilink 內含下列禁用詞：大廠 / 供應商 / 客戶 / 廠商 / 原廠 / 經銷商 / 製造商 / 業者 / 企業 / 公司 / 代理商 / 品牌商 / 營運商 / 貿易商 / 通路商 / 零售商 / 承包商 / 開發商 / 服務商 / 整合商。

> 過去 batch 整理階段針對 `[[國際農藥原廠]]`、`[[電信營運商]]`、`[[北美大型車廠]]`、`[[跨國農化公司]]` 等案例已徹底清理。Golden Rule #1 enforce 成功。

---

## Top 10 worst Pilot_Reports (需 enrichment 重跑)

依綜合品質分 (placeholder×10 + missing_meta×5/欄 + generic_wl×3/筆 + missing_section×8/節 + max(0, 8-wl)×2) 由高 (差) 到低排序：

| Score | 檔案 | wikilinks | placeholder | metadata 缺 | banned wl | 缺章節 |
|---|---|---|---|---|---|---|
| 4 | `Electronic Components/3622_洋華.md` | **6** | 0 | 0 | 0 | 0 |

**僅 1 檔需處理。** [[洋華]] (3622) 觸控面板 + 機電工程雙軌業務，現有 wikilinks 為 `[[台電]]`、`[[消費性電子]]`、`[[大亞]]`、`[[華新]]`。建議補：
- 機電上游：`[[古河電氣]]` (已於文中提及但未 wikilink)
- 觸控材料：`[[ITO 薄膜]]`、`[[控制 IC]]`
- 終端客戶：`[[電子紙]]`、`[[POS 機]]`、工控/醫療具體品牌
- `[[消費性電子]]` 屬廣義類別 — 可考慮換成具體下游品名或 [[Apple]]/[[Samsung]] 級 OEM

執行：
```bash
python scripts/update_enrichment.py --data <json> 3622
```

> **next worst**：除這 1 檔外，其餘 1,734 檔全部通過。沒有「top 10」可列。

---

## 建議 (排優先序的 cleanup 動作)

1. **(P0, 5 min)** 補 `3622_洋華` 至少 2 筆 wikilink，使達 8 下限。直接編輯或跑 `update_enrichment.py`，注意保留 `## 財務概況` (Golden Rule #5)。
2. **(P1, optional)** 若想將 wikilink floor 從 8 拉至 10，目標族群為 **307 檔** (數量 = 8 或 9)；建議以 sector 為單位先處理 `Real Estate - Development` (34 檔, avg 9.7)、`Real Estate Services` (19 檔, avg 9.2)、`Waste Management` (16 檔, avg 10.8)、`Business Equipment & Supplies` (14 檔, avg 11.0) — 服務業/不動產業可補通用客戶 (如 [[台積電]]、[[台塑]]、[[中華電信]]) 或上游建材 ([[預拌混凝土]]、[[鋼筋]])。
3. **(P2, monitoring)** 將本 audit 加入 weekly cron — 與 `vault_lint.py` 一同執行，輸出 append 到 `vault/log.md`。腳本可重複利用本檔 `/tmp/full_audit.py` 邏輯。
4. **(P3, 工具強化)** 為 `audit_batch.py` 新增 `--all-files` mode，不限於 `task.md` 標 `[x]` 的 batch；目前 `--all` 漏掉 batch 127 (132 個 batches 列表中跳過 127) 及任何未列入 task.md 的散戶 ticker。本次自製 audit 補上此盲點。
5. **(P4, 報告呈現)** WIKILINKS.md 索引可加入 `--check` mode，輸出「孤兒 wikilink」(只被 1 個 ticker 引用) 與「死連結」(wikilink target 不存在於任何 entity stub) 的清單，回補 `vault/entities/`。

---

## Sources

- [[CLAUDE.md]] (project root) — Golden Rules 1–10 是本 audit 的判定基準
- `scripts/audit_batch.py` — 既有單批/全批 audit (132 個已完成 batches，pass rate 100%)
- `scripts/build_wikilink_index.py` — 既有 wikilink 統計 (此次未跑 rebuild，僅 inspect 模式)
- `/tmp/full_audit.py` — 本 unit 自製 full-file scan，補齊 batch-only 盲點
- `/tmp/full_audit_result.json` — 機器可讀統計輸出 (含 98 sector 完整 rank、placeholder count、metadata gap、worst file 詳情)
- `Pilot_Reports/Electronic Components/洋華_3622.md` — 唯一一份違規檔案的當前內容
- `task.md` — batch 完成狀態 (用於對照 `--all` 模式覆蓋範圍)
- 全域指令 `~/.claude/CLAUDE.md` — DevOps Pipeline 與 verification-before-completion 規約
