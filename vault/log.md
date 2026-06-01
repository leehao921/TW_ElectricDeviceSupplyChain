# Vault Log

Append-only chronological record of vault events. Format: `## [YYYY-MM-DD HH:MM TWT] {event_type} | {summary}`

Event types: `ingest` (new source) · `query` (notable Q&A) · `lint` (health check) · `sync` (Redis → vault) · `update` (page edit) · `bootstrap` (initial population)

---

## [2026-05-15 16:00 TWT] bootstrap | Initial vault populated — 13 pages across user/projects/concepts/trading/meta

Pages created:
- meta/schema.md
- user/profile.md, preferences.md, tools.md
- projects/active.md, pending.md, completed.md
- concepts/TXF.md, DXY.md, covariance_panel.md, FOPLP.md
- trading/positions.md, playbooks.md
- log.md (this file), index.md

Source migration:
- 6 existing memory files (`reference_*`, `feedback_*`) → distilled into preferences.md
- Recent session findings (Asia panel covariance, 5/13–5/15 analyses) → concepts/TXF.md + DXY.md + covariance_panel.md
- Current positions (00763U @ 31.47) → trading/positions.md
- Trigger-based rules (DXY > 100, USD/TWD > 31.80) → trading/playbooks.md

## [2026-05-15 15:59 TWT] sync | claude:inbox stream initialized

First message: `TXF_boot — claude_msg.py 上線測試 (5/15 算出 TXF-DXY 60d β = -1.47)`. Redis port 6379, container `trading-redis`, stream `claude:inbox`. Cursor file at `~/.claude/projects/-Users-lulala-Documents-coding-My-TW-Coverage/.claude_msg_cursor`.

## [2026-05-15 16:05 TWT] sync | claude:inbox 3 msgs + signal_alerts 0 rows → vault/inbox/2026-W20.md

## [2026-05-15 16:08 TWT] lint | 1 orphans, 0 stale, 3 contradictions, 1 missing-from-index, 0 stale-in-index

## [2026-05-15 16:09 TWT] lint | 0 orphans, 0 stale, 1 contradictions, 0 missing-from-index, 0 stale-in-index

## [2026-05-16 12:15 TWT] ingest | themes/UAV.md created — 28 companies, 7 national team members, supply chain mapped. User search "自強建設" disambiguated to 自強工程顧問 (private, 3D GIS / 圖資 platform niche).

## [2026-05-20 22:30 TWT] ingest | themes/邊緣運算.md created (254 lines, 109 wikilinks) + concepts/edge_ai_inference.md (Nano-tier focus). Catalyst: NVDA Q1 FY27 公布 ACIE $37B 拆分,Edge / Industrial 推論 narrative 啟動. Seven competitor camps analyzed (NVIDIA Jetson Orin Nano Super / Hailo / AMD Kria / Rockchip RK3588 / Qualcomm QCS6490 / MediaTek Genio / Ambarella). NVDA Nano-tier 全球市占 <25%. TW alpha L1-L4 mapped: 6579 研揚 (純度最高) / 2454 聯發科 Genio (自家 SoC 挑戰) / 3044 健鼎 (carrier board 通吃) / 3289 松騰 (終端).

## [2026-05-21 10:23 TWT] lint | 0 orphans, 0 stale, 1 contradictions, 0 missing-from-index, 0 stale-in-index

## [2026-05-26 22:00 TWT] ingest | 008004 MLCC batch research (6 parallel worktrees) → themes/MLCC.md + vault/concepts/MLCC_008004.md

6 unit slices in `vault/research/008004/`:
1. spec + Big-4 量產現況 (Murata 2014 首發 / 2024/09 推出 **006003** next-gen, 非 005003)
2. 2327/2492 對 008004 真實 exposure (公開資料 0;最小 footprint 國巨 01005 imp / 華新科 0201 imp)
3. 3026/6173 利基 (兩家完全反方向 — 高壓/大尺寸 vs 008004 微小化)
4. 上游材料 (鈦酸鋇 nano 日商寡占, 6173 200nm→100nm 2027 才到位, 4760 銅漿 2026 進日本)
5. 3090/8043 代理通路 (8043 GB300 一台 45 萬顆 MLCC, 008004 占顆數 5.6% 但 ASP 占 45%)
6. 下游 BOM + Pair trade (LONG 8043/SHORT 2327 比 SHORT 2492 更乾淨;Vera Rubin VR200 MLCC $4,300/rack +182%)

Catalyst: 2327 +194.7% / 2492 +173.6% 過去 6 個月,99.9 percentile 3Y,5/14-5/25 連 4 根漲停 → 市場把 commodity 漲價 + AI server BOM + 008004 微小化錯誤掛勾。本研究釐清 TW 中游廠零 008004 直接 exposure,真正受惠是代理通路 (8043 蜜望實 + 3090 日電貿) 與材料 catch-up (6173 信昌電 + 4760 勤凱)。剔除 3236 千如 — 業務與 MLCC 介電粉體零相關。

## [2026-06-01 09:29 TWT] lint | 1 orphans, 0 stale, 1 contradictions, 1 missing-from-index, 0 stale-in-index (pre-aggregation snapshot)

## [2026-06-01 09:30 TWT] lint | 0 orphans, 0 stale, 1 contradictions, 0 missing-from-index, 0 stale-in-index

## [2026-06-01 14:00 TWT] ingest | 008004 第二輪深度驗證 batch (5 parallel worktrees) + 2 個新概念頁 + slice 01 補 Murata GRM011 SKU

5 個新 unit slice 在 `vault/research/008004/`:
7. 8043/3090 代理通路深度驗證 (305 行) — **Murata 4/1 漲價不利於 8043** (非 8043 principal);8043 008004 占 rev 6-9% (非 5.6%);Q3 OCF -405.82M = 70% A/R + 30% inventory, Q4 已收斂;3090 alpha 已 reversed 反超 8043 (+52% vs +37% 5/19-6/1)
8. 6173/4760 上游材料深度驗證 (276 行) — **6173 100nm 目標是 NP0/C0G (Class I), 不是 X7R**;6173 明確避開 0201 微小化, 主攻 1206+ 大尺寸高壓 NP0;**TW 零 Ni paste/nano-Ni 玩家** (科揚 只代理 MMS), 35-50% MLCC 成本卡死 TW 008004 整合;4760 日本仍在 cultivation
9. TW 隱藏候選 (291 行) — **新增 3030 德律 ★★★ (AXI X-ray AI server GPU PCBA 焊接後檢測, 一塊上千顆 008004)**;**新增 3189 景碩 (ABF 載板第三家, ECiP)**;觀察 3455 由田 + 6187 萬潤;ticker 修正 4977 眾達-KY 非 ABF (光通訊模組 OEM);排除 9 家 noise
10. 2327/2492 R&D pipeline (285 行) — **隱藏 R&D 強度 = 1/5 (極低)**, 跨 6 維度一致負向:專利 0 件 sub-0.4mm claim (vs Murata ≥ 3 件 US12,482,604/US20240282522A1/WO2024247128A1);0 篇 ECTC/CIPS 論文;Yageo Apple supplier list 但 design-in 止於 0402/01005;馬廠無 Hirano Tecseed/光洋熱工 high-end 設備訊號;Kemet 鉭電容才是 Yageo AI 武器
11. Catalyst calendar (372 行) — Top 3: **(1) 6/10 處置股結束 (2) 10/14-18 CEATEC (Murata 006003) (3) 11/14 前 Q3 法說 (8043 AI 占比 50%)**;25 個 catalyst rows;5 個 risk events;2026/12-2027/H1 = ASP cliff window

2 個新概念頁 (vault/concepts/):
- MLCC_008004_technical_deep_dive.md — 永久技術 reference (350+ 行, 10 段):規格命名陷阱 + 技術門檻 4 維度 + Murata GRM011 SKU 詳表 + Big-4 對照 + ASP 倍數 + 應用 4 類 + 漲價 + 006003 + TW 排序 + 檔案索引
- MLCC_008004_TW_verification.md — 6/1 驗證補丁:修正 Tier 排序 (3090 升 #1, 6173/4760 降);新增 3030/3189;TW Ni paste 0 玩家 critical finding;隱藏 R&D = 1/5;修正版 pair trade (LONG basket {3090+8043+3030}, SHORT 2327 比 2492 更乾淨)

Slice 01 補 Murata GRM011 SKU 詳表 (GRM011R60J104M 0.1µF 6.3V X5R / GRM011R61A101KE01L 100pF / C0G 1pF-0.1µF / X5R 100pF-0.1µF) + Izumo 新廠 JPY 47B 4/3 完工。

## [2026-06-01 11:29 TWT] lint | 11 orphans, 0 stale, 1 contradictions, 11 missing-from-index, 0 stale-in-index

## [2026-06-01 11:29 TWT] lint | 0 orphans, 0 stale, 1 contradictions, 0 missing-from-index, 0 stale-in-index

## [2026-06-01 14:00 TWT] ingest | 008004 PR #23 MERGED to master (commit 2b440cd)

## [2026-06-01 15:30 TWT] ingest | repo cleanup batch (4 parallel workers) — Git 整理 + Untracked → git + Vault audit + PR merge

**4 個 unit slice (cleanup):**
- 12. β_60d contradiction 解決 (commit 46ebeaa) — 5 vault 頁統一 β 口徑;真實 contradiction 為 lint over-match (「<−0.6」是 playbook 觸發條件, 不是 β 量測);正確 β: 3y avg −0.37, 60d 5/16 −1.47, 4× regime shift
- 13. Pilot_Reports audit — **1734/1735 clean (99.94%)**, 0 placeholder / 0 metadata gap / 0 banned-word wikilinks; 唯 1 違規: 3622 洋華 6 wikilinks (< 8 floor)
- 14. Untracked 27 files — (a) TRACK MUST 6 (vault scripts + themes) (b) TRACK SHOULD 19 (Asia panel + vault skeleton) (c) GITIGNORE data/ + .obsidian/ (d) EVALUATE 2 ingestion scripts (default TRACK)
- 15. Stale plans + 21 worktrees + system audit — 14 plans (13 屬 sibling repos 可刪);21 worktrees (19 clean+landed, 2 dirty);/tmp 2 enrichment JSON 可刪

**Coordinator actions:**
- PR #23 (008004 batch) MERGED → personal/master + 8 stale remote branches deleted
- cleanup/repo-organize branch + Unit 12/13/14 cherry-pick + 25 untracked files 加入 git
- .gitignore 加 data/*.parquet, data/raw/, vault/.obsidian/
- 13 stale plans + 2 /tmp enrichment 待刪;21 worktrees + 21 worktree-agent-* branches 待 prune

**Out of scope:** 921 modified Pilot_Reports (用戶前期 WIP), 其他 feature branches, PR #22
