# Valuation Anomaly Detection — Plan

**Date:** 2026-05-23
**Branch:** `feat/valuation-anomaly`
**Author:** Claude (auto-mode session)

---

## Motivation

`scripts/update_valuation.py` runs daily at 16:35 weekdays via cron and refreshes the
估值指標 section of all 926 ticker reports. Currently the script writes the new
values directly into each `Pilot_Reports/**/*.md` file with **no record of the
previous day's values** — so abnormal jumps (limit-up/down moves, suspended
trading, splits, capital increases) leave no trail and never alert the operator.

This feature adds:

1. **Daily snapshot persistence** — every valuation refresh writes a
   machine-readable snapshot under `data/valuation_snapshots/YYYY-MM-DD.json`.
2. **Anomaly detection script** — compares today's snapshot to the most recent
   prior snapshot and flags rule violations (see rules below).
3. **Inbox notification** — HIGH-severity anomalies are pushed to the existing
   `claude:inbox` Redis stream so the next session boot surfaces them.
4. **CI coverage** — pytest workflow runs on every push / PR.

## Non-goals

- No back-testing (we only persist forward-going snapshots from today onward).
- No web dashboard. CLI text + JSON output + inbox messages only.
- No automatic remediation. Anomalies are surfaced; the operator decides what
  to do (re-pull data, investigate corporate action, etc.).

## Rules

| ID | Trigger | Severity |
|----|---------|----------|
| **R1** | `\|ΔPrice%\| > 7%` (TW daily limit boundary) | HIGH |
| **R2** | `\|ΔP/E%\| > 20%` **AND** `\|absolute ΔP/E\| > 3` | MEDIUM |
| **R3** | `\|ΔP/B%\| > 25%` **AND** `\|absolute ΔP/B\| > 0.5` | MEDIUM |
| **R4** | `\|ΔMktCap%\| > 10%` **AND** divergence from ΔPrice% > 5pp (capital action) — *only fires for yfinance-sourced rows (~60 tickers/week); TWSE/TPEX bulk feeds omit market cap* | HIGH |
| **R5** | yesterday had price/pe/pb but today is None / missing (suspension / delisting) | HIGH |
| **R6** | yesterday `yield_pct > 0` and today `yield_pct == 0` (除息日) | INFO |

All rules operate only on tickers present in **both** snapshots. New listings
and graduations are silently ignored.

## Architecture

```
┌────────────────────────────┐  16:35 cron, Mon–Fri
│ update_valuation.py        │ ──┐
│  (modified to also write   │   │
│   snapshot JSON)           │   ▼
└────────────────────────────┘  data/valuation_snapshots/YYYY-MM-DD.json
                                    │
                                    ▼
┌────────────────────────────┐
│ detect_valuation_anomaly.py│ → stdout text or --json
│  (new)                     │ → --notify-inbox: claude:inbox stream
└────────────────────────────┘
```

## File layout

| Path | Status | Purpose |
|------|--------|---------|
| `scripts/update_valuation.py` | modified | Add snapshot writer (~30 LOC) |
| `scripts/detect_valuation_anomaly.py` | NEW | Rule engine + inbox push |
| `scripts/valuation_snapshot.py` | NEW | Shared snapshot load/save helpers |
| `data/valuation_snapshots/YYYY-MM-DD.json` | NEW (data) | Daily snapshots |
| `data/valuation_snapshots/.gitkeep` | NEW | Ensure dir exists in git |
| `tests/__init__.py` | NEW | Test package init |
| `tests/test_valuation_anomaly.py` | NEW | TDD coverage for all 6 rules + snapshot IO |
| `.github/workflows/valuation-anomaly-tests.yml` | NEW | CI pytest job |
| `crontab` (operator-owned) | modified | Chain anomaly detection after refresh; add weekly fallback |

## Snapshot format

```json
{
  "snapshot_date": "2026-05-23",
  "generated_at_utc": "2026-05-23T08:35:12Z",
  "source_summary": {"TWSE": 950, "TPEX": 800, "yfinance": 13},
  "tickers": {
    "2330": {
      "price": 1175.0,
      "pe": 26.4,
      "pb": 6.1,
      "yield_pct": 1.4,
      "market_cap_m": 30482500,
      "source": "TWSE"
    },
    ...
  }
}
```

All numeric fields are floats or `null`. No string formatting (defer that to
report renderers). Snapshot is committed to git so the comparison baseline is
versioned. (Each snapshot is ~150 KB, ~50 MB/year — acceptable for git LFS-free
storage.)

## Inbox message format

For each HIGH-severity rule violation:

```
python3 scripts/claude_msg.py send valuation_anomaly \
  "[R1] 2330 price jumped +9.8% (1175.0 -> 1290.0)" \
  --tags valuation anomaly R1 2330
```

MEDIUM and INFO are printed to stdout only. The operator can pipe them into
the log file (already done by the cron).

## Verification protocol

1. `pytest tests/test_valuation_anomaly.py -v` — must show all green.
2. Dry-run with synthetic two-day snapshots: assert each rule fires exactly
   when expected.
3. Live dry-run on today's real snapshot vs a manually constructed yesterday
   file with known deltas → eyeball results.
4. Commit + push branch, confirm CI workflow runs green on PR.

## Open questions

- **None at plan time.** R1-R6 thresholds + workflow shape approved by user
  in the prior turn ("ok").

## Rollback

If anomaly detection becomes noisy or causes false positives, the operator
can revert the cron chain to just `update_valuation.py` — the detector is
purely additive. Snapshot files keep accumulating regardless (no harm).
