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
