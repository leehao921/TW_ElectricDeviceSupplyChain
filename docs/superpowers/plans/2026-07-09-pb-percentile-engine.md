# P/B Historical-Percentile Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/pb_percentile.py`, a reusable engine that returns each ticker's current P/B, its percentile within 5 years of the ticker's own P/B history, and a GREEN/YELLOW/RED light at 85/70 bands.

**Architecture:** Separate the network layer (`fetch_yf`, thin, not unit-tested) from pure computation (`compute_bvps`, `build_pb_series`, `pct_rank`, `classify`, `compute_pb_light`, all unit-tested with synthetic fixtures). A JSON cutoff cache (`data/pb_percentile_cache.json`) gives a network-free daily fast path; weekly recompute refreshes cutoffs. Data gaps fail safe to `light="N/A"` (never RED), so the downstream `stop-break AND RED` 減碼 rule cannot mis-fire.

**Tech Stack:** Python 3, pandas, yfinance, pytest. Spec: `docs/superpowers/specs/2026-07-08-pb-percentile-engine-design.md`.

---

## File Structure

- Create: `scripts/pb_percentile.py` — the engine (all functions below).
- Create: `tests/test_pb_percentile.py` — unit tests (synthetic fixtures, no network) + one live acceptance test (network, skips if offline).
- Data (runtime, not committed): `data/pb_percentile_cache.json` — per-ticker cutoff cache.

Module-level constants (defined once in Task 1, reused everywhere):

```python
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "pb_percentile_cache.json"
RED_PCT = 85.0
YELLOW_PCT = 70.0
MIN_DAYS = 250
STALE_DAYS = 7
```

Test header (top of `tests/test_pb_percentile.py`):

```python
from __future__ import annotations
import sys
from pathlib import Path
import math
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import pb_percentile as pbp  # noqa: E402
```

---

### Task 1: `compute_bvps` — annual book value per share, dropping bad years

**Files:**
- Create: `scripts/pb_percentile.py`
- Test: `tests/test_pb_percentile.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pb_percentile.py` (after the header above):

```python
def test_compute_bvps_drops_nan_and_nonpositive():
    equity = {2021: float("nan"), 2022: 1000.0, 2023: 1100.0, 2024: -50.0}
    shares = 100.0
    bvps = pbp.compute_bvps(equity, shares)
    assert bvps == {2022: 10.0, 2023: 11.0}   # 2021 NaN dropped, 2024 negative dropped


def test_compute_bvps_empty_when_shares_missing():
    assert pbp.compute_bvps({2023: 1100.0}, 0.0) == {}
    assert pbp.compute_bvps({2023: 1100.0}, None) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pb_percentile.py -k compute_bvps -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pb_percentile'` (module not created yet).

- [ ] **Step 3: Write minimal implementation**

Create `scripts/pb_percentile.py`:

```python
"""P/B historical-percentile engine.

Per ticker: pull 5y annual book value + daily close from yfinance, build a
daily P/B series, and report the current P/B's percentile within its own
history as a GREEN / YELLOW / RED light (85 / 70 bands).

Pure functions (compute_bvps ... compute_pb_light) take already-fetched data
and are unit-tested with synthetic fixtures. fetch_yf is the only networked
function. Data gaps -> light="N/A" (never RED) so downstream stop-break rules
fail safe.

See docs/superpowers/specs/2026-07-08-pb-percentile-engine-design.md.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "pb_percentile_cache.json"
RED_PCT = 85.0
YELLOW_PCT = 70.0
MIN_DAYS = 250
STALE_DAYS = 7


def compute_bvps(equity: dict, shares) -> dict:
    """Book value per share per fiscal year. Drop NaN/<=0 equity; shares must be >0."""
    if not shares or shares <= 0:
        return {}
    out = {}
    for year, eq in equity.items():
        if eq is None:
            continue
        if isinstance(eq, float) and math.isnan(eq):
            continue
        if eq <= 0:
            continue
        out[int(year)] = eq / shares
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pb_percentile.py -k compute_bvps -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/pb_percentile.py tests/test_pb_percentile.py
git commit -m "feat(valuation): compute_bvps drops NaN/negative-equity years"
```

---

### Task 2: `build_pb_series` — daily P/B via as-of annual book value

**Files:**
- Modify: `scripts/pb_percentile.py`
- Test: `tests/test_pb_percentile.py`

- [ ] **Step 1: Write the failing test**

```python
def _prices(pairs):
    idx = pd.to_datetime([d for d, _ in pairs])
    return pd.Series([p for _, p in pairs], index=idx)


def test_build_pb_series_asof_annual_join():
    bvps = {2022: 10.0, 2023: 11.0}
    prices = _prices([
        ("2022-06-30", 50.0),   # before 2022 year-end -> no prior FY -> dropped
        ("2023-06-30", 100.0),  # most recent FY-end <= date is 2022-12-31 -> bvps 10 -> pb 10
        ("2024-01-02", 110.0),  # FY 2023-12-31 -> bvps 11 -> pb 10
    ])
    pb = pbp.build_pb_series(prices, bvps)
    assert list(pb.round(4)) == [10.0, 10.0]        # first row dropped
    assert len(pb) == 2


def test_build_pb_series_empty_bvps_returns_empty():
    pb = pbp.build_pb_series(_prices([("2023-06-30", 100.0)]), {})
    assert len(pb) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pb_percentile.py -k build_pb_series -v`
Expected: FAIL — `AttributeError: module 'pb_percentile' has no attribute 'build_pb_series'`.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/pb_percentile.py`:

```python
import pandas as pd  # add to imports at top of file


def build_pb_series(prices: "pd.Series", bvps: dict) -> "pd.Series":
    """Daily P/B = close / (BVPS of most recent fiscal year-end <= date).

    Dates earlier than the first available fiscal year-end are dropped.
    """
    if not bvps or prices is None or len(prices) == 0:
        return pd.Series(dtype=float)
    years = sorted(bvps)
    year_ends = [(pd.Timestamp(y, 12, 31), bvps[y]) for y in years]

    def asof(d):
        chosen = None
        for ye, val in year_ends:
            if ye <= d:
                chosen = val
        return chosen  # None if date precedes first FY-end

    idx = pd.to_datetime(prices.index)
    denom = pd.Series([asof(d) for d in idx], index=prices.index)
    pb = (prices / denom).dropna()
    return pb
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pb_percentile.py -k build_pb_series -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/pb_percentile.py tests/test_pb_percentile.py
git commit -m "feat(valuation): build_pb_series with as-of annual book value join"
```

---

### Task 3: `pct_rank` + `classify` — percentile and 85/70 bands

**Files:**
- Modify: `scripts/pb_percentile.py`
- Test: `tests/test_pb_percentile.py`

- [ ] **Step 1: Write the failing test**

```python
def test_pct_rank_strict_less_than():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert pbp.pct_rank(s, 4.0) == 60.0     # 3 of 5 strictly < 4
    assert pbp.pct_rank(s, 1.0) == 0.0
    assert pbp.pct_rank(s, 6.0) == 100.0


def test_classify_bands():
    assert pbp.classify(90.0) == "RED"
    assert pbp.classify(85.0) == "RED"      # boundary inclusive
    assert pbp.classify(84.9) == "YELLOW"
    assert pbp.classify(70.0) == "YELLOW"   # boundary inclusive
    assert pbp.classify(69.9) == "GREEN"
    assert pbp.classify(10.0) == "GREEN"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pb_percentile.py -k "pct_rank or classify" -v`
Expected: FAIL — attributes `pct_rank` / `classify` do not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/pb_percentile.py`:

```python
def pct_rank(values: "pd.Series", current: float) -> float:
    """Percentile of `current`: fraction of values strictly less, x100."""
    return float((values < current).mean() * 100.0)


def classify(percentile: float, red: float = RED_PCT, yellow: float = YELLOW_PCT) -> str:
    if percentile >= red:
        return "RED"
    if percentile >= yellow:
        return "YELLOW"
    return "GREEN"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pb_percentile.py -k "pct_rank or classify" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/pb_percentile.py tests/test_pb_percentile.py
git commit -m "feat(valuation): pct_rank + classify 85/70 bands"
```

---

### Task 4: `compute_pb_light` — pure orchestrator with N/A fallbacks

**Files:**
- Modify: `scripts/pb_percentile.py`
- Test: `tests/test_pb_percentile.py`

- [ ] **Step 1: Write the failing test**

```python
def _linear_prices(start, end, n, price_lo, price_hi):
    idx = pd.date_range(start, end, periods=n)
    vals = [price_lo + (price_hi - price_lo) * i / (n - 1) for i in range(n)]
    return pd.Series(vals, index=idx)


def test_compute_pb_light_happy_red():
    # 300 trading days across 2 fiscal years; price rises so latest P/B is top of range
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    equity = {2022: 1000.0, 2023: 1000.0}   # BVPS 10 both years (shares 100)
    res = pbp.compute_pb_light(prices, equity, shares=100.0, ticker="TEST")
    assert res["light"] == "RED"
    assert res["percentile"] >= 85.0
    assert res["pb_current"] == pytest.approx(30.0, rel=1e-3)   # 300 / 10
    assert res["n_days"] >= 250
    assert res["p85"] > 0 and res["p70"] > 0


def test_compute_pb_light_na_when_no_bvps():
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    res = pbp.compute_pb_light(prices, equity={2023: float("nan")}, shares=100.0, ticker="TEST")
    assert res["light"] == "N/A"
    assert res["percentile"] is None


def test_compute_pb_light_na_when_thin_history():
    prices = _linear_prices("2024-06-03", "2024-12-31", 100, 100.0, 120.0)  # <250 days
    res = pbp.compute_pb_light(prices, equity={2023: 1000.0}, shares=100.0, ticker="TEST")
    assert res["light"] == "N/A"
    assert "thin" in res["source"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pb_percentile.py -k compute_pb_light -v`
Expected: FAIL — attribute `compute_pb_light` does not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/pb_percentile.py`:

```python
def _na(ticker: str, asof: str, source: str) -> dict:
    return {
        "ticker": ticker, "pb_current": None, "percentile": None,
        "light": "N/A", "p70": None, "p85": None, "n_days": 0,
        "source": source, "asof": asof,
    }


def compute_pb_light(prices, equity, shares, ticker="", asof="",
                     red=RED_PCT, yellow=YELLOW_PCT) -> dict:
    """Pure: given fetched inputs, return the light dict. Fails safe to N/A."""
    bvps = compute_bvps(equity, shares)
    if not bvps:
        return _na(ticker, asof, "no valid annual book value")
    latest_bvps = bvps[max(bvps)]
    if latest_bvps <= 0:
        return _na(ticker, asof, "non-positive latest book value")
    series = build_pb_series(prices, bvps)
    if len(series) < MIN_DAYS:
        return _na(ticker, asof, f"thin history ({len(series)} days)")
    current_pb = float(prices.iloc[-1]) / latest_bvps
    percentile = pct_rank(series, current_pb)
    return {
        "ticker": ticker,
        "pb_current": round(current_pb, 4),
        "percentile": round(percentile, 1),
        "light": classify(percentile, red, yellow),
        "p70": round(float(series.quantile(yellow / 100.0)), 4),
        "p85": round(float(series.quantile(red / 100.0)), 4),
        "bvps": round(latest_bvps, 4),
        "n_days": int(len(series)),
        "source": "yfinance annual BVPS 5y",
        "asof": asof,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pb_percentile.py -k compute_pb_light -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/pb_percentile.py tests/test_pb_percentile.py
git commit -m "feat(valuation): compute_pb_light orchestrator with N/A fallbacks"
```

---

### Task 5: Cache read/write + `light_from_cutoffs` daily fast path

**Files:**
- Modify: `scripts/pb_percentile.py`
- Test: `tests/test_pb_percentile.py`

- [ ] **Step 1: Write the failing test**

```python
def test_light_from_cutoffs_matches_bands():
    assert pbp.light_from_cutoffs(30.0, p70=20.0, p85=25.0) == "RED"
    assert pbp.light_from_cutoffs(25.0, p70=20.0, p85=25.0) == "RED"    # boundary
    assert pbp.light_from_cutoffs(22.0, p70=20.0, p85=25.0) == "YELLOW"
    assert pbp.light_from_cutoffs(20.0, p70=20.0, p85=25.0) == "YELLOW"  # boundary
    assert pbp.light_from_cutoffs(10.0, p70=20.0, p85=25.0) == "GREEN"


def test_cache_roundtrip(tmp_path):
    p = tmp_path / "cache.json"
    cache = {"2408": {"bvps": 54.99, "p70": 5.0, "p85": 6.5, "asof": "2026-07-09", "n_days": 1214}}
    pbp.save_cache(cache, p)
    loaded = pbp.load_cache(p)
    assert loaded["2408"]["p85"] == 6.5


def test_load_cache_missing_file_returns_empty(tmp_path):
    assert pbp.load_cache(tmp_path / "nope.json") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pb_percentile.py -k "cutoffs or cache" -v`
Expected: FAIL — attributes `light_from_cutoffs` / `save_cache` / `load_cache` do not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/pb_percentile.py`:

```python
def light_from_cutoffs(current_pb: float, p70: float, p85: float) -> str:
    """Fast-path light: compare current P/B to cached absolute cutoffs.

    Equivalent to classify(percentile) because p70/p85 ARE the percentile
    cutoffs of the same historical distribution.
    """
    if current_pb >= p85:
        return "RED"
    if current_pb >= p70:
        return "YELLOW"
    return "GREEN"


def load_cache(path=CACHE_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache: dict, path=CACHE_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pb_percentile.py -k "cutoffs or cache" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/pb_percentile.py tests/test_pb_percentile.py
git commit -m "feat(valuation): cutoff cache + daily fast-path light"
```

---

### Task 6: `pb_light` public entry — fetch + cache orchestration (fetch injected)

**Files:**
- Modify: `scripts/pb_percentile.py`
- Test: `tests/test_pb_percentile.py`

**Design:** `pb_light` takes a `fetcher` parameter defaulting to the real
`fetch_yf`, and a `today` parameter for deterministic staleness tests. Tests
inject a fake fetcher so no network is touched. Cache hit that is fresh uses
`light_from_cutoffs`; miss or stale (> STALE_DAYS old) recomputes via fetcher.

- [ ] **Step 1: Write the failing test**

```python
def _fake_fetcher(prices, equity, shares):
    def _f(ticker):
        return prices, equity, shares
    return _f


def test_pb_light_cache_miss_computes_and_writes(tmp_path):
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    equity = {2022: 1000.0, 2023: 1000.0}
    p = tmp_path / "cache.json"
    res = pbp.pb_light("TEST", cache_path=p, today="2026-07-09",
                       fetcher=_fake_fetcher(prices, equity, 100.0))
    assert res["light"] == "RED"
    assert pbp.load_cache(p)["TEST"]["p85"] > 0        # cutoffs persisted


def test_pb_light_fresh_cache_uses_fast_path(tmp_path):
    p = tmp_path / "cache.json"
    pbp.save_cache({"TEST": {"bvps": 10.0, "p70": 15.0, "p85": 25.0,
                             "asof": "2026-07-08", "n_days": 300}}, p)

    def _boom(ticker):
        raise AssertionError("fetcher must not be called on fresh cache hit")

    res = pbp.pb_light("TEST", latest_close=300.0, cache_path=p,
                       today="2026-07-09", fetcher=_boom)
    assert res["pb_current"] == pytest.approx(30.0)    # 300 / 10
    assert res["light"] == "RED"                        # 30 >= p85 25


def test_pb_light_stale_cache_recomputes(tmp_path):
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    equity = {2022: 1000.0, 2023: 1000.0}
    p = tmp_path / "cache.json"
    pbp.save_cache({"TEST": {"bvps": 10.0, "p70": 15.0, "p85": 25.0,
                             "asof": "2026-06-01", "n_days": 300}}, p)   # >7d old
    res = pbp.pb_light("TEST", cache_path=p, today="2026-07-09",
                       fetcher=_fake_fetcher(prices, equity, 100.0))
    assert res["source"].startswith("yfinance")         # recomputed, not fast path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pb_percentile.py -k pb_light -v`
Expected: FAIL — attribute `pb_light` (and `fetch_yf`) do not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/pb_percentile.py`:

```python
from datetime import date, timedelta


def _days_between(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def fetch_yf(ticker: str):
    """Networked: return (prices: pd.Series, equity: dict[int,float], shares).

    Tries `<ticker>.TW` then `<ticker>.TWO`. Not unit-tested (injected in tests).
    """
    import yfinance as yf

    for suffix in (".TW", ".TWO"):
        t = yf.Ticker(f"{ticker}{suffix}")
        bs = getattr(t, "balance_sheet", None)
        if bs is None or bs.empty or "Stockholders Equity" not in bs.index:
            continue
        eq_row = bs.loc["Stockholders Equity"]
        equity = {ts.year: (None if pd.isna(v) else float(v))
                  for ts, v in eq_row.items()}
        shares = t.info.get("sharesOutstanding")
        px = t.history(period="5y")["Close"]
        if px is None or px.empty:
            continue
        px.index = px.index.tz_localize(None)
        return px, equity, shares
    return pd.Series(dtype=float), {}, None


def pb_light(ticker: str, latest_close: float | None = None,
             cache_path=CACHE_PATH, today: str | None = None,
             fetcher=fetch_yf) -> dict:
    """Public entry. Fresh cache -> fast path; miss/stale -> recompute + persist."""
    today = today or date.today().isoformat()
    cache = load_cache(cache_path)
    entry = cache.get(ticker)

    fresh = (entry and entry.get("asof")
             and _days_between(entry["asof"], today) <= STALE_DAYS
             and entry.get("p85") and entry.get("bvps"))
    if fresh and latest_close is not None:
        current_pb = float(latest_close) / entry["bvps"]
        return {
            "ticker": ticker,
            "pb_current": round(current_pb, 4),
            "percentile": None,   # fast path does not recompute percentile
            "light": light_from_cutoffs(current_pb, entry["p70"], entry["p85"]),
            "p70": entry["p70"], "p85": entry["p85"], "bvps": entry["bvps"],
            "n_days": entry.get("n_days", 0),
            "source": "cache fast-path", "asof": entry["asof"],
        }

    prices, equity, shares = fetcher(ticker)
    res = compute_pb_light(prices, equity, shares, ticker=ticker, asof=today)
    if res["light"] != "N/A":
        cache[ticker] = {
            "bvps": res["bvps"], "p70": res["p70"], "p85": res["p85"],
            "asof": today, "n_days": res["n_days"],
        }
        save_cache(cache, cache_path)
    return res
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pb_percentile.py -k pb_light -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full unit suite**

Run: `python3 -m pytest tests/test_pb_percentile.py -v -k "not live"`
Expected: PASS (all unit tests, no network).

- [ ] **Step 6: Commit**

```bash
git add scripts/pb_percentile.py tests/test_pb_percentile.py
git commit -m "feat(valuation): pb_light entry with cache fast-path + yfinance fetch"
```

---

### Task 7: Live acceptance test — 2408 validates RED (network, skips if offline)

**Files:**
- Modify: `tests/test_pb_percentile.py`

**Purpose:** The spec's core correctness anchor — 2408's current P/B must land
in the top percentiles (RED), reproducing the validated 2026-06-25 signal.
Marked `live`; skips gracefully when yfinance is unreachable so CI stays green
offline.

- [ ] **Step 1: Write the test**

```python
@pytest.mark.live
def test_live_2408_is_red(tmp_path):
    try:
        res = pbp.pb_light("2408", cache_path=tmp_path / "c.json", today="2026-07-09")
    except Exception as e:
        pytest.skip(f"network/yfinance unavailable: {e}")
    if res["light"] == "N/A":
        pytest.skip(f"yfinance returned no data: {res['source']}")
    assert res["pb_current"] > 5.0             # elevated regime
    assert res["percentile"] >= 85.0           # top of 5y history
    assert res["light"] == "RED"
```

- [ ] **Step 2: Register the `live` marker**

Create `pytest.ini` in repo root ONLY if it does not already exist:

```ini
[pytest]
markers =
    live: test hits the network (yfinance); skips if unreachable
```

If `pytest.ini` already exists, add just the `live:` line under `markers =`.

- [ ] **Step 3: Run the live test**

Run: `python3 -m pytest tests/test_pb_percentile.py -k live -v`
Expected: PASS (2408 percentile ≥ 85, light RED) — or SKIP if offline.

- [ ] **Step 4: Commit**

```bash
git add tests/test_pb_percentile.py pytest.ini
git commit -m "test(valuation): live 2408 P/B percentile RED acceptance anchor"
```

---

### Task 8: CLI entry for manual/ops use

**Files:**
- Modify: `scripts/pb_percentile.py`

- [ ] **Step 1: Write the failing test**

```python
def test_main_prints_light(capsys, tmp_path, monkeypatch):
    prices = _linear_prices("2023-01-02", "2024-12-31", 300, 100.0, 300.0)
    equity = {2022: 1000.0, 2023: 1000.0}
    monkeypatch.setattr(pbp, "fetch_yf", _fake_fetcher(prices, equity, 100.0))
    rc = pbp.main(["TEST", "--cache", str(tmp_path / "c.json"), "--today", "2026-07-09"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "TEST" in out and "RED" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pb_percentile.py -k main -v`
Expected: FAIL — attribute `main` does not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/pb_percentile.py`:

```python
import argparse


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P/B historical-percentile light per ticker")
    ap.add_argument("tickers", nargs="+", help="bare tickers, e.g. 2408 2344")
    ap.add_argument("--cache", default=str(CACHE_PATH))
    ap.add_argument("--today", default=None)
    args = ap.parse_args(argv)
    for tk in args.tickers:
        r = pb_light(tk, cache_path=args.cache, today=args.today, fetcher=fetch_yf)
        pct = "N/A" if r["percentile"] is None else f"{r['percentile']}"
        print(f"{r['ticker']}: P/B={r['pb_current']} pct={pct} -> {r['light']}  ({r['source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pb_percentile.py -k main -v`
Expected: PASS.

- [ ] **Step 5: Full suite + real smoke run**

Run: `python3 -m pytest tests/test_pb_percentile.py -v`
Expected: all PASS (live may SKIP if offline).

Run: `python3 scripts/pb_percentile.py 2408 2344 3037 3017 2455`
Expected: each prints a RED line (matches spec reference table).

- [ ] **Step 6: Commit**

```bash
git add scripts/pb_percentile.py tests/test_pb_percentile.py
git commit -m "feat(valuation): pb_percentile CLI entry"
```

---

## Self-Review

**Spec coverage:**
- Data source (annual equity/shares/5y close) → Task 6 `fetch_yf`. ✅
- Algorithm steps 1–5 (BVPS drop-NaN, as-of series, current_pb basis, percentile, bands) → Tasks 1–4. ✅
- Thresholds 85/70 configurable → Task 3 `classify` defaults `RED_PCT`/`YELLOW_PCT`. ✅
- Interface `pb_light(...) -> dict` with all documented keys → Tasks 4 + 6. ✅
- Caching (cutoffs, weekly staleness, daily fast path) → Tasks 5 + 6 (`STALE_DAYS=7`). ✅
- Error/fallback table (N/A on missing equity / bad shares / negative BVPS / thin history / network) → Task 4 + `fetch_yf` returning empties. ✅
- Acceptance tests 1–5: NaN handling (Task 1), basis consistency (Task 4 `pb_current == 300/10`), fallback N/A (Task 4), 2408 RED (Task 7). Cross-sector spread (#5) is validated by the Task 8 smoke run against the reference table. ✅
- Known limitation (current shares applied to history): inherent in `fetch_yf` using `sharesOutstanding`; documented in spec, no task needed. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✅

**Type consistency:** `compute_bvps`, `build_pb_series`, `pct_rank`, `classify`, `compute_pb_light`, `light_from_cutoffs`, `load_cache`/`save_cache`, `fetch_yf`, `pb_light`, `main` — names and signatures consistent across tasks. Dict keys (`light`, `pb_current`, `percentile`, `p70`, `p85`, `bvps`, `n_days`, `source`, `asof`) consistent between Task 4 and Task 6. ✅

**Note for executor:** `pb_light` fast path returns `percentile: None` (cutoffs give the light without recomputing rank) — this is intentional and matches the Task 6 fast-path test. Sub-project C should rely on `light`, not `percentile`, for the 減碼 rule.
