#!/usr/bin/env python3
"""discord_forward.py — claude:inbox → Discord webhook forwarder.

單一整合點:所有 routine 已寫 claude:inbox,本 forwarder 消費 stream 轉發
Discord(與 Grafana alerting 同一 Incoming Webhook,見 database/.env)。

Cursor: Redis key discord:forward:last_id。首跑初始化為當前最新 ID(不回灌
歷史),之後每輪 XRANGE (last_id, +]。逐筆送出成功才前移 → at-least-once。
Topic blocklist 擋高頻噪音(wakegate 每 ~15 分鐘價位 ping)。

launchd: com.lulala.discord-forward 每 300s(venv python 直跑,TCC)。
Plan: docs/plans/2026-07-30-discord-push.md
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

CURSOR_KEY = "discord:forward:last_id"
STREAM_KEY = "claude:inbox"
TOPIC_BLOCKLIST = {"wakegate"}          # 高頻價位 ping,會洗版
DATABASE_ENV = Path(__file__).resolve().parents[2] / "database" / ".env"
CHUNK_LIMIT = 1900                       # Discord content 上限 2000,留頁碼餘裕
MAX_PER_RUN = 25                         # webhook ~30/min,超出留給下輪
SEVERITY_EMOJI = {"WARN": "⚠️ ", "WARNING": "⚠️ ", "ALERT": "🚨 ", "CRITICAL": "🚨 "}


# ------------------------------------------------------------------ #
# Pure
# ------------------------------------------------------------------ #
def parse_env_file(text: str) -> dict:
    """極簡 .env 解析:KEY=VALUE,略過註解/空行,去除包覆引號。"""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k.strip()] = v
    return out


def should_forward(fields: dict, blocklist=None) -> bool:
    if not (fields.get("msg") or "").strip():
        return False
    topic = fields.get("topic", "")
    return topic not in (TOPIC_BLOCKLIST if blocklist is None else blocklist)


def format_entry(fields: dict) -> str:
    topic = fields.get("topic") or "inbox"
    emoji = SEVERITY_EMOJI.get((fields.get("severity") or "").upper(), "")
    return "**[%s]** %s%s" % (topic, emoji, fields.get("msg", ""))


def chunk_message(text: str, limit: int = CHUNK_LIMIT) -> list:
    """切段:優先在換行斷,無換行硬切;多段時加 (i/n) 頁碼。"""
    if len(text) <= limit:
        return [text]
    parts, rest = [], text
    while rest:
        if len(rest) <= limit:
            parts.append(rest)
            break
        cut = rest.rfind("\n", 1, limit)
        if cut <= 0:
            cut = limit
        parts.append(rest[:cut])
        rest = rest[cut:].lstrip("\n")
    n = len(parts)
    return ["(%d/%d) %s" % (i + 1, n, p) for i, p in enumerate(parts)]


# ------------------------------------------------------------------ #
# I/O
# ------------------------------------------------------------------ #
def resolve_webhook_url() -> str:
    import os
    url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if url:
        return url
    if DATABASE_ENV.exists():
        url = parse_env_file(DATABASE_ENV.read_text(encoding="utf-8")).get(
            "DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set (env or %s)" % DATABASE_ENV)
    return url


def post_discord(url: str, content: str) -> None:
    """POST 一則;429 依 retry_after 退避重試一次。"""
    import requests
    for attempt in range(2):
        r = requests.post(url, json={"content": content}, timeout=15)
        if r.status_code == 429 and attempt == 0:
            time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
            continue
        r.raise_for_status()
        return


def run_once(r, url: str, verbose: bool = False) -> int:
    """讀 cursor 之後的新訊息,過濾→格式化→送出→前移 cursor。回傳送出則數。"""
    last_id = r.get(CURSOR_KEY)
    if last_id is None:
        entries = r.xrevrange(STREAM_KEY, "+", "-", count=1)
        init = entries[0][0] if entries else "0-0"
        r.set(CURSOR_KEY, init)
        print("cursor initialized at %s (歷史不回灌)" % init)
        return 0

    entries = r.xrange(STREAM_KEY, "(" + last_id, "+", count=MAX_PER_RUN)
    sent = 0
    for entry_id, fields in entries:
        if should_forward(fields):
            for chunk in chunk_message(format_entry(fields)):
                post_discord(url, chunk)
                time.sleep(1)
            sent += 1
            if verbose:
                print("sent %s topic=%s" % (entry_id, fields.get("topic")))
        r.set(CURSOR_KEY, entry_id)   # 送出(或略過)成功才前移
    return sent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="送一則測試訊息後結束")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    url = resolve_webhook_url()
    if args.test:
        post_discord(url, "**[discord-forward]** ✅ 推送系統測試 — claude:inbox → Discord 通道已就緒")
        print("test message sent")
        return 0

    import redis
    r = redis.Redis(decode_responses=True)
    sent = run_once(r, url, verbose=args.verbose)
    if sent or args.verbose:
        print("forwarded %d message(s)" % sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
