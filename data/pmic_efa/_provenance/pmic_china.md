# PMIC EFA — China comparables (Unit 14)

**Fetched:** 2026-06-10 08:23 UTC
**Tickers:** 300661.SZ (SG Micro), 688484.SS (SouthChip)
**Output:** `data/pmic_efa/pmic_china_quarterly.parquet`

## Source viability summary

| ticker | name | actual Qs (CNY rev) | synth Qs | total Qs | range | status |
|---|---|---|---|---|---|---|
| 300661.SZ | SG Micro | 38 | 0 | 38 | 2015-03-31 → 2026-03-31 | OK |
| 688484.SS | SouthChip | 17 | 0 | 17 | 2022-03-31 → 2026-03-31 | PARTIAL |

`actual Qs` counts only `tag="revenue", val_unit="CNY_M", form="quarterly_actual"`
rows. `synth Qs` counts revenue rows with `form="annual_quarterized"`. In this
build all revenue rows are derived from Eastmoney's YTD figures (real data,
back-differenced into single quarters) so the synth column for revenue is 0.
The synthesized rows we *do* emit are `operating_margin` and `r_and_d_ratio`
for older quarters where yfinance has no detail — those are tracked in the
"rows by (ticker, tag, form)" table printed by the script.

## Sources

### Primary: Eastmoney `RPT_LICO_FN_CPD`
- Endpoint: `https://datacenter-web.eastmoney.com/api/data/v1/get`
- Returns YTD cumulative revenue (TOTAL_OPERATE_INCOME), parent net profit
  (PARENT_NETPROFIT) and gross margin pct (XSMLL) per period end.
- Coverage: SG Micro 2012 → 2026-Q1 (45 YTD points); SouthChip 2019 → 2026-Q1
  (21 YTD points; firm IPO'd 2022-10).
- We back-difference YTD → single quarter inside each fiscal year.
- Direct fields used: revenue (CNY_M), net_margin (derived from NI/REV),
  gross_margin (XSMLL pct).

### Supplementary: yfinance
- `quarterly_income_stmt`: covers the most recent ~5 quarters with full
  income statement detail (Operating Income, R&D). Used for `operating_margin`
  and `r_and_d_ratio` `quarterly_actual` rows.
- `income_stmt` (annual): FY 2022 → FY 2025 used to synthesize older
  `operating_margin` and `r_and_d_ratio` rows. These carry
  `form="annual_quarterized"`.

⚠️  **Quarterization risk for operating_margin / r_and_d_ratio synthesized
rows**: We project the *annual ratio* onto every unfilled quarter within
that fiscal year. This assumes margins don't swing seasonally — a common
simplification but not exact. China PMICs do have Q1/Q4 margin tilt from
inventory cycle and operating-leverage effects, so use these rows for trend
work, not for absolute single-quarter comparisons. Consumers can filter:

```python
df = df[df.form == "quarterly_actual"]
```

### FX
USD revenue rows (`tag="val_usd"`, `val_unit="USD_M"`) are computed as
`revenue_CNY_M / USD_per_CNY_mid_at_quarter_end`. The mid rate source:

> yfinance Ticker('USDCNY=X').history(period='max', interval='3mo'), Close column, mapped to nearest quarter end ≤ FX bar date (forward fill). 'max' is used instead of '5y' because Eastmoney revenue history extends back to 2015 for SG Micro; a 5y window would force every pre-2021 quarter to a stale rate.

If a quarter sits before the earliest FX bar, we forward-fill with the
earliest known rate (logged in stderr at fetch time).

### Yahoo symbol mapping note
688484 is on the Shanghai STAR (科創板) board. The unit spec listed
`688484.SH`, but Yahoo returns 404 on `.SH`; the correct Yahoo suffix is
**`.SS`**. We use `.SS` as `entity_id` to preserve a direct round-trip
with yfinance.

### 688484.SS coverage
SouthChip IPO'd on the STAR board in October 2022. Eastmoney has 2019-Q4,
2020-Q4, 2021-Q3, 2021-Q4, then a complete 2022-onwards record. The e2e
check does not enforce ≥ 18 on this ticker; expected count is ~15–18
depending on how many YTD gaps exist before IPO.

## Output rows per quarter
Each quarter emits up to 6 canonical rows: revenue (CNY_M), val_usd (USD_M),
gross_margin (pct), operating_margin (pct), net_margin (pct),
r_and_d_ratio (pct).

## Reproduction
```bash
python3 scripts/fetch_pmic_china.py
```
