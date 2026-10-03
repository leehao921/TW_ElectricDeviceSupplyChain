"""bb_followthrough 葛蘭碧 B3/B2 觀察標籤 (2026-10-03, analysis/bb_granville_verify_2026-10-03.md)"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import bb_followthrough_track as bft  # noqa: E402


def _rising(n=30, start=100.0, step=1.0):
    return [start + i * step for i in range(n)]


def test_b3_steady_above_rising_ma():
    assert bft.granville_tag(_rising()) == "B3"


def test_b2_recent_close_below_rising_ma():
    c = _rising()
    c[-3] = c[-3] - 20          # 前 5 日內一天收破 MA20, 今日站回
    assert bft.granville_tag(c) == "B2"


def test_dip_older_than_5_days_is_still_b3():
    c = _rising()
    c[-8] = c[-8] - 20          # 6 日以前的跌破不算
    assert bft.granville_tag(c) == "B3"


def test_s2_breakout_above_falling_ma():
    c = [200.0 - i * 2 for i in range(29)] + [200.0]   # 均線下彎, 今日暴漲站上
    assert bft.granville_tag(c) == "S2"


def test_below_ma():
    c = [200.0 - i for i in range(30)]
    assert bft.granville_tag(c) == "below"


def test_insufficient_data_returns_none():
    assert bft.granville_tag(_rising(n=20)) is None


GV_LABEL_KEYS = {"B3", "B2", "S2", "below"}


def test_labels_cover_all_tags_and_say_observation():
    assert set(bft.GRANVILLE_LABEL) == GV_LABEL_KEYS
    assert "觀察" in bft.GRANVILLE_LABEL["B3"]


def _entry(**kw):
    e = {"name": "測試", "first_seen": "2026-10-02", "days_tracked": 0, "status": "just_added",
         "daily_snapshots": [{"d": "2026-10-02", "close": 100.0, "vol_ratio": 2.0,
                              "foreign_1d": 0.5, "cumret_pct": 0.0}],
         "foreign_5d_at_entry": 1.0, "rules_hit": [], "cumret_pct": 0.0}
    e.update(kw)
    return e


def test_digest_shows_granville_label():
    state = {"tracked": {"2330": _entry(granville="B3")}}
    out = bft.build_digest(state, "2026-10-02", ["2330"], [], history=[])
    assert bft.GRANVILLE_LABEL["B3"] in out


def test_digest_without_granville_field_still_renders():
    state = {"tracked": {"2330": _entry()}}
    out = bft.build_digest(state, "2026-10-02", ["2330"], [], history=[])
    assert "2330" in out


def test_granville_not_in_rules_hit():
    e = _entry(granville="B3", vol_ratio_at_entry=3.0, foreign_5d_at_entry=1.0,
               foreign_20d_at_entry=0.0, themes=[])
    assert not any("B3" in t or "葛蘭碧" in t for t in bft.apply_rules(e))


def test_graduate_writes_granville_to_history(tmp_path, monkeypatch):
    hist = tmp_path / "h.json"
    monkeypatch.setattr(bft, "HISTORY_PATH", hist)
    e = _entry(granville="B2", days_tracked=bft.GRADUATE_DAYS, status="watch")
    state = {"tracked": {"2330": e}}
    bft.graduate_stale(state, "2026-10-09")
    import json
    rec = json.loads(hist.read_text(encoding="utf-8"))[-1]
    assert rec["granville"] == "B2"
