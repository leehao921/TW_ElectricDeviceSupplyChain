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
