#!/usr/bin/env python3
"""Cross-session messaging via Redis stream `claude:inbox`.

Each Claude Code session can:
  - send: push a message addressed to '*' (broadcast) or specific session
  - read: drain messages since last cursor (per-machine, idempotent)
  - list: show recent messages without advancing cursor

Stream is persistent — messages survive when no session is reading.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import pytz
import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
STREAM = os.environ.get("CLAUDE_INBOX_STREAM", "claude:inbox")
CURSOR_FILE = os.path.expanduser(
    "~/.claude/projects/-Users-lulala-Documents-coding-My-TW-Coverage/.claude_msg_cursor"
)
TPE = pytz.timezone("Asia/Taipei")

_R: redis.Redis | None = None


def _client() -> redis.Redis:
    global _R
    if _R is None:
        _R = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _R


def _load_cursor() -> str | None:
    if os.path.exists(CURSOR_FILE):
        return open(CURSOR_FILE).read().strip() or None
    return None


def _save_cursor(msg_id: str) -> None:
    os.makedirs(os.path.dirname(CURSOR_FILE), exist_ok=True)
    open(CURSOR_FILE, "w").write(msg_id)


def send(topic: str, msg: str, to: str = "*", tags: list[str] | None = None) -> None:
    payload = {
        "ts": datetime.now(TPE).isoformat(),
        "from": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
        "to": to,
        "topic": topic,
        "msg": msg,
        "tags": ",".join(tags or []),
    }
    msg_id = _client().xadd(STREAM, payload)
    print(f"sent {msg_id} [{topic}] {msg[:60]}{'...' if len(msg) > 60 else ''}")


def read(mark: bool = True, limit: int = 50) -> int:
    """Drain messages newer than saved cursor. Return number printed."""
    cursor = _load_cursor()
    # xrange is inclusive on min; bump to '(<id>' to exclude last-read
    start = f"({cursor}" if cursor else "-"
    msgs = _client().xrange(STREAM, min=start, count=limit)
    if not msgs:
        print("(claude:inbox 無新訊息)")
        return 0
    for msg_id, body in msgs:
        ts = body.get("ts", "?")
        topic = body.get("topic", "?")
        sender = body.get("from", "?")
        text = body.get("msg", "")
        tags = body.get("tags", "")
        line = f"[{ts}] [{topic}] {sender}: {text}"
        print(line)
        if tags:
            print(f"   tags: {tags}")
    if mark:
        _save_cursor(msgs[-1][0])
    return len(msgs)


def list_recent(limit: int = 20) -> None:
    msgs = _client().xrevrange(STREAM, count=limit)
    if not msgs:
        print("(claude:inbox 空)")
        return
    for msg_id, body in msgs:
        topic = body.get("topic", "?")
        text = body.get("msg", "")[:80]
        ts = body.get("ts", "?")[:19]
        print(f"{ts} | {msg_id} | [{topic}] {text}")


def stats() -> None:
    info = _client().xinfo_stream(STREAM) if _client().exists(STREAM) else None
    if not info:
        print(f"stream {STREAM} not yet created")
        return
    print(f"stream:       {STREAM}")
    print(f"length:       {info['length']}")
    print(f"first entry:  {info.get('first-entry', [None])[0]}")
    print(f"last entry:   {info.get('last-entry', [None])[0]}")
    print(f"cursor file:  {CURSOR_FILE}")
    print(f"cursor value: {_load_cursor() or '(none — read from start)'}")


def main(argv: list[str] | None = None) -> int:
    global REDIS_HOST, REDIS_PORT, _R
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--host", default=REDIS_HOST, help=f"Redis host (default: {REDIS_HOST})"
    )
    p.add_argument(
        "--port", type=int, default=REDIS_PORT, help=f"Redis port (default: {REDIS_PORT})"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("send", help="send a message")
    sp.add_argument("topic")
    sp.add_argument("msg")
    sp.add_argument("--to", default="*", help="recipient session id or '*'")
    sp.add_argument("--tags", nargs="*", default=[])

    sp = sub.add_parser("read", help="drain new messages since last cursor")
    sp.add_argument("--no-mark", action="store_true", help="don't advance cursor")
    sp.add_argument("--limit", type=int, default=50)

    sp = sub.add_parser("list", help="recent messages without advancing cursor")
    sp.add_argument("--limit", type=int, default=20)

    sub.add_parser("stats", help="stream info + cursor position")

    sp = sub.add_parser("reset", help="clear the read cursor")
    args = p.parse_args(argv)

    # Override env via CLI
    REDIS_HOST = args.host
    REDIS_PORT = args.port
    _R = None  # force reconnect with new host/port

    if args.cmd == "send":
        send(args.topic, args.msg, args.to, args.tags)
    elif args.cmd == "read":
        read(mark=not args.no_mark, limit=args.limit)
    elif args.cmd == "list":
        list_recent(args.limit)
    elif args.cmd == "stats":
        stats()
    elif args.cmd == "reset":
        if os.path.exists(CURSOR_FILE):
            os.remove(CURSOR_FILE)
            print(f"cursor reset ({CURSOR_FILE} removed)")
        else:
            print("no cursor to reset")
    return 0


if __name__ == "__main__":
    sys.exit(main())
