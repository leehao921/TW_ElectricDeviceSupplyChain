"""Idempotency guards so routine_watchdog can safely re-run a partially-completed
BB job on the same trading day without corrupting state.

- bb_inbox_alert.update_consolidation_state: a second call for the SAME as_of must
  NOT re-increment consecutive_days (else a crash-then-rerun double counts).
- bb_followthrough_track.append_history: a second graduation of the same
  (ticker, graduated_on) must REPLACE, not duplicate, the history entry.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bb_inbox_alert as bia  # noqa: E402
import bb_followthrough_track as bft  # noqa: E402


# ------------------------------------------------------------------ #
# bb_inbox_alert.update_consolidation_state — same-day re-run is a no-op
# ------------------------------------------------------------------ #
def test_consolidation_same_day_rerun_does_not_reincrement(tmp_path):
    sp = tmp_path / "bb_consolidation_state.json"
    d1 = date(2026, 7, 6)
    d2 = date(2026, 7, 7)
    tickers = {"2330": "buy", "2454": "watch"}

    # Day 1: first sighting → consecutive_days == 1
    s1 = bia.update_consolidation_state(state_path=sp, as_of=d1, today_tickers=tickers)
    assert s1["squeeze_days"]["2330"]["consecutive_days"] == 1

    # Day 2 (real next trading day) → increments to 2
    s2 = bia.update_consolidation_state(state_path=sp, as_of=d2, today_tickers=tickers)
    assert s2["squeeze_days"]["2330"]["consecutive_days"] == 2

    # Day 2 AGAIN (watchdog re-run same day) → must stay 2, not 3
    s2b = bia.update_consolidation_state(state_path=sp, as_of=d2, today_tickers=tickers)
    assert s2b["squeeze_days"]["2330"]["consecutive_days"] == 2
    assert s2b["squeeze_days"]["2454"]["consecutive_days"] == 2
    # state on disk also unchanged
    on_disk = json.loads(sp.read_text())
    assert on_disk["squeeze_days"]["2330"]["consecutive_days"] == 2


def test_consolidation_advances_normally_across_distinct_days(tmp_path):
    sp = tmp_path / "s.json"
    tickers = {"1101": "buy"}
    for i, d in enumerate([date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8)], start=1):
        st = bia.update_consolidation_state(state_path=sp, as_of=d, today_tickers=tickers)
        assert st["squeeze_days"]["1101"]["consecutive_days"] == i


# ------------------------------------------------------------------ #
# bb_followthrough_track.append_history — dedupe by (ticker, graduated_on)
# ------------------------------------------------------------------ #
def _entry(ticker: str, on: str, **kw) -> dict:
    e = {"ticker": ticker, "graduated_on": on, "final_status": "波段"}
    e.update(kw)
    return e


def test_append_history_replaces_same_ticker_same_day(tmp_path):
    hp = tmp_path / "hist.json"
    bft.append_history(_entry("3055", "2026-07-08", cumret_pct=14.6), hp)
    # watchdog re-run graduates the same ticker on the same day again
    bft.append_history(_entry("3055", "2026-07-08", cumret_pct=15.1), hp)

    hist = json.loads(hp.read_text())
    same = [h for h in hist if h["ticker"] == "3055" and h["graduated_on"] == "2026-07-08"]
    assert len(same) == 1, "same (ticker, day) must not duplicate"
    assert same[0]["cumret_pct"] == 15.1, "re-run should replace with latest values"


def test_append_history_keeps_distinct_days_and_tickers(tmp_path):
    hp = tmp_path / "hist.json"
    bft.append_history(_entry("3055", "2026-07-08"), hp)
    bft.append_history(_entry("3055", "2026-07-15"), hp)   # same ticker, later graduation
    bft.append_history(_entry("8109", "2026-07-08"), hp)   # different ticker same day
    hist = json.loads(hp.read_text())
    assert len(hist) == 3
