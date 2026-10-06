#!/usr/bin/env python3
"""discord_forward.py — claude:inbox → Discord webhook forwarder.

單一整合點:所有 routine 已寫 claude:inbox,本 forwarder 消費 stream 轉發
Discord(與 Grafana alerting 同一 Incoming Webhook,見 database/.env)。

Cursor: Redis key discord:forward:last_id。首跑初始化為當前最新 ID(不回灌
歷史),之後每輪 XRANGE (last_id, +]。逐筆送出成功才前移 → at-least-once。
Topic blocklist 擋高頻噪音(wakegate 每 ~15 分鐘價位 ping)。

launchd: com.lulala.discord-forward 常駐 `--daemon`(KeepAlive):XREAD BLOCK
~5s 即時轉發;一次性模式(無參數)仍可用。
路由:route_topic → trading / reports / system 三頻道,各自
DISCORD_WEBHOOK_URL_{TRADING,REPORTS,SYSTEM},未設則 fallback DISCORD_WEBHOOK_URL。
健康:Redis hash discord:forward:health;連續失敗 ≥3 或 >5 分鐘 → macOS 通知
(osascript,不經 Discord)。分段進度 discord:forward:partial 斷點續送。
Plans: docs/plans/2026-07-30-discord-push.md, docs/plans/2026-10-06-discord-forward-realtime.md
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import signal
import subprocess
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

CURSOR_KEY = "discord:forward:last_id"
PARTIAL_KEY = "discord:forward:partial"   # "<entry_id>:<chunks_sent>" 斷點續送
HEALTH_KEY = "discord:forward:health"
STREAM_KEY = "claude:inbox"
TOPIC_BLOCKLIST = {"wakegate"}          # 高頻價位 ping,會洗版
REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_ENV = REPO_ROOT.parent / "database" / ".env"
CHUNK_LIMIT = 1900                       # Discord content 上限 2000,留頁碼餘裕
MAX_PER_RUN = 25                         # 一輪 XRANGE 撈取 entry 上限
MAX_MSGS_PER_RUN = 25                    # 一輪送出訊息上限 (webhook ~30/min)
MAX_REPORT_CHUNKS = 15                   # 全文切段上限,超過改「見附件」提示
POST_SLEEP = 2.0
RATE_MAX_PER_MIN = 25                    # daemon 滑動視窗:每 60s 最多送出訊息數
BLOCK_MS = 5000                          # daemon XREAD BLOCK
BACKOFF_BASE_S = 5.0
BACKOFF_MAX_S = 60.0
ALERT_STREAK = 3                         # 連續失敗幾次發 macOS 通知
ALERT_PERSIST_S = 300.0                  # 或失敗持續超過 5 分鐘
CLASSES = ("trading", "reports", "system")

log = logging.getLogger("discord_forward")
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
# Routing (pure) — 三頻道
# ------------------------------------------------------------------ #
# trading = 即時交易警報(需要分鐘級反應);盤後日報即使來自交易系統也歸 reports。
TRADING_TOPICS = {
    "gex-regime", "position-watch", "trail_daemon", "trail-daemon", "placer_rejects",
    "loop_nag", "execution_agent", "armed_met", "arm_drift", "loop_anchor_harvest",
    "loop_breakout_cover", "loop_trade_lock", "margin_guard", "margin-guard",
    "margin_alert", "margin-alert", "div-buy", "coordination",
}
TRADING_PREFIXES = ("trail_", "trail-", "margin_guard", "margin-guard", "loop_")
# loop_* 中屬於 session 監管 (infra) 的,歸 system
SYSTEM_OVERRIDES = {"loop_autostart", "loop_down", "loop_heartbeat"}
REPORT_TOPICS = {
    "account-daily", "buy-list", "daily-review", "daily_review", "routine-synthesis",
    "bb-squeeze", "bb-followthrough", "ma-touch", "pb-lights", "disposition-alert",
    "disposition-track", "ddr-price", "brent-watch", "etf-00891", "etf-smart-money",
    "memory-cycle", "txf-levels", "signal-scan", "signal-ledger", "foreign-structure",
    "warrant-flow", "margin-vix", "geo-composite", "news-pulse", "sector-treemap",
    "sf-pairs", "dashboard", "gex-physics",
}
REPORT_PREFIXES = ("daily-review", "daily_review", "account-", "weekly-", "weekly_")


def route_topic(fields: dict) -> str:
    """entry → "trading" | "reports" | "system"。
    優先序:trading 名單 > 帶 report_path 或報告名單 > system(其餘)。"""
    topic = (fields.get("topic") or "").strip()
    if topic and topic not in SYSTEM_OVERRIDES and (
            topic in TRADING_TOPICS or topic.startswith(TRADING_PREFIXES)):
        return "trading"
    if (fields.get("report_path") or "").strip():
        return "reports"
    if topic in REPORT_TOPICS or topic.startswith(REPORT_PREFIXES):
        return "reports"
    return "system"


# ------------------------------------------------------------------ #
# I/O
# ------------------------------------------------------------------ #
def resolve_webhook_urls(environ=None, env_file: Path = DATABASE_ENV) -> dict:
    """每個 class 的 webhook:env → database/.env 的 DISCORD_WEBHOOK_URL_<CLASS>,
    未設則 fallback DISCORD_WEBHOOK_URL。任一 class 無 URL → RuntimeError。"""
    environ = os.environ if environ is None else environ
    file_env = {}
    if env_file is not None and Path(env_file).exists():
        file_env = parse_env_file(Path(env_file).read_text(encoding="utf-8"))

    def lookup(key):
        return (environ.get(key, "").strip() or file_env.get(key, "").strip())

    base = lookup("DISCORD_WEBHOOK_URL")
    urls = {}
    for cls in CLASSES:
        url = lookup("DISCORD_WEBHOOK_URL_" + cls.upper()) or base
        if not url:
            raise RuntimeError("DISCORD_WEBHOOK_URL(_%s) not set (env or %s)"
                               % (cls.upper(), env_file))
        urls[cls] = url
    return urls


def resolve_webhook_url() -> str:
    """相容舊介面:預設(system fallback)頻道。"""
    return resolve_webhook_urls()["system"]


def _as_urls(urls) -> dict:
    return {c: urls for c in CLASSES} if isinstance(urls, str) else urls


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


class RateLimiter:
    """滑動視窗:window 秒內最多 max_events 則;滿了就 sleep 到最舊一筆滑出。"""

    def __init__(self, max_events: int = RATE_MAX_PER_MIN, window: float = 60.0,
                 clock=time.monotonic, sleep=time.sleep):
        self.max_events, self.window = max_events, window
        self.clock, self.sleep = clock, sleep
        self.events = deque()

    def acquire(self) -> None:
        while True:
            now = self.clock()
            while self.events and now - self.events[0] >= self.window:
                self.events.popleft()
            if len(self.events) < self.max_events:
                self.events.append(now)
                return
            self.sleep(self.window - (now - self.events[0]))


def _read_partial(r, entry_id: str):
    """→ (已送段數, partial key 是否存在)。別的 entry 的殘留視為 0。"""
    raw = r.get(PARTIAL_KEY)
    if not raw:
        return 0, False
    pid, _, n = raw.rpartition(":")
    if pid != entry_id:
        return 0, True                        # 別的 entry 的殘留 → 忽略(完成時清掉)
    try:
        return max(0, int(n)), True
    except ValueError:
        return 0, True


def forward_entries(r, entries, urls, *, budget=None, limiter=None,
                    post=None, sleep=None, verbose=False) -> int:
    """逐 entry:過濾→路由→組訊息→(斷點續送)→送出→前移 cursor→清 partial。
    budget(訊息數)用於一次性模式:超出的 entry 整個留給下輪(首個例外)。
    送出失敗直接 raise:partial 已記下送到第幾段,cursor 停在上一 entry。
    回傳送出的 entry 數。"""
    post = post or post_discord
    sleep = sleep or time.sleep
    urls = _as_urls(urls)
    sent = 0
    for entry_id, fields in entries:
        dirty = False
        if should_forward(fields):
            cls = route_topic(fields)
            msgs = build_report_messages(fields, load_report(fields.get("report_path")))
            skip, dirty = _read_partial(r, entry_id)
            dirty = dirty or len(msgs) > 1
            remaining = msgs[skip:]
            if budget is not None:
                if len(remaining) > budget and sent:
                    break                    # 留下輪;cursor 停在上一 entry
                budget -= len(remaining)
            if skip:
                log.info("resume %s at chunk %d/%d", entry_id, skip + 1, len(msgs))
            for i, content in enumerate(remaining, start=skip):
                if limiter is not None:
                    limiter.acquire()
                post(urls[cls], content)
                if len(msgs) > 1:
                    r.set(PARTIAL_KEY, "%s:%d" % (entry_id, i + 1))
                sleep(POST_SLEEP)
            sent += 1
            log.info("sent %s topic=%s class=%s msgs=%d",
                    entry_id, fields.get("topic"), cls, len(remaining))
        r.set(CURSOR_KEY, entry_id)   # 送出(或略過)成功才前移
        if dirty:
            r.delete(PARTIAL_KEY)     # cursor 已前移後才清;中間 crash 也只留無害殘留
    return sent


def _init_cursor(r) -> str:
    entries = r.xrevrange(STREAM_KEY, "+", "-", count=1)
    init = entries[0][0] if entries else "0-0"
    r.set(CURSOR_KEY, init)
    log.info("cursor initialized at %s (歷史不回灌)", init)
    return init


def run_once(r, url, verbose: bool = False) -> int:
    """一次性模式:讀 cursor 之後的新訊息並送出。url 可為單一字串或 class→url dict。
    以送出訊息數為預算,超出的 entry 整個留給下輪(entry 級原子性)。
    回傳送出的 entry 數。"""
    last_id = r.get(CURSOR_KEY)
    if last_id is None:
        _init_cursor(r)
        return 0
    entries = r.xrange(STREAM_KEY, "(" + last_id, "+", count=MAX_PER_RUN)
    return forward_entries(r, entries, url, budget=MAX_MSGS_PER_RUN, verbose=verbose)


# ------------------------------------------------------------------ #
# Health / alerting (never through Discord)
# ------------------------------------------------------------------ #
def _iso(ts) -> str:
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds") if ts else ""


def macos_notify(title: str, msg: str) -> None:
    """本機通知中心(不需網路;Discord 可能正是壞掉的那一端)。"""
    try:
        subprocess.run(["osascript",
                        "-e", "on run argv",
                        "-e", 'display notification (item 2 of argv) with title '
                              '(item 1 of argv) sound name "Basso"',
                        "-e", "end run", title, msg[:200]],
                       capture_output=True, timeout=10)
    except Exception as e:  # noqa: BLE001
        log.error("osascript notification failed: %s", e)


class ForwardHealth:
    """連續失敗追蹤;每個 streak 只通知一次(streak≥3 或持續 >5 分鐘),恢復即清除。"""

    def __init__(self, clock=time.time, notify=macos_notify,
                 streak_alert: int = ALERT_STREAK, persist_alert_s: float = ALERT_PERSIST_S):
        self.clock, self.notify = clock, notify
        self.streak_alert, self.persist_alert_s = streak_alert, persist_alert_s
        self.fail_streak = 0
        self.first_fail_ts = None
        self.alerted = False
        self.last_ok_ts = None
        self.last_err = ""
        self.last_err_ts = None

    def record_ok(self) -> None:
        if self.fail_streak:
            log.info("recovered after %d consecutive failure(s)", self.fail_streak)
        self.fail_streak, self.first_fail_ts, self.alerted = 0, None, False
        self.last_ok_ts = self.clock()

    def record_fail(self, err) -> bool:
        now = self.clock()
        self.fail_streak += 1
        if self.first_fail_ts is None:
            self.first_fail_ts = now
        self.last_err = ("%s: %s" % (type(err).__name__, err))[:300]
        self.last_err_ts = now
        log.warning("delivery failure #%d: %s", self.fail_streak, self.last_err)
        if not self.alerted and (self.fail_streak >= self.streak_alert
                                 or now - self.first_fail_ts > self.persist_alert_s):
            self.alerted = True
            msg = "discord-forward 連續失敗 %d 次 (%ds): %s" % (
                self.fail_streak, int(now - self.first_fail_ts), self.last_err)
            log.error("ALERT (macOS notification): %s", msg)
            self.notify("discord-forward", msg)
            return True
        return False

    def snapshot(self) -> dict:
        return {
            "status": "failing" if self.fail_streak else "ok",
            "fail_streak": str(self.fail_streak),
            "last_ok_ts": _iso(self.last_ok_ts),
            "last_err": self.last_err,
            "last_err_ts": _iso(self.last_err_ts),
            "heartbeat_ts": _iso(self.clock()),
        }

    def write(self, r) -> None:
        r.hset(HEALTH_KEY, mapping=self.snapshot())


# ------------------------------------------------------------------ #
# Daemon
# ------------------------------------------------------------------ #
def daemon_step(r, urls, *, block_ms: int = BLOCK_MS, limiter=None,
                post=None, sleep=None) -> int:
    """一輪:XREAD BLOCK 等新 entry → 轉發。錯誤往上丟給 run_daemon 處理。"""
    last_id = r.get(CURSOR_KEY)
    if last_id is None:
        _init_cursor(r)
        return 0
    res = r.xread({STREAM_KEY: last_id}, count=MAX_PER_RUN, block=block_ms)
    entries = res[0][1] if res else []
    if not entries:
        return 0
    return forward_entries(r, entries, urls, limiter=limiter, post=post, sleep=sleep)


def make_redis(block_ms: int = BLOCK_MS):
    import redis
    return redis.Redis(host=os.environ.get("REDIS_HOST", "localhost"),
                       port=int(os.environ.get("REDIS_PORT", "6379")),
                       decode_responses=True,
                       socket_timeout=block_ms / 1000.0 + 10,
                       socket_connect_timeout=5)


def run_daemon(make_r, urls, *, health=None, limiter=None, block_ms: int = BLOCK_MS,
               post=None, sleep=time.sleep, should_stop=lambda: False,
               max_iterations=None) -> None:
    """常駐迴圈。任何 Redis/網路錯誤都不會讓它結束:記錄、退避、cursor 不動。"""
    health = health or ForwardHealth()
    limiter = limiter or RateLimiter(sleep=sleep)
    r, it = None, 0
    log.info("daemon started (XREAD BLOCK %dms, %d msgs/min)", block_ms, limiter.max_events)
    while not should_stop() and (max_iterations is None or it < max_iterations):
        it += 1
        try:
            if r is None:
                r = make_r()
            daemon_step(r, urls, block_ms=block_ms, limiter=limiter, post=post, sleep=sleep)
            health.record_ok()
            failed = False
        except Exception as e:  # noqa: BLE001 — 守護程序不可被任何錯誤殺死
            health.record_fail(e)
            failed = True
        if r is not None:
            try:
                health.write(r)
            except Exception as e:  # noqa: BLE001
                log.debug("health write failed: %s", e)
        if failed:
            sleep(min(BACKOFF_BASE_S * 2 ** (health.fail_streak - 1), BACKOFF_MAX_S))
    log.info("daemon stopped")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stdout, force=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="送一則測試訊息後結束")
    ap.add_argument("--daemon", action="store_true",
                    help="常駐:XREAD BLOCK 即時轉發 (launchd KeepAlive)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    setup_logging(args.verbose)

    urls = resolve_webhook_urls()
    if args.test:
        post_discord(urls["system"],
                     "**[discord-forward]** ✅ 推送系統測試 — claude:inbox → Discord 通道已就緒")
        log.info("test message sent")
        return 0

    if args.daemon:
        stop = {"flag": False}

        def _term(signum, frame):
            log.info("signal %d received, stopping", signum)
            stop["flag"] = True
        signal.signal(signal.SIGTERM, _term)
        signal.signal(signal.SIGINT, _term)
        distinct = len(set(urls.values()))
        log.info("routing: %d distinct webhook(s) for %s", distinct, ",".join(CLASSES))
        run_daemon(make_redis, urls, should_stop=lambda: stop["flag"])
        return 0

    sent = run_once(make_redis(), urls, verbose=args.verbose)
    if sent or args.verbose:
        log.info("forwarded %d message(s)", sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
