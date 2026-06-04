# CEVA Inc. — IP database provenance

- **Source:** SEC EDGAR XBRL companyfacts
- **URL:** https://data.sec.gov/api/xbrl/companyfacts/CIK0001173489.json
- **CIK:** 0001173489 (CEVA Inc., NASDAQ: CEVA)
- **Fetched:** 2026-06-04 13:00:59 UTC
- **Script:** scripts/fetch_ceva_rpo.py

## Source validity

| Series | Status |
|---|---|
| RPO (`RevenueRemainingPerformanceObligation` family) | OK — tag `RevenueRemainingPerformanceObligation`, 1 rows |
| Revenue (multi-tag) | OK — tags ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'RevenueFromContractWithCustomerIncludingAssessedTax', 'LicensesRevenue', 'LicenseAndServicesRevenue', 'RoyaltyRevenue'], 141 rows total |

RPO candidate tags tried (in order): ['RevenueRemainingPerformanceObligation', 'RevenueRemainingPerformanceObligations', 'RemainingPerformanceObligation', 'ContractWithCustomerLiability']

Revenue candidate tags tried (in order): ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'RevenueFromContractWithCustomerIncludingAssessedTax', 'SalesRevenueNet', 'LicensesRevenue', 'LicenseAndServicesRevenue', 'RoyaltyRevenue']

## Diagnostic — every us-gaap tag containing revenue/license/royalty/sales

  - `CostOfRevenue`  n=195
  - `OtherComprehensiveIncomeLossAvailableForSaleSecuritiesAdjustmentBeforeTax`  n=174
  - `AvailableForSaleSecuritiesGrossRealizedLosses`  n=119
  - `AvailableForSaleSecuritiesGrossRealizedGains`  n=107
  - `ProceedsFromMaturitiesPrepaymentsAndCallsOfAvailableForSaleSecurities`  n=99
  - `RevenueFromContractWithCustomerIncludingAssessedTax`  n=94
  - `PaymentsToAcquireAvailableForSaleSecurities`  n=92
  - `Revenues`  n=91
  - `RoyaltyRevenue`  n=91
  - `AvailableForSaleSecuritiesGrossRealizedGainLossNet`  n=90
  - `ProceedsFromSaleOfAvailableForSaleSecurities`  n=90
  - `AvailableForSaleSecuritiesDebtSecuritiesCurrent`  n=80
  - `AvailableForSaleSecuritiesContinuousUnrealizedLossPositionLessThanTwelveMonthsFairValue`  n=74
  - `AvailableForSaleSecuritiesContinuousUnrealizedLossPositionTwelveMonthsOrLongerFairValue`  n=72
  - `LicensesRevenue`  n=70
  - `IncreaseDecreaseInDeferredRevenue`  n=67
  - `DeferredRevenueCurrent`  n=60
  - `AvailableForSaleSecuritiesContinuousUnrealizedLossPosition12MonthsOrLongerAccumulatedLoss`  n=56
  - `AvailableForSaleSecuritiesContinuousUnrealizedLossPositionLessThan12MonthsAccumulatedLoss`  n=56
  - `AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearAmortizedCost`  n=53
  - `AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearFairValue`  n=53
  - `ContractWithCustomerLiabilityRevenueRecognized`  n=44
  - `PaymentsToAcquireAvailableForSaleSecuritiesDebt`  n=43
  - `ProceedsFromSaleOfAvailableForSaleSecuritiesDebt`  n=43
  - `AvailableForSaleSecuritiesDebtMaturitiesRollingYearTwoThroughFiveAmortizedCostBasis`  n=33

## Notes

- CEVA is a small-cap DSP / connectivity IP licensor (~$100M annual revenue).
  Small filers often do **not** disclose `RevenueRemainingPerformanceObligation`
  as a discrete us-gaap concept; instead RPO context may be narrative in the
  10-K/10-Q text. Treat missing-RPO as **expected**, not an error.
- `ContractWithCustomerLiability` (deferred revenue) is included as a fallback
  in the RPO tag list — it is NOT RPO but the closest balance-sheet proxy.
- Only `10-Q` and `10-K` forms are retained. Dedup by `(end, fp)` keeps the
  latest-filed value so post-filing restatements supersede originals.
