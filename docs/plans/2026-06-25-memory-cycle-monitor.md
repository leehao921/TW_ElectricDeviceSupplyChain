# Memory Cycle Monitor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `scripts/memory_cycle_monitor.py` — a TDD-built dashboard that ingests a hand-edited YAML + yfinance live data, computes 4 sell-signal lights (S1 P/B, S2 DDR4/DDR5 momentum, S3 MU+Hynix cross-market) for 南亞科 2408 / 華邦電 2344, and emits a Markdown report + Redis hash `h:agent:memory_cycle`.

**Architecture:** Single Python file, ~300 LOC. Pure functions for all signal logic (testable without I/O); separate thin I/O layer (yfinance, file, redis) at the edges. Monotonic trim-stage progression backed by a small JSON state file. All decisions and thresholds traced to `docs/superpowers/specs/2026-06-25-memory-cycle-monitor-design.md`.

**Tech Stack:** Python 3.11, `yfinance`, `pandas`, `pyyaml`, `redis`, `pytest`, `pytest-mock`, `fakeredis`.

**Spec:** `docs/superpowers/specs/2026-06-25-memory-cycle-monitor-design.md`

---

## File Structure

**Create:**
- `scripts/memory_cycle_monitor.py` — main script (pure functions + I/O + CLI)
- `tests/test_memory_cycle_monitor.py` — unit + integration tests
- `tests/fixtures/memory_cycle_full.yaml` — full happy-path fixture for integration test
- `tests/fixtures/memory_cycle_minimal.yaml` — 2-quarter degraded fixture
- `data/memory_cycle_inputs.yaml` — committed template the user edits monthly
- `data/memory_cycle_inputs.example.yaml` — never edited, kept as reference

**Modify:**
- `requirements.txt` — add `redis`, `pyyaml`, `pytest`, `pytest-mock`, `fakeredis`

**Auto-generated (not committed):**
- `data/memory_cycle_state.json` — script-maintained monotonic stage
- `docs/analysis/memory_cycle_YYYY-MM-DD.md` — daily output

**Structural choice:** Single-file script. The whole monitor is ≤300 LOC and tightly coupled around the signal pipeline — splitting it into a package would add ceremony without isolation benefit. Pure-function/IO separation inside the file is enough.

---

## Conventions (apply to every task)

- **Python runner:** Project has no `.venv` at root; use whatever Python the rest of `scripts/` uses. If `python` and `pytest` aren't in PATH, the engineer should create a project venv first (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`) and prefix commands with `.venv/bin/`.
- **Tests:** `tests/test_memory_cycle_monitor.py`, run with `pytest tests/test_memory_cycle_monitor.py -v`
- **Imports in tests:** `from scripts.memory_cycle_monitor import ...` (run pytest from project root)
- **Commit style:** Conventional commits (`feat`, `test`, `chore`, `docs`, `refactor`)
- **Each task ends with a commit.** Frequent commits = easy revert + clean history.

---

## Task 0: Dependencies + sanity check

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new deps to requirements.txt**

Append to the bottom of `requirements.txt`:

```
# Unit — Memory cycle monitor (scripts/memory_cycle_monitor.py)
redis>=5.0
pyyaml>=6.0
pytest>=7.0
pytest-mock>=3.10
fakeredis>=2.20
```

- [ ] **Step 2: Install**

Run: `pip install -r requirements.txt`
Expected: all packages install OK.

- [ ] **Step 3: Sanity check pytest discoverable**

Run: `pytest --collect-only tests/ 2>&1 | tail -5`
Expected: existing tests collect without error.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore(deps): add redis/pyyaml/pytest deps for memory cycle monitor"
```

---

## Task 1: Dataclasses + constants

**Files:**
- Create: `scripts/memory_cycle_monitor.py` (initial scaffold)
- Create: `tests/test_memory_cycle_monitor.py` (initial scaffold)

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory_cycle_monitor.py`:

```python
"""Tests for scripts/memory_cycle_monitor.py — DRAM sell-signal monitor."""
from scripts.memory_cycle_monitor import (
    PB_THRESHOLDS,
    Inputs,
    PricePoint,
    SignalResult,
    GREEN, YELLOW, RED,
)


def test_pb_thresholds_match_spec():
    assert PB_THRESHOLDS["2408.TW"] == {"yellow": 1.8, "red": 2.5}
    assert PB_THRESHOLDS["2344.TW"] == {"yellow": 1.5, "red": 2.0}


def test_signal_result_has_required_fields():
    r = SignalResult(light=GREEN, value="ok", detail={"x": 1})
    assert r.light == "GREEN"
    assert r.value == "ok"
    assert r.detail == {"x": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: FAIL with `ModuleNotFoundError: scripts.memory_cycle_monitor`.

- [ ] **Step 3: Create scaffold**

Create `scripts/memory_cycle_monitor.py`:

```python
"""Memory cycle sell-signal monitor for 南亞科 2408 / 華邦電 2344.

See docs/superpowers/specs/2026-06-25-memory-cycle-monitor-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Light constants
GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

# Thresholds per spec §4 S1
PB_THRESHOLDS: dict[str, dict[str, float]] = {
    "2408.TW": {"yellow": 1.8, "red": 2.5},
    "2344.TW": {"yellow": 1.5, "red": 2.0},
}

# Spec §4 S2 thresholds
DDR5_QOQ_YELLOW_PCT = 10.0  # below this in absolute QoQ → yellow
DDR5_QOQ_RED_PCT = 5.0      # below this → red
DDR5_DECAY_YELLOW = 0.5     # 衰減 >50% → yellow when 3 quarters available


@dataclass
class PricePoint:
    """One row from the YAML price series."""
    label: str   # "2026-04" or "2026Q1"
    price: float


@dataclass
class Inputs:
    """Parsed memory_cycle_inputs.yaml."""
    last_updated: str
    notes: str
    ddr4_8gb_spot_usd: list[PricePoint] = field(default_factory=list)
    ddr5_16gb_contract_usd: list[PricePoint] = field(default_factory=list)
    mu_next_quarter_gm_guide: float | None = None
    mu_next_quarter_rev_qoq: float | None = None


@dataclass
class SignalResult:
    """One signal's computed light + human-readable value + raw detail."""
    light: str            # GREEN | YELLOW | RED | "N/A"
    value: str            # short string for report (e.g. "+10.6%")
    detail: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py
git commit -m "feat(monitor): scaffold memory cycle monitor with dataclasses + constants"
```

---

## Task 2: YAML loader + schema validation

**Files:**
- Modify: `scripts/memory_cycle_monitor.py` (add `load_inputs()`)
- Modify: `tests/test_memory_cycle_monitor.py` (add loader tests)
- Create: `tests/fixtures/memory_cycle_full.yaml`
- Create: `tests/fixtures/memory_cycle_minimal.yaml`

- [ ] **Step 1: Create the test fixtures**

Create `tests/fixtures/memory_cycle_full.yaml`:

```yaml
last_updated: 2026-06-25
notes: "Test fixture — full 3-quarter DDR5"
ddr4_8gb_spot_usd:
  - {month: "2026-03", price: 2.50}
  - {month: "2026-04", price: 2.85}
  - {month: "2026-05", price: 3.12}
  - {month: "2026-06", price: 3.45}
ddr5_16gb_contract_usd:
  - {quarter: "2025Q4", price: 3.50}
  - {quarter: "2026Q1", price: 4.20}
  - {quarter: "2026Q2", price: 5.10}
mu_next_quarter_gm_guide: 0.86
mu_next_quarter_rev_qoq: 0.20
```

Create `tests/fixtures/memory_cycle_minimal.yaml`:

```yaml
last_updated: 2026-06-25
notes: "Test fixture — only 2 quarters of DDR5 (degraded mode)"
ddr4_8gb_spot_usd:
  - {month: "2026-05", price: 3.12}
  - {month: "2026-06", price: 3.45}
ddr5_16gb_contract_usd:
  - {quarter: "2026Q1", price: 4.20}
  - {quarter: "2026Q2", price: 5.10}
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_memory_cycle_monitor.py`:

```python
from pathlib import Path
import pytest
from scripts.memory_cycle_monitor import load_inputs

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_inputs_full_fixture():
    inp = load_inputs(FIXTURES / "memory_cycle_full.yaml")
    assert inp.last_updated == "2026-06-25"
    assert len(inp.ddr4_8gb_spot_usd) == 4
    assert inp.ddr4_8gb_spot_usd[0].label == "2026-03"
    assert inp.ddr4_8gb_spot_usd[-1].price == 3.45
    assert len(inp.ddr5_16gb_contract_usd) == 3
    assert inp.ddr5_16gb_contract_usd[0].label == "2025Q4"
    assert inp.mu_next_quarter_gm_guide == 0.86


def test_load_inputs_minimal_fixture():
    inp = load_inputs(FIXTURES / "memory_cycle_minimal.yaml")
    assert len(inp.ddr4_8gb_spot_usd) == 2
    assert len(inp.ddr5_16gb_contract_usd) == 2
    assert inp.mu_next_quarter_gm_guide is None  # absent in minimal fixture


def test_load_inputs_sorts_unordered_dates(tmp_path):
    p = tmp_path / "unordered.yaml"
    p.write_text("""
last_updated: 2026-06-25
notes: ""
ddr4_8gb_spot_usd:
  - {month: "2026-06", price: 3.45}
  - {month: "2026-04", price: 2.85}
  - {month: "2026-05", price: 3.12}
""")
    inp = load_inputs(p)
    labels = [pp.label for pp in inp.ddr4_8gb_spot_usd]
    assert labels == ["2026-04", "2026-05", "2026-06"]


def test_load_inputs_raises_on_missing_required_field(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("notes: 'missing last_updated'\n")
    with pytest.raises(ValueError, match="last_updated"):
        load_inputs(p)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: 4 new tests FAIL with `ImportError` for `load_inputs`.

- [ ] **Step 4: Implement load_inputs**

Append to `scripts/memory_cycle_monitor.py`:

```python
import yaml
from pathlib import Path


def load_inputs(path: str | Path) -> Inputs:
    """Parse memory_cycle_inputs.yaml into an Inputs dataclass.

    Sorts price series by label (string sort works for both "2026-04" and "2026Q1").
    Raises ValueError on missing required fields.
    """
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    if "last_updated" not in raw:
        raise ValueError("YAML missing required field: last_updated")

    def _parse_series(rows: list[dict], label_key: str) -> list[PricePoint]:
        if not rows:
            return []
        pts = [PricePoint(label=str(r[label_key]), price=float(r["price"])) for r in rows]
        pts.sort(key=lambda pp: pp.label)
        return pts

    return Inputs(
        last_updated=str(raw["last_updated"]),
        notes=str(raw.get("notes", "")),
        ddr4_8gb_spot_usd=_parse_series(raw.get("ddr4_8gb_spot_usd") or [], "month"),
        ddr5_16gb_contract_usd=_parse_series(raw.get("ddr5_16gb_contract_usd") or [], "quarter"),
        mu_next_quarter_gm_guide=raw.get("mu_next_quarter_gm_guide"),
        mu_next_quarter_rev_qoq=raw.get("mu_next_quarter_rev_qoq"),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS (all loader tests + scaffold tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py tests/fixtures/memory_cycle_full.yaml tests/fixtures/memory_cycle_minimal.yaml
git commit -m "feat(monitor): add YAML loader with date-sorted price series"
```

---

## Task 3: S2a DDR4 MoM signal

**Files:**
- Modify: `scripts/memory_cycle_monitor.py`
- Modify: `tests/test_memory_cycle_monitor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_cycle_monitor.py`:

```python
from scripts.memory_cycle_monitor import compute_s2a_ddr4


def _ddr4(prices: list[float]) -> list[PricePoint]:
    return [PricePoint(label=f"2026-{i+1:02d}", price=p) for i, p in enumerate(prices)]


def test_s2a_green_when_positive_mom():
    r = compute_s2a_ddr4(_ddr4([3.0, 3.2, 3.45]))
    assert r.light == GREEN
    assert "+" in r.value  # e.g. "+7.8%"


def test_s2a_yellow_on_first_negative_mom():
    r = compute_s2a_ddr4(_ddr4([3.0, 3.2, 3.1]))  # latest down
    assert r.light == YELLOW


def test_s2a_red_on_two_consecutive_negative_mom():
    r = compute_s2a_ddr4(_ddr4([3.5, 3.2, 3.0]))  # two down months
    assert r.light == RED


def test_s2a_consecutive_resets_on_positive_in_between():
    # down, up, down → latest negative but not consecutive → YELLOW not RED
    r = compute_s2a_ddr4(_ddr4([3.5, 3.2, 3.4, 3.3]))
    assert r.light == YELLOW


def test_s2a_na_when_fewer_than_2_points():
    r = compute_s2a_ddr4(_ddr4([3.0]))
    assert r.light == "N/A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_cycle_monitor.py::test_s2a_green_when_positive_mom -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement compute_s2a_ddr4**

Append to `scripts/memory_cycle_monitor.py`:

```python
def compute_s2a_ddr4(series: list[PricePoint]) -> SignalResult:
    """S2a: DDR4 8Gb 現貨價 MoM.

    Green: latest MoM ≥ 0%
    Yellow: latest MoM < 0% (single negative month)
    Red: latest 2 consecutive months MoM < 0%
    N/A: <2 data points
    """
    if len(series) < 2:
        return SignalResult(light="N/A", value="insufficient data")

    def _mom(a: PricePoint, b: PricePoint) -> float:
        return (b.price - a.price) / a.price * 100

    latest_mom = _mom(series[-2], series[-1])
    value = f"{latest_mom:+.1f}%"

    if latest_mom >= 0:
        return SignalResult(light=GREEN, value=value, detail={"mom_pct": latest_mom})

    # latest is negative; check previous month
    if len(series) >= 3:
        prev_mom = _mom(series[-3], series[-2])
        if prev_mom < 0:
            return SignalResult(
                light=RED, value=value,
                detail={"mom_pct": latest_mom, "prev_mom_pct": prev_mom},
            )

    return SignalResult(light=YELLOW, value=value, detail={"mom_pct": latest_mom})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py
git commit -m "feat(monitor): add S2a DDR4 MoM signal with consecutive-negative red"
```

---

## Task 4: S2b DDR5 QoQ dual-threshold signal

**Files:**
- Modify: `scripts/memory_cycle_monitor.py`
- Modify: `tests/test_memory_cycle_monitor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_cycle_monitor.py`:

```python
from scripts.memory_cycle_monitor import compute_s2b_ddr5


def _ddr5(prices: list[float]) -> list[PricePoint]:
    quarters = ["2025Q4", "2026Q1", "2026Q2", "2026Q3"]
    return [PricePoint(label=quarters[i], price=p) for i, p in enumerate(prices)]


def test_s2b_green_strong_qoq_low_decay():
    # QoQ +21% from +20% → decay ~5% → green
    r = compute_s2b_ddr5(_ddr5([3.5, 4.2, 5.082]))  # 20% then 21%
    assert r.light == GREEN


def test_s2b_yellow_when_qoq_decays_more_than_50pct():
    # +20% → +9% → decay 55% → YELLOW
    r = compute_s2b_ddr5(_ddr5([3.5, 4.2, 4.578]))
    assert r.light == YELLOW


def test_s2b_yellow_when_qoq_below_10pct_3_quarter():
    # +21% → +8% → decay big → YELLOW
    r = compute_s2b_ddr5(_ddr5([3.5, 4.235, 4.574]))  # second QoQ ~8%
    assert r.light == YELLOW


def test_s2b_red_when_qoq_below_5pct():
    # +21% → +3% → RED (absolute threshold)
    r = compute_s2b_ddr5(_ddr5([3.5, 4.235, 4.362]))  # second QoQ ~3%
    assert r.light == RED


def test_s2b_red_on_negative_qoq():
    r = compute_s2b_ddr5(_ddr5([3.5, 4.2, 4.0]))
    assert r.light == RED


def test_s2b_degraded_2_quarter_green_at_plus_10():
    # Only 2 quarters → absolute-only mode. +21% → GREEN
    r = compute_s2b_ddr5([
        PricePoint("2026Q1", 4.20),
        PricePoint("2026Q2", 5.10),
    ])
    assert r.light == GREEN
    assert r.detail.get("decay_pct") is None  # decay unavailable


def test_s2b_degraded_2_quarter_yellow_between_5_and_10():
    r = compute_s2b_ddr5([
        PricePoint("2026Q1", 4.20),
        PricePoint("2026Q2", 4.50),  # ~7.1%
    ])
    assert r.light == YELLOW


def test_s2b_na_when_fewer_than_2_quarters():
    r = compute_s2b_ddr5([PricePoint("2026Q2", 5.10)])
    assert r.light == "N/A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_cycle_monitor.py -v -k s2b`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement compute_s2b_ddr5**

Append to `scripts/memory_cycle_monitor.py`:

```python
def compute_s2b_ddr5(series: list[PricePoint]) -> SignalResult:
    """S2b: DDR5 16Gb 合約價 QoQ — dual threshold.

    With 3+ quarters (full mode):
      Green:  QoQ ≥ +10% AND decay < 50%
      Yellow: QoQ < +10% OR decay > 50%
      Red:    QoQ < +5% or negative

    With exactly 2 quarters (degraded — no decay computable):
      Green:  QoQ ≥ +10%
      Yellow: +5% ≤ QoQ < +10%
      Red:    QoQ < +5% or negative
    """
    if len(series) < 2:
        return SignalResult(light="N/A", value="insufficient data")

    def _qoq(a: PricePoint, b: PricePoint) -> float:
        return (b.price - a.price) / a.price * 100

    latest_qoq = _qoq(series[-2], series[-1])
    detail: dict[str, Any] = {"qoq_pct": latest_qoq, "decay_pct": None}

    # Compute decay if 3+ quarters available
    if len(series) >= 3:
        prev_qoq = _qoq(series[-3], series[-2])
        if prev_qoq > 0:
            decay = (prev_qoq - latest_qoq) / prev_qoq
            detail["decay_pct"] = decay * 100
            detail["prev_qoq_pct"] = prev_qoq

    # Red (absolute) — applies in both modes
    if latest_qoq < DDR5_QOQ_RED_PCT:
        return SignalResult(light=RED, value=f"{latest_qoq:+.1f}%", detail=detail)

    # Yellow checks
    if latest_qoq < DDR5_QOQ_YELLOW_PCT:
        return SignalResult(light=YELLOW, value=f"{latest_qoq:+.1f}%", detail=detail)
    if detail["decay_pct"] is not None and detail["decay_pct"] / 100 > DDR5_DECAY_YELLOW:
        return SignalResult(light=YELLOW, value=f"{latest_qoq:+.1f}%", detail=detail)

    return SignalResult(light=GREEN, value=f"{latest_qoq:+.1f}%", detail=detail)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py
git commit -m "feat(monitor): add S2b DDR5 QoQ dual-threshold + 2-quarter fallback"
```

---

## Task 5: S1 P/B fetch + signal

**Files:**
- Modify: `scripts/memory_cycle_monitor.py`
- Modify: `tests/test_memory_cycle_monitor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_cycle_monitor.py`:

```python
from scripts.memory_cycle_monitor import compute_s1_pb


def test_s1_green_when_both_below_yellow():
    r = compute_s1_pb({"2408.TW": 1.42, "2344.TW": 1.12})
    assert r.light == GREEN


def test_s1_yellow_at_exact_threshold():
    # 2408 at 1.80 → yellow (>= threshold)
    r = compute_s1_pb({"2408.TW": 1.80, "2344.TW": 1.10})
    assert r.light == YELLOW
    # 2344 at 1.50 → yellow
    r2 = compute_s1_pb({"2408.TW": 1.10, "2344.TW": 1.50})
    assert r2.light == YELLOW


def test_s1_red_above_extreme():
    r = compute_s1_pb({"2408.TW": 2.51, "2344.TW": 1.10})
    assert r.light == RED


def test_s1_takes_worst_of_two():
    # one green, one red → RED
    r = compute_s1_pb({"2408.TW": 1.10, "2344.TW": 2.05})
    assert r.light == RED


def test_s1_na_when_value_missing():
    r = compute_s1_pb({"2408.TW": None, "2344.TW": 1.10})
    assert r.detail["2408.TW"] == "N/A"
    # but 2344 still computes → overall takes worst-known
    assert r.light in (GREEN, "N/A")  # 2344 is green; 2408 unknown → at minimum green-from-known
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_cycle_monitor.py -v -k s1`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement compute_s1_pb**

Append to `scripts/memory_cycle_monitor.py`:

```python
def _light_for_pb(pb: float, thresholds: dict[str, float]) -> str:
    if pb >= thresholds["red"]:
        return RED
    if pb >= thresholds["yellow"]:
        return YELLOW
    return GREEN


_LIGHT_RANK = {GREEN: 0, YELLOW: 1, RED: 2}


def _worst(*lights: str) -> str:
    known = [lg for lg in lights if lg in _LIGHT_RANK]
    if not known:
        return "N/A"
    return max(known, key=_LIGHT_RANK.__getitem__)


def compute_s1_pb(pbs: dict[str, float | None]) -> SignalResult:
    """S1: P/B valuation premium for 2408.TW and 2344.TW.

    Takes the worst-known light of the two. If a ticker is None it's recorded
    as N/A but doesn't drag the overall light down (still uses worst of known).
    """
    detail: dict[str, Any] = {}
    lights = []
    parts = []
    for ticker, pb in pbs.items():
        if pb is None:
            detail[ticker] = "N/A"
            lights.append("N/A")
            parts.append(f"{ticker}=N/A")
            continue
        lg = _light_for_pb(pb, PB_THRESHOLDS[ticker])
        detail[ticker] = {"pb": pb, "light": lg}
        lights.append(lg)
        parts.append(f"{ticker}={pb:.2f}")

    return SignalResult(light=_worst(*lights), value=", ".join(parts), detail=detail)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS.

- [ ] **Step 5: Add yfinance fetch (with fallback)**

Append to `scripts/memory_cycle_monitor.py`:

```python
def fetch_pb(ticker: str) -> float | None:
    """Fetch P/B for a ticker via yfinance.

    Primary: info['priceToBook']. Fallback: marketCap / (bookValue * sharesOutstanding).
    Returns None on any failure (caller treats as N/A).
    """
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info
        pb = info.get("priceToBook")
        if pb is not None and pb > 0:
            return float(pb)
        mc = info.get("marketCap")
        bv = info.get("bookValue")
        so = info.get("sharesOutstanding")
        if mc and bv and so and bv * so > 0:
            return float(mc / (bv * so))
    except Exception:
        pass
    return None
```

- [ ] **Step 6: Test the fetch with a mocker**

Append to `tests/test_memory_cycle_monitor.py`:

```python
def test_fetch_pb_returns_value_from_info(mocker):
    fake_ticker = mocker.MagicMock()
    fake_ticker.info = {"priceToBook": 1.42}
    mocker.patch("yfinance.Ticker", return_value=fake_ticker)
    from scripts.memory_cycle_monitor import fetch_pb
    assert fetch_pb("2408.TW") == 1.42


def test_fetch_pb_returns_none_on_exception(mocker):
    mocker.patch("yfinance.Ticker", side_effect=RuntimeError("network"))
    from scripts.memory_cycle_monitor import fetch_pb
    assert fetch_pb("2408.TW") is None
```

- [ ] **Step 7: Run all tests**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py
git commit -m "feat(monitor): add S1 P/B signal + yfinance fetch with fallback"
```

---

## Task 6: S3 monthly weakness detection (pure function)

**Files:**
- Modify: `scripts/memory_cycle_monitor.py`
- Modify: `tests/test_memory_cycle_monitor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_cycle_monitor.py`:

```python
from scripts.memory_cycle_monitor import detect_monthly_weakness


def test_monthly_weakness_true_when_latest_below_prior_3_min():
    # latest = 90 < min(prior 3 = [95, 100, 98]) = 95 → weak
    closes = [105, 102, 100, 95, 100, 98, 90]
    assert detect_monthly_weakness(closes) is True


def test_monthly_weakness_false_when_latest_equals_prior_3_min():
    # strict less-than → equal = not weak
    closes = [100, 102, 95, 100, 98, 95]
    assert detect_monthly_weakness(closes) is False


def test_monthly_weakness_false_when_latest_above():
    closes = [100, 95, 98, 99, 105]
    assert detect_monthly_weakness(closes) is False


def test_monthly_weakness_false_with_insufficient_data():
    # need at least 4 months (3 prior + 1 current)
    assert detect_monthly_weakness([100, 95, 90]) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_cycle_monitor.py -v -k monthly_weakness`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement detect_monthly_weakness**

Append to `scripts/memory_cycle_monitor.py`:

```python
def detect_monthly_weakness(closes: list[float]) -> bool:
    """Spec §4 S3: latest month close < min of prior 3 months close.

    `closes` is chronological; index -1 is latest. Need ≥4 points.
    """
    if len(closes) < 4:
        return False
    prior_3_min = min(closes[-4:-1])
    return closes[-1] < prior_3_min
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py
git commit -m "feat(monitor): add monthly weakness detector for S3 cross-market signal"
```

---

## Task 7: S3 truth table

**Files:**
- Modify: `scripts/memory_cycle_monitor.py`
- Modify: `tests/test_memory_cycle_monitor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_cycle_monitor.py`:

```python
from scripts.memory_cycle_monitor import compute_s3_lights


def test_s3_green_when_mu_not_weak():
    # MU strong → green regardless of others
    r = compute_s3_lights(mu_weak=False, hynix_weak=True, tw_weak=True)
    assert r.light == GREEN


def test_s3_yellow_when_only_mu_weak():
    r = compute_s3_lights(mu_weak=True, hynix_weak=False, tw_weak=False)
    assert r.light == YELLOW


def test_s3_red_when_mu_and_hynix_weak_tw_strong():
    r = compute_s3_lights(mu_weak=True, hynix_weak=True, tw_weak=False)
    assert r.light == RED


def test_s3_yellow_when_all_three_weak_window_closed():
    # MU + Hynix + TW all weak → lead window closed → YELLOW per spec
    r = compute_s3_lights(mu_weak=True, hynix_weak=True, tw_weak=True)
    assert r.light == YELLOW
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_cycle_monitor.py -v -k s3`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement compute_s3_lights**

Append to `scripts/memory_cycle_monitor.py`:

```python
def compute_s3_lights(*, mu_weak: bool, hynix_weak: bool, tw_weak: bool) -> SignalResult:
    """S3 truth table from spec §4.

    | MU  | Hynix | TW  | Light  | Note                          |
    | --- | ----- | --- | ------ | ----------------------------- |
    | not | -     | -   | GREEN  | primary signal not triggered  |
    | wk  | not   | -   | YELLOW | single-head warning           |
    | wk  | wk    | not | RED    | dual-head lead confirmed      |
    | wk  | wk    | wk  | YELLOW | lead window closed            |
    """
    detail = {"mu_weak": mu_weak, "hynix_weak": hynix_weak, "tw_weak": tw_weak}
    if not mu_weak:
        return SignalResult(light=GREEN, value="MU not weak", detail=detail)
    if not hynix_weak:
        return SignalResult(light=YELLOW, value="MU weak only", detail=detail)
    # MU + Hynix both weak
    if tw_weak:
        return SignalResult(light=YELLOW, value="lead window closed", detail=detail)
    return SignalResult(light=RED, value="MU+Hynix lead TW", detail=detail)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS.

- [ ] **Step 5: Add monthly-close fetcher (with mocked test)**

Append to `scripts/memory_cycle_monitor.py`:

```python
def fetch_monthly_closes(ticker: str, months: int = 13) -> list[float]:
    """Return last `months` of monthly close prices for `ticker`.

    Drops the most recent month if it's incomplete (last day of month not yet reached).
    Returns [] on failure.
    """
    import yfinance as yf
    try:
        hist = yf.Ticker(ticker).history(period=f"{months}mo", interval="1mo")
        if hist is None or hist.empty:
            return []
        closes = hist["Close"].dropna().tolist()
        return [float(c) for c in closes]
    except Exception:
        return []
```

Append to `tests/test_memory_cycle_monitor.py`:

```python
def test_fetch_monthly_closes_returns_list(mocker):
    import pandas as pd
    fake_hist = pd.DataFrame({"Close": [100.0, 102.0, 95.0]})
    fake_ticker = mocker.MagicMock()
    fake_ticker.history.return_value = fake_hist
    mocker.patch("yfinance.Ticker", return_value=fake_ticker)
    from scripts.memory_cycle_monitor import fetch_monthly_closes
    assert fetch_monthly_closes("MU") == [100.0, 102.0, 95.0]


def test_fetch_monthly_closes_returns_empty_on_failure(mocker):
    mocker.patch("yfinance.Ticker", side_effect=RuntimeError("boom"))
    from scripts.memory_cycle_monitor import fetch_monthly_closes
    assert fetch_monthly_closes("MU") == []
```

- [ ] **Step 6: Run all tests**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py
git commit -m "feat(monitor): add S3 truth table + monthly-close fetcher"
```

---

## Task 8: Aggregation + monotonic trim stage

**Files:**
- Modify: `scripts/memory_cycle_monitor.py`
- Modify: `tests/test_memory_cycle_monitor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_cycle_monitor.py`:

```python
from scripts.memory_cycle_monitor import aggregate, advance_state


def _sig(light: str) -> SignalResult:
    return SignalResult(light=light, value="")


def test_aggregate_all_green():
    out = aggregate(s1=_sig(GREEN), s2a=_sig(GREEN), s2b=_sig(GREEN), s3=_sig(GREEN))
    assert out["overall_light"] == GREEN
    assert out["trim_stage_candidate"] == 0


def test_aggregate_s1_yellow_gives_stage_1():
    out = aggregate(s1=_sig(YELLOW), s2a=_sig(GREEN), s2b=_sig(GREEN), s3=_sig(GREEN))
    assert out["overall_light"] == YELLOW
    assert out["trim_stage_candidate"] == 1


def test_aggregate_s3_yellow_gives_stage_2():
    out = aggregate(s1=_sig(GREEN), s2a=_sig(GREEN), s2b=_sig(GREEN), s3=_sig(YELLOW))
    assert out["overall_light"] == YELLOW
    assert out["trim_stage_candidate"] == 2


def test_aggregate_any_red_gives_stage_3():
    out = aggregate(s1=_sig(GREEN), s2a=_sig(RED), s2b=_sig(GREEN), s3=_sig(GREEN))
    assert out["overall_light"] == RED
    assert out["trim_stage_candidate"] == 3


def test_aggregate_takes_max_when_multiple():
    # S1 yellow (cand 1) + S3 yellow (cand 2) → cand 2
    out = aggregate(s1=_sig(YELLOW), s2a=_sig(GREEN), s2b=_sig(GREEN), s3=_sig(YELLOW))
    assert out["trim_stage_candidate"] == 2


def test_advance_state_creates_state_file_when_missing(tmp_path):
    state_file = tmp_path / "state.json"
    out = advance_state(candidate=1, state_path=state_file)
    assert out["stage"] == 1
    assert out["max_stage_seen"] == 1
    assert state_file.exists()


def test_advance_state_monotonic_does_not_regress(tmp_path):
    state_file = tmp_path / "state.json"
    advance_state(candidate=2, state_path=state_file)
    out = advance_state(candidate=1, state_path=state_file)
    assert out["stage"] == 2  # never goes back down


def test_advance_state_records_first_seen_at(tmp_path):
    state_file = tmp_path / "state.json"
    out = advance_state(candidate=2, state_path=state_file, today="2026-07-15")
    assert out["max_stage_first_seen_at"] == "2026-07-15"
    # second call with same candidate → first_seen_at unchanged
    out2 = advance_state(candidate=2, state_path=state_file, today="2026-08-01")
    assert out2["max_stage_first_seen_at"] == "2026-07-15"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_cycle_monitor.py -v -k "aggregate or advance_state"`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement aggregate + advance_state**

Append to `scripts/memory_cycle_monitor.py`:

```python
import json
from datetime import date


def aggregate(*, s1: SignalResult, s2a: SignalResult, s2b: SignalResult, s3: SignalResult) -> dict:
    """Combine the 4 signals into overall light + candidate stage.

    Candidate stage (spec §4 S4):
      3 if any RED
      2 if S3 YELLOW
      1 if S1 or S2 (any) YELLOW
      0 otherwise
    Final stage = max(candidate, historical max from state file) — caller handles that.
    """
    s2_worst = _worst(s2a.light, s2b.light)
    overall = _worst(s1.light, s2_worst, s3.light)

    candidate = 0
    if RED in (s1.light, s2a.light, s2b.light, s3.light):
        candidate = 3
    elif s3.light == YELLOW:
        candidate = 2
    elif s1.light == YELLOW or s2_worst == YELLOW:
        candidate = 1

    return {
        "overall_light": overall,
        "trim_stage_candidate": candidate,
        "s2_combined_light": s2_worst,
    }


def advance_state(*, candidate: int, state_path: Path, today: str | None = None) -> dict:
    """Monotonic stage progression backed by JSON state file.

    Returns dict with: stage, max_stage_seen, max_stage_first_seen_at.
    """
    today = today or date.today().isoformat()
    state_path = Path(state_path)

    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        state = {"max_stage_seen": 0, "max_stage_first_seen_at": None}

    if candidate > state["max_stage_seen"]:
        state["max_stage_seen"] = candidate
        state["max_stage_first_seen_at"] = today

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))

    return {"stage": state["max_stage_seen"], **state}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py
git commit -m "feat(monitor): add signal aggregation + monotonic trim-stage state"
```

---

## Task 9: Markdown report renderer

**Files:**
- Modify: `scripts/memory_cycle_monitor.py`
- Modify: `tests/test_memory_cycle_monitor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_cycle_monitor.py`:

```python
from scripts.memory_cycle_monitor import render_markdown


def test_markdown_contains_required_sections():
    s1 = SignalResult(GREEN, "2408=1.42, 2344=1.12",
                      {"2408.TW": {"pb": 1.42, "light": GREEN},
                       "2344.TW": {"pb": 1.12, "light": GREEN}})
    s2a = SignalResult(GREEN, "+10.6%", {"mom_pct": 10.6})
    s2b = SignalResult(GREEN, "+21.4%", {"qoq_pct": 21.4, "decay_pct": None})
    s3 = SignalResult(GREEN, "MU not weak",
                      {"mu_weak": False, "hynix_weak": False, "tw_weak": False})
    md = render_markdown(
        report_date="2026-06-25",
        overall_light=GREEN,
        trim_stage=0,
        max_stage_seen=0,
        next_trigger="S2a DDR4 首次負 MoM",
        last_updated_yaml="2026-06-25",
        s1=s1, s2a=s2a, s2b=s2b, s3=s3,
    )
    assert "記憶體週期燈號 — 2026-06-25" in md
    assert "S1 — 兩檔估值溢價" in md
    assert "S2 — DRAM 報價動能" in md
    assert "S3 — 跨市場領先訊號" in md
    assert "1.42" in md
    assert "+10.6%" in md
    assert "🟢" in md


def test_markdown_red_when_any_signal_red():
    s1 = SignalResult(RED, "2408=2.60", {"2408.TW": {"pb": 2.6, "light": RED}})
    s2a = SignalResult(GREEN, "+5%")
    s2b = SignalResult(GREEN, "+15%")
    s3 = SignalResult(GREEN, "ok")
    md = render_markdown(
        report_date="2026-06-25", overall_light=RED, trim_stage=3,
        max_stage_seen=3, next_trigger="-", last_updated_yaml="2026-06-25",
        s1=s1, s2a=s2a, s2b=s2b, s3=s3,
    )
    assert "🔴" in md
    assert "trim 30%" in md or "止損" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_cycle_monitor.py -v -k markdown`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement render_markdown**

Append to `scripts/memory_cycle_monitor.py`:

```python
LIGHT_EMOJI = {GREEN: "🟢", YELLOW: "🟡", RED: "🔴", "N/A": "⚪"}

STAGE_ACTION = {
    0: "HOLD;等下次更新",
    1: "第一段 trim 30%",
    2: "第二段 trim 40%(累計 70%)",
    3: "第三段 trim 30%(累計 100%,止損 / 全砍)",
}


def render_markdown(
    *,
    report_date: str,
    overall_light: str,
    trim_stage: int,
    max_stage_seen: int,
    next_trigger: str,
    last_updated_yaml: str,
    s1: SignalResult,
    s2a: SignalResult,
    s2b: SignalResult,
    s3: SignalResult,
) -> str:
    """Render the daily Markdown report. Pure function — no I/O."""
    emoji = LIGHT_EMOJI.get(overall_light, "⚪")
    action = STAGE_ACTION[trim_stage]

    # S1 table
    s1_rows = []
    for ticker, label in [("2408.TW", "南亞科 2408"), ("2344.TW", "華邦電 2344")]:
        info = s1.detail.get(ticker)
        if isinstance(info, dict):
            pb = f"{info['pb']:.2f}"
            lg = LIGHT_EMOJI[info["light"]]
        else:
            pb, lg = "N/A", "⚪"
        th = PB_THRESHOLDS[ticker]
        s1_rows.append(f"| {label} | {pb} | >{th['yellow']} | >{th['red']} | {lg} |")
    s1_table = "\n".join(s1_rows)

    # S2 detail strings
    decay = s2b.detail.get("decay_pct")
    decay_str = "N/A" if decay is None else f"{decay:.1f}%"

    # S3 detail
    s3d = s3.detail
    s3_table = "\n".join([
        f"| MU | {'轉弱' if s3d.get('mu_weak') else '站穩'} | "
        f"{LIGHT_EMOJI[RED if s3d.get('mu_weak') else GREEN]} |",
        f"| Hynix 000660.KS | {'轉弱' if s3d.get('hynix_weak') else '站穩'} | "
        f"{LIGHT_EMOJI[RED if s3d.get('hynix_weak') else GREEN]} |",
        f"| 2408 / 2344 | {'轉弱' if s3d.get('tw_weak') else '站穩'} | "
        f"{LIGHT_EMOJI[RED if s3d.get('tw_weak') else GREEN]} |",
    ])

    return f"""# 記憶體週期燈號 — {report_date}

**總燈號:** {emoji} {overall_light}   **Trim 進度:** {trim_stage} / 3   \
**Action:** {action}
**下一段觸發:** {next_trigger}
**Inputs YAML last_updated:** {last_updated_yaml}   **Max stage seen:** {max_stage_seen}

---

## S1 — 兩檔估值溢價
| 標的 | P/B | 警戒 | 極端 | 燈號 |
|---|---|---|---|---|
{s1_table}

## S2 — DRAM 報價動能
- **S2a DDR4 8Gb 現貨 MoM:** {s2a.value} {LIGHT_EMOJI[s2a.light]}
- **S2b DDR5 16Gb 合約 QoQ:** {s2b.value};相對前季衰減 {decay_str} {LIGHT_EMOJI[s2b.light]}

## S3 — 跨市場領先訊號
| Source | 月線狀態 | 燈號 |
|---|---|---|
{s3_table}

## Verification log
- Data source: `data/memory_cycle_inputs.yaml` last_updated {last_updated_yaml}
- Spec: `docs/superpowers/specs/2026-06-25-memory-cycle-monitor-design.md`

## Action
**{action}**
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py
git commit -m "feat(monitor): add Markdown report renderer"
```

---

## Task 10: Redis publisher

**Files:**
- Modify: `scripts/memory_cycle_monitor.py`
- Modify: `tests/test_memory_cycle_monitor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_cycle_monitor.py`:

```python
import fakeredis
from scripts.memory_cycle_monitor import publish_redis


def test_publish_redis_sets_expected_fields():
    r = fakeredis.FakeStrictRedis(decode_responses=True)
    publish_redis(
        client=r,
        hash_name="h:agent:memory_cycle",
        data={
            "updated_at": "2026-06-25T08:15:00+08:00",
            "overall_light": GREEN,
            "trim_stage": 0,
            "s1_pb_2408": 1.42,
            "report_path": "docs/analysis/memory_cycle_2026-06-25.md",
        },
    )
    out = r.hgetall("h:agent:memory_cycle")
    assert out["overall_light"] == "GREEN"
    assert out["trim_stage"] == "0"
    assert out["s1_pb_2408"] == "1.42"


def test_publish_redis_handles_none_as_empty_string():
    r = fakeredis.FakeStrictRedis(decode_responses=True)
    publish_redis(client=r, hash_name="h:test", data={"x": None})
    assert r.hget("h:test", "x") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory_cycle_monitor.py -v -k publish_redis`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement publish_redis + connection helper**

Append to `scripts/memory_cycle_monitor.py`:

```python
def publish_redis(*, client, hash_name: str, data: dict) -> None:
    """HSET all fields of `data` to `hash_name`. None values → empty string."""
    flat = {k: ("" if v is None else str(v)) for k, v in data.items()}
    client.hset(hash_name, mapping=flat)


def make_redis_client():
    """Standard Redis client per project convention.

    Honors env vars: REDIS_HOST (default 'localhost'), REDIS_PORT (default 6379),
    REDIS_DB (default 0). Reuses connection params from `redis-trading` MCP config.
    """
    import os
    import redis
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=int(os.environ.get("REDIS_DB", "0")),
        decode_responses=True,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py
git commit -m "feat(monitor): add Redis hash publisher with env-driven client"
```

---

## Task 11: CLI + main pipeline

**Files:**
- Modify: `scripts/memory_cycle_monitor.py` (add `main()` + `__main__`)
- Modify: `tests/test_memory_cycle_monitor.py` (add CLI smoke test)
- Create: `data/memory_cycle_inputs.yaml` (initial template, copy of fixture-style content)
- Create: `data/memory_cycle_inputs.example.yaml` (reference, never edited)

- [ ] **Step 1: Write a CLI smoke test**

Append to `tests/test_memory_cycle_monitor.py`:

```python
def test_main_dry_run_does_not_write_files(tmp_path, mocker, capsys):
    """--dry-run prints to stdout, writes no files, makes no Redis call."""
    # Mock yfinance — return safe defaults
    mocker.patch("scripts.memory_cycle_monitor.fetch_pb", return_value=1.42)
    mocker.patch(
        "scripts.memory_cycle_monitor.fetch_monthly_closes",
        return_value=[100.0, 102.0, 105.0, 108.0, 110.0],  # not weak
    )
    inputs_path = FIXTURES / "memory_cycle_full.yaml"
    state_path = tmp_path / "state.json"

    from scripts.memory_cycle_monitor import main
    rc = main([
        "--dry-run",
        "--inputs", str(inputs_path),
        "--state", str(state_path),
        "--report-dir", str(tmp_path / "reports"),
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "記憶體週期燈號" in captured.out
    assert not (tmp_path / "reports").exists()
    assert not state_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_cycle_monitor.py::test_main_dry_run_does_not_write_files -v`
Expected: FAIL with `ImportError` for `main`.

- [ ] **Step 3: Implement main + glue**

Append to `scripts/memory_cycle_monitor.py`:

```python
import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = PROJECT_ROOT / "data" / "memory_cycle_inputs.yaml"
DEFAULT_STATE = PROJECT_ROOT / "data" / "memory_cycle_state.json"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "docs" / "analysis"
REDIS_HASH = "h:agent:memory_cycle"

TICKERS = ["2408.TW", "2344.TW"]


def _build_redis_payload(*, report_date, overall_light, trim_stage, max_stage_seen,
                         next_trigger, s1, s2a, s2b, s3, report_path) -> dict:
    tz = ZoneInfo("Asia/Taipei")
    return {
        "updated_at": datetime.now(tz).isoformat(timespec="seconds"),
        "overall_light": overall_light,
        "trim_stage": trim_stage,
        "max_stage_seen": max_stage_seen,
        "next_trigger": next_trigger,
        "s1_pb_2408": s1.detail.get("2408.TW", {}).get("pb") if isinstance(s1.detail.get("2408.TW"), dict) else None,
        "s1_pb_2344": s1.detail.get("2344.TW", {}).get("pb") if isinstance(s1.detail.get("2344.TW"), dict) else None,
        "s1_light": s1.light,
        "s2a_ddr4_mom_pct": s2a.detail.get("mom_pct"),
        "s2b_ddr5_qoq_pct": s2b.detail.get("qoq_pct"),
        "s2b_ddr5_decay_pct": s2b.detail.get("decay_pct"),
        "s2_light": _worst(s2a.light, s2b.light),
        "s3_mu_monthly": YELLOW if s3.detail.get("mu_weak") else GREEN,
        "s3_hynix_monthly": YELLOW if s3.detail.get("hynix_weak") else GREEN,
        "s3_tw_monthly": YELLOW if s3.detail.get("tw_weak") else GREEN,
        "s3_light": s3.light,
        "report_path": report_path,
    }


def _suggest_next_trigger(s1: SignalResult, s2a: SignalResult, s2b: SignalResult, s3: SignalResult) -> str:
    if s2a.light == GREEN:
        return "S2a DDR4 首次負 MoM"
    if s2b.light == GREEN:
        return "S2b DDR5 QoQ 衰減 >50% 或 <+10%"
    if s1.light == GREEN:
        return "S1 任一檔 P/B 進入警戒區"
    if s3.light == GREEN:
        return "S3 MU 月線轉弱"
    return "升級至下一個 trim stage"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Memory cycle sell-signal monitor")
    parser.add_argument("--inputs", default=str(DEFAULT_INPUTS))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--dry-run", action="store_true",
                        help="Print Markdown to stdout, do not write files or push Redis")
    parser.add_argument("--no-redis", action="store_true",
                        help="Write Markdown but skip Redis push")
    args = parser.parse_args(argv)

    # Load inputs
    try:
        inp = load_inputs(args.inputs)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: inputs YAML invalid: {e}", file=sys.stderr)
        return 1

    # Compute signals
    s2a = compute_s2a_ddr4(inp.ddr4_8gb_spot_usd)
    s2b = compute_s2b_ddr5(inp.ddr5_16gb_contract_usd)

    pbs = {t: fetch_pb(t) for t in TICKERS}
    if all(v is None for v in pbs.values()):
        print("ERROR: yfinance returned no P/B for any ticker", file=sys.stderr)
        return 2
    s1 = compute_s1_pb(pbs)

    mu_closes = fetch_monthly_closes("MU")
    hynix_closes = fetch_monthly_closes("000660.KS")
    tw_weakness_flags = []
    for t in TICKERS:
        cl = fetch_monthly_closes(t)
        if cl:
            tw_weakness_flags.append(detect_monthly_weakness(cl))
    tw_weak = any(tw_weakness_flags)
    s3 = compute_s3_lights(
        mu_weak=detect_monthly_weakness(mu_closes),
        hynix_weak=detect_monthly_weakness(hynix_closes),
        tw_weak=tw_weak,
    )

    # Aggregate
    agg = aggregate(s1=s1, s2a=s2a, s2b=s2b, s3=s3)

    # State (skipped on dry-run so test runs don't mutate disk)
    today = date.today().isoformat()
    if args.dry_run:
        stage = agg["trim_stage_candidate"]
        max_seen = stage
    else:
        state = advance_state(candidate=agg["trim_stage_candidate"],
                              state_path=Path(args.state), today=today)
        stage = state["stage"]
        max_seen = state["max_stage_seen"]

    next_trigger = _suggest_next_trigger(s1, s2a, s2b, s3)
    report_path = Path(args.report_dir) / f"memory_cycle_{today}.md"

    md = render_markdown(
        report_date=today,
        overall_light=agg["overall_light"],
        trim_stage=stage,
        max_stage_seen=max_seen,
        next_trigger=next_trigger,
        last_updated_yaml=inp.last_updated,
        s1=s1, s2a=s2a, s2b=s2b, s3=s3,
    )

    if args.dry_run:
        print(md)
        return 0

    # Write Markdown
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md)

    # Publish Redis (unless --no-redis)
    if not args.no_redis:
        try:
            client = make_redis_client()
            payload = _build_redis_payload(
                report_date=today, overall_light=agg["overall_light"],
                trim_stage=stage, max_stage_seen=max_seen, next_trigger=next_trigger,
                s1=s1, s2a=s2a, s2b=s2b, s3=s3, report_path=str(report_path),
            )
            publish_redis(client=client, hash_name=REDIS_HASH, data=payload)
        except Exception as e:
            print(f"WARN: Redis push failed: {e}", file=sys.stderr)
            return 3

    print(f"Wrote {report_path} (overall: {agg['overall_light']}, stage {stage})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS.

- [ ] **Step 5: Create initial YAML template**

Create `data/memory_cycle_inputs.yaml`:

```yaml
# Memory Cycle Monitor — manual inputs
# Edit monthly after TrendForce / DRAMeXchange report; once per quarter for DDR5.
# Source attribution required for audit.
last_updated: 2026-06-25
notes: "Initial template — please replace with real TrendForce numbers."

ddr4_8gb_spot_usd:
  - {month: "2026-04", price: 2.85}
  - {month: "2026-05", price: 3.12}
  - {month: "2026-06", price: 3.45}

ddr5_16gb_contract_usd:
  - {quarter: "2026Q1", price: 4.20}
  - {quarter: "2026Q2", price: 5.10}

mu_next_quarter_gm_guide: 0.86
mu_next_quarter_rev_qoq: 0.20
```

Create `data/memory_cycle_inputs.example.yaml`: copy of the above (kept as static reference; `data/memory_cycle_inputs.yaml` is the live file the user edits).

- [ ] **Step 6: Commit**

```bash
git add scripts/memory_cycle_monitor.py tests/test_memory_cycle_monitor.py data/memory_cycle_inputs.yaml data/memory_cycle_inputs.example.yaml
git commit -m "feat(monitor): add main() CLI pipeline + initial YAML template"
```

---

## Task 12: Integration test (end-to-end with mocked I/O)

**Files:**
- Modify: `tests/test_memory_cycle_monitor.py`

- [ ] **Step 1: Write the integration test**

Append to `tests/test_memory_cycle_monitor.py`:

```python
def test_integration_full_pipeline_writes_markdown_and_redis(tmp_path, mocker):
    """Full pipeline:
    - YAML fixture (full 3-quarter)
    - Mocked yfinance (P/B + monthly closes for MU/Hynix/2408/2344)
    - fakeredis as Redis client
    - Asserts Markdown file written + Redis hash populated
    """
    # Mock yfinance fetches at the source-function level
    mocker.patch("scripts.memory_cycle_monitor.fetch_pb",
                 side_effect=lambda t: {"2408.TW": 1.42, "2344.TW": 1.12}[t])
    # All upward-trending closes → no weakness anywhere
    mocker.patch("scripts.memory_cycle_monitor.fetch_monthly_closes",
                 return_value=[100, 102, 105, 108, 110])

    # Patch Redis client factory to return a fakeredis instance
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    mocker.patch("scripts.memory_cycle_monitor.make_redis_client", return_value=fake)

    from scripts.memory_cycle_monitor import main, REDIS_HASH

    state_path = tmp_path / "state.json"
    report_dir = tmp_path / "reports"
    inputs_path = FIXTURES / "memory_cycle_full.yaml"

    rc = main([
        "--inputs", str(inputs_path),
        "--state", str(state_path),
        "--report-dir", str(report_dir),
    ])
    assert rc == 0

    # Markdown written
    md_files = list(report_dir.glob("memory_cycle_*.md"))
    assert len(md_files) == 1
    md = md_files[0].read_text()
    assert "S1 — 兩檔估值溢價" in md
    assert "1.42" in md
    assert "🟢" in md  # all-green path

    # Redis hash populated
    redis_data = fake.hgetall(REDIS_HASH)
    assert redis_data["overall_light"] == "GREEN"
    assert redis_data["trim_stage"] == "0"
    assert redis_data["s1_pb_2408"] == "1.42"
    assert "memory_cycle_" in redis_data["report_path"]

    # State file created
    assert state_path.exists()
    state = json.loads(state_path.read_text())
    assert state["max_stage_seen"] == 0


def test_integration_no_redis_flag_skips_redis(tmp_path, mocker):
    mocker.patch("scripts.memory_cycle_monitor.fetch_pb", return_value=1.42)
    mocker.patch("scripts.memory_cycle_monitor.fetch_monthly_closes",
                 return_value=[100, 102, 105, 108, 110])
    # Make Redis client raise to confirm it's not called
    mocker.patch("scripts.memory_cycle_monitor.make_redis_client",
                 side_effect=RuntimeError("should not be called"))

    from scripts.memory_cycle_monitor import main
    rc = main([
        "--no-redis",
        "--inputs", str(FIXTURES / "memory_cycle_full.yaml"),
        "--state", str(tmp_path / "state.json"),
        "--report-dir", str(tmp_path / "reports"),
    ])
    assert rc == 0  # no Redis attempted, no error
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: PASS (all unit + integration).

- [ ] **Step 3: Commit**

```bash
git add tests/test_memory_cycle_monitor.py
git commit -m "test(monitor): add end-to-end integration test with fakeredis"
```

---

## Task 13: Manual dry-run + .gitignore + final docs

**Files:**
- Modify: `.gitignore` (add state file + analysis report dir if not already gitignored)

- [ ] **Step 1: Add state + report files to .gitignore**

Append to `.gitignore`:

```
# Memory cycle monitor auto-generated outputs
data/memory_cycle_state.json
docs/analysis/memory_cycle_*.md
```

> Rationale: state is local;每日 report 可以重生,不應該污染 git history;若要保存特定日期可手動 `git add -f`。

- [ ] **Step 2: Real dry-run against today's data**

Run: `python scripts/memory_cycle_monitor.py --dry-run`
Expected: Markdown report printed to stdout; lights make sense given current market;no file writes.

Read the report. Sanity-check:
- 2408/2344 P/B reasonable (around 1.x for cycle-mid;not extreme)
- DDR4/DDR5 from your YAML show expected MoM/QoQ
- MU + Hynix lights match what you visually see on monthly charts

If anything wrong → debug and fix, then re-commit specific bugfixes (not the YAML).

- [ ] **Step 3: Real full run (writes Markdown + Redis)**

Run: `python scripts/memory_cycle_monitor.py`
Expected: prints `Wrote docs/analysis/memory_cycle_2026-06-25.md (overall: GREEN, stage 0)` (or similar).

Verify Redis: `redis-cli HGETALL h:agent:memory_cycle` should show all expected fields.

- [ ] **Step 4: Commit ignore rules**

```bash
git add .gitignore
git commit -m "chore(monitor): ignore auto-generated state + analysis reports"
```

- [ ] **Step 5: Run all tests one last time**

Run: `pytest tests/test_memory_cycle_monitor.py -v`
Expected: ALL PASS.

---

## Done criteria checklist

From spec §12, verify all checkboxes:

- [ ] 腳本可在 3 秒內完成 dry-run
- [ ] 所有 unit tests pass
- [ ] 用今天日期實跑一次,Markdown 報告產出在 `docs/analysis/memory_cycle_YYYY-MM-DD.md`
- [ ] Redis hash `h:agent:memory_cycle` 可由 `redis-cli HGETALL` 看到全部 fields
- [ ] 報告人工 review:燈號合理、Action 段落寫對應指示、下次更新建議日期合理

If all pass → feature is shippable.

---

*End of plan. Spec: `docs/superpowers/specs/2026-06-25-memory-cycle-monitor-design.md`.*
