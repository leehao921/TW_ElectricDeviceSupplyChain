---
type: user
status: living
last_updated: 2026-05-15
related: [preferences.md, tools.md]
---

# User Profile

## Identity

- **Email:** leehao921@gmail.com
- **Github:** felix0921
- **Location:** Taiwan (UTC+8)
- **Role:** TW retail/semi-pro trader, technically literate (writes Python, manages Docker stacks, runs MCP servers locally)

## Trading

- **Main contract:** **台灣加權指數期貨 (TXF)** — Taiwan Index Futures, MX/TX series
- **Broker:** [[Shioaji]] (永豐證券) — has CA password, places real orders via API
- **Account scale:** Retail-sized; talks in 張 (lots) for stocks, 口 (contracts) for futures
- **Active positions (as of 2026-05-15):**
  - **00763U** 期街口道瓊銅 ETF, cost NT$31.47 (long), holding 100 張
  - Watchlist: [[3481]] 群創, [[2317]] 鴻海, [[5469]] 瀚宇博

## Knowledge base

Maintains **926 TW-listed electronics tickers** across 11 sectors in `../Pilot_Reports/`. Each ticker file has 業務簡介 / 供應鏈 / 客戶 / 財務概況. **Wikilinks `[[X]]` are the core cross-reference mechanism** (see `../CLAUDE.md` Golden Rules).

## Infrastructure (self-hosted)

- **`trading-timescaledb`** — Docker, port 5432, DB `tmf_market_data`, TIMESTAMPTZ Asia/Taipei
- **`trading-redis`** — Docker, port 6379, used for stream + bar-sync
- **`knowledge-platform-falkordb`** — :6380, graph layer (Graphiti `group_id="tw-electronics"`)
- **`knowledge-platform-postgres`** — :5433, dedicated `tw_electronics` DB
- See [tools.md](tools.md) for full stack inventory

## Analytical style

- Quantitative — runs PCA, factor regressions, z-score verification before claiming "extreme"
- Cites primary sources (法說會, 年報, IR PR) — secondary sources (新聞) clearly labelled
- Verifies dates with `strftime('%A')` (TW 5/1 = 勞動節 holiday)
- Treats memory of past sessions as authoritative until verified stale
