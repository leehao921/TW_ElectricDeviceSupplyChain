#!/usr/bin/env python3
"""PMIC EFA Unit 15 — power & AI-server cycle context collector.

Fetches three TW tickers (PMIC peripheral / co-cyclical names) plus the
WSTS / SIA worldwide monthly semiconductor sales macro series, packaged as
exogenous variables for the PMIC sector Exploratory Factor Analysis.

Tickers (filename is ground truth — Golden Rule #2):
  2308  台達電    (Delta Electronics)     server PSU + cooling / power delivery
  6770  力積電    (Powerchip Semi Mfg)    8" foundry, niche DRAM/NOR — memory cycle beta
  2454  聯發科    (MediaTek)              Richtek (2017 absorbed) → PMIC legacy proxy

Macro (no ticker — string entity_id):
  WSTS_GLOBAL              monthly worldwide semiconductor sales (USD billions)

Outputs (canonical 11-col long-format schema):
  data/pmic_efa/pmic_context_quarterly.parquet
  data/pmic_efa/macro_semis_monthly.parquet
  data/pmic_efa/_provenance/pmic_context.md

Allowed partial failure: yfinance lookups and WSTS XLSX download are
independent — each surfaces its own status in the provenance file. Script
exits 0 even if WSTS is unreachable, so long as at least one parquet was
written.

Spec notes:
- yfinance for TW tickers only exposes 4-6 quarters of quarterly_income_stmt
  and ~4-5 years of annual income_stmt. We emit BOTH (fp='Q1'..'FY' for
  quarterly, fp='FY' for annual) so EFA can use whatever granularity
  downstream prefers. We do NOT extrapolate or fabricate to hit a row count;
  spec wants 20+ quarters but yfinance is the bottleneck for TW — limitation
  documented in provenance.md.
- MediaTek's PMIC contribution is via Richtek (2017 acquisition); using 2454
  topline is a *legacy proxy* and carve-out risk is flagged in provenance.
"""

from __future__ import annotations

import io
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "pmic_efa"
PROV_DIR = OUT_DIR / "_provenance"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PROV_DIR.mkdir(parents=True, exist_ok=True)

QUARTERLY_OUT = OUT_DIR / "pmic_context_quarterly.parquet"
MACRO_OUT = OUT_DIR / "macro_semis_monthly.parquet"
PROV_FILE = PROV_DIR / "pmic_context.md"

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

# --------------------------------------------------------------------------- #
# Ticker registry — name MUST match Pilot_Reports filename (Golden Rule #2).
# --------------------------------------------------------------------------- #
TICKERS: list[tuple[str, str, str]] = [
    ("2308", "台達電", "Delta Electronics — server PSU / cooling / power delivery"),
    ("6770", "力積電", "Powerchip Semi Mfg — 8\" foundry, memory cycle beta"),
    ("2454", "聯發科", "MediaTek — Richtek (2017) PMIC legacy proxy"),
]

WSTS_PRESS_URL = "https://www.wsts.org/67/Historical-Billings-Report"
WSTS_XLSX_PATTERNS = (
    "WSTS-Historical-Billings-Report",
    "Historical-Billings-Report",
)
# Direct XLSX guesses — checked first because the press page is a JS-rendered
# search index. If both 404, we fall through to scraping the page HTML.
WSTS_DIRECT_XLSX_CANDIDATES = (
    "https://www.wsts.org/esraCMS/extension/media/f/WST/7644/"
    "WSTS-Historical-Billings-Report-Apr_2026.xlsx",
    "https://www.wsts.org/esraCMS/extension/media/f/WST/7644/"
    "WSTS-Historical-Billings-Report-Mar_2026.xlsx",
    "https://www.wsts.org/esraCMS/extension/media/f/WST/7644/"
    "WSTS-Historical-Billings-Report-Feb_2026.xlsx",
)

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


# --------------------------------------------------------------------------- #
# yfinance helpers
# --------------------------------------------------------------------------- #
def _quarter_to_fp(end: pd.Timestamp) -> str:
    """Map a calendar quarter-end to a quarter-period label.

    Note: Q4 is labelled `Q4`, NOT `FY` — full-year (FY) data comes from the
    annual income statement and is a distinct figure (~4× a single Q4), so the
    two must be distinguishable in the parquet.
    """
    m = end.month
    return {3: "Q1", 6: "Q2", 9: "Q3", 12: "Q4"}.get(m, "Qx")


def _safe_div(num, denom):
    if num is None or denom is None:
        return None
    if pd.isna(num) or pd.isna(denom) or denom == 0:
        return None
    return float(num) / float(denom) * 100.0


def _emit_margins(stmt: pd.DataFrame, ticker_id: str, name: str,
                  form_label: str, accn: str, source_url: str,
                  fetch_date: datetime, freq: str) -> list[dict]:
    """Walk a yfinance income statement (quarterly or annual) and emit
    canonical rows for the five EFA-required tags.
    """
    out: list[dict] = []
    if stmt is None or stmt.empty:
        return out

    # Defensive: dedup row labels (rare yfinance edge case).
    if stmt.index.has_duplicates:
        stmt = stmt[~stmt.index.duplicated(keep="first")]

    def _at(label, col):
        return stmt.at[label, col] if label in stmt.index else None

    for end_col in stmt.columns:
        ts = pd.Timestamp(end_col)
        fp = _quarter_to_fp(ts) if freq == "quarterly" else "FY"

        revenue = _at("Total Revenue", end_col)
        gross_profit = _at("Gross Profit", end_col)
        operating_income = _at("Operating Income", end_col)
        net_income = _at("Net Income", end_col)
        rnd = _at("Research And Development", end_col)

        if revenue is None or pd.isna(revenue) or revenue == 0:
            # Without revenue we can't anchor any margin row — skip quarter.
            continue

        # Revenue (TWD millions per spec)
        out.append({
            "end": ts,
            "entity_id": ticker_id,
            "entity_name": name,
            "tag": "revenue",
            "val": float(revenue) / 1e6,
            "val_unit": "TWD_M",
            "fp": fp,
            "form": form_label,
            "accn": accn,
            "source_url": source_url,
            "source_date": pd.Timestamp(fetch_date),
        })

        for tag, num in (
            ("gross_margin", gross_profit),
            ("operating_margin", operating_income),
            ("net_margin", net_income),
            ("r_and_d_ratio", rnd),
        ):
            val = _safe_div(num, revenue)
            if val is None:
                continue
            out.append({
                "end": ts,
                "entity_id": ticker_id,
                "entity_name": name,
                "tag": tag,
                "val": val,
                "val_unit": "pct",
                "fp": fp,
                "form": form_label,
                "accn": accn,
                "source_url": source_url,
                "source_date": pd.Timestamp(fetch_date),
            })

    return out


def _resolve_ticker(yf, ticker_id: str) -> tuple[str, object]:
    """Try .TW then .TWO. Returns (yahoo_symbol, Ticker_obj). Raises on miss."""
    last_err: str | None = None
    for suffix in (".TW", ".TWO"):
        yahoo_sym = f"{ticker_id}{suffix}"
        try:
            t = yf.Ticker(yahoo_sym)
            info = t.info or {}
            if info.get("marketCap") or info.get("regularMarketPrice"):
                return yahoo_sym, t
            last_err = f"empty info for {yahoo_sym}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{yahoo_sym}: {e}"
    raise ValueError(f"yfinance: no valid suffix for {ticker_id} ({last_err})")


def fetch_yfinance_rows(fetch_date: datetime) -> tuple[list[dict], list[str]]:
    """Fetch all three tickers; combine quarterly + annual income statements."""
    import yfinance as yf

    fetch_iso = fetch_date.strftime("%Y-%m-%d")
    rows: list[dict] = []
    errors: list[str] = []

    for ticker_id, name, _role in TICKERS:
        try:
            yahoo_sym, t = _resolve_ticker(yf, ticker_id)
        except ValueError as e:
            sys.stderr.write(f"WARN: {e}\n")
            errors.append(str(e))
            continue

        source_url = f"https://finance.yahoo.com/quote/{yahoo_sym}"
        accn = f"yfinance:{fetch_iso}"

        # Quarterly
        try:
            qi = t.quarterly_income_stmt
        except Exception as e:  # noqa: BLE001
            errors.append(f"{yahoo_sym} quarterly_income_stmt: {e}")
            qi = pd.DataFrame()

        q_rows = _emit_margins(
            qi, ticker_id, name, "yfinance_quarterly", accn,
            source_url, fetch_date, freq="quarterly",
        )
        rows.extend(q_rows)

        # Annual (gives 4-5 additional FY-end data points)
        try:
            ai = t.income_stmt
        except Exception as e:  # noqa: BLE001
            errors.append(f"{yahoo_sym} income_stmt: {e}")
            ai = pd.DataFrame()

        a_rows = _emit_margins(
            ai, ticker_id, name, "yfinance_annual", accn,
            source_url, fetch_date, freq="annual",
        )
        # Annual FY rows are kept even at overlapping Dec-31 dates as quarterly
        # Q4 rows: they carry DIFFERENT semantics (FY revenue ~= 4 × Q4) and
        # are distinguished downstream by the `fp` column (`FY` vs `Q4`).
        rows.extend(a_rows)

        n_quarters = len({r["end"] for r in q_rows if r["tag"] == "revenue"})
        n_annual = len({r["end"] for r in a_rows if r["tag"] == "revenue"})
        sys.stderr.write(
            f"OK yfinance: {ticker_id} ({name}) -> {yahoo_sym} "
            f"[{n_quarters} quarters + {n_annual} extra annual FY]\n"
        )

    return rows, errors


# --------------------------------------------------------------------------- #
# WSTS macro
# --------------------------------------------------------------------------- #
def _try_download_xlsx(url: str, timeout: int = 30) -> bytes | None:
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (PMIC-EFA-Unit-15 collector)"},
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    if len(resp.content) < 10_000:
        # XLSX file should be at least 10kB; smaller likely error page
        return None
    return resp.content


def _discover_xlsx_url_from_page() -> str | None:
    """Scrape the WSTS press page for the current XLSX link."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    try:
        resp = requests.get(
            WSTS_PRESS_URL,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (PMIC-EFA-Unit-15 collector)"},
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(pat in href for pat in WSTS_XLSX_PATTERNS) and href.endswith(".xlsx"):
            if href.startswith("/"):
                href = "https://www.wsts.org" + href
            return href
    return None


def _parse_wsts_xlsx(content: bytes) -> pd.DataFrame:
    """Parse the WSTS Historical Billings Report 'Monthly Data' sheet.

    Layout (verified Apr 2026 release):
      Row 3: header (column 1 = 'January' … column 12 = 'December')
      Subsequent rows: year-block of [year-header, Americas, Europe, Japan,
        Asia Pacific, Worldwide]. We extract the 'Worldwide' row per year.

    Values are 1000 USD; we convert to USD billions (val_unit='USD_B').
    """
    df = pd.read_excel(io.BytesIO(content), sheet_name="Monthly Data",
                       header=None)
    rows: list[dict] = []
    current_year: int | None = None

    for _, row in df.iterrows():
        v0 = row.iloc[0]

        # Year header (integer between 1986 and 2100)
        try:
            year_candidate = int(v0)
            if 1986 <= year_candidate <= 2100:
                current_year = year_candidate
                continue
        except (ValueError, TypeError):
            pass

        if current_year is not None and str(v0).strip() == "Worldwide":
            for col_idx, month_name in enumerate(MONTHS, start=1):
                val = row.iloc[col_idx]
                if pd.isna(val):
                    continue
                month = col_idx
                # Month-end timestamp
                end_ts = (pd.Timestamp(year=current_year, month=month, day=1)
                          + pd.offsets.MonthEnd(0))
                rows.append({
                    "year": current_year,
                    "month": month,
                    "end": end_ts,
                    # 1000 USD -> USD billions
                    "val_usd_b": float(val) / 1e6,
                })
    return pd.DataFrame(rows)


def fetch_wsts_rows(fetch_date: datetime) -> tuple[list[dict], list[str], str | None]:
    """Return (canonical_rows, error_messages, xlsx_url_used)."""
    errors: list[str] = []
    fetch_iso = fetch_date.strftime("%Y-%m-%d")
    content: bytes | None = None
    used_url: str | None = None

    # Try direct candidates first (avoids 1 round-trip when latest URL holds)
    for url in WSTS_DIRECT_XLSX_CANDIDATES:
        content = _try_download_xlsx(url)
        if content is not None:
            used_url = url
            break

    # Fall through: scrape the press page for the current link
    if content is None:
        sys.stderr.write(
            "WSTS direct candidates 404 — scraping press page for link...\n"
        )
        discovered = _discover_xlsx_url_from_page()
        if discovered:
            content = _try_download_xlsx(discovered)
            if content is not None:
                used_url = discovered
            else:
                errors.append(
                    f"WSTS: discovered URL {discovered} returned no XLSX"
                )
        else:
            errors.append(
                "WSTS: press page scrape did not surface an XLSX link"
            )

    if content is None:
        errors.append(
            "WSTS: all XLSX download attempts failed — macro parquet skipped"
        )
        return [], errors, None

    # Parse
    try:
        df = _parse_wsts_xlsx(content)
    except Exception as e:  # noqa: BLE001
        errors.append(f"WSTS XLSX parse failed: {e}")
        return [], errors, used_url

    if df.empty:
        errors.append("WSTS XLSX parsed but no 'Worldwide' rows surfaced")
        return [], errors, used_url

    accn = f"wsts:{fetch_iso}"
    rows: list[dict] = []
    for _, r in df.iterrows():
        rows.append({
            "end": r["end"],
            "entity_id": "WSTS_GLOBAL",
            "entity_name": "WSTS Global Semiconductor Sales",
            "tag": "monthly_sales",
            "val": float(r["val_usd_b"]),
            "val_unit": "USD_B",
            "fp": "monthly",
            "form": "wsts_press_release",
            "accn": accn,
            "source_url": used_url or WSTS_PRESS_URL,
            "source_date": pd.Timestamp(fetch_date),
        })
    sys.stderr.write(
        f"OK WSTS: {len(rows)} monthly worldwide rows, "
        f"{df['end'].min().date()} → {df['end'].max().date()}\n"
    )
    return rows, errors, used_url


# --------------------------------------------------------------------------- #
# Output / reporting
# --------------------------------------------------------------------------- #
def _to_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in CANONICAL_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[CANONICAL_COLS]
    df["end"] = pd.to_datetime(df["end"])
    df["source_date"] = pd.to_datetime(df["source_date"])
    df["val"] = df["val"].astype("float64")
    for col in ("entity_id", "entity_name", "tag", "val_unit", "fp",
                "form", "accn", "source_url"):
        df[col] = df[col].astype("string")
    df = df.sort_values(["entity_id", "tag", "end"]).reset_index(drop=True)
    return df


def _print_ascii_summary(qdf: pd.DataFrame, mdf: pd.DataFrame) -> None:
    print()
    print("=" * 72)
    print("PMIC EFA UNIT 15 — context fetch summary")
    print("=" * 72)

    if not qdf.empty:
        rev = qdf[qdf["tag"] == "revenue"]
        print("\n[TW ticker quarterly + annual coverage]")
        print(f"{'ticker':<8} {'name':<10} {'rows':>6} {'first':<12} {'last':<12}")
        print("-" * 52)
        for tid, name, _ in TICKERS:
            sub = rev[rev["entity_id"] == tid].sort_values("end")
            if sub.empty:
                print(f"{tid:<8} {name:<10} {'n/a':>6}")
                continue
            print(f"{tid:<8} {name:<10} {len(sub):>6} "
                  f"{sub['end'].min().strftime('%Y-%m-%d'):<12} "
                  f"{sub['end'].max().strftime('%Y-%m-%d'):<12}")

        print("\n[Latest quarter revenue / margins (TWD M)]")
        print(f"{'ticker':<8} {'name':<10} {'q_end':<12} {'fp':<4} "
              f"{'rev_M':>12} {'gm%':>7} {'om%':>7} {'nm%':>7} {'rd%':>7}")
        print("-" * 76)
        for tid, name, _ in TICKERS:
            # Restrict to genuine single-quarter rows (exclude FY annuals).
            sub = qdf[(qdf["entity_id"] == tid)
                      & (qdf["fp"].isin(("Q1", "Q2", "Q3", "Q4")))]
            if sub.empty:
                print(f"{tid:<8} {name:<10} {'n/a':<12}")
                continue
            last_end = sub["end"].max()
            snap = sub[(sub["end"] == last_end)
                      & (sub["form"] == "yfinance_quarterly")]
            fp_label = snap["fp"].iloc[0] if not snap.empty else "?"

            def _g(t):
                r = snap[snap["tag"] == t]
                return float(r.iloc[0]["val"]) if not r.empty else None

            def _fmt(v, w=7):
                return f"{'—':>{w}}" if v is None else f"{v:>{w}.1f}"

            print(f"{tid:<8} {name:<10} "
                  f"{last_end.strftime('%Y-%m-%d'):<12} "
                  f"{fp_label:<4} "
                  f"{(_g('revenue') or 0):>12,.0f} "
                  f"{_fmt(_g('gross_margin'))} "
                  f"{_fmt(_g('operating_margin'))} "
                  f"{_fmt(_g('net_margin'))} "
                  f"{_fmt(_g('r_and_d_ratio'))}")

    if not mdf.empty:
        print(f"\n[WSTS Worldwide monthly sales (USD B)]")
        print(f"rows : {len(mdf)} months")
        print(f"range: {mdf['end'].min().strftime('%Y-%m')} "
              f"→ {mdf['end'].max().strftime('%Y-%m')}")
        last12 = mdf.sort_values("end").tail(12)
        print("\nlast 12 months:")
        for _, r in last12.iterrows():
            print(f"  {r['end'].strftime('%Y-%m')}  {r['val']:7.2f}")
    else:
        print("\n[WSTS] no rows produced — see _provenance/pmic_context.md")
    print()


def _write_provenance(
    fetch_date: datetime,
    quarterly_rows: int,
    macro_rows: int,
    yf_errors: list[str],
    wsts_errors: list[str],
    wsts_url: str | None,
    qdf: pd.DataFrame,
) -> None:
    fetch_iso = fetch_date.strftime("%Y-%m-%d %H:%M:%S %Z").strip()

    # Per-ticker status
    yf_status_lines: list[str] = []
    if not qdf.empty:
        rev = qdf[qdf["tag"] == "revenue"]
        for tid, name, role in TICKERS:
            sub = rev[rev["entity_id"] == tid]
            if sub.empty:
                yf_status_lines.append(
                    f"- **{tid} {name}** — ✗ no rows (see warnings)"
                )
            else:
                yf_status_lines.append(
                    f"- **{tid} {name}** ({role}) — ✓ {len(sub)} revenue rows, "
                    f"{sub['end'].min().date()} → {sub['end'].max().date()}"
                )
    else:
        for tid, name, role in TICKERS:
            yf_status_lines.append(f"- **{tid} {name}** ({role}) — ✗ no data")

    wsts_status = "✓" if macro_rows > 0 else "✗"
    wsts_summary = (
        f"{macro_rows} months fetched from `{wsts_url}`"
        if wsts_url and macro_rows > 0
        else "download failed — see warnings below"
    )

    lines = [
        "# PMIC EFA Unit 15 — context provenance",
        "",
        f"**Fetch run:** {fetch_iso}",
        "",
        "## Purpose",
        "",
        "Unit 15 supplies the *exogenous variables* for the PMIC sector EFA.",
        "These tickers do not represent pure PMIC names; they provide the",
        "**power / AI server cycle context** and **memory cycle beta** that",
        "let factor analysis separate sector-specific PMIC factors from",
        "macro/cycle factors shared with the broader semiconductor complex.",
        "",
        "## Tickers",
        "",
        "| ticker | name | role |",
        "|---|---|---|",
        "| 2308 | 台達電 | Global PSU leader — server / AI rack power delivery, liquid cooling |",
        "| 6770 | 力積電 | 8\" foundry — niche DRAM/NOR — memory cycle high beta |",
        "| 2454 | 聯發科 | Richtek (2017 absorbed) → PMIC legacy revenue proxy |",
        "",
        "## yfinance status",
        "",
        *yf_status_lines,
        "",
        "## WSTS / SIA macro status",
        "",
        f"- **WSTS_GLOBAL monthly_sales** — {wsts_status} {wsts_summary}",
        "",
        "## Output rows",
        "",
        f"- `pmic_context_quarterly.parquet`: {quarterly_rows} rows "
        f"(3 tickers × 5 tags × quarterly+annual)",
        f"- `macro_semis_monthly.parquet`: {macro_rows} rows",
        "",
        "## Schema",
        "",
        "Both parquets share the 11-column canonical IP-DB long format:",
        "`end, entity_id, entity_name, tag, val, val_unit, fp, form, accn,",
        "source_url, source_date`. For the macro file, `entity_id =",
        "\"WSTS_GLOBAL\"` (string identifier, not a stock ticker).",
        "",
        "## Caveats",
        "",
        "1. **yfinance limit on TW tickers** — Yahoo Finance only surfaces",
        "   ~4-6 quarters of `quarterly_income_stmt` and 4-5 years of annual",
        "   `income_stmt` for Taiwan-listed names. We emit BOTH (each with",
        "   distinct `fp` labels) so the EFA caller can choose granularity.",
        "   The spec target of 20+ quarters per ticker is unattainable from",
        "   yfinance alone; reaching that would require TWSE MOPS / official",
        "   filings ingestion (out of scope for this unit).",
        "2. **2454 (MediaTek) PMIC carve-out risk** — MediaTek absorbed",
        "   Richtek (立錡, the dominant standalone TW PMIC name) in 2017.",
        "   Since then there has been no segment disclosure; using MediaTek",
        "   topline / margins as PMIC proxies will overweight the broader",
        "   SoC cycle. EFA downstream should regress against the WSTS macro",
        "   row to absorb the SoC-cycle component before reading any",
        "   PMIC-specific signal from 2454.",
        "3. **WSTS / SIA freshness** — the Historical Billings Report XLSX is",
        "   refreshed monthly. The download URL embeds the publication month",
        "   (e.g. `…-Apr_2026.xlsx`). The script first tries the most recent",
        "   guesses, then scrapes the press page link as a fallback.",
        "",
        "## Warnings / errors",
        "",
    ]
    if not yf_errors and not wsts_errors:
        lines.append("- (none — clean run)")
    else:
        for e in yf_errors:
            lines.append(f"- yfinance: {e}")
        for e in wsts_errors:
            lines.append(f"- wsts:     {e}")
    lines.append("")
    PROV_FILE.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    fetch_date = datetime.now(timezone.utc)

    yf_rows, yf_errors = fetch_yfinance_rows(fetch_date)
    wsts_rows, wsts_errors, wsts_url = fetch_wsts_rows(fetch_date)

    qdf = _to_dataframe(yf_rows)
    mdf = _to_dataframe(wsts_rows)

    if not qdf.empty:
        qdf.to_parquet(QUARTERLY_OUT, index=False)
        sys.stderr.write(f"Wrote {QUARTERLY_OUT} ({len(qdf)} rows)\n")
    else:
        sys.stderr.write("WARN: quarterly dataframe empty — parquet not written\n")

    if not mdf.empty:
        mdf.to_parquet(MACRO_OUT, index=False)
        sys.stderr.write(f"Wrote {MACRO_OUT} ({len(mdf)} rows)\n")
    else:
        sys.stderr.write("WARN: macro dataframe empty — parquet not written\n")

    _write_provenance(fetch_date, len(qdf), len(mdf), yf_errors,
                      wsts_errors, wsts_url, qdf)
    _print_ascii_summary(qdf, mdf)

    return 0


if __name__ == "__main__":
    sys.exit(main())
