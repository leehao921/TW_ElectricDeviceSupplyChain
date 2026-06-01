---
type: user
status: living
last_updated: 2026-05-15
related: [profile.md]
---

# User Preferences (Style + Working Rules)

> Synthesized from 2026-04 to 2026-05 session history. Update when new corrections observed.

## Language + tone

- **All responses in 繁體中文** (CLAUDE.md Golden Rule #6); technical terms can stay English
- **Terse, opinionated, data-cited** — no hedging unless data genuinely ambiguous
- **No emojis** unless explicitly requested
- **No summarizing what was just done** at end of response (the user reads the work)
- **Use tables and numbered lists** for multi-point answers — easier to scan
- **Bold key numbers + decisions** (e.g., `**β = -1.47**`)

## Analysis discipline (HARD rules)

1. **量化主張必先驗證** — anything with σ / outlier / percentile / extreme must run `scripts/verify_flow_zscore.py` first and paste output to *Verification log* in the report. (Origin: 2026-04-29 mislabeled −1,386 億 3-day flow as "3σ" when actual z = −1.04σ)
2. **Dates always verified** — use `strftime('%A')` before saying "下個交易日" / "明天" / "上週X". TW 5/1 = 勞動節 (closed).
3. **Live state always verified** — VM size, container state, config — never trust snapshots from earlier turns; re-query in current turn.
4. **No premature selling** — user pushed back hard on 5/14 when I suggested selling 30%/50% of 3481 despite data supporting continued strength. **Rule: only exit on data-driven trigger (stop loss hit, basis crash, regime shift); don't suggest profit-taking just because position is up.**
5. **Don't conflate upstream and downstream peers** — 5/14 user corrected me: "你的對比同業完全不合理啊,他們是產業鏈上下游關係啊". When doing PCA / peer comparison, use **proper tier classification**: 純同業 (lateral) vs 上游 / 下游 separate.
6. **Wikilinks must be specific proper nouns** (CLAUDE.md Golden Rule #1) — companies, named tech, named materials. Generic words (大廠 / 供應商) NEVER linked.

## Infrastructure discipline

1. **Never duplicate existing infrastructure** — if Docker/DB already collects X, READ from it or EXTEND existing repo. Never build a parallel collector. (Origin: feedback_no_duplicate_infra.md)
2. **Read TimescaleDB before WebSearch** — when checking TW market data, query the DB first; only fall back to web for things DB doesn't have (international news, intraday Asia, Trump-Xi statements).

## Response format

- **For tactical questions** (e.g., "should I sell 00763U?"): give numbered scenarios with explicit trigger levels, not vague "看情況"
- **For quant questions**: show the formula or SQL, then result, then interpretation
- **For "explain X"**: structured — definition / mechanism / why-it-matters / current-state / tactical-implication
- **End with a one-line summary** (the user explicitly does NOT want trailing recaps of *what was done*, but DOES like a 一句話總結 of the answer)

## Trade-off priorities

- **Speed > thoroughness** for tactical questions (intraday)
- **Thoroughness > speed** for deep-dives (ticker reports, regime detection)
- **Source primacy > comprehensiveness** — 1 法說會 quote > 5 二手新聞 paraphrases
- **Persistence > convenience** — prefer Parquet + DB dual-write over one-shot CSV
