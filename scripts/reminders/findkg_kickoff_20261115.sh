#!/bin/bash
# 一次性提醒: 2026-11-15 開始執行 FinDKG 路線 (analysis/findkg_gap_analysis_20261030.md)
# 發出後寫 marker + 自我 bootout, 避免明年同日重發
set -u
MARKER="$HOME/Library/Logs/reminder-findkg-20261115.done"
[ -f "$MARKER" ] && exit 0
[ "$(date +%Y%m%d)" -lt 20261115 ] && exit 0

MSG='⏰ 計畫提醒: 今天 (11/15) 開始執行 FinDKG 路線 P1。
先決定 2 件事: (1) 關係 schema 是否用 6 種 (供應給/客戶為/採用技術/使用材料/競爭/屬於族群) (2) 存 Postgres tw_electronics 還是 Graphiti 另開 tw-electronics group。
另: 是否先回補 MOPS 重訊歷史 (P4 前提)。
文件: analysis/findkg_gap_analysis_20261030.md — 開新 session 說「開始 FinDKG P1」即可。'

/opt/homebrew/bin/redis-cli XADD claude:inbox '*' \
  ts "$(date -Iseconds)" from reminder topic plan-reminder tags "findkg,reminder" \
  as_of "$(date +%Y-%m-%d)" msg "$MSG" report_path analysis/findkg_gap_analysis_20261030.md \
  && touch "$MARKER" \
  && launchctl bootout "gui/$(id -u)/com.lulala.reminder-findkg-20261115" 2>/dev/null
