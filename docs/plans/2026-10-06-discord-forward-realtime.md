# Discord forwarder: realtime daemon, topic routing, observability, chunk resume

Date: 2026-10-06
Files: `scripts/discord_forward.py`, `tests/test_discord_forward.py`,
`scripts/routine_watchdog.py`, `tests/test_routine_watchdog.py`,
`scripts/launchd/com.lulala.discord-forward.plist` (+ installed copy in ~/Library/LaunchAgents)

## Why

User diagnosis 2026-10-06:
1. Trading alerts (gex-regime, position-watch, trail_daemon) waited up to 300 s (StartInterval polling).
2. Every topic lands in one Discord channel.
3. The 10-03 network outage produced ~908 untimestamped error lines and nobody was alerted;
   the forwarder is not covered by routine-watchdog.
4. A multi-chunk entry that fails mid-way is resent from chunk 1.

## Design

1. **`--daemon` mode** — resident loop: `XREAD BLOCK 5000` from cursor `discord:forward:last_id`,
   forward immediately. Keeps POST_SLEEP, the 429 retry_after backoff, and a sliding per-minute
   message budget (25 msgs / 60 s, `RateLimiter`). Cursor still advances only after an entry is
   fully delivered (at-least-once). One-shot path (`run_once`) unchanged in behaviour.
   launchd: `KeepAlive` + `RunAtLoad`, no `StartInterval`. Reload via `launchctl bootout` +
   `launchctl bootstrap` (never `kickstart -k`).
2. **Routing** — pure `route_topic(fields) -> "trading" | "reports" | "system"`.
   Precedence: trading topic set/prefix → `report_path` present or report topic set → system.
   Webhooks: `DISCORD_WEBHOOK_URL_{TRADING,REPORTS,SYSTEM}` (env, then `../database/.env`),
   each falling back to `DISCORD_WEBHOOK_URL`. No URLs are written by this change.
3. **Observability** — `logging` with timestamps; `ForwardHealth` tracks fail streak; every
   loop writes hash `discord:forward:health` {status, fail_streak, last_ok_ts, last_err,
   last_err_ts, heartbeat_ts}. Streak ≥ 3 or failing > 5 min → ONE macOS notification
   (`osascript`, never Discord) per streak; cleared on recovery. Errors back off
   exponentially (5 s → 60 s cap) and never kill the daemon.
   `routine_watchdog.py` gains `check_forwarder`: heartbeat missing/older than 10 min →
   osascript notification (once per stale heartbeat value), runs every poll regardless of
   trading day.
4. **Chunk resume** — `discord:forward:partial = "<entry_id>:<chunks_sent>"` written after each
   successful chunk; a retry of the same entry skips the sent chunks; deleted when the entry
   completes (after the cursor moves).

## Test plan (TDD)

Fake Redis + fake post function: route_topic table, URL resolution fallback, partial resume,
partial cleared, stale partial ignored, daemon iteration forwards via XREAD and survives
Redis/post errors with cursor kept, health hash fields, single notification per streak,
recovery resets, rate limiter, watchdog stale/fresh/once-per-episode.

## Deploy / verify

Run `pytest tests/test_discord_forward.py tests/test_routine_watchdog.py`, swap plist, bootout +
bootstrap, confirm PID via `launchctl print`, timestamped log lines, health hash, and the cursor
advancing past a real inbox entry. No `--test` posts.
