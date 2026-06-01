---
type: project
status: pending
last_updated: 2026-05-15
---

# Pending / Queued Projects

## Daily Asia panel refresh cron
- Wire `crontab -e` line: `0 18 * * 1-5 cd /Users/lulala/Documents/coding/My-TW-Coverage && python3 scripts/fetch_asia_panel.py && python3 scripts/validate_asia_panel.py && python3 scripts/compute_asia_covariance.py && python3 analysis/dashboard_builder.py`
- Auto-rebuild dashboard at 18:00 TWT each weekday

## Bond yields + commodities panel extension
- Add: UST 10Y/2Y, JGB 10Y, WTI, Brent, copper, gold, silver
- Same TimescaleDB schema, separate table `bond_commodity_daily`
- Re-run covariance with 30 instrument matrix

## TXF intraday tick-level analysis
- Existing `ticks` table has 57M TXF rows last 3 weeks
- Build OFI / lead-lag features → predict next 5-min move
- Pair with `iv_metrics` (TXO options)

## Cross-session Redis → graph layer
- For high-conviction findings, also publish to FalkorDB Graphiti (group_id `tw-electronics`)
- Builds permanent semantic graph alongside vault markdown

## Shioaji auto-order scripts (per playbook)
- `scripts/place_00763u_ladder.py` — auto-place 4 sell limits + 3 stop triggers
- Requires CA password at runtime

## Quarterly lint + re-synthesis
- Cron last day of month: `vault_lint.py` + re-summarize stale concept pages

## Webhook receiver for external alerts
- Slack / Discord webhook → push to `claude:inbox` Redis stream
- Lets non-Claude tools also drop messages

## Daily market snapshot page (boot-test gap)
- Auto-generate `vault/market/daily_snapshot.md` at EOD (18:00 TWT)
- Pulls from `asia_index_daily` + `institutional_daily` + DXY close
- Boot script reads this so "今日台股怎麼樣" answerable without DB query
- Caught by 2026-05-15 boot validation: vault is event/playbook-driven, missing routine "today's prices"

## Confirm 00763U 張數 (positions.md note)
- Currently positions.md says `100 張 (假設, 待 user 確認)`
- Pending: user confirms actual lot count → update + remove "假設"
- Affects sizing of TP/SL ladders

## Resolve outstanding lint contradiction
- 2026-05-15 16:09 lint flagged 1 beta_60d contradiction across 5 pages
- Likely false positive (regex matches adjacent numbers, not all are β values)
- Improve regex or accept as v1 limitation; document in `meta/schema.md`
