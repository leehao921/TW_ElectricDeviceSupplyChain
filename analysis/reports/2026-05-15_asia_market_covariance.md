# Asia Market Covariance — TXF-Anchored (2026-05-15)

**Window:** 2023-05-15 → 2026-05-15 (939 daily log-return observations) · **Anchor:** ^TWII (TAIEX) — TXF cash tracker

## 1. Static 3y correlation — compact (anchor row)

Correlation of every instrument's daily log-return with TWII over the full 3y window:

| Symbol | corr(TWII) |
|---|---:|
| KS11 | +0.6345 |
| N225 | +0.6151 |
| KQ11 | +0.5555 |
| TPX | +0.5519 |
| AXJO | +0.5470 |
| STI | +0.4862 |
| HSI | +0.3698 |
| NSEI | +0.3142 |
| SZSE | +0.2435 |
| SSE | +0.2388 |
| CSI300 | +0.2334 |
| CHINEXT | +0.1992 |
| AUDUSD | +0.0583 |
| AUDJPY | +0.0142 |
| USDCNH | -0.0078 |
| USDHKD | -0.0152 |
| USDTWD | -0.0172 |
| USDKRW | -0.0268 |
| USDJPY | -0.0428 |
| USDINR | -0.0586 |
| USDSGD | -0.0664 |
| DXY | -0.1134 |

## 2. TWII top 10 positive / negative correlations

| Rank | Symbol | 3y corr |
|---|---|---:|
| +1 | KS11 | +0.6345 |
| +2 | N225 | +0.6151 |
| +3 | KQ11 | +0.5555 |
| +4 | TPX | +0.5519 |
| +5 | AXJO | +0.5470 |
| +6 | STI | +0.4862 |
| +7 | HSI | +0.3698 |
| +8 | NSEI | +0.3142 |
| +9 | SZSE | +0.2435 |
| +10 | SSE | +0.2388 |
| −1 | DXY | -0.1134 |
| −2 | USDSGD | -0.0664 |
| −3 | USDINR | -0.0586 |
| −4 | USDJPY | -0.0428 |
| −5 | USDKRW | -0.0268 |
| −6 | USDTWD | -0.0172 |
| −7 | USDHKD | -0.0152 |
| −8 | USDCNH | -0.0078 |
| −9 | AUDJPY | +0.0142 |
| −10 | AUDUSD | +0.0583 |

## 3. TWII–DXY β

- **Full-window β** (TWII = α + β·DXY): **-0.3694**
- **Last 60d β**: **-1.4678**
- 60d β mean over 3y: -0.4097  · range [-2.08, +1.08]

Interpretation: the 3y average TWII-DXY beta is mildly negative (-0.37) — typical EM-vs-dollar dynamics. However the **last 60d β has steepened sharply to +0.00**, meaning every 1% DXY move now reverses ~1% on TWII — roughly 2.0× the average sensitivity.
This is the macro hedge insight for TXF: USD weakness has become the dominant tailwind for TAIEX in the past quarter.

## 4. Top 3 regime shifts (|Δcorr_5d| > 0.3 in 60d-corr series)

| Date | Symbol | corr_t | corr_t−5 | Δ | Plausible driver |
|---|---|---:|---:|---:|---|
| 2025-06-20 | STI | -0.061 | +0.755 | -0.816 | Singapore decoupling — STI rally on Temasek/SovWealth flows while TWII tracked global semis sell-off |
| 2025-06-21 | STI | +0.075 | +0.755 | -0.679 | Continuation of the same STI decoupling |
| 2024-08-07 | TPX | +0.707 | +0.076 | +0.630 | Post-yen-carry-crash: Japan and Taiwan re-correlated as the global risk-off unwound together |

## 5. Tactical implications for TXF trading

1. **USD/TWD is now the most over-weighted single macro factor.** With 60d TWII-DXY β at -1.47 (vs -0.37 3y average), DXY moves currently flow through to TXF almost 4× harder than the long-run average. A long-TXF / long-USD pairing that worked as a natural hedge over 2023–24 is now a CONCENTRATED bet on DXY weakness.

2. **Nikkei (N225) remains the strongest co-mover** (corr +0.62) — TPX proxy similar. North-Asia tech-cycle exposure dominates the panel. KOSPI +0.63 and KOSDAQ +0.56 round out the cluster.

3. **TWD itself has near-zero static corr with TWII** (-0.02) — this is the policy buffer of the CBC defending the band; USD/TWD is *not* a clean TXF hedge. The DXY route (via N225/KS11 correlated currencies) is the cleaner macro proxy.

4. **Greater China indices cluster tightly with each other but only moderately with TWII** (SSE +0.24, CSI300 +0.23, SZSE +0.24, CHINEXT +0.20, HSI +0.37) — TAIEX has decoupled from mainland China beta over 3y; the AI/semi cycle dominates over property/consumer drag.

5. **Regime instability check:** 90 60d-corr regime shifts (|Δ5d|>0.3) over 3y average ~30/yr — rolling correlations are NOT stable, so any naive static-vol-targeting on TXF should be supplemented with the 60d-strip heatmap (dashboard chart #2) before sizing macro overlays.