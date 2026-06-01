---
type: project
status: active
last_updated: 2026-05-15
---

# Active Projects

## Asia covariance panel + dashboard
**Status:** ✅ Done 2026-05-15 — daily refresh + next-week regime monitoring pending
**Why:** Cross-market context for TXF trades (replaces ad-hoc WebSearch)
**Deliverables:** 9,560 rows × 13 indices, 7,776 rows × 10 FX, 416 news tagged, HTML dashboard `analysis/dashboards/latest/`
**Key finding:** **[[TXF]]–[[DXY]] 60d β = −1.47 (2026-05-16 最新)** vs 3y 平均 β = −0.37 → macro sensitivity 4× steeper. 三組數值與 [[covariance_panel]] 一致 (single source of truth: `data/twii_dxy_beta.parquet`). Single most important external variable currently.
**Next:** Daily 18:00 TWT cron + bond yields + commodities (Phase 8 in plan)

## FOPLP rotation basket
**Status:** monitoring
**Why:** 5/12 PCA identified glass-substrate-vs-ABF rotation factor
**LONG:** [[../../Pilot_Reports/Electronic Components/3481_群創]] (loading −0.438), [[../../Pilot_Reports/Electronic Components/2408_南亞科]], [[../../Pilot_Reports/Semiconductors/2454_聯發科]]
**SHORT:** 8046 南電 (+0.491), 3037 欣興, 3017 奇鋐
**Trigger:** Continue if 3481 法人 > +50M/week; exit if 3481 跌破 5MA
**Source:** `data/emergent_factor_baskets.foplp_glass_vs_abf_rotation_2026_05`

## 00763U copper position management
**Status:** active position, cost NT$31.47
**Why:** Inflation re-acceleration (4月 PPI YoY +6%) + DXY weakness in select windows = copper bull
**Take-profit ladder (5/13 set):** Sell 15 張 @36.50, 25 @37.50, 25 @39.00, 25 @41.00; hold 10
**Stop-loss ladder:** 34 / 33 / 31
**Latest check:** 5/15 close, position +13% from cost
**Trigger to review:** DXY > 100 (commodities pressured) or LME copper drop > 3% in single day

## TXF watchlist (top-of-mind)
**3481 群創** — FOPLP main, 5/13 法人 +127M 大買; 短線可能拉回 5% 但題材 intact
**2317 鴻海** — 純 AI 主題,5/13 法人 +17M; 加碼點 210/195 未到
**2330 台積電** — 外資賣投信買僵局,2,200 為觀察線,5/21 NVIDIA 法說會為催化
**5469 瀚宇博** — 深度價值 PCB,P/E 13.6, P/B 1.10;法人流向背離待解讀

## Vault + cross-session messaging
**Status:** ✅ Done 2026-05-15
**Why:** Each Claude session re-derives context; need persistent knowledge layer
**Deliverables:** `vault/`, `scripts/claude_msg.py`, `scripts/redis_to_vault.py`, `scripts/vault_session_boot.py`, `scripts/vault_lint.py`
**Boot:** every new Claude session runs `python3 scripts/vault_session_boot.py` first
