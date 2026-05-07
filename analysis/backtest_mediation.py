"""Mediation-first backtest: 5 overnight factors → next-month revenue surprise.

Implements rule #1 of the Jay (Two Sigma) 3-rule SOP from epic
https://github.com/leehao921/TW_ElectricDeviceSupplyChain/issues/13.

Why
---
The direct backtest in `analysis/backtest_overnight_signal.py` regresses 5
overnight factors against ^TWII close-to-close return on 803 trading days.
With 5 factors and a noisy daily-return target, that sample has weak
statistical power and is easy to overfit (which is exactly what the implied-
Sharpe check in `scripts/implied_sharpe.py` confirms).

The mediation-first principle: instead of `alt-data → return` (sparse target),
backtest `alt-data → fundamentals` (large panel target) and rely on the well-
validated `fundamentals → return` chain to transitively justify the signal.

What this script does
---------------------
For each of 10 large-cap electronics tickers, pull TaiwanStockMonthRevenue
from FinMind, compute YoY revenue surprise (de-meaned vs trailing-12-month
median of YoY), and Spearman-IC each overnight factor's monthly aggregate
against the *next* month's surprise.

Pass criteria per factor (per the SOP §7):
- |panel_IC| > 0.05  AND  |t_stat| > 2.0
- panel_IC = Spearman ρ across all (month × ticker) observations pooled

Usage:
    python3 analysis/backtest_mediation.py --start 2023-01-01 --as-of 2026-04-29
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "analysis" / "reports"
sys.path.insert(0, str(REPO_ROOT))

from analysis.backtest_overnight_signal import (  # noqa: E402
    fetch_finmind_foreign_net,
    fetch_yfinance,
)

FINMIND_API = "https://api.finmindtrade.com/api/v4/data"
DATASET = "TaiwanStockMonthRevenue"
TICKERS = ["2330", "2317", "2454", "2308", "2382", "3711", "3037", "2303", "2379", "2002"]
FACTORS = ["foreign_net", "usdtwd", "sp500", "tsm", "sox"]
RATE_LIMIT_SLEEP = 0.3  # FinMind free tier
TROLLING_WINDOW = 12  # months for surprise demeaning

PASS_IC = 0.05
PASS_T = 2.0


def fetch_monthly_revenue(ticker: str, start: str, end: str) -> pd.Series:
    params = {"dataset": DATASET, "data_id": ticker, "start_date": start, "end_date": end}
    token = os.getenv("FINMIND_TOKEN")
    if token:
        params["token"] = token
    url = f"{FINMIND_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read().decode())
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind error for {ticker}: {payload.get('msg', payload)}")
    rows = payload.get("data") or []
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    if "revenue_year" in df.columns and "revenue_month" in df.columns:
        df["report_month"] = pd.to_datetime(
            df["revenue_year"].astype(str) + "-" + df["revenue_month"].astype(str).str.zfill(2) + "-01"
        )
    else:
        df["report_month"] = pd.to_datetime(df["date"]).dt.to_period("M").dt.to_timestamp()
    df = df.sort_values("report_month")
    return df.set_index("report_month")["revenue"].astype(float)


def revenue_surprise(rev: pd.Series) -> pd.Series:
    """YoY (12-month) growth, then de-meaned vs trailing-12-month median."""
    yoy = rev / rev.shift(12) - 1.0
    rolling_median = yoy.rolling(window=TROLLING_WINDOW, min_periods=6).median()
    return (yoy - rolling_median).dropna()


def daily_factors_to_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily factors to month-end:

    - foreign_net: sum (it's a flow in 億 TWD per day)
    - usdtwd / sp500 / tsm / sox: sum of daily simple returns
      (close approximation to monthly compounded return for small daily values)
    """
    monthly = pd.DataFrame(index=pd.to_datetime(sorted(set(
        pd.to_datetime(daily.index).to_period("M").to_timestamp()
    ))))
    for col in FACTORS:
        if col == "foreign_net":
            grouped = daily[col].groupby(pd.to_datetime(daily.index).to_period("M")).sum()
        else:
            grouped = daily[col].groupby(pd.to_datetime(daily.index).to_period("M")).sum()
        grouped.index = grouped.index.to_timestamp()
        monthly[col] = grouped.reindex(monthly.index)
    return monthly


def compute_ic_t(x: pd.Series, y: pd.Series) -> tuple[float, float, int]:
    paired = pd.concat([x, y], axis=1, keys=["x", "y"]).dropna()
    if len(paired) < 6:
        return float("nan"), float("nan"), len(paired)
    ic, _ = spearmanr(paired["x"], paired["y"])
    n = len(paired)
    if abs(ic) >= 1.0 or n <= 2:
        t = float("inf") * np.sign(ic) if ic else 0.0
    else:
        t = ic * np.sqrt(n - 2) / np.sqrt(1 - ic * ic)
    return float(ic), float(t), n


def render_report(
    args: argparse.Namespace,
    feat_monthly: pd.DataFrame,
    surprises: dict[str, pd.Series],
    cell_results: dict[str, dict[str, tuple[float, float, int]]],
    panel_results: dict[str, tuple[float, float, int]],
) -> str:
    today = date.today().isoformat()
    lines: list[str] = []
    lines.append(f"# Mediation-First Backtest ({today})")
    lines.append("")
    lines.append(f"Sample window: `--start {args.start}` `--as-of {args.as_of}`")
    lines.append("")
    lines.append("## Stage-1 chain")
    lines.append("")
    lines.append("> alt-data (5 overnight factors) → next-month revenue YoY surprise")
    lines.append(">     (per-ticker IC + pooled panel IC)")
    lines.append("")
    lines.append(f"Universe: {', '.join(TICKERS)}")
    lines.append(f"Surprise = revenue YoY − trailing-{TROLLING_WINDOW}-month median(YoY)")
    lines.append("")
    for f in FACTORS:
        lines.append(f"### Factor: `{f}`")
        lines.append("")
        lines.append("| Ticker | n | IC | t-stat |")
        lines.append("|---|---:|---:|---:|")
        for t in TICKERS:
            ic, tstat, n = cell_results[f].get(t, (float("nan"), float("nan"), 0))
            ic_s = f"{ic:+.3f}" if not np.isnan(ic) else "n/a"
            tt_s = f"{tstat:+.2f}" if not np.isnan(tstat) else "n/a"
            lines.append(f"| {t} | {n} | {ic_s} | {tt_s} |")
        ic, tstat, n = panel_results[f]
        ic_s = f"{ic:+.4f}" if not np.isnan(ic) else "n/a"
        tt_s = f"{tstat:+.2f}" if not np.isnan(tstat) else "n/a"
        lines.append("")
        lines.append(f"**Pooled panel:** n={n}, IC={ic_s}, t-stat={tt_s}")
        passed = (
            (not np.isnan(ic)) and abs(ic) > PASS_IC and (not np.isnan(tstat)) and abs(tstat) > PASS_T
        )
        lines.append(f"**Verdict:** {'✅ PASS' if passed else '❌ FAIL'}")
        lines.append("")
    lines.append("## Composite verdict")
    lines.append("")
    passed_factors = [
        f for f in FACTORS
        if (
            (not np.isnan(panel_results[f][0]))
            and abs(panel_results[f][0]) > PASS_IC
            and (not np.isnan(panel_results[f][1]))
            and abs(panel_results[f][1]) > PASS_T
        )
    ]
    lines.append(f"- Passed factors: {passed_factors or '(none)'}")
    lines.append(f"- Threshold: |panel_IC| > {PASS_IC} AND |t-stat| > {PASS_T}")
    lines.append("")
    if len(passed_factors) >= 1:
        lines.append(
            "**MEDIATION VALIDATED** — at least one overnight factor predicts revenue "
            "surprises with statistical power. The fundamentals→return chain "
            "(Bartov, La Porta) transitively supports the alt-data→return claim "
            "for the passed factors."
        )
    else:
        lines.append(
            "**MEDIATION NOT VALIDATED** — no overnight factor reaches |IC|>0.05 + "
            "|t|>2 against the panel. The high direct-return IC in "
            "`backtest_overnight_signal.py` is *suspect* and likely overfit. "
            "Consider deferring production rollout."
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--as-of", default=date.today().isoformat())
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching daily 5-factor panel ({args.start} → {args.as_of})", file=sys.stderr)
    close = fetch_yfinance(args.start, args.as_of)
    foreign_net = fetch_finmind_foreign_net(args.start, args.as_of)
    daily = pd.DataFrame(index=close.index)
    daily["foreign_net"] = foreign_net.reindex(daily.index, method="ffill")
    daily["usdtwd"] = close["TWD=X"].pct_change()
    daily["sp500"] = close["^GSPC"].pct_change()
    daily["tsm"] = close["TSM"].pct_change()
    daily["sox"] = close["^SOX"].pct_change()
    feat_monthly = daily_factors_to_monthly(daily)

    surprises: dict[str, pd.Series] = {}
    print(f"Fetching monthly revenue for {len(TICKERS)} tickers", file=sys.stderr)
    for t in TICKERS:
        try:
            rev = fetch_monthly_revenue(t, args.start, args.as_of)
            surprises[t] = revenue_surprise(rev)
            print(f"  {t}: {len(surprises[t])} surprise obs", file=sys.stderr)
        except Exception as e:
            print(f"  {t}: ERROR {e}", file=sys.stderr)
            surprises[t] = pd.Series(dtype=float)
        time.sleep(RATE_LIMIT_SLEEP)

    cell_results: dict[str, dict[str, tuple[float, float, int]]] = {f: {} for f in FACTORS}
    panel_pairs: dict[str, list[tuple[float, float]]] = {f: [] for f in FACTORS}
    for f in FACTORS:
        factor_m = feat_monthly[f]
        # predict month M+1 surprise from month M factor
        factor_lagged = factor_m.shift(0)  # month M
        for t, surprise in surprises.items():
            if surprise.empty:
                continue
            target = surprise.shift(-1)  # month M+1 surprise
            ic, tstat, n = compute_ic_t(factor_lagged.reindex(target.index), target)
            cell_results[f][t] = (ic, tstat, n)
            paired = pd.concat([factor_lagged.reindex(target.index), target], axis=1).dropna()
            panel_pairs[f].extend(list(zip(paired.iloc[:, 0], paired.iloc[:, 1])))

    panel_results: dict[str, tuple[float, float, int]] = {}
    for f in FACTORS:
        if not panel_pairs[f]:
            panel_results[f] = (float("nan"), float("nan"), 0)
            continue
        xs = pd.Series([x for x, _ in panel_pairs[f]])
        ys = pd.Series([y for _, y in panel_pairs[f]])
        panel_results[f] = compute_ic_t(xs, ys)

    report = render_report(args, feat_monthly, surprises, cell_results, panel_results)
    out_path = Path(args.out) if args.out else REPORTS_DIR / f"mediation_backtest_{date.today().isoformat()}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"\nWrote {out_path}", file=sys.stderr)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
