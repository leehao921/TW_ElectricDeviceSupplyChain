"""Verify a quant claim ('z = …σ', 'percentile …', 'extreme', 'rare') against
historical distribution before publishing it.

Pulls market-wide 三大法人 daily flow from FinMind
(`TaiwanStockTotalInstitutionalInvestors`), restricts to a trailing N-trading-day
window ending at `--as-of`, and reports:
  - mean / std / min / max of single-day flow
  - rolling K-day-sum mean / std / min / max
  - z-score and percentile rank of the user-supplied value (or sum of values)
  - the K worst comparable windows in the same lookback

Usage:
    python3 scripts/verify_flow_zscore.py \
        --metric foreign_net \
        --values "-511.96,-392.98,-481.47" \
        --window 60 \
        --as-of 2026-04-29

The `--values` flag accepts a comma-separated list of 億-TWD daily values; the
script sums them to test against the K-day rolling distribution where K equals
the count of values you pass. A single value tests against the 1-day distribution.

Output is printable text intended to be pasted into an analysis report's
verification footnote, e.g.:

    z = −1.04σ vs 60d rolling-3d distribution (percentile = 15.5%, lower-tail).
    Comparable historical windows: 2026-03-05 (−2,428億), 2026-03-04 (−2,303億).
"""
from __future__ import annotations

import argparse
import bisect
import json
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

FINMIND_API = "https://api.finmindtrade.com/api/v4/data"
METRIC_NAMES = {
    "foreign_net": "Foreign_Investor",
    "trust_net": "Investment_Trust",
    "dealer_net": "Dealer",
}


def fetch_flow(metric: str, start: date, end: date) -> list[tuple[str, float]]:
    name = METRIC_NAMES[metric]
    url = f"{FINMIND_API}?{urllib.parse.urlencode({'dataset': 'TaiwanStockTotalInstitutionalInvestors', 'start_date': start.isoformat(), 'end_date': end.isoformat()})}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read().decode())
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind error: {payload}")
    rows = []
    for it in payload.get("data") or []:
        if it["name"] == name:
            v_yi = (it["buy"] - it["sell"]) / 1e8
            rows.append((it["date"], v_yi))
    rows.sort()
    return rows


def rolling_sums(values: list[float], k: int) -> list[float]:
    return [sum(values[i - k + 1: i + 1]) for i in range(k - 1, len(values))]


def parse_values(raw: str) -> list[float]:
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--metric", choices=list(METRIC_NAMES.keys()), default="foreign_net")
    p.add_argument("--values", required=True,
                   help="Comma-separated daily values in 億 TWD (sign included)")
    p.add_argument("--window", type=int, default=60,
                   help="Trailing N trading days for the historical distribution")
    p.add_argument("--as-of", default=date.today().isoformat(),
                   help="End-date for the window (YYYY-MM-DD)")
    args = p.parse_args(argv)

    end = datetime.fromisoformat(args.as_of).date()
    start = end - timedelta(days=int(args.window * 1.6) + 30)
    rows = fetch_flow(args.metric, start, end)
    dates = [r[0] for r in rows]
    vals = [r[1] for r in rows]

    if len(vals) < args.window + 1:
        raise SystemExit(f"insufficient history: got {len(vals)} obs, need {args.window+1}")
    win_dates = dates[-args.window:]
    win_vals = vals[-args.window:]

    user_vals = parse_values(args.values)
    k = len(user_vals)
    user_sum = sum(user_vals)

    if k == 1:
        ref_pop = win_vals
        ref_label = "1-day"
    else:
        ref_pop = rolling_sums(win_vals, k)
        ref_label = f"rolling-{k}d-sum"

    mu = statistics.mean(ref_pop)
    sd = statistics.pstdev(ref_pop)
    z = (user_sum - mu) / sd if sd > 0 else float("inf")
    sorted_pop = sorted(ref_pop)
    rank = bisect.bisect_left(sorted_pop, user_sum)
    pct = rank / len(sorted_pop) * 100

    print(f"# Verification report — {args.metric} ({args.as_of}, trailing {args.window} TD)")
    print()
    print(f"Window: {win_dates[0]} → {win_dates[-1]} ({len(win_vals)} obs)")
    print(f"Tested value: {ref_label} = **{user_sum:+.2f} 億**  (k={k} day{'s' if k>1 else ''})")
    print()
    print(f"## Distribution stats ({ref_label}, n={len(ref_pop)})")
    print(f"  mean = {mu:+.2f} 億")
    print(f"  std  = {sd:.2f} 億")
    print(f"  min  = {min(ref_pop):+.2f} 億")
    print(f"  max  = {max(ref_pop):+.2f} 億")
    print()
    print(f"## Verdict")
    print(f"  z-score   = **{z:+.3f} σ**")
    print(f"  percentile = **{pct:.1f}%** ({'lower' if z < 0 else 'upper'} tail)")
    side = "below" if z < 0 else "above"

    if abs(z) >= 3.0:
        flag = "✅ TRUE 3σ — extreme tail event"
    elif abs(z) >= 2.0:
        flag = "⚠️ 2σ — uncommon, ~5% probability"
    elif abs(z) >= 1.0:
        flag = "🟡 1σ — moderately heavy, ~15-30% probability"
    else:
        flag = "⚪ within 1σ — normal-range fluctuation"
    print(f"  classification = {flag}")
    print()
    print(f"## Worst {min(5, len(ref_pop))} comparable windows in this lookback")
    if k == 1:
        labelled = sorted(zip(ref_pop, win_dates))[:5]
    else:
        end_dates_for_windows = win_dates[k - 1:]
        labelled = sorted(zip(ref_pop, end_dates_for_windows))[:5]
    for v, d in labelled:
        ratio = v / user_sum if user_sum != 0 else 0
        print(f"  end={d}  {ref_label} = {v:+8.2f} 億  ({ratio:.2f}× of tested)")
    print()
    print(f"## Suggested wording")
    if abs(z) < 1.0:
        print(f"  '{user_sum:+.0f} 億 ({ref_label}) → 60d 內 normal range'")
    elif abs(z) < 2.0:
        print(f"  'z = {z:+.2f}σ vs 60d {ref_label} 分布 ({pct:.1f} percentile {side})'")
    else:
        print(f"  '*** {abs(z):.1f}σ EXTREME *** vs 60d {ref_label} 分布'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
