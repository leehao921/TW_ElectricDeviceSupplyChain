#!/usr/bin/env python3
"""Print session-boot summary: inbox + active projects + user preferences + recent log.

Claude Code reads this output at session start. Quick to run (<1s).

Usage:
    python3 scripts/vault_session_boot.py
    python3 scripts/vault_session_boot.py --rebuild-index   # also rebuild vault/index.md
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytz

TPE = pytz.timezone("Asia/Taipei")
REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT = REPO_ROOT / "vault"


def banner(label: str, char: str = "=") -> None:
    print(char * 60)
    print(label)
    print(char * 60)


def section(label: str) -> None:
    print(f"\n## {label}\n")


def strip_frontmatter(text: str) -> str:
    """Drop the leading `--- ... ---` YAML block (vault page metadata)."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")


def print_file(path: Path, max_chars: int = 2500, head: int | None = None) -> None:
    if not path.exists():
        print(f"(missing: {path.relative_to(REPO_ROOT)})")
        return
    text = strip_frontmatter(path.read_text())
    if head:
        text = "\n".join(text.splitlines()[:head])
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated, see {path.relative_to(REPO_ROOT)} for full]"
    print(text)


def run_claude_msg_read() -> None:
    """Call claude_msg.py read --no-mark so boot doesn't consume the cursor."""
    script = REPO_ROOT / "scripts" / "claude_msg.py"
    if not script.exists():
        print("(claude_msg.py not found)")
        return
    try:
        proc = subprocess.run(
            ["python3", str(script), "read", "--no-mark", "--limit", "20"],
            capture_output=True, text=True, timeout=5
        )
        print(proc.stdout.rstrip() or "(no recent msgs)")
        if proc.returncode != 0:
            print(f"[claude_msg.py exit {proc.returncode}] {proc.stderr.strip()[:200]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("[claude_msg.py timed out — is Redis up?]", file=sys.stderr)


def recent_log_entries(n: int = 8) -> None:
    log_path = VAULT / "log.md"
    if not log_path.exists():
        print("(log.md missing)")
        return
    entries = [line for line in log_path.read_text().splitlines() if line.startswith("## [")]
    for line in entries[-n:]:
        print(line)


def latest_inbox_dump() -> None:
    inbox_dir = VAULT / "inbox"
    if not inbox_dir.exists():
        print("(inbox/ missing)")
        return
    files = sorted(inbox_dir.glob("*.md"), reverse=True)
    if not files:
        print("(no inbox dumps yet)")
        return
    latest = files[0]
    print(f"latest dump: {latest.relative_to(REPO_ROOT)} ({latest.stat().st_size} bytes)")


def rebuild_index() -> None:
    """Scan vault/ and rebuild vault/index.md catalog. Currently a stub — full impl in vault_lint.py."""
    print("(rebuild-index: stub — use scripts/vault_lint.py --rebuild-index for full impl)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--rebuild-index", action="store_true")
    p.add_argument("--brief", action="store_true", help="compact mode (no full file dumps)")
    args = p.parse_args()

    now = datetime.now(TPE)
    banner(f"Claude session boot · {now.strftime('%Y-%m-%d %H:%M %Z (%A)')}")

    section("Cross-session inbox (claude:inbox, last 20)")
    run_claude_msg_read()

    section("Active projects")
    print_file(VAULT / "projects" / "active.md", max_chars=3000 if not args.brief else 1500)

    section("User preferences (style + rules) — FULL")
    # Preferences must NOT truncate — HARD rules are load-bearing
    print_file(VAULT / "user" / "preferences.md", max_chars=10_000)

    section("Open trading positions")
    print_file(VAULT / "trading" / "positions.md", max_chars=2000 if not args.brief else 1000)

    section("Recent vault activity (last 8 log entries)")
    recent_log_entries(8)

    section("Latest inbox dump")
    latest_inbox_dump()

    print()
    banner("Boot complete — proceed with user task", char="-")

    if args.rebuild_index:
        rebuild_index()

    return 0


if __name__ == "__main__":
    sys.exit(main())
