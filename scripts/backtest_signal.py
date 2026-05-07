"""Walk-forward backtest of the 3-factor signal layer.

Goal: validate the 2-of-3 trigger gate (defined in
``ingestion/snapshots/ticker_signal.py``) against historical data without
any peek into the future.

Universe is restricted to the top-N most newsy electronics tickers over
the backtest window — the only ones a news-density factor would ever
consider — so we avoid wasting compute on the long tail of names with
~0 daily mentions.

Forward returns come from ``institutional_stock.close_price`` (already
populated by the upstream backfill). 5d / 10d forward returns are
computed against the close of the *as_of* trade date.

Anti-look-ahead:
- ``compute_factors(as_of=D)`` already constrains every SQL filter to
  ``<= D``; the only un-tested code path is the ``WIKILINK_HEAT_SQL``
  upper bound (``published_at <= $1``), verified before backtest start.
- Forward-return prices are queried strictly from dates *after* D.

Usage::

    docker exec tw-electronics-scheduler python3 scripts/backtest_signal.py \\
        --start 2026-04-01 --end 2026-05-04 --top-n 150 \\
        --output analysis/reports/backtest_signal_2026-05-05.md

Reports:
- Per-as_of summary (date, alert count, mean fwd 10d return)
- Aggregate hit rate, IC, mean fwd return per fire-pattern
- Top-10 alerts by composite, with their forward returns
- 5 worst false-positives (alerts where fwd 10d <= -3%)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Repo root on sys.path so this runs from the container's /app.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingestion import db
from ingestion.snapshots.ticker_signal import compute_factors
from ingestion.universe import electronics_tickers, ticker_name

PG_TRADING_DSN = os.environ.get(
    "PG_TRADING_DSN",
    "postgresql://tmf:tmf_dev_2026@localhost:5432/tmf_market_data",
)

# Default 2-of-3 gate; --min-fired CLI arg overrides at runtime.
MIN_FACTORS_HIT = 2


# -- Universe selection -----------------------------------------------------


_TOP_NEWSY_SQL = """
SELECT t AS ticker, count(*) AS hits
  FROM news_items, unnest(tickers) t
 WHERE published_at >= $1::timestamptz
   AND published_at <= $2::timestamptz
   AND t = ANY($3::text[])
 GROUP BY t
 ORDER BY hits DESC
 LIMIT $4;
"""


async def pick_universe(start: datetime, end: datetime, top_n: int) -> list[str]:
    """Top-N electronics tickers by news count over the backtest window."""
    pool = await db.get_pool()
    eligible = list(electronics_tickers())
    async with pool.acquire() as conn:
        rows = await conn.fetch(_TOP_NEWSY_SQL, start, end, eligible, top_n)
    return [r["ticker"] for r in rows]


# -- Trading-day helpers ----------------------------------------------------


async def trading_dates_in(start: date, end: date) -> list[date]:
    """Return distinct dates in institutional_stock between start and end."""
    import asyncpg
    conn = await asyncpg.connect(PG_TRADING_DSN)
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT date
              FROM institutional_stock
             WHERE date BETWEEN $1 AND $2
             ORDER BY date
            """,
            start, end,
        )
    finally:
        await conn.close()
    # Filter out near-empty days (228 holiday returned 3 stocks).
    return [r["date"] for r in rows]


async def close_price_map(tickers: list[str], dates: list[date]) -> dict[tuple[str, date], float]:
    """Return ``{(ticker, date): close_price}`` for all (ticker × date) pairs."""
    import asyncpg
    conn = await asyncpg.connect(PG_TRADING_DSN)
    try:
        rows = await conn.fetch(
            """
            SELECT symbol, date, close_price
              FROM institutional_stock
             WHERE symbol = ANY($1) AND date = ANY($2)
            """,
            tickers, dates,
        )
    finally:
        await conn.close()
    return {(r["symbol"], r["date"]): float(r["close_price"] or 0) for r in rows}


def lookup_forward(prices: dict, ticker: str, all_dates: list[date], as_of: date,
                   horizon: int) -> Optional[float]:
    """Return the (close[D+horizon] / close[D] - 1) return, or None when
    either price is missing/zero or insufficient forward dates exist."""
    try:
        idx = all_dates.index(as_of)
    except ValueError:
        return None
    if idx + horizon >= len(all_dates):
        return None
    p_now = prices.get((ticker, as_of), 0)
    p_fwd = prices.get((ticker, all_dates[idx + horizon]), 0)
    if not p_now or not p_fwd:
        return None
    return p_fwd / p_now - 1


# -- Backtest core ----------------------------------------------------------


async def run_backtest(start: date, end: date, top_n: int) -> dict:
    pool = await db.get_pool()
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone(timedelta(hours=8)))
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=timezone(timedelta(hours=8)))

    print(f"[backtest] picking top-{top_n} newsy universe for {start}..{end}")
    universe = await pick_universe(start_dt, end_dt, top_n)
    print(f"[backtest] universe: {len(universe)} tickers")

    # Pull trading-day calendar from institutional_stock so forward-return
    # math operates on real trading days (no weekend skew).
    extended_end = end + timedelta(days=20)
    cal = await trading_dates_in(start, extended_end)
    print(f"[backtest] trading-day calendar: {len(cal)} days, {cal[0]}..{cal[-1]}")

    # Pre-load all close prices we'll need.
    print(f"[backtest] preloading close prices …")
    prices = await close_price_map(universe, cal)
    print(f"[backtest] close prices: {len(prices)} entries")

    as_of_dates = [d for d in cal if start <= d <= end]
    print(f"[backtest] as_of dates: {len(as_of_dates)}")

    alerts: list[dict] = []
    snapshot_summary: list[dict] = []

    for as_of_d in as_of_dates:
        as_of_dt = datetime.combine(as_of_d, datetime.min.time().replace(hour=18),
                                    tzinfo=timezone(timedelta(hours=8)))
        per_date_alerts = 0

        # Run compute_factors concurrently over the universe. Conservative
        # concurrency (5) because _compute_flow_z opens a new asyncpg
        # connection to trading-timescaledb per call — bursting too many
        # concurrent connects exhausts the server's reservation pool.
        sem = asyncio.Semaphore(5)

        async def one(ticker: str):
            async with sem:
                try:
                    return await compute_factors(ticker, as_of=as_of_dt)
                except Exception as exc:  # noqa: BLE001
                    return {"ticker": ticker, "error": str(exc) or "unnamed"}

        results = await asyncio.gather(*(one(t) for t in universe), return_exceptions=True)

        for r in results:
            if isinstance(r, BaseException):
                continue
            if not isinstance(r, dict) or "factors_hit" not in r:
                continue
            if r["factors_hit"] < MIN_FACTORS_HIT:
                continue
            fwd5 = lookup_forward(prices, r["ticker"], cal, as_of_d, 5)
            fwd10 = lookup_forward(prices, r["ticker"], cal, as_of_d, 10)
            alert = {
                "as_of": as_of_d.isoformat(),
                "ticker": r["ticker"],
                "name": ticker_name(r["ticker"]) or "",
                "flow_z": r["flow"]["z"] if r["flow"] else None,
                "news_z": r["news"]["z"] if r["news"] else None,
                "wiki_heat": r["wikilink"]["heat"],
                "factors_hit": r["factors_hit"],
                "composite": r["composite"],
                "fwd_5d": fwd5,
                "fwd_10d": fwd10,
            }
            alerts.append(alert)
            per_date_alerts += 1

        snapshot_summary.append({
            "date": as_of_d.isoformat(),
            "alerts": per_date_alerts,
        })
        print(f"[backtest] {as_of_d}  alerts={per_date_alerts}")

    return {
        "config": {"start": start.isoformat(), "end": end.isoformat(),
                   "top_n": top_n, "universe_size": len(universe)},
        "snapshots": snapshot_summary,
        "alerts": alerts,
    }


# -- Aggregation + report ---------------------------------------------------


def aggregate(alerts: list[dict]) -> dict:
    """Hit rate, IC, mean returns. Filters out alerts with NULL fwd_10d."""
    valid = [a for a in alerts if a["fwd_10d"] is not None]
    if not valid:
        return {"n_total": len(alerts), "n_with_fwd": 0}

    hits_5pct = sum(1 for a in valid if a["fwd_10d"] > 0.05)
    losses_3pct = sum(1 for a in valid if a["fwd_10d"] < -0.03)
    mean_10d = statistics.mean(a["fwd_10d"] for a in valid)
    median_10d = statistics.median(a["fwd_10d"] for a in valid)

    # Spearman rank IC of composite vs fwd_10d.
    rs = sorted(range(len(valid)), key=lambda i: valid[i]["composite"])
    rank_c = {i: rank for rank, i in enumerate(rs)}
    rs2 = sorted(range(len(valid)), key=lambda i: valid[i]["fwd_10d"])
    rank_r = {i: rank for rank, i in enumerate(rs2)}
    n = len(valid)
    if n > 1:
        d2 = sum((rank_c[i] - rank_r[i]) ** 2 for i in range(n))
        ic = 1 - (6 * d2) / (n * (n * n - 1))
    else:
        ic = 0.0

    return {
        "n_total": len(alerts),
        "n_with_fwd": n,
        "hit_rate_above_5pct": hits_5pct / n,
        "loss_rate_below_neg3pct": losses_3pct / n,
        "mean_fwd_10d": mean_10d,
        "median_fwd_10d": median_10d,
        "ic_composite_vs_fwd_10d": ic,
    }


def render_markdown(result: dict, agg: dict) -> str:
    cfg = result["config"]
    lines = [
        f"# Signal-layer backtest — {datetime.now(timezone(timedelta(hours=8))).date()}",
        "",
        f"Backtest window: **{cfg['start']} → {cfg['end']}**",
        f"Universe: top-**{cfg['top_n']}** electronics tickers by news mentions in window "
        f"(actual = {cfg['universe_size']})",
        "",
        "## Aggregate",
        "",
        f"- Total alerts (factors_hit ≥ 2): **{agg.get('n_total', 0)}**",
        f"- Alerts with forward-10d return available: **{agg.get('n_with_fwd', 0)}**",
    ]
    if agg.get("n_with_fwd"):
        lines += [
            f"- **Hit rate (fwd 10d > +5%): {agg['hit_rate_above_5pct']*100:.1f}%**",
            f"- Loss rate (fwd 10d < −3%): {agg['loss_rate_below_neg3pct']*100:.1f}%",
            f"- Mean fwd 10d return: {agg['mean_fwd_10d']*100:+.2f}%",
            f"- Median fwd 10d return: {agg['median_fwd_10d']*100:+.2f}%",
            f"- Spearman IC (composite vs fwd 10d): **{agg['ic_composite_vs_fwd_10d']:+.3f}**",
        ]

    # Per-snapshot
    lines += ["", "## Daily alert counts", "",
              "| Date | Alerts |", "|---|---:|"]
    for s in result["snapshots"]:
        lines.append(f"| {s['date']} | {s['alerts']} |")

    # Top by composite
    valid = [a for a in result["alerts"] if a["fwd_10d"] is not None]
    top = sorted(valid, key=lambda a: a["composite"], reverse=True)[:10]
    lines += ["", "## Top-10 alerts by composite",
              "",
              "| as_of | ticker | name | flow_z | news_z | wiki | hit | comp | fwd5d | fwd10d |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for a in top:
        flz = f"{a['flow_z']:+.2f}" if a["flow_z"] is not None else "n/a"
        nez = f"{a['news_z']:+.2f}" if a["news_z"] is not None else "n/a"
        f5 = f"{a['fwd_5d']*100:+.1f}%" if a["fwd_5d"] is not None else "n/a"
        f10 = f"{a['fwd_10d']*100:+.1f}%" if a["fwd_10d"] is not None else "n/a"
        lines.append(
            f"| {a['as_of']} | {a['ticker']} | {a['name']} | {flz} | {nez} | "
            f"{a['wiki_heat']} | {a['factors_hit']} | {a['composite']:+.2f} | {f5} | {f10} |"
        )

    # Worst FPs
    worst = sorted(valid, key=lambda a: a["fwd_10d"])[:5]
    lines += ["", "## 5 worst false-positives (most negative fwd 10d)",
              "",
              "| as_of | ticker | name | flow_z | news_z | wiki | comp | fwd10d |",
              "|---|---|---|---:|---:|---:|---:|---:|"]
    for a in worst:
        flz = f"{a['flow_z']:+.2f}" if a["flow_z"] is not None else "n/a"
        nez = f"{a['news_z']:+.2f}" if a["news_z"] is not None else "n/a"
        f10 = f"{a['fwd_10d']*100:+.1f}%" if a["fwd_10d"] is not None else "n/a"
        lines.append(
            f"| {a['as_of']} | {a['ticker']} | {a['name']} | {flz} | {nez} | "
            f"{a['wiki_heat']} | {a['composite']:+.2f} | {f10} |"
        )

    lines += ["", "## Verdict", ""]
    if agg.get("n_with_fwd", 0) < 30:
        lines.append("- **Insufficient data** (< 30 alerts with forward returns). "
                     "Cannot reliably reject or accept the gate.")
    elif agg.get("hit_rate_above_5pct", 0) >= 0.55:
        lines.append("- ✅ Hit rate ≥ 55% — gate is **promotable** to prod cron.")
    elif agg.get("ic_composite_vs_fwd_10d", 0) >= 0.10:
        lines.append("- 🟡 Hit rate < 55% but composite IC ≥ 0.10 — useful as a "
                     "ranking signal even if the binary gate is too loose. "
                     "Consider raising thresholds.")
    else:
        lines.append("- ❌ Neither hit rate nor IC clears thresholds. "
                     "Do **not** promote; iterate on factor formulation first.")

    return "\n".join(lines)


# -- CLI -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--start", required=True, type=lambda s: date.fromisoformat(s))
    p.add_argument("--end", required=True, type=lambda s: date.fromisoformat(s))
    p.add_argument("--top-n", type=int, default=150)
    p.add_argument("--min-fired", type=int, default=2,
                   help="Minimum factors_hit to qualify as alert (default: 2-of-3).")
    p.add_argument("--output", type=Path, default=Path("analysis/reports/backtest_signal.md"))
    p.add_argument("--json", type=Path, default=None,
                   help="Optional: dump raw alert list to JSON for re-analysis.")
    args = p.parse_args(argv)
    global MIN_FACTORS_HIT
    MIN_FACTORS_HIT = args.min_fired

    result = asyncio.run(run_backtest(args.start, args.end, args.top_n))
    agg = aggregate(result["alerts"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(result, agg), encoding="utf-8")
    print(f"[backtest] wrote {args.output}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[backtest] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
