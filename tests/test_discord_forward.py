"""Tests for scripts/discord_forward.py — claude:inbox → Discord webhook forwarder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from discord_forward import (  # noqa: E402
    TOPIC_BLOCKLIST,
    chunk_message,
    format_entry,
    parse_env_file,
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
