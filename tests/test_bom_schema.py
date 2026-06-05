"""Verify all data/vera_rubin_bom/*.parquet conform to canonical schema.

Prevents the 6-different-schema-from-12-workers regression that the Vera Rubin
BOM batch hit (unit_price_usd vs asp_usd, tw_supplier vs supplier_tw, ...).
"""
from pathlib import Path

import pandas as pd
import pytest

BOM_DIR = Path(__file__).resolve().parent.parent / "data" / "vera_rubin_bom"

REQUIRED = {
    "platform", "category", "sub_category", "component",
    "qty_per_rack", "unit_price_usd", "total_value_usd",
    "supplier_tw", "source",
}

ALIASES = {
    "asp_usd": "unit_price_usd",
    "bom_value_usd": "total_value_usd",
    "bom_usd_per_rack": "total_value_usd",
    "tw_supplier": "supplier_tw",
    "supplier_main": "supplier_tw",
    "supplier_tw_proxy": "supplier_tw",
    "tw_proxy_primary": "supplier_tw",
    "suppliers_primary": "supplier_tw",
}


def parquet_files():
    if not BOM_DIR.exists():
        return []
    return sorted(BOM_DIR.glob("*.parquet"))


@pytest.mark.parametrize("path", parquet_files(), ids=lambda p: p.name)
def test_bom_parquet_schema(path):
    df = pd.read_parquet(path).rename(columns=ALIASES)
    missing = REQUIRED - set(df.columns)
    assert not missing, f"{path.name} 缺欄位 (alias 後): {missing}"
    assert (df["total_value_usd"] >= 0).all(), \
        f"{path.name} 有負值 total_value_usd"
    assert df["platform"].notna().all(), \
        f"{path.name} 有 null platform"


def test_bom_dir_exists_after_pr25_merge():
    """Sentinel: 提醒 PR #25 合入時要把 data/vera_rubin_bom/ 一併帶上。"""
    if not BOM_DIR.exists():
        pytest.skip("data/vera_rubin_bom/ 尚未落地 (PR #25 未合)")
    assert len(list(BOM_DIR.glob("*.parquet"))) >= 1, \
        "data/vera_rubin_bom/ 存在但無 parquet"
