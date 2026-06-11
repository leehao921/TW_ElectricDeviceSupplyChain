# PMIC EFA v2 — Unit 16 monthly revenue

**Fetch run:** 2026-06-11T01:46:33+00:00 → 2026-06-11T01:52:48+00:00
**Status:** ✓ complete
**Output:** `data/pmic_efa/pmic_monthly_revenue.parquet` (770 rows)

## Goal
≥ 60 months × 10 tickers (PMIC + Power) of `tag=revenue, fp=monthly, val_unit=TWD_M` to feed PMIC EFA v2 + DFM Q2 monitoring. Hard floor enforced in CLI summary is `36` months.

## Sources
- **MOPS** static archive (authoritative): `https://mopsov.twse.com.tw/nas/t21/{sii,otc}/t21sc03_<ROC>_<M>_<suffix>.html`
  - `suffix=0` for domestic issuers, `suffix=1` for foreign issuers (e.g. -KY).
  - Referer: `https://mops.twse.com.tw/mops/web/t05st10_ifrs`.
  - User-Agent: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36`
  - Courtesy: `time.sleep(1.5)` between GETs, exp backoff (1.5, 3.0, 6.0, 12.0)s on security-block.
  - ROC year window scraped: 109..115 (AD 2020..2026).
- **Fallback (not used in this run):** yfinance `Ticker.history()` synthesised monthly revenue. The static MOPS archive returned every month needed, so fallback was unnecessary. If it ever is, provenance must flag the synthesised rows because Close×shares is a market-cap proxy, not the revenue 公開資訊觀測站 reports.

- **Why not `ajax_t05st10_ifrs`?** That endpoint returns only the latest 12 months, and the production `mops.twse.com.tw` host now answers external POSTs with a 686-byte `FOR SECURITY REASONS` block. The static archive on the `mopsov` mirror is the same underlying data exposed via GET. The row contract (year, month, current-month 千元 revenue, mom%, yoy%) matches `scripts/foplp_watchlist.py:52-98` — same parsing intent, durable source.

## Month coverage per ticker

| ticker | name | market | suffix | months | earliest | latest |
|---|---|---|---|---:|---|---|
| 8081 | 致新 | sii | 0 | 77 | 2020-01-31 | 2026-05-31 |
| 6719 | 力智 | sii | 0 | 77 | 2020-01-31 | 2026-05-31 |
| 6138 | 茂達 | otc | 0 | 77 | 2020-01-31 | 2026-05-31 |
| 6415 | 矽力-KY | sii | 1 | 77 | 2020-01-31 | 2026-05-31 |
| 4961 | 天鈺 | sii | 0 | 77 | 2020-01-31 | 2026-05-31 |
| 3588 | 通嘉 | sii | 0 | 77 | 2020-01-31 | 2026-05-31 |
| 3438 | 類比科 | otc | 0 | 77 | 2020-01-31 | 2026-05-31 |
| 2308 | 台達電 | sii | 0 | 77 | 2020-01-31 | 2026-05-31 |
| 6770 | 力積電 | sii | 0 | 77 | 2020-01-31 | 2026-05-31 |
| 2454 | 聯發科 | sii | 0 | 77 | 2020-01-31 | 2026-05-31 |

## Schema
Conforms to `tests/test_ip_database_schema.py` REQUIRED set and `tests/test_pmic_efa_data.py` ALLOWED_TAGS (uses `tag='revenue'` + `fp='monthly'` — ALLOWED_TAGS doesn't whitelist a separate `monthly_revenue` tag yet, so we tag as revenue and distinguish via fp). Columns:
`end | entity_id | entity_name | tag | val | val_unit | fp | form | accn | source_url | source_date`

## Conclusion
✓ complete — min months across all 10 tickers = 77 (target 60, floor 36).
