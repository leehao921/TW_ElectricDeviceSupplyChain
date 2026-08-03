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
import re
import sys
import time
from pathlib import Path

CURSOR_KEY = "discord:forward:last_id"
STREAM_KEY = "claude:inbox"
TOPIC_BLOCKLIST = {"wakegate"}          # 高頻價位 ping,會洗版
REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_ENV = REPO_ROOT.parent / "database" / ".env"
CHUNK_LIMIT = 1900                       # Discord content 上限 2000,留頁碼餘裕
MAX_PER_RUN = 25                         # 一輪 XRANGE 撈取 entry 上限
MAX_MSGS_PER_RUN = 25                    # 一輪送出訊息上限 (webhook ~30/min)
MAX_REPORT_CHUNKS = 15                   # 全文切段上限,超過改「見附件」提示
POST_SLEEP = 2.0
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
    # producer 常用字面 \n 當換行 (redis-cli 不解譯 escape) → 轉真換行
    msg = fields.get("msg", "").replace("\\n", "\n")
    return "**[%s]** %s%s" % (topic, emoji, msg)


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


def _disp_width_char(ch: str) -> int:
    """CJK 全形字在 monospace 下佔 2 格。"""
    import unicodedata
    return 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1


def _disp_width(s: str) -> int:
    return sum(_disp_width_char(ch) for ch in s)


def _pad(s: str, width: int) -> str:
    return s + " " * (width - _disp_width(s))


def _is_table_line(ln: str) -> bool:
    ln = ln.strip()
    return ln.startswith("|") and ln.endswith("|") and ln.count("|") >= 3


def _is_separator_cells(cells) -> bool:
    return all(c.strip() and set(c.strip()) <= set(":-") for c in cells)


def _render_table(lines) -> str:
    """markdown 表格行 → 等寬 ASCII 對齊 (CJK=2 計寬),包 code fence。"""
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    ncol = max(len(r) for r in rows)
    for r in rows:
        r.extend([""] * (ncol - len(r)))
    sep_idx = {i for i, r in enumerate(rows) if _is_separator_cells(r)}
    widths = [0] * ncol
    for i, r in enumerate(rows):
        if i in sep_idx:
            continue
        for j, c in enumerate(r):
            widths[j] = max(widths[j], _disp_width(c))
    out = []
    for i, r in enumerate(rows):
        if i in sep_idx:
            out.append("+" + "+".join("-" * (w + 2) for w in widths) + "+")
        else:
            out.append("| " + " | ".join(_pad(r[j], widths[j]) for j in range(ncol)) + " |")
    return "```\n" + "\n".join(out) + "\n```"


def convert_tables(text: str) -> str:
    """Discord 訊息不渲染 markdown 表格 → 轉 code block 等寬排版。非表格行原樣。"""
    lines = text.split("\n")
    out, block = [], []
    for ln in lines + [""]:                  # 哨兵行沖出最後一個 block
        if _is_table_line(ln):
            block.append(ln)
            continue
        if block:
            if len(block) >= 2:
                out.append(_render_table(block))
            else:
                out.extend(block)            # 孤行不是表格
            block = []
        out.append(ln)
    return "\n".join(out[:-1])               # 去掉哨兵


def rebalance_fences(chunks) -> list:
    """切段後每段的 ``` 必須成對:段尾未閉合→補閉合,下一段開頭補開啟。"""
    out, carry = [], False
    for c in chunks:
        if carry:
            m = re.match(r"^\(\d+/\d+\) ", c)
            cut = m.end() if m else 0
            c = c[:cut] + "```\n" + c[cut:]
        if c.count("```") % 2 == 1:
            c += "\n```"
            carry = True
        else:
            carry = False
        out.append(c)
    return out


def resolve_report_path(raw, repo_root: Path = REPO_ROOT):
    """report_path 解析:相對路徑以 repo root 為基準;resolve 後必須落在
    repo 內且為 .md,否則 None(stream 內容不可指到任意檔案)。"""
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = repo_root / p
    p = p.resolve()
    if p.suffix != ".md":
        return None
    try:
        p.relative_to(repo_root)
    except ValueError:
        return None
    return p


def build_report_messages(fields: dict, report_text,
                          limit: int = CHUNK_LIMIT,
                          max_report_chunks: int = MAX_REPORT_CHUNKS) -> list:
    """組出一個 entry 要送的訊息序列(內容字串 list)。

    有報告全文時:摘要切段 → 全文切段。
    去重:msg 已包含於全文(bb-followthrough msg==全文)→ 跳過全文段。
    全文段數超過 cap → 截斷並補一則提示(完整檔留在 analysis/)。
    """
    summary = chunk_message(format_entry(fields), limit)
    if not report_text:
        return summary
    if (fields.get("msg") or "").strip() in report_text:
        return summary
    body = rebalance_fences(chunk_message(convert_tables(report_text), limit))
    if len(body) > max_report_chunks:
        body = body[:max_report_chunks] + ["(報告全文過長，其餘截斷 — 完整檔在 analysis/)"]
    return summary + body


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


def load_report(raw):
    """report_path → 報告全文;任何失敗回 None,
    forwarder fallback 只送摘要,cursor 照常前移不卡死。"""
    try:
        p = resolve_report_path(raw)
        if p is None or not p.exists():
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def run_once(r, url: str, verbose: bool = False) -> int:
    """讀 cursor 之後的新訊息,過濾→格式化(含報告全文)→送出→前移 cursor。
    以送出訊息數為預算,超出的 entry 整個留給下輪(entry 級原子性)。
    回傳送出的 entry 數。"""
    last_id = r.get(CURSOR_KEY)
    if last_id is None:
        entries = r.xrevrange(STREAM_KEY, "+", "-", count=1)
        init = entries[0][0] if entries else "0-0"
        r.set(CURSOR_KEY, init)
        print("cursor initialized at %s (歷史不回灌)" % init)
        return 0

    entries = r.xrange(STREAM_KEY, "(" + last_id, "+", count=MAX_PER_RUN)
    sent, budget = 0, MAX_MSGS_PER_RUN
    for entry_id, fields in entries:
        if should_forward(fields):
            text = load_report(fields.get("report_path"))
            msgs = build_report_messages(fields, text)
            if len(msgs) > budget and sent:
                break                    # 留下輪;cursor 停在上一 entry
            for content in msgs:
                post_discord(url, content)
                time.sleep(POST_SLEEP)
            budget -= len(msgs)
            sent += 1
            if verbose:
                print("sent %s topic=%s msgs=%d"
                      % (entry_id, fields.get("topic"), len(msgs)))
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
