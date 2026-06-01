# Asia Market Panel — Ingestion Audit (2026-05-15)

**Window:** 2023-05-15 → 2026-05-15 · **Anchor:** ^TWII (TAIEX) — TXF tracker proxy

## Data summary — indices

| Symbol | yfinance ticker | Rows | First | Last | Missing |
|---|---|---:|---|---|---:|
| AXJO | ^AXJO | 762 | 2023-05-15 | 2026-05-15 | 0 |
| CHINEXT | 159915.SZ (ChiNext ETF proxy) | 726 | 2023-05-15 | 2026-05-15 | 0 |
| CSI300 | 000300.SS | 727 | 2023-05-15 | 2026-05-15 | 0 |
| HSI | ^HSI | 737 | 2023-05-15 | 2026-05-15 | 0 |
| KQ11 | ^KQ11 | 731 | 2023-05-15 | 2026-05-15 | 0 |
| KS11 | ^KS11 | 731 | 2023-05-15 | 2026-05-15 | 0 |
| N225 | ^N225 | 734 | 2023-05-15 | 2026-05-15 | 0 |
| NSEI | ^NSEI | 741 | 2023-05-15 | 2026-05-15 | 0 |
| SSE | 000001.SS | 727 | 2023-05-15 | 2026-05-15 | 0 |
| STI | ^STI | 755 | 2023-05-15 | 2026-05-15 | 0 |
| SZSE | 399001.SZ | 727 | 2023-05-15 | 2026-05-15 | 0 |
| TPX | 1306.T (TOPIX ETF proxy) | 733 | 2023-05-15 | 2026-05-15 | 0 |
| TWII | ^TWII | 729 | 2023-05-15 | 2026-05-15 | 0 |

## Data summary — FX

| Pair | yfinance ticker | Rows | First | Last | Missing |
|---|---|---:|---|---|---:|
| AUDJPY | AUDJPY=X | 780 | 2023-05-15 | 2026-05-15 | 0 |
| AUDUSD | AUDUSD=X | 780 | 2023-05-15 | 2026-05-15 | 0 |
| DXY | DX-Y.NYB | 756 | 2023-05-15 | 2026-05-15 | 0 |
| USDCNH | CNY=X (onshore Yuan proxy) | 780 | 2023-05-15 | 2026-05-15 | 0 |
| USDHKD | HKD=X | 780 | 2023-05-15 | 2026-05-15 | 0 |
| USDINR | INR=X | 780 | 2023-05-15 | 2026-05-15 | 0 |
| USDJPY | JPY=X | 780 | 2023-05-15 | 2026-05-15 | 0 |
| USDKRW | KRW=X | 780 | 2023-05-15 | 2026-05-15 | 0 |
| USDSGD | SGD=X | 780 | 2023-05-15 | 2026-05-15 | 0 |
| USDTWD | TWD=X | 780 | 2023-05-15 | 2026-05-15 | 0 |

## Outliers flagged (|z| > 5, kept in dataset)

Per project SOP: outliers are flagged (`outlier_flag=TRUE`) but never deleted. Whitelist: 2024-08-05 yen carry crash is REAL (preserved).

| Date (TWT) | Symbol | Close | Log-ret | z | Note |
|---|---|---:|---:|---:|---|
| 2025-05-07 | USDTWD | 29.1600 | -0.0516 | -10.86 | TWD policy-flip rally (real) |
| 2025-04-07 | STI | 3540.5000 | -0.0775 | -10.64 | Trump tariff selloff (real) |
| 2025-05-06 | USDTWD | 30.7043 | -0.0448 | -9.43 | TWD policy-flip rally (real) |
| 2025-04-07 | HSI | 19828.3008 | -0.1418 | -9.41 | Trump tariff selloff (real) |
| 2025-04-08 | AUDUSD | 0.5988 | -0.0546 | -9.01 | Trump tariff selloff (real) |
| 2025-04-08 | AUDJPY | 87.0540 | -0.0602 | -8.92 | Trump tariff selloff (real) |
| 2024-08-05 | TPX | 234.9500 | -0.1145 | -8.81 | yen carry crash (real, whitelisted) |
| 2024-09-30 | CHINEXT | 2.2320 | +0.1823 | +8.69 |  |
| 2024-10-08 | CHINEXT | 2.6780 | +0.1822 | +8.68 |  |
| 2024-08-05 | N225 | 31458.4199 | -0.1323 | -8.67 | yen carry crash (real, whitelisted) |
| 2024-10-09 | CHINEXT | 2.2420 | -0.1777 | -8.54 |  |
| 2026-03-04 | KQ11 | 978.4400 | -0.1508 | -8.39 | Korea AI/EV selloff (real) |
| 2026-03-04 | KS11 | 5093.5400 | -0.1285 | -7.86 | Korea AI/EV selloff (real) |
| 2024-09-30 | SSE | 3336.4971 | +0.0776 | +7.77 |  |
| 2025-04-07 | SSE | 3096.5759 | -0.0763 | -7.71 | Trump tariff selloff (real) |
| 2023-11-04 | USDINR | 83.2473 | -0.0231 | -7.69 |  |
| 2025-04-07 | TWII | 19232.3496 | -0.1020 | -7.57 | Trump tariff selloff (real) |
| 2024-06-04 | NSEI | 21884.5000 | -0.0611 | -7.47 |  |
| 2024-09-30 | CSI300 | 4017.8501 | +0.0814 | +7.46 |  |
| 2023-11-03 | USDINR | 85.1940 | +0.0228 | +7.44 |  |
| 2026-03-05 | KQ11 | 1116.4100 | +0.1319 | +7.29 | rebound (real) |
| 2026-04-14 | USDINR | 94.5088 | +0.0218 | +7.13 |  |
| 2025-04-10 | STI | 3577.8301 | +0.0528 | +7.12 | rebound from tariff selloff (real) |
| 2025-04-07 | SZSE | 9364.5000 | -0.1016 | -7.00 | Trump tariff selloff (real) |
| 2024-09-30 | SZSE | 10529.7598 | +0.1014 | +6.93 |  |
| 2024-10-09 | SSE | 3258.8579 | -0.0685 | -6.92 |  |
| 2024-10-09 | CSI300 | 3955.9800 | -0.0731 | -6.75 |  |
| 2025-04-07 | CSI300 | 3589.4399 | -0.0731 | -6.74 | Trump tariff selloff (real) |
| 2024-08-05 | KQ11 | 691.2800 | -0.1199 | -6.68 | yen carry crash (real, whitelisted) |
| 2024-10-08 | HSI | 20926.7891 | -0.0988 | -6.56 |  |
| 2024-08-05 | TWII | 19830.8809 | -0.0872 | -6.48 | yen carry crash (real, whitelisted) |
| 2025-04-07 | CHINEXT | 1.7750 | -0.1328 | -6.39 | Trump tariff selloff (real) |
| 2025-04-10 | TWII | 19000.0293 | +0.0884 | +6.38 | rebound from tariff selloff (real) |
| 2026-04-16 | USDINR | 93.1654 | -0.0189 | -6.31 |  |
| 2024-08-06 | N225 | 34675.4609 | +0.0974 | +6.26 |  |
| 2025-04-07 | TPX | 243.2500 | -0.0792 | -6.12 | Trump tariff selloff (real) |
| 2025-04-10 | TPX | 270.1500 | +0.0807 | +6.11 | rebound from tariff selloff (real) |
| 2023-10-31 | USDCNH | 7.1587 | -0.0216 | -6.00 |  |
| 2024-10-08 | SZSE | 11495.0996 | +0.0877 | +5.99 |  |
| 2023-11-01 | USDCNH | 7.3121 | +0.0212 | +5.91 |  |
| 2024-10-09 | SZSE | 10557.8096 | -0.0851 | -5.87 |  |
| 2025-04-11 | AUDJPY | 90.3950 | +0.0401 | +5.87 |  |
| 2025-05-08 | USDTWD | 29.9776 | +0.0277 | +5.81 |  |
| 2025-04-10 | AXJO | 7709.6001 | +0.0444 | +5.79 | rebound from tariff selloff (real) |
| 2024-08-05 | STI | 3243.6699 | -0.0416 | -5.75 | yen carry crash (real, whitelisted) |
| 2025-04-07 | AXJO | 7343.2998 | -0.0432 | -5.70 | Trump tariff selloff (real) |
| 2024-08-05 | KS11 | 2441.5500 | -0.0918 | -5.64 | yen carry crash (real, whitelisted) |
| 2025-04-10 | N225 | 34609.0000 | +0.0874 | +5.61 | rebound from tariff selloff (real) |
| 2026-03-05 | KS11 | 5583.8999 | +0.0919 | +5.47 | rebound (real) |
| 2023-10-18 | USDCNH | 7.3093 | +0.0195 | +5.43 |  |
| 2025-04-07 | N225 | 31136.5801 | -0.0815 | -5.36 | Trump tariff selloff (real) |
| 2025-08-21 | USDHKD | 7.7995 | -0.0026 | -5.29 |  |
| 2026-02-04 | USDINR | 90.2456 | -0.0158 | -5.29 |  |
| 2024-10-08 | CSI300 | 4256.1001 | +0.0576 | +5.27 |  |
| 2023-10-03 | USDCNH | 7.1636 | -0.0188 | -5.24 |  |
| 2024-11-08 | USDSGD | 1.3332 | +0.0150 | +5.16 |  |
| 2023-10-17 | USDCNH | 7.1681 | -0.0184 | -5.12 |  |
| 2023-09-06 | USDCNH | 7.2719 | +0.0183 | +5.10 |  |

## Cross-source check (Stooq)

Stooq cross-source backfill was NOT executed (yfinance returned ≥725 rows for every symbol, exceeding the plan's 600-day minimum). Proxy tickers (1306.T for TPX, 159915.SZ for ChiNext, CNY=X for USDCNH) were used where yfinance lost the original feed; a 10:1 reverse split on 1306.T (2026-03-30) was forward-adjusted in the validator before computing returns.

## FX timezone diagnostic

All FX pairs anchored to **NY 17:00 ET** (conventional global FX daily close), then converted to **Asia/Taipei** for storage (yields TWT ~05:00–06:00 next day). `source_close_tz='NY17ET'` recorded on every row.

Index closes are anchored to the local exchange close time, then converted to TWT:

| Symbol | Local close | → TWT |
|---|---|---|
| N225, TPX | 15:00 JST | 14:00 |
| KS11, KQ11 | 15:30 KST | 14:30 |
| TWII | 13:30 TWT | 13:30 |
| SSE, CSI300, SZSE, CHINEXT | 15:00 CST | 15:00 |
| HSI | 16:00 HKT | 16:00 |
| STI | 17:00 SGT | 17:00 |
| NSEI | 15:30 IST | 18:00 |
| AXJO | 16:00 AEST/AEDT | DST-aware via pytz |

## Files produced

| Path | Purpose |
|---|---|
| `data/raw/taiex_3y.parquet` | ^TWII 3y OHLCV (Phase 2) |
| `data/raw/asia_indices_raw.parquet` | 13 indices, raw yfinance |
| `data/raw/asia_fx_raw.parquet` | 10 FX pairs, raw yfinance |
| `data/asia_market_panel.parquet` | Wide daily closes, TWT-indexed (941 dates × 23 cols) |
| `data/outliers_audit.parquet` | 58 outlier rows flagged (39 idx + 19 fx) |
| `data/cov_3y.parquet` / `data/corr_3y.parquet` | Static 3y matrices |
| `data/rolling_corr_twii.parquet` | 60/90/252d rolling corr vs TWII |
| `data/twii_dxy_beta.parquet` | Full + rolling 60d β |
| `data/regime_shifts.parquet` | 90 regime-shift events (|Δcorr_5d|>0.3) |
| `data/twii_corr_ranked.parquet` | TWII top-10 ± correlations |
| TimescaleDB `asia_index_daily` | 9,560 rows (13 symbols) |
| TimescaleDB `fx_daily` | 7,776 rows (10 pairs) |
| TimescaleDB `market_news` | 416 rows, 2026-01-05 → 2026-05-15 |