---
type: concept
status: active
last_updated: 2026-05-15
related: [TXF.md, DXY.md]
tags: [covariance, panel, asia]
---

# Asia Market Covariance Panel

**Built 2026-05-15.** Persistent 3-year (2023-05-15 → 2026-05-15) daily panel of 13 Asian indices + 10 FX pairs, TXF-centric.

## Data scope

- **13 indices** (Tier 1): N225, TPX (1306.T proxy), KS11, KQ11, **TWII** (anchor), SSE, CSI300, SZSE, CHINEXT (159915.SZ proxy), HSI, STI, NSEI, AXJO
- **10 FX:** DXY, USD/JPY, USD/KRW, USD/TWD, USD/CNH (CNY=X proxy), USD/HKD, USD/SGD, USD/INR, AUD/USD, AUD/JPY
- **9,560 index-day rows + 7,776 FX-day rows + 416 news rows** in TimescaleDB

## Storage

| Layer | Path |
|---|---|
| Raw cache | `data/raw/asia_indices_raw.parquet`, `data/raw/asia_fx_raw.parquet` |
| Cleaned panel | `data/asia_market_panel.parquet` |
| Returns | `data/asia_returns.parquet` |
| Covariance (3y) | `data/cov_3y.parquet` |
| Correlation (3y) | `data/corr_3y.parquet` |
| Rolling 60/90/252d corr (TWII anchor) | `data/rolling_corr_twii.parquet` |
| TWII–DXY β series | `data/twii_dxy_beta.parquet` |
| Regime shifts | `data/regime_shifts.parquet` |
| DB tables | `asia_index_daily`, `fx_daily`, `market_news` |

## Top 10 TWII correlations (full 3y)

```
KS11      +0.634  ← KOSPI 最大同向
N225      +0.615
KQ11      +0.555
TPX       +0.552
AXJO      +0.547
STI       +0.486
HSI       +0.370
NSEI      +0.314
SZSE      +0.244
SSE       +0.239
```

## Negative correlations (FX side)

```
DXY       −0.113  ← 唯一稍微顯著
USDSGD    −0.066
USDINR    −0.059
USDJPY    −0.043
USDKRW    −0.027
USDTWD    −0.017  ← 近零 (央行干預)
USDHKD    −0.015  (peg)
USDCNH    −0.008
AUDJPY    +0.014
AUDUSD    +0.058
```

## TXF–DXY β (regression r_TWII = α + β · r_DXY)

| Window | β | 含義 |
|---|---:|---|
| Full 3y | **−0.37** | 平常 |
| **Last 60d (rolling)** | **−1.47** | **regime shift 4× 陡升** |

**Last 5 days 60d β:**
```
5/13: −1.437
5/14: −1.346
5/15: −1.431
5/16: −1.468  ← 最新
Full: −0.369
```

## Regime shifts detected

90 events flagged across all pairs (>0.3 corr-shift over 5d window). Most concentrated in 2024-08 (yen carry unwind) and 2026-05 (current PPI/Iran shock window).

## Update workflow

Daily refresh planned (Phase 8 pending project):
```
0 18 * * 1-5 python3 scripts/fetch_asia_panel.py && \
             python3 scripts/validate_asia_panel.py && \
             python3 scripts/compute_asia_covariance.py && \
             python3 analysis/dashboard_builder.py
```

## Dashboard

- HTML: `analysis/dashboards/latest/index.html` (4 charts + news sidebar)
- 4 figures: TXF candlestick + news annotations, 60d rolling-corr strip, cov heatmap, basis diag
