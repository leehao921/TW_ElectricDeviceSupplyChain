#!/usr/bin/env python3
"""Fetch TW PMIC core-4 quarterly fundamentals (≥20 quarters per ticker).

Unit 12 of the PMIC EFA batch — collects 5+ years of quarterly revenue + four
margins for the four core TW PMIC names so the downstream EFA coordinator has
enough N to run KMO / Bartlett / parallel-analysis / Varimax-Promax rotation.

Tickers (Golden Rule #2: filename is ground truth):
  8081  致新       (GMT)        純 PMIC fabless
  6719  力智       (uPI)        華碩集團 PMIC + GaN MOSFET
  6138  茂達       (Anpec)      PMIC + 馬達 driver (2025/10 國巨入股 21.4%)
  6415  矽力-KY    (Silergy)    開曼註冊 / 杭州總部, 高度集中中國

Tags collected per (entity_id, quarter_end):
  revenue          (TWD_M)
  gross_margin     (pct)
  operating_margin (pct)
  net_margin       (pct)
  r_and_d_ratio    (pct)

Data sources (in fallback order):
  1. MOPS t164sb04 (mopsov.twse.com.tw) — IFRS 合併綜合損益表, 6+ years deep.
     This is the authoritative source — every TW listed issuer files here.
  2. yfinance quarterly_income_stmt — best-effort supplement for the very
     latest quarter if MOPS hasn't surfaced it yet (and as sanity check).

Single-quarter values are derived by differencing cumulative YTD across
seasons (see `_cumulative_to_single` below) — this is the only correct
approach because TWSE-listed issuers only publish the cumulative column.

Output (canonical schema, see data/ip_database/_provenance/SCHEMA.md):
  data/pmic_efa/pmic_core4_quarterly.parquet
  data/pmic_efa/_provenance/pmic_core4.md
"""

from __future__ import annotations

import re
import sys
import time
import warnings
from collections import defaultdict
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

PARQUET_OUT = OUT_DIR / "pmic_core4_quarterly.parquet"
PROV_FILE = PROV_DIR / "pmic_core4.md"

# --------------------------------------------------------------------------- #
# Ticker registry — must match Pilot_Reports filename (Golden Rule #2).
# --------------------------------------------------------------------------- #
TICKERS: list[tuple[str, str]] = [
    ("8081", "致新"),
    ("6719", "力智"),
    ("6138", "茂達"),
    ("6415", "矽力-KY"),
]

# Target depth — spec asks for ≥ 20 quarters; we hard-assert ≥ 18 so the run
# can succeed even when one ticker is mid-cycle and the very latest filing
# hasn't reached MOPS.
TARGET_QUARTERS = 20
MIN_QUARTERS = 18

# 5+ year backfill window for MOPS: ROC year 109..114 == AD 2020..2025.
ROC_YEARS = list(range(109, 115))

# MOPS endpoint — `mopsov` mirror is the one that responds; the bare
# `mops.twse.com.tw` host blocks POSTs from outside its in-browser session.
MOPS_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t164sb04"
MOPS_REFERER = "https://mops.twse.com.tw/mops/web/t164sb04"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
MOPS_SLEEP = 1.5  # be polite — MOPS rate-limits aggressively after ~20-30 calls
MOPS_MAX_RETRIES = 4  # exponential-backoff retries on the "security block" 686-byte page
MOPS_BACKOFF_BASE = 15.0  # seconds — first cooldown after a block, doubled each retry

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

# Map MOPS row-label substrings to internal field keys. We anchor on the
# 含括弧 label form used in the t164sb04 table; the `(?!淨額)` lookahead
# avoids matching the duplicated 「營業毛利（毛損）淨額」 restated row.
MOPS_ROW_PATTERNS = [
    ("revenue", re.compile(r"營業收入合計")),
    ("gross_profit", re.compile(r"營業毛利（毛損）(?!淨額)")),
    ("rnd", re.compile(r"研究發展費用")),
    ("operating_income", re.compile(r"營業利益（損失）")),
    ("net_income", re.compile(r"本期淨利（淨損）")),
]


# --------------------------------------------------------------------------- #
# MOPS scrape helpers
# --------------------------------------------------------------------------- #
def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _extract_numbers(text: str) -> list[float]:
    """Pull every numeric token (comma-grouped, optional decimal, parenthesised
    negatives) from the row text. Returns floats in document order.
    """
    out: list[float] = []
    for tok in re.findall(r"\(?-?[\d,]+(?:\.\d+)?\)?", text):
        clean = tok.replace(",", "")
        neg = False
        if clean.startswith("(") and clean.endswith(")"):
            clean = clean[1:-1]
            neg = True
        try:
            v = float(clean)
        except ValueError:
            continue
        if neg:
            v = -v
        out.append(v)
    return out


def _parse_mops_income(html: str, season: int) -> dict[str, float] | None:
    """Parse a MOPS t164sb04 response. Return a dict of CUMULATIVE TWD-thousand
    values for the *current* fiscal period: {revenue, gross_profit,
    operating_income, net_income, rnd}. Return None when the page didn't carry
    a usable table (issuer hasn't filed yet, or MOPS error).

    The MOPS t164sb04 table comes in two layouts depending on season + issuer:

      Layout A (4-numeric-value rows, used by 8081-style S01 and ALL S04):
        [cum_curr, %, cum_prior, %]
      Layout B (8-numeric-value rows, used by 6138-style S01):
        [cum_curr, %, sq_curr, %, cum_prior, %, sq_prior, %]
      Layout C (8-numeric-value rows, used by S02 and S03 for everyone):
        [sq_curr, %, sq_prior, %, cum_curr, %, cum_prior, %]

    Column-order disambiguation (Layout B vs C):
      B is only ever seen at S01, where single-quarter == cumulative trivially.
      C is the canonical S02/S03 layout per the t164sb04 header row.

      → S01: cumulative is at index 0 in both A and B (A has only 2 vals).
      → S02 / S03: cumulative is at index 2 (third numeric value).
      → S04: cumulative is at index 0 (Layout A only).

    We pick whichever index corresponds to the cumulative and difference
    cumulatives across seasons to derive single-quarter values downstream.
    """
    if "營業收入合計" not in html:
        return None

    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    out: dict[str, float] = {}
    for tr in trs:
        text = _strip_tags(tr)
        if not text:
            continue
        for key, pat in MOPS_ROW_PATTERNS:
            if key in out:
                continue
            if not pat.search(text):
                continue
            nums = _extract_numbers(text)
            # Drop the % columns (they appear at odd indices after the value).
            # nums interleaves [v, pct, v, pct, ...] — take every other.
            value_seq = nums[::2]
            if not value_seq:
                continue
            cum_idx = _cumulative_index(season, len(value_seq))
            if cum_idx >= len(value_seq):
                continue
            out[key] = value_seq[cum_idx]
            break
        if len(out) == len(MOPS_ROW_PATTERNS):
            break
    return out if "revenue" in out else None


def _cumulative_index(season: int, n_values: int) -> int:
    """Map season + non-pct column count to the index of the current-period
    cumulative value. See the layout table in `_parse_mops_income`.
    """
    if season in (1, 4):
        # Layout A or B (S01) / Layout A (S04) — cumulative is at index 0.
        return 0
    # S02, S03: Layout C — cumulative is at index 2 if a 4-value row,
    # else index 0 (defensive: very old filings may not include cumulative).
    if n_values >= 3:
        return 2
    return 0


class MopsExhausted(Exception):
    """Raised when MOPS_MAX_RETRIES are spent on security-block responses.

    Caller should log this in the provenance errors list so the operator
    can distinguish "issuer didn't file" (silent None) from "we got blocked
    and never recovered" (this exception).
    """


def _fetch_mops(session: requests.Session, ticker: str, roc_year: int,
                season: int) -> str:
    """POST to MOPS t164sb04 with retry-on-block.

    MOPS returns a ~686-byte HTML page ("FOR SECURITY REASONS, THIS PAGE CAN
    NOT BE ACCESSED.") after ~25 consecutive requests. We detect that body
    and cool down with exponential backoff. Genuine empty results (the
    issuer has not filed a given period) are also short responses but never
    contain the security-block text.

    Raises MopsExhausted when all retries return the security-block page or
    raise network errors, so the caller can surface the gap in provenance.
    """
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "queryName": "co_id",
        "inpuType": "co_id",
        "TYPEK": "all",   # one TYPEK value that works for TWSE *and* TPEX
        "isnew": "false",
        "co_id": ticker,
        "year": str(roc_year),
        "season": f"{season:02d}",
    }
    backoff = MOPS_BACKOFF_BASE
    last_text = ""
    for attempt in range(MOPS_MAX_RETRIES):
        try:
            r = session.post(MOPS_URL, data=payload, timeout=30)
            r.raise_for_status()
        except (requests.Timeout, requests.ConnectionError) as e:
            sys.stderr.write(
                f"  [{ticker} Y{roc_year}S{season}] network err: {e}; "
                f"sleep {backoff:.0f}s\n"
            )
            time.sleep(backoff)
            backoff *= 2
            continue
        last_text = r.text
        # Two short-body cases:
        #   (a) security block — ~686 bytes, body contains "FOR SECURITY REASONS"
        #   (b) genuine no-data — ~2500 bytes, body contains "公司不存在" or empty table
        # Only (a) is retryable. Everything else (including genuinely empty
        # quarterly filings) is returned as-is for the caller's parser to handle.
        if ("FOR SECURITY REASONS" in last_text
                or "因為安全性考量" in last_text):
            sys.stderr.write(
                f"  [{ticker} Y{roc_year}S{season}] security-blocked "
                f"({len(last_text)} bytes); sleep {backoff:.0f}s\n"
            )
            time.sleep(backoff)
            backoff *= 2
            continue
        return last_text
    # All retries exhausted (network errors or security blocks) — let caller
    # log it instead of silently returning an empty / blocked body.
    raise MopsExhausted(
        f"{ticker} Y{roc_year}S{season}: {MOPS_MAX_RETRIES} retries exhausted"
    )


def _season_to_quarter_end(roc_year: int, season: int) -> pd.Timestamp:
    ad_year = roc_year + 1911
    month_end = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}[season]
    return pd.Timestamp(ad_year, month_end[0], month_end[1])


def _quarter_end_to_fp(end: pd.Timestamp) -> str:
    return {3: "Q1", 6: "Q2", 9: "Q3", 12: "Q4"}.get(end.month, "Qx")


def _cumulative_to_single(
    cum_by_q: dict[pd.Timestamp, float],
) -> dict[pd.Timestamp, float]:
    """Convert {quarter_end: cumulative_YTD} -> {quarter_end: single_quarter}.

      Q1 single = Q1 cumulative.
      Qn single (n>1) = Qn cumulative − Q(n-1) cumulative, only if Q(n-1) is
      in the SAME fiscal year and is present. Otherwise drop — we do not
      fabricate.
    """
    out: dict[pd.Timestamp, float] = {}
    for q_end, cum in cum_by_q.items():
        if q_end.month == 3:
            out[q_end] = cum
            continue
        prev_month = q_end.month - 3
        prev_end_day = {3: 31, 6: 30, 9: 30}[prev_month]
        prev_q = pd.Timestamp(q_end.year, prev_month, prev_end_day)
        if prev_q not in cum_by_q:
            continue
        out[q_end] = cum - cum_by_q[prev_q]
    return out


# --------------------------------------------------------------------------- #
# yfinance helper (best-effort supplement — not required to hit MIN_QUARTERS)
# --------------------------------------------------------------------------- #
def _resolve_yf(yf, ticker_id: str):
    for suffix in (".TW", ".TWO"):
        sym = f"{ticker_id}{suffix}"
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            if info.get("marketCap") or info.get("regularMarketPrice"):
                return sym, t
        except Exception:  # noqa: BLE001
            continue
    return None, None


def fetch_yfinance_supplement(
    fetch_date: datetime,
) -> tuple[list[dict], dict[str, int]]:
    """Best-effort yfinance pull — adds rows the MOPS scrape may have missed
    (typically the most recent quarter). Returns (rows, {ticker: yf_q_count}).
    """
    try:
        import yfinance as yf
    except ImportError:
        return [], {}

    fetch_iso = fetch_date.strftime("%Y-%m-%d")
    rows: list[dict] = []
    counts: dict[str, int] = {}

    for ticker_id, entity_name in TICKERS:
        sym, t = _resolve_yf(yf, ticker_id)
        if t is None:
            counts[ticker_id] = 0
            continue
        try:
            qis = t.quarterly_income_stmt
        except Exception:  # noqa: BLE001
            qis = None
        if qis is None or qis.empty:
            counts[ticker_id] = 0
            continue
        if qis.index.has_duplicates:
            qis = qis[~qis.index.duplicated(keep="first")]

        rnd_label = None
        for lab in ("Research And Development", "Research Development"):
            if lab in qis.index:
                rnd_label = lab
                break

        qcount = 0
        source_url = f"https://finance.yahoo.com/quote/{sym}/financials"
        accn = f"yfinance:{fetch_iso}"
        for q_end in qis.columns:
            q_ts = pd.Timestamp(q_end)
            rev = qis.at["Total Revenue", q_end] \
                if "Total Revenue" in qis.index else None
            # Skip near-zero revenues — exact == 0 misses float artefacts
            # (delisted, restated, currency-conversion edge cases) that would
            # explode the margin denominators below.
            if rev is None or pd.isna(rev) or abs(float(rev)) < 1.0:
                continue
            rev_m = float(rev) / 1e6  # yfinance returns raw TWD; canonical = M

            qcount += 1
            base = dict(
                end=q_ts,
                entity_id=ticker_id,
                entity_name=entity_name,
                fp=_quarter_end_to_fp(q_ts),
                form="yfinance",
                accn=accn,
                source_url=source_url,
                source_date=pd.Timestamp(fetch_date),
            )
            rows.append({**base, "tag": "revenue", "val": rev_m,
                         "val_unit": "TWD_M"})

            def _add_margin(tag: str, label: str, take_abs: bool = False) -> None:
                if label not in qis.index:
                    return
                v = qis.at[label, q_end]
                if pd.isna(v):
                    return
                num = abs(float(v)) if take_abs else float(v)
                rows.append({
                    **base,
                    "tag": tag,
                    "val": num / float(rev) * 100.0,
                    "val_unit": "pct",
                })

            _add_margin("gross_margin", "Gross Profit")
            _add_margin("operating_margin", "Operating Income")
            _add_margin("net_margin", "Net Income")
            if rnd_label is not None:
                _add_margin("r_and_d_ratio", rnd_label, take_abs=True)

        counts[ticker_id] = qcount
        time.sleep(0.3)

    return rows, counts


# --------------------------------------------------------------------------- #
# Main MOPS-driven collection (authoritative — 5+ years deep)
# --------------------------------------------------------------------------- #
def fetch_mops_rows(
    fetch_date: datetime,
) -> tuple[list[dict], dict[str, list[pd.Timestamp]], list[str]]:
    """For each ticker, scrape MOPS season-by-season then derive single-quarter
    values. Returns (canonical_rows, {ticker: [quarter_ends_emitted]}, errors).
    """
    fetch_iso = fetch_date.strftime("%Y-%m-%d")
    errors: list[str] = []
    rows: list[dict] = []
    ticker_quarters: dict[str, list[pd.Timestamp]] = {tid: [] for tid, _ in TICKERS}

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Referer": MOPS_REFERER,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    })

    for ticker_idx, (ticker_id, entity_name) in enumerate(TICKERS):
        if ticker_idx > 0:
            # Inter-ticker cooldown — MOPS throttles after ~25 sequential POSTs.
            sys.stderr.write(
                "  [cooldown 20s between tickers to avoid MOPS rate limit]\n"
            )
            time.sleep(20.0)

        # cum_data[field][quarter_end] = cumulative_YTD_value_in_TWD_thousands
        cum_data: dict[str, dict[pd.Timestamp, float]] = defaultdict(dict)

        for roc_year in ROC_YEARS:
            for season in (1, 2, 3, 4):
                q_end = _season_to_quarter_end(roc_year, season)
                # Skip future quarter-ends
                if q_end > pd.Timestamp(fetch_date.date()):
                    continue
                try:
                    html = _fetch_mops(session, ticker_id, roc_year, season)
                except Exception as e:  # noqa: BLE001
                    errors.append(
                        f"{ticker_id} MOPS Y{roc_year}S{season}: {e}"
                    )
                    time.sleep(MOPS_SLEEP)
                    continue

                parsed = _parse_mops_income(html, season)
                time.sleep(MOPS_SLEEP)
                if parsed is None:
                    # Not necessarily an error — issuer may not have filed
                    # this period yet, or page returned empty body.
                    continue

                for field in ("revenue", "gross_profit", "operating_income",
                              "net_income", "rnd"):
                    if field in parsed:
                        cum_data[field][q_end] = parsed[field]

        if not cum_data.get("revenue"):
            errors.append(
                f"{ticker_id}: MOPS yielded no revenue cumulatives — "
                "no rows emitted"
            )
            continue

        # Difference cumulatives -> single quarters
        single: dict[str, dict[pd.Timestamp, float]] = {}
        for field, cum in cum_data.items():
            single[field] = _cumulative_to_single(cum)

        source_url = (
            f"https://mopsov.twse.com.tw/mops/web/t164sb04?co_id={ticker_id}"
        )
        accn = f"mops:{fetch_iso}"

        for q_end, rev_thousand in sorted(single["revenue"].items()):
            base = dict(
                end=q_end,
                entity_id=ticker_id,
                entity_name=entity_name,
                fp=_quarter_end_to_fp(q_end),
                form="mops",
                accn=accn,
                source_url=source_url,
                source_date=pd.Timestamp(fetch_date),
            )
            rev_m = rev_thousand / 1000.0   # thousands -> millions

            ticker_quarters[ticker_id].append(q_end)
            rows.append({**base, "tag": "revenue", "val": rev_m,
                         "val_unit": "TWD_M"})

            for field, tag, take_abs in (
                ("gross_profit", "gross_margin", False),
                ("operating_income", "operating_margin", False),
                ("net_income", "net_margin", False),
                ("rnd", "r_and_d_ratio", True),
            ):
                num_q = single.get(field, {}).get(q_end)
                # Use abs(rev) < 1 (TWD thousand) — exact == 0 misses sentinel
                # values that produce nonsense margins downstream.
                if num_q is None or abs(rev_thousand) < 1.0:
                    continue
                rows.append({
                    **base,
                    "tag": tag,
                    "val": (abs(num_q) if take_abs else num_q)
                            / rev_thousand * 100.0,
                    "val_unit": "pct",
                })

        sys.stderr.write(
            f"OK MOPS: {ticker_id} ({entity_name}) -> "
            f"{len(ticker_quarters[ticker_id])} quarters\n"
        )

    return rows, ticker_quarters, errors


# --------------------------------------------------------------------------- #
# Merge / dedupe / output
# --------------------------------------------------------------------------- #
def _to_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in CANONICAL_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[CANONICAL_COLS]

    # Normalize timestamps to tz-naive — yfinance index timestamps may be
    # tz-aware (e.g. US/Eastern) while MOPS rows are tz-naive. Mixing them in
    # a Series produces NaT for the mismatched rows. Coerce each element via
    # `_strip_tz` so the final Series is uniformly tz-naive datetime64[ns].
    def _strip_tz(ts):
        if ts is None or pd.isna(ts):
            return pd.NaT
        ts = pd.Timestamp(ts)
        return ts.tz_localize(None) if ts.tz is not None else ts

    df["end"] = df["end"].map(_strip_tz)
    df["end"] = pd.to_datetime(df["end"])
    df["source_date"] = df["source_date"].map(_strip_tz)
    df["source_date"] = pd.to_datetime(df["source_date"])
    df["val"] = df["val"].astype("float64")
    for col in ("entity_id", "entity_name", "tag", "val_unit", "fp",
                "form", "accn", "source_url"):
        df[col] = df[col].astype("string")
    # When the same (entity_id, tag, end) appears from both MOPS and yfinance,
    # MOPS wins — "mops" sorts before "yfinance" alphabetically, so keep=first
    # after sort retains the MOPS row.
    df = df.sort_values(["entity_id", "tag", "end", "form"])
    df = df.drop_duplicates(["entity_id", "tag", "end"], keep="first")
    df = df.sort_values(["entity_id", "tag", "end"]).reset_index(drop=True)
    return df


def _write_provenance(
    fetch_date: datetime,
    df: pd.DataFrame,
    yf_counts: dict[str, int],
    mops_quarters: dict[str, list[pd.Timestamp]],
    errors: list[str],
) -> str:
    """Write provenance markdown. Returns overall status (✓ / ⚠️ partial / ✗)."""
    fetch_iso = fetch_date.strftime("%Y-%m-%d %H:%M:%S UTC")
    rev_counts = (df[df["tag"] == "revenue"]
                  .groupby("entity_id").size().to_dict()) if not df.empty else {}

    overall = "✓"
    for tid, _ in TICKERS:
        n = rev_counts.get(tid, 0)
        if n < MIN_QUARTERS:
            overall = "✗"
            break
        if n < TARGET_QUARTERS and overall == "✓":
            overall = "⚠️ partial"

    lines = [
        "# PMIC EFA — core 4 quarterly fundamentals (Unit 12)",
        "",
        f"**Fetch run:** {fetch_iso}",
        f"**Status:** {overall}",
        "",
        "## Goal",
        "",
        f"Provide ≥ {TARGET_QUARTERS} quarters × 4 tickers of revenue + 4 margins",
        "so the PMIC EFA coordinator can run KMO + Bartlett + parallel analysis",
        "+ Varimax / Promax rotation with adequate N.",
        "",
        "## Tickers (Golden Rule #2 verified)",
        "",
        "| ticker | name | role |",
        "|---|---|---|",
        "| 8081 | 致新 | GMT — 純 PMIC fabless |",
        "| 6719 | 力智 | uPI — 華碩集團 PMIC + GaN MOSFET |",
        "| 6138 | 茂達 | Anpec — PMIC + 馬達 driver; 2025/10 國巨入股 21.4% |",
        "| 6415 | 矽力-KY | Silergy — 開曼註冊 / 杭州總部 |",
        "",
        "## Sources",
        "",
        f"- **MOPS** (authoritative): {MOPS_URL}",
        "  - POST `co_id=<ticker>&year=<ROC>&season=<01..04>&TYPEK=all`",
        f"  - Referer: {MOPS_REFERER}",
        f"  - User-Agent: `{USER_AGENT}`",
        f"  - Courtesy: `time.sleep({MOPS_SLEEP})` between calls.",
        f"  - Years scraped: ROC {ROC_YEARS[0]}..{ROC_YEARS[-1]} "
        f"(AD {ROC_YEARS[0]+1911}..{ROC_YEARS[-1]+1911}).",
        "- **yfinance** (best-effort supplement): "
        "`Ticker(\"<id>.TW\").quarterly_income_stmt`. "
        "Typically returns 5-6 most recent quarters; used to backfill the very latest",
        "  quarter if MOPS hasn't published it yet.",
        "",
        "## Quarter coverage per ticker (revenue series)",
        "",
        "| ticker | name | yfinance Q's | MOPS Q's | merged Q's | earliest | latest |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for tid, nm in TICKERS:
        sub = df[(df["entity_id"] == tid) & (df["tag"] == "revenue")] \
            if not df.empty else pd.DataFrame()
        n_merged = len(sub)
        earliest = sub["end"].min() if n_merged else None
        latest = sub["end"].max() if n_merged else None
        n_mops = len(mops_quarters.get(tid, []))
        n_yf = yf_counts.get(tid, 0)
        lines.append(
            f"| {tid} | {nm} | {n_yf} | {n_mops} | {n_merged} | "
            f"{earliest.strftime('%Y-%m-%d') if earliest is not None else '—'} | "
            f"{latest.strftime('%Y-%m-%d') if latest is not None else '—'} |"
        )

    lines.extend([
        "",
        "## Methodology — single-quarter derivation",
        "",
        "MOPS publishes cumulative year-to-date figures. For each (ticker, year)",
        "we scrape seasons 1..4 (Q1, H1, 9M, FY) and difference:",
        "",
        "- `Q1_single = Q1_cumulative`",
        "- `Q2_single = H1_cumulative − Q1_cumulative`",
        "- `Q3_single = 9M_cumulative − H1_cumulative`",
        "- `Q4_single = FY_cumulative − 9M_cumulative`",
        "",
        "Where any required prior-cumulative is missing, that single-quarter is",
        "dropped (we do NOT fabricate). Margins are computed per single quarter:",
        "ratio of single-quarter line item to single-quarter revenue × 100.",
        "",
        "## Output schema (canonical)",
        "",
        "| col | type | notes |",
        "|---|---|---|",
        "| end | datetime64 | quarter-end date |",
        "| entity_id | str | 4-digit ticker |",
        "| entity_name | str | TC name from filename |",
        "| tag | str | revenue / gross_margin / operating_margin / net_margin / r_and_d_ratio |",
        "| val | float64 | numeric (negative allowed for margins) |",
        "| val_unit | str | TWD_M or pct |",
        "| fp | str | Q1 / Q2 / Q3 / Q4 |",
        "| form | str | mops or yfinance |",
        "| accn | str | provenance accession |",
        "| source_url | str | URL of source page |",
        "| source_date | datetime64 | when fetched |",
        "",
        "## Warnings / errors",
        "",
    ])
    if not errors:
        lines.append("- (none — clean run)")
    else:
        for e in errors:
            lines.append(f"- {e}")
    lines.append("")
    lines.append(f"## Conclusion: {overall}")
    if overall == "✓":
        lines.append("")
        lines.append(
            f"All 4 tickers ≥ {TARGET_QUARTERS} quarters; coordinator may proceed."
        )
    elif overall.startswith("⚠️"):
        lines.append("")
        lines.append(
            f"All 4 tickers ≥ {MIN_QUARTERS} quarters; one or more under target "
            f"{TARGET_QUARTERS}. EFA proceeds but flag in downstream report."
        )
    else:
        lines.append("")
        lines.append(
            f"At least one ticker < {MIN_QUARTERS} quarters — EFA must NOT run."
        )

    PROV_FILE.write_text("\n".join(lines), encoding="utf-8")
    return overall


def _print_ascii_summary(df: pd.DataFrame) -> None:
    print()
    print("=" * 72)
    print("PMIC EFA — core 4 quarterly fundamentals (Unit 12)")
    print("=" * 72)

    print(f"\nTickers found: {sorted(df['entity_id'].unique())}")
    if df["entity_id"].nunique() != 4:
        print(f"  WARN: expected 4 tickers, got {df['entity_id'].nunique()}")

    print(f"Tags: {sorted(df['tag'].unique())}")
    print(f"Distinct quarter-ends: {df['end'].nunique()}")
    print(f"Total rows: {len(df)}")

    rev = df[df["tag"] == "revenue"]
    print("\n[Coverage — revenue series per ticker]")
    print(f"{'ticker':<8} {'name':<10} {'count':>6} {'earliest':<12} {'latest':<12}")
    print("-" * 52)
    for tid, nm in TICKERS:
        sub = rev[rev["entity_id"] == tid].sort_values("end")
        if sub.empty:
            print(f"{tid:<8} {nm:<10} {'0':>6} {'—':<12} {'—':<12}")
            continue
        print(f"{tid:<8} {nm:<10} {len(sub):>6} "
              f"{sub['end'].min().strftime('%Y-%m-%d'):<12} "
              f"{sub['end'].max().strftime('%Y-%m-%d'):<12}")

    counts = rev.groupby("entity_id").size()
    if not counts.empty:
        print(f"\nQuarters per ticker (revenue): min={counts.min()}, "
              f"max={counts.max()}")
        if counts.min() < MIN_QUARTERS:
            print(f"  WARN: min quarters per ticker {counts.min()} < "
                  f"{MIN_QUARTERS} — coordinator should NOT proceed with EFA")

    print("\n[Tail(5) sample rows]")
    tail = df.tail(5)
    for _, r in tail.iterrows():
        print(f"  {r['end'].strftime('%Y-%m-%d')} | {r['entity_id']:<5} "
              f"| {r['tag']:<18} | {r['val']:>12.3f} {r['val_unit']:<6} "
              f"| {r['form']}")
    print()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    fetch_date = datetime.now(timezone.utc)
    sys.stderr.write(
        f"[pmic_core4] starting fetch {fetch_date.isoformat()}\n"
    )

    # 1) MOPS (authoritative, deep history)
    mops_rows, mops_quarters, mops_errors = fetch_mops_rows(fetch_date)
    # 2) yfinance supplement
    yf_rows, yf_counts = fetch_yfinance_supplement(fetch_date)

    df = _to_dataframe(mops_rows + yf_rows)

    if df.empty:
        sys.stderr.write("FATAL: no rows collected\n")
        _write_provenance(
            fetch_date, df, yf_counts, mops_quarters,
            mops_errors + ["empty dataframe — no rows collected"],
        )
        return 1

    df.to_parquet(PARQUET_OUT, index=False)
    sys.stderr.write(f"Wrote {PARQUET_OUT} ({len(df)} rows)\n")

    overall = _write_provenance(
        fetch_date, df, yf_counts, mops_quarters, mops_errors,
    )
    sys.stderr.write(f"Wrote {PROV_FILE} (status={overall})\n")

    _print_ascii_summary(df)

    return 0


if __name__ == "__main__":
    sys.exit(main())
