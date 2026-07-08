# Plan — Routine Watchdog: self-heal missed daily launchd routines

## Context

On 2026-07-07 the machine restarted ~18:27 (Asia/Taipei). Two post-market routines never
completed that day: `bb-squeeze` (14:30) started but hung mid-scan and never pushed to
`claude:inbox`; `bb-followthrough` (15:30) never ran at all. launchd `StartCalendarInterval`
jobs do **not** catch up a run missed while the Mac is asleep/off, so the user had to notice
the gap and re-run both by hand the next day.

**Goal:** a dedicated watchdog that detects any of the 6 TW daily routines failing to run on a
trading day and, **within a same-day usefulness window, auto-reruns it** (pushing the real
result to inbox); **past that window, alerts instead** of pushing stale data. This removes the
manual babysitting. Decisions confirmed with user: *hybrid heal · dedicated watchdog agent ·
cover all 6 routines*.

**Design principle — reuse, don't rebuild** (per user's no-duplicate-infra rule):
- Detection reuses the existing `claude:inbox` stream (every routine already pushes a `topic`;
  Redis stream IDs are timestamped) → **no edits to the 6 scripts for detection**.
- Re-invocation reuses **`launchctl kickstart -k`** (the exact pattern in
  `nautilus-shioaji/scripts/system_watchdog.py::kickstart_daemon`) so launchd supplies each
  job's identical env / working dir / args — the watchdog never duplicates command lines.
- Trading-day gate reuses `trading_days(conn, as_of, window)` in
  `scripts/smart_money_analysis.py:64`.
- Scheduling reuses the machine's standard `RunAtLoad=true + StartInterval` polling-agent
  pattern (same as `system-watchdog` 180s, `agent-thresholds` 1800s).

---

## Components

| Kind | Path | Purpose |
|---|---|---|
| NEW | `scripts/routine_watchdog.py` | Poll inbox, decide per-job action, kickstart or alert |
| NEW | `~/Library/LaunchAgents/com.lulala.routine-watchdog.plist` | RunAtLoad + StartInterval 1800s |
| NEW | `data/tw_market_holidays.txt` | Weekday-holiday skip list (one ISO date/line), seeded 2026 |
| NEW | `tests/test_routine_watchdog.py` | TDD unit tests (fakeredis + frozen clock) |
| EDIT | `scripts/bb_inbox_alert.py` | Make `consecutive_days` update idempotent per day (safe re-run) |
| EDIT | `scripts/bb_followthrough_track.py` | Dedupe history append by date (safe re-run) |

Reused as-is (imported, not modified): `scripts/inbox_view.py::parse_id_ts`,
`scripts/smart_money_analysis.py::trading_days`.

---

## Job registry (in `routine_watchdog.py`)

Each entry: `topic`, launchd `label`(s), scheduled `HH:MM`, `kind`, `auto_rerun_until`.

| topic | launchd label(s) | sched | kind | auto-rerun window | past window |
|---|---|---|---|---|---|
| `disposition-alert` | `disposition-daily` | 08:35 | premarket (static list) | until 13:30 | alert |
| `buy-list` | `buy-list-daily` | 08:50 | premarket | until 13:30 | alert |
| `ma-touch` | `ma-touch-preopen/noon/close` | 09:30/12:00/13:20 | intraday | only while now ≤ 13:35, per-slot | skip (session over) |
| `bb-squeeze` | `bb-squeeze` | 14:30 | EOD | until 23:59 same day | alert |
| `bb-followthrough` | `bb-followthrough` | 15:30 | EOD | until 23:59 same day | alert |
| `etf-smart-money` | `etf-smart-money` | 19:30 | EOD | until 23:59 same day | alert |

- **EOD jobs are the ones that actually failed** — an evening reboot (like 18:27) fires the
  watchdog via `RunAtLoad`, which finds no `bb-squeeze`/`bb-followthrough` fire today and, being
  well inside the EOD window, kickstarts both. This directly fixes the 7/7 scenario.
- **ma-touch** shares one topic across 3 slots; detect per-slot by the `(preopen|noon|close)`
  token already present in each ma-touch inbox message, and kickstart only the specific missing
  slot's label while the session is still open.

---

## Core logic (pure + testable)

**Detection** `fired_today(topic, since_hhmm, now) -> bool`:
query `XREVRANGE claude:inbox + - COUNT 300`, keep entries whose `topic` field matches and whose
stream-ID timestamp (via reused `parse_id_ts`) is on `now`'s date at/after `since_hhmm`.

**Trading-day gate** `is_trading_day(now, holidays) -> bool`: Mon–Fri **and** date not in
`data/tw_market_holidays.txt`. For EOD jobs additionally confirm today ∈ `trading_days(conn,
today, 3)` once DB has post-market data (belt-and-suspenders against unlisted holidays);
premarket jobs can't use the DB (today's rows not loaded yet) so rely on weekday+holiday file.

**Decision** `decide(job, now, fired, in_window, last_kick) -> "NONE"|"KICKSTART"|"ALERT"`:
```
if fired:                      NONE
elif not is_trading_day:       NONE
elif now < sched+grace(2min):  NONE            # not due yet
elif in_window and cooldown_ok(last_kick): KICKSTART
elif in_window:                NONE            # kicked recently, wait for inbox
else:                          ALERT           # past window → stale, notify only
```
- `KICKSTART` → `launchctl kickstart -k gui/<uid>/com.lulala.<label>`; record timestamp in
  `data/routine_watchdog_state.json` (per-job 30-min cooldown, mirrors stock-ofi watchdog).
- `ALERT` → push one `claude:inbox` message `topic="routine-watchdog"` naming the missed job,
  at most once/day/job (tracked in the same state file).

**Idempotency edits** (so an auto-rerun after a partial/crashed first run can't corrupt state):
- `bb_inbox_alert.py`: before incrementing `consecutive_days`, skip if that date is already the
  last recorded day (make the counter update a no-op on same-day re-run).
- `bb_followthrough_track.py`: in `append_history`, replace an existing entry for today's date
  instead of unconditionally appending a duplicate.

---

## launchd plist (`com.lulala.routine-watchdog`)

Mirror `com.lulala.system-watchdog.plist`: `ProgramArguments = [.venv/bin/python,
scripts/routine_watchdog.py]`, `RunAtLoad=true`, `StartInterval=1800`,
`EnvironmentVariables={PATH, TZ=Asia/Taipei, REDIS_HOST=localhost, REDIS_PORT=6379,
TMF_PG_PASSWORD=tmf_dev_2026}`, `WorkingDirectory=<repo>`, logs →
`~/Library/Logs/routine-watchdog.log`. Off-hours/holiday polls short-circuit fast via the gates.

---

## Testing (TDD — write tests first)

`tests/test_routine_watchdog.py`, using `fakeredis` + an injected `now`:
- `decide()` truth table: fired→NONE; not-due→NONE; in-window+no-cooldown→KICKSTART;
  in-window+recent-kick→NONE; past-window→ALERT; weekend/holiday→NONE.
- `fired_today()`: seed fake inbox with a `bb-squeeze` entry stamped today→True; only yesterday→
  False; today-but-before-sched→False.
- `is_trading_day()`: Sat/Sun→False; seeded holiday date→False; normal weekday→True.
- ma-touch per-slot: only `noon` fire present → `preopen` counts fired, `close` not-yet-due.
- Idempotency: call `bb_followthrough_track.append_history` twice for same date → one entry;
  `bb_inbox_alert` consecutive_days update twice same day → counter unchanged.

Run: `.venv/bin/pytest tests/test_routine_watchdog.py -v`.

---

## Verification (end-to-end)

1. `.venv/bin/python scripts/routine_watchdog.py --dry-run` on a normal trading evening →
   reports all 6 as fired/NONE, no kickstart.
2. Simulate a miss: `--dry-run --pretend-missed bb-squeeze` → prints `KICKSTART
   com.lulala.bb-squeeze` (dry-run doesn't actually kickstart).
3. Real heal test: `launchctl unload` bb-squeeze isn't needed — instead delete today's
   bb-squeeze inbox entry in a scratch test, run watchdog (non-dry) inside the EOD window,
   confirm it `launchctl kickstart`s and a fresh `bb-squeeze` fire appears in inbox within ~a few min.
4. `launchctl load ~/Library/LaunchAgents/com.lulala.routine-watchdog.plist`; confirm
   `launchctl list | grep routine-watchdog` shows it loaded and it logs a clean poll.

---

## Out of scope
- Fixing *why* `bb-squeeze` hung mid-scan (yfinance rate-limit robustness) — separate issue;
  the watchdog re-runs it regardless.
- A real TWSE/TPEx holiday API — the seeded `tw_market_holidays.txt` is enough; refine later.
- Cross-midnight EOD catch-up with `--as-of yesterday` — deferred; evening-reboot case (the real
  one) is covered by the same-day window.
