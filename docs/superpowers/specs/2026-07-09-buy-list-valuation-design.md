# Buy-List Valuation Display + Priority-Trim Rule — Design Spec

**Date:** 2026-07-09
**Status:** Approved (design), pending implementation plan
**Sub-project:** C of 3 (final)

---

## Context

Sub-projects A and B built a P/B percentile engine and published per-ticker
lights to Redis hash `h:agent:pb_lights` (populated daily at 08:35 by
`scripts/pb_lights_publish.py`). Sub-project C consumes that hash in the daily
buy-list routine (`scripts/buy_list_daily_alert.py`, runs 08:50) to:

- **C① Valuation display** — show each pick/watch's P/B + light (from the hash),
  plus PE and 殖利率 recomputed at the latest close (from the Pilot_Reports
  `估值指標` block). This closes the original request that started this whole
  effort: "integrate PE etc., and 殖利率 must use the latest price."
- **C② Priority-trim rule** — a stock that is **breaking its stop AND at P/B
  RED** gets flagged `🔴 優先減碼`. The intersection is the point: the daily
  dry-run showed ~39/50 tickers RED (broadly elevated market), so RED alone is
  not selective — pairing it with a stop-break is what makes it actionable.

**P/B source unification:** the buy-list uses the hash's engine-A P/B (annual
BVPS, percentile light) as the single authoritative P/B, NOT the report's
`priceToBook`. The report is used only for PE, 殖利率, and the base price needed
to rescale them. This keeps the displayed P/B consistent with the light the
trim rule keys on.

---

## Data Flow

```
08:50  buy_list_daily_alert
  ├─ snapshots (DB latest_close)      ← existing (fetch_latest_snapshot)
  ├─ bb_status / disposition          ← existing
  └─ h:agent:pb_lights (NEW)          ← engine-A P/B + light (published 08:35)
         │
         ▼
  build_digest → per pick/watch line append valuation string;
                 stop-breaking + RED picks get 🔴 優先減碼 in the urgent section
         │
         ▼
  claude:inbox topic=buy-list  (existing push)
```

---

## Components (new pure functions — unit-tested offline)

All added to `scripts/buy_list_daily_alert.py` unless noted.

1. **`load_pb_lights(redis_client) -> dict[str, dict]`**
   `client.hgetall("h:agent:pb_lights")`; for each field that is a ticker
   (skip `_updated`/`_count` meta), `json.loads` → `{light, pb_current,
   percentile, p70, p85, asof, source}`. A ticker absent from the hash, or a
   JSON parse error, yields no entry (callers treat missing as N/A). Redis
   error → `{}` + `[warn]` log (fail-safe; no trim rule fires).

2. **`parse_report_valuation(ticker) -> dict | None`**
   Locate the report via `utils.find_ticker_files([ticker])`; read it; from the
   `估值指標` block parse:
   - `base_price` from the header `股價 $<num> as of <date>` (strip commas),
   - `yield_pct` from the header `殖利率 <num>%`,
   - `pe` from the first data cell (`P/E (TTM)`) of the metrics table.
   Return `{pe: float|None, yield_pct: float|None, base_price: float|None}`.
   Missing file / unparseable block / `N/A` cells → None or None-valued fields
   (never raise).

3. **`recompute_valuation(report_val, latest_close) -> dict`**
   Scale by the price ratio (report metrics were computed at `base_price`):
   - `pe_now = report_val.pe * (latest_close / base_price)`
   - `yield_now = report_val.yield_pct * (base_price / latest_close)`
   Any missing input (None base_price/pe/yield, or latest_close None) → that
   output is None. Pure arithmetic, no I/O.

4. **`format_valuation(pb_rec, report_val, latest_close) -> str`**
   Compose the display suffix, e.g. `P/B 7.20 🔴 · PE 45.4 · 殖 0.8%`.
   - P/B value + light emoji from `pb_rec` (light "N/A" → ⚪, and P/B shown or
     `N/A`).
   - PE / 殖利率 from `recompute_valuation`; each None → `N/A`.
   - Uses the existing `LIGHT_EMOJI`-style mapping (RED 🔴 / YELLOW 🟡 /
     GREEN 🟢 / N/A ⚪).

5. **`is_priority_trim(pick, snap, pb_rec) -> bool`**
   `True` iff `snap.latest_close is not None and snap.latest_close <=
   pick["stop_loss"] * 1.02 and pb_rec.get("light") == "RED"`. (Same stop-break
   threshold as the existing `_urgency`; RED gate from the hash.) N/A light →
   False (fail-safe: a data gap never triggers a trim recommendation).

---

## Integration into `build_digest` / `main`

- `main()`: construct a redis client (reuse the module's existing
  `redis.Redis(host, port, decode_responses=True)` pattern), call
  `load_pb_lights`, and thread the resulting `pb_lights` dict into
  `build_digest(state, snapshots, bb_status, disposition, pb_lights)`.
- `build_digest`: for every **pick and watch** line, append
  `format_valuation(pb_lights.get(sym, {}), parse_report_valuation(sym),
  close)`. Parse reports only for the picks+watch set (~34 tickers), not the
  full universe.
- In the existing **`## 🚨 緊急 (逼近 stop/TP)`** section, when
  `is_priority_trim(pick, snap, pb_lights.get(sym, {}))`, append
  `· 🔴 優先減碼 (P/B RED)` after the existing `🔴 逼近停損!` marker.

Report parsing is done once per ticker per run; cache the parse result in a
local dict within `build_digest` if a ticker appears in more than one section.

---

## Error Handling

| Condition | Behaviour |
|---|---|
| `h:agent:pb_lights` unreachable / empty | `load_pb_lights` → `{}` + `[warn]`; all lights N/A; no trim fires; PE/殖 still shown |
| One ticker missing from hash | that ticker's light N/A; no trim; P/B shown `N/A` |
| Report file missing / block unparseable | PE/殖 shown `N/A`; P/B+light still from hash |
| `latest_close` missing (snapshot gap) | valuation string shows what it can; trim rule False (fail-safe) |

Guiding principle (inherited from A/B): a data gap **suppresses** the trim
recommendation rather than emitting a false one.

---

## Testing

New `tests/test_buy_list_valuation.py` (offline; fixtures + fake redis):

1. `parse_report_valuation` — against a real committed report (e.g. 2454) and a
   synthetic fixture: extracts pe/yield/base_price; `N/A` cells → None; missing
   file → None.
2. `recompute_valuation` — price-ratio math: PE scales up with price, 殖利率
   scales down; None inputs → None outputs. (e.g. base 4030, pe 64.22, close
   4433 → pe ≈ 70.6; yield 1.33% → ≈ 1.21%.)
3. `format_valuation` — full string when all present; `N/A` substrings when
   pb_rec light N/A / report None; correct light emoji.
4. `is_priority_trim` — the four quadrants: (stop-break, RED)→True;
   (stop-break, GREEN)→False; (above-stop, RED)→False; (N/A light)→False.
5. `load_pb_lights` — parses ticker fields, skips `_updated`/`_count`, missing
   ticker absent, bad JSON skipped, fake-redis raise → `{}`.

---

## Out of Scope

- Changing how P/B lights are computed or published (that is A/B, already
  shipped). C is a pure consumer.
- Recomputing P/B in the buy-list (it comes from the hash).
- Any change to the buy-list's entry/stop/TP or 三大法人 logic.
