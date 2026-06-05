#!/usr/bin/env python3
"""Fetch Cadence Design Systems (CDNS) RPO + segment/revenue XBRL data from SEC EDGAR.

CIK = 0000813672 (Cadence Design Systems Inc.)

Outputs:
  data/eda_ip/cdns_rpo.parquet      (cols: end, val_usd, fp, form, accn)
  data/eda_ip/cdns_revenue.parquet  (cols: end, val_usd, fp, form, accn, tag)

Prints last-8-quarter RPO + YoY% (vs 4 quarters prior, same fp) ASCII table.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import requests

CIK = "0000813672"
COMPANY_FACTS_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
HEADERS = {"User-Agent": "TW Coverage Research leehao921@gmail.com"}

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "eda_ip"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RPO_TAG_CANDIDATES = [
    "RevenueRemainingPerformanceObligation",
    "RemainingPerformanceObligation",
    "RevenueRemainingPerformanceObligations",
]

REVENUE_TAG_CANDIDATES = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
]


def fetch_company_facts() -> dict:
    resp = requests.get(COMPANY_FACTS_URL, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        sys.stderr.write(
            f"ERROR: companyfacts fetch returned HTTP {resp.status_code}\n"
            f"Body: {resp.text[:500]}\n"
        )
        sys.exit(1)
    return resp.json()


def find_tag(facts: dict, tag_candidates: list[str]) -> tuple[str | None, list[dict]]:
    """Look up the first tag candidate present under us-gaap with USD units."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tag_candidates:
        node = us_gaap.get(tag)
        if not node:
            continue
        units = node.get("units", {})
        usd_points = units.get("USD")
        if usd_points:
            return tag, usd_points
    return None, []


def extract_rpo(facts: dict) -> pd.DataFrame:
    tag, points = find_tag(facts, RPO_TAG_CANDIDATES)
    if not points:
        sys.stderr.write(
            "ERROR: no RPO tag found among candidates: "
            f"{RPO_TAG_CANDIDATES}\n"
            "Available us-gaap tag count: "
            f"{len(facts.get('facts', {}).get('us-gaap', {}))}\n"
        )
        return pd.DataFrame(columns=["end", "val_usd", "fp", "form", "accn", "tag"])

    rows = []
    for p in points:
        if p.get("form") not in ("10-Q", "10-K", "20-F", "6-K"):
            continue
        rows.append({
            "end": p.get("end"),
            "val_usd": p.get("val"),
            "fp": p.get("fp"),
            "form": p.get("form"),
            "accn": p.get("accn"),
            "tag": tag,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["end"] = pd.to_datetime(df["end"])
    # dedup keeping the latest-filed value per (end, fp)
    df = df.sort_values(["end", "fp", "accn"]).drop_duplicates(
        subset=["end", "fp"], keep="last"
    )
    df = df.sort_values("end").reset_index(drop=True)
    return df


def extract_revenue(facts: dict) -> pd.DataFrame:
    """Pull ALL viable revenue tags. Cadence segments may live under custom tags;
    we capture every USD-denominated revenue series and return long-format."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    company_facts_root = facts.get("facts", {})

    rows = []
    found_tags = []

    # Standard revenue tags
    for tag in REVENUE_TAG_CANDIDATES:
        node = us_gaap.get(tag)
        if not node:
            continue
        usd_points = node.get("units", {}).get("USD")
        if not usd_points:
            continue
        found_tags.append(("us-gaap", tag))
        for p in usd_points:
            if p.get("form") not in ("10-Q", "10-K", "20-F", "6-K"):
                continue
            rows.append({
                "end": p.get("end"),
                "start": p.get("start"),
                "val_usd": p.get("val"),
                "fp": p.get("fp"),
                "form": p.get("form"),
                "accn": p.get("accn"),
                "tag": f"us-gaap:{tag}",
            })

    # Also try custom Cadence segment tags under "cdns" namespace if present
    for ns, tags in company_facts_root.items():
        if ns == "us-gaap":
            continue
        if not isinstance(tags, dict):
            continue
        for tag_name, node in tags.items():
            if not isinstance(node, dict):
                continue
            # only grab if name suggests revenue / segment
            lower = tag_name.lower()
            if not any(k in lower for k in ("revenue", "segment", "ip", "system")):
                continue
            usd_points = node.get("units", {}).get("USD")
            if not usd_points:
                continue
            found_tags.append((ns, tag_name))
            for p in usd_points:
                if p.get("form") not in ("10-Q", "10-K", "20-F", "6-K"):
                    continue
                rows.append({
                    "end": p.get("end"),
                    "start": p.get("start"),
                    "val_usd": p.get("val"),
                    "fp": p.get("fp"),
                    "form": p.get("form"),
                    "accn": p.get("accn"),
                    "tag": f"{ns}:{tag_name}",
                })

    sys.stderr.write(f"INFO: revenue tags captured: {found_tags}\n")

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["end"] = pd.to_datetime(df["end"])
    df = df.sort_values(["tag", "end", "fp", "accn"]).drop_duplicates(
        subset=["tag", "end", "fp", "start"], keep="last"
    )
    df = df.sort_values(["tag", "end"]).reset_index(drop=True)
    return df


def print_rpo_table(df: pd.DataFrame) -> None:
    if df.empty:
        print("(no RPO data)")
        return
    # Keep one observation per (end, fp); use last 8 by end date
    snap = df.drop_duplicates(subset=["end", "fp"], keep="last").copy()
    snap = snap.sort_values("end").tail(12).copy()  # tail 12 so YoY lookup works

    # YoY: same fp 4 quarters earlier
    snap["yoy_pct"] = None
    fp_to_vals = {(row.end.year, row.fp): row.val_usd for row in snap.itertuples()}
    for idx, row in snap.iterrows():
        prior_key = (row["end"].year - 1, row["fp"])
        prior = fp_to_vals.get(prior_key)
        if prior:
            snap.at[idx, "yoy_pct"] = (row["val_usd"] / prior - 1.0) * 100.0

    last8 = snap.tail(8)
    print("\n=== CDNS RPO — last 8 quarters (USD millions) ===")
    print(f"{'end':<12} {'fp':<6} {'form':<6} {'RPO ($M)':>14} {'YoY %':>10}")
    print("-" * 52)
    for _, row in last8.iterrows():
        val_m = row["val_usd"] / 1e6
        yoy = row["yoy_pct"]
        yoy_str = f"{yoy:+.2f}%" if yoy is not None else "n/a"
        print(
            f"{row['end'].strftime('%Y-%m-%d'):<12} "
            f"{row['fp']:<6} {row['form']:<6} "
            f"{val_m:>14,.1f} {yoy_str:>10}"
        )


def main() -> int:
    sys.stderr.write(f"Fetching {COMPANY_FACTS_URL}\n")
    facts = fetch_company_facts()
    entity = facts.get("entityName", "?")
    sys.stderr.write(f"Entity: {entity}\n")

    rpo_df = extract_rpo(facts)
    rev_df = extract_revenue(facts)

    rpo_out = OUT_DIR / "cdns_rpo.parquet"
    rev_out = OUT_DIR / "cdns_revenue.parquet"

    if not rpo_df.empty:
        rpo_df.to_parquet(rpo_out, index=False)
        sys.stderr.write(f"Wrote {rpo_out} ({len(rpo_df)} rows)\n")
    else:
        sys.stderr.write("WARN: RPO dataframe empty — parquet not written\n")

    if not rev_df.empty:
        rev_df.to_parquet(rev_out, index=False)
        sys.stderr.write(f"Wrote {rev_out} ({len(rev_df)} rows)\n")
    else:
        sys.stderr.write("WARN: revenue dataframe empty — parquet not written\n")

    print_rpo_table(rpo_df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
