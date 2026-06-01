---
type: meta
status: living
last_updated: 2026-05-15
---

# Vault Schema — LLM Wiki Conventions

This vault sits on top of the `My-TW-Coverage` project as an LLM-maintained knowledge layer. Per the LLM Wiki manifesto: **the LLM writes/maintains all pages, the user curates sources and asks questions**. The vault gets richer with every ingest.

## Architecture (3 layers)

1. **Raw sources** — `../Pilot_Reports/` (926 ticker .md), `../themes/` (26 thematic .md), `../analysis/reports/` (dated reports + CSV). Vault never modifies these.
2. **The vault** (this dir) — LLM-owned markdown layer. Summaries, concept pages, user profile, trading playbooks, project state.
3. **The schema** — this file + project-level `../CLAUDE.md` `## Vault & Cross-Session Protocol` section.

## Page categories

| Category | Location | What it holds |
|---|---|---|
| user | `user/` | Profile, preferences, tools — synthesized from observed behavior |
| project | `projects/` | active / pending / completed work, dated |
| concept | `concepts/` | Topic synthesis (TXF, DXY, FOPLP, covariance) |
| entity | `entities/` | 1-line stubs linking back to `Pilot_Reports/*.md` (never duplicate) |
| trading | `trading/` | Open positions, reusable playbooks, watchlists |
| inbox | `inbox/` | Weekly dated dumps from Redis + signal_alerts |
| meta | `meta/` | This file + lint reports |

## Frontmatter standard (all vault pages)

```yaml
---
type: user|project|concept|entity|trading|inbox|meta
status: active|monitoring|completed|archived|stub
last_updated: YYYY-MM-DD
related: [page1.md, page2.md]   # optional outbound links
tags: [TXF, DXY, ...]            # optional, for filtering
---
```

`last_updated` is required and is what `vault_lint.py` uses to detect staleness (>30 days flagged).

## Wikilink rules (inherits `../CLAUDE.md` Golden Rule #1)

- `[[X]]` MUST resolve to a specific proper noun: company, named technology, named material, named process.
- Generic words (大廠 / 供應商 / 廠商) NEVER wikilinked.
- Cross-folder wikilinks: when linking to a ticker page outside vault, use **relative path**: `[[../Pilot_Reports/Semiconductors/2330_台積電|2330 台積電]]`. Obsidian respects this.
- When linking inside vault, use page basename: `[[TXF]]` → `concepts/TXF.md`.

## Ingest workflow

When the user shares a URL, file, or asks me to "save this finding":

1. Read the source.
2. Discuss key takeaways with the user (don't write yet).
3. Decide which existing pages to update vs whether to create a new page.
4. Update relevant `concepts/`, `projects/active.md`, `trading/playbooks.md` as needed.
5. Append `log.md` entry: `## [YYYY-MM-DD HH:MM TWT] ingest | {short summary}`.
6. If broad-impact (regime change, new playbook): also `python3 scripts/claude_msg.py send {topic} "{summary}"` for cross-session signal.
7. Update `index.md` if new pages were created.

## Query workflow

When the user asks a content question:

1. **Read `index.md` first** — find the relevant page(s).
2. Drill into those pages.
3. If the answer requires synthesis, build it; consider saving the synthesis back as a new `concepts/` page (per LLM Wiki "answers can become new pages").
4. Cite vault page paths in the answer.

## Lint cadence

Weekly (cron Sun 22:00 TWT): `python3 scripts/vault_lint.py`. Finds:

- Orphan pages (no inbound links)
- Stale pages (`last_updated` > 30 days)
- Contradiction candidates (same metric, conflicting values across pages)
- Index drift (`index.md` entries vs actual files in `vault/`)
- Missing wikilinks (proper nouns mentioned in plain text that have a vault page)

Lint outputs a report to console + appends `## [YYYY-MM-DD] lint | summary` to `log.md`. **Lint never auto-fixes** — it surfaces issues for the human (or next session) to address.

## Log format

`log.md` is append-only and chronological:

```
## [2026-05-15 22:30 TWT] ingest | TXF-DXY 60d β regime shift — see concepts/TXF.md
## [2026-05-15 23:00 TWT] sync | claude:inbox 5 msgs → vault/inbox/2026-W20.md
## [2026-05-16 09:00 TWT] lint | 0 orphans, 1 stale (concepts/FOPLP.md last_updated 2026-04-09)
```

Pattern is parseable: `grep "^## \[" log.md | tail -10` for quick recent timeline.

## Obsidian (optional)

Vault has minimal `.obsidian/` config. Open with `open -a Obsidian /Users/lulala/Documents/coding/My-TW-Coverage/vault/`. Vault is **fully usable as plain markdown** without Obsidian — Obsidian is just nicer for graph navigation.

## What this vault is NOT

- Not a chat log — `log.md` records events, not conversations.
- Not a research notebook — that's `../analysis/reports/`.
- Not the ticker database — that's `../Pilot_Reports/`.
- Not auto-generated from RAG — every page is curated/synthesized by the LLM (or migrated from prior context).
