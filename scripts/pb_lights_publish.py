"""Pre-market P/B lights publisher — single P/B-light source of truth.

Computes an engine-A P/B percentile light for every ticker in the portfolio
universe (data/buy_list_state.json) and publishes:
  - Redis hash `h:agent:pb_lights` (field=ticker -> JSON of the light record:
    {light, pb_current, percentile, p70, p85, asof, source})
  - an inbox summary (claude:inbox, topic=pb-lights)

Sub-project C (buy-list) reads the hash for its display + 減碼 rule.

Pure functions (load_universe ... build_inbox_summary) take already-fetched
data and are unit-tested offline. fetch_latest_closes / publish / push_inbox
are the only I/O and are injected/skipped in tests.

Note: `percentile` is best-effort — null on engine-A cache fast-path (only a
slow recompute fills it); consumers must key off `light`, not `percentile`.
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
                "percentile": None, "p70": None, "p85": None,
                "asof": today, "source": "no latest close",
            })
            continue
        rec = pb_light_fn(ticker, latest_close=close, today=today)
        records.append({
            "ticker": ticker,
            "light": rec["light"],
            "pb_current": rec["pb_current"],
            "percentile": rec["percentile"],
            "p70": rec.get("p70"),
            "p85": rec.get("p85"),
            "asof": rec["asof"],
            "source": rec["source"],
        })
    return records


def records_to_hash_mapping(records, now_iso) -> dict:
    """Flatten records to a Redis-hash mapping (all string values).

    Note: `percentile` is best-effort — null on engine-A cache fast-path;
    consumers must key off `light`, not `percentile`.
    """
    mapping = {}
    for rec in records:
        mapping[rec["ticker"]] = json.dumps({
            "light": rec["light"],
            "pb_current": rec["pb_current"],
            "percentile": rec["percentile"],
            "p70": rec.get("p70"),
            "p85": rec.get("p85"),
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
    # Elevated N/A count often signals a coverage regression (e.g. yfinance
    # rate-limited a batch) — list the tickers so it's diagnosable.
    if len(nas) > 3:
        lines.append(f"N/A: {', '.join(nas)}")
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
            multi = isinstance(data.columns, pd.MultiIndex)
            for sym, bare in suffix_map.items():
                try:
                    # yfinance column layout varies by version and by
                    # single-vs-multi symbol download; branch on the actual
                    # column shape, not the symbol count.
                    if multi:
                        close = data[sym]["Close"]
                    else:
                        close = data["Close"]
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
        ok = 0
        total = len(universe)
        for ticker in universe:
            try:
                pb_percentile.pb_light(ticker, today=today)  # no latest_close
                ok += 1
            except Exception as e:  # noqa: BLE001 — never let one ticker kill the run
                print(f"[warn] refresh failed for {ticker}: {e}",
                      file=sys.stderr)
        print(f"[ok] refreshed {ok}/{total} cutoffs", file=sys.stderr)
        return 0

    closes = fetch_latest_closes(universe)
    print(f"[info] closes fetched: {len(closes)}/{len(universe)}", file=sys.stderr)
    records = build_light_records(universe, closes, pb_percentile.pb_light, today)
    summary = build_inbox_summary(records, today)
    print(summary)

    if args.dry_run:
        print("\n[dry-run] not published, not notified", file=sys.stderr)
        return 0

    # Digest is already printed above; a Redis outage here must degrade to a
    # logged error (not a raw traceback) so the computed digest is preserved.
    try:
        client = None
        if not args.no_redis or not args.no_notify:
            client = make_redis_client()

        if not args.no_redis:
            now_iso = datetime.now().isoformat(timespec="seconds")
            publish(records_to_hash_mapping(records, now_iso), client)
            print(f"[ok] published {len(records)} to {HASH_KEY}",
                  file=sys.stderr)

        if not args.no_notify:
            push_inbox(summary, today, client)
            print(f"[ok] pushed to {INBOX_STREAM} topic=pb-lights",
                  file=sys.stderr)
    except Exception as e:  # noqa: BLE001 — Redis unreachable → degrade, don't crash
        print(f"[error] redis unavailable: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
