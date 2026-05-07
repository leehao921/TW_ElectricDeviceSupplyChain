# Mediation-First Backtest (2026-04-30)

Sample window: `--start 2023-01-01` `--as-of 2026-04-29`

## Stage-1 chain

> alt-data (5 overnight factors) → next-month revenue YoY surprise
>     (per-ticker IC + pooled panel IC)

Universe: 2330, 2317, 2454, 2308, 2382, 3711, 3037, 2303, 2379, 2002
Surprise = revenue YoY − trailing-12-month median(YoY)

### Factor: `foreign_net`

| Ticker | n | IC | t-stat |
|---|---:|---:|---:|
| 2330 | 22 | -0.229 | -1.05 |
| 2317 | 22 | -0.229 | -1.05 |
| 2454 | 22 | +0.089 | +0.40 |
| 2308 | 22 | -0.115 | -0.52 |
| 2382 | 22 | -0.257 | -1.19 |
| 3711 | 22 | -0.255 | -1.18 |
| 3037 | 22 | -0.343 | -1.63 |
| 2303 | 22 | -0.363 | -1.74 |
| 2379 | 22 | -0.221 | -1.01 |
| 2002 | 22 | -0.015 | -0.07 |

**Pooled panel:** n=220, IC=-0.1720, t-stat=-2.58
**Verdict:** ✅ PASS

### Factor: `usdtwd`

| Ticker | n | IC | t-stat |
|---|---:|---:|---:|
| 2330 | 22 | +0.054 | +0.24 |
| 2317 | 22 | +0.292 | +1.36 |
| 2454 | 22 | -0.027 | -0.12 |
| 2308 | 22 | +0.417 | +2.05 |
| 2382 | 22 | -0.160 | -0.72 |
| 3711 | 22 | +0.227 | +1.04 |
| 3037 | 22 | -0.266 | -1.23 |
| 2303 | 22 | +0.144 | +0.65 |
| 2379 | 22 | +0.116 | +0.52 |
| 2002 | 22 | +0.188 | +0.86 |

**Pooled panel:** n=220, IC=+0.0450, t-stat=+0.66
**Verdict:** ❌ FAIL

### Factor: `sp500`

| Ticker | n | IC | t-stat |
|---|---:|---:|---:|
| 2330 | 22 | -0.267 | -1.24 |
| 2317 | 22 | +0.100 | +0.45 |
| 2454 | 22 | -0.019 | -0.08 |
| 2308 | 22 | -0.048 | -0.21 |
| 2382 | 22 | -0.274 | -1.27 |
| 3711 | 22 | -0.297 | -1.39 |
| 3037 | 22 | +0.108 | +0.49 |
| 2303 | 22 | -0.136 | -0.61 |
| 2379 | 22 | -0.277 | -1.29 |
| 2002 | 22 | +0.028 | +0.12 |

**Pooled panel:** n=220, IC=-0.0894, t-stat=-1.32
**Verdict:** ❌ FAIL

### Factor: `tsm`

| Ticker | n | IC | t-stat |
|---|---:|---:|---:|
| 2330 | 22 | -0.315 | -1.48 |
| 2317 | 22 | -0.223 | -1.02 |
| 2454 | 22 | +0.036 | +0.16 |
| 2308 | 22 | -0.276 | -1.28 |
| 2382 | 22 | -0.224 | -1.03 |
| 3711 | 22 | -0.298 | -1.39 |
| 3037 | 22 | -0.064 | -0.29 |
| 2303 | 22 | -0.203 | -0.93 |
| 2379 | 22 | -0.221 | -1.01 |
| 2002 | 22 | +0.058 | +0.26 |

**Pooled panel:** n=220, IC=-0.1543, t-stat=-2.31
**Verdict:** ✅ PASS

### Factor: `sox`

| Ticker | n | IC | t-stat |
|---|---:|---:|---:|
| 2330 | 22 | -0.449 | -2.25 |
| 2317 | 22 | -0.189 | -0.86 |
| 2454 | 22 | +0.012 | +0.05 |
| 2308 | 22 | -0.177 | -0.80 |
| 2382 | 22 | -0.391 | -1.90 |
| 3711 | 22 | -0.193 | -0.88 |
| 3037 | 22 | -0.189 | -0.86 |
| 2303 | 22 | -0.264 | -1.22 |
| 2379 | 22 | -0.317 | -1.49 |
| 2002 | 22 | -0.063 | -0.28 |

**Pooled panel:** n=220, IC=-0.2217, t-stat=-3.36
**Verdict:** ✅ PASS

## Composite verdict

- Passed factors: ['foreign_net', 'tsm', 'sox']
- Threshold: |panel_IC| > 0.05 AND |t-stat| > 2.0

**MEDIATION VALIDATED** — at least one overnight factor predicts revenue surprises with statistical power. The fundamentals→return chain (Bartov, La Porta) transitively supports the alt-data→return claim for the passed factors.
