"""Load Vera Rubin VR200 BOM from per-unit parquet → TimescaleDB bom_components.

Reads all data/vera_rubin_bom/{NN}_*.parquet, NORMALIZES each unit's schema
(workers used different column names), UPSERTs into bom_components, writes
merged data/vera_rubin_bom.parquet.

Run: python3 scripts/load_vera_rubin_bom.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

REPO_ROOT = Path(__file__).resolve().parent.parent
BOM_DIR = REPO_ROOT / "data" / "vera_rubin_bom"

# Default category mapping per filename
CATEGORY_FROM_FILE = {
    "16_gpu_silicon": "GPU",
    "17_cpu_silicon": "CPU",
    "18_hbm4": "HBM",
    "19_dram_ssd": "Memory",
    "20_passives": "MLCC",
    "21_pcb_hdi": "PCB",
    "22_ccl": "CCL",
    "23_abf": "ABF",
    "24_power": "Power",
    "25_cooling": "Cooling",
    "26_connectors_network": "Connector",
    "27_optical_chassis": "Optical",
}


def normalize_platform(s):
    if pd.isna(s):
        return None
    s = str(s)
    if "VR200" in s or "Vera Rubin" in s:
        return "VR200"
    if "GB300" in s:
        return "GB300"
    if "GB200" in s:
        return "GB200"
    return s


def pick(row, *candidates):
    for c in candidates:
        if c in row.index and pd.notna(row[c]):
            return row[c]
    return None


def normalize_df(df: pd.DataFrame, stem: str) -> pd.DataFrame:
    default_cat = CATEGORY_FROM_FILE.get(stem, "Other")
    rows = []
    for _, r in df.iterrows():
        # supplier_tw_proxy may need to combine ticker+name
        tw = pick(r, "supplier_tw_proxy", "supplier_tw", "tw_proxy", "tw_proxy_primary", "tw_supplier", "primary_tw_supplier")
        if not tw:
            t = pick(r, "tw_supplier_ticker", "tw_proxy_ticker", "ticker")
            n = pick(r, "tw_supplier_name", "tw_proxy_name", "tw_supplier")
            if t and n:
                tw = f"{t} {n}"
            elif t:
                tw = str(t)

        rows.append(
            {
                "platform": normalize_platform(pick(r, "platform")),
                "category": pick(r, "category") or default_cat,
                "sub_category": (
                    pick(r, "sub_category", "component", "board") or "default"
                ),
                "supplier_main": pick(
                    r, "supplier_main", "supplier_intl", "supplier_primary", "supplier", "suppliers_primary"
                ),
                "supplier_tw_proxy": tw,
                "qty_per_rack": pick(
                    r, "qty_per_rack", "unit_per_rack", "boards_per_rack", "cpu_count_per_rack"
                ),
                "unit_price_usd": pick(r, "unit_price_usd", "asp_usd", "asp_usd_per_m2"),
                "total_value_usd": pick(
                    r, "total_value_usd", "subtotal_usd", "total_usd", "bom_value_usd", "bom_usd_per_rack"
                ),
                "prior_gen": pick(r, "prior_gen", "generation"),
                "yoy_change_pct": pick(
                    r,
                    "yoy_change_pct",
                    "yoy_pct",
                    "delta_vs_gb300_pct",
                    "delta_vs_prior_gen_pct",
                    "yoy_vs_gb300_pct",
                    "yoy_bom_dollar_pct",
                ),
                "source": pick(r, "source") or f"unit {stem}",
                "source_date": pick(r, "source_date"),
                "notes": pick(r, "notes", "note"),
            }
        )
    return pd.DataFrame(rows)


def load_and_validate() -> pd.DataFrame:
    files = sorted(BOM_DIR.glob("*.parquet"))
    if not files:
        print(f"No parquet files in {BOM_DIR}")
        sys.exit(1)

    print(f"Found {len(files)} unit parquets")
    frames = []
    for f in files:
        df = pd.read_parquet(f)
        stem = f.stem
        norm = normalize_df(df, stem)
        # Drop rows missing critical fields
        before = len(norm)
        norm = norm.dropna(subset=["platform", "category", "sub_category"])
        if before != len(norm):
            print(f"  {f.name}: {before} rows → {len(norm)} after dropna")
        else:
            print(f"  {f.name}: {len(norm)} rows")
        frames.append(norm)

    merged = pd.concat(frames, ignore_index=True)
    # De-dup on PK
    merged = merged.drop_duplicates(
        subset=["platform", "category", "sub_category", "source"], keep="last"
    )
    print(f"\nMerged: {len(merged)} rows total after dedup")
    return merged


def write_merged_parquet(df: pd.DataFrame) -> None:
    out = REPO_ROOT / "data" / "vera_rubin_bom.parquet"
    df.to_parquet(out)
    print(f"Wrote merged parquet: {out}")


def upsert_db(df: pd.DataFrame) -> None:
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="tmf_market_data",
        user="tmf",
        password="tmf_dev_2026",
    )
    try:
        with conn.cursor() as cur:
            rows = []
            for _, r in df.iterrows():
                rows.append(
                    (
                        r["platform"],
                        r["category"],
                        r["sub_category"],
                        r.get("supplier_main"),
                        r.get("supplier_tw_proxy"),
                        int(r["qty_per_rack"]) if pd.notna(r.get("qty_per_rack")) else None,
                        float(r["unit_price_usd"]) if pd.notna(r.get("unit_price_usd")) else None,
                        float(r["total_value_usd"]) if pd.notna(r.get("total_value_usd")) else None,
                        r.get("prior_gen") if pd.notna(r.get("prior_gen")) else None,
                        float(r["yoy_change_pct"]) if pd.notna(r.get("yoy_change_pct")) else None,
                        r["source"],
                        pd.to_datetime(r["source_date"]).date()
                        if pd.notna(r.get("source_date"))
                        else None,
                        r.get("notes") if pd.notna(r.get("notes")) else None,
                    )
                )

            execute_values(
                cur,
                """
                INSERT INTO bom_components (
                    platform, category, sub_category, supplier_main, supplier_tw_proxy,
                    qty_per_rack, unit_price_usd, total_value_usd, prior_gen, yoy_change_pct,
                    source, source_date, notes
                ) VALUES %s
                ON CONFLICT (platform, category, sub_category, source) DO UPDATE SET
                    supplier_main = EXCLUDED.supplier_main,
                    supplier_tw_proxy = EXCLUDED.supplier_tw_proxy,
                    qty_per_rack = EXCLUDED.qty_per_rack,
                    unit_price_usd = EXCLUDED.unit_price_usd,
                    total_value_usd = EXCLUDED.total_value_usd,
                    prior_gen = EXCLUDED.prior_gen,
                    yoy_change_pct = EXCLUDED.yoy_change_pct,
                    source_date = EXCLUDED.source_date,
                    notes = EXCLUDED.notes,
                    ingested_at = NOW()
                """,
                rows,
            )
            conn.commit()
            print(f"UPSERTed {len(rows)} rows")
    finally:
        conn.close()


def verify() -> None:
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="tmf_market_data",
        user="tmf",
        password="tmf_dev_2026",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT category,
                  SUM(CASE WHEN platform='VR200' THEN total_value_usd END) AS vr200,
                  SUM(CASE WHEN platform='GB300' THEN total_value_usd END) AS gb300,
                  ROUND((SUM(CASE WHEN platform='VR200' THEN total_value_usd END) /
                         NULLIF(SUM(CASE WHEN platform='GB300' THEN total_value_usd END), 0) - 1) * 100, 1) AS yoy_pct
                FROM bom_components
                WHERE platform IN ('VR200', 'GB300')
                GROUP BY category ORDER BY yoy_pct DESC NULLS LAST;
                """
            )
            print("\n=== YoY comparison (VR200 vs GB300) ===")
            print(f"{'category':<15} {'VR200 USD':>15} {'GB300 USD':>15} {'YoY %':>10}")
            print("-" * 60)
            total_vr, total_gb = 0, 0
            for cat, vr, gb, yoy in cur.fetchall():
                vr_v = float(vr) if vr else 0
                gb_v = float(gb) if gb else 0
                total_vr += vr_v
                total_gb += gb_v
                print(
                    f"{cat:<15} {vr_v:>15,.0f} {gb_v:>15,.0f} {(float(yoy) if yoy else 0):>+9.1f}%"
                )
            print("-" * 60)
            if total_gb > 0:
                print(
                    f"{'TOTAL':<15} {total_vr:>15,.0f} {total_gb:>15,.0f} {(total_vr/total_gb-1)*100:>+9.1f}%"
                )
    finally:
        conn.close()


if __name__ == "__main__":
    df = load_and_validate()
    write_merged_parquet(df)
    upsert_db(df)
    verify()
