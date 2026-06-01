---
type: trading
status: active
last_updated: 2026-05-15
related: [positions.md, ../concepts/TXF.md, ../concepts/DXY.md]
tags: [playbook, rules]
---

# Trading Playbooks (Trigger-Based Rules)

Reusable conditional rules. Each playbook = **explicit trigger + action** + rationale. Per user preferences: **trigger-based exit only, no premature profit-taking**.

## TWD Defense Line Breach
**Trigger:** USD/TWD daily close > 31.80
**Action:** 立即減 TXF 倉位 50%
**Rationale:** CBC defends band 30.5-33.0; breach signals capitulation, external 資金加速撤離. See `../concepts/TXF.md` USD/TWD warning levels.
**Last triggered:** Not in 2026 history yet (band held all year)

## DXY Macro Sensitivity (regime active)

**β 口徑** (與 [[covariance_panel]] / `concepts/TXF.md` / `concepts/DXY.md` 同步, single source of truth = `data/twii_dxy_beta.parquet`):
- 3y 平均 β = **−0.37** (regime baseline, 平常水準)
- **60d β = −1.47** (2026-05-16 最新, 4× 偏離 baseline) ← 本 playbook 使用此值

**Triggers + responses (using 60d β = −1.47):**

| DXY 變動 (24h) | 預期 TXF | Action |
|---|---:|---|
| > 100.5 (+1.5%) | −2.2% | 減 50%, 停損 41,200 |
| 99.5 | −0.7% | 觀望 |
| 平 (~99) | 震盪 | 持有 |
| 98.5 | +0.7% | 加碼 |
| < 98 (−1%) | +1.5% | 突破前高加碼 |

**Playbook 啟用條件 (activation threshold, 非 β 量測值):** 60d β 保持在 **< −0.6** 即視為 regime 仍在 (距 baseline −0.37 有顯著偏離)。Re-check weekly via `data/twii_dxy_beta.parquet`。當 60d β 回到 **−0.5 或更淺** (接近 3y baseline −0.37) 時, 切換至 alpha-driven 分析 ([[KOSPI]] / [[Nikkei]] lead)。

## Basis Extreme Short
**Trigger:** TXF futures-cash basis < −500 points (vs 平常 −50 to −150)
**Action:** Short TXF mini (MXF) when 5MA bounces fail
**Rationale:** Deep basis = forward sellers dominate; 5/15 closed at −591 (year's largest discount). 5/21 為 5 月期貨結算日 → squeeze 風險上行。
**Status (2026-05-15):** Basis = −591, conditions met, but 5/19 開盤先看 DXY 確認方向

## 00763U Copper Ladder (current)
**Take-profit (already documented in `positions.md`):**
- 36.50 sell 15; 37.50 sell 25; 39.00 sell 25; 41.00 sell 25; hold 10 runner
**Stop-loss:**
- 34 / 33 / 31 (sequential 30張 / 30張 / all)
**Re-evaluate triggers:**
- DXY > 100 sustained 3 days → 通膨壓力可能反轉 → 緊縮 ladder (move 37.50 → 36.00)
- LME copper drop > 3% single day → emergency review
- China PMI < 49 → demand weakness signal

## TXF Pair Trade (散熱 cannibalization, conditional)
**Trigger:** 5/19 開盤 USD/TWD > 31.80 AND 3481 法人轉賣
**Action:** Long 鴻海 2317 / Short 高力 8996 + 奇鋐 3017 + 健策 3653 配對
**Rationale:** AI 主題集中度高的散熱中段股,在 macro risk-off 環境下會被獲利了結, 純 AI ODM (2317) 相對抗跌. Source: 2026-05 PCA pure_ai_vs_iphone_dilution basket.
**Sizing:** Long 1 unit 2317, Short 0.3 + 0.3 + 0.4 unit (notional equal)

## NVIDIA Q1 法說會 (5/21) — known catalyst
**Pre-event:** 法說前 3 日減 50% AI 概念曝險 (2330/2449/3231)
**Post-event scenarios:**
- Beat & raise → 5/22 開盤加碼 2330 / 2449 / 6669
- In-line → 持平觀察一週
- Miss → AI 概念全面減碼,長空 6669

## When to break a playbook
Only when:
1. β / σ verification shows the underlying assumption no longer holds (e.g., 60d β 從 −1.47 重新接近 3y baseline −0.37; 或量測 β 跌出 < −0.6 啟用門檻)
2. Major event invalidates the regime (e.g., Fed surprise cut, Iran resolution)
3. User explicitly overrides

Otherwise: **trust the trigger, even when emotion says otherwise**.
