#!/usr/bin/env python3
"""Weekly drain: Redis stream `claude:inbox` + Postgres `signal_alerts` → `vault/inbox/YYYY-WW.md`.

Cron schedule (user must add via `crontab -e`):
    0 22 * * 0 cd /Users/lulala/Documents/coding/My-TW-Coverage && python3 scripts/redis_to_vault.py

Idempotent — re-running won't duplicate. Tracks cursors per source.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytz
import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
STREAM = os.environ.get("CLAUDE_INBOX_STREAM", "claude:inbox")

REPO_ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = REPO_ROOT / "vault" / "inbox"
LOG_FILE = REPO_ROOT / "vault" / "log.md"
CURSOR_DIR = Path(
    os.path.expanduser(
        "~/.claude/projects/-Users-lulala-Documents-coding-My-TW-Coverage"
    )
)
REDIS_CURSOR = CURSOR_DIR / ".redis_to_vault_cursor"
PG_CURSOR = CURSOR_DIR / ".signal_alerts_to_vault_cursor"
TPE = pytz.timezone("Asia/Taipei")

DOCKER_PSQL_BASE = [
    "docker", "exec", "trading-timescaledb",
    "psql", "-U", "tmf", "-d", "tmf_market_data", "-At", "-F", "|", "-c",
]


def _load(path: Path) -> str | None:
    return path.read_text().strip() if path.exists() else None


def _save(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def _week_key(dt: datetime) -> str:
    iso = dt.astimezone(TPE).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_range(dt: datetime) -> tuple[datetime, datetime]:
    # ISO week starts Monday
    d = dt.astimezone(TPE)
    monday = d - __import__("datetime").timedelta(days=d.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + __import__("datetime").timedelta(days=6, hours=23, minutes=59)
    return monday, sunday


def fetch_redis_messages() -> list[dict]:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    cursor = _load(REDIS_CURSOR)
    start = f"({cursor}" if cursor else "-"
    msgs = r.xrange(STREAM, min=start, count=10000)
    out = []
    for msg_id, body in msgs:
        out.append({
            "msg_id": msg_id,
            "ts": body.get("ts", "?"),
            "from": body.get("from", "?"),
            "topic": body.get("topic", "?"),
            "msg": body.get("msg", ""),
            "tags": body.get("tags", ""),
            "to": body.get("to", "*"),
        })
    if msgs:
        _save(REDIS_CURSOR, msgs[-1][0])
    return out


def fetch_signal_alerts() -> list[dict]:
    """Pull new rows from Postgres tw_electronics.signal_alerts (knowledge-platform-postgres)."""
    # Try to query via Docker exec; if DB not reachable, skip gracefully
    cursor = _load(PG_CURSOR) or "1970-01-01"
    try:
        # Note: signal_alerts table lives in knowledge-platform-postgres (port 5433),
        # NOT trading-timescaledb. Use a separate exec.
        cmd = [
            "docker", "exec", "knowledge-platform-postgres",
            "psql", "-U", "knowledge", "-d", "tw_electronics", "-At", "-F", "|", "-c",
            f"SELECT id, ts, ticker, signal_type, details::text FROM signal_alerts "
            f"WHERE ts > '{cursor}'::timestamptz ORDER BY ts;"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            print(f"[skip signal_alerts] {proc.stderr.strip()[:200]}", file=sys.stderr)
            return []
        rows = []
        for line in proc.stdout.strip().split("\n"):
            if not line: continue
            parts = line.split("|", 4)
            if len(parts) < 4: continue
            rows.append({
                "id": parts[0],
                "ts": parts[1],
                "ticker": parts[2],
                "signal_type": parts[3],
                "details": parts[4] if len(parts) > 4 else "",
            })
        if rows:
            _save(PG_CURSOR, rows[-1]["ts"])
        return rows
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[skip signal_alerts] {e}", file=sys.stderr)
        return []


def write_weekly_dump(messages: list[dict], signals: list[dict]) -> Path | None:
    now = datetime.now(TPE)
    week = _week_key(now)
    monday, sunday = _week_range(now)
    out_path = INBOX_DIR / f"{week}.md"
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    # Group messages by date
    by_date: dict[str, list[dict]] = {}
    for m in messages:
        d = m["ts"][:10]
        by_date.setdefault(d, []).append(m)

    signals_by_date: dict[str, list[dict]] = {}
    for s in signals:
        d = s["ts"][:10]
        signals_by_date.setdefault(d, []).append(s)

    if not messages and not signals:
        print(f"(nothing new since last sync; cursor advanced no-op)")
        return None

    # Append to existing file if same-week, else create fresh
    is_append = out_path.exists()
    mode = "a" if is_append else "w"
    with open(out_path, mode) as f:
        if not is_append:
            f.write(f"""---
type: inbox
week: {week}
range: {monday.date().isoformat()} → {sunday.date().isoformat()}
last_updated: {now.date().isoformat()}
---

# {week} Inbox Dump

Drained from Redis stream `claude:inbox` + Postgres `signal_alerts`.

""")
        f.write(f"\n## Sync at [{now.strftime('%Y-%m-%d %H:%M %Z')}]\n")
        if messages:
            f.write("\n### Redis messages (claude:inbox)\n\n")
            for d in sorted(by_date):
                f.write(f"#### {d}\n\n")
                for m in by_date[d]:
                    tags = f" `[{m['tags']}]`" if m["tags"] else ""
                    f.write(f"- **{m['ts'][11:19]} TWT** · **{m['topic']}** (from `{m['from']}`){tags}\n")
                    f.write(f"  > {m['msg']}\n\n")
        if signals:
            f.write("\n### signal_alerts (Postgres `tw_electronics`)\n\n")
            for d in sorted(signals_by_date):
                f.write(f"#### {d}\n\n")
                for s in signals_by_date[d]:
                    f.write(f"- **{s['signal_type']}** · `{s['ticker']}` (id {s['id']})\n")
                    details = s["details"][:200].replace("\n", " ")
                    f.write(f"  > {details}{'...' if len(s['details']) > 200 else ''}\n\n")
    return out_path


def append_log(out_path: Path | None, n_redis: int, n_signals: int) -> None:
    now = datetime.now(TPE)
    stamp = now.strftime("%Y-%m-%d %H:%M TWT")
    line = f"\n## [{stamp}] sync | claude:inbox {n_redis} msgs + signal_alerts {n_signals} rows"
    if out_path:
        line += f" → {out_path.relative_to(REPO_ROOT)}"
    else:
        line += " (no-op, nothing new)"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true", help="don't write files, don't advance cursors")
    args = p.parse_args()

    print(f"Redis sync starting at {datetime.now(TPE).isoformat()}")
    messages = fetch_redis_messages()
    print(f"  fetched {len(messages)} Redis messages")
    signals = fetch_signal_alerts()
    print(f"  fetched {len(signals)} signal_alerts rows")

    if args.dry_run:
        print("[dry-run] skipping file writes + cursor advances")
        return 0

    out_path = write_weekly_dump(messages, signals)
    if out_path:
        print(f"  wrote {out_path}")
    append_log(out_path, len(messages), len(signals))
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
