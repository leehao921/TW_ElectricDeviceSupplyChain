#!/usr/bin/env python3
"""Fetch ARM Holdings (NASDAQ: ARM) RPO + revenue XBRL data from SEC EDGAR.

CIK = 0001973239 (ARM Holdings plc / UK), 2023 IPO.

ARM is a foreign private issuer — its US filings are 20-F (annual) and 6-K
(interim), NOT the 10-K / 10-Q used by domestic US issuers. ARM still tags
under us-gaap when filing to EDGAR, so RPO + Revenue tags ARE accessible.
This script accepts forms in {20-F, 6-K, 10-Q, 10-K}.

Outputs (canonical schema for IP database):
  data/ip_database/arm_rpo.parquet
  data/ip_database/arm_revenue.parquet

Schema:
  end          datetime64    period end
  entity_id    str           CIK 10-digit padded "0001973239"
  entity_name  str           "ARM Holdings"
  tag          str           XBRL concept
  val          float64       USD value
  val_unit     str           "USD"
  fp           str           "Q1"/"Q2"/"Q3"/"FY"
  form         str           "20-F"/"6-K"/"10-Q"/"10-K"
  accn         str           SEC accession number
  source_url   str           companyfacts API URL
  source_date  datetime64    fetch timestamp (UTC)

Provenance:
  Status (OK / PARTIAL / MISSING) → data/ip_database/_provenance/arm.md

Run:
  python3 scripts/fetch_arm_rpo.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

CIK = "0001973239"  # ARM Holdings plc / UK (10-digit padded)
ENTITY_NAME = "ARM Holdings"
URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
HEADERS = {"User-Agent": "TW Coverage Research leehao921@gmail.com"}

# ARM is a foreign private issuer → uses 20-F / 6-K instead of 10-K / 10-Q.
ALLOWED_FORMS = {"10-Q", "10-K", "20-F", "6-K"}

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "ip_database"
PROV_DIR = OUT_DIR / "_provenance"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PROV_DIR.mkdir(parents=True, exist_ok=True)

RPO_TAG_CANDIDATES = [
    "RevenueRemainingPerformanceObligation",
    "RevenueRemainingPerformanceObligations",
    "RemainingPerformanceObligation",
]
# Fallback only — NOT real RPO (it is deferred revenue / contract liability)
FALLBACK_RPO_TAG_CANDIDATES = [
    "ContractWithCustomerLiability",
]

REVENUE_TAG_CANDIDATES = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
]


def fetch_companyfacts() -> dict:
    sys.stderr.write(f"[fetch] GET {URL}\n")
    r = requests.get(URL, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        sys.stderr.write(f"[fetch] HTTP {r.status_code}: {r.text[:300]}\n")
        r.raise_for_status()
    return r.json()


def find_first_tag(facts: dict, candidates: list[str]) -> Optional[str]:
    """Return first candidate tag present with USD units in us-gaap."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in candidates:
        node = gaap.get(tag)
        if not node:
            continue
        units = node.get("units", {})
        if units.get("USD"):
            return tag
    return None


def extract_points(facts: dict, tag: str, source_date: pd.Timestamp) -> pd.DataFrame:
    """Extract USD time-series for a us-gaap tag → canonical schema dataframe."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    node = gaap.get(tag, {})
    units = node.get("units", {}).get("USD", [])

    rows = []
    for u in units:
        form = u.get("form")
        if form not in ALLOWED_FORMS:
            continue
        rows.append(
            {
                "end": u.get("end"),
                "entity_id": CIK,
                "entity_name": ENTITY_NAME,
                "tag": tag,
                "val": u.get("val"),
                "val_unit": "USD",
                "fp": u.get("fp"),
                "form": form,
                "accn": u.get("accn"),
                "source_url": URL,
                "source_date": source_date,
                # auxiliary for dedup (drop before write)
                "_filed": u.get("filed"),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["end"] = pd.to_datetime(df["end"])
    df["val"] = df["val"].astype("float64")
    df["_filed_ts"] = pd.to_datetime(df["_filed"])
    # Dedup (end, fp) keep latest-filed (final restatement wins)
    df = (
        df.sort_values("_filed_ts")
        .drop_duplicates(subset=["end", "fp"], keep="last")
        .sort_values("end")
        .reset_index(drop=True)
    )
    return df.drop(columns=["_filed", "_filed_ts"])


CANONICAL_COLUMNS = [
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


def ensure_canonical(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    # Apply alias map defensively (val_usd→val, period_end→end, etc.) — even
    # though we already build with canonical names; future maintainers may
    # tweak extract_points.
    aliases = {
        "val_usd": "val",
        "value": "val",
        "amount": "val",
        "period_end": "end",
        "date": "end",
        "ticker": "entity_id",
        "symbol": "entity_id",
        "cik": "entity_id",
    }
    df = df.rename(columns={k: v for k, v in aliases.items() if k in df.columns})
    # Add missing canonical columns
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[CANONICAL_COLUMNS]


def print_summary(label: str, df: pd.DataFrame) -> None:
    if df.empty:
        print(f"\n=== {label} ===\n(no data)")
        return
    print(f"\n=== {label} ===")
    print(f"rows: {len(df)}")
    print(f"date range: {df['end'].min().date()} -> {df['end'].max().date()}")
    print(f"tags: {sorted(df['tag'].unique().tolist())}")
    print(f"forms: {sorted(df['form'].unique().tolist())}")
    print("\ntail(5):")
    tail = df.tail(5).copy()
    tail["val_USD_M"] = tail["val"] / 1e6
    cols = ["end", "fp", "form", "tag", "val_USD_M", "accn"]
    # Compact print without index
    print(tail[cols].to_string(index=False))


def write_provenance(
    rpo_tag: Optional[str],
    rpo_fallback: bool,
    rpo_rows: int,
    rev_tags: list[str],
    rev_rows: int,
    entity_name: str,
) -> None:
    """Write provenance markdown documenting source viability."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Status calculation
    if rpo_tag and not rpo_fallback and rpo_rows > 0:
        rpo_status = "OK"
        rpo_note = f"Native RPO tag `{rpo_tag}` present with {rpo_rows} rows."
    elif rpo_tag and rpo_fallback and rpo_rows > 0:
        rpo_status = "PARTIAL"
        rpo_note = (
            f"No native RPO tag. Fell back to `{rpo_tag}` "
            f"(contract liability / deferred revenue — NOT identical to RPO). "
            f"{rpo_rows} rows."
        )
    else:
        rpo_status = "MISSING"
        rpo_note = (
            "No RPO tag found in us-gaap namespace. "
            "ARM uses IFRS for primary reporting; RPO disclosure may not appear "
            "under standard us-gaap tags."
        )

    rev_status = "OK" if rev_rows > 0 else "MISSING"
    rev_note = (
        f"Tags captured: {', '.join(rev_tags)} ({rev_rows} rows)"
        if rev_rows
        else "No revenue tag matched."
    )

    body = f"""# ARM Holdings — IP Database Provenance

**Fetched:** {now}
**Entity (per EDGAR):** {entity_name}
**CIK:** {CIK}
**Source:** [{URL}]({URL})
**Reporting standard:** IFRS primary, also files US GAAP-tagged XBRL under foreign-private-issuer rules (20-F annual + 6-K interim).

## Source viability

| Dataset | Status | Notes |
|---|---|---|
| RPO (Remaining Performance Obligation) | {rpo_status} | {rpo_note} |
| Revenue | {rev_status} | {rev_note} |

## Forms accepted

`{sorted(ALLOWED_FORMS)}` — ARM is a foreign private issuer so its annual is **20-F** and interim is **6-K** (not 10-K/10-Q used by US-domestic registrants). Filtering to only 10-K/10-Q would yield ZERO rows for ARM.

## Known caveats

- **IFRS vs US GAAP**: ARM's primary financial statements are IFRS. EDGAR XBRL is filed in IFRS Inline XBRL inside 20-F; supplementary us-gaap tags reflect the same numbers translated to US GAAP concepts where applicable.
- **Fiscal year**: ARM FY ends 31 March. `fp=FY` rows correspond to 20-F annual filings at end-March.
- **RPO definition**: Under IFRS 15 / ASC 606, RPO = aggregate transaction price allocated to performance obligations unsatisfied at period end. ARM discloses this in 20-F and quarterly 6-K MD&A.
- **First period**: 2023-09-30 (post-IPO; ARM relisted on NASDAQ Sep 2023).

## Output files

- `data/ip_database/arm_rpo.parquet` ({rpo_rows} rows)
- `data/ip_database/arm_revenue.parquet` ({rev_rows} rows)

## Reproduction

```bash
python3 scripts/fetch_arm_rpo.py
```
"""
    out = PROV_DIR / "arm.md"
    out.write_text(body, encoding="utf-8")
    sys.stderr.write(f"[prov] wrote {out}\n")


def main() -> int:
    source_date = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))
    facts = fetch_companyfacts()
    entity_name = facts.get("entityName", ENTITY_NAME)
    sys.stderr.write(f"[info] entity={entity_name} cik={facts.get('cik')}\n")

    # --- RPO ---
    rpo_tag = find_first_tag(facts, RPO_TAG_CANDIDATES)
    rpo_fallback = False
    if not rpo_tag:
        rpo_tag = find_first_tag(facts, FALLBACK_RPO_TAG_CANDIDATES)
        rpo_fallback = True

    if rpo_tag:
        kind = "FALLBACK" if rpo_fallback else "NATIVE"
        sys.stderr.write(f"[rpo] {kind} tag = {rpo_tag}\n")
        rpo_df = extract_points(facts, rpo_tag, source_date)
    else:
        sys.stderr.write("[rpo] no RPO-like tag found\n")
        rpo_df = pd.DataFrame(columns=CANONICAL_COLUMNS)

    rpo_df = ensure_canonical(rpo_df)

    if not rpo_df.empty:
        out = OUT_DIR / "arm_rpo.parquet"
        rpo_df.to_parquet(out, index=False)
        sys.stderr.write(f"[ok] wrote {out} rows={len(rpo_df)}\n")
    else:
        sys.stderr.write("[warn] RPO empty — parquet not written\n")

    # --- Revenue ---
    rev_frames = []
    rev_tags_found: list[str] = []
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in REVENUE_TAG_CANDIDATES:
        if tag in gaap and "USD" in gaap[tag].get("units", {}):
            df = extract_points(facts, tag, source_date)
            if not df.empty:
                rev_frames.append(df)
                rev_tags_found.append(tag)
                sys.stderr.write(f"[rev] tag={tag} rows={len(df)}\n")

    if rev_frames:
        rev_df = pd.concat(rev_frames, ignore_index=True)
        # Re-dedup across multi-tag concat (per-tag dedup already happened)
        rev_df = (
            rev_df.sort_values(["end", "tag"])
            .drop_duplicates(subset=["end", "fp", "tag"], keep="last")
            .reset_index(drop=True)
        )
    else:
        rev_df = pd.DataFrame(columns=CANONICAL_COLUMNS)

    rev_df = ensure_canonical(rev_df)

    if not rev_df.empty:
        out = OUT_DIR / "arm_revenue.parquet"
        rev_df.to_parquet(out, index=False)
        sys.stderr.write(f"[ok] wrote {out} rows={len(rev_df)}\n")
    else:
        sys.stderr.write("[warn] revenue empty — parquet not written\n")

    # --- Provenance ---
    write_provenance(
        rpo_tag=rpo_tag,
        rpo_fallback=rpo_fallback,
        rpo_rows=len(rpo_df),
        rev_tags=rev_tags_found,
        rev_rows=len(rev_df),
        entity_name=entity_name,
    )

    # --- ASCII summaries ---
    print_summary("ARM RPO", rpo_df)
    print_summary("ARM Revenue", rev_df)

    return 0


if __name__ == "__main__":
    sys.exit(main())
