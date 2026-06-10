#!/usr/bin/env python3
"""Fetch PMIC EFA Unit 13: TW PMIC tail-3 quarterly fundamentals.

Tickers (Golden Rule #2 — filename / official roster is ground truth):
  4961  天鈺      (Fitipower)              中小型 PMIC + display driver + touch    [.TW]
  3588  通嘉      (Leadtrend)              中小型 PMIC                              [.TW]
  3438  類比科    (Analog Integrations)    純 analog IC, OTC 上櫃                   [.TWO]

Output (canonical EFA long-format schema, identical to Unit 12):
  data/pmic_efa/pmic_tail3_quarterly.parquet
  data/pmic_efa/_provenance/pmic_tail3.md

Tags emitted (per ticker × quarter):
  revenue          (TWD_M)   — quarter-only sales (no cumulative)
  gross_margin     (pct)
  operating_margin (pct)
  net_margin       (pct)
  r_and_d_ratio    (pct)

Data sources (tiered, no mocks):
  1. yfinance .quarterly_financials                   — 5 most-recent quarters.
  2. MOPS t164sb04 (HTML) via mopsov.twse.com.tw      — backfill to 20+ quarters.
     Q1 = standalone 3-month.  Q2 / Q3 = standalone quarter column (8-col layout).
     Q4 = annual; Q4 single-quarter is derived as (annual - 9M cumulative). The
     9M cumulative comes from the same year's Q3 filing.
  3. If a ticker still ends < 20 quarters, the gap is flagged in provenance.md.

Schema columns (11, identical to IP DB canonical):
  end | entity_id | entity_name | tag | val | val_unit
  fp  | form      | accn        | source_url | source_date
"""

from __future__ import annotations

import http.cookiejar
import re
import ssl
import sys
import time
import urllib.parse as up
import urllib.request as ur
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "pmic_efa"
PROV_DIR = OUT_DIR / "_provenance"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PROV_DIR.mkdir(parents=True, exist_ok=True)

QUARTERLY_OUT = OUT_DIR / "pmic_tail3_quarterly.parquet"
PROV_FILE = PROV_DIR / "pmic_tail3.md"

# --------------------------------------------------------------------------- #
# Ticker registry. yfinance suffix established from probe — do not auto-switch.
# (4961 + 3588 list TWSE -> .TW;  3438 lists TPEX -> .TWO.)
# --------------------------------------------------------------------------- #
TICKERS: list[tuple[str, str, str, str]] = [
    # (ticker, entity_name, yfinance_suffix, market)
    ("4961", "天鈺",   ".TW",  "TWSE"),
    ("3588", "通嘉",   ".TW",  "TWSE"),
    ("3438", "類比科", ".TWO", "TPEX"),
]

CANONICAL_COLS = [
    "end", "entity_id", "entity_name",
    "tag", "val", "val_unit",
    "fp", "form", "accn",
    "source_url", "source_date",
]

# Backfill window: ROC year 108 (2019) is the earliest reliably-served MOPS
# year for these issuers (probe-confirmed). 108..115 x Q1..Q4 = 28 quarters,
# plus 115 Q1 once filed — well above the 20-quarter floor.
MOPS_YEARS_ROC = list(range(108, 116))     # 108 .. 115
MOPS_SEASONS = [1, 2, 3, 4]
YFINANCE_SLEEP = 0.3                       # spec requirement
MOPS_SLEEP = 0.6                           # be polite to mopsov

# --------------------------------------------------------------------------- #
# yfinance — last few quarters with high confidence
# --------------------------------------------------------------------------- #
def fetch_yfinance_rows(fetch_date: datetime) -> tuple[list[dict], list[str]]:
    import yfinance as yf

    fetch_iso = fetch_date.strftime("%Y-%m-%d")
    accn = f"yfinance:{fetch_iso}"
    rows: list[dict] = []
    errors: list[str] = []

    for ticker_id, entity_name, suffix, _market in TICKERS:
        yahoo_sym = f"{ticker_id}{suffix}"
        source_url = f"https://finance.yahoo.com/quote/{yahoo_sym}"
        try:
            t = yf.Ticker(yahoo_sym)
            qf = t.quarterly_financials
        except Exception as e:  # noqa: BLE001
            errors.append(f"yfinance {yahoo_sym}: {e}")
            time.sleep(YFINANCE_SLEEP)
            continue

        if qf is None or qf.empty:
            errors.append(f"yfinance {yahoo_sym}: quarterly_financials empty")
            time.sleep(YFINANCE_SLEEP)
            continue

        if qf.index.has_duplicates:
            qf = qf[~qf.index.duplicated(keep="first")]

        for q_end in qf.columns:
            q_ts = pd.Timestamp(q_end)
            fp_label = _month_to_fp(q_ts.month)
            rev = qf.at["Total Revenue", q_end] if "Total Revenue" in qf.index else None
            if rev is None or pd.isna(rev) or float(rev) == 0:
                continue
            rev_f = float(rev)
            # revenue (convert raw TWD -> TWD_M)
            rows.append(_row(q_ts, ticker_id, entity_name, "revenue",
                             rev_f / 1e6, "TWD_M",
                             fp_label, "yfinance", accn, source_url, fetch_date))
            # margins
            for label, tag in (("Gross Profit", "gross_margin"),
                               ("Operating Income", "operating_margin"),
                               ("Net Income", "net_margin")):
                if label not in qf.index:
                    continue
                v = qf.at[label, q_end]
                if pd.isna(v):
                    continue
                rows.append(_row(q_ts, ticker_id, entity_name, tag,
                                 float(v) / rev_f * 100.0, "pct",
                                 fp_label, "yfinance", accn, source_url, fetch_date))
            # R&D — yfinance label is "Research And Development"
            for label in ("Research And Development",
                          "Research Development"):
                if label in qf.index:
                    v = qf.at[label, q_end]
                    if pd.notna(v):
                        rows.append(_row(q_ts, ticker_id, entity_name, "r_and_d_ratio",
                                         float(v) / rev_f * 100.0, "pct",
                                         fp_label, "yfinance", accn, source_url, fetch_date))
                    break

        sys.stderr.write(f"OK yfinance: {ticker_id} ({entity_name}) -> {yahoo_sym} "
                         f"({len(qf.columns)} quarters)\n")
        time.sleep(YFINANCE_SLEEP)

    return rows, errors


# --------------------------------------------------------------------------- #
# MOPS scrape — backfill to 20+ quarters
# --------------------------------------------------------------------------- #
MOPS_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t164sb04"
MOPS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Referer": "https://mopsov.twse.com.tw/",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded",
}
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class _POST307Redirect(ur.HTTPRedirectHandler):
    """Default urllib handler does NOT redirect POST on 307. MOPS sometimes
    returns 307 (likely load-balancer pin) — re-POST to the new URL with the
    same body / headers."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code not in (301, 302, 303, 307, 308):
            return None
        new_req = ur.Request(
            newurl, data=req.data, method="POST",
            headers=dict(req.header_items()),
        )
        return new_req


_COOKIE_JAR = http.cookiejar.CookieJar()
_MOPS_OPENER = ur.build_opener(
    _POST307Redirect,
    ur.HTTPCookieProcessor(_COOKIE_JAR),
    ur.HTTPSHandler(context=_SSL_CTX),
)


def _mops_fetch_html(co_id: str, year_roc: int, season: int,
                     max_attempts: int = 4) -> str:
    """POST to MOPS and return decoded HTML (utf-8). Empty string on hard fail.

    Retries with exponential backoff on transient errors (307 rate-limit
    redirects, 502, network blips). Uses a shared cookie jar so the
    load-balancer pin established on the first call is reused. Uses a custom
    opener that follows POST-on-307 redirects (urllib default skips them).
    """
    body = up.urlencode({
        "encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1",
        "queryName": "co_id", "inpuType": "co_id", "TYPEK": "all",
        "co_id": co_id, "year": str(year_roc), "season": str(season),
    }).encode("utf-8")
    last_err = None
    for attempt in range(max_attempts):
        # Build a fresh Request each attempt so headers aren't mutated by retries
        req = ur.Request(MOPS_URL, data=body, method="POST", headers=MOPS_HEADERS)
        try:
            r = _MOPS_OPENER.open(req, timeout=30)
            return r.read().decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            last_err = e
            # Exponential backoff: 1.5s, 3s, 6s, 12s
            time.sleep(1.5 * (2 ** attempt))
    sys.stderr.write(f"WARN MOPS {co_id} {year_roc}Q{season}: {last_err}\n")
    return ""


_NUM_CLEAN = re.compile(r"[,\s]")


def _to_float(s: str) -> float | None:
    if s is None:
        return None
    cleaned = _NUM_CLEAN.sub("", s).replace("(", "-").replace(")", "")
    if not cleaned or cleaned in {"-", "--"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_mops_rows(html: str) -> list[list[str]]:
    """Return a list of cell-arrays, one per <tr>."""
    out: list[list[str]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if cells:
            out.append(cells)
    return out


def _find_row(rows: list[list[str]], label: str) -> list[str] | None:
    for r in rows:
        if r and r[0] == label:
            return r
    # fallback to "starts with" for slight naming variants
    for r in rows:
        if r and r[0].startswith(label):
            return r
    return None


# MOPS label -> internal key. Listed in priority order; earlier labels win.
_LABEL_MAP = (
    ("營業收入合計",         "revenue"),
    ("營業毛利（毛損）淨額", "gross_profit"),
    ("營業毛利（毛損）",     "gross_profit"),
    ("營業利益（損失）",     "operating_income"),
    ("本期淨利（淨損）",     "net_income"),
    ("研究發展費用",         "r_and_d"),
)


def _extract_amounts(html: str, amount_col_idx: int) -> dict | None:
    """Pull MOPS line items at the given amount-column index (0-based on
    the amount-only sub-array, i.e. r[1] = idx 0, r[3] = idx 1, ...).

    Layout note: MOPS rows always interleave amount, %, amount, %, ...
    so amount_col_idx=0 -> r[1], amount_col_idx=1 -> r[3], idx=2 -> r[5], etc.
    """
    if "營業收入" not in html:
        return None
    rows = _parse_mops_rows(html)
    cell_idx = 1 + amount_col_idx * 2
    out: dict = {}
    for label, key in _LABEL_MAP:
        if key in out:
            continue
        r = _find_row(rows, label)
        if r is None or len(r) <= cell_idx:
            continue
        val = _to_float(r[cell_idx])
        if val is not None:
            out[key] = val
    return out if "revenue" in out else None


def _mops_extract_quarter(html: str, season: int) -> dict | None:
    """Single-quarter values for a season's filing.

    Q1: r[1] = curY single-quarter amount  (amount_col_idx=0)
    Q2/Q3: r[1] = curY single-quarter amount (amount_col_idx=0)
    Q4: r[1] = curY annual                (amount_col_idx=0)  — derived later
    """
    return _extract_amounts(html, amount_col_idx=0)


def _mops_extract_cumulative_9m(html: str) -> dict | None:
    """From Q3 filing: 9M cumulative (Jan-Sep) sits at amount_col_idx=2."""
    return _extract_amounts(html, amount_col_idx=2)


def _mops_extract_annual(html: str) -> dict | None:
    """From Q4 filing: annual sits at amount_col_idx=0."""
    return _extract_amounts(html, amount_col_idx=0)


def _quarter_end(year_roc: int, season: int) -> pd.Timestamp:
    year = year_roc + 1911
    end_month_day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}[season]
    return pd.Timestamp(year=year, month=end_month_day[0], day=end_month_day[1])


def _month_to_fp(month: int) -> str:
    return {3: "Q1", 6: "Q2", 9: "Q3", 12: "Q4"}.get(month, "Qx")


def _row(end_ts, ticker_id, entity_name, tag, val, val_unit,
         fp_label, form, accn, source_url, fetch_date) -> dict:
    return {
        "end": end_ts,
        "entity_id": ticker_id,
        "entity_name": entity_name,
        "tag": tag,
        "val": val,
        "val_unit": val_unit,
        "fp": fp_label,
        "form": form,
        "accn": accn,
        "source_url": source_url,
        "source_date": pd.Timestamp(fetch_date),
    }


def fetch_mops_rows(fetch_date: datetime) -> tuple[list[dict], list[str]]:
    fetch_iso = fetch_date.strftime("%Y-%m-%d")
    rows: list[dict] = []
    errors: list[str] = []

    for ticker_id, entity_name, _suffix, _market in TICKERS:
        # quarterly cache: {(year, season): single_quarter_amounts}
        single_q: dict[tuple[int, int], dict] = {}
        # 9M cum cache (Q3 only): {year: cum_amounts}
        cum_9m: dict[int, dict] = {}
        # annual cache: {year: annual_amounts}
        annual: dict[int, dict] = {}

        for year_roc in MOPS_YEARS_ROC:
            for season in MOPS_SEASONS:
                html = _mops_fetch_html(ticker_id, year_roc, season)
                time.sleep(MOPS_SLEEP)
                if not html or "營業收入" not in html:
                    continue
                if season in (1, 2, 3):
                    sq = _mops_extract_quarter(html, season)
                    if sq:
                        single_q[(year_roc, season)] = sq
                if season == 3:
                    cm = _mops_extract_cumulative_9m(html)
                    if cm:
                        cum_9m[year_roc] = cm
                if season == 4:
                    a = _mops_extract_annual(html)
                    if a:
                        annual[year_roc] = a

        # Derive Q4 single-quarter = annual - 9M cumulative
        for year_roc, ann in annual.items():
            cum = cum_9m.get(year_roc)
            if not cum:
                continue
            q4: dict = {}
            for k, v in ann.items():
                c = cum.get(k)
                if c is None:
                    continue
                q4[k] = v - c
            if "revenue" in q4 and q4["revenue"] > 0:
                single_q[(year_roc, 4)] = q4

        # Emit canonical rows
        source_url = f"https://mopsov.twse.com.tw/mops/web/ajax_t164sb04?co_id={ticker_id}"
        accn = f"mops:{fetch_iso}"
        for (year_roc, season), vals in sorted(single_q.items()):
            end_ts = _quarter_end(year_roc, season)
            fp_label = f"Q{season}"
            rev = vals.get("revenue")
            if rev is None or rev <= 0:
                continue
            # revenue (MOPS amounts are TWD thousands -> convert to TWD_M)
            rows.append(_row(end_ts, ticker_id, entity_name, "revenue",
                             rev / 1000.0, "TWD_M",
                             fp_label, "mops", accn, source_url, fetch_date))
            for key, tag in (("gross_profit", "gross_margin"),
                             ("operating_income", "operating_margin"),
                             ("net_income", "net_margin"),
                             ("r_and_d", "r_and_d_ratio")):
                v = vals.get(key)
                if v is None:
                    continue
                rows.append(_row(end_ts, ticker_id, entity_name, tag,
                                 v / rev * 100.0, "pct",
                                 fp_label, "mops", accn, source_url, fetch_date))

        if not single_q:
            errors.append(
                f"MOPS {ticker_id}: no parseable filings in "
                f"ROC {MOPS_YEARS_ROC[0]}..{MOPS_YEARS_ROC[-1]}")
        sys.stderr.write(
            f"OK MOPS: {ticker_id} ({entity_name}) -> "
            f"{len(single_q)} quarters\n")
    return rows, errors


# --------------------------------------------------------------------------- #
# Output / merge / reporting
# --------------------------------------------------------------------------- #
def _dedup_prefer_mops(df: pd.DataFrame) -> pd.DataFrame:
    """When yfinance + MOPS give the same (entity, end, tag), prefer MOPS
    (the primary, audited source). yfinance covers gap quarters MOPS missed.
    """
    if df.empty:
        return df
    df = df.copy()
    df["_pref"] = df["form"].map({"mops": 0, "yfinance": 1}).fillna(2)
    df = df.sort_values(["entity_id", "end", "tag", "_pref"])
    df = df.drop_duplicates(subset=["entity_id", "end", "tag"], keep="first")
    return df.drop(columns="_pref")


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


def _write_provenance(fetch_date: datetime, df: pd.DataFrame,
                      yf_errors: list[str], mops_errors: list[str]) -> None:
    fetch_iso = fetch_date.strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# PMIC EFA Unit 13 — TW PMIC tail-3 (provenance)",
        "",
        f"**Fetch run:** {fetch_iso}",
        "",
        "## Tickers",
        "",
        "| ticker | name | role | yfinance suffix |",
        "|---|---|---|---|",
        "| 4961 | 天鈺 | 中小型 PMIC + display driver + touch | .TW |",
        "| 3588 | 通嘉 | 中小型 PMIC (Leadtrend) | .TW |",
        "| 3438 | 類比科 | 純 analog IC (Analog Integrations, 上櫃) | .TWO |",
        "",
        "> 注意: 用戶 prompt 寫 \"3556\" 是 typo (3556 = 禾瑞亞 touch IC). 通嘉真正 ticker = 3588 已驗證.",
        "",
        "## Sources",
        "",
        "- **MOPS (mopsov.twse.com.tw) `t164sb04`** — primary. ROC 108..115 Q1..Q4. "
        "Q1 standalone, Q2/Q3 standalone single-quarter column (amount-col idx 0), "
        "Q4 single-quarter derived as (annual − 9M cumulative).",
        "- **yfinance** — fills any gap and provides most-recent quarters. "
        "MOPS preferred when both available (`_dedup_prefer_mops`).",
        "",
        "## Tags emitted",
        "",
        "- `revenue` (TWD_M)",
        "- `gross_margin` (pct)",
        "- `operating_margin` (pct)",
        "- `net_margin` (pct)",
        "- `r_and_d_ratio` (pct)",
        "",
        "## Coverage",
        "",
    ]
    if df.empty:
        lines.append("- (empty — fetch failed entirely)")
    else:
        rev = df[df["tag"] == "revenue"]
        per = rev.groupby("entity_id").size().sort_index()
        lines.append("| ticker | revenue quarters | min end | max end |")
        lines.append("|---|---|---|---|")
        for tid in per.index:
            sub = rev[rev["entity_id"] == tid]
            lines.append(f"| {tid} | {int(per[tid])} | "
                         f"{sub['end'].min().date()} | {sub['end'].max().date()} |")
    lines += ["", "## Warnings / errors", ""]
    if not yf_errors and not mops_errors:
        lines.append("- (none — clean run)")
    else:
        for e in yf_errors:
            lines.append(f"- yfinance: {e}")
        for e in mops_errors:
            lines.append(f"- mops:     {e}")

    # Floor check
    if not df.empty:
        rev = df[df["tag"] == "revenue"]
        per = rev.groupby("entity_id").size()
        gaps = per[per < 20]
        lines += ["", "## Floor check (>= 20 quarters per ticker)", ""]
        if gaps.empty:
            lines.append("- PASS — every ticker has >= 20 revenue quarters.")
        else:
            for tid in gaps.index:
                lines.append(f"- FLAG: {tid} only has {int(gaps[tid])} quarters.")
    lines.append("")
    PROV_FILE.write_text("\n".join(lines), encoding="utf-8")


def _print_ascii_summary(df: pd.DataFrame) -> None:
    print()
    print("=" * 72)
    print("PMIC EFA Unit 13 — TW PMIC tail-3 — fetch summary")
    print("=" * 72)
    if df.empty:
        print("\n(no rows — see provenance for failure detail)\n")
        return

    tickers = sorted(df["entity_id"].unique())
    tags = sorted(df["tag"].unique())
    quarters = sorted(df["end"].dt.strftime("%Y-%m-%d").unique())
    print(f"\n[4-dim summary]")
    print(f"  tickers  : {len(tickers)}  -> {tickers}")
    print(f"  tags     : {len(tags)}  -> {tags}")
    print(f"  quarters : {len(quarters)}  ({quarters[0]} .. {quarters[-1]})")
    print(f"  rows     : {len(df)}")

    print(f"\n[Per-ticker quarter count (revenue rows)]")
    rev = df[df["tag"] == "revenue"]
    for tid, name, _, _ in TICKERS:
        sub = rev[rev["entity_id"] == tid].sort_values("end")
        if sub.empty:
            print(f"  {tid} {name:<8}: 0 quarters")
            continue
        print(f"  {tid} {name:<8}: {len(sub):>2} quarters "
              f"({sub['end'].min().date()} -> {sub['end'].max().date()})")

    print(f"\n[tail(5) of full dataframe]")
    cols = ["end", "entity_id", "entity_name", "tag", "val", "val_unit", "fp", "form"]
    tail = df[cols].tail(5).to_string(index=False)
    print(tail)
    print()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    fetch_date = datetime.now(timezone.utc)
    sys.stderr.write(f"=== PMIC EFA Unit 13 fetch run @ {fetch_date.isoformat()} ===\n")

    yf_rows, yf_errors = fetch_yfinance_rows(fetch_date)
    mops_rows, mops_errors = fetch_mops_rows(fetch_date)

    df = _to_dataframe(yf_rows + mops_rows)
    df = _dedup_prefer_mops(df)

    if not df.empty:
        df.to_parquet(QUARTERLY_OUT, index=False)
        sys.stderr.write(f"Wrote {QUARTERLY_OUT} ({len(df)} rows)\n")
    else:
        sys.stderr.write("WARN: dataframe empty — parquet not written\n")

    _write_provenance(fetch_date, df, yf_errors, mops_errors)
    _print_ascii_summary(df)

    return 0


if __name__ == "__main__":
    sys.exit(main())
