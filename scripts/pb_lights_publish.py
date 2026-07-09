"""Pre-market P/B lights publisher — single P/B-light source of truth.

Computes an engine-A P/B percentile light for every ticker in the portfolio
universe (data/buy_list_state.json) and publishes:
  - Redis hash `h:agent:pb_lights` (field=ticker -> JSON of the light record)
  - an inbox summary (claude:inbox, topic=pb-lights)

Sub-project C (buy-list) reads the hash for its display + 減碼 rule.

Pure functions (load_universe ... build_inbox_summary) take already-fetched
data and are unit-tested offline. fetch_latest_closes / publish / push_inbox
are the only I/O and are injected/skipped in tests.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pb_percentile

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "data" / "buy_list_state.json"
HASH_KEY = "h:agent:pb_lights"
INBOX_STREAM = "claude:inbox"


# --------------------------------------------------------------------- #
# Pure functions (unit-tested)
# --------------------------------------------------------------------- #
def load_universe(state_path=STATE_PATH) -> list[str]:
    """Union tickers from picks + watch_list + avoid_list, deduped, ordered.

    Each entry may be a dict (ticker at ["ticker"]) or a bare string ticker.
    """
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
    out: list[str] = []
    seen: set[str] = set()
    for key in ("picks", "watch_list", "avoid_list"):
        for entry in state.get(key, []) or []:
            tk = entry["ticker"] if isinstance(entry, dict) else entry
            if tk not in seen:
                seen.add(tk)
                out.append(tk)
    return out


def build_light_records(universe, closes, pb_light_fn, today) -> list[dict]:
    """Per ticker -> light record. Never drops a ticker; gaps become N/A."""
    records = []
    for ticker in universe:
        close = closes.get(ticker)
        if close is None:
            records.append({
                "ticker": ticker, "light": "N/A", "pb_current": None,
                "percentile": None, "asof": today, "source": "no latest close",
            })
            continue
        rec = pb_light_fn(ticker, latest_close=close, today=today)
        records.append({
            "ticker": ticker,
            "light": rec["light"],
            "pb_current": rec["pb_current"],
            "percentile": rec["percentile"],
            "asof": rec["asof"],
            "source": rec["source"],
        })
    return records


def records_to_hash_mapping(records, now_iso) -> dict:
    """Flatten records to a Redis-hash mapping (all string values)."""
    mapping = {}
    for rec in records:
        mapping[rec["ticker"]] = json.dumps({
            "light": rec["light"],
            "pb_current": rec["pb_current"],
            "percentile": rec["percentile"],
            "asof": rec["asof"],
            "source": rec["source"],
        }, ensure_ascii=False)
    mapping["_updated"] = now_iso
    mapping["_count"] = str(len(records))
    return mapping


def build_inbox_summary(records, today) -> str:
    """Concise markdown: counts + RED/YELLOW ticker lists."""
    reds = [r["ticker"] for r in records if r["light"] == "RED"]
    yellows = [r["ticker"] for r in records if r["light"] == "YELLOW"]
    nas = [r["ticker"] for r in records if r["light"] == "N/A"]
    total = len(records)
    lines = [
        f"**P/B Lights {today}** — "
        f"{len(reds)} RED / {len(yellows)} YELLOW / {len(nas)} N/A of {total}",
        f"RED: {', '.join(reds) if reds else '(none)'}",
        f"YELLOW: {', '.join(yellows) if yellows else '(none)'}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------- #
# I/O functions (thin, not unit-tested)
# --------------------------------------------------------------------- #
def fetch_latest_closes(universe) -> dict:
    """Batched yfinance download -> {bare_ticker: last non-NaN close}.

    Tries `.TW` for all; retries `.TWO` for tickers that come back empty.
    On any failure returns {} and logs a warning.
    """
    try:
        import pandas as pd
        import yfinance as yf

        def _download(suffix_map):
            # suffix_map: {yf_symbol: bare_ticker}
            symbols = list(suffix_map)
            if not symbols:
                return {}
            data = yf.download(symbols, period="5d", progress=False,
                               group_by="ticker", threads=True)
            out = {}
            for sym, bare in suffix_map.items():
                try:
                    if len(symbols) == 1:
                        close = data["Close"]
                    else:
                        close = data[sym]["Close"]
                    close = close.dropna()
                    if len(close):
                        out[bare] = float(close.iloc[-1])
                except (KeyError, IndexError, ValueError):
                    continue
            return out

        tw_map = {f"{t}.TW": t for t in universe}
        closes = _download(tw_map)
        missing = [t for t in universe if t not in closes]
        if missing:
            two_map = {f"{t}.TWO": t for t in missing}
            closes.update(_download(two_map))
        return closes
    except Exception as e:  # noqa: BLE001
        print(f"[warn] fetch_latest_closes failed: {e}", file=sys.stderr)
        return {}


def publish(mapping, redis_client, key=HASH_KEY) -> None:
    """Delete-then-set so delisted tickers don't linger."""
    redis_client.delete(key)
    redis_client.hset(key, mapping=mapping)


def push_inbox(summary, as_of, redis_client) -> None:
    redis_client.xadd(INBOX_STREAM, {
        "topic": "pb-lights",
        "from": "pb_lights_publish",
        "tags": "pb-lights,daily",
        "as_of": as_of,
        "msg": summary,
    })


def make_redis_client():
    import redis
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=0,
        decode_responses=True,
    )


# --------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="Print digest only; no publish, no notify")
    ap.add_argument("--no-redis", action="store_true", help="Skip Redis publish")
    ap.add_argument("--no-notify", action="store_true", help="Skip inbox push")
    ap.add_argument("--refresh-cutoffs", action="store_true",
                    help="Recompute engine-A cutoffs (no publish/notify)")
    ap.add_argument("--state", default=str(STATE_PATH))
    ap.add_argument("--today", default=date.today().isoformat())
    args = ap.parse_args(argv)

    today = args.today
    universe = load_universe(Path(args.state))
    print(f"[info] universe: {len(universe)} tickers", file=sys.stderr)

    if args.refresh_cutoffs:
        n = 0
        for ticker in universe:
            pb_percentile.pb_light(ticker, today=today)  # no latest_close
            n += 1
        print(f"[ok] refreshed cutoffs for {n} tickers", file=sys.stderr)
        return 0

    closes = fetch_latest_closes(universe)
    print(f"[info] closes fetched: {len(closes)}/{len(universe)}", file=sys.stderr)
    records = build_light_records(universe, closes, pb_percentile.pb_light, today)
    summary = build_inbox_summary(records, today)
    print(summary)

    if args.dry_run:
        print("\n[dry-run] not published, not notified", file=sys.stderr)
        return 0

    client = None
    if not args.no_redis or not args.no_notify:
        client = make_redis_client()

    if not args.no_redis:
        now_iso = datetime.now().isoformat(timespec="seconds")
        publish(records_to_hash_mapping(records, now_iso), client)
        print(f"[ok] published {len(records)} to {HASH_KEY}", file=sys.stderr)

    if not args.no_notify:
        push_inbox(summary, today, client)
        print(f"[ok] pushed to {INBOX_STREAM} topic=pb-lights", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
