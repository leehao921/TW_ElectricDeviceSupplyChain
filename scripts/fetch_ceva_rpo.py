#!/usr/bin/env python3
"""Fetch CEVA Inc. (NASDAQ: CEVA) RPO + revenue XBRL data from SEC EDGAR companyfacts.

CEVA = small-cap DSP / connectivity IP licensor (5G, Wi-Fi, Bluetooth, AI-edge).
CIK = 0001173489.

Outputs:
  data/ip_database/ceva_rpo.parquet
  data/ip_database/ceva_revenue.parquet

Schema (canonical, shared across IP database units):
  end           datetime64   period end
  entity_id     str          10-digit CIK ("0001173489")
  entity_name   str          "CEVA"
  tag           str          XBRL concept name
  val           float64      numeric value
  val_unit      str          "USD"
  fp            str          "Q1"/"Q2"/"Q3"/"FY"
  form          str          "10-Q" / "10-K"
  accn          str          SEC accession number
  source_url    str          companyfacts API URL
  source_date   datetime64   when this row was fetched

If RPO tag is missing (common for small-cap filers that don't disclose RPO as
a top-line us-gaap tag), this is reported in the ASCII summary and a provenance
note is written to data/ip_database/_provenance/ceva.md so downstream consumers
know the source returned no RPO.

Run:
  python3 scripts/fetch_ceva_rpo.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

CIK = "0001173489"  # CEVA Inc.
ENTITY_NAME = "CEVA"
COMPANY_FACTS_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"

# SEC EDGAR requires identifying User-Agent. Schema from CLAUDE.md / unit spec.
HEADERS = {"User-Agent": "TW Coverage Research leehao921@gmail.com"}

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "ip_database"
PROV_DIR = OUT_DIR / "_provenance"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PROV_DIR.mkdir(parents=True, exist_ok=True)

RPO_TAG_CANDIDATES = [
    "RevenueRemainingPerformanceObligation",
    "RevenueRemainingPerformanceObligations",  # plural variant
    "RemainingPerformanceObligation",
    "ContractWithCustomerLiability",  # fallback: deferred revenue (proxy, not RPO)
]

REVENUE_TAG_CANDIDATES = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "LicensesRevenue",  # CEVA may report licensing rev separately
    "LicenseAndServicesRevenue",
    "RoyaltyRevenue",
]

CANONICAL_COLS = [
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
]


def fetch_company_facts() -> dict:
    print(f"[fetch] GET {COMPANY_FACTS_URL}", file=sys.stderr)
    resp = requests.get(COMPANY_FACTS_URL, headers=HEADERS, timeout=60)
    if resp.status_code != 200:
        print(
            f"[fetch] HTTP {resp.status_code}: {resp.text[:300]}",
            file=sys.stderr,
        )
        resp.raise_for_status()
    return resp.json()


def find_first_tag(facts: dict, candidates: list[str]) -> Optional[str]:
    """Return first tag in `candidates` that exists under us-gaap with USD units."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in candidates:
        node = gaap.get(tag)
        if not node:
            continue
        units = node.get("units", {})
        if units.get("USD"):
            return tag
    return None


def extract_points_for_tag(
    facts: dict, tag: str, source_date: datetime
) -> pd.DataFrame:
    """Build canonical-schema DataFrame for one tag under us-gaap, USD-only."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    node = gaap.get(tag, {})
    points = node.get("units", {}).get("USD", [])
    if not points:
        return pd.DataFrame(columns=CANONICAL_COLS)

    rows = []
    for p in points:
        form = p.get("form")
        if form not in ("10-Q", "10-K"):
            continue
        rows.append(
            {
                "end": p.get("end"),
                "entity_id": CIK,
                "entity_name": ENTITY_NAME,
                "tag": tag,
                "val": p.get("val"),
                "val_unit": "USD",
                "fp": p.get("fp"),
                "form": form,
                "accn": p.get("accn"),
                "source_url": COMPANY_FACTS_URL,
                "source_date": source_date,
                # internal-only, dropped before write
                "_filed": p.get("filed"),
            }
        )

    if not rows:
        return pd.DataFrame(columns=CANONICAL_COLS)

    df = pd.DataFrame(rows)
    df["end"] = pd.to_datetime(df["end"])
    df["val"] = pd.to_numeric(df["val"], errors="coerce").astype("float64")
    df["source_date"] = pd.to_datetime(df["source_date"])
    df["_filed"] = pd.to_datetime(df["_filed"])

    # Dedup by (end, fp) keeping the latest-filed value (restatement wins).
    df = df.sort_values("_filed").drop_duplicates(
        subset=["end", "fp"], keep="last"
    )
    df = df.drop(columns=["_filed"]).sort_values("end").reset_index(drop=True)

    return df[CANONICAL_COLS]


def collect_revenue_tags(facts: dict, source_date: datetime) -> tuple[pd.DataFrame, list[str]]:
    """Pull every viable revenue tag and stack long-format."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    frames: list[pd.DataFrame] = []
    found: list[str] = []
    for tag in REVENUE_TAG_CANDIDATES:
        node = gaap.get(tag)
        if not node:
            continue
        if not node.get("units", {}).get("USD"):
            continue
        df = extract_points_for_tag(facts, tag, source_date)
        if not df.empty:
            frames.append(df)
            found.append(tag)
    if not frames:
        return pd.DataFrame(columns=CANONICAL_COLS), found

    combined = pd.concat(frames, ignore_index=True)
    # Per-tag dedup (already applied inside extract_points_for_tag, but cross-tag
    # rows differ by tag so just sort).
    combined = combined.sort_values(["tag", "end"]).reset_index(drop=True)
    return combined, found


def list_revenue_like_tags(facts: dict) -> list[tuple[str, int]]:
    """Diagnostic: list all us-gaap tags whose name suggests revenue."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    hits: list[tuple[str, int]] = []
    for tag, node in gaap.items():
        if not isinstance(node, dict):
            continue
        lower = tag.lower()
        if not any(k in lower for k in ("revenue", "license", "royalty", "sales")):
            continue
        units = node.get("units", {}).get("USD") or []
        hits.append((tag, len(units)))
    return sorted(hits, key=lambda x: -x[1])


def ascii_summary(df: pd.DataFrame, label: str, n: int = 8) -> str:
    if df.empty:
        return f"\n=== {label} ===\n(no data)"
    snap = df.sort_values("end").copy()
    snap["val_m"] = snap["val"] / 1e6
    snap["year"] = snap["end"].dt.year
    snap["fp_norm"] = snap["fp"].fillna("")

    yoy = []
    for _, row in snap.iterrows():
        prior = snap[
            (snap["year"] == row["year"] - 1)
            & (snap["fp_norm"] == row["fp_norm"])
            & (snap["tag"] == row["tag"])
        ]
        if not prior.empty:
            p = prior.iloc[0]["val"]
            yoy.append((row["val"] / p - 1.0) * 100.0 if p else None)
        else:
            yoy.append(None)
    snap["yoy_pct"] = yoy

    tail = snap.tail(n)
    lines = [f"\n=== {label} (last {len(tail)} rows) ==="]
    lines.append(
        f"{'end':<12}{'fp':<6}{'form':<6}{'val_USD_M':>14}{'YoY%':>10}  tag"
    )
    lines.append("-" * 78)
    for _, r in tail.iterrows():
        yoy_s = f"{r['yoy_pct']:+.1f}%" if r["yoy_pct"] is not None else "n/a"
        lines.append(
            f"{r['end'].date()!s:<12}{(r['fp'] or ''):<6}{r['form']:<6}"
            f"{r['val_m']:>14,.2f}{yoy_s:>10}  {r['tag']}"
        )
    return "\n".join(lines)


def write_provenance(
    rpo_tag: Optional[str],
    rpo_rows: int,
    rev_tags: list[str],
    rev_rows: int,
    diag: list[tuple[str, int]],
    source_date: datetime,
) -> Path:
    path = PROV_DIR / "ceva.md"
    fetched = source_date.strftime("%Y-%m-%d %H:%M:%S UTC")
    rpo_status = (
        f"OK — tag `{rpo_tag}`, {rpo_rows} rows"
        if rpo_tag
        else "MISSING — none of the candidate tags returned USD points"
    )
    rev_status = (
        f"OK — tags {rev_tags}, {rev_rows} rows total"
        if rev_tags
        else "MISSING — no candidate revenue tag returned data"
    )
    diag_lines = "\n".join(f"  - `{t}`  n={n}" for t, n in diag[:25]) or "  (none)"

    content = f"""# CEVA Inc. — IP database provenance

- **Source:** SEC EDGAR XBRL companyfacts
- **URL:** {COMPANY_FACTS_URL}
- **CIK:** {CIK} (CEVA Inc., NASDAQ: CEVA)
- **Fetched:** {fetched}
- **Script:** scripts/fetch_ceva_rpo.py

## Source validity

| Series | Status |
|---|---|
| RPO (`RevenueRemainingPerformanceObligation` family) | {rpo_status} |
| Revenue (multi-tag) | {rev_status} |

RPO candidate tags tried (in order): {RPO_TAG_CANDIDATES}

Revenue candidate tags tried (in order): {REVENUE_TAG_CANDIDATES}

## Diagnostic — every us-gaap tag containing revenue/license/royalty/sales

{diag_lines}

## Notes

- CEVA is a small-cap DSP / connectivity IP licensor (~$100M annual revenue).
  Small filers often do **not** disclose `RevenueRemainingPerformanceObligation`
  as a discrete us-gaap concept; instead RPO context may be narrative in the
  10-K/10-Q text. Treat missing-RPO as **expected**, not an error.
- `ContractWithCustomerLiability` (deferred revenue) is included as a fallback
  in the RPO tag list — it is NOT RPO but the closest balance-sheet proxy.
- Only `10-Q` and `10-K` forms are retained. Dedup by `(end, fp)` keeps the
  latest-filed value so post-filing restatements supersede originals.
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> int:
    source_date = datetime.now(timezone.utc)
    facts = fetch_company_facts()
    entity_name = facts.get("entityName", "?")
    print(
        f"[info] entityName={entity_name} CIK={facts.get('cik')}",
        file=sys.stderr,
    )

    diag = list_revenue_like_tags(facts)
    print(f"[diag] {len(diag)} revenue-like us-gaap tags (USD):", file=sys.stderr)
    for t, n in diag[:25]:
        print(f"   {t}  n={n}", file=sys.stderr)

    # --- RPO ---
    rpo_tag = find_first_tag(facts, RPO_TAG_CANDIDATES)
    rpo_df = pd.DataFrame(columns=CANONICAL_COLS)
    if rpo_tag is None:
        print(
            f"[warn] no RPO tag among {RPO_TAG_CANDIDATES}", file=sys.stderr
        )
    else:
        print(f"[ok] RPO tag = {rpo_tag}", file=sys.stderr)
        rpo_df = extract_points_for_tag(facts, rpo_tag, source_date)
        out_path = OUT_DIR / "ceva_rpo.parquet"
        rpo_df.to_parquet(out_path, index=False)
        print(
            f"[ok] wrote {out_path} rows={len(rpo_df)}", file=sys.stderr
        )

    # --- Revenue ---
    rev_df, rev_tags = collect_revenue_tags(facts, source_date)
    if not rev_df.empty:
        out_path = OUT_DIR / "ceva_revenue.parquet"
        rev_df.to_parquet(out_path, index=False)
        print(
            f"[ok] wrote {out_path} rows={len(rev_df)} tags={rev_tags}",
            file=sys.stderr,
        )
    else:
        print("[warn] no revenue tag returned data", file=sys.stderr)

    # --- Provenance ---
    prov_path = write_provenance(
        rpo_tag=rpo_tag,
        rpo_rows=len(rpo_df),
        rev_tags=rev_tags,
        rev_rows=len(rev_df),
        diag=diag,
        source_date=source_date,
    )
    print(f"[ok] wrote provenance: {prov_path}", file=sys.stderr)

    # --- ASCII summary to stdout ---
    print(f"\n=== CEVA Inc. (CIK {CIK}) — IP database fetch summary ===")
    print(f"Source: {COMPANY_FACTS_URL}")
    print(f"Fetched: {source_date.isoformat()}")
    print(f"RPO tag chosen: {rpo_tag or 'NONE — see _provenance/ceva.md'}")
    print(f"Revenue tags captured: {rev_tags or 'NONE'}")

    if not rpo_df.empty:
        print(ascii_summary(rpo_df, f"CEVA RPO — {rpo_tag}"))
        print(
            f"\nRPO date range: {rpo_df['end'].min().date()} -> "
            f"{rpo_df['end'].max().date()} ({len(rpo_df)} rows)"
        )
        print("\nRPO tail(5):")
        print(rpo_df.tail(5).to_string(index=False))
    else:
        print("\nRPO: no rows. Candidate tags tried:")
        for t in RPO_TAG_CANDIDATES:
            print(f"  - {t}")

    if not rev_df.empty:
        # Pick primary revenue tag = the one with the most rows
        primary = rev_df["tag"].value_counts().index[0]
        primary_df = rev_df[rev_df["tag"] == primary].copy()
        print(ascii_summary(primary_df, f"CEVA Revenue — {primary}"))
        print(
            f"\nRevenue date range: {rev_df['end'].min().date()} -> "
            f"{rev_df['end'].max().date()} ({len(rev_df)} rows across "
            f"{rev_df['tag'].nunique()} tag(s))"
        )
        print("\nRevenue tail(5):")
        print(rev_df.tail(5).to_string(index=False))
    else:
        print("\nRevenue: no rows. Candidate tags tried:")
        for t in REVENUE_TAG_CANDIDATES:
            print(f"  - {t}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
