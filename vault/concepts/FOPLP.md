---
type: concept
status: monitoring
last_updated: 2026-05-15
related: [../projects/active.md, ../../themes/FOPLP.md]
tags: [FOPLP, glass_substrate, ABF, rotation]
---

# FOPLP Rotation Basket

**Fan-Out Panel Level Packaging** — glass-substrate-based advanced packaging, alternative to ABF substrate. Identified as **PC2 factor** in 2026-05-12 PCA analysis (15.43% variance) of TW electronics universe.

Linked: [../../themes/FOPLP.md](../../themes/FOPLP.md), [../../themes/玻璃基板.md](../../themes/玻璃基板.md), [../../themes/TGV.md](../../themes/TGV.md).

## The factor: glass-substrate vs ABF rotation

PC2 loadings sort companies into:

**LONG side (negative loadings → benefit from glass-substrate adoption):**
| Ticker | Name | Loading | Why |
|---|---|---:|---|
| **3481** | [[../../Pilot_Reports/Electronic Components/3481_群創]] | **−0.438** | 玻璃基板 + TGV 主受惠 |
| 2408 | [[../../Pilot_Reports/Semiconductors/2408_南亞科]] | −0.4xx | DRAM, indirect glass demand |
| 2409 | 友達 | — | LCD glass technology |
| 2454 | [[../../Pilot_Reports/Semiconductors/2454_聯發科]] | — | IC design demand |
| 6239 | 力成 | — | 封測 |
| 2303 | 聯電 | — | foundry |
| 2376 | 技嘉 | — | mobo |

**SHORT side (positive loadings → ABF incumbents):**
| Ticker | Name | Loading | Why |
|---|---|---:|---|
| **8046** | 南電 | **+0.491** | ABF 載板龍頭, FOPLP 替代風險最大 |
| 3037 | 欣興 | +0.4xx | ABF 載板 |
| 3017 | 奇鋐 | +0.3xx | 散熱 (隨 ABF 量增受惠) |
| 6213 | — | +0.3xx | — |

## Stored in DB

Postgres `tw_electronics`:
```sql
SELECT * FROM emergent_factor_baskets 
WHERE basket_key = 'foplp_glass_vs_abf_rotation_2026_05';
```

11 tickers with full loadings, signal_strength, market_cap_weighted_score.

## Triggers (per `../trading/playbooks.md`)

- **CONTINUE:** 3481 法人 > +50M/week
- **EXIT:** 3481 跌破 5MA
- **EXPAND:** 8046 法人 < −30M/week confirms SHORT side

## Recent context

- 5/13 法人: 3481 **+127M 大買** (外資主力) — 主題持續
- 5/14: 振盪持平
- 5/15: TWII −0.78% 但 3481 相對抗跌
- 5/19 (一) 開盤觀察: USD/TWD 站穩 31.6 + DXY 守 99 + 3481 持續法人買 = 信號 intact
