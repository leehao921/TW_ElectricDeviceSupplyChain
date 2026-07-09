# 處置股 Lifecycle Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `scripts/disposition_daily_fetch.py` (the 08:35 disposition routine) to neutrally track each disposition stock's full lifecycle — enter → during → release → post (T+1/5/20) → history — and surface a `disposition-track` inbox digest with accumulating conditional statistics, so we can later test whether disposition marks a top (A), a post-release resume (B), or repeat-disposition danger (C).

**Architecture:** A state machine over `data/disposition_tracking_state.json` (currently-tracked names) + a lifetime log `data/disposition_tracking_history.json`, mirroring the proven `bb_followthrough_track.py` pattern. Pure functions (entry/snapshot/release/graduate/stats/digest) are unit-tested offline; DB price+flow helpers are reused from `bb_followthrough_track` (DRY). Tracking runs inside the existing 08:35 process using the prior trading day's close.

**Tech Stack:** Python 3, psycopg2 (via reused helpers), redis, pytest. Spec: `docs/superpowers/specs/2026-07-09-disposition-tracker-design.md`.

---

## File Structure

- Modify: `scripts/disposition_daily_fetch.py` — add lifecycle state machine, DB snapshot pass, `disposition-track` digest, and `main()` wiring. Reuse DB helpers via `from bb_followthrough_track import DB_CONFIG, fetch_daily_snapshot, fetch_20d_foreign` (both scripts are in `scripts/`, on sys.path when run).
- Create: `tests/test_disposition_tracker.py` — offline unit tests (fixtures, no DB/network).

Module constants to add near the existing `STATE_PATH` (`scripts/disposition_daily_fetch.py:33`):

```python
TRACK_STATE_PATH = REPO / "data" / "disposition_tracking_state.json"
TRACK_HISTORY_PATH = REPO / "data" / "disposition_tracking_history.json"
POST_TRACK_DAYS = 20      # graduate at T+20 after release
MIN_STATS_SAMPLES = 10    # below this, show "樣本累積中"
```

Test header:

```python
from __future__ import annotations
import sys, json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import disposition_daily_fetch as dt  # noqa: E402
```

Record shapes (used across tasks — keep consistent):

```python
# tracking-state entry (one per currently-tracked ticker)
{
  "ticker": "3055", "name": "蔚華科",
  "enter_date": "2026-07-02", "disp_start": "2026-07-02", "disp_end": "2026-07-15",
  "condition": "連續三次", "count_label": "第二次處置", "count_n": 2, "source": "TWSE",
  "runup_5d_pct": 12.3, "runup_20d_pct": 41.0,
  "foreign_5d_at_enter": 7.5, "foreign_20d_at_enter": 7.3,
  "enter_close": 155.0,
  "during": [ {"d": "2026-07-02", "close": 155.0, "cumret_pct": 0.0, "foreign_1d": 0.3} ],
  "release_date": None,            # set when released
  "post": {"t1": None, "t5": None, "t20": None},   # returns vs release close
  "release_close": None,
}
```

---

### Task 1: `count_to_n` — normalize disposition count label to an integer

**Files:**
- Modify: `scripts/disposition_daily_fetch.py`
- Test: `tests/test_disposition_tracker.py`

- [ ] **Step 1: Write the failing test**

```python
def test_count_to_n():
    assert dt.count_to_n("第一次處置") == 1
    assert dt.count_to_n("第二次處置") == 2
    assert dt.count_to_n("第三次處置") == 3
    assert dt.count_to_n("連續三次") == 1     # condition text, not a count → default 1
    assert dt.count_to_n(None) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k count_to_n -v`
Expected: FAIL — attribute `count_to_n` does not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/disposition_daily_fetch.py`:

```python
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}

def count_to_n(action_label: str | None) -> int:
    """Map '第二次處置' → 2. Non-count text or None → 1."""
    if not action_label:
        return 1
    import re as _re
    m = _re.search(r"第([一二三四五六七八九])次處置", action_label)
    if not m:
        return 1
    return _CN_NUM.get(m.group(1), 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k count_to_n -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/disposition_daily_fetch.py tests/test_disposition_tracker.py
git commit -m "feat(disposition-track): count_to_n normalizes disposition count label"
```

---

### Task 2: `record_entry` — build a tracking entry from disposition + market data

**Files:**
- Modify: `scripts/disposition_daily_fetch.py`
- Test: `tests/test_disposition_tracker.py`

- [ ] **Step 1: Write the failing test**

```python
def test_record_entry_builds_full_record():
    disp = {"name": "蔚華科", "start": "2026-07-02", "end": "2026-07-15",
            "condition": "連續三次", "action": "第二次處置", "source": "TWSE"}
    market = {"enter_close": 155.0, "runup_5d_pct": 12.3, "runup_20d_pct": 41.0,
              "foreign_5d": 7.5, "foreign_20d": 7.3, "foreign_1d": 0.3}
    e = dt.record_entry("3055", disp, market, "2026-07-02")
    assert e["ticker"] == "3055" and e["count_n"] == 2
    assert e["runup_20d_pct"] == 41.0 and e["enter_close"] == 155.0
    assert e["release_date"] is None
    assert e["during"] == [{"d": "2026-07-02", "close": 155.0, "cumret_pct": 0.0, "foreign_1d": 0.3}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k record_entry -v`
Expected: FAIL — attribute does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def record_entry(ticker: str, disp: dict, market: dict, as_of: str) -> dict:
    """Assemble a new tracking-state entry at disposition entry."""
    close = market.get("enter_close")
    return {
        "ticker": ticker, "name": disp.get("name", ""),
        "enter_date": as_of, "disp_start": disp.get("start"), "disp_end": disp.get("end"),
        "condition": disp.get("condition"), "count_label": disp.get("action"),
        "count_n": count_to_n(disp.get("action")), "source": disp.get("source"),
        "runup_5d_pct": market.get("runup_5d_pct"), "runup_20d_pct": market.get("runup_20d_pct"),
        "foreign_5d_at_enter": market.get("foreign_5d"), "foreign_20d_at_enter": market.get("foreign_20d"),
        "enter_close": close,
        "during": [{"d": as_of, "close": close, "cumret_pct": 0.0, "foreign_1d": market.get("foreign_1d")}],
        "release_date": None, "release_close": None,
        "post": {"t1": None, "t5": None, "t20": None},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k record_entry -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/disposition_daily_fetch.py tests/test_disposition_tracker.py
git commit -m "feat(disposition-track): record_entry builds lifecycle entry"
```

---

### Task 3: `append_during` — daily during-disposition snapshot, idempotent

**Files:**
- Modify: `scripts/disposition_daily_fetch.py`
- Test: `tests/test_disposition_tracker.py`

- [ ] **Step 1: Write the failing test**

```python
def _entry():
    return {"ticker": "3055", "enter_close": 100.0,
            "during": [{"d": "2026-07-02", "close": 100.0, "cumret_pct": 0.0, "foreign_1d": 0.0}]}

def test_append_during_computes_cumret_and_is_idempotent():
    e = _entry()
    dt.append_during(e, {"close": 110.0, "foreign_1d": 1.2}, "2026-07-03")
    assert e["during"][-1] == {"d": "2026-07-03", "close": 110.0, "cumret_pct": 10.0, "foreign_1d": 1.2}
    # same-day re-run must NOT duplicate
    dt.append_during(e, {"close": 999.0, "foreign_1d": 9.9}, "2026-07-03")
    assert len([s for s in e["during"] if s["d"] == "2026-07-03"]) == 1
    assert e["during"][-1]["close"] == 110.0     # first write wins on re-run
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k append_during -v`
Expected: FAIL — attribute does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def append_during(entry: dict, snap: dict, as_of: str) -> None:
    """Append a during-disposition daily snapshot. No-op if as_of already recorded (idempotent)."""
    if any(s["d"] == as_of for s in entry["during"]):
        return
    base = entry["enter_close"]
    close = snap.get("close")
    cumret = round((close - base) / base * 100, 2) if base and close else None
    entry["during"].append({"d": as_of, "close": close, "cumret_pct": cumret,
                            "foreign_1d": snap.get("foreign_1d")})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k append_during -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/disposition_daily_fetch.py tests/test_disposition_tracker.py
git commit -m "feat(disposition-track): append_during idempotent daily snapshot"
```

---

### Task 4: `mark_release` + `record_post` — release detection and post-release returns

**Files:**
- Modify: `scripts/disposition_daily_fetch.py`
- Test: `tests/test_disposition_tracker.py`

- [ ] **Step 1: Write the failing test**

```python
def test_mark_release_sets_date_and_close_once():
    e = {"ticker": "3055", "release_date": None, "release_close": None}
    dt.mark_release(e, {"close": 120.0}, "2026-07-16")
    assert e["release_date"] == "2026-07-16" and e["release_close"] == 120.0
    dt.mark_release(e, {"close": 130.0}, "2026-07-17")   # already released → no change
    assert e["release_date"] == "2026-07-16" and e["release_close"] == 120.0

def test_record_post_fills_checkpoints():
    e = {"release_date": "2026-07-16", "release_close": 100.0,
         "post": {"t1": None, "t5": None, "t20": None}}
    dt.record_post(e, {"close": 105.0}, days_since_release=1)
    assert e["post"]["t1"] == 5.0
    dt.record_post(e, {"close": 90.0}, days_since_release=5)
    assert e["post"]["t5"] == -10.0
    dt.record_post(e, {"close": 100.0}, days_since_release=3)   # not a checkpoint → unchanged
    assert e["post"]["t20"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k "mark_release or record_post" -v`
Expected: FAIL — attributes do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def mark_release(entry: dict, snap: dict, as_of: str) -> None:
    """Set release_date/close on first release detection (idempotent)."""
    if entry.get("release_date"):
        return
    entry["release_date"] = as_of
    entry["release_close"] = snap.get("close")

def record_post(entry: dict, snap: dict, days_since_release: int) -> None:
    """Record T+1/T+5/T+20 return vs release close at the matching checkpoint."""
    base = entry.get("release_close")
    close = snap.get("close")
    if not base or not close:
        return
    key = {1: "t1", 5: "t5", 20: "t20"}.get(days_since_release)
    if key and entry["post"].get(key) is None:
        entry["post"][key] = round((close - base) / base * 100, 2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k "mark_release or record_post" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/disposition_daily_fetch.py tests/test_disposition_tracker.py
git commit -m "feat(disposition-track): mark_release + record_post checkpoints"
```

---

### Task 5: `compute_conditional_stats` — grouped win-rate / median (or 樣本累積中)

**Files:**
- Modify: `scripts/disposition_daily_fetch.py`
- Test: `tests/test_disposition_tracker.py`

Grouping: `count_group` = "1st" if `count_n == 1` else "2nd+"; `flow_group` = "法人接" if `foreign_20d_at_enter >= 0` else "法人撤". Success at a horizon = post return > 0.

- [ ] **Step 1: Write the failing test**

```python
def _hist_entry(count_n, f20, t5, t20):
    return {"count_n": count_n, "foreign_20d_at_enter": f20, "post": {"t1": None, "t5": t5, "t20": t20}}

def test_conditional_stats_below_threshold():
    stats = dt.compute_conditional_stats([_hist_entry(1, 5, 3, 4)], min_samples=10)
    assert stats["enough"] is False and stats["n"] == 1

def test_conditional_stats_groups_and_winrate():
    hist = [_hist_entry(2, -1, -5, -8) for _ in range(6)] + [_hist_entry(1, 5, 4, 9) for _ in range(6)]
    stats = dt.compute_conditional_stats(hist, min_samples=10)
    assert stats["enough"] is True and stats["n"] == 12
    g = stats["groups"]
    # 2nd+ & 法人撤 → all negative T+20 → win-rate 0
    assert g["2nd+/法人撤"]["t20_winrate"] == 0.0
    # 1st & 法人接 → all positive T+20 → win-rate 100
    assert g["1st/法人接"]["t20_winrate"] == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k conditional_stats -v`
Expected: FAIL — attribute does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
from statistics import median as _median

def _grp(e):
    cg = "1st" if e.get("count_n", 1) == 1 else "2nd+"
    f20 = e.get("foreign_20d_at_enter")
    fg = "法人接" if (f20 is not None and f20 >= 0) else "法人撤"
    return f"{cg}/{fg}"

def compute_conditional_stats(history: list[dict], min_samples: int = MIN_STATS_SAMPLES) -> dict:
    """Group graduated history by (count 1st/2nd+) × (entry 20D 法人接/撤); win-rate + median T+5/T+20."""
    graded = [e for e in history if e.get("post", {}).get("t20") is not None]
    if len(graded) < min_samples:
        return {"enough": False, "n": len(graded), "groups": {}}
    groups: dict[str, dict] = {}
    buckets: dict[str, list] = {}
    for e in graded:
        buckets.setdefault(_grp(e), []).append(e)
    for key, es in buckets.items():
        t5 = [e["post"]["t5"] for e in es if e["post"].get("t5") is not None]
        t20 = [e["post"]["t20"] for e in es if e["post"].get("t20") is not None]
        groups[key] = {
            "n": len(es),
            "t5_winrate": round(sum(1 for x in t5 if x > 0) / len(t5) * 100, 1) if t5 else None,
            "t20_winrate": round(sum(1 for x in t20 if x > 0) / len(t20) * 100, 1) if t20 else None,
            "t5_median": round(_median(t5), 1) if t5 else None,
            "t20_median": round(_median(t20), 1) if t20 else None,
        }
    return {"enough": True, "n": len(graded), "groups": groups}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k conditional_stats -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/disposition_daily_fetch.py tests/test_disposition_tracker.py
git commit -m "feat(disposition-track): compute_conditional_stats grouped win-rate"
```

---

### Task 6: `build_track_digest` — the disposition-track inbox message

**Files:**
- Modify: `scripts/disposition_daily_fetch.py`
- Test: `tests/test_disposition_tracker.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_track_digest_sections():
    state = {"tracked": {
        "3055": {"ticker": "3055", "name": "蔚華科", "enter_date": "2026-07-09",
                 "runup_5d_pct": 12.3, "runup_20d_pct": 41.0, "count_label": "第二次處置",
                 "foreign_20d_at_enter": 7.3, "disp_end": "2026-07-22", "release_date": None,
                 "during": [{"d": "2026-07-09", "close": 158.0, "cumret_pct": 0.0, "foreign_1d": 0.0}],
                 "post": {"t1": None, "t5": None, "t20": None}},
    }}
    md = dt.build_track_digest(state, history=[], as_of="2026-07-09")
    assert "處置股追蹤" in md
    assert "3055" in md and "第二次處置" in md
    assert "樣本累積中" in md          # empty history → stats not enough
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k build_track_digest -v`
Expected: FAIL — attribute does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def build_track_digest(state: dict, history: list[dict], as_of: str) -> str:
    tracked = state.get("tracked", {})
    lines = [f"# 📈 處置股追蹤 {as_of} (追蹤中 {len(tracked)} 檔)"]

    new_today = [e for e in tracked.values() if e.get("enter_date") == as_of]
    if new_today:
        lines.append(f"\n## 🆕 今日新進處置 ({len(new_today)})")
        for e in new_today:
            lines.append(f"- **{e['ticker']} {e['name']}** {e.get('count_label','')} · "
                         f"進場前 5D {e.get('runup_5d_pct')}% / 20D {e.get('runup_20d_pct')}% · "
                         f"20D 外資 {e.get('foreign_20d_at_enter')}億")

    releasing = [e for e in tracked.values()
                 if not e.get("release_date") and e.get("disp_end") in (as_of, _next_trading_day(as_of))]
    if releasing:
        lines.append(f"\n## 🔓 今日/明日解除 ({len(releasing)})")
        for e in releasing:
            lines.append(f"- **{e['ticker']} {e['name']}** 解除 {e.get('disp_end')} · "
                         f"處置期累計 {e['during'][-1].get('cumret_pct')}%")

    post = [e for e in tracked.values() if e.get("release_date")]
    if post:
        lines.append(f"\n## 📊 解除後表現 ({len(post)})")
        for e in post:
            p = e["post"]
            lines.append(f"- **{e['ticker']} {e['name']}** T+1 {p.get('t1')}% · T+5 {p.get('t5')}% · T+20 {p.get('t20')}%")

    stats = compute_conditional_stats(history)
    lines.append("\n## 📈 累積條件統計")
    if not stats["enough"]:
        lines.append(f"樣本累積中 ({stats['n']}/{MIN_STATS_SAMPLES})")
    else:
        for key, g in sorted(stats["groups"].items()):
            lines.append(f"- **{key}** (n={g['n']}): T+5 勝率 {g['t5_winrate']}% (中位 {g['t5_median']}%) · "
                         f"T+20 勝率 {g['t20_winrate']}% (中位 {g['t20_median']}%)")

    lines.append(f"\n*源: scripts/disposition_daily_fetch.py · state {TRACK_STATE_PATH.name}*")
    return "\n".join(lines)
```

Also add the small helper (place near the ROC date helpers):

```python
def _next_trading_day(iso: str) -> str:
    """Next calendar day (approx next trading day; weekend skew acceptable for a ±1d release window)."""
    from datetime import date as _date, timedelta as _td
    y, m, d = (int(x) for x in iso.split("-"))
    return (_date(y, m, d) + _td(days=1)).isoformat()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k build_track_digest -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/disposition_daily_fetch.py tests/test_disposition_tracker.py
git commit -m "feat(disposition-track): build_track_digest sections + stats"
```

---

### Task 7: `update_tracking` + `main` wiring — the daily DB pass

**Files:**
- Modify: `scripts/disposition_daily_fetch.py`
- Test: `tests/test_disposition_tracker.py`

`update_tracking` is the orchestration: given the current `active` disposition dict, the loaded tracking `state`, a market-data lookup callable, and `as_of`, it (a) enters new dispositions, (b) snapshots during-disposition names, (c) detects releases, (d) records post checkpoints, (e) graduates T+20 names into `history`. The DB is abstracted behind a `market_fn(ticker, as_of) -> dict` callable so the orchestration is unit-testable without a database.

- [ ] **Step 1: Write the failing test**

```python
def test_update_tracking_enter_snapshot_release_graduate():
    # market_fn returns deterministic data
    def market_fn(ticker, as_of):
        return {"enter_close": 100.0, "close": 100.0, "runup_5d_pct": 5.0, "runup_20d_pct": 20.0,
                "foreign_5d": 1.0, "foreign_20d": 2.0, "foreign_1d": 0.1,
                "days_since_release": 0}
    state = {"tracked": {}}
    history = []
    active = {"3055": {"name": "蔚華科", "start": "2026-07-09", "end": "2026-07-09",
                       "condition": "x", "action": "第一次處置", "source": "TWSE"}}
    # Day 1: enters tracking
    dt.update_tracking(state, active, history, market_fn, "2026-07-09")
    assert "3055" in state["tracked"]
    # Day 2: no longer in active (end passed) → release marked
    dt.update_tracking(state, {}, history, market_fn, "2026-07-10")
    assert state["tracked"]["3055"]["release_date"] == "2026-07-10"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k update_tracking -v`
Expected: FAIL — attribute does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def _trading_days_between(a: str, b: str) -> int:
    """Approx trading-day gap (calendar days; good enough for T+N checkpoints)."""
    from datetime import date as _date
    ya, ma, da = (int(x) for x in a.split("-")); yb, mb, db = (int(x) for x in b.split("-"))
    return (_date(yb, mb, db) - _date(ya, ma, da)).days

def update_tracking(state: dict, active: dict, history: list, market_fn, as_of: str) -> None:
    """Advance the disposition lifecycle for as_of. market_fn(ticker, as_of)->dict abstracts the DB."""
    tracked = state.setdefault("tracked", {})
    # (a) enter new dispositions
    for ticker, disp in active.items():
        if ticker not in tracked:
            m = market_fn(ticker, as_of)
            if m:
                tracked[ticker] = record_entry(ticker, disp, m, as_of)
    # (b)-(e) advance existing
    graduated = []
    for ticker, entry in list(tracked.items()):
        m = market_fn(ticker, as_of) or {}
        still_disposed = ticker in active
        if not entry.get("release_date"):
            if still_disposed:
                append_during(entry, m, as_of)
            else:
                mark_release(entry, m, as_of)     # first day out of active
        else:
            dsr = _trading_days_between(entry["release_date"], as_of)
            record_post(entry, m, dsr)
            if dsr >= POST_TRACK_DAYS:
                history.append(entry)
                graduated.append(ticker)
    for t in graduated:
        del tracked[t]
```

Then wire `main()` (after the existing `save_state(active, ...)` block, only when not `--dry-run`):

```python
    # --- lifecycle tracking pass (reuses bb_followthrough DB helpers) ---
    try:
        import psycopg2
        from bb_followthrough_track import DB_CONFIG, fetch_daily_snapshot, fetch_20d_foreign
        conn = psycopg2.connect(**DB_CONFIG)
        def market_fn(ticker, as_of_):
            snap = fetch_daily_snapshot(conn, ticker, as_of_) or {}
            return {
                "enter_close": snap.get("close"), "close": snap.get("close"),
                "foreign_1d": snap.get("foreign_net"),
                "foreign_5d": snap.get("foreign_net"),  # best-effort; refine later
                "foreign_20d": fetch_20d_foreign(conn, ticker, as_of_),
                "runup_5d_pct": _return_pct(conn, ticker, as_of_, 5),
                "runup_20d_pct": _return_pct(conn, ticker, as_of_, 20),
            }
        track_state = load_json(TRACK_STATE_PATH) or {"tracked": {}}
        track_history = load_json(TRACK_HISTORY_PATH) or []
        update_tracking(track_state, active, track_history, market_fn, today_iso)
        _save_json(TRACK_STATE_PATH, track_state)
        _save_json(TRACK_HISTORY_PATH, track_history)
        conn.close()
        track_digest = build_track_digest(track_state, track_history, today_iso)
        print(track_digest)
        if not args.dry_run:
            push_inbox_track(track_digest, today_iso)
    except Exception as e:
        print(f"[warn] disposition tracking pass failed: {e}", file=sys.stderr)
```

Add the small helpers `_return_pct`, `_save_json`, `push_inbox_track`:

```python
def _return_pct(conn, ticker: str, as_of: str, lookback: int) -> float | None:
    """Cumulative % return over `lookback` trading rows into as_of, from stock_daily_ohlcv."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT close FROM stock_daily_ohlcv WHERE symbol=%s AND ts::date<=%s
                 ORDER BY ts DESC LIMIT %s
            """, (ticker, as_of, lookback + 1))
            rows = [r[0] for r in cur.fetchall()]
        if len(rows) < 2 or not rows[-1]:
            return None
        return round((rows[0] - rows[-1]) / rows[-1] * 100, 2)
    except Exception:
        return None

def _save_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def push_inbox_track(msg: str, as_of: str) -> bool:
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.xadd("claude:inbox", {"topic": "disposition-track", "from": "disposition_daily_fetch",
                                "tags": "disposition,track,daily", "as_of": as_of, "msg": msg})
        return True
    except Exception as e:
        print(f"[warn] disposition-track inbox push failed: {e}", file=sys.stderr)
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_disposition_tracker.py -k update_tracking -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + real smoke**

Run: `python3 -m pytest tests/test_disposition_tracker.py -v`
Expected: all PASS.

Run: `python3 scripts/disposition_daily_fetch.py --dry-run 2>&1 | grep -A3 "處置股追蹤" | head`
Expected: prints the tracking digest (new-disposition / releasing / stats sections). DB gaps degrade to N/A per the try/except; if the DB is unreachable it prints the `[warn]` and the existing disposition-alert digest still works.

- [ ] **Step 6: Commit**

```bash
git add scripts/disposition_daily_fetch.py tests/test_disposition_tracker.py
git commit -m "feat(disposition-track): update_tracking lifecycle pass + main wiring"
```

---

### Task 8: Register `disposition-track` in routine_watchdog

**Files:**
- Modify: `scripts/routine_watchdog.py`
- Test: `tests/test_routine_watchdog.py`

The tracking runs inside the existing `disposition-daily` launchd job (08:35), so no new plist. But it emits a distinct inbox topic; the watchdog should know it fires so a missed disposition run flags both topics. Since one launchd job now emits two topics (`disposition-alert` + `disposition-track`), add a registry row that maps the new topic to the SAME label.

- [ ] **Step 1: Write the failing test**

```python
def test_disposition_track_registered_same_label():
    checks = {c.key: c for c in rw.build_checks()}
    assert "disposition-track" in checks
    assert checks["disposition-track"].label == "com.lulala.disposition-daily"
    assert checks["disposition-track"].sched == time(8, 35)
```

(Add `from datetime import time` import to the test if not present.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_routine_watchdog.py -k disposition_track -v`
Expected: FAIL — no `disposition-track` check.

- [ ] **Step 3: Write minimal implementation**

Add to `_REGISTRY` in `scripts/routine_watchdog.py` (after the `disposition-alert` row):

```python
    ("disposition-track", "disposition-daily", time(8, 35), time(13, 30)),
```

Also update the existing `test_build_checks_expands_ma_touch_slots` count from 10 to 11 and add `"disposition-track"` to its key-set assertion.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_routine_watchdog.py -v`
Expected: all PASS (17 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/routine_watchdog.py tests/test_routine_watchdog.py
git commit -m "feat(disposition-track): register disposition-track topic in watchdog"
```

---

## Self-Review

**Spec coverage:**
- Extend disposition_daily_fetch, run in the 08:35 process, prior-close snapshots → Task 7 wiring. ✅
- Enter (5D+20D run-up, flow, count) → Tasks 1–2. ✅
- During (idempotent daily snapshot) → Task 3. ✅
- Release + post T+1/5/20 → Task 4. ✅
- Conditional stats (1st vs 2nd+ × 法人接/撤, threshold) → Task 5. ✅
- Digest with new/releasing/post/stats sections, topic `disposition-track` distinct from `disposition-alert` → Tasks 6–7. ✅
- State + history files (bb_followthrough pattern), idempotent re-run → Tasks 3, 7. ✅
- Fail-safe (DB/flow gaps don't crash, don't abort existing alert) → Task 7 try/except. ✅
- Watchdog registration → Task 8. ✅

**Placeholder scan:** none — every step has complete code. (`foreign_5d` in `market_fn` is a documented best-effort approximation, not a placeholder — refine later noted inline.)

**Type consistency:** entry record shape (`during`, `post.t1/t5/t20`, `count_n`, `foreign_20d_at_enter`, `release_date/close`, `runup_5d_pct/20d_pct`) consistent across Tasks 2–7; `market_fn(ticker, as_of) -> dict` signature consistent Tasks 7; `compute_conditional_stats` return (`enough`/`n`/`groups`) consistent Tasks 5–6; helpers `count_to_n`/`_return_pct`/`_save_json`/`push_inbox_track` referenced only where defined. ✅

**Note for executor:** the existing `disposition-alert` message and `save_state` for `disposition_current.json` MUST remain unchanged; the tracking pass is purely additive and wrapped in try/except so a DB outage never breaks the existing 08:35 alert.
