# Overnight Composite Signal — Backtest Report (2026-04-29)

Sample: **2023-01-05 → 2026-04-29**, 862 trading days
Window: `--start 2023-01-01` `--end 2026-04-29`

## Per-Component IC

| Component | n | Spearman IC | Hit rate |
|---|---:|---:|---:|
| `foreign_net` | 803 | +0.0131 | 53.15% |
| `usdtwd` | 803 | -0.0866 | 44.83% |
| `sp500` | 803 | +0.4554 | 66.58% |
| `tsm` | 803 | +0.4465 | 65.91% |
| `sox` | 803 | +0.4579 | 65.37% |

## Composite (default weights)

Weights: `foreign_net`=+0.25, `usdtwd`=-0.15, `sp500`=+0.15, `tsm`=+0.25, `sox`=+0.20

- n = **803**
- Spearman IC = **+0.4190**
- Hit rate = **67.65%**

## Variance attribution (w² / Σw²)

| Component | Share |
|---|---:|
| `foreign_net` | 29.8% |
| `usdtwd` | 10.7% |
| `sp500` | 10.7% |
| `tsm` | 29.8% |
| `sox` | 19.0% |

## Grid search — top 5 by IC (10% steps, max single weight ≤ 0.7)

| foreign | usdtwd | sp500 | tsm | sox | IC |
|---:|---:|---:|---:|---:|---:|
| 0.00 | -0.10 | 0.40 | 0.30 | 0.20 | +0.5054 |
| 0.00 | -0.10 | 0.40 | 0.40 | 0.10 | +0.5053 |
| 0.00 | -0.10 | 0.50 | 0.40 | 0.00 | +0.5048 |
| 0.00 | -0.10 | 0.30 | 0.40 | 0.20 | +0.5044 |
| 0.00 | -0.10 | 0.30 | 0.30 | 0.30 | +0.5042 |

## Pass-Bar Check

- Composite IC ≥ 0.10 → **+0.4190** → PASS
- Hit rate ≥ 54% → **67.65%** → PASS
- N ≥ 500 → **803** → PASS
- Max var-attribution ≤ 70% → **29.8%** → PASS

**Overall: PASS — proceed to Phase 2**
