# Quant Claim Verification Protocol

This document is a **mandatory checklist** for any analysis that uses
distribution-based quantitative descriptors (σ, percentile, "extreme", "rare",
"60d worst", "outlier") about Taiwan-market flow data. It exists because of an
incident on 2026-04-29 where a "3σ 罕見" claim about the 3-day foreign-investor
outflow was published *without* checking the historical distribution; the true
value was **z = −1.04σ (17.2 percentile)** — a moderately-heavy but non-extreme
event. 3 月份就已經發生過 4 次更糟的 3-day 賣壓。

## Triggers — when this checklist applies

If the draft analysis contains **any** of these phrases or their Chinese equivalents:

| Trigger | Why it's a quant claim |
|---|---|
| "σ", "sigma", "3σ", "2σ" | Direct distributional reference |
| "罕見", "極端", "outlier", "tail event" | Implies non-normal frequency |
| "60d 最大", "近 N 日最高/最低", "Q1 最…" | Comparative max/min over a window |
| "percentile", "分位", "前 X%" | Direct quantile reference |
| "z-score", "z = …" | Explicit standardized score |
| "罕見組合", "60d 內僅出現 N 次" | Frequency claim |

If a draft contains none of these — purely descriptive language ("外資 3 日賣
1,386 億"), it does **not** require this protocol. But the moment a magnitude
descriptor enters, the protocol is mandatory.

## Procedure

1. **Identify the metric** — single-day or rolling-K-day flow? Which actor
   (Foreign_Investor / Investment_Trust / Dealer)?

2. **Run the verifier**:
   ```bash
   python3 scripts/verify_flow_zscore.py \
       --metric foreign_net \
       --values "-511.96,-392.98,-481.47" \
       --window 60 \
       --as-of 2026-04-29
   ```
   - `--values` is a comma-separated list in **億 TWD** (signed).
   - `--window` defaults to 60 trading days; expand to 252 for "this year"
     claims.
   - `--as-of` should be the report's reference date.

3. **Read the verdict**:
   - `|z| < 1` → use neutral language ("中等", "偏空", "正常範圍")
   - `1 ≤ |z| < 2` → use "中等偏空" or "moderately heavy" (~15–30% probability)
   - `2 ≤ |z| < 3` → use "uncommon" or "near-tail" (~5% probability)
   - `|z| ≥ 3` → only then use "罕見", "extreme", "tail event"

4. **Paste the verifier output** into a "Verification log" section at the end of
   the report. Future readers must be able to reproduce the verdict.

5. **Reword the claim** to match the actual classification.

## Common pitfalls

- **3-day rolling sum ≠ 3 × single-day std.** The std of a K-day rolling sum is
  approximately √K · σ¹ᵈ only if observations are independent — which they
  aren't for foreign flow. Always use the rolling-K-day-sum's *own* empirical
  distribution, not a back-of-envelope calculation.

- **Window-end matters.** A −1,386 億 3-day window ending 2026-04-29 is
  z=−1.04σ; the same value ending 2026-03-15 (when std was 30% smaller) might
  have been z=−1.5σ. Always specify and pass `--as-of`.

- **"This year" ≠ "60d".** If the user asked about year-to-date significance,
  use `--window 252`. Don't substitute 60d.

- **Population vs sample std.** The verifier uses `pstdev` (population). For a
  60-obs window this matches the convention used in equity quant work.

## See also

- `scripts/verify_flow_zscore.py` — the verifier
- `analysis/backtest_overnight_signal.py` — IC/percentile harness (similar
  pattern; 803-day distribution against trailing 60d z-scores)
- `analysis/reports/market_view_2026-04-29_close.md` — first report following
  this protocol

---


## § 7 — Mediation-first backtesting

Adopted from rule #1 of the Jay (Two Sigma) 3-rule SOP (epic
[#13](https://github.com/leehao921/TW_ElectricDeviceSupplyChain/issues/13)). Standalone CLI: `analysis/backtest_mediation.py`.

### The principle

Don't backtest `alt-data → return` directly when alt-data history is short
(2-3 years). The return target is too noisy and the sample size (~800 days for
daily, ~36 months for monthly TW data) gives weak statistical power. With 5
factors and a noisy target, grid-search will find spurious-IC weights every
time.

Instead, split the chain:

1. **Stage 1: alt-data → fundamentals** (this is where mediation lives).
   Fundamentals (monthly revenue, quarterly earnings) are large panel data.
   For a Taiwan electronics universe of ~50 large-caps over 3 years, that's
   ~1,800 (ticker × month) observations versus ~800 daily-return samples.
   Power is much higher and overfitting risk is much lower.
2. **Stage 2: fundamentals → return** (already validated literature; Bartov,
   La Porta, Sloan). If Stage 1 holds for our specific panel, Stage 2 is
   transitively valid.

If you can't show Stage 1 with statistical significance, your alt-data
return-prediction IC is unreliable — even if it looks great on the 800-day
sample.

### Procedure

1. Run the CLI:
   ```bash
   python3 analysis/backtest_mediation.py --start 2023-01-01 --as-of 2026-04-29
   ```
2. The script:
   - pulls daily 5-factor panel via the same helpers as
     `analysis/backtest_overnight_signal.py`
   - aggregates each factor to month-end (sum for `foreign_net`, sum of daily
     simple returns for the four price factors)
   - pulls `TaiwanStockMonthRevenue` from FinMind for 10 large-cap electronics
     names: 2330, 2317, 2454, 2308, 2382, 3711, 3037, 2303, 2379, 2002
   - computes revenue surprise = YoY − trailing-12-month median(YoY)
   - Spearman-IC each factor's month-M against month-(M+1) surprise per ticker,
     plus a pooled-panel IC across all `(month × ticker)` pairs
3. Pass criteria per factor:
   - `|panel_IC| > 0.05` AND `|t_stat| > 2.0`
4. Verdict: report PASS/FAIL per factor.

### Empirical baseline (sample 2023-01 → 2026-04, n=220 obs/factor)

First run on the production 5-factor panel:

| Factor | Panel IC | t-stat | Verdict |
|---|---:|---:|---|
| `foreign_net` | −0.1720 | −2.58 | ✅ PASS |
| `usdtwd` | +0.0450 | +0.66 | ❌ FAIL |
| `sp500` | −0.0894 | −1.32 | ❌ FAIL |
| `tsm` | −0.1543 | −2.31 | ✅ PASS |
| `sox` | −0.2217 | −3.36 | ✅ PASS |

Three factors pass with **negative** panel IC — meaning a high overnight value
in month M predicts a *lower-than-expected* revenue YoY surprise in month M+1
(contrarian/mean-reversion at the monthly horizon, opposite the same factors'
*daily* IC sign). The fundamentals chain validates the signals, but the
production composite's daily-positive weights may be eating signal.

### When to apply

Run before promoting any alt-data → return signal to production. Specifically:

- New signal added to `ingestion/snapshots/`.
- Weights changed materially in
  `ingestion/snapshots/overnight_signal.py:WEIGHTS` or
  `analysis/backtest_overnight_signal.py:DEFAULT_WEIGHTS`.
- New factor introduced (universe expansion).

If mediation fails, the signal should NOT be deployed even if the direct-
return IC looks great. The production module
`ingestion/snapshots/overnight_signal.py` will eventually carry a
`mediation_passed: bool` flag in its body — that work is deferred to a
follow-up consolidation PR.

### See also

- `analysis/backtest_overnight_signal.py` — the direct-return backtest.
- `scripts/implied_sharpe.py` (§ 8) — the *next* check to run after this one.

---

## § 8 — Implied-Sharpe sanity check

Adopted from rule #2 of the Jay (Two Sigma) 3-rule SOP (epic
[#13](https://github.com/leehao921/TW_ElectricDeviceSupplyChain/issues/13)). Standalone CLI: `scripts/implied_sharpe.py`.

### When this protocol applies

Run after **any** signal-construction change — new weights, new factor added,
new universe, new aggregation horizon. Specifically:

- After running `analysis/backtest_overnight_signal.py` and getting grid-best
  weights — before promoting them to `ingestion/snapshots/overnight_signal.py`.
- Whenever a "diversified composite" claim appears in a report or commit
  message.
- Quarterly even when nothing changed, to detect regime drift in component
  correlations.

### Procedure

1. Run the CLI:
   ```bash
   python3 scripts/implied_sharpe.py --start 2023-01-01 --as-of 2026-04-29
   ```
2. Read the **Pearson correlation matrix** for the 5 overnight components
   (foreign_net / usdtwd / sp500 / tsm / sox). Note pairs within the
   `(sp500, tsm, sox)` US-overnight triplet — they are co-driven by US-session
   risk-on/off and typically have ρ ≈ 0.6-0.8.
3. Read the **Implied Sharpe — Floored cov** table. Each component's value is
   `w_i · IC_i · √252 / sqrt(component_variance_contribution)`.
4. Apply the thresholds (defined as constants in the script):
   - `IS_THRESHOLD = 2.0` — any |implied_sharpe| > 2 → false precision
   - `RHO_FLOOR = 0.5` — any |ρ| < 0.5 within the US triplet gets floored to
     ±0.5 before the implied-Sharpe computation
5. If the verdict is `⚠️ FALSE PRECISION`, **swap weights** to `grid_top[0]`
   from the floored grid output (5%-step grid, sum=1, max single weight ≤ 0.7).
6. Paste the verifier output into the relevant report's *Verification log*.

### Why this matters (Jay's rule)

> "After cov matrix shrinkage and portfolio construction, reverse-calc each
> idea's implied Sharpe in the portfolio. If alt-data shows implied Sharpe = 3,
> you know you trust it too much. Short history + understated correlation =
> false precision. Rule of thumb: if cov says ρ=0.1 between two factors, force
> ρ=0.5 and rerun. Diversification is your only true friend — diversification
> ratio < 1.5 means the portfolio is effectively concentrated."

### Empirical baseline (sample 2023-01-05 → 2026-04-28, 861 days)

The first run on production weights (`foreign_net`=+0.25, `usdtwd`=−0.15,
`sp500`=+0.15, `tsm`=+0.25, `sox`=+0.20) gave:

- ρ(sp500, tsm) = +0.619, ρ(sp500, sox) = +0.792, ρ(tsm, sox) = +0.785 — all
  already ≥ 0.5, no flooring needed.
- Implied Sharpes: foreign_net +0.16, usdtwd +1.10, **sp500 +3.89, tsm +4.69,
  sox +4.26** — three components flag false precision.
- Diversification ratio = 1.49 (≈ 5-factor portfolio behaving like a 2-factor
  portfolio — the US-overnight triplet collapses into a single risk).

The grid-best floored replacement is `(0.00, −0.10, 0.35, 0.35, 0.20)` with
IC +0.5057. **Decision (deferred to a follow-up PR):** whether to swap, given
that dropping foreign_net to 0 trades one symptom (false precision) for another
(losing the 籌碼 read in the body of `news_items`).

### See also

- `analysis/backtest_overnight_signal.py:DEFAULT_WEIGHTS` — current weights.
- `ingestion/snapshots/overnight_signal.py:WEIGHTS` — production weights.
