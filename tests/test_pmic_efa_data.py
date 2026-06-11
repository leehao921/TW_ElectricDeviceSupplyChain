"""Verify data/pmic_efa/*.parquet schema and PMIC-specific data quality.

Catches:
- Schema drift across the 4 worker parquets (core4 / tail3 / china / context)
- Tickers falling below 18-quarter EFA floor (silent data regression)
- EFA pipeline outputs (loadings, scores) staying schema-consistent
"""
from pathlib import Path

import pandas as pd
import pytest

PMIC_DIR = Path(__file__).resolve().parent.parent / "data" / "pmic_efa"

# Core 11-col schema inherited from IP database
REQUIRED = {
    "end", "entity_id", "entity_name", "tag", "val", "val_unit",
    "fp", "form", "accn", "source_url", "source_date",
}

# Allowed tags for PMIC data
ALLOWED_TAGS = {
    "revenue", "gross_margin", "operating_margin", "net_margin",
    "r_and_d_ratio", "inventory_days", "accounts_receivable_days",
    "val_usd", "monthly_sales",
    # Unit 17 — DFM exogenous covariates derived from the WSTS monthly panel
    "wsts_yoy", "wsts_yoy_3ma", "wsts_level_zscore",
}

# Tags allowed to be negative (P&L margins + macro deltas can go below 0)
NEG_OK = {
    "operating_margin", "net_margin", "gross_margin",
    "operating_income", "net_income", "gross_profit",
    # WSTS-derived features: YoY and z-score legitimately go below zero
    "wsts_yoy", "wsts_yoy_3ma", "wsts_level_zscore",
}

EFA_TICKERS_MIN_QUARTERS = 18

# Core tickers expected (excludes Unit 15 yfinance-only context)
EXPECTED_CORE_TICKERS = {
    "8081",       # 致新
    "6719",       # 力智 (IPO 2021/12, may be exactly 18)
    "6138",       # 茂達
    "6415",       # 矽力-KY
    "4961",       # 天鈺
    "3588",       # 通嘉
    "3438",       # 類比科
    "300661.SZ",  # 聖邦微
}


def quarterly_parquets():
    """Worker quarterly parquets (core4/tail3/china/context)."""
    if not PMIC_DIR.exists():
        return []
    return sorted(PMIC_DIR.glob("pmic_*_quarterly.parquet"))


@pytest.mark.parametrize("path", quarterly_parquets(), ids=lambda p: p.name)
def test_pmic_quarterly_schema(path):
    df = pd.read_parquet(path)
    missing = REQUIRED - set(df.columns)
    assert not missing, f"{path.name} 缺欄位: {missing}"
    # All tags must be from the allowed set
    bad_tags = set(df["tag"].unique()) - ALLOWED_TAGS
    assert not bad_tags, f"{path.name} 未知 tag: {bad_tags}"
    # val numeric
    assert pd.api.types.is_numeric_dtype(df["val"]), f"{path.name} val 非 numeric"
    # Negative values only on NEG_OK tags
    must_be_nonneg = df[~df["tag"].isin(NEG_OK)]
    assert (must_be_nonneg["val"].dropna() >= 0).all(), \
        f"{path.name} 非 NEG_OK tag 有負值"


def test_pmic_efa_core_coverage():
    """Each expected core PMIC ticker must have at least 18 quarters of revenue.

    Catches the silent-regression case where a worker re-fetch returns fewer
    quarters and would crash the EFA pipeline at trim time.
    """
    if not quarterly_parquets():
        pytest.skip("data/pmic_efa/ 尚未落地 (PMIC EFA batch 未合)")

    frames = [pd.read_parquet(p) for p in quarterly_parquets()]
    df = pd.concat(frames, ignore_index=True)
    rev = df[(df["tag"] == "revenue") & (df["val_unit"].isin(["TWD_M", "CNY_M"]))]
    quarter_count = rev.groupby("entity_id").size()

    failures = []
    for ticker in EXPECTED_CORE_TICKERS:
        n = quarter_count.get(ticker, 0)
        if n < EFA_TICKERS_MIN_QUARTERS:
            failures.append(f"  {ticker}: {n} quarters (< {EFA_TICKERS_MIN_QUARTERS})")
    if failures:
        pytest.fail(
            "Core PMIC tickers below EFA floor:\n" + "\n".join(failures)
            + "\n修正: 重跑對應 worker fetcher (MOPS 補抓)"
        )


def test_efa_output_schema():
    """If EFA has run, loadings and factor_scores must be present + well-formed."""
    loadings_path = PMIC_DIR / "loadings.parquet"
    scores_path = PMIC_DIR / "factor_scores.parquet"
    if not loadings_path.exists():
        pytest.skip("EFA not yet run (loadings.parquet missing)")

    loadings = pd.read_parquet(loadings_path)
    assert "entity_id" in loadings.columns, "loadings 缺 entity_id"
    assert "entity_name" in loadings.columns, "loadings 缺 entity_name"
    factor_cols = [c for c in loadings.columns if c.startswith("F")]
    assert factor_cols, "loadings 無 F1.. columns"

    scores = pd.read_parquet(scores_path)
    # v2 refactor renamed "quarter" → "period" (frequency-agnostic)
    assert ("quarter" in scores.columns) or ("period" in scores.columns), \
        "scores 缺 period/quarter"
    assert len(scores) >= 10, f"factor_scores 太少 ({len(scores)} 季)"


def test_pmic_dir_exists_after_batch_merge():
    """Sentinel: PMIC EFA batch 全部合入後 data/pmic_efa/ 應有檔。"""
    if not PMIC_DIR.exists():
        pytest.skip("data/pmic_efa/ 尚未落地")
    has_parquet = bool(list(PMIC_DIR.glob("*.parquet")))
    assert has_parquet, "data/pmic_efa/ 存在但無 parquet"


def test_wsts_macro_features_schema():
    """Unit 17 WSTS DFM exogenous covariates must obey canonical schema.

    Checks the 3 derived features produced by `scripts/build_wsts_features.py`:
    wsts_yoy / wsts_yoy_3ma / wsts_level_zscore. The file is optional (skip
    if Unit 17 hasn't run) but if present must be well-formed.
    """
    path = PMIC_DIR / "wsts_macro_features.parquet"
    if not path.exists():
        pytest.skip("wsts_macro_features.parquet missing (Unit 17 not run)")

    df = pd.read_parquet(path)
    missing = REQUIRED - set(df.columns)
    assert not missing, f"{path.name} 缺欄位: {missing}"
    assert pd.api.types.is_numeric_dtype(df["val"]), \
        f"{path.name} val 非 numeric"

    expected_tags = {"wsts_yoy", "wsts_yoy_3ma", "wsts_level_zscore"}
    assert set(df["tag"].unique()) == expected_tags, \
        f"{path.name} tag set 不符: {set(df['tag'].unique())}"
    bad_tags = set(df["tag"].unique()) - ALLOWED_TAGS
    assert not bad_tags, f"{path.name} 未知 tag: {bad_tags}"

    # entity_id should be the WSTS macro identifier
    assert set(df["entity_id"].unique()) == {"WSTS_GLOBAL"}, \
        f"{path.name} entity_id 非 WSTS_GLOBAL"

    # Sanity check: feature panel should be long enough to be useful as a
    # DFM covariate (>= 100 month-ends across the 3 tags).
    assert df["end"].nunique() >= 100, \
        f"{path.name} 月份太少 ({df['end'].nunique()})"
