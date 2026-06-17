# Add Bollinger-Squeeze Scanner to smart_money_analysis.py

**Created:** 2026-06-17 (Wed)
**Repo:** `/Users/lulala/Documents/coding/My-TW-Coverage/`
**Owner:** leehao921

---

## Context

### Why this is being built
This session produced a one-shot Bollinger-squeeze + volume-breakout scanner (inline in Bash, against the 925 Pilot_Reports tickers via yfinance) that surfaced **2455 全新** and **6668 中揚光** as A-grade buy candidates and flagged **6884 海柏特 / 8091 翔名** as bearish/distribution. The user wants this turned into a reusable, repeatable part of the existing daily smart-money workflow.

The scanner answers a question the current `scripts/smart_money_analysis.py` does NOT: **"which tickers are in a low-volatility squeeze AND today broke out on volume?"** Smart-money report tells you where sector/theme flow is going; squeeze scanner tells you which specific stocks are technically primed and have just fired. The two views are complementary: squeeze hits gain conviction when 5D 法人 also confirms (e.g., 2455 +5.24 億); they become avoidance signals when 5D 法人 contradicts (e.g., 8091 −5,400 萬 外資 selling into the breakout).

### Intended outcome
A new **Section 9** in the existing smart-money Markdown report containing two tables — **🟢 Buy candidates** and **🔴 Avoid signals** — automatically populated each time `scripts/smart_money_analysis.py` is run. No new file, no new CLI command — the existing daily workflow gains the scanner output for free.

### User-confirmed scope (this session)
- **Integration:** new section inside `analysis/smart_money_YYYY-MM-DD.md` (not a separate file)
- **Default thresholds:** BBW ≤ 30 percentile of own 60D history, ≥ 4 of last 7 days squeezed, today's volume / 20D avg ≥ 2.0×
- **Output structure:** Buy table (squeeze + breakout up + 法人 confluence positive) AND Avoid table (squeeze breakdown OR 法人 reverse), side by side

---

## Design

### Where the code lives
**`scripts/smart_money_analysis.py`** — extend the existing 639-LOC script. No new files for scanner logic. One new optional flag: `--skip-bb-scan` (default = enabled). Skip path is provided because yfinance batch over ~900 tickers adds ~60 seconds — useful in dev iteration.

### New functions (added in module order)

| Function | Responsibility |
|---|---|
| `fetch_ohlcv_universe(tickers, period='3mo')` | Batch yfinance download with `.TW` then `.TWO` fallback. Returns `{ticker: pd.DataFrame}`. Uses `yf.download` with `group_by='ticker'`, threads=True, chunks of 50. |
| `compute_squeeze_signal(df, bbw_pct=30, min_squeeze_days=4, vol_mult=2.0)` | Per-ticker: compute BB (20D ±2σ), bbw, vol_ratio. Return dict of squeeze metrics + breakout direction. None if < 35 rows. |
| `scan_squeeze(ohlcv_map, sector_map, name_map, per_ticker_flow, **thresholds)` | Loop over tickers, apply `compute_squeeze_signal`, attach 5D 法人 from `per_ticker_flow` (we already have it from the main flow), classify each hit as 'buy' / 'avoid' / 'watch'. Return two DataFrames. |
| `render_bb_squeeze_panel(buy_df, avoid_df, thresholds)` | Render Section 9: methodology paragraph + Buy table + Avoid table + footnote on parameters. |

### Classification rules

| Bucket | Condition |
|---|---|
| 🟢 **Buy** | squeezed ≥ 4/7 days + today vol ≥ 2× + today return > +1.5% + close above upper band + 5D 外資 ≥ +0.3 億 (or shares > 0 for OTC where TWD ≈ 0) |
| 🟡 **Watch** | squeezed + breakout up but 法人 confluence weak / OTC where TWD unavailable |
| 🔴 **Avoid** | (squeezed + breakdown down, return < −1.5% + below lower band) OR (breakout up + 5D 外資 ≤ −0.3 億) — the 8091 / 3481 distribution pattern |

Watch bucket is rendered as a footnote line, not its own table, to keep the panel readable.

### Reuse from existing code (no rebuilding)

| Reused from | Function | Purpose |
|---|---|---|
| `scripts/smart_money_analysis.py:120` | `build_sector_map()` | Pilot_Reports → ticker→sector |
| `scripts/smart_money_analysis.py:132` | `build_theme_map()` | themes/ → theme→tickers (for wikilink annotation) |
| `scripts/smart_money_analysis.py:144` | `build_ticker_name_map()` | filename → ticker→中文名 |
| `scripts/smart_money_analysis.py:206` | `per_ticker_window_sum()` | 5D 法人 confluence already computed inline by the main flow — pass it through |
| `scripts/smart_money_analysis.py:274` | `fmt()` | number formatting |

The scanner does NOT re-query the DB for 法人 data — it slices `per_ticker_cov` (already in memory from the main flow) to get the 5D window. Free.

### CLI flag added
```python
ap.add_argument("--skip-bb-scan", action="store_true",
                help="Skip the Bollinger squeeze panel (~60s yfinance pull)")
```
Default: scanner runs. `--skip-bb-scan` for dev iteration.

### Section 9 layout in the report

```markdown
---

## 9. 盤整突破掃描 (Bollinger Squeeze + Volume Breakout)

過去 7 個交易日內 BBW ≤ 30 percentile (自身 60D) 達 ≥ 4 天,且今日量能 ≥ 2× 20D 平均。
與 5D 三大法人 confluence 交叉,分 Buy / Avoid 兩類。Watch (法人未確認的突破) 列在腳註。

### 🟢 Buy (squeeze 突破 + 法人加碼確認)
| Ticker | 名稱 | Sector | 收 | 今日% | vol× | BBW(今/7均) | 5D 外資 (億) | 主題 |
| ... |

### 🔴 Avoid (突破方向反轉 OR 法人逢高出貨)
| Ticker | 名稱 | 訊號 | 收 | 今日% | vol× | 5D 外資 |
| ... |

*Watch (突破但法人未跟): 6498 久禾光 / 3527 聚積 / 2380 虹光 / 3360 尚立*

*Methodology: BBW = (upper-lower)/middle; squeeze threshold = own 60D percentile;
data: yfinance 3mo + trading-timescaledb.institutional_stock 5D window.*
```

### Universe = the same `universe` set already built by main flow

`scripts/smart_money_analysis.py:454` already builds `universe = set(sector_map.keys()) | set().union(*theme_map.values())` = ~926 tickers. The scanner uses the same set — no separate universe list, no inconsistency between the two report sections.

### Edge cases handled inline
1. **yfinance noisy stderr** (`possibly delisted` for OTC-only tickers) — captured silently; the `.TW` → `.TWO` fallback chain handles it. Final coverage logged to stderr.
2. **< 35 trading days of history** — silently skipped (returns None from `compute_squeeze_signal`).
3. **All-NaN tickers** (delisted) — `dropna(how='all')` in fetch step.
4. **Today's row missing** (yfinance hasn't yet captured a closed bar) — scanner uses the latest available bar; logs warning if it's not today's TPE date.
5. **5D 法人 lookup fails** (ticker not in `per_ticker_cov`) — treated as `confluence_missing`, ticker drops to Watch bucket.
6. **Theme lookup for hot wikilinks** — for each Buy hit, look up which themes contain that ticker (via `theme_map`); show up to 3 in `主題` column for narrative context (e.g. 2455 → "[[砷化鎵]] [[5G]] [[低軌衛星]]").

### Out of scope (deferred)
- **Scheduling** — user has APScheduler context elsewhere; this just produces output on demand. Can layer cron later.
- **yfinance cache layer** — re-fetch every run for now (60s overhead). Cache speedup is meaningful but adds correctness risk (stale on volatile days). Skip for v1.
- **Multi-window scanner** — only the daily snapshot. Intraday squeeze is a different beast.
- **Backtest of squeeze→breakout return distribution** — could be its own PR; this is a screener, not a strategy backtester.
- **Custom threshold CLI flags** — user explicitly chose "Recommended" defaults. If needed later, three flags can be added.

---

## Files to create / modify

| File | Action |
|---|---|
| `scripts/smart_money_analysis.py` | **EDIT** — add 4 functions (~150 LOC), 1 CLI flag, splice Section 9 into report assembly. |
| `analysis/smart_money_2026-06-17.md` | **OUTPUT** — first-run regenerated with the new section. |
| `docs/plans/2026-06-17-bb-squeeze-integration.md` | **NEW** — plan committed per CLAUDE.md DevOps trail. |

No new top-level scripts. No new tests (consistent with existing scripts/* in this repo which have no companion tests). `requirements` no change (yfinance + pandas already used).

---

## Verification

After implementation:

1. **Run with --skip-bb-scan to confirm legacy path still works:**
   ```bash
   python scripts/smart_money_analysis.py --as-of 2026-06-16 --window 20 --skip-bb-scan
   # Expect: same output as before, Section 9 absent
   ```

2. **Run full pipeline:**
   ```bash
   python scripts/smart_money_analysis.py --as-of 2026-06-17 --window 20
   # Expect: ~60s extra wall time (yfinance batch). Section 9 populated.
   # 2455 全新 in Buy with 5D 外資 +5.2 億.
   # 6668 中揚光 in Buy or Watch (depending on whether 0.43 億 crosses confluence floor).
   # 6884 海柏特 in Avoid (breakdown).
   # 8091 翔名 in Avoid (distribution: foreign sell + retail breakout).
   ```

3. **Spot-check 2455 against inline analysis already done this turn:**
   - close ≈ 421, vol × ≈ 2.04 (today 19.13M / 20D avg 9.38M)
   - 5D 外資 = +5.24 億
   - BBW today ≈ 30.38

4. **Threshold robustness — temporarily edit threshold to BBW≤20 (stricter) and re-run:**
   - Buy table shrinks to 2-3 candidates
   - 2455 should survive (BBW 30.38 / 60D min 23.35 → still close to lows)

5. **No-hit day:** pick a date well outside any obvious narrative (e.g. 2026-04-15) — Section 9 should render gracefully with "*無 squeeze breakout hits*" empty-state message.

If all five pass, implementation is complete. Branch + commit to `feat/bb-squeeze-scanner` and PR.
