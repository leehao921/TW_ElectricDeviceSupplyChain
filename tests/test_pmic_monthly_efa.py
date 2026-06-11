"""Verify monthly EFA + DFM outputs (v2 batch).

Schema + coverage gates for:
- data/pmic_efa/pmic_monthly_revenue.parquet (Unit 16)
- data/pmic_efa/wsts_macro_features.parquet (Unit 17, also covered in test_pmic_efa_data.py)
- data/pmic_efa/loadings_monthly.parquet (Coordinator EFA --frequency monthly)
- data/pmic_efa/factor_scores_monthly.parquet
- data/pmic_efa/dfm_loadings.parquet (Coordinator DFM)
- data/pmic_efa/dfm_smoothed_factors.parquet
- data/pmic_efa/dfm_diagnostics.json
"""
import json
from pathlib import Path

import pandas as pd
import pytest

PMIC_DIR = Path(__file__).resolve().parent.parent / "data" / "pmic_efa"

MIN_MONTHS_PER_TICKER = 36
EXPECTED_MONTHLY_TICKERS = {
    "8081", "6719", "6138", "6415", "4961", "3588", "3438",
    "2308", "6770", "2454",
}


def test_monthly_panel_exists_and_covers_floor():
    """Monthly panel must contain ≥36 months per expected ticker."""
    p = PMIC_DIR / "pmic_monthly_revenue.parquet"
    if not p.exists():
        pytest.skip("pmic_monthly_revenue.parquet 尚未產生 (Unit 16 未跑)")
    df = pd.read_parquet(p)
    assert df["fp"].eq("monthly").all(), "fp 應全為 'monthly'"
    counts = df.groupby("entity_id").size()
    failures = []
    for ticker in EXPECTED_MONTHLY_TICKERS:
        n = counts.get(ticker, 0)
        if n < MIN_MONTHS_PER_TICKER:
            failures.append(f"  {ticker}: {n} months (< {MIN_MONTHS_PER_TICKER})")
    if failures:
        pytest.fail(
            "Monthly EFA core tickers below floor:\n"
            + "\n".join(failures)
            + "\n修正: 重跑 scripts/fetch_pmic_monthly.py"
        )


def test_efa_monthly_outputs_present():
    """If EFA --frequency monthly has run, outputs must conform."""
    loadings_p = PMIC_DIR / "loadings_monthly.parquet"
    scores_p = PMIC_DIR / "factor_scores_monthly.parquet"
    if not loadings_p.exists():
        pytest.skip("loadings_monthly.parquet 尚未產生 (EFA 月頻未跑)")

    loadings = pd.read_parquet(loadings_p)
    assert "entity_id" in loadings.columns
    factor_cols = [c for c in loadings.columns if c.startswith("F")]
    assert factor_cols, "loadings_monthly 無 F1.. columns"
    assert len(loadings) >= 8, f"月 loadings 太少 ({len(loadings)} tickers)"

    scores = pd.read_parquet(scores_p)
    assert "period" in scores.columns
    assert len(scores) >= 36, f"factor_scores_monthly 太少 ({len(scores)} months)"


def test_dfm_outputs_present():
    """DFM outputs must be present and minimally valid."""
    loadings_p = PMIC_DIR / "dfm_loadings.parquet"
    smoothed_p = PMIC_DIR / "dfm_smoothed_factors.parquet"
    diag_p = PMIC_DIR / "dfm_diagnostics.json"
    if not loadings_p.exists():
        pytest.skip("DFM outputs 尚未產生")

    loadings = pd.read_parquet(loadings_p)
    assert "entity_id" in loadings.columns
    assert "entity_name" in loadings.columns
    f_cols = [c for c in loadings.columns if c.startswith("F")]
    assert len(f_cols) >= 1

    smoothed = pd.read_parquet(smoothed_p)
    assert "month" in smoothed.columns
    assert len(smoothed) >= 36

    with open(diag_p) as f:
        diag = json.load(f)
    assert "k_factors" in diag
    assert "log_likelihood" in diag
    assert "factor_ar_coefficients" in diag
    # All AR coefs should be < 1 in absolute value (stationary)
    for k, v in diag["factor_ar_coefficients"].items():
        assert abs(v) < 1.0, f"{k} = {v} (non-stationary?)"


def test_dfm_vs_efa_consistency():
    """DFM smoothed F1 (resampled to quarterly) should correlate with v1 EFA F1.

    Sanity check that v1 (quarterly EFA) and v2 (monthly DFM) capture the same
    underlying PMIC sector signal. Sign is arbitrary; we check |corr|.
    """
    dfm_p = PMIC_DIR / "dfm_smoothed_factors.parquet"
    v1_p = PMIC_DIR / "factor_scores.parquet"
    if not dfm_p.exists() or not v1_p.exists():
        pytest.skip("DFM 或 v1 EFA outputs 尚未產生")

    dfm = pd.read_parquet(dfm_p)
    dfm["month"] = pd.to_datetime(dfm["month"])
    dfm = dfm.set_index("month").sort_index()
    dfm_q = dfm.resample("QE").mean()

    v1 = pd.read_parquet(v1_p)
    period_col = "period" if "period" in v1.columns else "quarter"
    v1["period"] = pd.to_datetime(v1[period_col])
    v1 = v1.set_index("period").sort_index()

    common = dfm_q.index.intersection(v1.index)
    if len(common) < 4:
        pytest.skip(f"DFM 跟 v1 only {len(common)} common quarters")

    corr = dfm_q.loc[common, "F1"].corr(v1.loc[common, "F1"])
    assert abs(corr) >= 0.5, (
        f"|corr(DFM F1 quarterly, v1 F1)| = {abs(corr):.3f} < 0.5 — "
        "v2 月與 v1 季可能捕捉不同訊號, 需檢視"
    )
