---
type: concept
status: active
last_updated: 2026-05-15
related: [DXY.md, covariance_panel.md, ../trading/playbooks.md]
tags: [TXF, futures, anchor]
---

# TXF — 台灣加權指數期貨

User's **main trading contract**.

## Basics

- **Underlying:** TAIEX (`^TWII`) — Taiwan Weighted Index, cash market
- **Multiplier:** NT$200 per point
- **Tick size:** 1 point = NT$200
- **Daily settlement:** by TAIFEX clearinghouse
- **Symbols in DB (`futures_ohlcv`):** TXF202605 (current month), TXFR1 (front-month rolling), TXFR2, TXF202606/07/09/12/202703 (further out)
- **Tick data:** `ticks` table has 57M TXF rows last ~3 weeks; full history backfill is OUT of scope (use TAIEX as 3y proxy)

## Basis (TXF − TAIEX)

- Typical range: **−30 to +30 points** (≈ 0.07-0.2% of index)
- Driven by: implied carry (interest rate − dividend yield), demand for hedging, contract roll
- **5/15 close:** TXF 末檔 41,012 vs TWII 41,603 = **basis −591 點 (−1.42%)** — **EXTREME, year's largest discount**
- Historical context: 5/13–5/15 long-上影線 K + basis 急貼水 = 期貨參與者押注下週現貨補跌
- **Trigger:** basis 收斂至 −100 = 多頭重建訊號; 擴大至 −800 = 強空頭

## Covariance findings (from `data/cov_3y.parquet`, 3y 939 obs)

| 對手 | r (full 3y) | β (full) | β (last 60d) |
|---|---:|---:|---:|
| KOSPI (KS11) | **+0.634** | — | — |
| Nikkei (N225) | +0.615 | — | — |
| KOSDAQ (KQ11) | +0.555 | — | — |
| TOPIX (TPX) | +0.552 | — | — |
| ASX 200 (AXJO) | +0.547 | — | — |
| STI | +0.486 | — | — |
| HSI | +0.370 | — | — |
| NIFTY (NSEI) | +0.314 | — | — |
| **[[DXY]]** | **−0.113** | **−0.37** (3y baseline) | **−1.47** (60d, 5/16 最新) ← 4× regime shift |
| USD/TWD | −0.017 | ~0 | — |
| USD/KRW | −0.027 | — | — |
| USD/JPY | −0.043 | — | — |

→ **KOSPI is the dominant co-mover** (北亞科技週期). USD/TWD is near-zero (CBC defends band).

## Regime shift 2026-05-13 → present

**[[TXF]]–[[DXY]] β_60d 權威數值** (single source of truth: `data/twii_dxy_beta.parquet`, 由 [[covariance_panel]] 2026-05-15 計算):

| 口徑 | β | 角色 |
|---|---:|---|
| 3y 平均 (full window) | **−0.37** | regime baseline (平常水準) |
| 60d rolling (2026-05-16 最新) | **−1.47** | regime-shift 當前值 |
| 倍率 | **4.0×** | 偏離歷史水準 |

最近 5 個交易日的 60d β: 5/13 −1.437 / 5/14 −1.346 / 5/15 −1.431 / 5/16 −1.468 → 已連續 4 天 < −1.3,非單日 outlier。

**驅動因子:**
- 美 4月 PPI YoY +6% (2022 以來最高) → Fed 升息預期 升至 30%
- US 10Y 升至 4.36%, 2Y > 4% (一年來首次)
- [[DXY]] 週度 +1% to 99.05
- SOX 盤中 −6.8% / 收 −3% (5/12 night)

**Tactical reading:** [[TXF]] 已從「科技 alpha 標的」轉為「macro risk asset」。每天 [[DXY]] 變動 1% → [[TXF]] 預期變動 1.5% (β 從 −0.37 變 −1.47, 故 4× 平常)。

## Operational guidance

- **Always read TXF data from `futures_ohlcv` (TimescaleDB)** — TIMESTAMPTZ Asia/Taipei
- For 3y covariance use `^TWII` proxy (in `asia_index_daily`)
- For basis check: query latest TXF202605 close vs TWII close from DB
- For intraday lead/lag: use `ticks` + `stock_ofi` tables

## Related playbooks

- [USD/TWD > 31.80 → 立即減倉](../trading/playbooks.md#twd-defense-line-breach)
- [DXY > 100 → TXF expected -1.5% from β](../trading/playbooks.md#dxy-macro-sensitivity)
- [Basis 擴大 > -800 → 短空 TXF mini](../trading/playbooks.md#basis-extreme-short)
