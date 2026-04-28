---
name: research-ticker
description: Deep research on a single ticker by chaining report + recent news + institutional flow. Use when the user asks for a full briefing on one Taiwan electronics ticker.
---

# Research Ticker

Produce a single-ticker briefing by chaining three MCP tools exposed by `tw-electronics-research`:

1. `get_report(ticker)` — full Markdown report (`業務簡介`, `供應鏈位置`, `主要客戶及供應商`, `財務概況`).
2. `get_recent_news(ticker, 7)` — last 7 days of news from `news_items` (MOPS, CNA, UDN, CTEE, Yahoo, Google).
3. `get_institutional_flow(ticker, 5)` — last 5 trading sessions of 三大法人 net flow from `trading-timescaledb`.

## Usage

User: "Give me a full briefing on 2330"

Execute in order:

```
get_report("2330")
get_recent_news("2330", days=7)
get_institutional_flow("2330", sessions=5)
```

## Output structure

Present a concise briefing in Traditional Chinese with these sections, in this order:

1. **公司定位** — one-paragraph summary derived from `業務簡介`.
2. **供應鏈位置** — bulleted upstream / midstream / downstream lifted from the report; preserve `[[wikilinks]]`.
3. **主要客戶與供應商** — segmented list from the report.
4. **近 7 日新聞要點** — top 5–10 headlines with source + date, grouped by MOPS disclosures vs general news.
5. **近 5 日法人動向** — a compact table: 日期 / 外資 / 投信 / 自營 / 合計 (in 張 or 百萬台幣).
6. **重點觀察** — 3 bullets synthesizing the above.

## When NOT to use

- Broad theme questions — use `query-supply-chain` instead.
- New ticker not yet in the corpus — run `/add-ticker` first, then research.
- Multi-ticker screens — make separate calls per ticker, do not try to chain a single MCP call across N tickers.
