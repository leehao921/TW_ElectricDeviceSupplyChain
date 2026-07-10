# Options Quant Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/options_quant.py` — the 4-angle TXO intraday options quant analyzer specced in `docs/plans/2026-07-09-options-quant-spec.md` (GEX, IV-vs-RV/VRP, term/skew dynamics, PCR/OI flow → rule-based vol environment labels, markdown report).

**Architecture:** Single script, three layers: data-access (`fetch_*`, the only I/O), four pure analysis functions returning `Section = {"metrics": dict, "verdict": str, "verification": list[str]}`, and a report layer (labels + markdown). Tests hit only the pure layer with synthetic DataFrames.

**Tech Stack:** Python 3.9 (repo system python — has pandas/psycopg2/pytest; NO 3.10+ syntax: no `X | Y` unions, no match), pandas, psycopg2. Tests in `tests/test_options_quant.py` following existing `tests/` conventions (conftest.py exists). Run tests: `python3 -m pytest tests/test_options_quant.py -v` from repo root.

**Repo & branch:** `/Users/lulala/Documents/coding/My-TW-Coverage`. Create branch `feat/options-quant` from current HEAD before Task 1. The working tree has the user's uncommitted Pilot_Reports changes — NEVER `git add -A`; add ONLY the files this plan names. Commits touch only `scripts/options_quant.py` and `tests/test_options_quant.py`.

**Verified schema facts (2026-07-09/10, live DB `tmf_market_data` via `docker exec trading-timescaledb psql -U tmf`):**
- `iv_metrics` (raw, ~10s): `time, underlying, expiry, atm_iv, iv_skew_25d, near_month_iv, far_month_iv, iv_term_slope, avg_delta, avg_gamma, avg_theta, avg_vega, points_count, underlying_price, product_code, skew_25d, rr_25d, pcr_volume`. `expiry` is text `YYYYMMDD`.
- `iv_strikes` (~10s): `time, product_code, expiry, strike, call_put, price, iv, delta, gamma, theta, vega, volume, source`. `call_put` is 'C'/'P'.
- `option_oi_daily`: `settle_date (date), underlying, expiry (date), strike, cp ('C'/'P'), open_interest, volume, settle_price`. **`underlying` 值是 `'TX'`**（live 驗證 556,792 rows；`'TXO'` 為 0 rows — Task 1 審查抓到）。
- `ohlcv_1m`: `bucket, symbol, open, high, low, close, volume`. TXF rows present and fresh.
- DB conn convention (copy from `scripts/etf_smart_money.py:36-40`): env-driven dict `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`, defaults `localhost/5432/tmf/tmf_dev_2026/tmf_market_data`, `psycopg2.connect(**DB_CONFIG)`.

**Sequence:** Task 1 (skeleton + shared pure helpers) → Task 2 (GEX) → Task 3 (IV-RV/VRP) → Task 4 (term/skew + flow) → Task 5 (labels + report + main + live smoke).

---

## Task 1: Skeleton, shared pure helpers, data-access layer

**Files:**
- Create: `scripts/options_quant.py`
- Create: `tests/test_options_quant.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_options_quant.py`:

```python
"""Tests for scripts/options_quant.py — pure analysis layer only (no DB)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import options_quant as oq


class TestParseWindow:
    def test_parses_hhmm_range(self):
        assert oq.parse_window("09:00-12:00") == ("09:00", "12:00")

    def test_rejects_bad_format(self):
        with pytest.raises(ValueError):
            oq.parse_window("9am-noon")

    def test_rejects_inverted(self):
        with pytest.raises(ValueError):
            oq.parse_window("12:00-09:00")


class TestSelectFrontExpiry:
    def test_picks_shortest_tenor_with_data(self):
        df = pd.DataFrame({
            "expiry": ["20260715", "20260819", "20260916"],
            "n": [120, 118, 90],
        })
        assert oq.select_front_expiry(df, min_rows=10) == "20260715"

    def test_skips_expiry_with_too_few_rows(self):
        df = pd.DataFrame({"expiry": ["20260715", "20260819"], "n": [3, 200]})
        assert oq.select_front_expiry(df, min_rows=10) == "20260819"

    def test_empty_returns_none(self):
        assert oq.select_front_expiry(pd.DataFrame({"expiry": [], "n": []}), min_rows=10) is None


class TestPercentileWithVerification:
    def test_percentile_and_log(self):
        hist = pd.Series([1.0, 2.0, 3.0, 4.0] * 15)  # n=60
        pct, log = oq.percentile_verified(3.5, hist, metric_name="VRP")
        assert 70 <= pct <= 80
        assert any("n=60" in line for line in log)

    def test_insufficient_history_returns_none(self):
        hist = pd.Series([1.0] * 19)  # n=19 < 20
        pct, log = oq.percentile_verified(3.5, hist, metric_name="VRP")
        assert pct is None
        assert any("insufficient-history(n=19)" in line for line in log)

    def test_small_but_usable_history_flags_n(self):
        hist = pd.Series(list(range(30)))  # 20 <= n < 60
        pct, log = oq.percentile_verified(15, hist, metric_name="VRP")
        assert pct is not None
        assert any("n=30" in line for line in log)
```

- [ ] **Step 2: Verify FAIL** — `python3 -m pytest tests/test_options_quant.py -v` from repo root. Expected: `ModuleNotFoundError`/`AttributeError`.

- [ ] **Step 3: Implement** — create `scripts/options_quant.py` with module docstring (purpose, spec link, usage), then:

```python
#!/usr/bin/env python3
"""TXO 選擇權盤中量化分析 — GEX / IV-RV / term-skew / PCR-OI flow.

Spec: docs/plans/2026-07-09-options-quant-spec.md
Usage: python3 scripts/options_quant.py --date 2026-07-09 --window 09:00-12:00
Read-only vs trading-timescaledb. No trade directives — environment labels only.
"""
import argparse
import os
import re
import sys
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd

DB_CONFIG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5432")),
    user=os.environ.get("DB_USER", "tmf"),
    password=os.environ.get("DB_PASSWORD", "tmf_dev_2026"),
    dbname=os.environ.get("DB_NAME", "tmf_market_data"),
)

TZ = "Asia/Taipei"
CONTRACT_MULTIPLIER = 50
HISTORY_DAYS = 60           # percentile lookback (trading days)
MIN_HISTORY = 20            # below this: no percentile, no distributional adjectives
GAP_MINUTES = 5             # window gap threshold for DATA GAP flag


def parse_window(s):
    """'HH:MM-HH:MM' -> (start, end). Raises ValueError on bad/inverted input."""
    m = re.fullmatch(r"(\d{2}:\d{2})-(\d{2}:\d{2})", s)
    if not m:
        raise ValueError(f"window must be HH:MM-HH:MM, got {s!r}")
    start, end = m.group(1), m.group(2)
    if start >= end:
        raise ValueError(f"window start must precede end: {s!r}")
    return start, end


def select_front_expiry(counts_df, min_rows=10):
    """Pick shortest-tenor expiry with enough window rows.

    counts_df: DataFrame[expiry(YYYYMMDD str), n(row count)]. Sorted lexically
    == sorted by date for YYYYMMDD. Settlement weeks need no special case —
    whatever near expiry has data wins (spec §2).
    """
    if counts_df.empty:
        return None
    ok = counts_df[counts_df["n"] >= min_rows]
    if ok.empty:
        return None
    return sorted(ok["expiry"].tolist())[0]


def percentile_verified(value, history, metric_name):
    """Return (percentile 0-100 or None, verification log lines).

    Golden Rule 0: distributional adjectives require this to have run.
    n < MIN_HISTORY -> (None, log with 'insufficient-history(n=X)').
    """
    n = int(history.dropna().shape[0])
    if n < MIN_HISTORY:
        return None, [f"{metric_name}: insufficient-history(n={n}) — "
                      f"percentile unavailable, distributional adjectives forbidden"]
    pct = float((history.dropna() < value).mean() * 100.0)
    log = [f"{metric_name}: value={value:.4f} percentile={pct:.0f} vs same-window "
           f"history n={n} (rank = share of history strictly below value)"]
    return pct, log
```

Then the data-access layer (I/O only, no logic — each returns a DataFrame; NOT unit-tested, exercised by the Task 5 live smoke):

```python
def _connect():
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def fetch_iv_metrics(conn, date_str, start, end):
    """Raw iv_metrics rows for all TXO-family expiries in the window."""
    sql = """
        SELECT time, expiry, product_code, atm_iv, skew_25d, rr_25d,
               pcr_volume, iv_term_slope, underlying_price
        FROM iv_metrics
        WHERE underlying='TX'
          AND time >= %(t0)s::timestamptz AND time < %(t1)s::timestamptz
        ORDER BY time
    """
    t0 = f"{date_str} {start}:00+08"
    t1 = f"{date_str} {end}:00+08"
    return pd.read_sql(sql, conn, params={"t0": t0, "t1": t1})


def fetch_strikes_snapshot(conn, date_str, end, expiry):
    """Latest per-(strike, cp) iv_strikes rows at/before window end for expiry."""
    sql = """
        SELECT DISTINCT ON (strike, call_put)
               strike, call_put, iv, gamma, delta, volume
        FROM iv_strikes
        WHERE expiry = %(expiry)s
          AND time <= %(t1)s::timestamptz AND time >= %(t1)s::timestamptz - interval '15 minutes'
        ORDER BY strike, call_put, time DESC
    """
    return pd.read_sql(sql, conn, params={"expiry": expiry, "t1": f"{date_str} {end}:00+08"})


def fetch_oi(conn, expiry_yyyymmdd, before_date=None):
    """Latest settle-day OI per (strike, cp) for expiry; before_date bounds settle_date."""
    sql = """
        SELECT strike, cp, open_interest, settle_date
        FROM option_oi_daily
        WHERE underlying='TX' AND expiry = %(expiry)s::date
          AND settle_date = (
            SELECT max(settle_date) FROM option_oi_daily
            WHERE underlying='TX' AND expiry = %(expiry)s::date
              AND (%(before)s::date IS NULL OR settle_date < %(before)s::date)
          )
    """
    exp_date = f"{expiry_yyyymmdd[:4]}-{expiry_yyyymmdd[4:6]}-{expiry_yyyymmdd[6:]}"
    return pd.read_sql(sql, conn, params={"expiry": exp_date, "before": before_date})


def fetch_txf_bars(conn, date_str, start, end):
    sql = """
        SELECT bucket, open, high, low, close FROM ohlcv_1m
        WHERE symbol='TXF'
          AND bucket >= %(t0)s::timestamptz AND bucket < %(t1)s::timestamptz
        ORDER BY bucket
    """
    return pd.read_sql(sql, conn, params={"t0": f"{date_str} {start}:00+08",
                                          "t1": f"{date_str} {end}:00+08"})


def fetch_vrp_history(conn, date_str, start, end, days=HISTORY_DAYS):
    """Per-day same-window (ATM IV mean, RV) for the past `days` trading days
    BEFORE date_str. One SQL per source, joined in pandas by day."""
    iv_sql = """
        SELECT (time at time zone 'Asia/Taipei')::date AS d, avg(atm_iv) AS iv_mean
        FROM iv_metrics
        WHERE underlying='TX' AND product_code='TXO'
          AND (time at time zone 'Asia/Taipei')::date < %(d)s::date
          AND (time at time zone 'Asia/Taipei')::date >= %(d)s::date - %(days)s * interval '1 day' * 2
          AND (time at time zone 'Asia/Taipei')::time >= %(s)s::time
          AND (time at time zone 'Asia/Taipei')::time <  %(e)s::time
          AND expiry = (SELECT min(expiry) FROM iv_metrics m2
                        WHERE m2.underlying='TX' AND m2.product_code='TXO'
                          AND (m2.time at time zone 'Asia/Taipei')::date
                            = (iv_metrics.time at time zone 'Asia/Taipei')::date)
        GROUP BY 1 ORDER BY 1 DESC LIMIT %(days)s
    """
    bars_sql = """
        SELECT (bucket at time zone 'Asia/Taipei')::date AS d,
               (bucket at time zone 'Asia/Taipei')::time AS t, close
        FROM ohlcv_1m
        WHERE symbol='TXF'
          AND (bucket at time zone 'Asia/Taipei')::date < %(d)s::date
          AND (bucket at time zone 'Asia/Taipei')::date >= %(d)s::date - %(days)s * interval '1 day' * 2
          AND (bucket at time zone 'Asia/Taipei')::time >= %(s)s::time
          AND (bucket at time zone 'Asia/Taipei')::time <  %(e)s::time
        ORDER BY d, t
    """
    p = {"d": date_str, "s": f"{start}:00", "e": f"{end}:00", "days": days}
    return pd.read_sql(iv_sql, conn, params=p), pd.read_sql(bars_sql, conn, params=p)
```

> Note for implementer: `pd.read_sql` with psycopg2 emits a UserWarning (non-SQLAlchemy connection) — suppress once at module level with `warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")`. The nested-subquery front-expiry filter in `fetch_vrp_history`'s iv_sql selects each day's own nearest expiry (correlated min) — if it proves too slow in the Task 5 smoke (>30s), simplify to fetching all expiries and doing per-day min-expiry selection in pandas; note the change in your report.

- [ ] **Step 4: Verify PASS** — `python3 -m pytest tests/test_options_quant.py -v`. Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/options_quant.py tests/test_options_quant.py
git commit -m "feat(quant): options_quant skeleton — window/expiry/percentile helpers + data layer

Pure helpers (parse_window, select_front_expiry, percentile_verified with
Golden-Rule-0 verification logging) plus the read-only data-access layer.
Spec: docs/plans/2026-07-09-options-quant-spec.md

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: analyze_gex

**Files:** Modify both files from Task 1.

- [ ] **Step 1: Failing tests** — append:

```python
def _mk_strikes(rows):
    return pd.DataFrame(rows, columns=["strike", "call_put", "iv", "gamma", "delta", "volume"])


def _mk_oi(rows):
    return pd.DataFrame(rows, columns=["strike", "cp", "open_interest", "settle_date"])


class TestAnalyzeGex:
    def test_flip_between_put_and_call_mass(self):
        strikes = _mk_strikes([
            (45000, "P", 0.30, 0.0002, -0.4, 100),
            (45000, "C", 0.30, 0.0002, 0.6, 100),
            (46000, "P", 0.28, 0.0001, -0.2, 50),
            (46000, "C", 0.28, 0.0003, 0.4, 50),
        ])
        oi = _mk_oi([
            (45000, "P", 20000, "2026-07-08"),  # big put OI low  -> negative GEX below
            (45000, "C", 1000, "2026-07-08"),
            (46000, "P", 500, "2026-07-08"),
            (46000, "C", 15000, "2026-07-08"),  # big call OI high -> positive GEX above
        ])
        sec = oq.analyze_gex(strikes, oi, spot=45500.0)
        m = sec["metrics"]
        assert m["flip"] is not None and 45000 < m["flip"] <= 46000
        assert m["total_gex"] != 0
        assert len(m["top_strikes"]) <= 5
        assert "T+1" in " ".join(sec["verification"])  # OI staleness disclosed

    def test_spot_below_flip_is_expansion_zone(self):
        strikes = _mk_strikes([(45000, "P", 0.3, 0.0002, -0.4, 10),
                               (46000, "C", 0.3, 0.0002, 0.4, 10)])
        oi = _mk_oi([(45000, "P", 30000, "2026-07-08"),
                     (46000, "C", 30000, "2026-07-08")])
        sec = oq.analyze_gex(strikes, oi, spot=44000.0)
        assert sec["metrics"]["zone"] == "expansion"

    def test_empty_inputs_yield_data_gap(self):
        sec = oq.analyze_gex(_mk_strikes([]), _mk_oi([]), spot=45000.0)
        assert sec["metrics"]["total_gex"] is None
        assert "DATA GAP" in sec["verdict"]
```

- [ ] **Step 2: Verify FAIL.**

- [ ] **Step 3: Implement** in `scripts/options_quant.py`:

```python
def analyze_gex(strikes_df, oi_df, spot):
    """GEX per spec §3.1. Naive dealer convention: call OI +gamma, put OI -gamma.

    GEX(K) = gamma * OI * MULTIPLIER * spot^2 * 0.01  (NTD per 1% move)
    Flip = zero-crossing of cumulative GEX over strikes (ascending).
    zone: 'pinning' if spot in positive-cumulative region (>= flip), else 'expansion'.
    """
    empty = {"metrics": {"total_gex": None, "flip": None, "zone": None, "top_strikes": []},
             "verdict": "GEX: DATA GAP — no strikes/OI rows in window",
             "verification": []}
    if strikes_df.empty or oi_df.empty:
        return empty
    df = strikes_df.merge(oi_df, left_on=["strike", "call_put"],
                          right_on=["strike", "cp"], how="inner")
    if df.empty:
        return empty
    sign = df["call_put"].map({"C": 1.0, "P": -1.0})
    df = df.assign(gex=df["gamma"] * df["open_interest"] * CONTRACT_MULTIPLIER
                        * spot * spot * 0.01 * sign)
    by_k = df.groupby("strike")["gex"].sum().sort_index()
    cum = by_k.cumsum()
    flip = None
    prev_k, prev_v = None, None
    for k, v in cum.items():
        if prev_v is not None and prev_v < 0 <= v:
            flip = float(k)
            break
        prev_k, prev_v = k, v
    total = float(by_k.sum())
    zone = None
    if flip is not None:
        zone = "pinning" if spot >= flip else "expansion"
    elif total > 0:
        zone = "pinning"
    elif total < 0:
        zone = "expansion"
    top = (by_k.abs().sort_values(ascending=False).head(5).index.astype(float).tolist())
    settle = str(oi_df["settle_date"].iloc[0])
    verdict = (f"總 GEX {total/1e8:.2f} 億/1%; flip={flip}; spot={spot:.0f} → "
               f"{'磁吸區 (pinning)' if zone == 'pinning' else '放大區 (expansion)'}")
    verification = [
        f"GEX assumptions: naive dealer sign (call +, put -); OI from settle {settle} (T+1 approximation); "
        f"gamma from window-end iv_strikes snapshot; multiplier {CONTRACT_MULTIPLIER}",
    ]
    return {"metrics": {"total_gex": total, "flip": flip, "zone": zone,
                        "top_strikes": top},
            "verdict": verdict, "verification": verification}
```

- [ ] **Step 4: Verify PASS** (12 total). **Step 5: Commit** (`feat(quant): GEX analyzer — flip, zone, top strikes`).

---

## Task 3: analyze_iv_rv (VRP)

**Files:** Modify both files.

> **Like-for-like 決策（Task 1 審查 issue 2）:** VRP 的當日 ATM IV 序列必須限定 `product_code='TXO'`（月選 front），與 `fetch_vrp_history` 的 TXO-only 歷史同 product 比較 — 否則非結算週的 nearest 是 TX2 週選，跟月選歷史分布比是 apples-to-oranges，會偏置 §4 標籤。main() 組裝時（Task 5）對 VRP 用 TXO-filtered series；GEX（§3.1，無 percentile）照用 nearest live expiry。

> **Like-for-like 決策（Task 1 審查 issue 2）:** VRP 的當日 ATM IV 序列必須限定 `product_code='TXO'`（月選 front），與 `fetch_vrp_history` 的 TXO-only 歷史同 product 比較 — 否則結算週外的近月是 TX2 週選，跟月選歷史分布比是 apples-to-oranges，會偏置 §4 標籤。main() 組裝時（Task 5）對 VRP 用 TXO-filtered series；GEX（§3.1，無 percentile）照用 nearest live expiry。

- [ ] **Step 1: Failing tests** — append:

```python
import numpy as np


def _mk_bars(closes, date="2026-07-09"):
    idx = pd.date_range(f"{date} 09:00", periods=len(closes), freq="1min", tz="Asia/Taipei")
    c = pd.Series(closes, index=idx)
    return pd.DataFrame({"bucket": idx, "open": c.values, "high": c.values * 1.0005,
                         "low": c.values * 0.9995, "close": c.values})


class TestAnalyzeIvRv:
    def test_flat_prices_give_zero_rv_positive_vrp(self):
        bars = _mk_bars([45000.0] * 180)
        atm = pd.Series([0.30] * 180)
        hist = pd.DataFrame({"vrp": np.linspace(-0.05, 0.25, 60)})
        sec = oq.analyze_iv_rv(atm, bars, hist)
        m = sec["metrics"]
        assert m["rv"] == pytest.approx(0.0, abs=1e-9)
        assert m["vrp"] == pytest.approx(0.30, abs=1e-6)
        assert m["percentile"] is not None
        assert any("percentile" in v for v in sec["verification"])

    def test_no_adjective_without_history(self):
        bars = _mk_bars([45000, 45100, 44950, 45200] * 45)
        atm = pd.Series([0.30] * 180)
        hist = pd.DataFrame({"vrp": [0.1] * 5})  # n=5 < 20
        sec = oq.analyze_iv_rv(atm, bars, hist)
        assert sec["metrics"]["percentile"] is None
        assert "insufficient-history" in " ".join(sec["verification"])
        for word in ("貴", "便宜", "極端", "罕見"):
            assert word not in sec["verdict"]

    def test_empty_bars_data_gap(self):
        sec = oq.analyze_iv_rv(pd.Series([0.3]), _mk_bars([]), pd.DataFrame({"vrp": []}))
        assert "DATA GAP" in sec["verdict"]
```

- [ ] **Step 2: Verify FAIL.**

- [ ] **Step 3: Implement**:

```python
import numpy as np


def realized_vol_annualized(closes, bars_per_day):
    """Close-to-close annualized RV from a 1m close series (window subset).

    sigma = std of 1m log returns (population) * sqrt(252 * bars_per_day).
    """
    r = np.diff(np.log(closes.astype(float)))
    if r.size == 0:
        return None
    return float(np.sqrt(np.mean(r * r)) * np.sqrt(252.0 * bars_per_day))


def analyze_iv_rv(atm_iv_series, txf_bars, history_df):
    """VRP = mean window ATM IV - window annualized RV. Percentile vs
    same-window history (history_df['vrp']). Spec §3.2 + Golden Rule 0."""
    if txf_bars.empty or atm_iv_series.dropna().empty:
        return {"metrics": {"rv": None, "iv": None, "vrp": None, "percentile": None},
                "verdict": "IV-RV: DATA GAP — missing bars or ATM IV in window",
                "verification": []}
    closes = txf_bars["close"]
    bars_per_day = max(len(closes), 1)
    rv = realized_vol_annualized(closes, bars_per_day=270)  # 09:00-13:30 ≈ 270 1m bars
    iv_mean = float(atm_iv_series.dropna().mean())
    vrp = iv_mean - rv
    pct, vlog = percentile_verified(vrp, history_df.get("vrp", pd.Series(dtype=float)),
                                    metric_name="VRP")
    if pct is None:
        verdict = f"VRP {vrp*100:+.1f} vol pts (IV {iv_mean*100:.1f} vs RV {rv*100:.1f})"
    else:
        rich = "選擇權相對已實現波動偏貴" if pct >= 70 else (
               "選擇權相對已實現波動偏便宜" if pct <= 30 else "VRP 居中")
        verdict = (f"VRP {vrp*100:+.1f} vol pts (IV {iv_mean*100:.1f} vs RV {rv*100:.1f}),"
                   f" 60 日同窗 percentile {pct:.0f} → {rich}")
    return {"metrics": {"rv": rv, "iv": iv_mean, "vrp": vrp, "percentile": pct},
            "verdict": verdict, "verification": vlog}
```

> Note (superseded during review: constant corrected to **300** — TXF day session 08:45-13:45; the 270 below referenced the TWSE cash session by mistake): `bars_per_day=270` annualization is fixed to the full-session bar count regardless of window length — RV over a 3h window annualizes with the same per-bar variance scale. Parkinson variant: optional; if trivial add `rv_parkinson` to metrics, else note as skipped (YAGNI).

- [ ] **Step 4: Verify PASS.** **Step 5: Commit** (`feat(quant): IV-vs-RV analyzer — VRP with verified percentile`).

---

## Task 4: analyze_term_skew + analyze_flow

**Files:** Modify both files.

- [ ] **Step 1: Failing tests** — append:

```python
def _mk_metrics(n=180, skew_start=0.05, skew_end=0.05, date="2026-07-09"):
    idx = pd.date_range(f"{date} 09:00", periods=n, freq="1min", tz="Asia/Taipei")
    return pd.DataFrame({
        "time": idx,
        "atm_iv": np.linspace(0.32, 0.30, n),
        "skew_25d": np.linspace(skew_start, skew_end, n),
        "rr_25d": -np.linspace(skew_start, skew_end, n),
        "pcr_volume": np.linspace(0.8, 1.1, n),
        "iv_term_slope": np.full(n, -0.03),
        "underlying_price": np.linspace(45800, 45500, n),
    })


class TestAnalyzeTermSkew:
    def test_deltas_and_percentile(self):
        df = _mk_metrics(skew_start=0.04, skew_end=0.12)
        hist = pd.DataFrame({"skew_delta": np.linspace(-0.02, 0.03, 60)})
        sec = oq.analyze_term_skew(df, hist)
        m = sec["metrics"]
        assert m["skew_delta"] == pytest.approx(0.08, abs=1e-6)
        assert m["skew_delta_pct"] == 100.0  # 0.08 above entire history
        assert m["atm_iv_delta"] == pytest.approx(-0.02, abs=1e-6)

    def test_data_gap_flag(self):
        df = _mk_metrics(n=30)
        df = pd.concat([df.iloc[:10], df.iloc[25:]])  # 15-min hole
        sec = oq.analyze_term_skew(df, pd.DataFrame({"skew_delta": []}))
        assert "DATA GAP" in sec["verdict"]


class TestAnalyzeFlow:
    def test_oi_delta_top_strikes(self):
        oi_now = _mk_oi([(45000, "P", 25000, "2026-07-09"), (45500, "C", 8000, "2026-07-09"),
                         (46000, "C", 12000, "2026-07-09")])
        oi_prev = _mk_oi([(45000, "P", 10000, "2026-07-08"), (45500, "C", 9000, "2026-07-08"),
                          (46000, "C", 5000, "2026-07-08")])
        df = _mk_metrics()
        sec = oq.analyze_flow(df, oi_now, oi_prev)
        m = sec["metrics"]
        builds = dict((k, v) for k, v, cp in m["top_oi_builds"])
        assert builds.get(45000.0) == 15000
        assert m["pcr_mean"] == pytest.approx(0.95, abs=0.01)

    def test_missing_prev_oi_noted(self):
        sec = oq.analyze_flow(_mk_metrics(), _mk_oi([(45000, "P", 100, "2026-07-09")]), _mk_oi([]))
        assert "無前日 OI" in sec["verdict"] or "no prior OI" in sec["verdict"]
```

- [ ] **Step 2: Verify FAIL.**

- [ ] **Step 3: Implement**:

```python
def _window_gaps(times, gap_minutes=GAP_MINUTES):
    """Return list of (start, end) gaps > gap_minutes in a time series."""
    t = pd.Series(pd.to_datetime(times)).sort_values()
    dt = t.diff()
    gaps = []
    for i, d in enumerate(dt):
        if pd.notna(d) and d > pd.Timedelta(minutes=gap_minutes):
            gaps.append((t.iloc[i - 1], t.iloc[i]))
    return gaps


def analyze_term_skew(metrics_df, history_df):
    """Window deltas + path extremes for ATM IV / skew_25d / term slope. Spec §3.3."""
    if metrics_df.empty:
        return {"metrics": {}, "verdict": "TERM/SKEW: DATA GAP — no iv_metrics rows",
                "verification": []}
    df = metrics_df.dropna(subset=["atm_iv"]).sort_values("time")
    gaps = _window_gaps(df["time"])
    skew = df["skew_25d"].dropna()
    skew_delta = float(skew.iloc[-1] - skew.iloc[0]) if len(skew) >= 2 else None
    atm_delta = float(df["atm_iv"].iloc[-1] - df["atm_iv"].iloc[0])
    slope_last = float(df["iv_term_slope"].dropna().iloc[-1]) if df["iv_term_slope"].notna().any() else None
    pct, vlog = (None, [])
    if skew_delta is not None:
        pct, vlog = percentile_verified(skew_delta,
                                        history_df.get("skew_delta", pd.Series(dtype=float)),
                                        metric_name="skew_25d window delta")
    verdict = (f"ATM IV Δ {atm_delta*100:+.1f} pts; skew_25d Δ "
               f"{(skew_delta or 0)*100:+.2f} (pct {pct if pct is not None else 'n/a'}); "
               f"term slope {slope_last}")
    if gaps:
        gap_txt = ", ".join(f"{a:%H:%M}–{b:%H:%M}" for a, b in gaps)
        verdict = f"DATA GAP {gap_txt} | " + verdict
    return {"metrics": {"atm_iv_delta": atm_delta, "skew_delta": skew_delta,
                        "skew_delta_pct": pct, "term_slope": slope_last,
                        "atm_iv_path_max": float(df["atm_iv"].max()),
                        "atm_iv_path_min": float(df["atm_iv"].min())},
            "verdict": verdict, "verification": vlog}


def analyze_flow(metrics_df, oi_now, oi_prev):
    """PCR path + per-strike OI build/unwind. Spec §3.4."""
    pcr = metrics_df["pcr_volume"].dropna() if not metrics_df.empty else pd.Series(dtype=float)
    pcr_mean = float(pcr.mean()) if not pcr.empty else None
    builds = []
    note = ""
    if oi_prev.empty or oi_now.empty:
        note = "無前日 OI 可比 (no prior OI)"
    else:
        merged = oi_now.merge(oi_prev, on=["strike", "cp"], how="outer",
                              suffixes=("_now", "_prev")).fillna({"open_interest_now": 0,
                                                                  "open_interest_prev": 0})
        merged["d_oi"] = merged["open_interest_now"] - merged["open_interest_prev"]
        top = merged.reindex(merged["d_oi"].abs().sort_values(ascending=False).index).head(5)
        builds = [(float(r.strike), int(r.d_oi), str(r.cp)) for r in top.itertuples()]
    verdict = f"PCR(vol) mean {pcr_mean}; top ΔOI: {builds[:3]}"
    if note:
        verdict += f" | {note}"
    return {"metrics": {"pcr_mean": pcr_mean, "top_oi_builds": builds},
            "verdict": verdict, "verification": []}
```

- [ ] **Step 4: Verify PASS.** **Step 5: Commit** (`feat(quant): term/skew + PCR/OI flow analyzers`).

---

## Task 5: Labels, report, main(), live smoke

**Files:** Modify both files.

- [ ] **Step 1: Failing tests** — append:

```python
class TestVolLabels:
    def _sections(self, gex_total, vrp_pct, skew_pct):
        return {
            "gex": {"metrics": {"total_gex": gex_total, "flip": 45500, "zone": None,
                                "top_strikes": []}},
            "iv_rv": {"metrics": {"percentile": vrp_pct}},
            "term_skew": {"metrics": {"skew_delta_pct": skew_pct}},
        }

    def test_expansion_risk(self):
        assert "expansion-risk" in oq.vol_labels(self._sections(-1e9, 20, 50))

    def test_premium_rich_pinning(self):
        assert "premium-rich-pinning" in oq.vol_labels(self._sections(+1e9, 80, 50))

    def test_hedging_bid(self):
        assert "hedging-bid" in oq.vol_labels(self._sections(+1e9, 50, 85))

    def test_neutral_fallback(self):
        assert oq.vol_labels(self._sections(+1e9, 50, 50)) == ["neutral-carry"]

    def test_none_inputs_neutral(self):
        assert oq.vol_labels(self._sections(None, None, None)) == ["neutral-carry"]


class TestRender:
    def test_report_contains_required_sections(self):
        secs = {
            "gex": {"metrics": {"total_gex": 1e9, "flip": 45500.0, "zone": "pinning",
                                "top_strikes": [45500.0]},
                    "verdict": "v1", "verification": ["a1"]},
            "iv_rv": {"metrics": {"rv": 0.2, "iv": 0.3, "vrp": 0.1, "percentile": 75.0},
                      "verdict": "v2", "verification": ["a2"]},
            "term_skew": {"metrics": {"skew_delta_pct": 50.0}, "verdict": "v3",
                          "verification": ["a3"]},
            "flow": {"metrics": {"pcr_mean": 0.9, "top_oi_builds": []},
                     "verdict": "v4", "verification": []},
        }
        md = oq.render_report("2026-07-09", "09:00-12:00", secs, ["premium-rich-pinning"])
        for needle in ("# TXO", "GEX", "IV vs RV", "Term / Skew", "資金流",
                       "premium-rich-pinning", "Verification log", "a1", "a2",
                       "不出買賣指令"):
            assert needle in md
```

- [ ] **Step 2: Verify FAIL.**

- [ ] **Step 3: Implement** `vol_labels`, `render_report`, `main`:

```python
LABEL_RULES = (
    ("expansion-risk", "總 GEX < 0 且 VRP percentile < 30"),
    ("premium-rich-pinning", "總 GEX > 0 且 VRP percentile > 70"),
    ("hedging-bid", "skew Δ percentile > 80"),
    ("neutral-carry", "其餘 (fallback)"),
)


def vol_labels(sections):
    """Rule-based env labels per spec §4. Multi-label; neutral-carry fallback."""
    g = sections["gex"]["metrics"].get("total_gex")
    vp = sections["iv_rv"]["metrics"].get("percentile")
    sp = sections["term_skew"]["metrics"].get("skew_delta_pct")
    labels = []
    if g is not None and vp is not None and g < 0 and vp < 30:
        labels.append("expansion-risk")
    if g is not None and vp is not None and g > 0 and vp > 70:
        labels.append("premium-rich-pinning")
    if sp is not None and sp > 80:
        labels.append("hedging-bid")
    return labels or ["neutral-carry"]


def render_report(date_str, window, sections, labels):
    lines = [f"# TXO 選擇權盤中量化分析 — {date_str} {window}", ""]
    lines += [f"**Vol 環境標籤:** {', '.join('`%s`' % l for l in labels)}", ""]
    titles = (("gex", "## 1. GEX / Dealer Gamma"), ("iv_rv", "## 2. IV vs RV (VRP)"),
              ("term_skew", "## 3. Term / Skew 盤中動態"), ("flow", "## 4. PCR / OI 資金流"))
    for key, title in titles:
        s = sections[key]
        lines += [title, "", f"**Verdict:** {s['verdict']}", ""]
        for k, v in s["metrics"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    lines += ["## Verification log", ""]
    for key, _ in titles:
        for v in sections[key]["verification"]:
            lines.append(f"- {v}")
    lines += ["", "## 標籤定義", ""]
    for name, rule in LABEL_RULES:
        lines.append(f"- `{name}`: {rule}")
    lines += ["", "> 本報告為環境判定,不出買賣指令。資料 read-only 取自 trading-timescaledb。"]
    return "\n".join(lines)
```

**skew_delta 歷史（Task 4 的 analyze_term_skew 需要，data 層補一個 fetch）:**

```python
def fetch_skew_delta_history(conn, date_str, start, end, days=HISTORY_DAYS):
    """Per-day same-window skew_25d (last - first), TXO only, past `days`
    trading days before date_str. Returns DataFrame[d, skew_delta]."""
    sql = """
        WITH w AS (
          SELECT (time at time zone 'Asia/Taipei')::date AS d, time, skew_25d
          FROM iv_metrics
          WHERE underlying='TX' AND product_code='TXO' AND skew_25d IS NOT NULL
            AND (time at time zone 'Asia/Taipei')::date < %(d)s::date
            AND (time at time zone 'Asia/Taipei')::date >= %(d)s::date - %(days)s * interval '1 day' * 2
            AND (time at time zone 'Asia/Taipei')::time >= %(s)s::time
            AND (time at time zone 'Asia/Taipei')::time <  %(e)s::time
        )
        SELECT d, (max(skew_25d) FILTER (WHERE time = last_t)
                 - max(skew_25d) FILTER (WHERE time = first_t)) AS skew_delta
        FROM (SELECT d, time, skew_25d,
                     min(time) OVER (PARTITION BY d) AS first_t,
                     max(time) OVER (PARTITION BY d) AS last_t
              FROM w) x
        WHERE time IN (first_t, last_t)
        GROUP BY d ORDER BY d DESC LIMIT %(days)s
    """
    p = {"d": date_str, "s": f"{start}:00", "e": f"{end}:00", "days": days}
    return pd.read_sql(sql, conn, params=p)
```

`main()`: argparse (`--date` default today TW via `datetime.now()`, `--window` default `09:00-13:30`, `--out-dir` default `analysis`); connect (exit 1 with clear message on failure); fetch window `iv_metrics` → per-expiry counts → `select_front_expiry` → filter metrics to front expiry; fetch strikes snapshot / OI(latest & prev via `before_date`) / bars / VRP history (join iv & bars per day in pandas: RV per day via `realized_vol_annualized`, vrp = iv_mean − rv → history_df); run 4 analyzers; labels; render; write `analysis/options_quant_<date>.md`; print verdicts + labels to stdout.

- [ ] **Step 4: Verify PASS** (full file).

- [ ] **Step 5: Live smoke (real DB, read-only)** —

```bash
python3 scripts/options_quant.py --date 2026-07-09 --window 09:00-12:00
```
Expected: report written to `analysis/options_quant_2026-07-09.md`; stdout shows 4 verdicts + labels; no traceback. Eyeball: GEX flip is a plausible strike near spot (~45-46k); VRP has a percentile with n stated; term/skew shows the morning IV compression (ATM IV fell through the window per earlier session analysis). If `fetch_vrp_history` exceeds ~30s, apply the documented pandas fallback and rerun. Paste key report lines in your task report.

- [ ] **Step 6: Commit** (`feat(quant): vol labels + report + CLI, live-smoked on 2026-07-09`). Add ONLY the two source files plus the generated `analysis/options_quant_2026-07-09.md` (evidence artifact — this repo commits analysis outputs, see analysis/ history).

---

## Post-implementation

- Full suite: `python3 -m pytest tests/test_options_quant.py -v` — all green.
- Deferred (spec §7): launchd scheduling + inbox notify; realtime Redis mode; label-vs-next-day-RV backtest.
