from __future__ import annotations
import sys, json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import disposition_daily_fetch as dt  # noqa: E402


def test_count_to_n():
    assert dt.count_to_n("第一次處置") == 1
    assert dt.count_to_n("第二次處置") == 2
    assert dt.count_to_n("第三次處置") == 3
    assert dt.count_to_n("連續三次") == 1     # condition text, not a count → default 1
    assert dt.count_to_n(None) == 1


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
