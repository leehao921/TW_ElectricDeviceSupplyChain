"""PMIC Sector Exploratory Factor Analysis.

Pipeline:
1. Load 4 worker parquets (core4 + tail3 + china + context)
2. Filter tag='revenue', pivot to wide: rows=quarter, cols=ticker, values=YoY log-return
3. Drop tickers with <18 quarters; drop quarters with <8 tickers
4. Standardize (z-score)
5. KMO test (≥0.6 to proceed) + Bartlett sphericity (p<0.001)
6. Horn parallel analysis → choose k factors
7. Fit FactorAnalyzer with Varimax (or Promax if inter-factor corr >0.3)
8. Write rotated loadings + diagnostics + charts

Outputs:
- data/pmic_efa/loadings.parquet
- data/pmic_efa/factor_scores.parquet
- data/pmic_efa/efa_diagnostics.json
- analysis/charts/2026-06-10_pmic_corr_heatmap.png
- analysis/charts/2026-06-10_pmic_parallel_analysis.png
- analysis/charts/2026-06-10_pmic_loadings.png

Run: python3 scripts/efa_pmic.py [--k N] [--rotation varimax|promax]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from factor_analyzer import FactorAnalyzer
from factor_analyzer.factor_analyzer import (
    calculate_bartlett_sphericity,
    calculate_kmo,
)

REPO = Path(__file__).resolve().parent.parent
PMIC_DIR = REPO / "data" / "pmic_efa"
CHARTS_DIR = REPO / "analysis" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

QUARTERLY_PARQUETS = [
    "pmic_core4_quarterly.parquet",
    "pmic_tail3_quarterly.parquet",
    "pmic_china_quarterly.parquet",
    "pmic_context_quarterly.parquet",
]

MONTHLY_PARQUETS = [
    "pmic_monthly_revenue.parquet",
]

# Frequency-dependent thresholds
FREQ_CONFIG = {
    "quarterly": {
        "parquets": QUARTERLY_PARQUETS,
        "lag": 4,                         # YoY = 4-quarter shift
        "min_obs_per_ticker": 18,         # 4.5 years quarterly
        "min_tickers_per_obs": 5,
        "out_suffix": "",                  # legacy v1 outputs
    },
    "monthly": {
        "parquets": MONTHLY_PARQUETS,
        "lag": 12,                        # YoY = 12-month shift
        "min_obs_per_ticker": 36,         # 3 years monthly
        "min_tickers_per_obs": 6,
        "out_suffix": "_monthly",
    },
}

KMO_THRESHOLD = 0.6
BARTLETT_THRESHOLD = 0.001
OBLIQUE_TRIGGER_CORR = 0.30
RANDOM_SEED = 42


def load_all(parquets) -> pd.DataFrame:
    frames = []
    for fname in parquets:
        p = PMIC_DIR / fname
        if not p.exists():
            print(f"WARN: {p.name} missing — skipping", file=sys.stderr)
            continue
        frames.append(pd.read_parquet(p))
    if not frames:
        sys.exit("No PMIC parquets found")
    return pd.concat(frames, ignore_index=True)


def build_revenue_panel(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Pivot revenue → wide (rows=period, cols=ticker). Filter to local currency rows."""
    rev = df[(df.tag == "revenue") & (df.val_unit.isin(["TWD_M", "CNY_M"]))].copy()
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


def to_yoy_log(panel: pd.DataFrame, lag: int) -> pd.DataFrame:
    """YoY log-return: log(rev_t / rev_{t-lag})."""
    return np.log(panel / panel.shift(lag))


def trim_panel(yoy: pd.DataFrame, min_obs: int, min_tickers: int) -> pd.DataFrame:
    """Drop tickers with <min_obs and obs with <min_tickers."""
    cols_keep = yoy.notna().sum(axis=0) >= min_obs
    yoy = yoy.loc[:, cols_keep]
    rows_keep = yoy.notna().sum(axis=1) >= min_tickers
    yoy = yoy.loc[rows_keep]
    yoy = yoy.dropna()
    return yoy


def parallel_analysis(
    n_obs: int, n_vars: int, n_iter: int = 1000, percentile: int = 95
) -> np.ndarray:
    """Horn's parallel analysis. Returns 95-percentile eigenvalues of random data."""
    rng = np.random.default_rng(RANDOM_SEED)
    eig_dist = np.zeros((n_iter, n_vars))
    for i in range(n_iter):
        random_data = rng.standard_normal((n_obs, n_vars))
        random_corr = np.corrcoef(random_data, rowvar=False)
        eig_dist[i] = np.sort(np.linalg.eigvalsh(random_corr))[::-1]
    return np.percentile(eig_dist, percentile, axis=0)


def write_corr_heatmap(corr: pd.DataFrame, name_map: dict, out: Path) -> None:
    plt.figure(figsize=(10, 8))
    labels = [f"{tid} {name_map.get(tid, '')}" for tid in corr.columns]
    sns.heatmap(
        corr.values,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        center=0,
        xticklabels=labels,
        yticklabels=labels,
        vmin=-1,
        vmax=1,
        cbar_kws={"label": "Pearson correlation"},
    )
    plt.title("PMIC Sector — YoY revenue correlation matrix")
    plt.tight_layout()
    plt.savefig(out, dpi=120)
    plt.close()


def write_parallel_plot(
    actual: np.ndarray, random_95: np.ndarray, k: int, out: Path
) -> None:
    plt.figure(figsize=(8, 5))
    xs = np.arange(1, len(actual) + 1)
    plt.plot(xs, actual, "o-", label="Actual eigenvalues", lw=2, color="C0")
    plt.plot(xs, random_95, "s--", label="Random data 95th pct", lw=1.5, color="C3")
    plt.axhline(1.0, color="gray", ls=":", alpha=0.5, label="Kaiser (λ=1)")
    plt.axvline(k + 0.5, color="green", ls=":", alpha=0.5, label=f"Selected k={k}")
    plt.xlabel("Factor index")
    plt.ylabel("Eigenvalue")
    plt.title("Horn parallel analysis — PMIC YoY revenue")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out, dpi=120)
    plt.close()


def write_loadings_plot(loadings: pd.DataFrame, name_map: dict, out: Path) -> None:
    plt.figure(figsize=(10, max(6, 0.4 * len(loadings))))
    labels = [f"{tid} {name_map.get(tid, '')}" for tid in loadings.index]
    sns.heatmap(
        loadings.values,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        center=0,
        yticklabels=labels,
        xticklabels=loadings.columns,
        vmin=-1,
        vmax=1,
        cbar_kws={"label": "Loading"},
    )
    plt.title("PMIC Sector — Rotated factor loadings")
    plt.tight_layout()
    plt.savefig(out, dpi=120)
    plt.close()


def fit_efa(data: pd.DataFrame, k: int, rotation: str) -> FactorAnalyzer:
    fa = FactorAnalyzer(n_factors=k, rotation=rotation, method="minres")
    fa.fit(data.values)
    return fa


def factor_correlation(fa: FactorAnalyzer) -> np.ndarray | None:
    phi = getattr(fa, "phi_", None)
    return phi


def main(args):
    cfg = FREQ_CONFIG[args.frequency]
    period_word = "month" if args.frequency == "monthly" else "quarter"
    suffix = cfg["out_suffix"]
    print("=" * 72)
    print(f"PMIC Sector EFA — frequency={args.frequency}")
    print("=" * 72)

    df = load_all(cfg["parquets"])
    print(f"Loaded {len(df)} rows from {len(cfg['parquets'])} parquets")

    panel, name_map = build_revenue_panel(df)
    print(f"Pivoted revenue panel: {panel.shape[0]} {period_word}s × {panel.shape[1]} tickers")

    yoy = to_yoy_log(panel, cfg["lag"])
    yoy_trimmed = trim_panel(yoy, cfg["min_obs_per_ticker"], cfg["min_tickers_per_obs"])
    print(
        f"After trim (≥{cfg['min_obs_per_ticker']} {period_word}/ticker, "
        f"≥{cfg['min_tickers_per_obs']} t/{period_word}): "
        f"{yoy_trimmed.shape[0]} {period_word}s × {yoy_trimmed.shape[1]} tickers"
    )
    if yoy_trimmed.shape[0] < 10 or yoy_trimmed.shape[1] < 5:
        sys.exit(f"Panel too small after trim: {yoy_trimmed.shape}")

    print(f"Window: {yoy_trimmed.index.min().date()} → {yoy_trimmed.index.max().date()}")
    print(f"Tickers retained: {list(yoy_trimmed.columns)}")

    # Standardize (z-score per ticker)
    standardized = (yoy_trimmed - yoy_trimmed.mean()) / yoy_trimmed.std(ddof=1)

    # Diagnostics
    print()
    print("--- Pre-flight diagnostics ---")
    chi2, p_val = calculate_bartlett_sphericity(standardized)
    print(f"Bartlett sphericity: chi2={chi2:.2f}, p={p_val:.2e}")
    kmo_all, kmo_model = calculate_kmo(standardized)
    print(f"KMO (overall) = {kmo_model:.3f}")
    print("KMO per ticker:")
    for ticker, k in zip(standardized.columns, kmo_all):
        print(f"  {ticker} ({name_map.get(ticker, '')}): {k:.3f}")

    if kmo_model < KMO_THRESHOLD:
        print(
            f"\n⚠ KMO {kmo_model:.3f} < {KMO_THRESHOLD} — factor analysis NOT suitable.",
            file=sys.stderr,
        )
    if p_val > BARTLETT_THRESHOLD:
        print(
            f"\n⚠ Bartlett p={p_val:.2e} > {BARTLETT_THRESHOLD} — correlation matrix ≈ identity.",
            file=sys.stderr,
        )

    # Correlation heatmap
    corr = standardized.corr()
    write_corr_heatmap(
        corr, name_map, CHARTS_DIR / f"2026-06-{'11' if args.frequency=='monthly' else '10'}_pmic_corr_heatmap{suffix}.png"
    )
    print(f"Wrote {CHARTS_DIR / '2026-06-10_pmic_corr_heatmap.png'}")

    # Parallel analysis
    print()
    print("--- Horn parallel analysis ---")
    actual_eig = np.sort(np.linalg.eigvalsh(corr.values))[::-1]
    random_95 = parallel_analysis(
        n_obs=standardized.shape[0], n_vars=standardized.shape[1]
    )
    print("Eigenvalues vs random 95th-pct:")
    for i, (a, r) in enumerate(zip(actual_eig, random_95), 1):
        marker = "✓" if a > r else "✗"
        print(f"  Factor {i}: actual={a:.3f}, random95={r:.3f} {marker}")
    k_horn = int((actual_eig > random_95).sum())
    if k_horn < 1:
        k_horn = 1
    k = args.k or k_horn
    print(f"Horn k = {k_horn}; using k = {k}")

    write_parallel_plot(
        actual_eig,
        random_95,
        k,
        CHARTS_DIR / f"2026-06-{'11' if args.frequency=='monthly' else '10'}_pmic_parallel_analysis{suffix}.png",
    )

    # Fit EFA
    print()
    print(f"--- Fitting EFA with k={k}, rotation={args.rotation} ---")
    fa = fit_efa(standardized, k, args.rotation)
    loadings = pd.DataFrame(
        fa.loadings_,
        index=standardized.columns,
        columns=[f"F{i+1}" for i in range(k)],
    )

    # If varimax + multiple factors → check inter-factor score correlation
    if args.rotation == "varimax" and k > 1:
        scores = fa.transform(standardized.values)
        score_corr = np.corrcoef(scores, rowvar=False)
        np.fill_diagonal(score_corr, 0)
        max_off = np.abs(score_corr).max()
        print(f"Max |inter-factor score corr| (varimax) = {max_off:.3f}")
        if max_off > OBLIQUE_TRIGGER_CORR:
            print(
                f"  > {OBLIQUE_TRIGGER_CORR} → re-fitting with promax (oblique)"
            )
            fa = fit_efa(standardized, k, "promax")
            loadings = pd.DataFrame(
                fa.loadings_,
                index=standardized.columns,
                columns=[f"F{i+1}" for i in range(k)],
            )

    print()
    print("--- Rotated loadings (sorted by |F1|) ---")
    loadings_print = loadings.copy()
    loadings_print["ticker_name"] = [
        name_map.get(t, "") for t in loadings_print.index
    ]
    loadings_print = loadings_print.reindex(
        loadings_print["F1"].abs().sort_values(ascending=False).index
    )
    print(loadings_print.to_string(float_format="%+.3f"))

    # Variance explained
    var_pct = fa.get_factor_variance()[2]
    print()
    print("Variance explained (cumulative %):")
    for i, v in enumerate(var_pct, 1):
        print(f"  F1..F{i}: {v*100:.1f}%")

    # Factor scores
    scores_df = pd.DataFrame(
        fa.transform(standardized.values),
        index=standardized.index,
        columns=[f"F{i+1}" for i in range(k)],
    )

    write_loadings_plot(
        loadings, name_map, CHARTS_DIR / f"2026-06-{'11' if args.frequency=='monthly' else '10'}_pmic_loadings{suffix}.png"
    )
    print(f"Wrote {CHARTS_DIR / '2026-06-10_pmic_loadings.png'}")

    # Persist outputs
    loadings_out = loadings.reset_index().rename(columns={"index": "entity_id"})
    loadings_out["entity_name"] = loadings_out["entity_id"].map(name_map)
    loadings_out.to_parquet(PMIC_DIR / f"loadings{suffix}.parquet", index=False)
    print(f"Wrote {PMIC_DIR / f'loadings{suffix}.parquet'}")

    scores_out = scores_df.reset_index().rename(columns={"end": "period"})
    scores_out.to_parquet(PMIC_DIR / f"factor_scores{suffix}.parquet", index=False)
    print(f"Wrote {PMIC_DIR / f'factor_scores{suffix}.parquet'}")

    phi = factor_correlation(fa)
    diagnostics = {
        "n_obs": int(standardized.shape[0]),
        "n_vars": int(standardized.shape[1]),
        "tickers": list(standardized.columns),
        "window_start": str(standardized.index.min().date()),
        "window_end": str(standardized.index.max().date()),
        "kmo_overall": float(kmo_model),
        "kmo_per_ticker": {
            t: float(k) for t, k in zip(standardized.columns, kmo_all)
        },
        "bartlett_chi2": float(chi2),
        "bartlett_p": float(p_val),
        "k_horn": int(k_horn),
        "k_used": int(k),
        "rotation": fa.rotation,
        "variance_explained_cumulative": [float(v) for v in var_pct],
        "phi_max_offdiag": (
            float(np.abs(phi - np.eye(phi.shape[0])).max()) if phi is not None else None
        ),
    }
    with open(PMIC_DIR / f"efa_diagnostics{suffix}.json", "w") as f:
        json.dump(diagnostics, f, indent=2)
    print(f"Wrote {PMIC_DIR / 'efa_diagnostics.json'}")

    print()
    print("=" * 72)
    print("EFA pipeline complete.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--frequency", default="quarterly", choices=["quarterly", "monthly"],
        help="EFA frequency mode (loads different parquets, different lag)"
    )
    p.add_argument("--k", type=int, default=None, help="Override factor count")
    p.add_argument(
        "--rotation", default="varimax", choices=["varimax", "promax", "oblimin", "none"]
    )
    main(p.parse_args())
