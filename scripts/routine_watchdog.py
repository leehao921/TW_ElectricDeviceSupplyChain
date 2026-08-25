"""routine_watchdog.py — self-heal missed daily launchd routines.

launchd StartCalendarInterval jobs do NOT catch up a run missed while the Mac was
asleep/off (e.g. the 2026-07-07 18:27 reboot that skipped bb-squeeze/bb-followthrough).
This watchdog polls the shared ``claude:inbox`` stream — where every TW daily routine
already publishes a ``topic`` — and, for any routine that hasn't fired on a trading day:

  * within its same-day usefulness window → re-runs it via ``launchctl kickstart -k``
    (launchd supplies the job's identical env/args — no command duplication here);
  * past that window (data would be stale) → pushes a one-shot alert to the inbox.

Detection reuses ``inbox_view.parse_id_ts``; scheduling mirrors the machine's standard
``RunAtLoad=true + StartInterval`` polling agents (system-watchdog, agent-thresholds).

Run:
    python scripts/routine_watchdog.py                 # real poll (launchd)
    python scripts/routine_watchdog.py --dry-run       # decide + print, no side effects
    python scripts/routine_watchdog.py --dry-run --pretend-missed bb-squeeze --now 2026-07-08T18:30

Exit code is always 0 (a watchdog must not flap launchd's KeepAlive/last-exit state).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path

import redis

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from inbox_view import parse_id_ts  # noqa: E402  (reuse stream-id → datetime)

INBOX_STREAM = "claude:inbox"
ALERT_TOPIC = "routine-watchdog"
DEFAULT_STATE = REPO / "data" / "routine_watchdog_state.json"
DEFAULT_HOLIDAYS = REPO / "data" / "tw_market_holidays.txt"

GRACE = timedelta(minutes=2)       # wait this long after sched before acting
COOLDOWN = timedelta(minutes=30)   # min gap between kickstarts of the same job
INBOX_SCAN = 400                   # entries to pull from the stream tail


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
@dataclass
class Check:
    topic: str
    label: str          # launchd label to kickstart
    key: str            # unique state key (topic, or topic:slot)
    sched: time         # scheduled fire time
    window_end: time    # last wall-clock time an auto-rerun is still useful
    slot: str | None = None   # ma-touch: substring that must appear in the msg


# One row per launchd job. ma-touch is one topic across 3 slots → expanded below.
_REGISTRY = [
    # topic, label-suffix, sched, window_end
    ("pb-lights", "pb-lights", time(8, 35), time(13, 30)),
    ("disposition-alert", "disposition-daily", time(8, 35), time(13, 30)),
    ("disposition-track", "disposition-daily", time(8, 35), time(13, 30)),
    ("ddr-price", "ddr-price", time(8, 20), time(13, 30)),
    ("brent-watch", "brent-watch", time(8, 25), time(13, 30)),
    ("etf-00891", "etf-00891-watch", time(8, 30), time(13, 30)),
    ("memory-cycle", "memory-cycle", time(8, 40), time(13, 30)),
    ("buy-list", "buy-list-daily", time(8, 50), time(13, 30)),
    ("bb-squeeze", "bb-squeeze", time(14, 30), time(23, 59)),
    ("bb-followthrough", "bb-followthrough", time(15, 30), time(23, 59)),
    ("etf-smart-money", "etf-smart-money", time(19, 30), time(23, 59)),
    ("routine-synthesis", "daily-synthesis", time(15, 50), time(23, 59)),
    ("foreign-structure", "foreign-structure", time(17, 10), time(23, 59)),
    ("warrant-flow", "warrant-flow", time(17, 40), time(23, 59)),
    ("news-pulse", "news-pulse", time(20, 35), time(23, 59)),
    ("db-backup", "db-backup", time(21, 30), time(23, 59)),
]

# ma-touch: shared topic, 3 intraday slots, only useful while the session is open.
_MA_TOUCH_SLOTS = [
    ("preopen", "ma-touch-preopen", time(9, 30)),
    ("noon", "ma-touch-noon", time(12, 0)),
    ("close", "ma-touch-close", time(13, 20)),
]
_MA_TOUCH_WINDOW_END = time(13, 35)


def build_checks() -> list[Check]:
    checks: list[Check] = []
    for topic, suffix, sched, wend in _REGISTRY:
        checks.append(Check(topic=topic, label=f"com.lulala.{suffix}", key=topic,
                            sched=sched, window_end=wend))
    for slot, suffix, sched in _MA_TOUCH_SLOTS:
        checks.append(Check(topic="ma-touch", label=f"com.lulala.{suffix}",
                            key=f"ma-touch:{slot}", sched=sched,
                            window_end=_MA_TOUCH_WINDOW_END, slot=slot))
    return checks


# --------------------------------------------------------------------------- #
# Pure logic
# --------------------------------------------------------------------------- #
def is_trading_day(now: datetime, holidays: set[str]) -> bool:
    """Mon–Fri and not a listed TW market holiday (YYYY-MM-DD)."""
    if now.weekday() >= 5:            # 5=Sat, 6=Sun
        return False
    return now.date().isoformat() not in holidays


def fired_today(entries, topic: str, since: time, now: datetime,
                slot: str | None = None) -> bool:
    """True if an inbox entry for ``topic`` (and ``slot`` token, if given) exists on
    ``now``'s date at or after ``since``.

    ``entries`` is an XREVRANGE-style list of ``(id_str, {field: value})``.
    """
    today = now.date()
    for entry_id, fields in entries:
        if fields.get("topic") != topic:
            continue
        if slot is not None and f"({slot})" not in (fields.get("msg") or ""):
            continue
        ts = parse_id_ts(entry_id)
        if ts.date() == today and ts.time() >= since:
            return True
    return False


def decide(check: Check, now: datetime, *, fired: bool,
           last_kick: datetime | None) -> str:
    """Return NONE | KICKSTART | ALERT for one check (trading-day already confirmed)."""
    if fired:
        return "NONE"
    if now < datetime.combine(now.date(), check.sched) + GRACE:
        return "NONE"                                    # not due yet
    if now.time() <= check.window_end:
        if last_kick is None or (now - last_kick) >= COOLDOWN:
            return "KICKSTART"
        return "NONE"                                    # kicked recently, let it land
    return "ALERT"                                       # past window → stale


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #
def make_redis_client() -> redis.Redis:
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        decode_responses=True,
    )


def fetch_inbox_entries(client) -> list:
    """Newest-first list of (id, fields) from the inbox stream tail."""
    return client.xrevrange(INBOX_STREAM, max="+", min="-", count=INBOX_SCAN)


def load_holidays(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"last_kick": {}, "alerted": {}}
    try:
        d = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        d = {}
    d.setdefault("last_kick", {})
    d.setdefault("alerted", {})
    return d


def save_state(state: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def kickstart(label: str) -> bool:
    """launchctl kickstart -k gui/<uid>/<label> — force launchd to run the job now."""
    target = f"gui/{os.getuid()}/{label}"
    r = subprocess.run(["launchctl", "kickstart", "-k", target],
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        print(f"[error] kickstart {label} failed: {r.stderr.strip()}", file=sys.stderr)
        return False
    return True


def push_alert(client, *, key: str, label: str, now: datetime) -> None:
    client.xadd(INBOX_STREAM, {
        "ts": now.astimezone().isoformat(),
        "from": "routine_watchdog",
        "topic": ALERT_TOPIC,
        "tags": "watchdog,missed-routine,alert",
        "as_of": now.date().isoformat(),
        "msg": (f"⚠️ 例行任務今日未執行且已過補跑視窗: **{key}** "
                f"({label})。資料已可能過期,建議手動確認。"),
    })


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="decide + print only; no kickstart, no alert, no state write")
    ap.add_argument("--now", default=None, help="override clock (ISO) for testing")
    ap.add_argument("--pretend-missed", action="append", default=[],
                    help="treat this topic/key as not-fired (repeatable)")
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    ap.add_argument("--holidays", default=str(DEFAULT_HOLIDAYS))
    args = ap.parse_args(argv)

    now = datetime.fromisoformat(args.now) if args.now else datetime.now()
    state_path = Path(args.state)
    holidays = load_holidays(Path(args.holidays))
    pretend = set(args.pretend_missed)

    if not is_trading_day(now, holidays):
        print(f"[skip] {now.date()} is not a trading day — nothing to do.")
        return 0

    client = make_redis_client()
    try:
        entries = fetch_inbox_entries(client)
    except Exception as e:  # inbox unreachable → can't judge; don't guess
        print(f"[error] inbox unreachable: {e}", file=sys.stderr)
        return 0

    state = load_state(state_path)
    last_kick = state["last_kick"]
    alerted = state["alerted"]
    today = now.date().isoformat()
    changed = False
    n_kick = n_alert = 0

    for chk in build_checks():
        if chk.key in pretend or chk.topic in pretend:
            fired = False
        else:
            fired = fired_today(entries, chk.topic, chk.sched, now, slot=chk.slot)

        lk_raw = last_kick.get(chk.key)
        lk = datetime.fromisoformat(lk_raw) if lk_raw else None
        # cooldown only applies within the same day
        if lk and lk.date() != now.date():
            lk = None

        action = decide(chk, now, fired=fired, last_kick=lk)

        if action == "NONE":
            continue
        if action == "KICKSTART":
            print(f"KICKSTART {chk.key} → {chk.label}"
                  + ("  [dry-run]" if args.dry_run else ""))
            n_kick += 1
            if not args.dry_run:
                if kickstart(chk.label):
                    last_kick[chk.key] = now.isoformat()
                    changed = True
        elif action == "ALERT":
            if alerted.get(chk.key) == today:
                continue                       # already alerted today
            print(f"ALERT {chk.key} (missed, past window)"
                  + ("  [dry-run]" if args.dry_run else ""))
            n_alert += 1
            if not args.dry_run:
                push_alert(client, key=chk.key, label=chk.label, now=now)
                alerted[chk.key] = today
                changed = True

    print(f"[poll] {now:%Y-%m-%d %H:%M} trading_day=True checks={len(build_checks())} "
          f"kickstart={n_kick} alert={n_alert}"
          + ("  [dry-run]" if args.dry_run else ""))
    if changed and not args.dry_run:
        save_state(state, state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
