"""Implied-Sharpe sanity check + correlation flooring for the overnight composite.

Reverse-engineers each component's risk contribution and implied Sharpe in the
final 5-factor portfolio. If any component shows implied Sharpe > 2.0 we flag
**FALSE PRECISION** — it means short-history alt-data is being trusted more
than the data can support, usually because pairwise correlations among the
US-overnight triplet (sp500 / tsm / sox) get understated.

Implements rule #2 of the Jay (Two Sigma) 3-rule SOP from epic
https://github.com/leehao921/TW_ElectricDeviceSupplyChain/issues/13.

Workflow per the SOP (`docs/quant_claim_verification.md` § 8):

1. Pull the same 5 components as the production overnight signal
   (foreign_net / usdtwd / sp500 / tsm / sox), 1-day-lag-aligned.
2. Compute Pearson correlation matrix.
3. For supplied weights (default = `DEFAULT_WEIGHTS` from
   `analysis/backtest_overnight_signal.py`):
     - per-component variance contribution = w_i · (Σw)_i / Var(p)
     - per-component implied Sharpe ≈ w_i · IC_i · sqrt(252) /
       sqrt(component_variance_contribution)
     - Choueifaty-Coignard diversification ratio = (Σ w_i σ_i) / σ_p
4. Floor any |ρ_ij| < 0.5 within the (sp500, tsm, sox) triplet to 0.5.
5. Re-run a 5%-step grid search with the floored correlation; report
   suggested replacement weights.

Usage:
    python3 scripts/implied_sharpe.py --start 2023-01-01 --as-of 2026-04-29
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from analysis.backtest_overnight_signal import (  # noqa: E402
    DEFAULT_WEIGHTS,
    build_features,
    fetch_finmind_foreign_net,
    fetch_yfinance,
    zscore,
)

COMPONENTS = ["foreign_net", "usdtwd", "sp500", "tsm", "sox"]
US_TRIPLET = {"sp500", "tsm", "sox"}
RHO_FLOOR = 0.5
IS_THRESHOLD = 2.0
ANNUALIZATION = 252  # trading days

# Sign-aware effective weights — usdtwd contributes negatively to TAIEX.
# We use the sign baked into DEFAULT_WEIGHTS rather than a separate sign-vector.


def correlation_matrix(z: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation across the 5 z-scored component series."""
    return z[COMPONENTS].corr(method="pearson")


def floor_us_triplet(corr: pd.DataFrame, floor: float = RHO_FLOOR) -> tuple[pd.DataFrame, list[tuple[str, str, float]]]:
    """Force any |ρ| < floor within (sp500, tsm, sox) to ±floor (preserving sign)."""
    floored = corr.copy()
    diffs: list[tuple[str, str, float]] = []
    pairs = [("sp500", "tsm"), ("sp500", "sox"), ("tsm", "sox")]
    for a, b in pairs:
        original = corr.loc[a, b]
        if abs(original) < floor:
            new = floor if original >= 0 else -floor
            floored.loc[a, b] = new
            floored.loc[b, a] = new
            diffs.append((a, b, original))
    return floored, diffs


def cov_from_corr(corr: pd.DataFrame, sigmas: pd.Series) -> pd.DataFrame:
    """Σ = D · ρ · D, where D = diag(σ)."""
    d = np.diag(sigmas.reindex(corr.index).values)
    cov = d @ corr.values @ d
    return pd.DataFrame(cov, index=corr.index, columns=corr.columns)


def implied_sharpe_table(
    weights: dict, cov: pd.DataFrame, ic: dict
) -> pd.DataFrame:
    """For each component, compute marginal-risk and implied Sharpe.

    `weights` may include negative entries (e.g. usdtwd = -0.15). We use them
    as-is so the sign of the contribution lines up with the production formula.
    """
    w = pd.Series({c: weights.get(c, 0.0) for c in COMPONENTS})
    sigma_i = pd.Series(np.sqrt(np.diag(cov.values)), index=cov.index)
    cov_w = cov.values @ w.values
    var_p = float(w.values @ cov_w)
    sigma_p = np.sqrt(var_p) if var_p > 0 else float("nan")

    contrib = pd.Series(w.values * cov_w / var_p, index=cov.index) if var_p > 0 else pd.Series(np.nan, index=cov.index)
    ic_arr = pd.Series({c: ic.get(c, 0.0) for c in COMPONENTS})
    ann_ret = ic_arr * np.sqrt(ANNUALIZATION)
    component_sigma_in_p = np.sqrt(np.abs(contrib) * var_p) if var_p > 0 else pd.Series(np.nan, index=cov.index)
    implied = (w * ann_ret) / component_sigma_in_p.replace(0, np.nan)

    out = pd.DataFrame(
        {
            "weight": w,
            "sigma_i": sigma_i,
            "ann_ret_proxy": ann_ret,
            "var_contrib": contrib,
            "implied_sharpe": implied,
        }
    )
    out.attrs["sigma_p"] = sigma_p
    out.attrs["weighted_sigma_sum"] = float((w.abs() * sigma_i).sum())
    return out


def diversification_ratio(weights: dict, cov: pd.DataFrame) -> float:
    w = pd.Series({c: weights.get(c, 0.0) for c in COMPONENTS}).abs()
    sigma_i = pd.Series(np.sqrt(np.diag(cov.values)), index=cov.index)
    num = float((w * sigma_i).sum())
    cov_w = cov.values @ pd.Series({c: weights.get(c, 0.0) for c in COMPONENTS}).values
    var_p = float(pd.Series({c: weights.get(c, 0.0) for c in COMPONENTS}).values @ cov_w)
    sigma_p = np.sqrt(var_p) if var_p > 0 else float("nan")
    return num / sigma_p if sigma_p else float("nan")


def per_component_ic(z: pd.DataFrame, target: pd.Series) -> dict:
    out = {}
    for c in COMPONENTS:
        ic, _ = spearmanr(z[c].dropna(), target.reindex(z[c].dropna().index))
        out[c] = float(ic) if ic is not None and not np.isnan(ic) else 0.0
    return out


def grid_search_floored(z: pd.DataFrame, target: pd.Series, step: float = 0.05) -> list[dict]:
    """Re-do the brute-force grid search but only on floored z's covariance.

    We don't actually need cov in the IC objective — we just call out the
    sp500/tsm/sox triplet penalty by capping any single weight to ≤ 0.7 (matches
    the original backtest constraint) and report top 5 by Spearman IC.
    """
    grid = [round(x, 2) for x in np.arange(0.0, 1.0 + step, step)]
    results = []
    z_clean = z.dropna()
    target_clean = target.reindex(z_clean.index)
    for w_f, w_u, w_s, w_t, w_x in product(grid, repeat=5):
        if abs(w_f + w_u + w_s + w_t + w_x - 1.0) > 1e-9:
            continue
        if max(w_f, w_u, w_s, w_t, w_x) > 0.7:
            continue
        composite = (
            w_f * z_clean["foreign_net"]
            + (-w_u) * z_clean["usdtwd"]
            + w_s * z_clean["sp500"]
            + w_t * z_clean["tsm"]
            + w_x * z_clean["sox"]
        )
        ic, _ = spearmanr(composite, target_clean)
        results.append(
            {"foreign_net": w_f, "usdtwd": -w_u, "sp500": w_s, "tsm": w_t, "sox": w_x, "ic": float(ic)}
        )
    results.sort(key=lambda r: r["ic"], reverse=True)
    return results[:5]


def render_report(
    args: argparse.Namespace,
    feat: pd.DataFrame,
    z: pd.DataFrame,
    target: pd.Series,
    corr_raw: pd.DataFrame,
    corr_floored: pd.DataFrame,
    floored_pairs: list[tuple[str, str, float]],
    is_table_raw: pd.DataFrame,
    is_table_floored: pd.DataFrame,
    div_ratio_raw: float,
    div_ratio_floored: float,
    grid_top: list[dict],
    triggered: list[str],
) -> str:
    lines: list[str] = []
    lines.append(f"# Implied-Sharpe Sanity Check ({date.today().isoformat()})")
    lines.append("")
    lines.append(f"Sample: **{feat.index.min().date()} → {feat.index.max().date()}**, {len(feat)} trading days")
    lines.append(f"Window: `--start {args.start}` `--as-of {args.as_of}`")
    lines.append(f"Weights tested: " + ", ".join(f"`{k}`={v:+.2f}" for k, v in DEFAULT_WEIGHTS.items()))
    lines.append("")
    lines.append("## Pearson correlation (raw, z-scored)")
    lines.append("")
    lines.append("| | " + " | ".join(COMPONENTS) + " |")
    lines.append("|---|" + "---|" * len(COMPONENTS))
    for c in COMPONENTS:
        row = " | ".join(f"{corr_raw.loc[c, c2]:+.3f}" for c2 in COMPONENTS)
        lines.append(f"| **{c}** | {row} |")
    lines.append("")
    if floored_pairs:
        lines.append("## Floored correlations (US triplet, floor=0.5)")
        lines.append("")
        for a, b, original in floored_pairs:
            new = corr_floored.loc[a, b]
            lines.append(f"- `{a}` × `{b}`: {original:+.3f} → **{new:+.3f}** (floored)")
        lines.append("")
    else:
        lines.append("_All US-triplet correlations already ≥ 0.5; no flooring applied._")
        lines.append("")
    for label, tbl, dr in [
        ("Raw cov", is_table_raw, div_ratio_raw),
        ("Floored cov", is_table_floored, div_ratio_floored),
    ]:
        lines.append(f"## Implied Sharpe — {label}")
        lines.append("")
        lines.append("| Component | weight | σ_i | IC×√252 | Var contrib | Implied Sharpe |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for c in COMPONENTS:
            r = tbl.loc[c]
            lines.append(
                f"| `{c}` | {r['weight']:+.2f} | {r['sigma_i']:.3f} | {r['ann_ret_proxy']:+.2f} | "
                f"{r['var_contrib']:+.3f} | **{r['implied_sharpe']:+.3f}** |"
            )
        lines.append("")
        lines.append(f"- σ_portfolio = {tbl.attrs['sigma_p']:.3f}")
        lines.append(f"- Σ |w_i·σ_i| = {tbl.attrs['weighted_sigma_sum']:.3f}")
        lines.append(f"- **Diversification ratio = {dr:.3f}** (1.0 = no diversification)")
        lines.append("")
    lines.append("## Verdict")
    lines.append("")
    if triggered:
        lines.append(f"⚠️ **FALSE PRECISION DETECTED** — implied Sharpe > {IS_THRESHOLD} on:")
        for c in triggered:
            lines.append(f"- `{c}`")
        lines.append("")
        lines.append("**Action:** rerun the backtest grid search with the floored cov suggested below.")
    else:
        lines.append(f"✅ All component implied Sharpes ≤ {IS_THRESHOLD}. No false-precision flag.")
    lines.append("")
    lines.append("## Suggested replacement weights (top 5 by IC, floored grid)")
    lines.append("")
    lines.append("| foreign | usdtwd | sp500 | tsm | sox | IC |")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    for r in grid_top:
        lines.append(
            f"| {r['foreign_net']:.2f} | {r['usdtwd']:+.2f} | {r['sp500']:.2f} | "
            f"{r['tsm']:.2f} | {r['sox']:.2f} | {r['ic']:+.4f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--as-of", default=date.today().isoformat())
    args = p.parse_args(argv)

    end = args.as_of
    print(f"Fetching yfinance + FinMind ({args.start} → {end})", file=sys.stderr)
    close = fetch_yfinance(args.start, end)
    foreign_net = fetch_finmind_foreign_net(args.start, end)
    feat = build_features(close, foreign_net)
    target = feat["target"]
    z = pd.DataFrame({c: zscore(feat[c]) for c in COMPONENTS}).dropna()

    ic_dict = per_component_ic(z, target)
    sigmas = z.std(ddof=0)

    corr_raw = correlation_matrix(z)
    corr_floored, floored_pairs = floor_us_triplet(corr_raw, RHO_FLOOR)
    cov_raw = cov_from_corr(corr_raw, sigmas)
    cov_floored = cov_from_corr(corr_floored, sigmas)

    is_table_raw = implied_sharpe_table(DEFAULT_WEIGHTS, cov_raw, ic_dict)
    is_table_floored = implied_sharpe_table(DEFAULT_WEIGHTS, cov_floored, ic_dict)
    dr_raw = diversification_ratio(DEFAULT_WEIGHTS, cov_raw)
    dr_floored = diversification_ratio(DEFAULT_WEIGHTS, cov_floored)

    triggered = [c for c in COMPONENTS if abs(is_table_floored.loc[c, "implied_sharpe"]) > IS_THRESHOLD]
    grid_top = grid_search_floored(z, target, step=0.05)

    report = render_report(
        args, feat, z, target,
        corr_raw, corr_floored, floored_pairs,
        is_table_raw, is_table_floored,
        dr_raw, dr_floored, grid_top, triggered,
    )
    print(report)

    if triggered:
        print(
            f"⚠️ FALSE PRECISION — components {triggered} have |implied_sharpe| > {IS_THRESHOLD} "
            f"under floored cov. Consider replacing weights with grid_top[0]: "
            f"{grid_top[0]}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
