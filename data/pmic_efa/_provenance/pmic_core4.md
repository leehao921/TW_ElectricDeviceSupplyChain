# PMIC EFA — core 4 quarterly fundamentals (Unit 12)

**Fetch run:** 2026-06-10 08:54:18 UTC
**Status:** ⚠️ partial

## Goal

Provide ≥ 20 quarters × 4 tickers of revenue + 4 margins
so the PMIC EFA coordinator can run KMO + Bartlett + parallel analysis
+ Varimax / Promax rotation with adequate N.

## Tickers (Golden Rule #2 verified)

| ticker | name | role |
|---|---|---|
| 8081 | 致新 | GMT — 純 PMIC fabless |
| 6719 | 力智 | uPI — 華碩集團 PMIC + GaN MOSFET |
| 6138 | 茂達 | Anpec — PMIC + 馬達 driver; 2025/10 國巨入股 21.4% |
| 6415 | 矽力-KY | Silergy — 開曼註冊 / 杭州總部 |

## Sources

- **MOPS** (authoritative): https://mopsov.twse.com.tw/mops/web/ajax_t164sb04
  - POST `co_id=<ticker>&year=<ROC>&season=<01..04>&TYPEK=all`
  - Referer: https://mops.twse.com.tw/mops/web/t164sb04
  - User-Agent: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36`
  - Courtesy: `time.sleep(1.5)` between calls.
  - Years scraped: ROC 109..114 (AD 2020..2025).
- **yfinance** (best-effort supplement): `Ticker("<id>.TW").quarterly_income_stmt`. Typically returns 5-6 most recent quarters; used to backfill the very latest
  quarter if MOPS hasn't published it yet.

## Quarter coverage per ticker (revenue series)

| ticker | name | yfinance Q's | MOPS Q's | merged Q's | earliest | latest |
|---|---|---:|---:|---:|---|---|
| 8081 | 致新 | 5 | 24 | 24 | 2020-03-31 | 2025-12-31 |
| 6719 | 力智 | 5 | 18 | 18 | 2021-09-30 | 2025-12-31 |
| 6138 | 茂達 | 5 | 24 | 24 | 2020-03-31 | 2025-12-31 |
| 6415 | 矽力-KY | 5 | 24 | 24 | 2020-03-31 | 2025-12-31 |

## Methodology — single-quarter derivation

MOPS publishes cumulative year-to-date figures. For each (ticker, year)
we scrape seasons 1..4 (Q1, H1, 9M, FY) and difference:

- `Q1_single = Q1_cumulative`
- `Q2_single = H1_cumulative − Q1_cumulative`
- `Q3_single = 9M_cumulative − H1_cumulative`
- `Q4_single = FY_cumulative − 9M_cumulative`

Where any required prior-cumulative is missing, that single-quarter is
dropped (we do NOT fabricate). Margins are computed per single quarter:
ratio of single-quarter line item to single-quarter revenue × 100.

## Output schema (canonical)

| col | type | notes |
|---|---|---|
| end | datetime64 | quarter-end date |
| entity_id | str | 4-digit ticker |
| entity_name | str | TC name from filename |
| tag | str | revenue / gross_margin / operating_margin / net_margin / r_and_d_ratio |
| val | float64 | numeric (negative allowed for margins) |
| val_unit | str | TWD_M or pct |
| fp | str | Q1 / Q2 / Q3 / Q4 |
| form | str | mops or yfinance |
| accn | str | provenance accession |
| source_url | str | URL of source page |
| source_date | datetime64 | when fetched |

## Warnings / errors

- (none — clean run)

## Conclusion: ⚠️ partial

All 4 tickers ≥ 18 quarters; one or more under target 20. EFA proceeds but flag in downstream report.