"""P/B historical-percentile engine.

Per ticker: pull 5y annual book value + daily close from yfinance, build a
daily P/B series, and report the current P/B's percentile within its own
history as a GREEN / YELLOW / RED light (85 / 70 bands).

Pure functions (compute_bvps ... compute_pb_light) take already-fetched data
and are unit-tested with synthetic fixtures. fetch_yf is the only networked
function. Data gaps -> light="N/A" (never RED) so downstream stop-break rules
fail safe.

See docs/superpowers/specs/2026-07-08-pb-percentile-engine-design.md.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "pb_percentile_cache.json"
RED_PCT = 85.0
YELLOW_PCT = 70.0
MIN_DAYS = 250
STALE_DAYS = 7


def compute_bvps(equity: dict, shares) -> dict:
    """Book value per share per fiscal year. Drop NaN/<=0 equity; shares must be >0."""
    if not shares or shares <= 0:
        return {}
    out = {}
    for year, eq in equity.items():
        if eq is None:
            continue
        if isinstance(eq, float) and math.isnan(eq):
            continue
        if eq <= 0:
            continue
        out[int(year)] = eq / shares
    return out


def build_pb_series(prices: "pd.Series", bvps: dict) -> "pd.Series":
    """Daily P/B = close / (BVPS of most recent fiscal year-end <= date).

    Dates earlier than the first available fiscal year-end are dropped.
    """
    if not bvps or prices is None or len(prices) == 0:
        return pd.Series(dtype=float)
    years = sorted(bvps)
    year_ends = [(pd.Timestamp(y, 12, 31), bvps[y]) for y in years]

    def asof(d):
        chosen = None
        for ye, val in year_ends:
            if ye <= d:
                chosen = val
        return chosen  # None if date precedes first FY-end

    idx = pd.to_datetime(prices.index)
    denom = pd.Series([asof(d) for d in idx], index=prices.index)
    pb = (prices / denom).dropna()
    return pb


def pct_rank(values: "pd.Series", current: float) -> float:
    """Percentile of `current`: fraction of values strictly less, x100."""
    return float((values < current).mean() * 100.0)


def classify(percentile: float, red: float = RED_PCT, yellow: float = YELLOW_PCT) -> str:
    if percentile >= red:
        return "RED"
    if percentile >= yellow:
        return "YELLOW"
    return "GREEN"


def _na(ticker: str, asof: str, source: str) -> dict:
    return {
        "ticker": ticker, "pb_current": None, "percentile": None,
        "light": "N/A", "p70": None, "p85": None, "bvps": None, "n_days": 0,
        "source": source, "asof": asof,
    }


def compute_pb_light(prices, equity, shares, ticker="", asof="",
                     red=RED_PCT, yellow=YELLOW_PCT) -> dict:
    """Pure: given fetched inputs, return the light dict. Fails safe to N/A."""
    bvps = compute_bvps(equity, shares)
    if not bvps:
        return _na(ticker, asof, "no valid annual book value")
    latest_bvps = bvps[max(bvps)]
    if latest_bvps <= 0:
        return _na(ticker, asof, "non-positive latest book value")
    series = build_pb_series(prices, bvps)
    if len(series) < MIN_DAYS:
        return _na(ticker, asof, f"thin history ({len(series)} days)")
    current_pb = float(prices.iloc[-1]) / latest_bvps
    percentile = pct_rank(series, current_pb)
    return {
        "ticker": ticker,
        "pb_current": round(current_pb, 4),
        "percentile": round(percentile, 1),
        "light": classify(percentile, red, yellow),
        "p70": round(float(series.quantile(yellow / 100.0)), 4),
        "p85": round(float(series.quantile(red / 100.0)), 4),
        "bvps": round(latest_bvps, 4),
        "n_days": int(len(series)),
        "source": "yfinance annual BVPS 5y",
        "asof": asof,
    }


def light_from_cutoffs(current_pb: float, p70: float, p85: float) -> str:
    """Fast-path light: compare current P/B to cached absolute cutoffs.

    Equivalent to classify(percentile) because p70/p85 ARE the percentile
    cutoffs of the same historical distribution.
    """
    if current_pb >= p85:
        return "RED"
    if current_pb >= p70:
        return "YELLOW"
    return "GREEN"


def load_cache(path=CACHE_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache: dict, path=CACHE_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def _days_between(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def fetch_yf(ticker: str):
    """Networked: return (prices: pd.Series, equity: dict[int,float], shares).

    Tries `<ticker>.TW` then `<ticker>.TWO`. Not unit-tested (injected in tests).
    """
    import yfinance as yf

    # Fallback assumes symbol consistency: a ticker's balance sheet AND price come
    # from the same suffix. A transient empty history() under .TW could fall
    # through to .TWO — acceptable given TW/TWO tickers don't collide.
    for suffix in (".TW", ".TWO"):
        t = yf.Ticker(f"{ticker}{suffix}")
        bs = getattr(t, "balance_sheet", None)
        if bs is None or bs.empty or "Stockholders Equity" not in bs.index:
            continue
        eq_row = bs.loc["Stockholders Equity"]
        equity = {ts.year: (None if pd.isna(v) else float(v))
                  for ts, v in eq_row.items()}
        shares = t.info.get("sharesOutstanding")
        px = t.history(period="5y")["Close"]
        if px is None or px.empty:
            continue
        px.index = px.index.tz_localize(None)
        return px, equity, shares
    return pd.Series(dtype=float), {}, None


def pb_light(ticker: str, latest_close: float | None = None,
             cache_path=CACHE_PATH, today: str | None = None,
             fetcher=fetch_yf) -> dict:
    """Public entry. Fresh cache -> fast path; miss/stale -> recompute + persist."""
    today = today or date.today().isoformat()
    cache = load_cache(cache_path)
    entry = cache.get(ticker)

    fresh = (entry and entry.get("asof")
             and _days_between(entry["asof"], today) <= STALE_DAYS
             and entry.get("p85") is not None and entry.get("bvps") is not None)
    if fresh and latest_close is not None:
        current_pb = float(latest_close) / entry["bvps"]
        return {
            "ticker": ticker,
            "pb_current": round(current_pb, 4),
            "percentile": None,   # fast path does not recompute percentile
            "light": light_from_cutoffs(current_pb, entry["p70"], entry["p85"]),
            "p70": entry["p70"], "p85": entry["p85"], "bvps": entry["bvps"],
            "n_days": entry.get("n_days", 0),
            "source": "cache fast-path", "asof": entry["asof"],
        }

    prices, equity, shares = fetcher(ticker)
    res = compute_pb_light(prices, equity, shares, ticker=ticker, asof=today)
    if res["light"] != "N/A":
        cache[ticker] = {
            "bvps": res["bvps"], "p70": res["p70"], "p85": res["p85"],
            "asof": today, "n_days": res["n_days"],
        }
        save_cache(cache, cache_path)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P/B historical-percentile light per ticker")
    ap.add_argument("tickers", nargs="+", help="bare tickers, e.g. 2408 2344")
    ap.add_argument("--cache", default=str(CACHE_PATH))
    ap.add_argument("--today", default=None)
    args = ap.parse_args(argv)
    for tk in args.tickers:
        r = pb_light(tk, cache_path=args.cache, today=args.today, fetcher=fetch_yf)
        pct = "N/A" if r["percentile"] is None else f"{r['percentile']}"
        print(f"{r['ticker']}: P/B={r['pb_current']} pct={pct} -> {r['light']}  ({r['source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
