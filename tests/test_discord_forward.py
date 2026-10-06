"""Tests for scripts/discord_forward.py — claude:inbox → Discord webhook forwarder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import discord_forward  # noqa: E402
from discord_forward import (  # noqa: E402
    REPO_ROOT,
    TOPIC_BLOCKLIST,
    build_report_messages,
    chunk_message,
    convert_tables,
    format_entry,
    parse_env_file,
    rebalance_fences,
    resolve_report_path,
    should_forward,
)


# ------------------------------------------------------------------ #
# parse_env_file
# ------------------------------------------------------------------ #
class TestParseEnvFile:
    def test_basic_kv(self):
        env = parse_env_file("FOO=bar\nDISCORD_WEBHOOK_URL=https://x/y\n")
        assert env["DISCORD_WEBHOOK_URL"] == "https://x/y"

    def test_skips_comments_and_blanks(self):
        env = parse_env_file("# comment\n\nA=1\n  # indented comment\n")
        assert env == {"A": "1"}

    def test_strips_quotes(self):
        env = parse_env_file('A="quoted"\nB=\'single\'\n')
        assert env["A"] == "quoted"
        assert env["B"] == "single"

    def test_value_may_contain_equals(self):
        env = parse_env_file("URL=https://a/b?x=1&y=2\n")
        assert env["URL"] == "https://a/b?x=1&y=2"

    def test_malformed_lines_ignored(self):
        env = parse_env_file("JUSTAWORD\nA=1\n")
        assert env == {"A": "1"}


# ------------------------------------------------------------------ #
# should_forward
# ------------------------------------------------------------------ #
class TestShouldForward:
    def test_normal_topic_forwarded(self):
        assert should_forward({"topic": "bb-squeeze", "msg": "x"})

    def test_wakegate_blocked_by_default(self):
        assert "wakegate" in TOPIC_BLOCKLIST
        assert not should_forward({"topic": "wakegate", "msg": "price ping"})

    def test_missing_topic_still_forwarded(self):
        assert should_forward({"msg": "orphan message"})

    def test_empty_msg_not_forwarded(self):
        assert not should_forward({"topic": "bb-squeeze", "msg": ""})
        assert not should_forward({"topic": "bb-squeeze"})

    def test_custom_blocklist(self):
        assert not should_forward({"topic": "noisy", "msg": "x"}, blocklist={"noisy"})


# ------------------------------------------------------------------ #
# format_entry
# ------------------------------------------------------------------ #
class TestFormatEntry:
    def test_topic_header_and_msg(self):
        out = format_entry({"topic": "ma-touch", "msg": "跌破季線"})
        assert out.startswith("**[ma-touch]**")
        assert "跌破季線" in out

    def test_severity_emoji_warn(self):
        out = format_entry({"topic": "t", "severity": "WARN", "msg": "x"})
        assert "⚠️" in out

    def test_severity_emoji_alert(self):
        out = format_entry({"topic": "t", "severity": "ALERT", "msg": "x"})
        assert "🚨" in out

    def test_info_severity_no_emoji(self):
        out = format_entry({"topic": "t", "severity": "INFO", "msg": "x"})
        assert "⚠️" not in out and "🚨" not in out

    def test_missing_topic_placeholder(self):
        out = format_entry({"msg": "x"})
        assert out.startswith("**[inbox]**")

    def test_literal_backslash_n_converted_to_newline(self):
        # daily_synthesis 等 producer 用字面 \n 當換行 (redis-cli 不解譯)
        out = format_entry({"topic": "routine-synthesis", "msg": "第一行\\n\\n第二行"})
        assert "\\n" not in out
        assert "第一行\n\n第二行" in out

    def test_real_newlines_untouched(self):
        out = format_entry({"topic": "t", "msg": "第一行\n第二行"})
        assert out == "**[t]** 第一行\n第二行"


# ------------------------------------------------------------------ #
# chunk_message
# ------------------------------------------------------------------ #
class TestChunkMessage:
    def test_short_message_single_chunk_no_pagination(self):
        assert chunk_message("hello") == ["hello"]

    def test_long_message_split_under_limit(self):
        text = "\n".join("line %04d" % i for i in range(500))  # ~4500 chars
        chunks = chunk_message(text, limit=1900)
        assert len(chunks) >= 2
        assert all(len(c) <= 2000 for c in chunks)

    def test_pagination_markers(self):
        text = "\n".join("line %04d" % i for i in range(500))
        chunks = chunk_message(text, limit=1900)
        n = len(chunks)
        assert chunks[0].startswith("(1/%d) " % n)
        assert chunks[-1].startswith("(%d/%d) " % (n, n))

    def test_splits_at_newline_boundary(self):
        text = "\n".join("line %04d" % i for i in range(500))
        chunks = chunk_message(text, limit=1900)
        # 除頁碼前綴外,每段應以完整行結尾 (不從行中間硬切)
        for c in chunks[:-1]:
            assert c.endswith("line %s" % c.rstrip().split("line ")[-1])
            assert not c.endswith(" ")

    def test_no_content_lost(self):
        text = "\n".join("line %04d" % i for i in range(500))
        chunks = chunk_message(text, limit=1900)
        rejoined = "".join(c.split(") ", 1)[1] for c in chunks)
        assert rejoined.replace("\n", "") == text.replace("\n", "")

    def test_giant_single_line_hard_split(self):
        text = "x" * 5000  # 無換行可斷
        chunks = chunk_message(text, limit=1900)
        assert all(len(c) <= 2000 for c in chunks)
        assert sum(len(c.split(") ", 1)[1]) for c in chunks) == 5000


# ------------------------------------------------------------------ #
# convert_tables — markdown 表格 → code block 等寬 ASCII
# ------------------------------------------------------------------ #
class TestConvertTables:
    TABLE = ("前文\n"
             "| 題材 | 則數 | z |\n"
             "|---|---|---|\n"
             "| 記憶體 | 36 | 2.1 |\n"
             "| AI | 11 | 0.5 |\n"
             "後文\n")

    def test_table_wrapped_in_code_fence(self):
        out = convert_tables(self.TABLE)
        assert out.count("```") == 2
        assert "前文" in out and "後文" in out

    def test_separator_row_becomes_dashes(self):
        out = convert_tables(self.TABLE)
        assert "|---|" not in out
        assert "-" in out.split("```")[1]

    def test_columns_aligned_cjk_double_width(self):
        out = convert_tables(self.TABLE)
        block = out.split("```")[1].strip("\n").splitlines()
        rows = [ln for ln in block if not set(ln) <= set("-+| ")]
        # 「記憶體」顯示寬 6、「AI」寬 2:第二欄起點須一致 (CJK=2 計寬)
        starts = []
        for ln in rows:
            cells = ln.split("|")
            first = cells[1]
            w = sum(2 if discord_forward._disp_width_char(ch) == 2 else 1 for ch in first)
            starts.append(w)
        assert len(set(starts)) == 1

    def test_text_without_table_unchanged(self):
        assert convert_tables("plain\ntext\n") == "plain\ntext\n"

    def test_multiple_tables_each_fenced(self):
        two = self.TABLE + "\n" + self.TABLE
        assert convert_tables(two).count("```") == 4


# ------------------------------------------------------------------ #
# rebalance_fences — 切段不可把 code block 劈成兩半
# ------------------------------------------------------------------ #
class TestRebalanceFences:
    def test_split_inside_fence_gets_closed_and_reopened(self):
        chunks = ["(1/2) text\n```\n| a | b |", "(2/2) | c | d |\n```\nrest"]
        out = rebalance_fences(chunks)
        assert all(c.count("```") % 2 == 0 for c in out)
        assert out[0].endswith("```")
        assert "```" in out[1].split("\n")[0] or out[1].startswith("(2/2) ```")

    def test_balanced_chunks_untouched(self):
        chunks = ["```\nx\n```", "plain"]
        assert rebalance_fences(chunks) == chunks

    def test_build_report_messages_all_chunks_balanced(self):
        rows = "\n".join("| 題材%d | %d | 內容說明文字較長一點 |" % (i, i) for i in range(300))
        report = "# 報告\n| 題材 | 則數 | 說明 |\n|---|---|---|\n" + rows + "\n尾文"
        msgs = build_report_messages({"topic": "t", "msg": "摘要"}, report)
        assert len(msgs) > 2
        assert all(c.count("```") % 2 == 0 for c in msgs)
        assert all(len(c) <= 2000 for c in msgs)


# ------------------------------------------------------------------ #
# resolve_report_path
# ------------------------------------------------------------------ #
class TestResolveReportPath:
    def test_absolute_inside_repo(self):
        p = resolve_report_path(str(REPO_ROOT / "analysis" / "x.md"))
        assert p == REPO_ROOT / "analysis" / "x.md"

    def test_relative_resolved_against_repo_root(self):
        p = resolve_report_path("analysis/x.md")
        assert p == REPO_ROOT / "analysis" / "x.md"

    def test_outside_repo_rejected(self):
        assert resolve_report_path("/tmp/evil.md") is None

    def test_traversal_rejected(self):
        assert resolve_report_path("../../../etc/passwd.md") is None

    def test_empty_or_none(self):
        assert resolve_report_path("") is None
        assert resolve_report_path(None) is None

    def test_non_md_rejected(self):
        assert resolve_report_path("analysis/x.txt") is None


# ------------------------------------------------------------------ #
# build_report_messages
# ------------------------------------------------------------------ #
class TestBuildReportMessages:
    FIELDS = {"topic": "news-pulse", "msg": "題材脈衝摘要一行"}

    def test_no_report_same_as_plain(self):
        msgs = build_report_messages(self.FIELDS, None)
        assert msgs == chunk_message(format_entry(self.FIELDS))

    def test_short_report_summary_then_body(self):
        msgs = build_report_messages(self.FIELDS, "# 報告\n完整內容")
        assert msgs == [format_entry(self.FIELDS), "# 報告\n完整內容"]

    def test_long_report_chunked(self):
        report = "\n".join("row %04d" % i for i in range(1200))  # ~10KB
        msgs = build_report_messages(self.FIELDS, report)
        assert len(msgs) >= 4
        assert all(len(c) <= 2000 for c in msgs)

    def test_containment_dedup_skips_body(self):
        # bb-followthrough 情境: msg 即報告全文 → 不重複切段
        digest = "**BB 追蹤**\n多行報告內容\n第三行"
        fields = {"topic": "bb-followthrough", "msg": digest}
        msgs = build_report_messages(fields, digest + "\n")
        assert msgs == [format_entry(fields)]

    def test_over_cap_truncated_with_notice(self):
        report = "\n".join("row %05d" % i for i in range(6000))  # 遠超 15 段
        msgs = build_report_messages(self.FIELDS, report, max_report_chunks=15)
        summary_n = len(chunk_message(format_entry(self.FIELDS)))
        assert len(msgs) == summary_n + 15 + 1
        assert "截斷" in msgs[-1]

    def test_empty_report_text_treated_as_none(self):
        msgs = build_report_messages(self.FIELDS, "")
        assert msgs == chunk_message(format_entry(self.FIELDS))


# ------------------------------------------------------------------ #
# post_discord (mock requests)
# ------------------------------------------------------------------ #
class _Resp:
    def __init__(self, status_code=204, retry_after=1):
        self.status_code = status_code
        self._retry = retry_after

    def json(self):
        return {"retry_after": self._retry}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %d" % self.status_code)


class TestPostDiscord:
    def test_plain_uses_json_payload(self, monkeypatch):
        calls = []
        import requests
        monkeypatch.setattr(requests, "post", lambda url, **kw: calls.append(kw) or _Resp())
        discord_forward.post_discord("http://x", "hello")
        assert calls[0]["json"] == {"content": "hello"}
        assert "files" not in calls[0]

    def test_429_backoff_then_retry(self, monkeypatch):
        seq = [_Resp(429, retry_after=0), _Resp(204)]
        import requests
        monkeypatch.setattr(requests, "post", lambda url, **kw: seq.pop(0))
        monkeypatch.setattr(discord_forward.time, "sleep", lambda s: None)
        discord_forward.post_discord("http://x", "hello")
        assert not seq  # 兩次都用掉


# ------------------------------------------------------------------ #
# run_once (fake redis)
# ------------------------------------------------------------------ #
class FakeRedis:
    def __init__(self, entries, cursor="0-0"):
        self.entries = entries      # [(id, fields)]
        self.kv = {"discord:forward:last_id": cursor}

    def get(self, k):
        return self.kv.get(k)

    def set(self, k, v):
        self.kv[k] = v

    def delete(self, k):
        self.kv.pop(k, None)

    def xrange(self, stream, lo, hi, count=None):
        lo_id = lo.lstrip("(")
        out = [(i, f) for i, f in self.entries if i > lo_id]
        return out[:count] if count else out

    def xrevrange(self, stream, hi, lo, count=None):
        return list(reversed(self.entries))[:count]


class TestRunOnce:
    def _patch(self, monkeypatch, load_ret=None):
        sent = []
        monkeypatch.setattr(discord_forward, "post_discord",
                            lambda url, content: sent.append(content))
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: load_ret)
        monkeypatch.setattr(discord_forward.time, "sleep", lambda s: None)
        return sent

    def test_report_entry_sends_summary_then_body(self, monkeypatch):
        sent = self._patch(monkeypatch, load_ret="# 報告\n內容")
        r = FakeRedis([("1-0", {"topic": "t", "msg": "摘要", "report_path": "analysis/r.md"})])
        n = discord_forward.run_once(r, "http://x")
        assert n == 1
        assert sent == ["**[t]** 摘要", "# 報告\n內容"]
        assert r.kv["discord:forward:last_id"] == "1-0"

    def test_bogus_report_path_falls_back_to_summary(self, monkeypatch):
        sent = self._patch(monkeypatch, load_ret=None)
        r = FakeRedis([("1-0", {"topic": "t", "msg": "摘要", "report_path": "analysis/nope.md"})])
        assert discord_forward.run_once(r, "http://x") == 1
        assert sent == ["**[t]** 摘要"]
        assert r.kv["discord:forward:last_id"] == "1-0"

    def test_old_format_entry_unchanged(self, monkeypatch):
        sent = self._patch(monkeypatch)
        r = FakeRedis([("1-0", {"topic": "t", "msg": "普通訊息"})])
        assert discord_forward.run_once(r, "http://x") == 1
        assert sent == ["**[t]** 普通訊息"]

    def test_budget_defers_entry_to_next_run(self, monkeypatch):
        big = "\n".join("row %04d" % i for i in range(1200))  # ~10KB → 摘要+多段
        sent = self._patch(monkeypatch, load_ret=big)
        entries = [("%d-0" % i, {"topic": "t", "msg": "摘要", "report_path": "analysis/r.md"})
                   for i in range(1, 6)]
        r = FakeRedis(entries)
        n = discord_forward.run_once(r, "http://x")
        assert n < 5                                    # 有 entry 留到下輪
        assert r.kv["discord:forward:last_id"] == "%d-0" % n  # cursor 停在最後送出的
        per_entry = len(build_report_messages(entries[0][1], big))
        assert len(sent) == n * per_entry
        assert len(sent) <= discord_forward.MAX_MSGS_PER_RUN

    def test_first_entry_over_budget_still_sent(self, monkeypatch):
        huge = "x" * 60000
        monkeypatch.setattr(discord_forward, "MAX_MSGS_PER_RUN", 1)
        sent = self._patch(monkeypatch, load_ret=huge)
        r = FakeRedis([("1-0", {"topic": "t", "msg": "摘要", "report_path": "analysis/r.md"})])
        assert discord_forward.run_once(r, "http://x") == 1
        assert len(sent) >= 2
        assert r.kv["discord:forward:last_id"] == "1-0"


# ================================================================== #
# 2026-10-06 — realtime daemon / routing / observability / chunk resume
# ================================================================== #
class FakeRedis2(FakeRedis):
    """FakeRedis + delete/hset/xread + failure injection."""

    def __init__(self, entries, cursor="0-0"):
        super().__init__(entries, cursor)
        if cursor is None:
            self.kv.pop("discord:forward:last_id")
        self.hashes = {}
        self.fail_next = 0          # raise on the next N xread calls
        self.xread_calls = []

    def hset(self, k, mapping=None, **kw):
        self.hashes.setdefault(k, {}).update(mapping or {})

    def xread(self, streams, count=None, block=None):
        self.xread_calls.append((dict(streams), count, block))
        if self.fail_next:
            self.fail_next -= 1
            raise ConnectionError("Error 49 connecting: Can't assign requested address")
        (stream, last), = streams.items()
        out = [(i, f) for i, f in self.entries if i > last]
        if count:
            out = out[:count]
        return [[stream, out]] if out else []


URLS = {"trading": "http://trading", "reports": "http://reports", "system": "http://system"}


# ------------------------------------------------------------------ #
# route_topic
# ------------------------------------------------------------------ #
class TestRouteTopic:
    def test_trading_topics(self):
        for t in ("gex-regime", "position-watch", "trail_daemon", "trail-daemon",
                  "placer_rejects", "loop_nag", "execution_agent", "armed_met",
                  "margin_guard", "loop_anchor_harvest"):
            assert discord_forward.route_topic({"topic": t, "msg": "x"}) == "trading", t

    def test_report_topics(self):
        for t in ("account-daily", "buy-list", "daily-review", "bb-squeeze",
                  "routine-synthesis", "ma-touch", "news-pulse"):
            assert discord_forward.route_topic({"topic": t, "msg": "x"}) == "reports", t

    def test_report_path_routes_to_reports(self):
        f = {"topic": "brand-new-topic", "msg": "x", "report_path": "analysis/a.md"}
        assert discord_forward.route_topic(f) == "reports"

    def test_trading_wins_over_report_path(self):
        f = {"topic": "position-watch", "msg": "x", "report_path": "analysis/a.md"}
        assert discord_forward.route_topic(f) == "trading"

    def test_system_default(self):
        for t in ("collector_health_watchdog", "wake_read", "routine-watchdog",
                  "loop_autostart", "loop_down", "baseline_heal", "margin-heal", None):
            f = {"msg": "x"} if t is None else {"topic": t, "msg": "x"}
            assert discord_forward.route_topic(f) == "system", t


# ------------------------------------------------------------------ #
# resolve_webhook_urls — per-class with DISCORD_WEBHOOK_URL fallback
# ------------------------------------------------------------------ #
class TestResolveWebhookUrls:
    def test_all_fall_back_to_base(self, tmp_path):
        urls = discord_forward.resolve_webhook_urls(
            {"DISCORD_WEBHOOK_URL": "http://base"}, tmp_path / "none.env")
        assert urls == {"trading": "http://base", "reports": "http://base",
                        "system": "http://base"}

    def test_class_override_from_env_and_file(self, tmp_path):
        envf = tmp_path / ".env"
        envf.write_text("DISCORD_WEBHOOK_URL=http://base\nDISCORD_WEBHOOK_URL_REPORTS=http://rep\n")
        urls = discord_forward.resolve_webhook_urls(
            {"DISCORD_WEBHOOK_URL_TRADING": "http://trade"}, envf)
        assert urls == {"trading": "http://trade", "reports": "http://rep",
                        "system": "http://base"}

    def test_missing_raises(self, tmp_path):
        import pytest
        with pytest.raises(RuntimeError):
            discord_forward.resolve_webhook_urls({}, tmp_path / "none.env")


# ------------------------------------------------------------------ #
# forward_entries — routing + chunk-level resume
# ------------------------------------------------------------------ #
def _fake_post(fail_at=None):
    calls = []

    def post(url, content):
        if fail_at is not None and len(calls) == fail_at:
            raise ConnectionError("boom")
        calls.append((url, content))
    return post, calls


class TestForwardEntries:
    def _multi(self):
        return [("5-0", {"topic": "account-daily", "msg": "摘要",
                         "report_path": "analysis/r.md"})]

    def test_routes_each_entry_to_its_class_url(self, monkeypatch):
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)
        post, calls = _fake_post()
        r = FakeRedis2([("1-0", {"topic": "gex-regime", "msg": "a"}),
                        ("2-0", {"topic": "buy-list", "msg": "b"}),
                        ("3-0", {"topic": "wake_read", "msg": "c"})])
        n = discord_forward.forward_entries(r, r.entries, URLS, post=post, sleep=lambda s: None)
        assert n == 3
        assert [u for u, _ in calls] == ["http://trading", "http://reports", "http://system"]
        assert r.kv["discord:forward:last_id"] == "3-0"

    def test_partial_progress_persisted_and_resumed(self, monkeypatch):
        big = "\n".join("row %04d" % i for i in range(1200))
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: big)
        r = FakeRedis2(self._multi())
        total = len(build_report_messages(r.entries[0][1], big))
        assert total >= 4
        post, calls = _fake_post(fail_at=2)
        import pytest
        with pytest.raises(ConnectionError):
            discord_forward.forward_entries(r, r.entries, URLS, post=post, sleep=lambda s: None)
        assert r.kv["discord:forward:partial"] == "5-0:2"
        assert r.kv["discord:forward:last_id"] == "0-0"        # cursor not advanced
        post2, calls2 = _fake_post()
        discord_forward.forward_entries(r, r.entries, URLS, post=post2, sleep=lambda s: None)
        expected = build_report_messages(r.entries[0][1], big)
        assert [c for _, c in calls2] == expected[2:]           # resumed at chunk 3
        assert r.kv["discord:forward:last_id"] == "5-0"
        assert "discord:forward:partial" not in r.kv           # cleared on completion

    def test_stale_partial_for_other_entry_ignored(self, monkeypatch):
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)
        r = FakeRedis2([("7-0", {"topic": "t", "msg": "x"})])
        r.kv["discord:forward:partial"] = "6-0:3"
        post, calls = _fake_post()
        discord_forward.forward_entries(r, r.entries, URLS, post=post, sleep=lambda s: None)
        assert [c for _, c in calls] == ["**[t]** x"]
        assert "discord:forward:partial" not in r.kv

    def test_blocked_topic_advances_cursor_without_post(self, monkeypatch):
        post, calls = _fake_post()
        r = FakeRedis2([("1-0", {"topic": "wakegate", "msg": "ping"})])
        discord_forward.forward_entries(r, r.entries, URLS, post=post, sleep=lambda s: None)
        assert calls == []
        assert r.kv["discord:forward:last_id"] == "1-0"

    def test_limiter_acquired_per_message(self, monkeypatch):
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)
        acquired = []

        class L:
            def acquire(self):
                acquired.append(1)
        post, calls = _fake_post()
        r = FakeRedis2([("1-0", {"topic": "t", "msg": "a"}), ("2-0", {"topic": "t", "msg": "b"})])
        discord_forward.forward_entries(r, r.entries, URLS, post=post, sleep=lambda s: None,
                                        limiter=L())
        assert len(acquired) == 2


# ------------------------------------------------------------------ #
# RateLimiter — sliding per-minute budget
# ------------------------------------------------------------------ #
class TestRateLimiter:
    def test_blocks_when_window_full(self):
        now = [0.0]
        slept = []

        def sleep(s):
            slept.append(s)
            now[0] += s
        lim = discord_forward.RateLimiter(3, 60.0, clock=lambda: now[0], sleep=sleep)
        for _ in range(3):
            lim.acquire()
        assert slept == []
        lim.acquire()                       # 4th within the window → wait until slot frees
        assert slept and abs(sum(slept) - 60.0) < 1e-6


# ------------------------------------------------------------------ #
# ForwardHealth — fail streak + single macOS alert per streak
# ------------------------------------------------------------------ #
class TestForwardHealth:
    def _h(self, now):
        notes = []
        h = discord_forward.ForwardHealth(clock=lambda: now[0],
                                          notify=lambda title, msg: notes.append(msg))
        return h, notes

    def test_alert_once_at_streak_3(self):
        now = [1000.0]
        h, notes = self._h(now)
        for i in range(6):
            now[0] += 1
            h.record_fail(RuntimeError("dns %d" % i))
        assert len(notes) == 1
        assert h.fail_streak == 6

    def test_alert_when_failing_over_5min_even_if_streak_low(self):
        now = [1000.0]
        h, notes = self._h(now)
        h.record_fail(RuntimeError("a"))
        now[0] += 301
        h.record_fail(RuntimeError("b"))
        assert len(notes) == 1

    def test_recovery_clears_and_rearms(self):
        now = [1000.0]
        h, notes = self._h(now)
        for _ in range(3):
            h.record_fail(RuntimeError("x"))
        h.record_ok()
        assert h.fail_streak == 0
        for _ in range(3):
            h.record_fail(RuntimeError("y"))
        assert len(notes) == 2

    def test_snapshot_written_to_redis(self):
        now = [1_791_273_000.0]
        h, _ = self._h(now)
        h.record_fail(RuntimeError("Timeout reading from socket"))
        r = FakeRedis2([])
        h.write(r)
        snap = r.hashes["discord:forward:health"]
        for k in ("status", "fail_streak", "last_ok_ts", "last_err", "last_err_ts",
                  "heartbeat_ts"):
            assert k in snap, k
        assert snap["status"] == "failing"
        assert snap["fail_streak"] == "1"
        assert "Timeout" in snap["last_err"]


# ------------------------------------------------------------------ #
# daemon loop
# ------------------------------------------------------------------ #
class TestDaemon:
    def test_step_forwards_new_entries_via_xread_block(self, monkeypatch):
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)
        post, calls = _fake_post()
        r = FakeRedis2([("1-0", {"topic": "gex-regime", "msg": "zg"})])
        n = discord_forward.daemon_step(r, URLS, block_ms=5000, post=post,
                                        sleep=lambda s: None)
        assert n == 1
        assert r.xread_calls[0][2] == 5000
        assert r.xread_calls[0][0] == {"claude:inbox": "0-0"}
        assert calls == [("http://trading", "**[gex-regime]** zg")]
        assert r.kv["discord:forward:last_id"] == "1-0"

    def test_step_initializes_cursor_without_backfill(self):
        post, calls = _fake_post()
        r = FakeRedis2([("1-0", {"topic": "t", "msg": "old"})], cursor=None)
        assert discord_forward.daemon_step(r, URLS, post=post, sleep=lambda s: None) == 0
        assert r.kv["discord:forward:last_id"] == "1-0"
        assert calls == []

    def test_run_daemon_survives_errors_and_keeps_cursor(self, monkeypatch):
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)
        post, calls = _fake_post()
        r = FakeRedis2([("1-0", {"topic": "position-watch", "msg": "p"})])
        r.fail_next = 3
        notes = []
        health = discord_forward.ForwardHealth(clock=lambda: 0.0,
                                               notify=lambda t, m: notes.append(m))
        slept = []
        discord_forward.run_daemon(lambda: r, URLS, health=health, post=post,
                                   sleep=slept.append, max_iterations=4)
        assert len(notes) == 1                         # alerted once during the streak
        assert calls == [("http://trading", "**[position-watch]** p")]
        assert r.kv["discord:forward:last_id"] == "1-0"
        assert health.fail_streak == 0                 # recovered
        assert r.hashes["discord:forward:health"]["status"] == "ok"
        assert slept and max(slept) <= 60

    def test_run_daemon_reconnects_when_factory_fails(self, monkeypatch):
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)
        post, calls = _fake_post()
        r = FakeRedis2([("1-0", {"topic": "t", "msg": "x"})])
        attempts = []

        def factory():
            attempts.append(1)
            if len(attempts) == 1:
                raise ConnectionError("nodename nor servname provided")
            return r
        health = discord_forward.ForwardHealth(clock=lambda: 0.0, notify=lambda t, m: None)
        discord_forward.run_daemon(factory, URLS, health=health, post=post,
                                   sleep=lambda s: None, max_iterations=2)
        assert len(attempts) == 2
        assert len(calls) == 1


# ------------------------------------------------------------------ #
# Dead-letter: permanent 4xx must not block the queue (2026-10-06)
# ------------------------------------------------------------------ #
class _Resp2(_Resp):
    def __init__(self, status_code=204, text=""):
        super().__init__(status_code)
        self.text = text


class FakeRedis3(FakeRedis2):
    def __init__(self, entries, cursor="0-0"):
        super().__init__(entries, cursor)
        self.lists = {}

    def rpush(self, k, v):
        self.lists.setdefault(k, []).append(v)

    def ltrim(self, k, start, end):
        self.lists[k] = self.lists.get(k, [])[start:None if end == -1 else end + 1]


class TestPostDiscordPermanent:
    def test_non_retryable_4xx_raises_permanent(self, monkeypatch):
        import requests
        for code in (400, 401, 403, 404, 413):
            monkeypatch.setattr(requests, "post",
                                lambda url, _c=code, **kw: _Resp2(_c, "x" * 900))
            import pytest
            with pytest.raises(discord_forward.PermanentPostError) as ei:
                discord_forward.post_discord("http://x", "hello")
            assert ei.value.status == code
            assert len(ei.value.body) <= 500

    def test_5xx_is_not_permanent(self, monkeypatch):
        import requests
        import pytest
        monkeypatch.setattr(requests, "post", lambda url, **kw: _Resp2(502, "bad gateway"))
        with pytest.raises(Exception) as ei:
            discord_forward.post_discord("http://x", "hello")
        assert not isinstance(ei.value, discord_forward.PermanentPostError)


class TestDeadLetter:
    def _notifier(self):
        notes = []
        return discord_forward.DeadLetterNotifier(clock=lambda: 0.0,
                                                  notify=lambda t, m: notes.append(m)), notes

    def test_permanent_chunk_retried_once_then_dead_lettered(self, monkeypatch):
        import json
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)
        calls = []

        def post(url, content):
            calls.append(content)
            if content.endswith("bad"):
                raise discord_forward.PermanentPostError(400, '{"content":["too long"]}')
        r = FakeRedis3([("1-0", {"topic": "t", "msg": "bad"}),
                        ("2-0", {"topic": "gex-regime", "msg": "good"})])
        dn, notes = self._notifier()
        n = discord_forward.forward_entries(r, r.entries, URLS, post=post,
                                            sleep=lambda s: None, dead_notifier=dn)
        assert calls == ["**[t]** bad", "**[t]** bad", "**[gex-regime]** good"]  # 1 retry
        assert r.kv["discord:forward:last_id"] == "2-0"          # queue not blocked
        dead = [json.loads(x) for x in r.lists["discord:forward:dead"]]
        assert len(dead) == 1
        d = dead[0]
        assert d["entry_id"] == "1-0" and d["chunk"] == 0 and d["status"] == 400
        assert "too long" in d["body"] and d["ts"]
        assert len(notes) == 1
        assert n == 2

    def test_permanent_retry_success_not_dead_lettered(self, monkeypatch):
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)
        seq = [discord_forward.PermanentPostError(404, "Unknown Webhook"), None]

        def post(url, content):
            e = seq.pop(0)
            if e:
                raise e
        r = FakeRedis3([("1-0", {"topic": "t", "msg": "x"})])
        dn, notes = self._notifier()
        discord_forward.forward_entries(r, r.entries, URLS, post=post,
                                        sleep=lambda s: None, dead_notifier=dn)
        assert "discord:forward:dead" not in r.lists and notes == []
        assert r.kv["discord:forward:last_id"] == "1-0"

    def test_mid_entry_chunk_dead_lettered_and_partial_advances(self, monkeypatch):
        import json
        big = "\n".join("row %04d" % i for i in range(1200))
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: big)
        fields = {"topic": "account-daily", "msg": "摘要", "report_path": "analysis/r.md"}
        msgs = build_report_messages(fields, big)
        bad = msgs[2]
        sent = []

        def post(url, content):
            if content == bad:
                raise discord_forward.PermanentPostError(413, "too large")
            sent.append(content)
        r = FakeRedis3([("5-0", fields)])
        dn, notes = self._notifier()
        discord_forward.forward_entries(r, r.entries, URLS, post=post,
                                        sleep=lambda s: None, dead_notifier=dn)
        assert sent == msgs[:2] + msgs[3:]
        d = json.loads(r.lists["discord:forward:dead"][0])
        assert d["chunk"] == 2 and d["status"] == 413
        assert r.kv["discord:forward:last_id"] == "5-0"
        assert "discord:forward:partial" not in r.kv
        assert len(notes) == 1

    def test_one_notification_per_entry_and_throttled(self, monkeypatch):
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)

        def post(url, content):
            raise discord_forward.PermanentPostError(404, "Unknown Webhook")
        r = FakeRedis3([("%d-0" % i, {"topic": "t", "msg": "m%d" % i}) for i in range(1, 6)])
        dn, notes = self._notifier()
        discord_forward.forward_entries(r, r.entries, URLS, post=post,
                                        sleep=lambda s: None, dead_notifier=dn)
        assert len(r.lists["discord:forward:dead"]) == 5
        assert len(notes) == 1                    # deleted webhook ≠ notification storm
        assert r.kv["discord:forward:last_id"] == "5-0"

    def test_network_error_still_raises_without_dead_letter(self, monkeypatch):
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: None)
        import pytest

        def post(url, content):
            raise ConnectionError("Can't assign requested address")
        r = FakeRedis3([("1-0", {"topic": "t", "msg": "x"})])
        dn, notes = self._notifier()
        with pytest.raises(ConnectionError):
            discord_forward.forward_entries(r, r.entries, URLS, post=post,
                                            sleep=lambda s: None, dead_notifier=dn)
        assert "discord:forward:dead" not in r.lists
        assert r.kv["discord:forward:last_id"] == "0-0"


# ------------------------------------------------------------------ #
# bot identity (2026-10-06): 各頻道以對應 bot 發文,401/403 退回 webhook
# ------------------------------------------------------------------ #
class _BotResp(_Resp):
    text = ""


class TestBotTarget:
    def test_bot_target_posts_to_channel_with_bot_auth(self, monkeypatch):
        calls = []
        import requests
        monkeypatch.setattr(requests, "post",
                            lambda url, **kw: calls.append((url, kw)) or _BotResp(200))
        t = discord_forward.BotTarget("tok123", "555", "http://hook")
        discord_forward.post_discord(t, "hello")
        url, kw = calls[0]
        assert url == "https://discord.com/api/v10/channels/555/messages"
        assert kw["headers"]["Authorization"] == "Bot tok123"
        assert kw["json"]["content"] == "hello"
        assert kw["json"]["allowed_mentions"] == {"parse": []}

    def test_bot_unauthorized_falls_back_to_webhook(self, monkeypatch):
        calls = []
        seq = [_BotResp(401), _BotResp(204)]
        import requests
        monkeypatch.setattr(requests, "post", lambda url, **kw: calls.append(url) or seq.pop(0))
        t = discord_forward.BotTarget("revoked", "555", "http://hook")
        discord_forward.post_discord(t, "hello")
        assert calls == ["https://discord.com/api/v10/channels/555/messages", "http://hook"]

    def test_bot_unauthorized_without_fallback_is_permanent(self, monkeypatch):
        import pytest
        import requests
        monkeypatch.setattr(requests, "post", lambda url, **kw: _BotResp(403))
        with pytest.raises(discord_forward.PermanentPostError):
            discord_forward.post_discord(discord_forward.BotTarget("t", "555", ""), "x")

    def test_bot_target_repr_hides_token(self):
        assert "secret" not in repr(discord_forward.BotTarget("secret", "555", "http://hook"))


class TestResolveTargets:
    def test_bot_where_configured_else_webhook(self, tmp_path):
        env = {
            "DISCORD_WEBHOOK_URL": "http://base",
            "DISCORD_WEBHOOK_URL_TRADING": "http://trade",
            "DISCORD_BOT_TOKEN_GUYU": "guyu-tok", "DISCORD_CHANNEL_ID_TRADING": "111",
            "DISCORD_BOT_TOKEN_GULI": "guli-tok",          # 缺 channel id → 不啟用
        }
        t = discord_forward.resolve_targets(env, tmp_path / "none.env")
        assert t["trading"] == discord_forward.BotTarget("guyu-tok", "111", "http://trade")
        assert t["reports"] == "http://base"
        assert t["system"] == "http://base"
