---
name: query-supply-chain
description: Find companies exposed to a technology/material wikilink or map the upstream/downstream of a ticker. Use when the user asks "which companies are in the X supply chain" or "show upstream/downstream of ticker Y".
---

# Query Supply Chain

Answer supply-chain questions by chaining two MCP tools exposed by `tw-electronics-research`:

- `find_tickers_exposed_to(wikilink)` — returns every ticker connected to a `[[wikilink]]` node in the graph (FalkorDB, `group_id="tw-electronics"`).
- `get_supply_chain(ticker, depth)` — returns upstream + downstream neighbors of a ticker to the given depth.

## When to use

- "Which Taiwan companies make CoWoS?" → `find_tickers_exposed_to("CoWoS")`
- "Who supplies 台積電?" → `get_supply_chain("2330", depth=1)` and filter upstream edges
- "Show me the full HBM supply chain" → `find_tickers_exposed_to("HBM")`, then `get_supply_chain(ticker, depth=2)` on each hit
- "Who are 鴻海's downstream customers?" → `get_supply_chain("2317", depth=1)` and filter downstream edges

## Typical chain

1. If the user gives a **theme/technology/material** (e.g. `矽光子`, `HBM`, `光阻液`), start with `find_tickers_exposed_to`.
2. If the user gives a **ticker**, start with `get_supply_chain`.
3. For each returned ticker, optionally call `get_report(ticker)` to pull the Markdown report for full context.
4. Present the result grouped by upstream / midstream / downstream, matching the structure in `Pilot_Reports/*/*.md`.

## Example

User: "Which companies are in the CoWoS supply chain and what do they each do?"

```
find_tickers_exposed_to("CoWoS")
  → ["2330", "3661", "3374", "3037", ...]
for each ticker:
  get_report(ticker)   # pull the ## 供應鏈位置 section
```

Summarize upstream (equipment, substrates), midstream (packaging), downstream (AI accelerators).
