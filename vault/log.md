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
