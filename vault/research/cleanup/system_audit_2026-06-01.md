---
type: research
status: draft
last_updated: 2026-06-01
source_unit: 15
tags: [cleanup, plans, worktrees, system]
---

# Unit 15: Stale Plans + Worktrees + System Audit

## TL;DR — total cleanup possible

| Bucket | Found | Safe to clean | Notes |
|---|---|---|---|
| Stale plans in `~/.claude/plans/` | **14** files (spec said 11; 3 extra) | **13** can be archived/deleted | Keep `lovely-sparking-dijkstra.md` (today's `/batch` repo-cleanup plan). All others are completed work or belong to sibling repos (nautilus-shioaji / database). |
| Git worktrees | **21** worktrees (spec said 15; 6 extra) | **19** clean + landed → safe to prune. **2 dirty** → need rescue review. | All worktrees match prefix `agent-a*`. PR #23 squash-merged 008004 work; PRs #1-9 merged Unit 1-9 work via merge-commits. |
| `/tmp/` leftover | 2 enrichment JSON files | both safe — already merged into reports | `/tmp/enrichment_008004.json` (16 KB), `/tmp/enrichment_2313.json` (4 KB). |
| Memory files | 10 markdown files (informational) | **DO NOT TOUCH** | Per spec; listed below for record only. |

**Recommended coordinator actions (NOT executed by this unit):**
1. Delete 13 stale plan `.md` files (keep `lovely-sparking-dijkstra.md`).
2. Prune 19 clean worktrees + their `worktree-agent-*` branches.
3. **First** inspect 2 dirty worktrees: `agent-a894c02106ec80af8` (untracked `vault/`) and `agent-ad11a5d2` (modified `requirements.txt` + untracked `ingestion/`). These two share the same HEAD `396b8da` ("README: add Token Usage & Cost Guide") and look like abandoned scratchpads, but rescue check is required before prune.
4. Remove 2 `/tmp` enrichment files after confirming reports merged.

---

## Stale plans (14 個 — spec said 11)

| Plan file | 修改日 | One-line 摘要 | 建議 |
|---|---|---|---|
| `lovely-sparking-dijkstra.md` | 2026-06-01 13:16 | 今天 `/batch` 整理 repo 4 維度並行清理 plan (worktrees + stale branches + untracked + plans). | **KEEP** (active) |
| `tender-sparking-fern.md` | 2026-06-01 12:22 | 圖文並茂 PDF 資料庫工作流程報告 (Kenji team call demo)。屬於 knowledge-platform / ZES 90-day BD plan，非本 repo。 | DELETE (sibling repo) |
| `lexical-wobbling-riddle.md` | 2026-06-01 12:04 | Fix TAIEX baseline pipeline — `h:taiex:baseline`/`h:taiex:live` 空。屬於 database / nautilus-shioaji。 | DELETE (sibling repo) |
| `iterative-finding-lemur.md` | 2026-06-01 11:29 | Reverse-reflect Ingest SOP §A into `docs/crm-usage-guide.md`。屬於 knowledge-platform。 | DELETE (sibling repo) |
| `reflective-weaving-aho.md` | 2026-05-31 21:42 | Redo failing tests in `database` repo (24 collection errors, 6 clusters, out of CI scope)。屬於 database。 | DELETE (sibling repo) |
| `cozy-seeking-badger.md` | 2026-05-31 17:38 | Install + load `master_orchestrator` + `reward-snapshot` launchd daemons (nautilus-shioaji `feat/p4-handler-exploration-tuning`)。 | DELETE (sibling repo) |
| `hidden-hopping-steele.md` | 2026-05-28 10:01 | Fix all-zero stock OFI (multi-TF field mismatch + mis-scaled sigmoid)。屬於 database。 | DELETE (sibling repo) |
| `sparkling-humming-puddle.md` | 2026-05-27 12:32 | ZES (Zero-Error Systems) vendor profile + datasheet ingest。屬於 knowledge-platform。 | DELETE (sibling repo) |
| `sequential-brewing-tiger.md` | 2026-05-14 13:49 | Provenance integrity + Knowledge Architecture wiki (two PRs)。屬於 knowledge-platform。 | DELETE (sibling repo) |
| `vivid-questing-conway.md` | 2026-05-14 09:43 | trading-redis 不該無限長大 — OOM 救火 + 找根因 (v3)。屬於 database / trading-timescaledb。 | DELETE (sibling repo) |
| `velvety-humming-wave.md` | 2026-05-14 09:32 | Free-Path Quality + Robustness Iteration on Local Ollama (qwen2.5:7b edge quality)。屬於 knowledge-platform。 | DELETE (sibling repo) |
| `declarative-humming-codd.md` | 2026-05-11 22:54 | Fix MCP_DOCKER catalog & rerun `/mcp-discover`。屬於 global MCP config，已完成。 | DELETE (completed) |
| `go-frolicking-panda.md` | 2026-05-05 14:19 | Fix PR #71 Code Review Issues (range-regime detector etc.)。屬於 nautilus-shioaji。 | DELETE (sibling repo) |
| `merry-snuggling-lampson.md` | 2026-05-05 13:08 | Milestone v1.0 Bullish-Aware Trading System (10 issues, ~10 days)。屬於 nautilus-shioaji milestone。 | DELETE (sibling repo) |

**Total to delete:** 13 plans. None of the 13 are for the My-TW-Coverage repo; they all belong to sibling repos (`nautilus-shioaji`, `database`, `knowledge-platform`) or are completed global config tasks. Best home for them long-term is each sibling repo's own `docs/plans/` per global standards, but for **today's** `/batch` cleanup they can be removed from `~/.claude/plans/` (a working-scratch directory).

---

## 21 Worktrees status (spec said 15)

Sorted by branch name. `landed` column: YES = HEAD commit is direct master ancestor OR content landed via squash-merge PR.

| Worktree | HEAD | Branch / topic | Clean? | Landed? | 建議 |
|---|---|---|---|---|---|
| `agent-a1d556d805b688043` | `0625841` | 008004 unit 4 — TW upstream materials | YES | YES (via PR #23 squash) | PRUNE |
| `agent-a1fc6b6c` | `a19053f` | Unit 4 RSS collectors (CNA/UDN/CTEE) | YES | YES (PR #3 merge) | PRUNE |
| `agent-a38c159ae48227acb` | `baf51ad` | 008004 unit 1 — spec and global leaders | YES | YES (PR #23) | PRUNE |
| `agent-a414e43e83a32e9bc` | `32d4561` | 008004 unit 6 — downstream takeaway risks | YES | YES (PR #23) | PRUNE |
| `agent-a5d5d75b` | `c653c70` | Unit 7 MCP research server | YES | YES (PR #7) | PRUNE |
| `agent-a65d2ad592230bf1d` | `d17b4d7` | 008004 unit 8 — upstream deep verification | YES | YES (PR #23) | PRUNE |
| `agent-a85d1081081a381cc` | `a75c3f9` | 008004 unit 5 — TW distributors 3090 8043 | YES | YES (PR #23) | PRUNE |
| `agent-a894c02106ec80af8` | `396b8da` | README Token Usage & Cost Guide | **NO** (untracked `vault/`) | YES (HEAD is master ancestor) | **RESCUE NEEDED** — inspect untracked `vault/` for unsaved work before prune |
| `agent-a8e9c13fb3f3fecce` | `1df3890` | 008004 unit 3 — TW niche 3026 6173 | YES | YES (PR #23) | PRUNE |
| `agent-a92d8197` | `951a05c` | Unit 6 Graph layer (Graphiti + bootstrap) | YES | YES (PR #8) | PRUNE |
| `agent-a9bcb510` | `9fd825b` | Unit 5 Search + fundamentals collectors | YES | YES (PR #6) | PRUNE |
| `agent-ab417b2aad0fa9e85` | `1830db5` | 008004 unit 9 — hidden candidate companies | YES | YES (PR #23) | PRUNE |
| `agent-ab41c4080d9078f00` | `d961d56` | 008004 unit 10 — 2327/2492 R&D pipeline | YES | YES (PR #23) | PRUNE |
| `agent-ad11a5d2` | `396b8da` | README Token Usage & Cost Guide | **NO** (` M requirements.txt`, `?? ingestion/`) | YES (HEAD is master ancestor) | **RESCUE NEEDED** — `requirements.txt` diff + untracked `ingestion/` may contain unsaved work. Inspect before prune. |
| `agent-ad4d6a54` | `0280947` | Unit 2 Ingestion shared infrastructure | YES | YES (PR #1) | PRUNE |
| `agent-ada329c3a7482c953` | `396b8da` | README Token Usage & Cost Guide | YES | YES (HEAD is master ancestor) | PRUNE |
| `agent-ae109e11d334e93ea` | `396b8da` | README Token Usage & Cost Guide | YES | YES (HEAD is master ancestor) | PRUNE |
| `agent-ae20fc9258c834963` | `41ecdb1` | 008004 unit 7 — distributors deep verification | YES | YES (PR #23) | PRUNE |
| `agent-aec80f143193ecc64` | `db6ba62` | 008004 unit 2 — TW mid 2327 2492 | YES | YES (PR #23) | PRUNE |
| `agent-af7cd7ab43b8a9f49` | `396b8da` | (this unit 15 worktree) — README Token Usage & Cost Guide | YES* | YES (HEAD is master ancestor) | KEEP UNTIL THIS UNIT COMMITS, then PRUNE |
| `agent-afab1402` | `d148723` | Unit 3 MOPS 重大訊息 collector | YES | YES (PR #5) | PRUNE |

*This worktree will become dirty briefly while unit 15 commits its report; after commit it returns to clean.

### Cross-check vs spec assumptions

- Spec said **PR #23 packs unit 1-6 + 7-11** — confirmed via `gh pr list`. PR #23 ("research(MLCC): add 008004 batch") was MERGED 2026-06-01 01:57 UTC and the merge-commit `2b440cd` in master touches `Pilot_Reports/Communication Equipment/2313_華通.md`, `themes/MLCC.md`, `vault/concepts/MLCC_008004*.md`, etc. → All 008004-research worktrees (a1d556d, a38c159, a414e43, a65d2ad, a85d108, a8e9c13, ab417b2, ab41c40, ae20fc9, aec80f1) are content-landed.
- Spec said PRs #1-9 (Unit 1-9) merged — confirmed via 9 `Merge pull request #N` commits in master log. Worktrees `agent-a1fc6b6c`, `agent-a5d5d75b`, `agent-a92d8197`, `agent-a9bcb510`, `agent-ad4d6a54`, `agent-afab1402` are content-landed.
- **No worktree contains UN-landed work that needs cherry-pick.** Only the 2 dirty worktrees may have unsaved scratch in untracked directories.

---

## /tmp leftover

| Path | Size | Source | 建議 |
|---|---|---|---|
| `/tmp/enrichment_008004.json` | 16 KB | `/update-enrichment 008004` run on 2026-06-01 09:59 | DELETE (content already merged into `Pilot_Reports/.../008004*.md` via PR #23) |
| `/tmp/enrichment_2313.json` | 4 KB | `/update-enrichment 2313` run on 2026-06-01 10:30 | DELETE (content already merged into `Pilot_Reports/Communication Equipment/2313_華通.md` via PR #23) |
| `/tmp/claude-settings-91d44609dbe0b2d6.json` | 4 KB | Claude Code session settings cache | LEAVE (managed by Claude Code) |
| `/tmp/claude-501` | 536 KB | Claude Code per-user runtime dir | LEAVE (managed by Claude Code) |
| `/tmp/claude-mcp-browser-bridge-lulala` | 0 B | MCP browser bridge socket dir | LEAVE (managed by Chrome MCP) |
| `/tmp/backup_reports.launchd.{err,log}` | 0 B | launchd backup daemon logs | LEAVE (managed by launchd) |

**No `/tmp/008004*` or `/tmp/cleanup*` files found** — those glob patterns in the spec returned `no matches`.

---

## Memory files (informational — DO NOT TOUCH)

Path: `/Users/lulala/.claude/projects/-Users-lulala-Documents-coding-My-TW-Coverage/memory/`

```
MEMORY.md
feedback_date_accuracy.md
feedback_no_duplicate_infra.md
feedback_quant_claim_verification.md
feedback_session_boot_protocol.md
feedback_vault_maintenance.md
feedback_verify_live_state.md
reference_cross_session_inbox.md
reference_tmf_trading_stack.md
reference_vault_index.md
```

10 files total. All 6 `feedback_*` are user-correction memories; all 3 `reference_*` are stable infrastructure notes; `MEMORY.md` is the index. Per spec, **not touched**.

---

## 統整 cleanup actions (for coordinator — NOT executed here)

1. **Plans:** `rm` 13 stale plans under `~/.claude/plans/` (keep `lovely-sparking-dijkstra.md`). Consider relocating sibling-repo plans to their respective `docs/plans/` first per global devops SOP — but they are duplicates of work already done, so simple delete is acceptable.
2. **Worktrees:**
   - **First, rescue check 2 dirty worktrees:**
     - `agent-a894c02106ec80af8` — `cd` in and inspect untracked `vault/` directory; if it contains unsaved research, copy out before prune.
     - `agent-ad11a5d2` — `git diff requirements.txt` (may be a stale dependency change) and inspect untracked `ingestion/` directory.
   - **Then `git worktree prune` 19 clean worktrees + `git branch -D` their `worktree-agent-*` branches.** The current unit-15 worktree (`agent-af7cd7ab43b8a9f49`) should be pruned last, after this unit's commit lands and coordinator exits it.
3. **/tmp:** `rm /tmp/enrichment_008004.json /tmp/enrichment_2313.json`.
4. **Memory files:** no action.

---

## Sources

- `ls -lt /Users/lulala/.claude/plans/` (14 files, 2026-05-05 → 2026-06-01)
- `head -8` on each plan file for one-line summary classification
- `git worktree list` (21 worktrees, all locked)
- Per-worktree `git status --short` + `git rev-parse HEAD` + `git merge-base --is-ancestor HEAD master`
- `git log --oneline master` (top 20) — confirmed PR #23 squash-merge commit `2b440cd` and PR #1-9 merge commits
- `gh pr list --state all --limit 30` — confirmed PRs #1-9 MERGED, PR #23 MERGED, PR #22 OPEN (not related to worktrees)
- `git show --stat 2b440cd` — confirmed PR #23 touches the files the 008004 worktrees produced
- `ls -la /tmp/` filtered to `enrichment|008004|cleanup|claude|repo`
- `ls ~/.claude/projects/-Users-lulala-Documents-coding-My-TW-Coverage/memory/`
