# PMIC EFA Unit 15 — context provenance

**Fetch run:** 2026-06-10 08:19:07 UTC

## Purpose

Unit 15 supplies the *exogenous variables* for the PMIC sector EFA.
These tickers do not represent pure PMIC names; they provide the
**power / AI server cycle context** and **memory cycle beta** that
let factor analysis separate sector-specific PMIC factors from
macro/cycle factors shared with the broader semiconductor complex.

## Tickers

| ticker | name | role |
|---|---|---|
| 2308 | 台達電 | Global PSU leader — server / AI rack power delivery, liquid cooling |
| 6770 | 力積電 | 8" foundry — niche DRAM/NOR — memory cycle high beta |
| 2454 | 聯發科 | Richtek (2017 absorbed) → PMIC legacy revenue proxy |

## yfinance status

- **2308 台達電** (Delta Electronics — server PSU / cooling / power delivery) — ✓ 9 revenue rows, 2022-12-31 → 2025-12-31
- **6770 力積電** (Powerchip Semi Mfg — 8" foundry, memory cycle beta) — ✓ 9 revenue rows, 2022-12-31 → 2025-12-31
- **2454 聯發科** (MediaTek — Richtek (2017) PMIC legacy proxy) — ✓ 9 revenue rows, 2022-12-31 → 2025-12-31

## WSTS / SIA macro status

- **WSTS_GLOBAL monthly_sales** — ✓ 484 months fetched from `https://www.wsts.org/esraCMS/extension/media/f/WST/7644/WSTS-Historical-Billings-Report-Apr_2026.xlsx`

## Output rows

- `pmic_context_quarterly.parquet`: 135 rows (3 tickers × 5 tags × quarterly+annual)
- `macro_semis_monthly.parquet`: 484 rows

## Schema

Both parquets share the 11-column canonical IP-DB long format:
`end, entity_id, entity_name, tag, val, val_unit, fp, form, accn,
source_url, source_date`. For the macro file, `entity_id =
"WSTS_GLOBAL"` (string identifier, not a stock ticker).

## Caveats

1. **yfinance limit on TW tickers** — Yahoo Finance only surfaces
   ~4-6 quarters of `quarterly_income_stmt` and 4-5 years of annual
   `income_stmt` for Taiwan-listed names. We emit BOTH (each with
   distinct `fp` labels) so the EFA caller can choose granularity.
   The spec target of 20+ quarters per ticker is unattainable from
   yfinance alone; reaching that would require TWSE MOPS / official
   filings ingestion (out of scope for this unit).
2. **2454 (MediaTek) PMIC carve-out risk** — MediaTek absorbed
   Richtek (立錡, the dominant standalone TW PMIC name) in 2017.
   Since then there has been no segment disclosure; using MediaTek
   topline / margins as PMIC proxies will overweight the broader
   SoC cycle. EFA downstream should regress against the WSTS macro
   row to absorb the SoC-cycle component before reading any
   PMIC-specific signal from 2454.
3. **WSTS / SIA freshness** — the Historical Billings Report XLSX is
   refreshed monthly. The download URL embeds the publication month
   (e.g. `…-Apr_2026.xlsx`). The script first tries the most recent
   guesses, then scrapes the press page link as a fallback.

## Warnings / errors

- (none — clean run)
