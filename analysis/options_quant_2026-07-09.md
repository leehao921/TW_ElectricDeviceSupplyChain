# TXO 選擇權盤中量化分析 — 2026-07-09 09:00-12:00

**Vol 環境標籤:** `neutral-carry`

## 1. GEX / Dealer Gamma

**Verdict:** 總 GEX 1.20 億/1%; flip=48000.0; spot=45839 → 放大區 (expansion)

- total_gex: 120339835.12921402
- flip: 48000.0
- zone: expansion
- top_strikes: [47000.0, 45000.0, 48000.0, 47200.0, 44000.0]

## 2. IV vs RV (VRP)

**Verdict:** VRP +10.9 vol pts (IV 35.9 vs RV 25.0), 60 日同窗 percentile 43 → VRP 居中

- rv: 0.24967766572109182
- iv: 0.35883071300149777
- vrp: 0.10915304728040595
- percentile: 42.857142857142854

## 3. Term / Skew 盤中動態

**Verdict:** ATM IV Δ -16.2 pts; skew_25d Δ -0.65 (pct 48.38709677419355); term slope 0.00036679812596923655

- atm_iv_delta: -0.16231342337492055
- skew_delta: -0.006485685413280373
- skew_delta_pct: 48.38709677419355
- term_slope: 0.00036679812596923655
- atm_iv_path_max: 0.5036162899513577
- atm_iv_path_min: 0.3099964971777449

## 4. PCR / OI 資金流

**Verdict:** PCR(vol) mean 0.67; top ΔOI: [(52000.0, 918, 'C'), (51500.0, 699, 'C'), (49000.0, 536, 'C')]

- pcr_mean: 0.6678768960278761
- top_oi_builds: [(52000.0, 918, 'C'), (51500.0, 699, 'C'), (49000.0, 536, 'C'), (44200.0, 521, 'P'), (48500.0, 336, 'C')]

## Verification log

- GEX assumptions: naive dealer sign (call +, put -); OI from settle 2026-07-08 (T+1 approximation); gamma from window-end iv_strikes snapshot; multiplier 50
- VRP: value=0.1092 percentile=43 vs same-window history n=35 (rank = share of history strictly below value)
- RV: intraday-only (day-session 1m bars), overnight variance excluded; annualized sqrt(252*300)
- skew_25d window delta: value=-0.0065 percentile=48 vs same-window history n=31 (rank = share of history strictly below value)

## 標籤定義

- `expansion-risk`: 總 GEX < 0 且 VRP percentile < 30
- `premium-rich-pinning`: 總 GEX > 0 且 VRP percentile > 70
- `hedging-bid`: skew Δ percentile > 80
- `neutral-carry`: 其餘 (fallback)

> 本報告為環境判定,不出買賣指令。資料 read-only 取自 trading-timescaledb。
