# Plan — BB Squeeze + Breakout daily inbox alerts

## Background

`scripts/smart_money_analysis.py` already runs a Bollinger-Band squeeze + volume-breakout scanner (Section 8, commits 1cff8bf + 96e5ae9). It classifies hits into 🟢 Buy / 🔴 Avoid / 🟡 Watch, and writes a daily Markdown report to `analysis/smart_money_YYYY-MM-DD.md`. DB-backed mode runs in ~5s.

**Gap:** the scanner only runs when I (Claude) am invoked. No standing schedule, no persistent tracking of "consolidating" universe across days. User has to manually run it.

**Goal:** daily cron pushes a compact alert to `claude:inbox` Redis stream so the next session boot (via `vault_session_boot.py`) surfaces hits + persistent squeeze candidates.

## Files

- `scripts/smart_money_analysis.py` — add headless helper `run_bb_scan_headless(as_of, conn, source) -> ScanResult` (extract scan slice from main, no refactor of main itself)
- `scripts/bb_inbox_alert.py` — new wrapper (~120 LOC)
- `tests/test_bb_inbox_alert.py` — pure-function tests
- `data/bb_consolidation_state.json` — gitignored, tracks consecutive-day squeeze counts
- `.gitignore` — add the state file pattern

## Design

### `run_bb_scan_headless()` (in smart_money_analysis.py)
Encapsulates the BB-scan slice from `main()`. Returns dataclass:
```python
@dataclass
class BBScanResult:
    as_of: dtdate
    universe_size: int
    buy_df: pd.DataFrame
    avoid_df: pd.DataFrame
    watch_labels: list[str]
```

### `bb_inbox_alert.py`
1. Call `run_bb_scan_headless(as_of)` → ScanResult
2. Update `data/bb_consolidation_state.json`:
   - For each ticker in today's `watch_labels + buy_df + avoid_df`, increment consecutive-day counter
   - Drop tickers not in any list (reset)
   - Surface tickers with `consecutive_days >= 5` as "已盤整 N+ 天" persistent candidates
3. `build_inbox_message(scan, persistent_squeeze, as_of) -> str` — compact summary
4. `push_to_inbox(msg, tags)` — XADD `claude:inbox` via redis-cli (no extra dep, plain subprocess)
5. CLI: `--as-of YYYY-MM-DD` (default: today), `--dry-run` (print only, skip XADD), `--state-path`

### State file schema
```json
{
  "as_of": "2026-06-26",
  "squeeze_days": {
    "2425.TW": {"first_seen": "2026-06-22", "consecutive_days": 5, "last_status": "watch"},
    "3019.TW": {"first_seen": "2026-06-26", "consecutive_days": 1, "last_status": "buy"}
  }
}
```

### Inbox message format (Markdown, ≤ 1500 chars)
```
**BB Squeeze 巡檢 2026-06-26** (N Buy / M Avoid / K Watch / J 持續盤整≥5d)

🟢 Buy: 2425 承啟 (+3.2%, vol×4.1, 5D 外資 +1.2億)
       3019 亞光 (...)
🔴 Avoid: 6784 (向下突破, -8.4%) / 3664 (...)
🟡 Watch (新): 7 / 6188 / 8093
⏳ 持續盤整≥5d: 2425 (6d, watch), 4942 (5d, watch)

源: scripts/smart_money_analysis.py · 詳見 analysis/smart_money_2026-06-26.md
```

## TDD steps

1. Write `tests/test_bb_inbox_alert.py` — RED:
   - `test_build_inbox_message_with_buy_hits`
   - `test_build_inbox_message_empty_scan`
   - `test_update_state_first_time_seen`
   - `test_update_state_consecutive_increment`
   - `test_update_state_drops_off_when_absent`
   - `test_extract_persistent_squeeze_filters_by_threshold`
2. Add `run_bb_scan_headless` to smart_money_analysis.py — GREEN
3. Implement `scripts/bb_inbox_alert.py` — GREEN
4. Verify all tests pass

## Verify

- `python scripts/bb_inbox_alert.py --dry-run` — no XADD, prints what would be sent + state diff
- `redis-cli XLEN claude:inbox` before/after live run — confirms +1 entry
- `redis-cli XREVRANGE claude:inbox + - COUNT 1` — confirms payload format

## Schedule

- `/schedule` daily 14:30 Asia/Taipei (15 min after market close → time for `stock_daily_ohlcv` collector to land same-day bar)
- Command: `cd /Users/lulala/Documents/coding/My-TW-Coverage && python3 scripts/bb_inbox_alert.py`

## Out of scope

- Re-architecting smart_money_analysis.py main() to use the new helper (kept inline, will refactor later if needed)
- Integrating with memory-cycle-monitor (separate dashboard, separate Redis hash)
- Web/UI surface — inbox-only for now
