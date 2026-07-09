# 處置股生命週期 Tracker — Design Spec

**Date:** 2026-07-09
**Status:** Approved (design), pending implementation plan
**Relation:** Extends `scripts/disposition_daily_fetch.py` (the 08:35 disposition routine)

---

## Context / Strategy

Taiwan 處置 (disposition) throttles speculation (分盤 5–20 min matching, 預收款券,
10 trading days per period). The same event admits three opposite theses:

- **A. Disposition = momentum-climax top** (short/avoid) — the speculative
  premium deflates once trading friction arrives.
- **B. Post-release resume** (long the release day) — friction lifts; if the
  fundamental story is real, buying resumes.
- **C. Second/third disposition = danger** (avoid) — persistent speculation →
  violent unwind risk.

These are likely **conditional**, not mutually exclusive. Which one holds
probably depends on: run-up into disposition, 三大法人 flow during it,
disposition count (1st vs 2nd/3rd), and fundamental backing.

**Decision: neutral tracking first — let the data speak.** This spec builds an
evidence collector that records each disposition stock's full lifecycle. Once
enough samples accrue, conditional statistics (e.g. "1st vs 2nd disposition"
× "法人接 vs 撤" → T+5/T+20 win-rate) will tell us which thesis holds and under
what conditions. No directional alert bias is baked in yet.

---

## Where it lives

**Extend `scripts/disposition_daily_fetch.py`** (not a new script). That routine
already runs at **08:35** (launchd `com.lulala.disposition-daily`), fetches the
TWSE+TPEx disposition list, and writes `data/disposition_current.json`. The
lifecycle tracking is folded into the **same 08:35 run**, immediately after the
fetch — so no new launchd job is added. Because the run is pre-market, daily
snapshots use the **most recent available close** (prior trading day) + that
day's 三大法人 flow.

Single-responsibility note: the fetch/portfolio-alert digest (existing) and the
lifecycle-tracking digest (new) are separate concerns sharing one process; keep
their functions and their inbox messages distinct (existing topic
`disposition-alert`; new topic `disposition-track`).

---

## Data Sources

- `data/disposition_current.json` — active disposition entries `{ticker: {name,
  start, end, condition, action, source, count?}}` (written earlier in the same
  run).
- DB (`institutional_stock`) — daily close + 5D/20D 外資 & 投信 net flow (reuse
  the existing snapshot/flow helpers already in the disposition/buy-list
  scripts, e.g. the `fetch_*_foreign` / snapshot patterns). Note OTC close gaps
  (per project memory): fall back to yfinance `.TWO` where the DB lacks OTC
  close.

---

## Lifecycle State Machine

State file `data/disposition_tracking_state.json`; lifetime log
`data/disposition_tracking_history.json` (same pattern as
`bb_followthrough_state.json` / `_history.json`).

```
ENTER  (ticker newly in disposition_current, not yet tracked)
  record: enter_date, disposition start/end, condition, count (1st/2nd/3rd),
          runup_5d_pct, runup_20d_pct (returns into enter_date),
          foreign_5d, foreign_20d, trust_5d, trust_20d at entry
DURING (disposition period, ticker still in disposition_current)
  daily snapshot: close, cumret_since_enter_pct, foreign_1d, trust_1d
  (⚠ volume distorted by 分盤 — flag, do not use vol signals here)
RELEASE (ticker was tracked, no longer in disposition_current, or end date passed)
  mark release_date; snapshot T+0 (release day)
POST   (T+1 … T+20 after release)
  record ret_t1_pct, ret_t5_pct, ret_t20_pct + flow at each checkpoint
GRADUATE at T+20 → append full lifecycle to history, drop from state
```

Idempotency: a same-day re-run (watchdog kickstart) must not double-count a
snapshot or re-enter an already-tracked ticker — mirror the guards in
`bb_followthrough_track.append_history` / `update_consolidation_state`
(referenced by `tests/test_bb_idempotency.py`).

---

## Output — new inbox digest (topic `disposition-track`)

Pushed in the same 08:35 run (separate from the existing `disposition-alert`
message). Sections:

- **🆕 今日新進處置** — with runup_5d/20d + entry flow + disposition count.
- **🔓 今日/明日解除** — the tradeable events (thesis B watch-list).
- **📊 解除後表現** — recently released names' T+1/T+5/T+20 so far.
- **📈 累積條件統計** — once `history` has enough samples (≥ a small threshold,
  e.g. 10): grouped win-rate & median T+5/T+20 by (1st vs 2nd+ disposition) and
  (entry 法人 net positive vs negative). Below threshold: show
  "樣本累積中 (n/10)". No directional recommendation until stats exist.

Fail-safe: DB/flow gaps → record what is available, mark missing fields None,
never crash; a snapshot gap for one ticker does not abort the run.

---

## Testing

Extend/add tests (offline; fixtures + fake DB rows, no network):

1. Entry recording — a new disposition ticker enters state with runup_5d/20d +
   flow + count populated from injected snapshots.
2. During-snapshot — cumret computed vs enter close; idempotent same-day re-run
   doesn't duplicate the day's snapshot.
3. Release detection — ticker leaving `disposition_current` (or past end date) →
   release_date set, POST tracking begins.
4. Graduation — at T+20 the lifecycle moves to history with ret_t1/t5/t20.
5. `compute_conditional_stats(history)` — grouping + win-rate/median math;
   below-threshold → "樣本累積中"; correct group assignment (1st vs 2nd,
   flow-positive vs negative).
6. Digest rendering — new sections present; distinct from the existing
   `disposition-alert` message.

---

## Out of Scope

- Directional alerts (short/long recommendations) — deferred until the neutral
  tracker has accumulated enough samples to justify a thesis.
- Any change to the existing `disposition-alert` portfolio-cross-ref message.
- Intraday / same-day-close tracking (pre-market run uses prior close by design).
