"""PMIC Sector Dynamic Factor Model (DFM) with WSTS macro covariate.

Pipeline:
1. Load monthly PMIC panel (10 ticker × 77 months) + WSTS macro features
2. Compute YoY log-return per ticker (12-month lag)
3. Standardize z-score per ticker
4. Align WSTS exog (wsts_yoy_3ma, smoothed for stability) to panel index
5. Fit statsmodels DynamicFactor:
     factor_t = phi * factor_{t-1} + gamma * wsts_yoy_3ma_t + eta_t   (AR(1) + exog)
     y_{i,t} = lambda_i * factor_t + epsilon_{i,t}                     (measurement)
6. Output:
   - data/pmic_efa/dfm_loadings.parquet
   - data/pmic_efa/dfm_smoothed_factors.parquet (Kalman-smoothed)
   - data/pmic_efa/dfm_diagnostics.json (AIC/BIC/log-likelihood/factor AR coef/exog gamma)
   - analysis/charts/2026-06-11_pmic_dfm_factor_trajectory.png (overlay v1 quarterly scores)

Run: python3 scripts/dfm_pmic.py [--k N]
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="statsmodels")

REPO = Path(__file__).resolve().parent.parent
PMIC_DIR = REPO / "data" / "pmic_efa"
CHARTS_DIR = REPO / "analysis" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

MONTHLY_PARQUET = PMIC_DIR / "pmic_monthly_revenue.parquet"
WSTS_FEATURES = PMIC_DIR / "wsts_macro_features.parquet"

YOY_LAG = 12
MIN_MONTHS_PER_TICKER = 36
RANDOM_SEED = 42


def load_monthly_panel() -> tuple[pd.DataFrame, dict]:
    df = pd.read_parquet(MONTHLY_PARQUET)
    rev = df[(df.tag == "revenue") & (df.val_unit == "TWD_M")].copy()
    rev["end"] = pd.to_datetime(rev["end"]).dt.normalize()
    rev = rev[["end", "entity_id", "entity_name", "val"]].drop_duplicates(
        subset=["end", "entity_id"], keep="last"
    )
    name_map = (
        rev.drop_duplicates("entity_id")
        .set_index("entity_id")["entity_name"]
        .to_dict()
    )
    panel = rev.pivot(index="end", columns="entity_id", values="val").sort_index()
    return panel, name_map


def load_wsts_exog(feature_tag: str = "wsts_yoy_3ma") -> pd.Series:
    df = pd.read_parquet(WSTS_FEATURES)
    s = df[df.tag == feature_tag].copy()
    s["end"] = pd.to_datetime(s["end"]).dt.normalize()
    return s.set_index("end")["val"].sort_index().rename(feature_tag)


def main(args):
    print("=" * 72)
    print("PMIC Sector Dynamic Factor Model — monthly + WSTS exogenous")
    print("=" * 72)

    panel, name_map = load_monthly_panel()
    print(f"Monthly panel: {panel.shape[0]} months × {panel.shape[1]} tickers")
    print(f"Window: {panel.index.min().date()} → {panel.index.max().date()}")

    # YoY log return
    yoy = np.log(panel / panel.shift(YOY_LAG))
    # Drop early rows where lag undefined
    yoy = yoy.dropna(how="all")
    # Drop tickers with < MIN_MONTHS
    cols_keep = yoy.notna().sum(axis=0) >= MIN_MONTHS_PER_TICKER
    yoy = yoy.loc[:, cols_keep]
    yoy = yoy.dropna()  # require all tickers
    print(f"YoY panel (trimmed): {yoy.shape[0]} months × {yoy.shape[1]} tickers")

    # Standardize
    std_yoy = (yoy - yoy.mean()) / yoy.std(ddof=1)

    # WSTS exog aligned to panel
    wsts = load_wsts_exog(args.exog_tag)
    exog = wsts.reindex(std_yoy.index).to_frame()
    exog_z = (exog - exog.mean()) / exog.std(ddof=1)
    print(f"Exog ({args.exog_tag}) aligned: {exog_z.shape}, "
          f"missing={exog_z.isna().sum().iloc[0]}")
    if exog_z.isna().any().any():
        # Forward-fill any missing (last month may lag if WSTS not yet released)
        exog_z = exog_z.ffill()
        print("  → forward-filled missing exog values")

    # Fit DFM
    from statsmodels.tsa.statespace.dynamic_factor import DynamicFactor

    np.random.seed(RANDOM_SEED)
    print()
    print(f"--- Fitting DFM (k={args.k}, factor_order=1, exog=WSTS) ---")
    try:
        model = DynamicFactor(
            endog=std_yoy.values,
            k_factors=args.k,
            factor_order=1,
            exog=exog_z.values,
            error_cov_type="diagonal",
            error_order=0,
            enforce_stationarity=True,
        )
        res = model.fit(method="lbfgs", maxiter=200, disp=False)
    except Exception as e:
        print(f"DFM fit failed: {e}", file=sys.stderr)
        print("Trying without exog...", file=sys.stderr)
        model = DynamicFactor(
            endog=std_yoy.values,
            k_factors=args.k,
            factor_order=1,
            error_cov_type="diagonal",
            error_order=0,
            enforce_stationarity=True,
        )
        res = model.fit(method="lbfgs", maxiter=200, disp=False)

    # Convergence
    print(f"Converged: {res.mle_retvals.get('converged', 'unknown')}")
    print(f"Log-likelihood: {res.llf:.2f}")
    print(f"AIC: {res.aic:.2f}, BIC: {res.bic:.2f}")

    # Extract loadings via design matrix (state-space Λ)
    # res.filter_results.design shape: (k_endog, k_factors, n_obs); time-invariant → take [..., 0]
    loadings_arr = res.filter_results.design[..., 0]
    loadings = pd.DataFrame(
        loadings_arr,
        index=std_yoy.columns,
        columns=[f"F{i+1}" for i in range(args.k)],
    )

    # Pull params via model.param_names lookup
    param_names = res.model.param_names
    params_series = pd.Series(res.params, index=param_names)

    # AR(1) coefficient on factor(s)
    factor_ar = {}
    for f in range(args.k):
        for f2 in range(args.k):
            param_name = f"L1.f{f+1}.f{f2+1}"
            if param_name in params_series.index:
                factor_ar[f"phi_F{f+1}_to_F{f2+1}"] = float(params_series[param_name])

    # Exog beta — statsmodels DFM puts exog in the OBSERVATION equation,
    # one beta per ticker:  y_i,t = λ_i × F_t + β_i × WSTS_t + ε_i,t
    # β_i is the DIRECT effect of WSTS on ticker i, beyond what factor captures.
    exog_beta = {}
    for j in range(std_yoy.shape[1]):
        param_name = f"beta.x1.y{j+1}"
        if param_name in params_series.index:
            ticker = std_yoy.columns[j]
            exog_beta[ticker] = float(params_series[param_name])

    # Kalman-smoothed factor scores
    smoothed = pd.DataFrame(
        res.smoothed_state[: args.k].T,
        index=std_yoy.index,
        columns=[f"F{i+1}" for i in range(args.k)],
    )

    print()
    print("--- DFM loadings (Λ matrix) ---")
    loadings_print = loadings.copy()
    loadings_print["ticker_name"] = [name_map.get(t, "") for t in loadings_print.index]
    loadings_print = loadings_print.reindex(
        loadings_print["F1"].abs().sort_values(ascending=False).index
    )
    print(loadings_print.to_string(float_format="%+.3f"))

    print()
    print("--- Factor AR(1) coefficients ---")
    for k, v in factor_ar.items():
        print(f"  {k} = {v:+.3f}")

    print()
    print("--- Exog beta (WSTS direct effect on each ticker, beyond factor) ---")
    print("  (positive β = ticker responds directly to WSTS in addition to common factor)")
    exog_beta_sorted = sorted(exog_beta.items(), key=lambda x: -abs(x[1]))
    for ticker, beta in exog_beta_sorted:
        print(f"  {ticker} ({name_map.get(ticker, '')}): β = {beta:+.3f}")

    # Cross-check with v1 quarterly factor scores
    v1_scores_path = PMIC_DIR / "factor_scores.parquet"
    if v1_scores_path.exists():
        v1 = pd.read_parquet(v1_scores_path)
        v1["period"] = pd.to_datetime(v1.get("period", v1.get("quarter")))
        v1 = v1.set_index("period").sort_index()
        # Resample monthly DFM scores to quarterly to compare
        dfm_q = smoothed.resample("QE").mean()
        # Sign-align (DFM may have flipped sign vs v1)
        common = dfm_q.index.intersection(v1.index)
        if len(common) >= 4:
            corr_signed = np.corrcoef(
                dfm_q.loc[common, "F1"], v1.loc[common, "F1"]
            )[0, 1]
            # Use |corr| since EFA factor sign is arbitrary
            print()
            print(f"--- v1 vs v2 sanity check ---")
            print(f"Pearson corr(DFM F1 quarterly avg, v1 EFA F1) over {len(common)} quarters: {corr_signed:+.3f}")
            print(f"|corr| = {abs(corr_signed):.3f} (target > 0.7 for confirmation)")

    # Persist outputs
    loadings_out = loadings.reset_index().rename(columns={"index": "entity_id"})
    loadings_out["entity_name"] = loadings_out["entity_id"].map(name_map)
    loadings_out.to_parquet(PMIC_DIR / "dfm_loadings.parquet", index=False)
    print(f"Wrote {PMIC_DIR / 'dfm_loadings.parquet'}")

    smoothed_out = smoothed.reset_index().rename(columns={"end": "month"})
    smoothed_out.to_parquet(PMIC_DIR / "dfm_smoothed_factors.parquet", index=False)
    print(f"Wrote {PMIC_DIR / 'dfm_smoothed_factors.parquet'}")

    diagnostics = {
        "k_factors": args.k,
        "n_obs": int(std_yoy.shape[0]),
        "n_vars": int(std_yoy.shape[1]),
        "tickers": list(std_yoy.columns),
        "exog_tag": args.exog_tag,
        "window_start": str(std_yoy.index.min().date()),
        "window_end": str(std_yoy.index.max().date()),
        "log_likelihood": float(res.llf),
        "aic": float(res.aic),
        "bic": float(res.bic),
        "converged": bool(res.mle_retvals.get("converged", False)),
        "factor_ar_coefficients": factor_ar,
        "exog_beta_per_ticker": exog_beta,
    }
    with open(PMIC_DIR / "dfm_diagnostics.json", "w") as f:
        json.dump(diagnostics, f, indent=2)
    print(f"Wrote {PMIC_DIR / 'dfm_diagnostics.json'}")

    # Plot DFM factor trajectory
    fig, ax = plt.subplots(args.k, 1, figsize=(11, 3 * args.k), sharex=True)
    if args.k == 1:
        ax = [ax]
    for i in range(args.k):
        ax[i].plot(smoothed.index, smoothed[f"F{i+1}"], lw=1.5, color=f"C{i}")
        ax[i].axhline(0, color="gray", ls=":", alpha=0.5)
        ax[i].axhline(0.5, color="green", ls="--", alpha=0.4, label="+0.5σ threshold")
        ax[i].axhline(-0.5, color="red", ls="--", alpha=0.4)
        ax[i].set_ylabel(f"Factor {i+1} (smoothed)")
        ax[i].grid(alpha=0.3)
        ax[i].legend(loc="upper left", fontsize=8)
    ax[-1].set_xlabel("Month")
    fig.suptitle(f"PMIC DFM monthly smoothed factors (k={args.k}, exog=WSTS)")
    plt.tight_layout()
    out_path = CHARTS_DIR / "2026-06-11_pmic_dfm_factor_trajectory.png"
    plt.savefig(out_path, dpi=120)
    plt.close()
    print(f"Wrote {out_path}")

    print()
    print("=" * 72)
    print("DFM pipeline complete.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--k", type=int, default=2, help="Number of factors (default 2 from EFA Horn)")
    p.add_argument(
        "--exog-tag",
        default="wsts_yoy_3ma",
        choices=["wsts_yoy", "wsts_yoy_3ma", "wsts_level_zscore"],
        help="WSTS feature to use as exogenous covariate",
    )
    main(p.parse_args())
