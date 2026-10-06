"""Tests for scripts/routine_watchdog.py — self-heal missed daily launchd routines.

Pure-logic focus (injected clock + synthetic inbox entries); IO (launchctl, redis)
is exercised via fakeredis / dry-run at the main() level.
"""
from __future__ import annotations

import sys
from datetime import datetime, time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import routine_watchdog as rw  # noqa: E402


# ------------------------------------------------------------------ #
# is_trading_day
# ------------------------------------------------------------------ #
def test_is_trading_day_weekend_false():
    assert rw.is_trading_day(datetime(2026, 7, 11, 10, 0), holidays=set()) is False  # Sat
    assert rw.is_trading_day(datetime(2026, 7, 12, 10, 0), holidays=set()) is False  # Sun


def test_is_trading_day_holiday_false():
    hol = {"2026-07-08"}
    assert rw.is_trading_day(datetime(2026, 7, 8, 10, 0), holidays=hol) is False


def test_is_trading_day_normal_weekday_true():
    assert rw.is_trading_day(datetime(2026, 7, 8, 10, 0), holidays=set()) is True  # Wed


# ------------------------------------------------------------------ #
# registry / build_checks — ma-touch expands to 3 slots
# ------------------------------------------------------------------ #
def test_build_checks_expands_ma_touch_slots():
    checks = rw.build_checks()
    keys = {c.key for c in checks}
    # 21 registry topics, but ma-touch → 3 slot checks ⇒ 24 total
    assert len(checks) == 24
    assert {"ma-touch:preopen", "ma-touch:noon", "ma-touch:close"} <= keys
    assert {"bb-squeeze", "bb-followthrough", "etf-smart-money",
            "disposition-alert", "disposition-track", "buy-list", "pb-lights",
            "memory-cycle", "routine-synthesis", "news-pulse",
            "foreign-structure", "ddr-price", "geo-composite", "txf-levels"} <= keys
    labels = {c.key: c.label for c in checks}
    assert labels["ma-touch:preopen"] == "com.lulala.ma-touch-preopen"
    assert labels["pb-lights"] == "com.lulala.pb-lights"
    assert labels["memory-cycle"] == "com.lulala.memory-cycle"
    assert labels["bb-squeeze"] == "com.lulala.bb-squeeze"
    assert labels["routine-synthesis"] == "com.lulala.daily-synthesis"


def test_disposition_track_registered_same_label():
    checks = {c.key: c for c in rw.build_checks()}
    assert "disposition-track" in checks
    assert checks["disposition-track"].label == "com.lulala.disposition-daily"
    assert checks["disposition-track"].sched == time(8, 35)


# ------------------------------------------------------------------ #
# fired_today
# ------------------------------------------------------------------ #
def _entry(ms: int, topic: str, msg: str = ""):
    return (f"{ms}-0", {"topic": topic, "msg": msg})


def test_fired_today_true_when_entry_today_after_sched():
    now = datetime(2026, 7, 8, 16, 0)
    ms = int(datetime(2026, 7, 8, 14, 36).timestamp() * 1000)
    entries = [_entry(ms, "bb-squeeze")]
    assert rw.fired_today(entries, "bb-squeeze", time(14, 30), now) is True


def test_fired_today_false_when_only_yesterday():
    now = datetime(2026, 7, 8, 16, 0)
    ms = int(datetime(2026, 7, 7, 14, 36).timestamp() * 1000)
    entries = [_entry(ms, "bb-squeeze")]
    assert rw.fired_today(entries, "bb-squeeze", time(14, 30), now) is False


def test_fired_today_false_when_today_but_before_sched():
    # a stray same-topic entry earlier than the scheduled time doesn't count
    now = datetime(2026, 7, 8, 16, 0)
    ms = int(datetime(2026, 7, 8, 9, 0).timestamp() * 1000)
    entries = [_entry(ms, "bb-squeeze")]
    assert rw.fired_today(entries, "bb-squeeze", time(14, 30), now) is False


def test_fired_today_ma_touch_per_slot_via_msg_token():
    now = datetime(2026, 7, 8, 13, 0)
    ms = int(datetime(2026, 7, 8, 12, 1).timestamp() * 1000)
    entries = [_entry(ms, "ma-touch", "MA Touch 巡檢 ... (noon)")]
    # noon slot present
    assert rw.fired_today(entries, "ma-touch", time(12, 0), now, slot="noon") is True
    # preopen slot NOT present in inbox
    assert rw.fired_today(entries, "ma-touch", time(9, 30), now, slot="preopen") is False


# ------------------------------------------------------------------ #
# decide truth table
# ------------------------------------------------------------------ #
def _check(**kw):
    base = dict(topic="bb-squeeze", label="com.lulala.bb-squeeze", key="bb-squeeze",
                sched=time(14, 30), window_end=time(23, 59), slot=None)
    base.update(kw)
    return rw.Check(**base)


def test_decide_fired_is_none():
    now = datetime(2026, 7, 8, 16, 0)
    assert rw.decide(_check(), now, fired=True, last_kick=None) == "NONE"


def test_decide_not_yet_due_is_none():
    now = datetime(2026, 7, 8, 14, 31)  # within 2-min grace of 14:30
    assert rw.decide(_check(), now, fired=False, last_kick=None) == "NONE"


def test_decide_in_window_no_cooldown_kickstart():
    now = datetime(2026, 7, 8, 18, 27)  # evening reboot, well past sched, in window
    assert rw.decide(_check(), now, fired=False, last_kick=None) == "KICKSTART"


def test_decide_in_window_recent_kick_is_none():
    now = datetime(2026, 7, 8, 18, 27)
    recent = datetime(2026, 7, 8, 18, 10)  # 17 min ago < 30-min cooldown
    assert rw.decide(_check(), now, fired=False, last_kick=recent) == "NONE"


def test_decide_in_window_stale_kick_kickstart_again():
    now = datetime(2026, 7, 8, 19, 5)
    old = datetime(2026, 7, 8, 18, 27)  # 38 min ago > cooldown
    assert rw.decide(_check(), now, fired=False, last_kick=old) == "KICKSTART"


def test_decide_past_window_alerts():
    # premarket buy-list window ends 13:30; at 15:00 it's stale → alert
    now = datetime(2026, 7, 8, 15, 0)
    chk = _check(topic="buy-list", key="buy-list", label="com.lulala.buy-list-daily",
                 sched=time(8, 50), window_end=time(13, 30))
    assert rw.decide(chk, now, fired=False, last_kick=None) == "ALERT"


# ------------------------------------------------------------------ #
# main() dry-run wiring with fakeredis
# ------------------------------------------------------------------ #
def test_main_dry_run_pretend_missed_reports_kickstart(tmp_path, capsys, monkeypatch):
    import fakeredis
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    # seed all topics as fired today so only the pretend-missed one is actionable
    now = datetime(2026, 7, 8, 18, 30)
    monkeypatch.setattr(rw, "make_redis_client", lambda: fake)

    rc = rw.main([
        "--dry-run",
        "--now", now.isoformat(),
        "--pretend-missed", "bb-squeeze",
        "--state", str(tmp_path / "wd_state.json"),
        "--holidays", str(tmp_path / "none.txt"),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "KICKSTART" in out and "com.lulala.bb-squeeze" in out


def test_main_non_trading_day_short_circuits(tmp_path, capsys, monkeypatch):
    import fakeredis
    monkeypatch.setattr(rw, "make_redis_client", lambda: fakeredis.FakeStrictRedis(decode_responses=True))
    rc = rw.main([
        "--dry-run",
        "--now", datetime(2026, 7, 11, 18, 0).isoformat(),  # Saturday
        "--state", str(tmp_path / "s.json"),
        "--holidays", str(tmp_path / "none.txt"),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "non-trading" in out.lower() or "not a trading day" in out.lower()


# ── host health: macOS ~49.7-day TCP timer stall (2026-10-03) ────────────
# 開機 50 天後 TIME_WAIT 不再過期 (29k 筆), 臨時埠耗盡 → Redis/TWSE/GitHub 全斷,
# options-iv crash loop。inbox 本身也連不上, 所以告警要能退回本機通知。

def test_host_health_flags_uptime_before_the_49_day_wall():
    from routine_watchdog import host_health
    assert host_health(44.9, 300) == []
    msgs = host_health(45.0, 300)
    assert len(msgs) == 1 and "重開機" in msgs[0] and "45" in msgs[0]


def test_host_health_flags_time_wait_pileup():
    from routine_watchdog import host_health
    msgs = host_health(10.0, 12_000)
    assert len(msgs) == 1 and "TIME_WAIT" in msgs[0] and "12,000" in msgs[0]
    assert len(host_health(50.5, 29_216)) == 2


# ------------------------------------------------------------------ #
# discord forwarder heartbeat (2026-10-06) — alert path must NOT be Discord
# ------------------------------------------------------------------ #
def test_forwarder_stale_fresh_is_none():
    now = datetime(2026, 10, 6, 16, 10)
    health = {"heartbeat_ts": "2026-10-06T16:05:00+08:00", "status": "ok"}
    assert rw.forwarder_stale(health, now) is None


def test_forwarder_stale_old_heartbeat():
    now = datetime(2026, 10, 6, 16, 30)
    health = {"heartbeat_ts": "2026-10-06T16:05:00+08:00", "status": "ok"}
    assert "25" in rw.forwarder_stale(health, now)


def test_forwarder_stale_missing_heartbeat():
    assert rw.forwarder_stale({}, datetime(2026, 10, 6, 16, 30)) is not None


class _HealthRedis:
    def __init__(self, health):
        self.health = health
        self.xadds = []

    def hgetall(self, k):
        assert k == "discord:forward:health"
        return self.health

    def xadd(self, *a, **kw):
        self.xadds.append(a)


def test_check_forwarder_notifies_once_per_stale_heartbeat():
    notes = []
    client = _HealthRedis({"heartbeat_ts": "2026-10-06T15:00:00+08:00"})
    state = {}
    now = datetime(2026, 10, 6, 16, 30)
    assert rw.check_forwarder(client, state, now, dry_run=False, notify=notes.append)
    assert not rw.check_forwarder(client, state, now, dry_run=False, notify=notes.append)
    assert len(notes) == 1
    assert client.xadds == []           # never via inbox→Discord
    # recovery clears, a later stall alerts again
    client.health = {"heartbeat_ts": "2026-10-06T16:29:00+08:00"}
    rw.check_forwarder(client, state, now, dry_run=False, notify=notes.append)
    assert "forwarder_alerted" not in state
    client.health = {"heartbeat_ts": "2026-10-06T16:40:00+08:00"}
    rw.check_forwarder(client, state, datetime(2026, 10, 6, 17, 0), dry_run=False,
                       notify=notes.append)
    assert len(notes) == 2


def test_check_forwarder_dry_run_no_notify():
    notes = []
    client = _HealthRedis({})
    state = {}
    rw.check_forwarder(client, state, datetime(2026, 10, 6, 16, 30), dry_run=True,
                       notify=notes.append)
    assert notes == [] and state == {}
