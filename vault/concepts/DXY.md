---
type: concept
status: active
last_updated: 2026-05-15
related: [TXF.md, covariance_panel.md]
tags: [DXY, USD, macro]
---

# DXY — U.S. Dollar Index

ICE-calculated index of USD vs basket of 6 currencies. 1973-03 = 100 baseline.

## Composition (fixed weights, last reset 1999 post-EUR)

| Currency | Weight |
|---|---:|
| 🇪🇺 EUR | **57.6%** |
| 🇯🇵 JPY | **13.6%** |
| 🇬🇧 GBP | 11.9% |
| 🇨🇦 CAD | 9.1% |
| 🇸🇪 SEK | 4.2% |
| 🇨🇭 CHF | 3.6% |

**Note:** No CNY, no KRW, no TWD. DXY is essentially "USD vs EUR + JPY" (71% combined).

## Levels

| Range | Status |
|---|---|
| > 110 | 強美元極端 (2022 Q3 高點 114) |
| 105-110 | 強美元 |
| **99-105** | **平衡區 (5/15 closed 99.05)** |
| 95-99 | 弱美元 |
| < 90 | 弱美元極端 (2021 低 89) |

## Channels into TXF (per `concepts/TXF.md`)

1. **Macro risk-off chain:** DXY ↑ → EM 資金回流美國 → 亞股(含 TXF)被賣
2. **Fed expectation proxy:** PPI/CPI hot → Fed 升息預期 ↑ → DXY ↑ → tech 估值不能擴張
3. **Commodity inverse:** DXY ↑ → 銅 / 原油 / 黃金 ↓ → 直接影響 00763U position

## Where to read DXY

| Source | Address |
|---|---|
| **DB** (best for analysis) | `SELECT close FROM fx_daily WHERE pair='DXY' ORDER BY ts DESC LIMIT 1` |
| yfinance | `DX-Y.NYB` |
| TradingView | `TVC:DXY` |
| Bloomberg | `DXY <Index>` |

DXY trades 24/5; "close" = NY 17:00 ET = TW 05:00 next-day.

## Current state (2026-05-15 close)

```
99.05   (+0.16% day, +1.0% week)
Pressure: 100 (psychological), 102 (2026/2 high)
Support:  98.5 (5MA), 97.0 (last week low)
```

Driver: PPI shock 2026-05-13 → Fed expectation reset → DXY 週度大漲。

## Tactical map ([[TXF]] perspective)

**β 口徑 (與 `concepts/TXF.md` + [[covariance_panel]] 同步):**
- 3y 平均 β = **−0.37** (regime baseline)
- **60d β = −1.47** (2026-05-16 最新, 4× 偏離 baseline) ← 本表使用此值
- 切換回 baseline 的條件: 60d β 重回 −0.5 或更淺 (re-check weekly via `data/twii_dxy_beta.parquet`)

| DXY 變動 (next-day) | TXF 預期反應 | 操作 |
|---|---:|---|
| **+1.5% to 100.5** | −2.2% | 立即減 50%, 停損 41,200 |
| +0.5% to 99.5 | −0.7% | 觀望 |
| **平 (~99)** | 震盪 | 持有 |
| −0.5% to 98.5 | +0.7% | 加碼 |
| **−1% to 98** | **+1.5%** | 突破前高加碼 |

**5/19 (週一) 開盤前最重要的單一變數: [[DXY]] 是否站穩 99.0**
