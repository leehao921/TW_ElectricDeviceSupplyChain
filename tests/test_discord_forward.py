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
    format_entry,
    parse_env_file,
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
        assert msgs == [(c, False) for c in chunk_message(format_entry(self.FIELDS))]

    def test_short_report_summary_then_body_with_attach(self):
        msgs = build_report_messages(self.FIELDS, "# 報告\n完整內容")
        assert len(msgs) == 2
        assert msgs[0] == (format_entry(self.FIELDS), False)
        assert msgs[1] == ("# 報告\n完整內容", True)

    def test_long_report_chunked_attach_only_last(self):
        report = "\n".join("row %04d" % i for i in range(1200))  # ~10KB
        msgs = build_report_messages(self.FIELDS, report)
        assert len(msgs) >= 4
        assert all(len(c) <= 2000 for c, _ in msgs)
        assert [a for _, a in msgs] == [False] * (len(msgs) - 1) + [True]

    def test_containment_dedup_skips_body(self):
        # bb-followthrough 情境: msg 即報告全文 → 不重複切段,附件掛摘要尾
        digest = "**BB 追蹤**\n多行報告內容\n第三行"
        fields = {"topic": "bb-followthrough", "msg": digest}
        msgs = build_report_messages(fields, digest + "\n")
        assert msgs == [(format_entry(fields), True)]

    def test_over_cap_replaced_by_notice(self):
        report = "\n".join("row %05d" % i for i in range(6000))  # 遠超 15 段
        msgs = build_report_messages(self.FIELDS, report, max_report_chunks=15)
        assert len(msgs) == 2
        assert "見附件" in msgs[1][0]
        assert msgs[1][1] is True

    def test_long_summary_chunked_attach_still_last(self):
        fields = {"topic": "t", "msg": "\n".join("s %04d" % i for i in range(400))}
        msgs = build_report_messages(fields, "short body")
        assert sum(1 for _, a in msgs if a) == 1
        assert msgs[-1][1] is True

    def test_empty_report_text_treated_as_none(self):
        msgs = build_report_messages(self.FIELDS, "")
        assert all(a is False for _, a in msgs)


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

    def test_attachment_uses_multipart(self, monkeypatch):
        calls = []
        import requests
        monkeypatch.setattr(requests, "post", lambda url, **kw: calls.append(kw) or _Resp())
        discord_forward.post_discord("http://x", "hi", attachment=("r.md", b"data"))
        kw = calls[0]
        assert "json" not in kw
        assert kw["files"]["files[0]"] == ("r.md", b"data")
        import json as _json
        assert _json.loads(kw["data"]["payload_json"])["content"] == "hi"

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

    def xrange(self, stream, lo, hi, count=None):
        lo_id = lo.lstrip("(")
        out = [(i, f) for i, f in self.entries if i > lo_id]
        return out[:count] if count else out

    def xrevrange(self, stream, hi, lo, count=None):
        return list(reversed(self.entries))[:count]


class TestRunOnce:
    def _patch(self, monkeypatch, load_ret=(None, None)):
        sent = []
        monkeypatch.setattr(discord_forward, "post_discord",
                            lambda url, content, attachment=None: sent.append((content, attachment)))
        monkeypatch.setattr(discord_forward, "load_report", lambda raw: load_ret)
        monkeypatch.setattr(discord_forward.time, "sleep", lambda s: None)
        return sent

    def test_report_entry_sends_summary_body_attachment(self, monkeypatch):
        sent = self._patch(monkeypatch, load_ret=("# 報告\n內容", ("r.md", b"x")))
        r = FakeRedis([("1-0", {"topic": "t", "msg": "摘要", "report_path": "analysis/r.md"})])
        n = discord_forward.run_once(r, "http://x")
        assert n == 1
        assert len(sent) == 2
        assert sent[0] == ("**[t]** 摘要", None)
        assert sent[1] == ("# 報告\n內容", ("r.md", b"x"))
        assert r.kv["discord:forward:last_id"] == "1-0"

    def test_bogus_report_path_falls_back_to_summary(self, monkeypatch):
        sent = self._patch(monkeypatch, load_ret=(None, None))
        r = FakeRedis([("1-0", {"topic": "t", "msg": "摘要", "report_path": "analysis/nope.md"})])
        assert discord_forward.run_once(r, "http://x") == 1
        assert sent == [("**[t]** 摘要", None)]
        assert r.kv["discord:forward:last_id"] == "1-0"

    def test_old_format_entry_unchanged(self, monkeypatch):
        sent = self._patch(monkeypatch)
        r = FakeRedis([("1-0", {"topic": "t", "msg": "普通訊息"})])
        assert discord_forward.run_once(r, "http://x") == 1
        assert sent == [("**[t]** 普通訊息", None)]

    def test_budget_defers_entry_to_next_run(self, monkeypatch):
        big = "\n".join("row %04d" % i for i in range(1200))  # ~10KB → 摘要+多段
        sent = self._patch(monkeypatch, load_ret=(big, ("r.md", b"x")))
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
        huge = "x" * 60000  # 硬切 >25 段 → cap 後仍是 摘要+提示,但驗證單 entry 超算照送
        monkeypatch.setattr(discord_forward, "MAX_MSGS_PER_RUN", 1)
        sent = self._patch(monkeypatch, load_ret=(huge, ("r.md", b"x")))
        r = FakeRedis([("1-0", {"topic": "t", "msg": "摘要", "report_path": "analysis/r.md"})])
        assert discord_forward.run_once(r, "http://x") == 1
        assert len(sent) >= 2
        assert r.kv["discord:forward:last_id"] == "1-0"

    def test_multipart_failure_degrades_to_plain(self, monkeypatch):
        sent = []

        def flaky_post(url, content, attachment=None):
            if attachment is not None:
                raise RuntimeError("multipart boom")
            sent.append((content, attachment))

        monkeypatch.setattr(discord_forward, "post_discord", flaky_post)
        monkeypatch.setattr(discord_forward, "load_report",
                            lambda raw: ("body", ("r.md", b"x")))
        monkeypatch.setattr(discord_forward.time, "sleep", lambda s: None)
        r = FakeRedis([("1-0", {"topic": "t", "msg": "摘要", "report_path": "analysis/r.md"})])
        assert discord_forward.run_once(r, "http://x") == 1
        assert ("body", None) in sent                    # 降級純文字
        assert r.kv["discord:forward:last_id"] == "1-0"
