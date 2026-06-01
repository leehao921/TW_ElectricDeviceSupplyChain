"""Phase 5: Asia panel covariance, correlation, rolling β, regime shifts.

Inputs: data/asia_market_panel.parquet (wide, daily closes).
Outputs:
  data/cov_3y.parquet                 — static 3y covariance
  data/corr_3y.parquet                — static 3y correlation
  data/rolling_corr_twii.parquet      — long-form rolling 60/90/252d corr vs TWII
  data/twii_dxy_beta.parquet          — full window + rolling 60d β
  data/regime_shifts.parquet          — date,pair,corr_t,corr_t_minus5,delta
  data/twii_corr_ranked.parquet       — TWII-anchored top10±

Run: python3 scripts/compute_asia_covariance.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

ANCHOR = "TWII"


def load_panel() -> pd.DataFrame:
    """Wide daily closes, intersection of anchor-trading days."""
    df = pd.read_parquet(DATA_DIR / "asia_market_panel.parquet")
    # ffill across markets to avoid losing the union of trading days, then
    # drop dates where the anchor (TWII) itself has no close.
    df = df.sort_index().ffill()
    df = df.dropna(subset=[ANCHOR])
    return df


def main() -> None:
    panel = load_panel()
    print(f"[load] panel shape={panel.shape} dates={panel.index.min().date()} -> {panel.index.max().date()}")
    print(f"  columns ({len(panel.columns)}): {list(panel.columns)}")

    # 1) Log returns
    rets = np.log(panel.astype(float)).diff().dropna(how="all")
    rets = rets.dropna(how="any")  # full intersection
    print(f"[rets] returns shape={rets.shape}")

    # 2) Static 3y covariance & correlation
    cov = rets.cov()
    corr = rets.corr()
    cov.to_parquet(DATA_DIR / "cov_3y.parquet")
    corr.to_parquet(DATA_DIR / "corr_3y.parquet")
    print(f"[save] cov_3y.parquet {cov.shape}")
    print(f"[save] corr_3y.parquet {corr.shape}")

    # 3) Rolling 60/90/252d correlation vs TWII
    windows = [60, 90, 252]
    rolling_parts = []
    for w in windows:
        rc = rets.rolling(w).corr(rets[ANCHOR])
        # rc rows = dates, cols = symbols (incl TWII itself = 1.0)
        for sym in rc.columns:
            if sym == ANCHOR:
                continue
            series = rc[sym].dropna()
            if series.empty:
                continue
            rolling_parts.append(
                pd.DataFrame({
                    "date": series.index,
                    "symbol": sym,
                    "window": w,
                    "corr_vs_twii": series.values,
                })
            )
    rolling_long = pd.concat(rolling_parts, ignore_index=True)
    rolling_long.to_parquet(DATA_DIR / "rolling_corr_twii.parquet")
    print(f"[save] rolling_corr_twii.parquet rows={len(rolling_long)}")

    # 4) TWII-vs-DXY β (full + rolling 60d)
    beta_rows = []
    if "DXY" in rets.columns:
        x = rets["DXY"].values
        y = rets[ANCHOR].values
        # full-window OLS
        var_x = float(np.var(x, ddof=1))
        cov_xy = float(np.cov(x, y, ddof=1)[0, 1])
        beta_full = cov_xy / var_x if var_x > 0 else np.nan
        alpha_full = float(y.mean() - beta_full * x.mean())
        # rolling 60d β
        roll = rets[[ANCHOR, "DXY"]].rolling(60)
        roll_cov = roll.cov().unstack()[(ANCHOR, "DXY")]
        roll_var = rets["DXY"].rolling(60).var()
        roll_beta = (roll_cov / roll_var).dropna()
        for d, b in roll_beta.items():
            beta_rows.append({"date": d, "window": "60d", "beta": float(b)})
        beta_rows.append({"date": rets.index[-1], "window": "full", "beta": float(beta_full), "alpha": alpha_full})
    beta_df = pd.DataFrame(beta_rows)
    beta_df.to_parquet(DATA_DIR / "twii_dxy_beta.parquet")
    print(f"[save] twii_dxy_beta.parquet rows={len(beta_df)} full_beta={beta_full:.4f}")

    # 5) Regime detection: |corr_t - corr_{t-5}| > 0.3 in 60d-corr series
    rc60 = rets.rolling(60).corr(rets[ANCHOR])
    regime_rows = []
    for sym in rc60.columns:
        if sym == ANCHOR:
            continue
        s = rc60[sym].dropna()
        if len(s) < 6:
            continue
        delta = s - s.shift(5)
        shifts = delta[delta.abs() > 0.3]
        for d, dlt in shifts.items():
            regime_rows.append({
                "date": d,
                "symbol": sym,
                "corr_t": float(s.loc[d]),
                "corr_t_minus5": float(s.shift(5).loc[d]),
                "delta": float(dlt),
            })
    regime_df = pd.DataFrame(regime_rows).sort_values("delta", key=lambda s: s.abs(), ascending=False)
    regime_df.to_parquet(DATA_DIR / "regime_shifts.parquet")
    print(f"[save] regime_shifts.parquet rows={len(regime_df)}")

    # 6) TWII-anchored ranked table (top-10 positive and top-10 negative static corr)
    twii_corr = corr[ANCHOR].drop(ANCHOR).sort_values(ascending=False)
    rank_rows = []
    for sym, val in twii_corr.head(10).items():
        rank_rows.append({"rank": "top_pos", "symbol": sym, "corr_3y": float(val)})
    for sym, val in twii_corr.tail(10).iloc[::-1].items():
        rank_rows.append({"rank": "top_neg", "symbol": sym, "corr_3y": float(val)})
    rank_df = pd.DataFrame(rank_rows)
    rank_df.to_parquet(DATA_DIR / "twii_corr_ranked.parquet")
    print(f"[save] twii_corr_ranked.parquet rows={len(rank_df)}")

    # ----------- Summary print -----------
    print("\n========== SUMMARY ==========")
    print(f"TWII–USDTWD 3y corr: {corr.loc[ANCHOR, 'USDTWD']:.4f}")
    print(f"TWII–DXY    3y corr: {corr.loc[ANCHOR, 'DXY']:.4f}")
    print(f"TWII–N225   3y corr: {corr.loc[ANCHOR, 'N225']:.4f}")
    print(f"TWII–DXY β (full):   {beta_full:.4f}")
    if len(beta_df[beta_df['window'] == '60d']) > 0:
        last60 = beta_df[beta_df['window'] == '60d']['beta'].iloc[-1]
        print(f"TWII–DXY β (last 60d): {last60:.4f}")

    print("\nTop 3 regime shifts:")
    print(regime_df.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
