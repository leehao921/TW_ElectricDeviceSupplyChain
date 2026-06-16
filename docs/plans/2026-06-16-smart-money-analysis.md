# Smart Money Analysis — Sector × Theme Dual View

**Created:** 2026-06-16 (Tue)
**As-of data:** 2026-06-15 (Mon, latest available in trading-timescaledb)
**Owner:** leehao921

---

## Context

### Why this is being built
User wants a quantified view of **三大法人 20 日累計淨買** across (a) Taiwan electronics **11 sectors** and (b) **25 thematic supply chains** (CoWoS, HBM, 矽光子, 電動車...) — so smart-money rotation across both classical industry boundaries and cross-cutting technology winners can be read at a glance, with **外資 / 投信 / 自營 split** to expose divergence signals.

### What's already in place (verified live this turn)
- `trading-timescaledb.institutional_stock` updated daily at **15:15 TPE** by Docker `institutional-collector`. Latest row: **2026-06-15** (18,788 tickers).
- TWSE close_price populated (1,330 tickers). OTC tickers have `close_price = 0` — must fallback to yfinance `.TWO` for TWD valuation.
- `scripts/verify_flow_zscore.py` — mandatory quant-claim verifier (must run before using σ/percentile/罕見/極端 words).
- `themes/` — 25 curated supply-chain maps under `/Users/lulala/Documents/coding/My-TW-Coverage/themes/`.
- `Pilot_Reports/{Sector}/{Ticker}_{Name}.md` — folder = sector; 926 tickers across 11 sectors.
- `WIKILINKS.md` — 2,405 wikilinks indexed; cross-sector technology→ticker mapping.

### Intended outcome
A single reusable script `scripts/smart_money_analysis.py` that, given `--as-of` and `--window`, emits a Markdown report under `analysis/smart_money_YYYY-MM-DD.md` containing:

- TL;DR (1 paragraph + 3 bullet headlines)
- Sector view: 11 sectors × {外資 / 投信 / 自營} 20D cumulative net buy in 億 TWD
- Theme view: 25 themes × {外資 / 投信 / 自營} 20D cumulative net buy in 億 TWD
- Divergence signals: where 外資 and 投信 disagree (one buys, the other sells)
- Top 5 stocks inside each of the top-3 net-bought sectors and themes (per institution)
- Verification log (any distributional claim run through `verify_flow_zscore.py`)

User confirmed scope: **三方分開 / 20 日累計 / Sector + Theme 雙視角 / 可重用腳本先跑一次**.

---

## Design

### Script signature
```bash
python scripts/smart_money_analysis.py \
    --as-of 2026-06-15 \
    --window 20 \
    --top-tickers 5 \
    --output analysis/smart_money_2026-06-15.md
```
All flags optional; `--as-of` defaults to latest `institutional_stock.date`; `--window` defaults to 20.

### Data flow
```
trading-timescaledb.institutional_stock  ──┐
  (date, ticker, foreign_net, trust_net,    │
   dealer_net, close_price, volume)         │
                                             │
Pilot_Reports/{Sector}/{Ticker}_*.md  ──────┼──►  pandas DataFrame
  (ticker → sector via folder)               │     ├── per-ticker 20D net
                                             │     ├── per-sector aggregate
themes/*.md  ───────────────────────────────┘     ├── per-theme aggregate
  (theme → [ticker, ...] via wikilink scan)        └── divergence + ranking
                                                           │
                                                           ▼
                                          analysis/smart_money_YYYY-MM-DD.md
```

### Module structure (inside the single script)

| Function | Responsibility |
|---|---|
| `load_flow(conn, as_of, window)` | SQL pull from `institutional_stock` for the rolling window; returns DataFrame indexed by (ticker, date). |
| `build_sector_map()` | Walk `Pilot_Reports/`; return `{ticker: sector}` dict (~926 entries). |
| `build_theme_map()` | Parse `themes/*.md`; extract `\d{4}` ticker mentions; return `{theme: set(tickers)}` dict (~25 entries, many-to-many). |
| `attach_twd(df)` | Multiply `net_volume × close_price`; for OTC rows where `close_price == 0`, fallback to `yfinance.Ticker(f"{tk}.TWO").history(period="1mo").Close.iloc[-1]` (cached locally to `.cache/otc_close_{as_of}.json` to avoid re-hitting yfinance). |
| `aggregate(df, grouper)` | groupby sector / theme → sum 20D net by institution; return ranked DataFrame in 億 TWD. |
| `divergence(sector_df)` | Find rows where sign(外資) ≠ sign(投信) and |both| > threshold. |
| `render_markdown(...)` | Compose final report. |

### Reuse, not reinvent
- **DB connection:** copy pattern from `analysis/backtest_overnight_signal.py` (already connects to trading-timescaledb).
- **σ/percentile claims:** if the script flags an "extreme" sector flow, call `verify_flow_zscore.py` as a subprocess and embed its output verbatim under "## Verification Log" — satisfies the global rule in CLAUDE.md.
- **Theme parsing:** lift the wikilink-scan regex from `scripts/build_themes.py` (already does this) rather than re-writing.
- **Sector mapping:** filename parse with `pathlib`, no new mapping file.

### Edge cases handled inline
1. **OTC close_price = 0** → yfinance fallback with on-disk cache (only fired for tickers in `themes/` or sectors aggregated).
2. **Ticker in multiple themes** (e.g., 2330 ∈ CoWoS ∩ HBM ∩ 矽光子) → counted in each theme bucket; explicitly noted in the report methodology so the reader doesn't double-add across themes.
3. **Holiday in the 20-day window** → use trading-day count from the data, not calendar days. SQL: `count(distinct date) = 20`.
4. **`futures_oi_daily` is 22 days stale** — not used in this script, so OK; but log a one-line warning in the report header so the reader knows option flow is unavailable today.

### Out of scope (deferred)
- Scheduling (APScheduler / cron) — user picked one-shot script first; can layer scheduling later if the report is useful.
- 1-day / 5-day windows — user picked 20-day only.
- Inter-sector flow heatmap / network plot — Markdown tables only.
- Backtest of whether smart-money flow predicts forward returns — separate question.

---

## Files to create / modify

| File | Action |
|---|---|
| `scripts/smart_money_analysis.py` | **NEW** — the main script (~250–350 LOC). |
| `analysis/smart_money_2026-06-15.md` | **NEW** — first-run output. |
| `.cache/otc_close_2026-06-15.json` | **NEW** (auto-generated) — yfinance OTC close cache. |
| `docs/plans/2026-06-16-smart-money-analysis.md` | **NEW** — copy of this plan committed to repo per CLAUDE.md DevOps rule. |

No edits to existing files. No `themes/` or `Pilot_Reports/` touched.

---

## Verification

After implementation:

1. **End-to-end run:**
   ```bash
   python scripts/smart_money_analysis.py --as-of 2026-06-15 --window 20
   # → expect file analysis/smart_money_2026-06-15.md, ~80–120 lines, no exceptions
   ```

2. **Spot-check totals:** pick ticker **2330 (台積電)** — run independently:
   ```sql
   SELECT SUM(foreign_net) FROM institutional_stock
   WHERE ticker='2330' AND date BETWEEN '<as-of - 20 trading days>' AND '2026-06-15';
   ```
   Confirm it matches the 2330 row in the report's "Top tickers within Semiconductors" table.

3. **Sector totals reconcile:** assert that `sum(per-ticker foreign_net inside sector) == sector aggregate` in the report (the script should print this assertion at end of run as a sanity check).

4. **OTC fallback works:** pick a known OTC ticker (e.g., **6488 環球晶 OTC**) — verify its row carries non-zero TWD net buy and that the yfinance cache file contains an entry for it.

5. **Verification log non-empty if extreme:** if any sector shows |z| > 2σ, the report must include a `## Verification Log` block with `verify_flow_zscore.py` output pasted in. If nothing extreme, the block says "No σ-class claims this run."

6. **Read the report end-to-end** and sanity-check the narrative makes sense (e.g., 外資 top sector + the listed Top-5 tickers within it should be coherent).

If all six pass, the implementation is done.
