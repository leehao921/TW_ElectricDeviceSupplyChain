# ARM Holdings — IP Database Provenance

**Fetched:** 2026-06-04 13:05 UTC
**Entity (per EDGAR):** ARM HOLDINGS PLC /UK
**CIK:** 0001973239
**Source:** [https://data.sec.gov/api/xbrl/companyfacts/CIK0001973239.json](https://data.sec.gov/api/xbrl/companyfacts/CIK0001973239.json)
**Reporting standard:** IFRS primary, also files US GAAP-tagged XBRL under foreign-private-issuer rules (20-F annual + 6-K interim).

## Source viability

| Dataset | Status | Notes |
|---|---|---|
| RPO (Remaining Performance Obligation) | OK | Native RPO tag `RevenueRemainingPerformanceObligation` present with 11 rows. |
| Revenue | OK | Tags captured: RevenueFromContractWithCustomerExcludingAssessedTax (16 rows) |

## Forms accepted

`['10-K', '10-Q', '20-F', '6-K']` — ARM is a foreign private issuer so its annual is **20-F** and interim is **6-K** (not 10-K/10-Q used by US-domestic registrants). Filtering to only 10-K/10-Q would yield ZERO rows for ARM.

## Known caveats

- **IFRS vs US GAAP**: ARM's primary financial statements are IFRS. EDGAR XBRL is filed in IFRS Inline XBRL inside 20-F; supplementary us-gaap tags reflect the same numbers translated to US GAAP concepts where applicable.
- **Fiscal year**: ARM FY ends 31 March. `fp=FY` rows correspond to 20-F annual filings at end-March.
- **RPO definition**: Under IFRS 15 / ASC 606, RPO = aggregate transaction price allocated to performance obligations unsatisfied at period end. ARM discloses this in 20-F and quarterly 6-K MD&A.
- **First period**: 2023-09-30 (post-IPO; ARM relisted on NASDAQ Sep 2023).

## Output files

- `data/ip_database/arm_rpo.parquet` (11 rows)
- `data/ip_database/arm_revenue.parquet` (16 rows)

## Reproduction

```bash
python3 scripts/fetch_arm_rpo.py
```
