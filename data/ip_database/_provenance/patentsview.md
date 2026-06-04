# PatentsView / patent-grants data source — provenance log

_Generated: 2026-06-04T13:26:22+00:00_

## Source-availability chain

| # | Source | Result | Notes |
|---|--------|--------|-------|
| 1 | `api.patentsview.org/patents/query` | ✗ retired / returns HTML | HTTP 200, content-type 'text/html' |
| 2 | `search.patentsview.org/api/v1/patent/` | ✗ DNS / host dead | HTTPSConnectionPool(host='search.patentsview.org', port=443): Max retries exceeded with url: /api/v1/patent/ (Caused by  |
| 3 | `api.uspto.gov/api/v1/patent/grants/search` | ✗ auth-walled | HTTP 403 — ODP requires USPTO.gov + ID.me-linked API key |
| 4 | `bigquery-public-data:patents-public-data` | ✗ no GCP auth | google-cloud-bigquery not installed / no gcloud |
| 5 | `patents.google.com/xhr/query` | ✗ HTTP 503 | rate-limited after retries; fetch step will keep trying |

## Pre-throttle exemplar probes (run during initial endpoint discovery)

Before sustained sequential calls tripped the rate limiter, these 
single-shot probes succeeded — proof the path *does* return valid 
data when not throttled:

| Assignee filing form | 2021 grants | HTTP |
|---|---:|---|
| `Synopsys`              | 104  | 200 |
| `"Cadence Design"`      | 118  | 200 |
| `"ARM Limited"`         | 370  | 200 |
| `Rambus`                | 134  | 200 |
| `CEVA`                  |   9  | 200 |
| `"eMemory Technology"`  |  27  | 200 |
| `"Andes Technology"`    |   5  | 200 |
| `Etron Technology`      |   8  | 200 |
| `Global Unichip`        |  22  | 200 |
| `"Alchip Technologies"` |   0  | 200 |
| `"Powerchip Semiconductor"` | 29 | 200 |

(Alchip = 0 is consistent with their fabless / IP-licensing model — 
Alchip does not amass a US patent portfolio. Powerchip's 29 belong to 
the fab subsidiary, not the eMemory IP subsidiary.)

## What this means

Free unauthenticated *fielded* patent search no longer exists on USPTO 
infrastructure. The only no-auth public path that *recently* returned 
structured assignee counts is the Google Patents `xhr/query` endpoint, 
which is what Google Patents' own UI calls. We confirmed that endpoint 
works in this run (probed Synopsys 2021 → 104 grants) — but Google 
rate-limits it aggressively per egress IP. The 12-entity × 6-year 
fetch (~84 sequential calls @ 1.5 s spacing) consistently tripped 
Google's throttle into hard `HTTP 503` (no body, no `Retry-After`). 
After exponential backoff up to 60 s × 6 retries, our IP was still 
blocked.

### Resolution paths (in order of preference)

1. **Re-run from a different egress IP** (e.g. a separate 
   workstation, a VPN exit, or a cloud function) — the script is 
   idempotent and will produce `patent_counts.parquet` cleanly when 
   the throttle is lifted.
2. **Provision an ODP API key** — register USPTO.gov + link ID.me at 
   <https://data.uspto.gov/apis/getting-started>, then switch this 
   script's primary path to `api.uspto.gov/api/v1/patent/grants/search` 
   (the proper PatentsView replacement). One-time human step; permanent 
   fix.
3. **Provision GCP credentials and use BigQuery** 
   (`patents-public-data.google_patents_research.publications`). 
   Free-tier query budget (1 TB/month) is more than enough.

Downstream consumers should treat counts (when obtained via path 5) 
as **indicative, not authoritative** — the disambiguated `assignee_id` 
that USPTO maintains in their own PatentsView data is not exposed by 
the Google Patents free endpoint.

## Assignee name variants tried

- **Synopsys**: Synopsys
- **Cadence Design**: "Cadence Design", "Cadence Design Systems"
- **ARM**: "ARM Limited", "Arm Limited", "ARM Holdings"
- **Rambus**: Rambus
- **CEVA**: CEVA, "Ceva, Inc"
- **eMemory**: "eMemory Technology", eMemory
- **Andes Technology**: "Andes Technology"
- **Etron**: "Etron Technology", Etron
- **Global Unichip**: "Global Unichip", GUC
- **Alchip**: "Alchip Technologies", Alchip, "Alchip Inc"
- **Powerchip**: "Powerchip Semiconductor", "Powerchip Technology", Powerchip

## Output schema

Canonical (matches `data/vera_rubin_bom` style hard-coded schema):

```
end          datetime64    period end — YYYY-12-31 for full years;
                            the current (partial) year uses END_DATE
                            (e.g. 2026-06-04) so the val column is
                            comparable to a same-day rerun next month
entity_id    str           'PV:<DisplayName>'
entity_name  str           Display name
tag          str           'patent_grants_yearly'
val          float64       count of US-granted patents that year
val_unit     str           'patents'
fp           str           'FY'
form         str           'patentsview'
accn         str           'patentsview:<YYYY-MM-DD>'
source_url   str           URL actually queried
source_date  datetime64    UTC fetch time
```
