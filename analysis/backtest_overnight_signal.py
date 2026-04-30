"""Backtest the TXF overnight composite signal.

Pulls daily close data for ^TWII, ^GSPC, ^SOX, TSM, TWD=X (yfinance) and
foreign-investor net flow (FinMind `TaiwanStockTotalInstitutionalInvestors`),
aligns them onto TWII trading dates with a 1-day lag (predict day t from
overnight info available at 08:45 TPE), computes per-component and composite
Spearman IC + directional hit rate, and writes a Markdown report.

Pass-bar (from plan):
- Composite Spearman IC >= 0.10 over full sample
- Hit rate >= 54% across at least 500 trading days
- No single component contributes > 70% of weight-squared variance
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "analysis" / "reports"

YF_TICKERS = ["^TWII", "^GSPC", "^SOX", "TSM", "TWD=X"]
DEFAULT_WEIGHTS = {
    "foreign_net": 0.25,
    "usdtwd": -0.15,  # negative — TWD weakening hurts TAIEX
    "sp500": 0.15,
    "tsm": 0.25,
    "sox": 0.20,
}
FINMIND_API = "https://api.finmindtrade.com/api/v4/data"


def fetch_yfinance(start: str, end: str) -> pd.DataFrame:
    """One batched yfinance call for all tickers; returns a Close-price frame."""
    df = yf.download(YF_TICKERS, start=start, end=end, auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"].copy()
    else:
        close = df[["Close"]].rename(columns={"Close": YF_TICKERS[0]})
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close


def fetch_finmind_foreign_net(start: str, end: str) -> pd.Series:
    """Fetch market-wide foreign-investor net buy from FinMind.

    Dataset: TaiwanStockTotalInstitutionalInvestors. Returns one row per TW
    trading day per investor type ('Foreign_Investor', 'Investment_Trust',
    'Dealer'). We pivot to total foreign net (buy - sell) per date.
    """
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start,
        "end_date": end,
    }
    url = f"{FINMIND_API}?{urllib.parse.urlencode(params)}"
    print(f"FinMind GET {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read().decode())
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind error: {payload}")
    rows = payload.get("data") or []
    if not rows:
        raise RuntimeError("FinMind returned no rows for foreign net")
    df = pd.DataFrame(rows)
    df = df[df["name"] == "Foreign_Investor"]
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["foreign_net"] = df["buy"].astype(float) - df["sell"].astype(float)
    s = df.set_index("date")["foreign_net"].sort_index()
    return s


def build_features(close: pd.DataFrame, foreign_net: pd.Series) -> pd.DataFrame:
    """Align features on TWII trading dates with proper 1-day lag.

    Logic: at TPE 08:45 of day t, the latest available info is from US data
    dated <= t-1 (US Mon close becomes available at TPE Tue 04:00, dated Mon).
    We shift US-ticker close-to-close returns forward by 1 calendar day so the
    return that arrived overnight appears under the *next* TPE date.
    """
    ret = close.pct_change()
    twii_target = ret["^TWII"].rename("target")

    us_cols = ["^GSPC", "^SOX", "TSM", "TWD=X"]
    us_ret = ret[us_cols].copy()
    us_ret.index = us_ret.index + pd.Timedelta(days=1)
    us_aligned = us_ret.reindex(twii_target.index, method="ffill").rename(
        columns={"^GSPC": "sp500", "^SOX": "sox", "TSM": "tsm", "TWD=X": "usdtwd"}
    )

    foreign_lagged = foreign_net.shift(1).reindex(twii_target.index, method="ffill")

    feat = pd.concat(
        [
            twii_target,
            us_aligned,
            foreign_lagged.rename("foreign_net"),
        ],
        axis=1,
    )
    feat = feat.dropna()
    return feat


def zscore(s: pd.Series, window: int = 60) -> pd.Series:
    return (s - s.rolling(window).mean()) / s.rolling(window).std(ddof=0)


def per_component_metrics(feat: pd.DataFrame, components: list[str]) -> pd.DataFrame:
    rows = []
    for c in components:
        z = zscore(feat[c]).dropna()
        target = feat["target"].reindex(z.index)
        ic, _ = spearmanr(z, target)
        sign_z = np.sign(z)
        sign_t = np.sign(target)
        valid = (sign_z != 0) & (sign_t != 0)
        hit = (sign_z[valid] == sign_t[valid]).mean()
        rows.append({"component": c, "n": len(z), "spearman_ic": ic, "hit_rate": hit})
    return pd.DataFrame(rows)


def composite_metrics(feat: pd.DataFrame, weights: dict, components: list[str]) -> dict:
    z = pd.DataFrame({c: zscore(feat[c]) for c in components}).dropna()
    target = feat["target"].reindex(z.index)
    composite = sum(weights[c] * z[c] for c in components)
    ic, _ = spearmanr(composite, target)
    sign_c = np.sign(composite)
    sign_t = np.sign(target)
    valid = (sign_c != 0) & (sign_t != 0)
    hit = (sign_c[valid] == sign_t[valid]).mean()
    return {
        "n": len(composite),
        "ic": ic,
        "hit_rate": hit,
        "composite": composite,
        "target": target,
    }


def variance_attribution(weights: dict) -> dict:
    sq = {k: w * w for k, w in weights.items()}
    total = sum(sq.values())
    return {k: v / total for k, v in sq.items()}


def grid_search_weights(feat: pd.DataFrame, components: list[str], step: float = 0.10) -> list[dict]:
    """Brute-force weight grid (sum=1, abs steps); return top 5 by IC.

    Note: we keep usdtwd's sign negative throughout and search abs values.
    """
    z = pd.DataFrame({c: zscore(feat[c]) for c in components}).dropna()
    target = feat["target"].reindex(z.index)

    grid = [round(x, 2) for x in np.arange(0.0, 1.0 + step, step)]
    results = []
    for w_f, w_u, w_s, w_t, w_x in product(grid, repeat=5):
        if abs(w_f + w_u + w_s + w_t + w_x - 1.0) > 1e-9:
            continue
        if max(w_f, w_u, w_s, w_t, w_x) > 0.7:
            continue  # respect variance-attribution cap
        composite = (
            w_f * z["foreign_net"]
            + (-w_u) * z["usdtwd"]
            + w_s * z["sp500"]
            + w_t * z["tsm"]
            + w_x * z["sox"]
        )
        ic, _ = spearmanr(composite, target)
        results.append(
            {
                "foreign_net": w_f,
                "usdtwd": -w_u,
                "sp500": w_s,
                "tsm": w_t,
                "sox": w_x,
                "ic": ic,
            }
        )
    results.sort(key=lambda r: r["ic"], reverse=True)
    return results[:5]


def render_report(
    start: str,
    end: str,
    feat: pd.DataFrame,
    per_comp: pd.DataFrame,
    composite: dict,
    var_attr: dict,
    grid: list[dict],
    pass_bar: dict,
) -> str:
    today = datetime.now().date().isoformat()
    lines = [
        f"# Overnight Composite Signal — Backtest Report ({today})",
        "",
        f"Sample: **{feat.index.min().date()} → {feat.index.max().date()}**, {len(feat)} trading days",
        f"Window: `--start {start}` `--end {end}`",
        "",
        "## Per-Component IC",
        "",
        "| Component | n | Spearman IC | Hit rate |",
        "|---|---:|---:|---:|",
    ]
    for _, r in per_comp.iterrows():
        lines.append(
            f"| `{r['component']}` | {r['n']} | {r['spearman_ic']:+.4f} | {r['hit_rate']*100:.2f}% |"
        )

    lines += [
        "",
        "## Composite (default weights)",
        "",
        "Weights: " + ", ".join(f"`{k}`={v:+.2f}" for k, v in DEFAULT_WEIGHTS.items()),
        "",
        f"- n = **{composite['n']}**",
        f"- Spearman IC = **{composite['ic']:+.4f}**",
        f"- Hit rate = **{composite['hit_rate']*100:.2f}%**",
        "",
        "## Variance attribution (w² / Σw²)",
        "",
        "| Component | Share |",
        "|---|---:|",
    ]
    for k, v in var_attr.items():
        lines.append(f"| `{k}` | {v*100:.1f}% |")

    lines += [
        "",
        "## Grid search — top 5 by IC (10% steps, max single weight ≤ 0.7)",
        "",
        "| foreign | usdtwd | sp500 | tsm | sox | IC |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for r in grid:
        lines.append(
            f"| {r['foreign_net']:.2f} | {r['usdtwd']:+.2f} | {r['sp500']:.2f} | "
            f"{r['tsm']:.2f} | {r['sox']:.2f} | {r['ic']:+.4f} |"
        )

    lines += [
        "",
        "## Pass-Bar Check",
        "",
        f"- Composite IC ≥ 0.10 → **{composite['ic']:+.4f}** → "
        f"{'PASS' if composite['ic'] >= 0.10 else 'FAIL'}",
        f"- Hit rate ≥ 54% → **{composite['hit_rate']*100:.2f}%** → "
        f"{'PASS' if composite['hit_rate'] >= 0.54 else 'FAIL'}",
        f"- N ≥ 500 → **{composite['n']}** → "
        f"{'PASS' if composite['n'] >= 500 else 'FAIL'}",
        f"- Max var-attribution ≤ 70% → **{max(var_attr.values())*100:.1f}%** → "
        f"{'PASS' if max(var_attr.values()) <= 0.70 else 'FAIL'}",
        "",
        f"**Overall: {'PASS — proceed to Phase 2' if pass_bar['ok'] else 'FAIL — abort Phase 2'}**",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--end", default=date.today().isoformat())
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching yfinance {YF_TICKERS} {args.start}..{args.end}", file=sys.stderr)
    close = fetch_yfinance(args.start, args.end)
    print(f"  yfinance: {close.shape[0]} rows, cols={list(close.columns)}", file=sys.stderr)

    finmind_start = (datetime.fromisoformat(args.start) - timedelta(days=10)).date().isoformat()
    foreign_net = fetch_finmind_foreign_net(finmind_start, args.end)
    print(f"  finmind:  {len(foreign_net)} rows", file=sys.stderr)

    feat = build_features(close, foreign_net)
    print(f"Aligned features: {feat.shape}, "
          f"{feat.index.min().date()} → {feat.index.max().date()}", file=sys.stderr)

    components = ["foreign_net", "usdtwd", "sp500", "tsm", "sox"]
    per_comp = per_component_metrics(feat, components)
    composite = composite_metrics(feat, DEFAULT_WEIGHTS, components)
    var_attr = variance_attribution(DEFAULT_WEIGHTS)
    grid = grid_search_weights(feat, components, step=0.10)

    pass_bar = {
        "ok": (
            composite["ic"] >= 0.10
            and composite["hit_rate"] >= 0.54
            and composite["n"] >= 500
            and max(var_attr.values()) <= 0.70
        )
    }
    report = render_report(args.start, args.end, feat, per_comp, composite, var_attr, grid, pass_bar)

    out_path = Path(args.out) if args.out else (
        REPORTS_DIR / f"overnight_signal_backtest_{date.today().isoformat()}.md"
    )
    out_path.write_text(report, encoding="utf-8")
    print(f"\nWrote {out_path}", file=sys.stderr)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
