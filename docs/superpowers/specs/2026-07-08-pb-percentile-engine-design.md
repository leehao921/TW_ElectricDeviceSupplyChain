# P/B 歷史分位判斷引擎 — Design Spec

**Date:** 2026-07-08
**Status:** Approved (design), pending implementation plan
**Sub-project:** A of 3 (see Context)

---

## Context

This is **sub-project A** of a larger effort to bring valuation into the daily
`buy_list_daily_alert.py` routine. The full decomposition:

- **A (this spec)** — a reusable P/B 高檔判斷引擎: per-ticker, pull P/B history,
  compute the current P/B's historical percentile, emit GREEN/YELLOW/RED.
- **B** — expand `memory_cycle_monitor.py` signal S1 to use engine A across the
  full portfolio (not just 2408/2344), deploy it (merge branch, schedule,
  publish per-ticker light to Redis `h:agent:memory_cycle`).
- **C** — integrate into `buy_list_daily_alert.py`: (①) show PE/PB/殖利率
  recomputed at latest price, (②) new rule `close ≤ stop×1.02 且 P/B=RED →
  🔴 優先減碼`.

Engine A is the shared foundation for both B's S1 expansion and C②'s rule.
It replaces the hardcoded `PB_THRESHOLDS` (currently 2 hand-set tickers) with a
data-derived, self-normalizing percentile that scales to any ticker.

### Why percentile, not absolute multiple

Empirical check (2026-07-08) across 5 currently-elevated names showed
`current P/B ÷ 5y-median` ranges from **2.5x (散熱 3017) to 6.6x (記憶體 2408)** —
a single cross-sector multiple threshold cannot work. The **percentile** of the
current P/B within the stock's own history self-normalizes: all 5 land at
**95–99th percentile**, cleanly RED under a single 85/70 band.

---

## Data Source & Feasibility (verified 2026-07-08)

yfinance, per ticker:

| Input | yfinance field | Availability |
|---|---|---|
| Annual stockholders equity | `balance_sheet.loc['Stockholders Equity']` | **5 fiscal years** (e.g. 2021–2025) ✅ |
| Shares outstanding | `info['sharesOutstanding']` | current (single value) |
| Daily close, 5y | `history(period='5y')['Close']` | ~1,200 trading days ✅ |

Quarterly balance sheet gives only ~5 quarters → too shallow, **rejected**.
Annual equity (5 points) + daily price (~1,200 points) is the usable basis.

---

## Algorithm

```
1. BVPS[year] = StockholdersEquity[year] / sharesOutstanding
   - DROP any year whose equity is NaN or ≤ 0  (2408 FY2021 equity is NaN)
2. Build daily P/B series over 5y:
   pb[date] = close[date] / BVPS[most recent fiscal year-end ≤ date]
   - drop rows where BVPS unavailable (dates before earliest kept year)
3. current_pb = latest_close / BVPS[latest fiscal year]
   - MUST use same annual-BVPS basis as the history (apples-to-apples),
     NOT yfinance info['priceToBook']
4. percentile = fraction of historical pb strictly < current_pb, ×100
5. light = RED    if percentile ≥ 85
           YELLOW if percentile ≥ 70
           GREEN  otherwise
```

### Thresholds (approved)

| Band | Rule |
|---|---|
| RED | percentile ≥ 85 |
| YELLOW | percentile ≥ 70 |
| GREEN | otherwise |

Configurable via constants (default 85/70). Lookback = 5 years (bounded by
annual balance-sheet depth). Book-value basis = **annual** (quarterly rejected).

---

## Interface

New module `scripts/pb_percentile.py`:

```python
def pb_light(ticker: str) -> dict:
    """
    Returns:
      {
        "ticker": "2408",
        "pb_current": 7.20,
        "percentile": 99.0,
        "light": "RED",           # GREEN | YELLOW | RED | "N/A"
        "p70": <abs P/B at 70th>,
        "p85": <abs P/B at 85th>,
        "bvps": 54.99,            # latest annual book value per share; None on N/A
        "n_days": 1214,
        "source": "yfinance annual BVPS 5y",
        "asof": "2026-07-08",
      }
    """
```

- Accepts bare ticker ("2408"); appends `.TW`/`.TWO` as needed (reuse existing
  suffix-resolution helper if one exists in the codebase; otherwise `.TW` then
  `.TWO` fallback).
- Consumed by sub-project B (monitor S1) and C② (buy-list 減碼 rule).

---

## Caching

Pulling 5y history is ~1–2 s/ticker × 15+ picks → too slow for a daily
08:50 pre-open routine.

- Cache each ticker's computed **cutoffs** (`p70`, `p85` absolute P/B values,
  latest `BVPS`, `asof` date, `n_days`) to `data/pb_percentile_cache.json`.
- **Weekly** refresh of cutoffs (book value and the historical distribution
  move slowly).
- **Daily** fast path: latest_close → current_pb = close / cached BVPS →
  compare to cached p70/p85 → light. No network call.
- Cache-miss or stale (> 7 days) → recompute that ticker live.

---

## Error Handling / Fallback

| Condition | Behaviour |
|---|---|
| Annual equity all NaN / missing | `light = "N/A"`, percentile = None |
| sharesOutstanding missing | `light = "N/A"` |
| Latest BVPS ≤ 0 (negative equity) | `light = "N/A"` |
| < 250 valid daily P/B points | `light = "N/A"` + `source` notes thin history |
| yfinance network error | `light = "N/A"`, do not fabricate |

Rationale: the downstream 減碼 rule is `stop-break AND P/B=RED`. N/A never
equals RED → a data gap **suppresses** the rule rather than mis-firing it.
Failing safe (no false 減碼) is the correct default.

---

## Acceptance Tests (empirically grounded, measured 2026-07-08)

1. **2408 validates RED** — current P/B ≈ 7.20 → **99th percentile → RED**.
   This reproduces the 2026-06-25 memory-cycle RED signal that was validated by
   the subsequent −10.2% correction. (Core correctness anchor.)
2. **NaN-year handling** — a ticker whose earliest annual equity is NaN
   (real case: 2408 FY2021) must drop that year and still compute a valid
   percentile. Regression guard against the prototype bug where NaN poisoned
   `np.percentile` → wrong GREEN.
3. **Basis consistency** — current_pb uses annual BVPS, not
   `info['priceToBook']`; a unit test asserts current_pb == close / latest_BVPS.
4. **Fallback** — a ticker with missing/negative equity returns
   `light == "N/A"`, never RED.
5. **Cross-sector spread** — 3017 (散熱) and 2408 (記憶體) both classify RED via
   percentile despite cur/median multiples of 2.7x vs 6.6x (validates
   self-normalization; a fixed multiple threshold would fail this).

Measured reference values (2026-07-08, for test fixtures):

| Ticker | current P/B | 5y percentile | light |
|---|---|---|---|
| 2408 | 7.20 | 99 | RED |
| 2344 | 7.02 | 98 | RED |
| 3037 | 13.51 | 97 | RED |
| 3017 | 20.46 | 95 | RED |
| 2455 | 18.80 | 96 | RED |

---

## Known Limitations

- **Shares-outstanding is current, applied to all historical years.** If a stock
  materially changed its share count (2408 diluted during the downturn), older
  BVPS is slightly biased. Effect is second-order for percentile *ranking*
  (2408 still 99th pct); documented, not fixed. Possible future refinement:
  per-year shares via `get_shares_full`.
- **Annual (not quarterly) book value** → P/B step-updates once a year. Price
  dominates intra-year variation; acceptable for percentile ranking.
- **5y window may not span a full cycle** for the longest cyclicals; bounded by
  yfinance annual depth. Accepted per YAGNI.

---

## Out of Scope (this sub-project)

- Wiring into `memory_cycle_monitor.py` S1 (→ sub-project B).
- Wiring into `buy_list_daily_alert.py` display or 減碼 rule (→ sub-project C).
- Recomputing PE / 殖利率 at latest price (→ sub-project C①).
