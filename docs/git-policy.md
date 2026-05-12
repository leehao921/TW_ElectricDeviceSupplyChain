# Git Policy — TW-Coverage

Conventions for what enters this repository, how commits are written, and how the 926-ticker coverage corpus stays clean over time. **All contributors (human and AI) must follow this.**

---

## 1. What This Repo Tracks (and Why)

This repo is a **research-data + tooling** repo, not a typical software project. The asset hierarchy:

| Tier | Contents | Why it's tracked |
|---|---|---|
| **Tier 1 — Research corpus** | `Pilot_Reports/**/*.md`, `WIKILINKS.md`, `themes/`, `screens/`, `task.md` | The product. 926 ticker reports + cross-reference graph. Every change must preserve research quality (see CLAUDE.md). |
| **Tier 2 — Production code** | `scripts/*.py`, `scripts/generators/`, `analysis/*.py` | Pipelines that generate, refresh, and audit Tier 1. Treated as production. |
| **Tier 3 — Analysis evidence** | `analysis/reports/*.md`, `analysis/reports/*.json`, `analysis/reports/talks/*.md` | Written research output (market views, backtests, deep-dives) + receipts (backtest JSON dumps that back claims in the `.md`). Keeps a verifiable audit trail — aligned with `docs/quant_claim_verification.md`. |
| **Tier 4 — Configuration** | `.mcp.json`, `docker/.env.example`, `event_calendar.yaml`, `.claude/` (excluding `settings.local.json`) | Reproducibility. No real secrets — local-dev credentials only. |
| **Tier 5 — Planning & docs** | `docs/plans/*.md`, `docs/*.md`, `README.md`, `CLAUDE.md` | Decision trail; required by global DevOps pipeline. |

### Never tracked

- Build/cache: `__pycache__/`, `*.pyc`, `*.egg-info/`, virtualenvs
- Local config & secrets: `.claude/settings.local.json`, `docker/.env`, real DB credentials
- Generated/printable artifacts: `*.pdf`, `*.html` exports of analysis reports (regenerate from the `.md` source)
- Ephemeral data dumps: tick/quote CSVs older than the current analysis day (see §3)
- OS junk: `.DS_Store`, `*.tmp`, `*.log`
- Agent scratch: `.claude/worktrees/`, `.graph_*.txt`, `_temp_fix_*.py`, `enrichment*.json`

### The `analysis/reports/` rule (permissive policy)

- **`.md`** — track. Human-written analysis.
- **`.json`** — track. Backtest evidence; small, supports claim verification.
- **`.csv`** — track only if it backs a specific `.md` claim. Bulk tick/quote dumps are ephemeral.
- **`.pdf`, `.html`** — never track. Regenerate on demand.

---

## 2. Commit Conventions

Conventional Commits, extended with a `data:` prefix for bulk research refreshes.

### Prefix taxonomy

| Prefix | When to use | Example |
|---|---|---|
| `feat:` | New capability (new script, new section, new sector folder) | `feat(screen): add foplp watchlist` |
| `fix:` | Bug fix in code or data correctness | `fix(ner): match by company name, not ticker` |
| `refactor:` | Code/data restructure with no behavior change | `refactor(scripts): extract common utils` |
| `docs:` | Docs only (`docs/`, `CLAUDE.md`, `README.md`) | `docs(plan): wikilink IDF redesign` |
| `test:` | Test additions/fixes | `test(audit): cover empty-supply-chain edge` |
| `chore:` | Tooling, deps, gitignore, config | `chore(git): add gitattributes` |
| `data:` | **Bulk research refresh** — script-generated updates to Tier 1 reports (valuations, financials, enrichment) | `data(valuation): refresh 926 tickers 2026-05-12` |
| `research:` | Hand-authored ticker enrichment, deep-dives, market views | `research(2330): refresh CoWoS supply chain` |

### Message body rules

- **Explain WHY, not WHAT.** The diff shows what changed.
- Reference triggering events: "post-earnings refresh", "yfinance schema change", "Q1 close".
- For `data:` commits, include the script command in the body for reproducibility:
  ```
  data(valuation): refresh 926 tickers 2026-05-12

  Run as part of weekly close cycle.
  Command: python scripts/update_valuation.py
  Source: yfinance @ 2026-05-12 close
  ```
- For `research:` commits affecting many tickers, list affected sectors or tickers in the body.

### What never goes in a commit message

- "Updated files" / "Made changes" / "Various fixes" (zero information)
- Internal references that rot ("for the bug Felix mentioned", "per Slack DM")
- AI-author tags except the required `Co-Authored-By: Claude ...` trailer

---

## 3. Commit Granularity

### Split into separate commits when:

- A change touches both Tier 2 code AND Tier 1 reports — commit the code first, then the regenerated data
- A `data:` refresh and a `fix:` happen on the same day — separate them
- More than one sector's reports are touched for different reasons

### Bundle into one commit when:

- All ticker reports change because of a single script run (`data(valuation): refresh ...`)
- A `feat:` adds a script and its initial output together (acceptable for the very first run)
- A refactor mechanically affects many files identically

### The 922-file problem

When `update_valuation.py` or `update_financials.py` runs, **commit all touched ticker files in one `data:` commit**. Don't sector-split a single script run — it implies the sectors were updated for different reasons. They weren't.

---

## 4. Branching & PR Rules

### Branch model
- `master` is the trunk. Production. Always green.
- Feature branches: `feat/<short-slug>`, `fix/<short-slug>`, `data/<YYYY-MM-DD>` (for data refreshes that need review).
- One-off ticker hand-edits: commit directly to `master` is acceptable for single-ticker fixes; multi-ticker enrichment should go via a branch.

### PR checklist (per global standards)
- [ ] Plan committed to `docs/plans/YYYY-MM-DD-<topic>.md`
- [ ] All `data:` commits include the script command in the body
- [ ] If touching Tier 1 reports: confirm ticker-company identity per CLAUDE.md Golden Rule #2
- [ ] If a quant claim is added (σ, percentile, outlier): `verify_flow_zscore.py` output pasted into the relevant report's Verification log
- [ ] CI / audit script clean: `python scripts/audit_batch.py --all -v` passes for touched batches

### Never force-push to `master`
- Use `git revert` for mistakes; never `reset --hard` published history.

---

## 5. Tier 1 Sanctity Rules (CLAUDE.md → git)

Specific commit-time invariants enforced by reviewers:

1. **Financial tables (`## 財務概況`) are script-output only.** Hand edits to that section are a `fix:` (only to correct a script bug) or `data:` (regeneration). Never a `research:`.
2. **Wikilink rules** — every PR touching `[[...]]` must comply with CLAUDE.md Golden Rule #1 (specific proper nouns only). Reviewer rejects on first violation.
3. **Filename = ground truth.** `XXXX_中文名.md` — never rename a ticker file without explicit confirmation that the company actually renamed.
4. **No placeholders shipped.** PRs containing `*(待 AI 補充)*`, `(待更新)`, or `(基於嚴格實名制...)` are blocked.

---

## 6. .mcp.json & Local Credentials

- `.mcp.json` is **tracked**: it documents which MCP servers this repo expects.
- Credentials in `.mcp.json` are **local-dev only** (`knowledge:knowledge`, `localhost`, container-internal hostnames). No production secrets ever land there.
- For real secrets, use `docker/.env` (gitignored) and document the variable name in `docker/.env.example` (tracked).

---

## 7. Quick Reference

```bash
# Before committing a data refresh:
python scripts/audit_batch.py --all -v

# Bulk valuation refresh commit:
git add Pilot_Reports/
git commit -m "data(valuation): refresh 926 tickers $(date +%Y-%m-%d)" \
  -m "Command: python scripts/update_valuation.py" \
  -m "Source: yfinance @ market close"

# Hand-authored research commit:
git add "Pilot_Reports/Semiconductors/2330_台積電.md"
git commit -m "research(2330): expand CoWoS customer list per Q1 法說會"

# View Chinese filenames un-escaped:
git config core.quotepath false
```

---

**Last reviewed:** 2026-05-12
**Owner:** repo maintainer
