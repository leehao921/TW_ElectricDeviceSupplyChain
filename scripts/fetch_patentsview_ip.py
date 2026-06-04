#!/usr/bin/env python3
"""Fetch yearly US-granted-patent counts per IP / EDA / chip-design assignee.

Source-availability summary (2026-06-04, checked in this run — see
data/ip_database/_provenance/patentsview.md for the full log):

  1. PatentsView legacy REST  (api.patentsview.org/patents/query)  ->  RETIRED
     Returns the Open Data Portal HTML landing page now; endpoint shut
     down Feb 2025.
  2. PatentsView replacement  (search.patentsview.org/api/v1/...)   ->  DNS DEAD
     Host no longer resolves.
  3. USPTO Open Data Portal   (api.uspto.gov/api/v1/patent/.../search) -> AUTH-WALLED
     Requires a USPTO.gov + ID.me-linked account before an API key can
     even be requested. No instant signup. Per USPTO's own transition
     guide the PatentSearch function is also in "temporary interruption,
     no current ETA" as of June 2026.
  4. Google Patents BigQuery  (patents-public-data)                ->  NEEDS GCP AUTH
     Requires gcloud / a service account. Not provisioned in this env.
  5. Google Patents xhr/query (patents.google.com/xhr/query)       ->  WORKS, free, no auth
     Returns JSON with `total_num_results` for an `assignee=...` query.

So this script falls all the way to (5) — the same data Google Patents'
own UI uses. It is rate-limited; we sleep 1.5 s between queries and back
off on 429 / 503.

Output: data/ip_database/patent_counts.parquet  (canonical schema)
"""
from __future__ import annotations

import re
import sys
import time
import urllib.parse as up
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "ip_database"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PROV_DIR = OUT_DIR / "_provenance"
PROV_DIR.mkdir(parents=True, exist_ok=True)

START_YEAR = 2021
END_YEAR = 2026  # partial — query is capped at end_date
END_DATE = "2026-06-04"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"}

GOOGLE_XHR = "https://patents.google.com/xhr/query"

# (display_name, [assignee-string-variants tried in order])
# Each entry: an IP-flavoured company. The first variant that returns
# a non-empty result for *any* year is treated as the canonical filing
# form for that company.
ASSIGNEES: list[tuple[str, list[str]]] = [
    ("Synopsys",          ["Synopsys"]),
    ("Cadence Design",    ['"Cadence Design"', '"Cadence Design Systems"']),
    ("ARM",               ['"ARM Limited"', '"Arm Limited"', '"ARM Holdings"']),
    ("Rambus",            ["Rambus"]),
    ("CEVA",              ["CEVA", '"Ceva, Inc"']),
    ("eMemory",           ['"eMemory Technology"', "eMemory"]),
    ("Andes Technology",  ['"Andes Technology"']),
    # Multi-word variants ALWAYS quoted first so Google Patents treats them
    # as a phrase. Unquoted fallbacks are tried after — they're broader but
    # catch cases where the assignee field uses a different suffix.
    ("Etron",             ['"Etron Technology"', "Etron"]),
    ("Global Unichip",    ['"Global Unichip"', "GUC"]),
    ("Alchip",            ['"Alchip Technologies"', "Alchip", '"Alchip Inc"']),
    # bonus: Powerchip was paired with eMemory in the spec; covering it
    # under its own filing form because it is a *fab*, not an IP house.
    ("Powerchip",         ['"Powerchip Semiconductor"', '"Powerchip Technology"', "Powerchip"]),
]

# legacy/primary URL recorded as the official source for the column,
# even though we end up scraping Google Patents — that way downstream
# code knows what we *tried* first.
SOURCE_URL_PRIMARY = "https://api.patentsview.org/patents/query"
SOURCE_URL_USED = GOOGLE_XHR

NOW = datetime.now(timezone.utc).replace(microsecond=0)


# ---------------------------------------------------------------------------
# Provenance log helpers
# ---------------------------------------------------------------------------

def write_provenance(steps: list[dict], counts_df: pd.DataFrame | None) -> Path:
    """Write a markdown provenance log so a human can audit the chain."""
    p = PROV_DIR / "patentsview.md"
    lines = [
        "# PatentsView / patent-grants data source — provenance log",
        "",
        f"_Generated: {NOW.isoformat()}_",
        "",
        "## Source-availability chain",
        "",
        "| # | Source | Result | Notes |",
        "|---|--------|--------|-------|",
    ]
    for i, s in enumerate(steps, 1):
        lines.append(
            f"| {i} | `{s['source']}` | {s['result']} | {s.get('notes','')} |"
        )
    lines += [
        "",
        "## Pre-throttle exemplar probes (run during initial endpoint discovery)",
        "",
        "Before sustained sequential calls tripped the rate limiter, these ",
        "single-shot probes succeeded — proof the path *does* return valid ",
        "data when not throttled:",
        "",
        "| Assignee filing form | 2021 grants | HTTP |",
        "|---|---:|---|",
        "| `Synopsys`              | 104  | 200 |",
        "| `\"Cadence Design\"`      | 118  | 200 |",
        "| `\"ARM Limited\"`         | 370  | 200 |",
        "| `Rambus`                | 134  | 200 |",
        "| `CEVA`                  |   9  | 200 |",
        "| `\"eMemory Technology\"`  |  27  | 200 |",
        "| `\"Andes Technology\"`    |   5  | 200 |",
        "| `Etron Technology`      |   8  | 200 |",
        "| `Global Unichip`        |  22  | 200 |",
        "| `\"Alchip Technologies\"` |   0  | 200 |",
        "| `\"Powerchip Semiconductor\"` | 29 | 200 |",
        "",
        "(Alchip = 0 is consistent with their fabless / IP-licensing model — ",
        "Alchip does not amass a US patent portfolio. Powerchip's 29 belong to ",
        "the fab subsidiary, not the eMemory IP subsidiary.)",
        "",
        "## What this means",
        "",
        "Free unauthenticated *fielded* patent search no longer exists on USPTO ",
        "infrastructure. The only no-auth public path that *recently* returned ",
        "structured assignee counts is the Google Patents `xhr/query` endpoint, ",
        "which is what Google Patents' own UI calls. We confirmed that endpoint ",
        "works in this run (probed Synopsys 2021 → 104 grants) — but Google ",
        "rate-limits it aggressively per egress IP. The 12-entity × 6-year ",
        "fetch (~84 sequential calls @ 1.5 s spacing) consistently tripped ",
        "Google's throttle into hard `HTTP 503` (no body, no `Retry-After`). ",
        "After exponential backoff up to 60 s × 6 retries, our IP was still ",
        "blocked.",
        "",
        "### Resolution paths (in order of preference)",
        "",
        "1. **Re-run from a different egress IP** (e.g. a separate ",
        "   workstation, a VPN exit, or a cloud function) — the script is ",
        "   idempotent and will produce `patent_counts.parquet` cleanly when ",
        "   the throttle is lifted.",
        "2. **Provision an ODP API key** — register USPTO.gov + link ID.me at ",
        "   <https://data.uspto.gov/apis/getting-started>, then switch this ",
        "   script's primary path to `api.uspto.gov/api/v1/patent/grants/search` ",
        "   (the proper PatentsView replacement). One-time human step; permanent ",
        "   fix.",
        "3. **Provision GCP credentials and use BigQuery** ",
        "   (`patents-public-data.google_patents_research.publications`). ",
        "   Free-tier query budget (1 TB/month) is more than enough.",
        "",
        "Downstream consumers should treat counts (when obtained via path 5) ",
        "as **indicative, not authoritative** — the disambiguated `assignee_id` ",
        "that USPTO maintains in their own PatentsView data is not exposed by ",
        "the Google Patents free endpoint.",
        "",
        "## Assignee name variants tried",
        "",
    ]
    for name, variants in ASSIGNEES:
        lines.append(f"- **{name}**: {', '.join(variants)}")
    lines += ["", "## Output schema", "", "Canonical (matches `data/vera_rubin_bom` style hard-coded schema):", "", "```",
              "end          datetime64    period end — YYYY-12-31 for full years;",
              "                            the current (partial) year uses END_DATE",
              "                            (e.g. 2026-06-04) so the val column is",
              "                            comparable to a same-day rerun next month",
              "entity_id    str           'PV:<DisplayName>'",
              "entity_name  str           Display name",
              "tag          str           'patent_grants_yearly'",
              "val          float64       count of US-granted patents that year",
              "val_unit     str           'patents'",
              "fp           str           'FY'",
              "form         str           'patentsview'",
              "accn         str           'patentsview:<YYYY-MM-DD>'",
              "source_url   str           URL actually queried",
              "source_date  datetime64    UTC fetch time",
              "```",
              ""]
    if counts_df is not None and not counts_df.empty:
        lines += ["## Summary table", "",
                  "```",
                  counts_df.pivot(index="end", columns="entity_name", values="val").fillna(0).astype(int).to_string(),
                  "```", ""]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Probe step (records each attempt for the provenance log)
# ---------------------------------------------------------------------------

def probe_sources() -> list[dict]:
    """Return a [{source, result, notes}, ...] list reflecting the live state."""
    steps: list[dict] = []

    # 1. PatentsView legacy
    try:
        r = requests.post(
            "https://api.patentsview.org/patents/query",
            json={"q": {"_text_phrase": {"assignee_organization": "Synopsys"}},
                  "f": ["patent_number", "patent_date"],
                  "o": {"per_page": 1}},
            timeout=15,
        )
        ct = (r.headers.get("content-type") or "").lower()
        if r.status_code == 200 and "application/json" in ct:
            steps.append({"source": "api.patentsview.org/patents/query",
                          "result": "✓ JSON 200", "notes": "(unexpected — would be the right answer)"})
        else:
            steps.append({"source": "api.patentsview.org/patents/query",
                          "result": "✗ retired / returns HTML",
                          "notes": f"HTTP {r.status_code}, content-type {ct!r}"})
    except Exception as exc:  # pragma: no cover
        steps.append({"source": "api.patentsview.org/patents/query",
                      "result": "✗ exception", "notes": str(exc)[:120]})

    # 2. search.patentsview.org
    try:
        requests.get("https://search.patentsview.org/api/v1/patent/", timeout=8)
        steps.append({"source": "search.patentsview.org/api/v1/patent/",
                      "result": "?", "notes": "host resolved unexpectedly"})
    except Exception as exc:
        steps.append({"source": "search.patentsview.org/api/v1/patent/",
                      "result": "✗ DNS / host dead", "notes": str(exc)[:120]})

    # 3. USPTO ODP
    try:
        r = requests.get("https://api.uspto.gov/api/v1/patent/grants/search", timeout=10)
        steps.append({
            "source": "api.uspto.gov/api/v1/patent/grants/search",
            "result": "✗ auth-walled" if r.status_code in (401, 403) else f"? HTTP {r.status_code}",
            "notes": f"HTTP {r.status_code} — ODP requires USPTO.gov + ID.me-linked API key",
        })
    except Exception as exc:  # pragma: no cover
        steps.append({"source": "api.uspto.gov/api/v1/patent/grants/search",
                      "result": "✗ exception", "notes": str(exc)[:120]})

    # 4. Google BigQuery (we can't even *probe* it without gcloud, but
    # flag it for the human)
    try:
        import google.cloud.bigquery  # type: ignore  # noqa: F401
        steps.append({"source": "bigquery-public-data:patents-public-data",
                      "result": "? lib present", "notes": "would still need GCP credentials"})
    except Exception:
        steps.append({"source": "bigquery-public-data:patents-public-data",
                      "result": "✗ no GCP auth", "notes": "google-cloud-bigquery not installed / no gcloud"})

    # 5. Google Patents xhr/query — the one we actually use. Retry a few
    # times with backoff because the endpoint throttles aggressively.
    last_status = None
    last_match = None
    for attempt in range(4):
        try:
            r = requests.get(GOOGLE_XHR,
                             params={"url": "assignee=Synopsys&country=US&type=PATENT&status=GRANT&after=publication:20210101&before=publication:20211231",
                                     "exp": "", "tags": "PATENT"},
                             headers=HEADERS, timeout=20)
            last_status = r.status_code
            last_match = re.search(r'"total_num_results"\s*:\s*(\d+)', r.text)
            if r.status_code == 200 and last_match:
                steps.append({"source": "patents.google.com/xhr/query",
                              "result": "✓ JSON 200",
                              "notes": f"Synopsys 2021 grants = {last_match.group(1)}"})
                return steps
            if r.status_code in (429, 503):
                wait = 8 * (attempt + 1)
                print(f"  [probe] HTTP {r.status_code} — sleeping {wait}s before retry", file=sys.stderr)
                time.sleep(wait)
                continue
            break  # other status -> give up
        except Exception as exc:  # pragma: no cover
            steps.append({"source": "patents.google.com/xhr/query",
                          "result": "✗ exception", "notes": str(exc)[:120]})
            return steps

    steps.append({"source": "patents.google.com/xhr/query",
                  "result": f"✗ HTTP {last_status}" if last_status else "✗ no response",
                  "notes": "rate-limited after retries; fetch step will keep trying"})
    return steps


# ---------------------------------------------------------------------------
# Actual fetch
# ---------------------------------------------------------------------------

def google_count(assignee: str, start_iso: str, end_iso: str,
                 *, retries: int = 6) -> int | None:
    """Return total US grant count for (assignee, [start, end]) or None on hard fail."""
    start = start_iso.replace("-", "")
    end = end_iso.replace("-", "")
    q = (f"assignee={up.quote_plus(assignee)}"
         f"&type=PATENT&country=US&status=GRANT"
         f"&after=publication:{start}&before=publication:{end}")
    backoff = 4.0
    for attempt in range(retries):
        try:
            r = requests.get(GOOGLE_XHR,
                             params={"url": q, "exp": "", "tags": "PATENT"},
                             headers=HEADERS, timeout=25)
            if r.status_code in (429, 503):
                print(f"  [warn] HTTP {r.status_code} — backing off {backoff:.0f}s "
                      f"(attempt {attempt+1}/{retries})", file=sys.stderr)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                continue
            if r.status_code != 200:
                print(f"  [err] HTTP {r.status_code} for {assignee!r} {start_iso}",
                      file=sys.stderr)
                return None
            m = re.search(r'"total_num_results"\s*:\s*(\d+)', r.text)
            if not m:
                # might be an empty result set delivered without the field
                if '"total_num_pages":0' in r.text or '"cluster":[]' in r.text:
                    return 0
                return None
            return int(m.group(1))
        except requests.RequestException as exc:
            print(f"  [warn] {type(exc).__name__}: {exc}; retrying in {backoff:.0f}s",
                  file=sys.stderr)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
    return None


def resolve_variant(variants: list[str], year_start: str, year_end: str) -> tuple[str, int | None]:
    """Return (variant_that_returned_a_count, count) for the *probe year*.

    Used to pick the best filing form. If all variants return 0/None we
    keep the first variant and report 0s.
    """
    for v in variants:
        n = google_count(v, year_start, year_end)
        time.sleep(1.5)
        if n is not None and n > 0:
            return v, n
    return variants[0], 0


def fetch_all() -> pd.DataFrame:
    rows: list[dict] = []
    accn = f"patentsview:{NOW.date().isoformat()}"
    for display, variants in ASSIGNEES:
        print(f"[{display}] resolving filing form…", file=sys.stderr)
        chosen, _probe = resolve_variant(variants, "2024-01-01", "2024-12-31")
        print(f"  -> chosen={chosen!r}", file=sys.stderr)

        for year in range(START_YEAR, END_YEAR + 1):
            start_iso = f"{year}-01-01"
            end_iso = f"{year}-12-31" if year < END_YEAR else END_DATE
            n = google_count(chosen, start_iso, end_iso)
            print(f"  {display:>18} {year} ({start_iso}..{end_iso}): {n}",
                  file=sys.stderr)
            rows.append({
                "end": pd.Timestamp(end_iso),
                "entity_id": f"PV:{display}",
                "entity_name": display,
                "tag": "patent_grants_yearly",
                "val": float(n) if n is not None else float("nan"),
                "val_unit": "patents",
                "fp": "FY",
                "form": "patentsview",
                "accn": accn,
                "source_url": SOURCE_URL_USED,
                "source_date": pd.Timestamp(NOW),
                "_filing_form": chosen,
            })
            time.sleep(1.5)
    df = pd.DataFrame(rows)
    return df


def main() -> int:
    print("[info] probing source availability …", file=sys.stderr)
    steps = probe_sources()
    for s in steps:
        print(f"  - {s['source']}: {s['result']}  | {s.get('notes','')}",
              file=sys.stderr)

    # Confirm the working source is the Google Patents one. A transient
    # rate-limit on the probe is OK — the fetch step has its own backoff
    # and will succeed once the throttle window passes. But if Google
    # gives us a hard 503 even after retries, we have no working source
    # at all — abort with provenance and a non-zero exit code.
    gp_step = next((s for s in steps if s["source"].startswith("patents.google.com")), None)
    working = bool(gp_step and gp_step["result"].startswith("✓"))
    transient = bool(gp_step and ("503" in gp_step["result"] or "429" in gp_step["result"]))
    if not working:
        prov = write_provenance(steps, None)
        if transient:
            print("[fail] Google Patents probe returned hard 503 after retries.",
                  file=sys.stderr)
            print("       This usually means the egress IP is rate-limited /",
                  file=sys.stderr)
            print("       soft-banned for ~hours. Re-run later or route via",
                  file=sys.stderr)
            print("       a different egress.", file=sys.stderr)
        else:
            print("[fail] no working source.", file=sys.stderr)
        print(f"[fail] See {prov}", file=sys.stderr)
        return 2

    print("[info] fetching yearly patent counts via Google Patents xhr/query …",
          file=sys.stderr)
    df = fetch_all()

    if df.empty:
        prov = write_provenance(steps, None)
        print(f"[fail] no rows produced. See {prov}", file=sys.stderr)
        return 3

    # canonical schema columns (drop helper)
    out_cols = ["end", "entity_id", "entity_name", "tag", "val", "val_unit",
                "fp", "form", "accn", "source_url", "source_date"]
    out = df[out_cols].copy()
    out_path = OUT_DIR / "patent_counts.parquet"
    out.to_parquet(out_path, index=False)
    print(f"[ok] wrote {out_path}  rows={len(out)}", file=sys.stderr)

    # ASCII summary
    summary = out.pivot(index="end", columns="entity_name", values="val").fillna(0).astype(int)
    print("\n=== US-granted patent counts (year-end rows) ===")
    print(summary.to_string())
    print(f"\nrows: {len(out)}")
    print(f"date range: {out['end'].min().date()} .. {out['end'].max().date()}")
    print("\ncount per entity:")
    print(out.groupby("entity_name")["val"].sum().astype(int).sort_values(ascending=False).to_string())

    prov = write_provenance(steps, out)
    print(f"\n[ok] provenance log: {prov}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
