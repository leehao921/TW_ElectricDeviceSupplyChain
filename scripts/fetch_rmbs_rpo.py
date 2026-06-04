#!/usr/bin/env python3
"""Fetch Rambus (RMBS) RPO + revenue (incl. royalty segment) from SEC EDGAR XBRL companyfacts.

Unit 8 of the IP database batch — memory + interface IP licensing pure-play.

Outputs (canonical schema):
  data/ip_database/rmbs_rpo.parquet     — RevenueRemainingPerformanceObligation timeseries
  data/ip_database/rmbs_revenue.parquet — total revenue + RoyaltyRevenue segment (long format)
  data/ip_database/_provenance/rmbs.md  — source/quality notes (✓/✗)

Canonical columns (after alias normalisation):
  end, entity_id (CIK 10-digit), entity_name, tag, val, val_unit,
  fp, form, accn, source_url, source_date

Run:
  python3 scripts/fetch_rmbs_rpo.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

CIK = "0000917273"  # Rambus Inc
ENTITY_NAME = "Rambus"
URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
HEADERS = {"User-Agent": "TW Coverage Research leehao921@gmail.com"}

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

# Order matters: prefer the modern ASC 606 tag first, then fall back.
REVENUE_TAG_CANDIDATES = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "ContractsRevenue",
    "SalesRevenueNet",
]

# Rambus segments revenue into Royalty + Product + Contract & Other.
# Only the royalty piece is consistently broken out at the us-gaap level.
ROYALTY_TAG_CANDIDATES = [
    "RoyaltyRevenue",
    "RoyaltyIncomeNonoperating",
]


# ---------------------------------------------------------------------------
# fetching + extraction
# ---------------------------------------------------------------------------

def fetch_companyfacts() -> dict:
    print(f"[fetch] GET {URL}", file=sys.stderr)
    r = requests.get(URL, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        print(f"[fetch] HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
        r.raise_for_status()
    return r.json()


def find_first_tag(facts: dict, candidates: list[str]) -> Optional[str]:
    """Return first candidate that exists with non-empty USD units."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in candidates:
        node = gaap.get(tag)
        if not node:
            continue
        usd = node.get("units", {}).get("USD")
        if usd:
            return tag
    return None


def extract_points(facts: dict, tag: str, source_date: datetime) -> pd.DataFrame:
    """Pull the USD points for `tag` and return a canonical-schema DataFrame."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    node = gaap.get(tag, {})
    units = node.get("units", {}).get("USD", [])
    rows = []
    for u in units:
        rows.append(
            {
                "end": u.get("end"),
                "entity_id": CIK,
                "entity_name": ENTITY_NAME,
                "tag": tag,
                "val": u.get("val"),
                "val_unit": "USD",
                "fp": u.get("fp"),
                "form": u.get("form"),
                "accn": u.get("accn"),
                "filed": u.get("filed"),
                "source_url": URL,
                "source_date": source_date,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # 10-Q / 10-K only (ignore 8-K, S-1, etc.)
    df = df[df["form"].isin(["10-Q", "10-K"])].copy()
    if df.empty:
        return df
    df["end"] = pd.to_datetime(df["end"])
    df["filed"] = pd.to_datetime(df["filed"])
    # final restatement wins on (end, fp)
    df = df.sort_values("filed").drop_duplicates(subset=["end", "fp"], keep="last")
    df = df.sort_values("end").reset_index(drop=True)
    df["val"] = df["val"].astype("float64")
    # drop transient `filed` from output - keep schema tight
    df = df.drop(columns=["filed"])
    return df


def normalise_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the canonical-schema alias map (idempotent — used as a final guard)."""
    alias_map = {
        "val_usd": "val",
        "value": "val",
        "amount": "val",
        "period_end": "end",
        "date": "end",
        "ticker": "entity_id",
        "symbol": "entity_id",
        "cik": "entity_id",
    }
    rename = {k: v for k, v in alias_map.items() if k in df.columns}
    if rename:
        df = df.rename(columns=rename)
    return df


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def yoy_table(df: pd.DataFrame, label: str, n: int = 8) -> str:
    if df.empty:
        return f"(no {label} data)"
    df = df.copy().sort_values("end").reset_index(drop=True)
    df["year"] = df["end"].dt.year
    df["fp_norm"] = df["fp"].fillna("")
    df["val_m"] = df["val"] / 1e6
    yoy_vals = []
    for _, row in df.iterrows():
        prior = df[(df["year"] == row["year"] - 1) & (df["fp_norm"] == row["fp_norm"])]
        if not prior.empty and prior.iloc[0]["val"]:
            yoy_vals.append((row["val"] / prior.iloc[0]["val"] - 1.0) * 100.0)
        else:
            yoy_vals.append(None)
    df["yoy_pct"] = yoy_vals
    last = df.tail(n)
    lines = [f"\n=== {label} (last {len(last)} qtrs) ==="]
    lines.append(f"{'end':<12}{'fp':<6}{'form':<6}{'val_USD_M':>12}{'YoY%':>10}")
    lines.append("-" * 46)
    for _, r in last.iterrows():
        yoy = f"{r['yoy_pct']:+.1f}%" if r["yoy_pct"] is not None else "n/a"
        lines.append(
            f"{r['end'].date()!s:<12}{(r['fp'] or ''):<6}{r['form']:<6}"
            f"{r['val_m']:>12.2f}{yoy:>10}"
        )
    return "\n".join(lines)


def write_provenance(
    rpo_tag: Optional[str],
    revenue_tag: Optional[str],
    royalty_tag: Optional[str],
    rpo_rows: int,
    rev_rows: int,
    royalty_rows: int,
    rpo_range: Optional[tuple],
    rev_range: Optional[tuple],
    royalty_range: Optional[tuple],
    source_date: datetime,
) -> None:
    path = PROV_DIR / "rmbs.md"
    check = lambda ok: "✓" if ok else "✗"  # noqa: E731

    def fmt_range(r: Optional[tuple]) -> str:
        if not r:
            return "—"
        return f"{r[0]} → {r[1]}"

    body = f"""# RMBS — Rambus Inc XBRL provenance

- **Source**: SEC EDGAR companyfacts API
- **URL**: {URL}
- **CIK**: {CIK}
- **Entity**: RAMBUS INC
- **Fetched at**: {source_date.isoformat()}
- **Forms kept**: 10-Q, 10-K (dedup by `(end, fp)` keeping latest filing — final restatement wins)

## Tag availability

| Concept | Tag used | Rows | Date range | Status |
|---|---|---|---|---|
| RPO | `{rpo_tag or '—'}` | {rpo_rows} | {fmt_range(rpo_range)} | {check(rpo_tag is not None and rpo_rows > 0)} |
| Total revenue (primary) | `{revenue_tag or '—'}` | {rev_rows} | {fmt_range(rev_range)} | {check(revenue_tag is not None and rev_rows > 0)} |
| Royalty segment | `{royalty_tag or '—'}` | {royalty_rows} | {fmt_range(royalty_range)} | {check(royalty_tag is not None and royalty_rows > 0)} |

## Source validity (✓/✗)

- **SEC EDGAR companyfacts** — ✓ valid, public, free; standard 10-Q/10-K XBRL feed.
- **RPO disclosure** — ✓ Rambus discloses `RevenueRemainingPerformanceObligation` from
  the ASC 606 adoption (FY18+). Earlier filings do not have RPO rows.
- **Total revenue** — ✓ usable but tag-version drift: Rambus stopped tagging
  `SalesRevenueNet` mid-2018 and switched to
  `RevenueFromContractWithCustomerIncludingAssessedTax` (the ASC 606 concept). The
  primary tag is auto-selected as whichever has the most recent `end` date so the
  headline series is always current. The full revenue parquet keeps every tag in long
  format (distinguished by `tag` column) so the pre-2018 history is still available.
- **Royalty segment** — ⚠ PARTIAL: `RoyaltyRevenue` ran through Q2-2018 then stopped at
  the us-gaap concept level. After ASC 606 Rambus reports royalty inside the segment
  footnote as a custom extension (`rmbs:RoyaltyRevenue` or
  `srt:ProductOrServiceAxis = RoyaltyMember`), which is NOT in companyfacts. For
  current-quarter royalty splits, parse the segment table from the 10-Q filing HTML
  directly. This script captures the historical royalty trend through 2018 only.

## Tags considered but rejected

- `RoyaltyIncomeNonoperating` — Rambus does not file this concept (royalty is
  operating revenue for the company, not non-operating income).
- `Revenues` — not used by Rambus.
- `RevenueFromContractWithCustomerExcludingAssessedTax` — Rambus uses the
  "Including" variant. The script falls through cleanly.

## Output schema (canonical)

| Column | Type | Notes |
|---|---|---|
| end | datetime64 | period-end |
| entity_id | str | "0000917273" |
| entity_name | str | "Rambus" |
| tag | str | XBRL concept |
| val | float64 | USD |
| val_unit | str | "USD" |
| fp | str | Q1/Q2/Q3/FY |
| form | str | 10-Q / 10-K |
| accn | str | SEC accession |
| source_url | str | this companyfacts URL |
| source_date | datetime64 | fetch timestamp (UTC) |
"""
    path.write_text(body, encoding="utf-8")
    print(f"[ok] wrote provenance {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    source_date = datetime.utcnow()
    facts = fetch_companyfacts()
    print(
        f"[info] entity: {facts.get('entityName')} CIK={facts.get('cik')}",
        file=sys.stderr,
    )

    # --- RPO ---
    rpo_tag = find_first_tag(facts, RPO_TAG_CANDIDATES)
    if rpo_tag:
        print(f"[ok] RPO tag = {rpo_tag}", file=sys.stderr)
        rpo_df = normalise_aliases(extract_points(facts, rpo_tag, source_date))
        rpo_out = OUT_DIR / "rmbs_rpo.parquet"
        rpo_df.to_parquet(rpo_out, index=False)
        print(f"[ok] wrote {rpo_out} rows={len(rpo_df)}", file=sys.stderr)
    else:
        print(f"[err] no RPO tag found among {RPO_TAG_CANDIDATES}", file=sys.stderr)
        rpo_df = pd.DataFrame()

    # --- Total revenue (concat every matching candidate; distinguished by `tag`) ---
    rev_frames = []
    for tag in REVENUE_TAG_CANDIDATES:
        gaap = facts.get("facts", {}).get("us-gaap", {})
        if tag in gaap and gaap[tag].get("units", {}).get("USD"):
            df = extract_points(facts, tag, source_date)
            if not df.empty:
                rev_frames.append(df)
                print(f"[ok] revenue tag={tag} rows={len(df)}", file=sys.stderr)

    # --- Royalty segment ---
    royalty_tag = find_first_tag(facts, ROYALTY_TAG_CANDIDATES)
    if royalty_tag:
        royalty_df = extract_points(facts, royalty_tag, source_date)
        if not royalty_df.empty:
            rev_frames.append(royalty_df)
            print(
                f"[ok] royalty tag={royalty_tag} rows={len(royalty_df)}",
                file=sys.stderr,
            )
    else:
        royalty_df = pd.DataFrame()
        print(
            f"[warn] no royalty tag found among {ROYALTY_TAG_CANDIDATES}",
            file=sys.stderr,
        )

    if rev_frames:
        rev_df = normalise_aliases(pd.concat(rev_frames, ignore_index=True))
        rev_out = OUT_DIR / "rmbs_revenue.parquet"
        rev_df.to_parquet(rev_out, index=False)
        print(f"[ok] wrote {rev_out} rows={len(rev_df)}", file=sys.stderr)
    else:
        rev_df = pd.DataFrame()
        print("[warn] no revenue tags matched", file=sys.stderr)

    # --- pick primary revenue tag for headline (latest end date wins) ---
    # Most rows != most current — pre-ASC-606 tags can have more history but be stale.
    primary_tag = None
    primary_df = pd.DataFrame()
    if not rev_df.empty:
        non_royalty = rev_df[rev_df["tag"] != (royalty_tag or "")]
        if not non_royalty.empty:
            latest_per_tag = non_royalty.groupby("tag")["end"].max().sort_values(
                ascending=False
            )
            primary_tag = latest_per_tag.index[0]
            primary_df = non_royalty[non_royalty["tag"] == primary_tag].copy()

    # --- provenance ---
    def _range(df: pd.DataFrame) -> Optional[tuple]:
        if df.empty:
            return None
        return (str(df["end"].min().date()), str(df["end"].max().date()))

    write_provenance(
        rpo_tag=rpo_tag,
        revenue_tag=primary_tag,
        royalty_tag=royalty_tag,
        rpo_rows=len(rpo_df),
        rev_rows=len(primary_df),
        royalty_rows=len(royalty_df) if not royalty_df.empty else 0,
        rpo_range=_range(rpo_df),
        rev_range=_range(primary_df),
        royalty_range=_range(royalty_df) if not royalty_df.empty else None,
        source_date=source_date,
    )

    # --- ASCII summaries ---
    if not rpo_df.empty:
        print(yoy_table(rpo_df, f"RPO ({rpo_tag})"))
        print(
            f"\n[summary] RPO rows={len(rpo_df)} "
            f"range={rpo_df['end'].min().date()} → {rpo_df['end'].max().date()}"
        )
        print("\n--- RPO tail(5) ---")
        print(rpo_df.tail(5).to_string(index=False))

    if not primary_df.empty:
        print(yoy_table(primary_df, f"Total Revenue ({primary_tag})"))
        print(
            f"\n[summary] Revenue (primary tag) rows={len(primary_df)} "
            f"range={primary_df['end'].min().date()} → {primary_df['end'].max().date()}"
        )

    if not royalty_df.empty:
        print(yoy_table(royalty_df, f"Royalty Segment ({royalty_tag})"))
        print(
            f"\n[summary] Royalty rows={len(royalty_df)} "
            f"range={royalty_df['end'].min().date()} → {royalty_df['end'].max().date()}"
        )
        print("\n--- Royalty tail(5) ---")
        print(royalty_df.tail(5).to_string(index=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
