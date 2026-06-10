# PMIC EFA Unit 13 — TW PMIC tail-3 (provenance)

**Fetch run:** 2026-06-10 08:33:15 UTC

## Tickers

| ticker | name | role | yfinance suffix |
|---|---|---|---|
| 4961 | 天鈺 | 中小型 PMIC + display driver + touch | .TW |
| 3588 | 通嘉 | 中小型 PMIC (Leadtrend) | .TW |
| 3438 | 類比科 | 純 analog IC (Analog Integrations, 上櫃) | .TWO |

> 注意: 用戶 prompt 寫 "3556" 是 typo (3556 = 禾瑞亞 touch IC). 通嘉真正 ticker = 3588 已驗證.

## Sources

- **MOPS (mopsov.twse.com.tw) `t164sb04`** — primary. ROC 108..115 Q1..Q4. Q1 standalone, Q2/Q3 standalone single-quarter column (amount-col idx 0), Q4 single-quarter derived as (annual − 9M cumulative).
- **yfinance** — fills any gap and provides most-recent quarters. MOPS preferred when both available (`_dedup_prefer_mops`).

## Tags emitted

- `revenue` (TWD_M)
- `gross_margin` (pct)
- `operating_margin` (pct)
- `net_margin` (pct)
- `r_and_d_ratio` (pct)

## Coverage

| ticker | revenue quarters | min end | max end |
|---|---|---|---|
| 3438 | 29 | 2019-03-31 | 2026-03-31 |
| 3588 | 27 | 2019-03-31 | 2026-03-31 |
| 4961 | 29 | 2019-03-31 | 2026-03-31 |

## Warnings / errors

- (none — clean run)

## Floor check (>= 20 quarters per ticker)

- PASS — every ticker has >= 20 revenue quarters.
