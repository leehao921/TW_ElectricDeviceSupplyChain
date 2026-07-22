#!/usr/bin/env python3
"""daily_synthesis.py — 每交易日 15:50 由 launchd (com.lulala.daily-synthesis) 觸發。

用 headless Claude 讀當日全部 routine 輸出，產跨 routine 綜合分析：
  analysis/routine_synthesis_<date>.md + claude:inbox topic=routine-synthesis + macOS 通知。

launchd 必須以 .venv/bin/python 直接執行本檔（不能經 /bin/bash — bash 無
~/Documents 的 TCC 授權，會 Operation not permitted / exit 126）。
手動補跑: python3 scripts/daily_synthesis.py
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path("/Users/lulala/Documents/coding/My-TW-Coverage")
CLAUDE_BIN = "/opt/homebrew/bin/claude"
PROMPT_FILE = REPO / "scripts" / "daily_synthesis_prompt.md"


def log(msg: str) -> None:
    print(f"[{datetime.now():%F %T}] {msg}", flush=True)


def main() -> int:
    log("daily_synthesis start")
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    r = subprocess.run(
        [CLAUDE_BIN, "-p", prompt,
         "--allowedTools", "Read,Glob,Grep,Write,Bash",
         "--max-turns", "60"],
        cwd=REPO, text=True, capture_output=True, timeout=1800,
    )
    if r.stdout:
        print(r.stdout, flush=True)
    if r.stderr:
        print(r.stderr, file=sys.stderr, flush=True)
    log(f"daily_synthesis done rc={r.returncode}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
