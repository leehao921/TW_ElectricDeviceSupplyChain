"""Verify data/ip_database/*.parquet conform to the IP-DB canonical schema.

Same protection model as test_bom_schema.py — the IP DB is being populated
by 5 parallel worker units (Units 7-11). They MUST all agree on column
names; this test catches drift.
"""
from pathlib import Path

import pandas as pd
import pytest

IP_DIR = Path(__file__).resolve().parent.parent / "data" / "ip_database"

REQUIRED = {
    "end",
    "entity_id",
    "entity_name",
    "tag",
    "val",
    "val_unit",
    "fp",
    "form",
    "accn",
    "source_url",
    "source_date",
}

ALIASES = {
    "count": "val",
    "patent_count": "val",
    "grants": "val",
    "year": "end",
    "granted_date": "end",
    "assignee": "entity_name",
    "company": "entity_name",
    "org": "entity_name",
}


def parquet_files():
    if not IP_DIR.exists():
        return []
    return sorted(IP_DIR.glob("*.parquet"))


@pytest.mark.parametrize("path", parquet_files(), ids=lambda p: p.name)
def test_ip_parquet_schema(path):
    df = pd.read_parquet(path).rename(columns=ALIASES)
    missing = REQUIRED - set(df.columns)
    assert not missing, f"{path.name} 缺欄位 (alias 後): {missing}"
    assert pd.api.types.is_numeric_dtype(df["val"]), \
        f"{path.name} val 不是 numeric"
    # Negative allowed only for explicit metrics (P&L losses, net flow 淨賣)
    NEG_OK = {
        "net_income", "operating_income", "gross_profit",
        "gross_margin", "operating_margin",
        "foreign_net_lots", "trust_net_lots", "total_net_lots",
    }
    must_be_nonneg = df[~df["tag"].isin(NEG_OK)]
    assert (must_be_nonneg["val"].dropna() >= 0).all(), \
        f"{path.name} 非 NEG_OK tag 有負值"
    # end / source_date must be parseable to datetime
    assert pd.api.types.is_datetime64_any_dtype(df["end"]), \
        f"{path.name} end 不是 datetime"
    assert df["entity_name"].notna().all(), \
        f"{path.name} 有 null entity_name"
    assert df["tag"].notna().all(), \
        f"{path.name} 有 null tag"


def test_ip_dir_exists_after_batch_merge():
    """Sentinel: 提醒 IP DB batch 全部合入後 data/ip_database/ 應該有檔。"""
    if not IP_DIR.exists():
        pytest.skip("data/ip_database/ 尚未落地 (IP DB batch 未合)")
    # at least the _provenance dir or one parquet should exist
    has_parquet = bool(list(IP_DIR.glob("*.parquet")))
    has_provenance = (IP_DIR / "_provenance").exists()
    assert has_parquet or has_provenance, \
        "data/ip_database/ 存在但無 parquet 也無 _provenance/"
