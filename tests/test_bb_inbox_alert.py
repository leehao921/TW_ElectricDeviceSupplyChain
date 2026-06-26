"""Tests for scripts/bb_inbox_alert.py — daily BB squeeze + breakout inbox alerts.

Covers:
- build_inbox_message: compact summary format with/without hits
- update_consolidation_state: first-seen / consecutive increment / drop-off
- extract_persistent_squeeze: filter by min-day threshold
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bb_inbox_alert as alert  # noqa: E402


@pytest.fixture
def sample_buy_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": "3019.TW", "name": "亞光", "sector": "Electronic Components",
            "close": 245.5, "ret_today_pct": 3.21, "vol_ratio": 4.10,
            "bbw_today": 4.5, "bbw_avg7_prior": 6.0,
            "days_squeezed_of_7": 6,
            "foreign_5d_oku": 1.20, "trust_5d_oku": 0.30,
            "themes": ["矽光子", "光通訊"],
        },
        {
            "ticker": "2425.TW", "name": "承啟", "sector": "Computer Hardware",
            "close": 88.3, "ret_today_pct": 2.10, "vol_ratio": 2.50,
            "bbw_today": 5.0, "bbw_avg7_prior": 6.5,
            "days_squeezed_of_7": 5,
            "foreign_5d_oku": 0.40, "trust_5d_oku": 0.05,
            "themes": [],
        },
    ])


@pytest.fixture
def sample_avoid_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": "6784.TW", "name": "鋐昇", "sector": "Electronic Components",
            "close": 38.5, "ret_today_pct": -8.4, "vol_ratio": 3.20,
            "bbw_today": 8.0, "bbw_avg7_prior": 5.5,
            "days_squeezed_of_7": 4,
            "foreign_5d_oku": -0.20, "trust_5d_oku": 0.0,
            "themes": [],
            "avoid_reason": "盤整向下突破 (Bollinger 下緣 + 量增)",
        },
    ])


# ------------------------------------------------------------------ #
# build_inbox_message
# ------------------------------------------------------------------ #
def test_build_inbox_message_with_buy_hits(sample_buy_df, sample_avoid_df):
    msg = alert.build_inbox_message(
        as_of=date(2026, 6, 26),
        buy_df=sample_buy_df,
        avoid_df=sample_avoid_df,
        watch_labels=["7 仁寶", "6188 廣明"],
        persistent=[],
        universe_size=900,
    )
    assert "BB Squeeze 巡檢 2026-06-26" in msg
    assert "2 Buy" in msg and "1 Avoid" in msg and "2 Watch" in msg
    assert "3019" in msg and "亞光" in msg
    assert "2425" in msg
    assert "6784" in msg
    assert "+3.21%" in msg or "+3.2%" in msg
    assert "scripts/smart_money_analysis.py" in msg


def test_build_inbox_message_empty_scan():
    empty = pd.DataFrame()
    msg = alert.build_inbox_message(
        as_of=date(2026, 6, 26),
        buy_df=empty,
        avoid_df=empty,
        watch_labels=[],
        persistent=[],
        universe_size=900,
    )
    assert "0 Buy" in msg
    assert "0 Avoid" in msg
    assert "0 Watch" in msg


def test_build_inbox_message_includes_persistent_squeeze():
    empty = pd.DataFrame()
    persistent = [
        {"ticker": "4942.TW", "name": "嘉彰", "consecutive_days": 7, "last_status": "watch"},
        {"ticker": "2425.TW", "name": "承啟", "consecutive_days": 5, "last_status": "buy"},
    ]
    msg = alert.build_inbox_message(
        as_of=date(2026, 6, 26),
        buy_df=empty,
        avoid_df=empty,
        watch_labels=[],
        persistent=persistent,
        universe_size=900,
    )
    assert "持續盤整" in msg
    assert "4942" in msg and "7d" in msg
    assert "2425" in msg and "5d" in msg


# ------------------------------------------------------------------ #
# update_consolidation_state
# ------------------------------------------------------------------ #
def test_update_state_first_time_seen(tmp_path):
    state_path = tmp_path / "state.json"
    today = date(2026, 6, 26)
    new_state = alert.update_consolidation_state(
        state_path=state_path,
        as_of=today,
        today_tickers={"3019.TW": "buy", "7.TW": "watch"},
    )
    assert new_state["as_of"] == "2026-06-26"
    assert new_state["squeeze_days"]["3019.TW"]["consecutive_days"] == 1
    assert new_state["squeeze_days"]["3019.TW"]["first_seen"] == "2026-06-26"
    assert new_state["squeeze_days"]["3019.TW"]["last_status"] == "buy"
    assert new_state["squeeze_days"]["7.TW"]["last_status"] == "watch"
    # file written
    assert state_path.exists()
    loaded = json.loads(state_path.read_text())
    assert loaded == new_state


def test_update_state_consecutive_increment(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "as_of": "2026-06-25",
        "squeeze_days": {
            "3019.TW": {"first_seen": "2026-06-22", "consecutive_days": 3, "last_status": "watch"},
        },
    }))
    new_state = alert.update_consolidation_state(
        state_path=state_path,
        as_of=date(2026, 6, 26),
        today_tickers={"3019.TW": "buy"},
    )
    assert new_state["squeeze_days"]["3019.TW"]["consecutive_days"] == 4
    assert new_state["squeeze_days"]["3019.TW"]["first_seen"] == "2026-06-22"
    assert new_state["squeeze_days"]["3019.TW"]["last_status"] == "buy"


def test_update_state_drops_off_when_absent(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "as_of": "2026-06-25",
        "squeeze_days": {
            "3019.TW": {"first_seen": "2026-06-22", "consecutive_days": 3, "last_status": "watch"},
            "6784.TW": {"first_seen": "2026-06-24", "consecutive_days": 1, "last_status": "watch"},
        },
    }))
    new_state = alert.update_consolidation_state(
        state_path=state_path,
        as_of=date(2026, 6, 26),
        today_tickers={"3019.TW": "buy"},  # 6784 dropped off
    )
    assert "3019.TW" in new_state["squeeze_days"]
    assert "6784.TW" not in new_state["squeeze_days"]


def test_update_state_handles_missing_file(tmp_path):
    state_path = tmp_path / "does_not_exist.json"
    new_state = alert.update_consolidation_state(
        state_path=state_path,
        as_of=date(2026, 6, 26),
        today_tickers={"3019.TW": "buy"},
    )
    assert new_state["squeeze_days"]["3019.TW"]["consecutive_days"] == 1


# ------------------------------------------------------------------ #
# extract_persistent_squeeze
# ------------------------------------------------------------------ #
def test_extract_persistent_squeeze_filters_by_threshold():
    state = {
        "as_of": "2026-06-26",
        "squeeze_days": {
            "3019.TW": {"first_seen": "2026-06-22", "consecutive_days": 5, "last_status": "buy"},
            "2425.TW": {"first_seen": "2026-06-19", "consecutive_days": 8, "last_status": "watch"},
            "6784.TW": {"first_seen": "2026-06-25", "consecutive_days": 2, "last_status": "watch"},
        },
    }
    name_map = {"3019.TW": "亞光", "2425.TW": "承啟", "6784.TW": "鋐昇"}
    persistent = alert.extract_persistent_squeeze(state, name_map=name_map, min_days=5)
    tickers = [p["ticker"] for p in persistent]
    assert "3019.TW" in tickers
    assert "2425.TW" in tickers
    assert "6784.TW" not in tickers
    # sorted by consecutive_days desc
    assert persistent[0]["ticker"] == "2425.TW"
    assert persistent[0]["consecutive_days"] == 8
    assert persistent[0]["name"] == "承啟"


def test_extract_persistent_squeeze_empty_when_none_qualify():
    state = {
        "as_of": "2026-06-26",
        "squeeze_days": {
            "3019.TW": {"first_seen": "2026-06-25", "consecutive_days": 1, "last_status": "buy"},
        },
    }
    persistent = alert.extract_persistent_squeeze(state, name_map={}, min_days=5)
    assert persistent == []
