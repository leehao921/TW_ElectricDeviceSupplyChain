#!/usr/bin/env python3
"""Fetch Synopsys (SNPS) RPO + revenue time series from SEC EDGAR XBRL companyfacts.

Outputs:
  data/eda_ip/snps_rpo.parquet     (RPO timeseries)
  data/eda_ip/snps_revenue.parquet (segment / total revenue timeseries)

Run:
  python3 scripts/fetch_snps_rpo.py
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

CIK = "0000883241"  # Synopsys
URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
HEADERS = {
    "User-Agent": "TW Coverage Research leehao921@gmail.com",
    "Accept": "application/json",
}

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "eda_ip"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RPO_TAG_CANDIDATES = [
    "RevenueRemainingPerformanceObligation",
    "RevenueRemainingPerformanceObligations",  # plural variant
    "RemainingPerformanceObligation",
    "ContractWithCustomerLiability",  # fallback (deferred rev, different concept)
]

REVENUE_TAG_CANDIDATES = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
]


def fetch_companyfacts() -> dict:
    print(f"[fetch] GET {URL}", file=sys.stderr)
    r = requests.get(URL, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        print(f"[fetch] HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
        r.raise_for_status()
    return r.json()


def find_tag(facts: dict, candidates: list[str]) -> Optional[str]:
    """Return first matching tag name from us-gaap facts that exists with USD units."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in candidates:
        node = gaap.get(tag)
        if not node:
            continue
        units = node.get("units", {})
        if "USD" in units and units["USD"]:
            return tag
    return None


def extract_points(facts: dict, tag: str) -> pd.DataFrame:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    node = gaap.get(tag, {})
    units = node.get("units", {}).get("USD", [])
    rows = []
    for u in units:
        rows.append(
            {
                "tag": tag,
                "end": u.get("end"),
                "start": u.get("start"),
                "val_usd": u.get("val"),
                "fp": u.get("fp"),
                "fy": u.get("fy"),
                "form": u.get("form"),
                "accn": u.get("accn"),
                "filed": u.get("filed"),
                "frame": u.get("frame"),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[df["form"].isin(["10-Q", "10-K", "20-F", "6-K"])].copy()
    df["end"] = pd.to_datetime(df["end"])
    df = df.sort_values("end")
    # dedup by end+fp keeping latest filed (final restatement wins)
    df["filed_ts"] = pd.to_datetime(df["filed"])
    df = df.sort_values("filed_ts").drop_duplicates(subset=["end", "fp"], keep="last")
    df = df.sort_values("end").reset_index(drop=True)
    return df


def list_revenue_like_tags(facts: dict) -> list[str]:
    """Find all us-gaap tags whose name contains 'Revenue' for diagnostic."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    hits = []
    for tag, node in gaap.items():
        if "Revenue" in tag or "Segment" in tag:
            units = node.get("units", {}).get("USD")
            if units:
                hits.append((tag, len(units)))
    return sorted(hits, key=lambda x: -x[1])


def yoy_table(df: pd.DataFrame, label: str, n: int = 8) -> str:
    """Print last n quarters with YoY% vs same fp 4 quarters earlier."""
    if df.empty:
        return f"(no {label} data)"
    df = df.copy().sort_values("end")
    # For RPO we want point-in-time values per quarter end; use end+fp as key
    # YoY = same fp from 1 year earlier
    df["year"] = df["end"].dt.year
    df["fp_norm"] = df["fp"].replace({None: ""})
    df = df.sort_values("end").reset_index(drop=True)
    df["val_b"] = df["val_usd"] / 1e9

    yoy_vals = []
    for i, row in df.iterrows():
        prior_year = row["year"] - 1
        prior = df[(df["year"] == prior_year) & (df["fp_norm"] == row["fp_norm"])]
        if not prior.empty:
            p = prior.iloc[0]["val_usd"]
            yoy_vals.append((row["val_usd"] / p - 1.0) * 100.0 if p else None)
        else:
            yoy_vals.append(None)
    df["yoy_pct"] = yoy_vals

    last = df.tail(n)
    lines = [f"\n=== {label} (last {len(last)} qtrs) ==="]
    lines.append(f"{'end':<12}{'fp':<6}{'form':<6}{'val_USD_B':>12}{'YoY%':>10}")
    lines.append("-" * 46)
    for _, r in last.iterrows():
        yoy = f"{r['yoy_pct']:+.1f}%" if r["yoy_pct"] is not None else "n/a"
        lines.append(
            f"{r['end'].date()!s:<12}{r['fp'] or '':<6}{r['form']:<6}"
            f"{r['val_b']:>12.3f}{yoy:>10}"
        )
    return "\n".join(lines)


def main() -> int:
    facts = fetch_companyfacts()
    print(f"[info] entity: {facts.get('entityName')} CIK={facts.get('cik')}", file=sys.stderr)

    # Diagnostic: list available revenue-ish tags
    diag = list_revenue_like_tags(facts)
    print(f"[diag] {len(diag)} revenue/segment-like tags (USD):", file=sys.stderr)
    for t, n in diag[:25]:
        print(f"   {t}  n={n}", file=sys.stderr)

    # --- RPO ---
    rpo_tag = find_tag(facts, RPO_TAG_CANDIDATES)
    if not rpo_tag:
        print(f"[err] no RPO tag found among {RPO_TAG_CANDIDATES}", file=sys.stderr)
        rpo_df = pd.DataFrame()
    else:
        print(f"[ok] RPO tag = {rpo_tag}", file=sys.stderr)
        rpo_df = extract_points(facts, rpo_tag)
        out = OUT_DIR / "snps_rpo.parquet"
        rpo_df.to_parquet(out, index=False)
        print(f"[ok] wrote {out} rows={len(rpo_df)}", file=sys.stderr)

    # --- Revenue (try multiple tags, keep all that exist) ---
    rev_frames = []
    for tag in REVENUE_TAG_CANDIDATES:
        gaap = facts.get("facts", {}).get("us-gaap", {})
        if tag in gaap and "USD" in gaap[tag].get("units", {}):
            df = extract_points(facts, tag)
            if not df.empty:
                rev_frames.append(df)
                print(f"[ok] revenue tag={tag} rows={len(df)}", file=sys.stderr)
    if rev_frames:
        rev_df = pd.concat(rev_frames, ignore_index=True)
        out = OUT_DIR / "snps_revenue.parquet"
        rev_df.to_parquet(out, index=False)
        print(f"[ok] wrote {out} rows={len(rev_df)}", file=sys.stderr)
    else:
        rev_df = pd.DataFrame()
        print("[warn] no revenue tags matched", file=sys.stderr)

    # --- ASCII summaries to stdout ---
    if not rpo_df.empty:
        print(yoy_table(rpo_df, f"RPO ({rpo_tag})"))
    if not rev_df.empty:
        # Pick the primary revenue tag (most rows) for the headline table
        primary = rev_df["tag"].value_counts().index[0]
        primary_df = rev_df[rev_df["tag"] == primary].copy()
        print(yoy_table(primary_df, f"Revenue ({primary})"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
