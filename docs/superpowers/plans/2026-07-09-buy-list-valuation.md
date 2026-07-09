# Buy-List Valuation Display + Priority-Trim Rule — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/buy_list_daily_alert.py` show each pick/watch's P/B + light (from Redis hash `h:agent:pb_lights`) plus PE/殖利率 recomputed at the latest close, and flag `🔴 優先減碼` for picks that are both breaking stop AND at P/B RED.

**Architecture:** Five new pure functions (offline-tested) + a thin Redis loader, wired into the existing `build_digest`/`main`. P/B and its light come from the hash (single source of truth, matches the trim rule); PE/殖利率 come from the Pilot_Reports `估值指標` block, rescaled by `latest_close / report_base_price`. Data gaps fail safe (N/A shown, no false trim).

**Tech Stack:** Python 3, redis, pytest. Reuses `utils.find_ticker_files`. Spec: `docs/superpowers/specs/2026-07-09-buy-list-valuation-design.md`.

---

## File Structure

- Modify: `scripts/buy_list_daily_alert.py` — add 5 pure functions + `load_pb_lights`, wire into `build_digest` + `main`.
- Create: `tests/test_buy_list_valuation.py` — offline unit tests (fixtures + fake redis).

Module constants to add near the top of `buy_list_daily_alert.py` (with existing imports — confirm `json`, `sys`, `re`, `Path` are imported; add any missing):

```python
from utils import find_ticker_files  # scripts/ is already on sys.path in this module

PB_LIGHTS_KEY = "h:agent:pb_lights"
PB_LIGHT_EMOJI = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢", "N/A": "⚪"}
```

Test file header:

```python
from __future__ import annotations
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import buy_list_daily_alert as bl  # noqa: E402
```

---

### Task 1: `load_pb_lights` — read the Redis hash, fail-safe

**Files:**
- Modify: `scripts/buy_list_daily_alert.py`
- Test: `tests/test_buy_list_valuation.py`

- [ ] **Step 1: Write the failing test**

```python
class _FakeRedis:
    def __init__(self, data, boom=False):
        self._data = data
        self._boom = boom
    def hgetall(self, key):
        if self._boom:
            raise ConnectionError("redis down")
        return self._data


def test_load_pb_lights_parses_and_skips_meta():
    fake = _FakeRedis({
        "2408": '{"light":"RED","pb_current":7.2,"percentile":99,"p70":1.3,"p85":3.5,"asof":"2026-07-09","source":"cache fast-path"}',
        "_count": "50", "_updated": "2026-07-09T08:35",
    })
    out = bl.load_pb_lights(fake)
    assert set(out) == {"2408"}           # meta fields skipped
    assert out["2408"]["light"] == "RED"
    assert out["2408"]["pb_current"] == 7.2


def test_load_pb_lights_bad_json_skipped_and_redis_down_empty():
    assert bl.load_pb_lights(_FakeRedis({"2408": "{not json"})) == {}
    assert bl.load_pb_lights(_FakeRedis({}, boom=True)) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k load_pb_lights -v`
Expected: FAIL — `AttributeError: module 'buy_list_daily_alert' has no attribute 'load_pb_lights'`.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/buy_list_daily_alert.py` (ensure `import json`, `import sys` present):

```python
def load_pb_lights(redis_client) -> dict:
    """Read h:agent:pb_lights → {ticker: record}. Fail-safe: missing/bad → skipped; redis error → {}."""
    try:
        raw = redis_client.hgetall(PB_LIGHTS_KEY)
    except Exception as e:
        print(f"[warn] load_pb_lights: {PB_LIGHTS_KEY} unreachable: {e}", file=sys.stderr)
        return {}
    out = {}
    for k, v in (raw or {}).items():
        if k.startswith("_"):
            continue
        try:
            out[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            continue
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k load_pb_lights -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/buy_list_daily_alert.py tests/test_buy_list_valuation.py
git commit -m "feat(buy-list): load_pb_lights reads h:agent:pb_lights fail-safe"
```

---

### Task 2: `parse_report_valuation` — extract PE / 殖利率 / base price from the report

**Files:**
- Modify: `scripts/buy_list_daily_alert.py`
- Test: `tests/test_buy_list_valuation.py`

The `估值指標` block looks like:
```
### 估值指標 (殖利率 1.33%) (股價 $4,030.00 as of 2026-07-08)
| P/E (TTM) | Forward P/E | P/S (TTM) |   P/B | EV/EBITDA |
|-----------|-------------|-----------|-------|-----------|
|     64.22 |         N/A |       N/A | 16.48 |       N/A |
```

- [ ] **Step 1: Write the failing test**

```python
_REPORT_FIXTURE = """# 2454 - [[聯發科]]
## 估值概況
### 估值指標 (殖利率 1.33%) (股價 $4,030.00 as of 2026-07-08)
| P/E (TTM) | Forward P/E | P/S (TTM) |   P/B | EV/EBITDA |
|-----------|-------------|-----------|-------|-----------|
|     64.22 |         N/A |       N/A | 16.48 |       N/A |
"""

def test_parse_report_valuation_extracts_fields(tmp_path):
    fp = tmp_path / "2454_聯發科.md"
    fp.write_text(_REPORT_FIXTURE, encoding="utf-8")
    v = bl.parse_report_valuation("2454", files={"2454": str(fp)})
    assert v["pe"] == 64.22
    assert v["yield_pct"] == 1.33
    assert v["base_price"] == 4030.0


def test_parse_report_valuation_missing_file_returns_none():
    assert bl.parse_report_valuation("9999", files={}) is None


def test_parse_report_valuation_na_pe(tmp_path):
    txt = _REPORT_FIXTURE.replace("     64.22 ", "       N/A ")
    fp = tmp_path / "2454_聯發科.md"
    fp.write_text(txt, encoding="utf-8")
    v = bl.parse_report_valuation("2454", files={"2454": str(fp)})
    assert v["pe"] is None
    assert v["yield_pct"] == 1.33
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k parse_report_valuation -v`
Expected: FAIL — attribute `parse_report_valuation` does not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/buy_list_daily_alert.py` (ensure `import re` present):

```python
def parse_report_valuation(ticker: str, files: dict | None = None) -> dict | None:
    """From the report's 估值指標 block: {pe, yield_pct, base_price}. Missing file → None; unparseable field → None."""
    files = files if files is not None else find_ticker_files([ticker])
    fp = files.get(ticker)
    if not fp:
        return None
    text = Path(fp).read_text(encoding="utf-8", errors="replace")
    idx = text.find("估值指標")
    if idx == -1:
        return None
    header = text[idx:text.find("\n", idx)]
    mp = re.search(r"股價\s*\$([\d,]+\.?\d*)", header)
    base_price = float(mp.group(1).replace(",", "")) if mp else None
    my = re.search(r"殖利率\s*([\d.]+)%", header)
    yield_pct = float(my.group(1)) if my else None
    pe = None
    rows = [ln for ln in text[idx:].splitlines() if ln.strip().startswith("|")]
    # rows[0] header, rows[1] separator, rows[2] data
    if len(rows) >= 3:
        cells = [c.strip() for c in rows[2].strip().strip("|").split("|")]
        if cells and cells[0] not in ("N/A", ""):
            try:
                pe = float(cells[0])
            except ValueError:
                pe = None
    return {"pe": pe, "yield_pct": yield_pct, "base_price": base_price}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k parse_report_valuation -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/buy_list_daily_alert.py tests/test_buy_list_valuation.py
git commit -m "feat(buy-list): parse_report_valuation extracts PE/yield/base-price"
```

---

### Task 3: `recompute_valuation` — rescale PE / 殖利率 to the latest close

**Files:**
- Modify: `scripts/buy_list_daily_alert.py`
- Test: `tests/test_buy_list_valuation.py`

- [ ] **Step 1: Write the failing test**

```python
def test_recompute_valuation_scales_by_price_ratio():
    rv = bl.recompute_valuation({"pe": 64.22, "yield_pct": 1.33, "base_price": 4030.0}, 4433.0)
    assert rv["pe"] == pytest.approx(64.22 * 4433.0 / 4030.0, rel=1e-4)   # ≈ 70.6, PE up with price
    assert rv["yield_pct"] == pytest.approx(1.33 * 4030.0 / 4433.0, rel=1e-4)  # ≈ 1.21, yield down


def test_recompute_valuation_none_inputs():
    assert bl.recompute_valuation(None, 100.0) == {"pe": None, "yield_pct": None}
    assert bl.recompute_valuation({"pe": 10, "yield_pct": 2, "base_price": None}, 100.0) == {"pe": None, "yield_pct": None}
    assert bl.recompute_valuation({"pe": 10, "yield_pct": 2, "base_price": 50.0}, None) == {"pe": None, "yield_pct": None}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k recompute_valuation -v`
Expected: FAIL — attribute does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def recompute_valuation(report_val: dict | None, latest_close: float | None) -> dict:
    """Rescale PE (∝ price) and 殖利率 (∝ 1/price) from report base price to latest close."""
    if not report_val:
        return {"pe": None, "yield_pct": None}
    base = report_val.get("base_price")
    if not base or not latest_close:
        return {"pe": None, "yield_pct": None}
    ratio = latest_close / base
    pe = report_val.get("pe")
    y = report_val.get("yield_pct")
    return {
        "pe": pe * ratio if pe is not None else None,
        "yield_pct": y / ratio if y is not None else None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k recompute_valuation -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/buy_list_daily_alert.py tests/test_buy_list_valuation.py
git commit -m "feat(buy-list): recompute_valuation rescales PE/yield to latest close"
```

---

### Task 4: `format_valuation` — the display suffix string

**Files:**
- Modify: `scripts/buy_list_daily_alert.py`
- Test: `tests/test_buy_list_valuation.py`

- [ ] **Step 1: Write the failing test**

```python
def test_format_valuation_full():
    s = bl.format_valuation(
        {"light": "RED", "pb_current": 7.2},
        {"pe": 64.22, "yield_pct": 1.33, "base_price": 4030.0},
        4030.0,
    )
    assert "P/B 7.20 🔴" in s
    assert "PE 64.2" in s
    assert "殖 1.3%" in s


def test_format_valuation_na_when_missing():
    s = bl.format_valuation({}, None, None)
    assert "P/B N/A ⚪" in s
    assert "PE N/A" in s
    assert "殖 N/A" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k format_valuation -v`
Expected: FAIL — attribute does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def format_valuation(pb_rec: dict | None, report_val: dict | None, latest_close: float | None) -> str:
    """Compose 'P/B 7.20 🔴 · PE 64.2 · 殖 1.3%'. P/B+light from hash; PE/殖 rescaled from report."""
    rec = pb_rec or {}
    light = rec.get("light", "N/A")
    emoji = PB_LIGHT_EMOJI.get(light, "⚪")
    pb = rec.get("pb_current")
    pb_str = f"{pb:.2f}" if isinstance(pb, (int, float)) else "N/A"
    rv = recompute_valuation(report_val, latest_close)
    pe_str = f"{rv['pe']:.1f}" if rv["pe"] is not None else "N/A"
    y_str = f"{rv['yield_pct']:.1f}%" if rv["yield_pct"] is not None else "N/A"
    return f"P/B {pb_str} {emoji} · PE {pe_str} · 殖 {y_str}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k format_valuation -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/buy_list_daily_alert.py tests/test_buy_list_valuation.py
git commit -m "feat(buy-list): format_valuation display suffix"
```

---

### Task 5: `is_priority_trim` — stop-break AND P/B RED

**Files:**
- Modify: `scripts/buy_list_daily_alert.py`
- Test: `tests/test_buy_list_valuation.py`

- [ ] **Step 1: Write the failing test**

```python
def _pick(stop=100.0):
    return {"ticker": "T", "stop_loss": stop, "entry_range": [110, 120], "tp1": 150}

def test_is_priority_trim_quadrants():
    # stop-break (close ≤ stop×1.02) AND RED → True
    assert bl.is_priority_trim(_pick(100), {"latest_close": 101.0}, {"light": "RED"}) is True
    # stop-break but GREEN → False
    assert bl.is_priority_trim(_pick(100), {"latest_close": 101.0}, {"light": "GREEN"}) is False
    # above stop but RED → False
    assert bl.is_priority_trim(_pick(100), {"latest_close": 130.0}, {"light": "RED"}) is False
    # N/A light → False
    assert bl.is_priority_trim(_pick(100), {"latest_close": 101.0}, {"light": "N/A"}) is False
    # no close → False
    assert bl.is_priority_trim(_pick(100), {}, {"light": "RED"}) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k is_priority_trim -v`
Expected: FAIL — attribute does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def is_priority_trim(pick: dict, snap: dict, pb_rec: dict | None) -> bool:
    """True iff close ≤ stop_loss×1.02 AND the hash light is RED. Data gap → False (fail-safe)."""
    close = snap.get("latest_close")
    if close is None:
        return False
    if close > pick["stop_loss"] * 1.02:
        return False
    return (pb_rec or {}).get("light") == "RED"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k is_priority_trim -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/buy_list_daily_alert.py tests/test_buy_list_valuation.py
git commit -m "feat(buy-list): is_priority_trim (stop-break AND P/B RED)"
```

---

### Task 6: Wire valuation + priority-trim into `build_digest` and `main`

**Files:**
- Modify: `scripts/buy_list_daily_alert.py` (`build_digest` ~L188-291, `main` ~L305)
- Test: `tests/test_buy_list_valuation.py`

**Wiring details:**
- `build_digest` gains a `pb_lights: dict | None = None` param (default `{}` inside). Add a per-run report cache `report_cache: dict = {}` and a local helper to avoid re-parsing a ticker present in both picks and watch:
  ```python
  def _val_suffix(sym, snap, pick_or_watch, pb_lights, report_cache):
      close = snap.get("latest_close")
      if sym not in report_cache:
          report_cache[sym] = parse_report_valuation(sym)
      pb_rec = pb_lights.get(sym, {})
      return pb_rec, format_valuation(pb_rec, report_cache[sym], close)
  ```
- In the **picks loop** (after `line += f" · **{urgency_label}**"`, inside `if close:`), append:
  ```python
  pb_rec, vstr = _val_suffix(sym, snap, pick, pb_lights, report_cache)
  line += f" · {vstr}"
  if is_priority_trim(pick, snap, pb_rec):
      line += " · 🔴 優先減碼 (P/B RED)"
  ```
- In the **watch-list rendering** (the section iterating `state.get("watch_list", [])` with a `close`), append `f" · {format_valuation(pb_lights.get(w['ticker'], {}), report_cache.setdefault(w['ticker'], parse_report_valuation(w['ticker'])), c)}"` to each watch line (no trim marker on watch — trim applies to held picks only).
- `main()`: build a redis client the same way `push_inbox` does (`redis.Redis(host="localhost", port=6379, decode_responses=True)`), call `pb_lights = load_pb_lights(client)`, and pass `pb_lights=pb_lights` into `build_digest`. Wrap the client construction in try/except → `pb_lights = {}` + `[warn]` on failure (never block the digest).

- [ ] **Step 1: Write the failing test**

```python
def test_build_digest_shows_valuation_and_priority_trim(monkeypatch):
    # a pick that is breaking stop and RED → 優先減碼; report parse stubbed
    state = {
        "version": "t", "picks": [
            {"ticker": "2454", "name": "聯發科", "tier": 1, "weight_pct": 20,
             "entry_range": [4250, 4350], "stop_loss": 4250, "tp1": 4700},
        ],
        "watch_list": [], "avoid_list": [],
    }
    snapshots = {"2454": {"latest_close": 4030.0, "f5": -100.0, "f20": 10.0, "t20": 0}}
    monkeypatch.setattr(bl, "parse_report_valuation",
                        lambda t, files=None: {"pe": 64.22, "yield_pct": 1.33, "base_price": 4030.0})
    pb_lights = {"2454": {"light": "RED", "pb_current": 7.2}}
    md = bl.build_digest(state, snapshots, {}, {}, pb_lights=pb_lights)
    assert "P/B 7.20 🔴" in md
    assert "PE 64.2" in md
    assert "🔴 優先減碼 (P/B RED)" in md


def test_build_digest_no_trim_when_green(monkeypatch):
    state = {"version": "t", "picks": [
        {"ticker": "2454", "name": "聯發科", "tier": 1, "weight_pct": 20,
         "entry_range": [4250, 4350], "stop_loss": 4250, "tp1": 4700}],
        "watch_list": [], "avoid_list": []}
    snapshots = {"2454": {"latest_close": 4030.0, "f5": 0, "f20": 0, "t20": 0}}
    monkeypatch.setattr(bl, "parse_report_valuation", lambda t, files=None: None)
    md = bl.build_digest(state, snapshots, {}, {}, pb_lights={"2454": {"light": "GREEN", "pb_current": 3.0}})
    assert "優先減碼" not in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k build_digest -v`
Expected: FAIL — `build_digest() got an unexpected keyword argument 'pb_lights'`.

- [ ] **Step 3: Implement the wiring**

Apply the wiring described above: add the `pb_lights` param + `report_cache` + `_val_suffix` helper to `build_digest`; append valuation to pick lines and the priority-trim marker; append valuation to watch lines; update `main` to load and pass `pb_lights`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -k build_digest -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full new suite + a real dry-run smoke**

Run: `python3 -m pytest tests/test_buy_list_valuation.py -v`
Expected: all PASS.

Run: `python3 scripts/buy_list_daily_alert.py --dry-run 2>&1 | grep -E "P/B|優先減碼" | head`
Expected: pick lines show `P/B .. · PE .. · 殖 ..`; the stop-breaking RED picks (2454/3037/3711/3017 per today's data) show `🔴 優先減碼`.

- [ ] **Step 6: Commit**

```bash
git add scripts/buy_list_daily_alert.py tests/test_buy_list_valuation.py
git commit -m "feat(buy-list): wire valuation display + priority-trim into digest"
```

---

## Self-Review

**Spec coverage:**
- C① valuation display (P/B+light from hash, PE/殖利率 recomputed) → Tasks 1–4 + Task 6 wiring. ✅
- C② priority-trim rule (stop-break AND RED → 優先減碼) → Task 5 + Task 6 urgent-section wiring. ✅
- Picks + watch scope → Task 6 wires both loops; report parsed only for picks+watch via `report_cache`. ✅
- P/B unified on hash; report only for PE/yield/base-price → `format_valuation` uses hash P/B, `parse_report_valuation` returns no P/B. ✅
- Error handling (hash empty → N/A no trim; report missing → PE/殖 N/A; close missing → trim False) → `load_pb_lights` (Task 1), `parse_report_valuation`/`recompute_valuation` None paths (Tasks 2–3), `is_priority_trim` guards (Task 5). ✅
- Tests 1–5 from spec → Tasks 1–5 unit tests + Task 6 integration. ✅

**Placeholder scan:** none — every step has complete code.

**Type consistency:** `pb_rec` records use keys `light`/`pb_current` (from `pb_lights_publish` hash) consistently; `report_val` uses `pe`/`yield_pct`/`base_price` across Tasks 2–4; `recompute_valuation` returns `{pe, yield_pct}` consumed by `format_valuation`; `build_digest` `pb_lights` param name consistent Task 6 wiring ↔ tests. ✅

**Note for executor:** `percentile` in the hash is often `null` (engine-A fast-path) — this plan never reads `percentile`; the display uses `pb_current` + `light` only, and the trim rule keys on `light`. Do not surface `percentile`.
