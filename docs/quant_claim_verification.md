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
