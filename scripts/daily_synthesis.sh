#!/bin/bash
# daily_synthesis.sh — 每交易日 15:50 由 launchd (com.lulala.daily-synthesis) 觸發。
# 用 headless Claude 讀當日全部 routine 輸出，產跨 routine 綜合分析：
#   analysis/routine_synthesis_<date>.md + claude:inbox topic=routine-synthesis + macOS 通知。
# 手動補跑: bash scripts/daily_synthesis.sh
set -uo pipefail

REPO=/Users/lulala/Documents/coding/My-TW-Coverage
CLAUDE_BIN=/opt/homebrew/bin/claude
PROMPT_FILE="$REPO/scripts/daily_synthesis_prompt.md"

cd "$REPO" || exit 1
echo "[$(date '+%F %T')] daily_synthesis start"

"$CLAUDE_BIN" -p "$(cat "$PROMPT_FILE")" \
  --allowedTools "Read,Glob,Grep,Write,Bash" \
  --max-turns 60 2>&1
rc=$?

echo "[$(date '+%F %T')] daily_synthesis done rc=$rc"
exit $rc
