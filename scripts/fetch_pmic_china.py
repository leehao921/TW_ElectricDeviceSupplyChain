#!/usr/bin/env python3
"""Fetch China PMIC comparables — Unit 14 of PMIC EFA batch.

Tickers (verified):
  - 300661.SZ  SG Micro Corp     (深圳創業板, China analog IC leader)
  - 688484.SS  SouthChip         (上海科創板, PMIC + battery management IC, 2022 IPO)
                                 (Yahoo uses `.SS` for Shanghai STAR board, not `.SH`.)

Outputs:
  data/pmic_efa/pmic_china_quarterly.parquet
  data/pmic_efa/_provenance/pmic_china.md

Canonical schema (11 cols) — same as Unit 12, with A-share entity_id keeping
the Yahoo suffix unchanged:

  end          datetime64    period end (quarter-end)
  entity_id    str           "300661.SZ" / "688484.SS" (suffix preserved)
  entity_name  str           "SG Micro" / "SouthChip"
  tag          str           revenue / val_usd / gross_margin / operating_margin
                              / net_margin / r_and_d_ratio
  val          float64       value in CNY millions / USD millions / percent
  val_unit     str           "CNY_M" / "USD_M" / "pct"
  fp           str           "Q1"/"Q2"/"Q3"/"Q4"
  form         str           "quarterly_actual"    (single-Q from Eastmoney YTD diff
                                                    or yfinance quarterly_income_stmt)
                              "annual_quarterized" (synthesized = annual / unfilled count)
  accn         str           "eastmoney:<symbol>:<series>" or "yfinance:<symbol>:<series>"
  source_url   str           HTTP endpoint URL
  source_date  datetime64    fetch timestamp (UTC)

Source viability tiers (see provenance.md):

  Eastmoney (primary): RPT_LICO_FN_CPD JSON via
    https://datacenter-web.eastmoney.com/api/data/v1/get
    Returns YTD totals back to 2012 (SG Micro) / 2019 (SouthChip). We invert
    YTD → single-quarter by differencing within each fiscal year. Gross margin
    (XSMLL) and net profit (PARENT_NETPROFIT) come directly from Eastmoney.

  yfinance (supplementary): quarterly_income_stmt for the last ~5 quarters has
    full P&L detail (Operating Income, R&D), which Eastmoney's CPD report does
    not break out. Annual income_stmt covers FY 2022 → 2025 and is used to
    synthesize older operating_margin / r_and_d_ratio rows when no real
    quarterly is available (form="annual_quarterized"). yfinance returns ~5
    real quarters for both names.

  FX: yfinance USDCNY=X 3-mo bars, forward-filled to quarter end.

Run:
  python3 scripts/fetch_pmic_china.py
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "pmic_efa"
PROV_DIR = OUT_DIR / "_provenance"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PROV_DIR.mkdir(parents=True, exist_ok=True)

# (yahoo_symbol, eastmoney_code, display_name)
TICKERS = [
    ("300661.SZ", "300661", "SG Micro"),
    ("688484.SS", "688484", "SouthChip"),
]

# yfinance financial-statement row labels we care about
ROW_REVENUE = "Total Revenue"
ROW_GROSS_PROFIT = "Gross Profit"
ROW_OPERATING_INCOME = "Operating Income"
ROW_NET_INCOME = "Net Income"
ROW_RND = "Research And Development"

EASTMONEY_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EASTMONEY_REPORT = "RPT_LICO_FN_CPD"
YFINANCE_HTTP_BASE = "https://query2.finance.yahoo.com/v10/finance/quoteSummary"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "TW-Coverage-Research leehao921@gmail.com"
    )
}

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

PROVENANCE_FX_NOTE = (
    "yfinance Ticker('USDCNY=X').history(period='max', interval='3mo'), Close column, "
    "mapped to nearest quarter end ≤ FX bar date (forward fill). 'max' is used "
    "instead of '5y' because Eastmoney revenue history extends back to 2015 for "
    "SG Micro; a 5y window would force every pre-2021 quarter to a stale rate."
)


# ---------------------------------------------------------------------------
# FX helpers
# ---------------------------------------------------------------------------
def fetch_fx_usdcny() -> pd.Series:
    """Return USD/CNY mid rate, indexed by quarter-end Timestamp.

    Uses period='max' so old (pre-2021) Eastmoney quarters get the correct
    contemporaneous rate. A 5y window would silently apply the 2021 rate to
    every 2015-2020 quarter (off by 0.2-0.8 CNY/USD).
    """
    sys.stderr.write("[fx] fetching USDCNY=X max-history quarterly...\n")
    h = yf.Ticker("USDCNY=X").history(period="max", interval="3mo")
    if h.empty:
        sys.stderr.write("[fx] WARNING: USDCNY=X returned empty\n")
        return pd.Series(dtype="float64")
    close = h["Close"].copy()
    close.index = close.index.tz_localize(None)
    quarter_ends = close.index.to_period("Q").to_timestamp(how="end").normalize()
    fx = pd.Series(close.values, index=quarter_ends)
    fx = fx[~fx.index.duplicated(keep="last")].sort_index()
    return fx


def fx_at(fx: pd.Series, quarter_end: pd.Timestamp) -> Optional[float]:
    """Return USD/CNY for quarter_end via forward fill."""
    if fx.empty:
        return None
    qe = pd.Timestamp(quarter_end).normalize()
    candidates = fx[fx.index <= qe]
    if candidates.empty:
        return float(fx.iloc[0])
    return float(candidates.iloc[-1])


# ---------------------------------------------------------------------------
# Eastmoney YTD → single-quarter
# ---------------------------------------------------------------------------
def fetch_eastmoney(code: str) -> pd.DataFrame:
    """Fetch RPT_LICO_FN_CPD YTD rows for a Chinese A-share security code.

    Returns DataFrame with columns:
      end (datetime), revenue_ytd_cny, net_profit_ytd_cny, gross_margin_pct
    """
    params = {
        "sortColumns": "REPORTDATE",
        "sortTypes": -1,
        "pageSize": 100,
        "pageNumber": 1,
        "reportName": EASTMONEY_REPORT,
        "columns": "ALL",
        "filter": f'(SECURITY_CODE="{code}")',
    }
    sys.stderr.write(f"[eastmoney] GET {EASTMONEY_URL} code={code}\n")
    r = requests.get(EASTMONEY_URL, params=params, timeout=20, headers=HEADERS)
    r.raise_for_status()
    j = r.json()
    if not j.get("success", True) or not j.get("result"):
        sys.stderr.write(f"[eastmoney] EMPTY result for {code}: {j.get('message')}\n")
        return pd.DataFrame(columns=["end", "revenue_ytd_cny", "net_profit_ytd_cny", "gross_margin_pct"])
    data = j["result"]["data"] or []
    rows = []
    for d in data:
        end_str = (d.get("REPORTDATE") or "")[:10]
        if not end_str:
            continue
        rows.append(
            {
                "end": pd.Timestamp(end_str),
                "revenue_ytd_cny": d.get("TOTAL_OPERATE_INCOME"),
                "net_profit_ytd_cny": d.get("PARENT_NETPROFIT"),
                "gross_margin_pct": d.get("XSMLL"),
            }
        )
    df = pd.DataFrame(rows).sort_values("end").reset_index(drop=True)
    df["revenue_ytd_cny"] = pd.to_numeric(df["revenue_ytd_cny"], errors="coerce")
    df["net_profit_ytd_cny"] = pd.to_numeric(df["net_profit_ytd_cny"], errors="coerce")
    df["gross_margin_pct"] = pd.to_numeric(df["gross_margin_pct"], errors="coerce")
    return df


def ytd_to_single_quarter(em: pd.DataFrame) -> pd.DataFrame:
    """Convert Eastmoney YTD rows into single-quarter rows.

    For a given fiscal year:
      Q1 single = Q1 YTD
      Q2 single = H1 YTD − Q1 YTD
      Q3 single = 9M YTD − H1 YTD
      Q4 single = Annual YTD − 9M YTD

    If an earlier-quarter YTD value is missing (e.g. Eastmoney only has annual
    + H1 for early years), we skip that single quarter rather than fabricate.

    `gross_margin_pct` from Eastmoney's XSMLL field is *YTD-cumulative* not
    single-quarter. We back out a single-Q gross margin by reconstructing
    YTD gross profit (= YTD revenue × XSMLL/100) and differencing.
    """
    em = em.copy()
    em["year"] = em["end"].dt.year
    em["q"] = ((em["end"].dt.month - 1) // 3 + 1).astype(int)

    # Pre-compute YTD gross profit (CNY) where both revenue and margin exist
    em["gross_profit_ytd_cny"] = em["revenue_ytd_cny"] * em["gross_margin_pct"] / 100.0

    out_rows = []
    for year, grp in em.groupby("year", sort=True):
        by_q = {int(row["q"]): row for _, row in grp.iterrows()}
        prev_rev = 0.0
        prev_ni = 0.0
        prev_gp = 0.0
        for q in (1, 2, 3, 4):
            if q not in by_q:
                # Missing this YTD point: we cannot infer a single Q without
                # the previous cumulative — reset prev_* so later Qs in same
                # year don't double-count.
                prev_rev = None
                prev_ni = None
                prev_gp = None
                continue
            row = by_q[q]
            rev_ytd = row["revenue_ytd_cny"]
            ni_ytd = row["net_profit_ytd_cny"]
            gp_ytd = row["gross_profit_ytd_cny"]
            if pd.isna(rev_ytd):
                prev_rev = None
                prev_ni = None
                prev_gp = None
                continue
            if prev_rev is None:
                # After a gap, only Q1 produces a valid single-Q value.
                if q != 1:
                    continue
                single_rev = float(rev_ytd)
                single_ni = float(ni_ytd) if not pd.isna(ni_ytd) else float("nan")
                single_gp = float(gp_ytd) if not pd.isna(gp_ytd) else float("nan")
            else:
                single_rev = float(rev_ytd) - prev_rev
                single_ni = (
                    float(ni_ytd) - prev_ni
                    if not pd.isna(ni_ytd) and prev_ni is not None
                    else float("nan")
                )
                single_gp = (
                    float(gp_ytd) - prev_gp
                    if not pd.isna(gp_ytd) and prev_gp is not None
                    else float("nan")
                )

            if single_rev <= 0:
                # Implausible negative single-Q revenue — skip but preserve
                # the YTD cumulative state for the next quarter.
                prev_rev = float(rev_ytd)
                if not pd.isna(ni_ytd):
                    prev_ni = float(ni_ytd)
                if not pd.isna(gp_ytd):
                    prev_gp = float(gp_ytd)
                continue

            # Derived single-Q gross margin (may be NaN if YTD GP missing)
            if not pd.isna(single_gp):
                single_gm_pct = 100.0 * single_gp / single_rev
            else:
                single_gm_pct = float("nan")

            out_rows.append(
                {
                    "end": row["end"],
                    "year": year,
                    "q": q,
                    "revenue_cny": single_rev,
                    "net_profit_cny": single_ni,
                    "gross_margin_pct": single_gm_pct,
                }
            )
            prev_rev = float(rev_ytd)
            if not pd.isna(ni_ytd):
                prev_ni = float(ni_ytd)
            if not pd.isna(gp_ytd):
                prev_gp = float(gp_ytd)
    return pd.DataFrame(out_rows)


# ---------------------------------------------------------------------------
# yfinance extractors (operating_margin + R&D ratio)
# ---------------------------------------------------------------------------
def safe_get_row(df: pd.DataFrame, row: str) -> pd.Series:
    if df is None or df.empty or row not in df.index:
        return pd.Series(dtype="float64")
    s = df.loc[row].dropna()
    s.index = pd.to_datetime(s.index).normalize()
    return s.astype("float64")


def fetch_yfinance_oi_rnd(symbol: str) -> dict:
    """Return dict of ratios keyed by quarter-end Timestamp.

    keys:
      'oi_q'  : real quarter operating_margin %
      'rnd_q' : real quarter R&D ratio %
      'oi_a'  : annual operating margin % (annual basis, used to synthesize)
      'rnd_a' : annual R&D ratio %
      'rev_q' : real quarter revenue (for sanity)
      'rev_a' : annual revenue (for sanity)
    """
    t = yf.Ticker(symbol)
    try:
        qis = t.quarterly_income_stmt
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"  yfinance qis err {symbol}: {e}\n")
        qis = pd.DataFrame()
    time.sleep(0.5)
    try:
        ann = t.income_stmt
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"  yfinance annual err {symbol}: {e}\n")
        ann = pd.DataFrame()
    time.sleep(0.5)

    rev_q = safe_get_row(qis, ROW_REVENUE)
    oi_q = safe_get_row(qis, ROW_OPERATING_INCOME)
    rnd_q = safe_get_row(qis, ROW_RND)
    rev_a = safe_get_row(ann, ROW_REVENUE)
    oi_a = safe_get_row(ann, ROW_OPERATING_INCOME)
    rnd_a = safe_get_row(ann, ROW_RND)
    return {
        "rev_q": rev_q,
        "oi_q": oi_q,
        "rnd_q": rnd_q,
        "rev_a": rev_a,
        "oi_a": oi_a,
        "rnd_a": rnd_a,
    }


# ---------------------------------------------------------------------------
# Row assembly (canonical schema)
# ---------------------------------------------------------------------------
def fp_label(q: int) -> str:
    return f"Q{q}"


def assemble_ticker_rows(
    symbol: str,
    em_code: str,
    name: str,
    em_singleq: pd.DataFrame,
    yf_pack: dict,
    fx: pd.Series,
    source_date: pd.Timestamp,
    earliest_synth: pd.Timestamp,
) -> pd.DataFrame:
    """Combine Eastmoney single-Q + yfinance OI/R&D into canonical rows."""
    em_source_url = (
        f"{EASTMONEY_URL}?reportName={EASTMONEY_REPORT}&filter=(SECURITY_CODE=%22{em_code}%22)"
    )
    yf_source_url = (
        f"{YFINANCE_HTTP_BASE}/{symbol}?modules=incomeStatementHistoryQuarterly,incomeStatementHistory"
    )

    rev_q_yf = yf_pack["rev_q"]
    oi_q_yf = yf_pack["oi_q"]
    rnd_q_yf = yf_pack["rnd_q"]
    rev_a_yf = yf_pack["rev_a"]
    oi_a_yf = yf_pack["oi_a"]
    rnd_a_yf = yf_pack["rnd_a"]

    real_yf_quarters = set(rev_q_yf.index)

    rows: list[dict] = []

    def push(end_ts, tag, val, val_unit, form, accn, source_url):
        rows.append(
            {
                "end": end_ts,
                "entity_id": symbol,
                "entity_name": name,
                "tag": tag,
                "val": val,
                "val_unit": val_unit,
                "fp": fp_label((end_ts.month - 1) // 3 + 1),
                "form": form,
                "accn": accn,
                "source_url": source_url,
                "source_date": source_date,
            }
        )

    # ------------------------------------------------------------------
    # 1) Revenue + net_margin + gross_margin from Eastmoney (single-Q)
    # ------------------------------------------------------------------
    for _, row in em_singleq.iterrows():
        end_ts = row["end"]
        rev = float(row["revenue_cny"])
        if rev <= 0:
            continue
        rev_m = rev / 1e6
        # revenue (CNY_M)
        push(
            end_ts,
            "revenue",
            rev_m,
            "CNY_M",
            "quarterly_actual",
            f"eastmoney:{em_code}:revenue",
            em_source_url,
        )
        # val_usd (USD_M)
        fx_rate = fx_at(fx, end_ts)
        if fx_rate and fx_rate > 0:
            push(
                end_ts,
                "val_usd",
                rev_m / fx_rate,
                "USD_M",
                "quarterly_actual",
                f"eastmoney:{em_code}:val_usd",
                em_source_url,
            )
        # gross_margin (pct) — straight from Eastmoney
        if not pd.isna(row["gross_margin_pct"]):
            push(
                end_ts,
                "gross_margin",
                float(row["gross_margin_pct"]),
                "pct",
                "quarterly_actual",
                f"eastmoney:{em_code}:gross_margin",
                em_source_url,
            )
        # net_margin (pct) — derived
        ni = row["net_profit_cny"]
        if not pd.isna(ni):
            push(
                end_ts,
                "net_margin",
                100.0 * float(ni) / rev,
                "pct",
                "quarterly_actual",
                f"eastmoney:{em_code}:net_margin",
                em_source_url,
            )

    # ------------------------------------------------------------------
    # 2) operating_margin + r_and_d_ratio
    #    Prefer yfinance quarterly_actual (last ~5 quarters with full P&L).
    #    For other quarters covered by an annual statement, synthesize from
    #    the annual ratio (form="annual_quarterized").
    # ------------------------------------------------------------------
    em_quarter_set = set(em_singleq["end"].tolist())

    # 2a) yfinance real quarters
    for end_ts in sorted(real_yf_quarters):
        rev = rev_q_yf.get(end_ts, float("nan"))
        if pd.isna(rev) or rev <= 0:
            continue
        oi = oi_q_yf.get(end_ts, float("nan"))
        rnd = rnd_q_yf.get(end_ts, float("nan"))
        if not pd.isna(oi):
            push(
                end_ts,
                "operating_margin",
                100.0 * float(oi) / float(rev),
                "pct",
                "quarterly_actual",
                f"yfinance:{symbol}:operating_margin",
                yf_source_url,
            )
        if not pd.isna(rnd):
            push(
                end_ts,
                "r_and_d_ratio",
                100.0 * float(rnd) / float(rev),
                "pct",
                "quarterly_actual",
                f"yfinance:{symbol}:r_and_d_ratio",
                yf_source_url,
            )

    # 2b) Synthesized from annual for quarters where Eastmoney has revenue
    #     but yfinance has no real quarterly OI/R&D.
    for annual_end in sorted(rev_a_yf.index):
        ann_rev = rev_a_yf.get(annual_end, float("nan"))
        if pd.isna(ann_rev) or ann_rev <= 0:
            continue
        ann_oi = oi_a_yf.get(annual_end, float("nan"))
        ann_rnd = rnd_a_yf.get(annual_end, float("nan"))
        oi_ratio = 100.0 * float(ann_oi) / float(ann_rev) if not pd.isna(ann_oi) else float("nan")
        rnd_ratio = 100.0 * float(ann_rnd) / float(ann_rev) if not pd.isna(ann_rnd) else float("nan")

        year = annual_end.year
        synth_quarter_ends = [
            pd.Timestamp(year=year, month=3, day=31),
            pd.Timestamp(year=year, month=6, day=30),
            pd.Timestamp(year=year, month=9, day=30),
            pd.Timestamp(year=year, month=12, day=31),
        ]
        for q_end in synth_quarter_ends:
            if q_end < earliest_synth:
                continue
            # Only synthesize when this quarter has a revenue row (Eastmoney
            # or yfinance) AND yfinance has no real quarterly OI/R&D for it.
            has_revenue_row = q_end in em_quarter_set or q_end in real_yf_quarters
            if not has_revenue_row:
                continue
            if q_end in real_yf_quarters:
                # yfinance gave us real quarterly OI / R&D — skip synth
                continue
            if not pd.isna(oi_ratio):
                push(
                    q_end,
                    "operating_margin",
                    oi_ratio,
                    "pct",
                    "annual_quarterized",
                    f"yfinance:{symbol}:operating_margin_annual",
                    yf_source_url,
                )
            if not pd.isna(rnd_ratio):
                push(
                    q_end,
                    "r_and_d_ratio",
                    rnd_ratio,
                    "pct",
                    "annual_quarterized",
                    f"yfinance:{symbol}:r_and_d_ratio_annual",
                    yf_source_url,
                )

    if not rows:
        return pd.DataFrame(columns=CANONICAL_COLS)

    df = pd.DataFrame(rows)
    df["end"] = pd.to_datetime(df["end"])
    df["val"] = df["val"].astype("float64")
    df["source_date"] = pd.to_datetime(df["source_date"])
    df = df.sort_values(["end", "tag"]).reset_index(drop=True)
    return df[CANONICAL_COLS]


# ---------------------------------------------------------------------------
# Provenance + summary
# ---------------------------------------------------------------------------
def status_label(d: dict) -> str:
    total = d.get("total_quarters", 0)
    if total >= 18:
        return "OK"
    if total >= 10:
        return "PARTIAL"
    return "MISSING"


def write_provenance(per_ticker_summary: dict) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = []
    for sym, _em, name in TICKERS:
        d = per_ticker_summary[sym]
        rows.append(
            f"| {sym} | {name} | {d['actual_quarters']} | {d['synth_quarters']} | "
            f"{d['total_quarters']} | {d['date_min']} → {d['date_max']} | {status_label(d)} |"
        )
    table = "\n".join(rows) if rows else "(no rows)"

    body = f"""# PMIC EFA — China comparables (Unit 14)

**Fetched:** {now}
**Tickers:** 300661.SZ (SG Micro), 688484.SS (SouthChip)
**Output:** `data/pmic_efa/pmic_china_quarterly.parquet`

## Source viability summary

| ticker | name | actual Qs (CNY rev) | synth Qs | total Qs | range | status |
|---|---|---|---|---|---|---|
{table}

`actual Qs` counts only `tag="revenue", val_unit="CNY_M", form="quarterly_actual"`
rows. `synth Qs` counts revenue rows with `form="annual_quarterized"`. In this
build all revenue rows are derived from Eastmoney's YTD figures (real data,
back-differenced into single quarters) so the synth column for revenue is 0.
The synthesized rows we *do* emit are `operating_margin` and `r_and_d_ratio`
for older quarters where yfinance has no detail — those are tracked in the
"rows by (ticker, tag, form)" table printed by the script.

## Sources

### Primary: Eastmoney `RPT_LICO_FN_CPD`
- Endpoint: `{EASTMONEY_URL}`
- Returns YTD cumulative revenue (TOTAL_OPERATE_INCOME), parent net profit
  (PARENT_NETPROFIT) and gross margin pct (XSMLL) per period end.
- Coverage: SG Micro 2012 → 2026-Q1 (45 YTD points); SouthChip 2019 → 2026-Q1
  (21 YTD points; firm IPO'd 2022-10).
- We back-difference YTD → single quarter inside each fiscal year.
- Direct fields used: revenue (CNY_M), net_margin (derived from NI/REV),
  gross_margin (XSMLL pct).

### Supplementary: yfinance
- `quarterly_income_stmt`: covers the most recent ~5 quarters with full
  income statement detail (Operating Income, R&D). Used for `operating_margin`
  and `r_and_d_ratio` `quarterly_actual` rows.
- `income_stmt` (annual): FY 2022 → FY 2025 used to synthesize older
  `operating_margin` and `r_and_d_ratio` rows. These carry
  `form="annual_quarterized"`.

⚠️  **Quarterization risk for operating_margin / r_and_d_ratio synthesized
rows**: We project the *annual ratio* onto every unfilled quarter within
that fiscal year. This assumes margins don't swing seasonally — a common
simplification but not exact. China PMICs do have Q1/Q4 margin tilt from
inventory cycle and operating-leverage effects, so use these rows for trend
work, not for absolute single-quarter comparisons. Consumers can filter:

```python
df = df[df.form == "quarterly_actual"]
```

### FX
USD revenue rows (`tag="val_usd"`, `val_unit="USD_M"`) are computed as
`revenue_CNY_M / USD_per_CNY_mid_at_quarter_end`. The mid rate source:

> {PROVENANCE_FX_NOTE}

If a quarter sits before the earliest FX bar, we forward-fill with the
earliest known rate (logged in stderr at fetch time).

### Yahoo symbol mapping note
688484 is on the Shanghai STAR (科創板) board. The unit spec listed
`688484.SH`, but Yahoo returns 404 on `.SH`; the correct Yahoo suffix is
**`.SS`**. We use `.SS` as `entity_id` to preserve a direct round-trip
with yfinance.

### 688484.SS coverage
SouthChip IPO'd on the STAR board in October 2022. Eastmoney has 2019-Q4,
2020-Q4, 2021-Q3, 2021-Q4, then a complete 2022-onwards record. The e2e
check does not enforce ≥ 18 on this ticker; expected count is ~15–18
depending on how many YTD gaps exist before IPO.

## Output rows per quarter
Each quarter emits up to 6 canonical rows: revenue (CNY_M), val_usd (USD_M),
gross_margin (pct), operating_margin (pct), net_margin (pct),
r_and_d_ratio (pct).

## Reproduction
```bash
python3 scripts/fetch_pmic_china.py
```
"""
    out = PROV_DIR / "pmic_china.md"
    out.write_text(body, encoding="utf-8")
    sys.stderr.write(f"[prov] wrote {out}\n")


def print_summary(df: pd.DataFrame) -> None:
    print("\n=== PMIC China (Unit 14) summary ===")
    if df.empty:
        print("(no data)")
        return
    print(f"total rows: {len(df)}")
    print(f"tickers: {sorted(df.entity_id.unique())}")
    print(f"tags: {sorted(df.tag.unique())}")
    print(f"date range: {df['end'].min().date()} → {df['end'].max().date()}")

    print("\nrows by (ticker, tag, form):")
    grp = df.groupby(["entity_id", "tag", "form"]).size().rename("n").reset_index()
    print(grp.to_string(index=False))

    rev_cny = df[(df.tag == "revenue") & (df.val_unit == "CNY_M")]
    print("\nCNY revenue quarter counts (this is what the e2e test asserts):")
    print(rev_cny.groupby("entity_id").size().to_string())


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main() -> int:
    source_date = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))

    fx = fetch_fx_usdcny()
    if not fx.empty:
        sys.stderr.write(
            f"[fx] {len(fx)} bars; latest = {fx.index[-1].date()} → {fx.iloc[-1]:.4f}\n"
        )

    frames = []
    per_ticker_summary: dict[str, dict] = {}

    for symbol, em_code, name in TICKERS:
        sys.stderr.write(f"\n[ticker] {symbol} ({name})\n")
        em = fetch_eastmoney(em_code)
        time.sleep(0.5)
        em_singleq = ytd_to_single_quarter(em)
        sys.stderr.write(
            f"  eastmoney YTD rows={len(em)}, single-Q rows={len(em_singleq)}\n"
        )

        yf_pack = fetch_yfinance_oi_rnd(symbol)
        sys.stderr.write(
            f"  yfinance real Qs (rev): {len(yf_pack['rev_q'])}, "
            f"annual rows: {len(yf_pack['rev_a'])}\n"
        )

        # earliest synth boundary
        earliest_synth = (
            pd.Timestamp("2022-12-31") if symbol == "688484.SS" else pd.Timestamp("2017-03-31")
        )

        df = assemble_ticker_rows(
            symbol, em_code, name, em_singleq, yf_pack, fx, source_date, earliest_synth
        )
        frames.append(df)

        rev_rows = df[(df.tag == "revenue") & (df.val_unit == "CNY_M")]
        actual_q = (rev_rows.form == "quarterly_actual").sum()
        synth_q = (rev_rows.form == "annual_quarterized").sum()
        total_q = len(rev_rows)
        per_ticker_summary[symbol] = {
            "actual_quarters": int(actual_q),
            "synth_quarters": int(synth_q),
            "total_quarters": int(total_q),
            "date_min": rev_rows["end"].min().date().isoformat() if not rev_rows.empty else "n/a",
            "date_max": rev_rows["end"].max().date().isoformat() if not rev_rows.empty else "n/a",
        }

    if frames:
        combined = pd.concat(frames, ignore_index=True)
    else:
        combined = pd.DataFrame(columns=CANONICAL_COLS)

    if not combined.empty:
        out = OUT_DIR / "pmic_china_quarterly.parquet"
        combined.to_parquet(out, index=False)
        sys.stderr.write(f"[ok] wrote {out} rows={len(combined)}\n")
    else:
        sys.stderr.write("[warn] combined dataframe empty — parquet not written\n")

    write_provenance(per_ticker_summary)
    print_summary(combined)
    return 0


if __name__ == "__main__":
    sys.exit(main())
