# RMBS — Rambus Inc XBRL provenance

- **Source**: SEC EDGAR companyfacts API
- **URL**: https://data.sec.gov/api/xbrl/companyfacts/CIK0000917273.json
- **CIK**: 0000917273
- **Entity**: RAMBUS INC
- **Fetched at**: 2026-06-04T13:01:17.257223
- **Forms kept**: 10-Q, 10-K (dedup by `(end, fp)` keeping latest filing — final restatement wins)

## Tag availability

| Concept | Tag used | Rows | Date range | Status |
|---|---|---|---|---|
| RPO | `RevenueRemainingPerformanceObligation` | 33 | 2018-03-31 → 2026-03-31 | ✓ |
| Total revenue (primary) | `RevenueFromContractWithCustomerIncludingAssessedTax` | 48 | 2016-12-31 → 2026-03-31 | ✓ |
| Royalty segment | `RoyaltyRevenue` | 44 | 2008-12-31 → 2018-06-30 | ✓ |

## Source validity (✓/✗)

- **SEC EDGAR companyfacts** — ✓ valid, public, free; standard 10-Q/10-K XBRL feed.
- **RPO disclosure** — ✓ Rambus discloses `RevenueRemainingPerformanceObligation` from
  the ASC 606 adoption (FY18+). Earlier filings do not have RPO rows.
- **Total revenue** — ✓ usable but tag-version drift: Rambus stopped tagging
  `SalesRevenueNet` mid-2018 and switched to
  `RevenueFromContractWithCustomerIncludingAssessedTax` (the ASC 606 concept). The
  primary tag is auto-selected as whichever has the most recent `end` date so the
  headline series is always current. The full revenue parquet keeps every tag in long
  format (distinguished by `tag` column) so the pre-2018 history is still available.
- **Royalty segment** — ⚠ PARTIAL: `RoyaltyRevenue` ran through Q2-2018 then stopped at
  the us-gaap concept level. After ASC 606 Rambus reports royalty inside the segment
  footnote as a custom extension (`rmbs:RoyaltyRevenue` or
  `srt:ProductOrServiceAxis = RoyaltyMember`), which is NOT in companyfacts. For
  current-quarter royalty splits, parse the segment table from the 10-Q filing HTML
  directly. This script captures the historical royalty trend through 2018 only.

## Tags considered but rejected

- `RoyaltyIncomeNonoperating` — Rambus does not file this concept (royalty is
  operating revenue for the company, not non-operating income).
- `Revenues` — not used by Rambus.
- `RevenueFromContractWithCustomerExcludingAssessedTax` — Rambus uses the
  "Including" variant. The script falls through cleanly.

## Output schema (canonical)

| Column | Type | Notes |
|---|---|---|
| end | datetime64 | period-end |
| entity_id | str | "0000917273" |
| entity_name | str | "Rambus" |
| tag | str | XBRL concept |
| val | float64 | USD |
| val_unit | str | "USD" |
| fp | str | Q1/Q2/Q3/FY |
| form | str | 10-Q / 10-K |
| accn | str | SEC accession |
| source_url | str | this companyfacts URL |
| source_date | datetime64 | fetch timestamp (UTC) |
