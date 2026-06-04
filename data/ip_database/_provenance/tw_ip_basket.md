# TW IP / ASIC service basket — provenance

**Fetch run:** 2026-06-04 13:04:09 UTC

## Tickers

| ticker | name | role |
|---|---|---|
| 3529 | 力旺 | NVM IP (OTP/MTP) |
| 6531 | 愛普 | 客製化 DRAM IP |
| 6533 | 晶心科 | RISC-V CPU core IP |
| 3443 | 創意 | TSMC ASIC service |
| 3661 | 世芯-KY | Amazon Trainium ASIC service |

## Sources

- **yfinance** — quarterly_financials + .info snapshot. Suffix .TW preferred, .TWO fallback.
- **trading-timescaledb** — `institutional_stock` table on localhost:5432/tmf_market_data; 90-day cumulative foreign/trust/total net.

## Output rows

- `tw_ip_basket_quarterly.parquet`: 198 rows
- `tw_ip_basket_flow.parquet`: 15 rows

## Warnings / errors

- (none — clean run)
