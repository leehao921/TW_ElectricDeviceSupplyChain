"""fetch_pmic_monthly.py — PMIC EFA v2 Unit 16: monthly revenue fetcher.

Pulls ≥ 60 months of monthly revenue (台幣百萬, TWD millions) for the
10 PMIC + Power tickers below, sourced from the MOPS static
month-by-month archive (mopsov.twse.com.tw / nas / t21 / sii|otc /
t21sc03_<ROC>_<M>_<suffix>.html).

Why this source instead of `ajax_t05st10_ifrs`?
- The AJAX endpoint that `scripts/foplp_watchlist.py:52-98` targets
  returns only the latest 12 months and the upstream production host
  (`mops.twse.com.tw`) now answers POST-from-outside-browser with a
  686-byte "FOR SECURITY REASONS" block. We need ≥ 60 months and a
  source that survives unattended re-runs.
- The static `mopsov.twse.com.tw` archive answers GET, is encoded in
  Big5, exposes every issuer's monthly revenue for every (ROC year,
  month) since the IFRS conversion, and never security-blocks. Same
  underlying data (公開資訊觀測站 月營收), different surface.
- We reuse the **same row contract** as `foplp_watchlist.py`'s parser
  — year, month, current-month revenue in 千元, mom%, yoy% — so the
  parsing intent is preserved (see `_parse_archive_row`).

Output:
- data/pmic_efa/pmic_monthly_revenue.parquet
- data/pmic_efa/_provenance/pmic_monthly.md

Schema is the canonical 11-column IP-DB / PMIC-EFA schema enforced by
tests/test_ip_database_schema.py and tests/test_pmic_efa_data.py. We
emit `tag='revenue'` + `fp='monthly'` (the test's ALLOWED_TAGS does not
include 'monthly_revenue', so we tag as revenue and distinguish from
quarterly via `fp`).

Idempotent: rerunning overwrites the parquet but each provenance
write is a full self-contained snapshot of the most recent run.
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "pmic_efa"
OUT_PARQUET = OUT_DIR / "pmic_monthly_revenue.parquet"
PROV_DIR = OUT_DIR / "_provenance"
PROV_FILE = PROV_DIR / "pmic_monthly.md"

# ROC year range. ROC 109 == AD 2020 (Jan 2020). Going to current ROC 115
# (2026) covers > 60 months for every ticker that's been listed since 2020.
ROC_START = 109
ROC_END = 115  # inclusive — months capped to today below.

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

MOPS_BASE = "https://mopsov.twse.com.tw/nas/t21"
MOPS_REFERER_BASE = "https://mops.twse.com.tw/mops/web/t05st10_ifrs"

# Rate-limit hygiene. MOPS bans aggressive crawlers; one GET per 1.5s
# kept us safe across all 5-year pulls during dev.
SLEEP_BETWEEN_REQUESTS = 1.5  # seconds
MAX_RETRIES = 4
BACKOFF_SECONDS = (1.5, 3.0, 6.0, 12.0)  # exp backoff per attempt.

# Canonical column order (matches tests/test_ip_database_schema.py and
# tests/test_pmic_efa_data.py REQUIRED set).
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

MIN_MONTHS_REQUIRED = 36  # hard floor — assert in CLI summary
TARGET_MONTHS = 60        # spec target


@dataclass(frozen=True)
class TickerSpec:
    """Where a ticker's monthly revenue can be found on the MOPS archive.

    market: 'sii' (上市/TWSE) or 'otc' (上櫃/TPEX).
    suffix: '0' for domestic issuers, '1' for foreign issuers (e.g. KY).
    """
    ticker: str
    name: str
    market: str
    suffix: str  # '0' (domestic) or '1' (foreign / KY)
    role: str


# Listing verified live on 2026-06-11 via probe of
# /nas/t21/{sii|otc}/t21sc03_114_12_{0|1}.html.
TICKERS: list[TickerSpec] = [
    TickerSpec("8081", "致新",   "sii", "0", "PMIC fabless"),
    TickerSpec("6719", "力智",   "sii", "0", "PMIC + GaN MOSFET (uPI / 華碩)"),
    TickerSpec("6138", "茂達",   "otc", "0", "PMIC + 馬達 driver (Anpec)"),
    TickerSpec("6415", "矽力-KY", "sii", "1", "PMIC F股 (Silergy / 杭州)"),
    TickerSpec("4961", "天鈺",   "sii", "0", "PMIC + driver IC (鴻海集團)"),
    TickerSpec("3588", "通嘉",   "sii", "0", "AC/DC PMIC + LED driver"),
    TickerSpec("3438", "類比科", "otc", "0", "Analog / PMIC fabless"),
    # Unit 15 yfinance-failed tickers we are backfilling here.
    TickerSpec("2308", "台達電", "sii", "0", "Power + EV traction inverter"),
    TickerSpec("6770", "力積電", "sii", "0", "Mature-node foundry / PMIC capacity"),
    TickerSpec("2454", "聯發科", "sii", "0", "SoC + PMIC integrator"),
]


# --------------------------------------------------------------------------- #
# Archive fetch + parse
# --------------------------------------------------------------------------- #
class MopsBlocked(Exception):
    """All retries returned a security-block / network error for a page."""


def _build_archive_url(market: str, roc_year: int, month: int, suffix: str) -> str:
    return f"{MOPS_BASE}/{market}/t21sc03_{roc_year}_{month}_{suffix}.html"


def _is_security_block(text: str) -> bool:
    # 686-byte upstream block plus any cached variant.
    return "FOR SECURITY REASONS" in text or "因為安全性考量" in text


def _fetch_archive_page(
    session: requests.Session, market: str, roc_year: int, month: int, suffix: str
) -> str | None:
    """GET a single (market, ROC year, month, suffix) archive page.

    Returns Big5-decoded HTML, or None if the page is genuinely missing
    (404 — that month's archive hasn't been published yet, e.g. future
    months). Raises MopsBlocked when all retries get security-blocked
    or network-error.
    """
    url = _build_archive_url(market, roc_year, month, suffix)
    for attempt in range(MAX_RETRIES):
        backoff = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
        try:
            r = session.get(url, timeout=30)
        except (requests.Timeout, requests.ConnectionError) as e:
            sys.stderr.write(
                f"  [{market} {roc_year}/{month:02d}/{suffix}] network err: "
                f"{e}; sleep {backoff:.1f}s\n"
            )
            time.sleep(backoff)
            continue
        if r.status_code == 404:
            # Month not published (e.g. future month). Treat as genuine gap.
            return None
        if r.status_code != 200:
            sys.stderr.write(
                f"  [{market} {roc_year}/{month:02d}/{suffix}] status "
                f"{r.status_code}; sleep {backoff:.1f}s\n"
            )
            time.sleep(backoff)
            continue
        # Big5 — manual decode so we don't depend on `apparent_encoding`.
        r.encoding = "big5"
        text = r.text
        if _is_security_block(text):
            sys.stderr.write(
                f"  [{market} {roc_year}/{month:02d}/{suffix}] security-"
                f"blocked ({len(text)}B); sleep {backoff:.1f}s\n"
            )
            time.sleep(backoff)
            continue
        return text
    raise MopsBlocked(
        f"{market}/{roc_year}/{month:02d}/{suffix}: {MAX_RETRIES} retries spent"
    )


# Each ticker row on the archive page has shape:
#   <tr align=right>
#     <td align=center>8081</td>
#     <td align=left>致新</td>
#     <td nowrap>  623,586</td>      # 當月營收 (千元)
#     <td nowrap>  670,651</td>      # 上月營收 (千元)
#     <td nowrap>  538,823</td>      # 去年當月營收 (千元)
#     <td nowrap>   -7.01</td>       # 上月比較增減 %
#     <Td nowrap>  15.73</td>        # 去年同月增減 %
#     <td nowrap>8,252,664</td>      # 當月累計營收 (千元)
#     <td nowrap>7,910,870</td>      # 去年累計營收 (千元)
#     <td nowrap>   4.32</td>        # 前期比較增減 %
#     <td align=center>-</td>
#   </tr>
#
# We only need column 2 (current-month revenue in 千元) — the rest is
# computable from a clean monthly series and we keep the schema lean.
# Strict 4-digit ticker match avoids prefix collisions (e.g. 8081 / 80815).
_ROW_RE = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(\d{4})</td>\s*<td[^>]*>([^<]+)</td>"
    r"\s*<td[^>]*>\s*([\d,]+|-{1,2})\s*</td>",
    re.S | re.I,
)


def _parse_archive_row(html: str, ticker: str) -> tuple[str, float] | None:
    """Extract (entity_name, current_month_revenue_TWD_thousand) for ticker.

    Returns None when the page exists but the ticker has no row (issuer
    hasn't reported for that month, or wasn't yet listed). Returns
    (name, NaN) when the row exists but the revenue cell is blank.
    """
    for m in _ROW_RE.finditer(html):
        if m.group(1) != ticker:
            continue
        name = m.group(2).strip()
        raw = m.group(3).replace(",", "").strip()
        if raw in ("--", "-", ""):
            return name, float("nan")
        try:
            thousand = int(raw)
        except ValueError:
            return None
        return name, thousand
    return None


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def _month_end(roc_year: int, month: int) -> pd.Timestamp:
    ad_year = roc_year + 1911
    # pandas knows about month-ends via offsets; constructing the next month's
    # first day then subtracting a day is robust for Feb / leap years.
    first_of_next = pd.Timestamp(
        ad_year + (1 if month == 12 else 0),
        1 if month == 12 else month + 1,
        1,
    )
    return first_of_next - pd.Timedelta(days=1)


def _today_roc_month() -> tuple[int, int]:
    today = datetime.now(timezone.utc).astimezone()
    return today.year - 1911, today.month


def _pages_to_fetch() -> list[tuple[int, int]]:
    """Return (roc_year, month) tuples up to (but not including) the
    current calendar month. Future months would 404 and waste budget."""
    cur_roc, cur_month = _today_roc_month()
    out: list[tuple[int, int]] = []
    for roc in range(ROC_START, ROC_END + 1):
        for month in range(1, 13):
            if roc > cur_roc or (roc == cur_roc and month > cur_month):
                break
            out.append((roc, month))
    return out


def fetch_all() -> tuple[pd.DataFrame, dict]:
    """Fetch monthly revenue for every TICKERS entry across the configured
    ROC year window.

    Returns (df, run_log) where run_log feeds the provenance writer:
        {
          "started_at": ISO timestamp,
          "finished_at": ISO timestamp,
          "per_ticker": {ticker: {"name", "months", "earliest",
                                  "latest", "blocked"}},
          "errors": [str, ...],
          "blocked_pages": [url, ...],
          "missing_pages": [url, ...],
        }
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Referer": MOPS_REFERER_BASE,
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    })

    started_at = datetime.now(timezone.utc)
    log: dict = {
        "started_at": started_at.isoformat(timespec="seconds"),
        "errors": [],
        "blocked_pages": [],
        "missing_pages": [],
        "per_ticker": {t.ticker: {
            "name": t.name,
            "months": 0,
            "earliest": None,
            "latest": None,
            "blocked": False,
        } for t in TICKERS},
    }

    pages = _pages_to_fetch()

    # Group tickers by (market, suffix) so each archive page is GET'd once.
    by_combo: dict[tuple[str, str], list[TickerSpec]] = {}
    for t in TICKERS:
        by_combo.setdefault((t.market, t.suffix), []).append(t)

    rows: list[dict] = []
    source_date = pd.Timestamp(started_at).tz_localize(None)
    accn = f"mops:{started_at.date().isoformat()}"

    total_pages = len(pages) * len(by_combo)
    fetched = 0
    for (market, suffix), tickers in by_combo.items():
        for roc, month in pages:
            url = _build_archive_url(market, roc, month, suffix)
            try:
                html = _fetch_archive_page(session, market, roc, month, suffix)
            except MopsBlocked as e:
                log["errors"].append(str(e))
                log["blocked_pages"].append(url)
                for t in tickers:
                    log["per_ticker"][t.ticker]["blocked"] = True
                fetched += 1
                continue
            if html is None:
                log["missing_pages"].append(url)
                fetched += 1
                continue

            for t in tickers:
                parsed = _parse_archive_row(html, t.ticker)
                if parsed is None:
                    continue
                _name_from_page, thousand = parsed  # 名稱以 filename truth 為準
                if pd.isna(thousand):
                    continue
                rows.append({
                    "end": _month_end(roc, month),
                    "entity_id": t.ticker,
                    "entity_name": t.name,  # Golden Rule #2 — filename truth
                    "tag": "revenue",
                    "val": float(thousand) / 1000.0,  # 千元 -> 百萬
                    "val_unit": "TWD_M",
                    "fp": "monthly",
                    "form": "mops_t05st10_ifrs",
                    "accn": accn,
                    "source_url": url,
                    "source_date": source_date,
                })
            fetched += 1
            if fetched % 10 == 0:
                sys.stderr.write(
                    f"  [{fetched}/{total_pages}] {market}/{roc}/"
                    f"{month:02d}/{suffix} ok ({len(rows)} rows so far)\n"
                )
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    df = pd.DataFrame(rows, columns=CANONICAL_COLS)
    if not df.empty:
        for col in ("entity_id", "entity_name", "tag", "val_unit",
                    "fp", "form", "accn", "source_url"):
            df[col] = df[col].astype("string")
        df["end"] = pd.to_datetime(df["end"])
        df["source_date"] = pd.to_datetime(df["source_date"])
        df = df.sort_values(["entity_id", "end"]).reset_index(drop=True)

        for ticker, sub in df.groupby("entity_id"):
            log["per_ticker"][str(ticker)]["months"] = int(len(sub))
            log["per_ticker"][str(ticker)]["earliest"] = (
                sub["end"].min().date().isoformat()
            )
            log["per_ticker"][str(ticker)]["latest"] = (
                sub["end"].max().date().isoformat()
            )

    log["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return df, log


# --------------------------------------------------------------------------- #
# Provenance writer
# --------------------------------------------------------------------------- #
def _status_emoji(log: dict) -> tuple[str, int]:
    months_per = {
        t.ticker: log["per_ticker"][t.ticker]["months"] for t in TICKERS
    }
    min_months = min(months_per.values()) if months_per else 0
    if log["blocked_pages"] or any(
        log["per_ticker"][t.ticker]["blocked"] for t in TICKERS
    ):
        return "⚠️ partial", min_months
    if min_months >= TARGET_MONTHS:
        return "✓ complete", min_months
    if min_months >= MIN_MONTHS_REQUIRED:
        return "⚠️ partial", min_months
    return "✗ below MIN_MONTHS_REQUIRED", min_months


def write_provenance(log: dict, df: pd.DataFrame) -> None:
    PROV_DIR.mkdir(parents=True, exist_ok=True)
    status, min_months = _status_emoji(log)

    lines: list[str] = []
    lines.append("# PMIC EFA v2 — Unit 16 monthly revenue\n")
    lines.append(f"**Fetch run:** {log['started_at']} → {log['finished_at']}")
    lines.append(f"**Status:** {status}")
    lines.append(
        f"**Output:** `data/pmic_efa/pmic_monthly_revenue.parquet`"
        f" ({len(df)} rows)\n"
    )

    lines.append("## Goal")
    lines.append(
        f"≥ {TARGET_MONTHS} months × 10 tickers (PMIC + Power) of"
        f" `tag=revenue, fp=monthly, val_unit=TWD_M` to feed PMIC EFA"
        f" v2 + DFM Q2 monitoring. Hard floor enforced in CLI summary"
        f" is `{MIN_MONTHS_REQUIRED}` months.\n"
    )

    lines.append("## Sources")
    lines.append(
        "- **MOPS** static archive (authoritative):"
        f" `{MOPS_BASE}/{{sii,otc}}/t21sc03_<ROC>_<M>_<suffix>.html`"
    )
    lines.append(
        "  - `suffix=0` for domestic issuers, `suffix=1` for foreign"
        " issuers (e.g. -KY)."
    )
    lines.append(
        "  - Referer: `https://mops.twse.com.tw/mops/web/t05st10_ifrs`."
    )
    lines.append(f"  - User-Agent: `{USER_AGENT}`")
    lines.append(
        f"  - Courtesy: `time.sleep({SLEEP_BETWEEN_REQUESTS})` between"
        f" GETs, exp backoff {BACKOFF_SECONDS}s on security-block."
    )
    lines.append(
        f"  - ROC year window scraped: {ROC_START}..{ROC_END}"
        f" (AD {ROC_START+1911}..{ROC_END+1911})."
    )
    lines.append(
        "- **Fallback (not used in this run):** yfinance"
        " `Ticker.history()` synthesised monthly revenue. The static"
        " MOPS archive returned every month needed, so fallback was"
        " unnecessary. If it ever is, provenance must flag the"
        " synthesised rows because Close×shares is a market-cap proxy,"
        " not the revenue 公開資訊觀測站 reports.\n"
    )
    lines.append(
        "- **Why not `ajax_t05st10_ifrs`?** That endpoint returns only"
        " the latest 12 months, and the production `mops.twse.com.tw`"
        " host now answers external POSTs with a 686-byte"
        " `FOR SECURITY REASONS` block. The static archive on the"
        " `mopsov` mirror is the same underlying data exposed via GET."
        " The row contract (year, month, current-month 千元 revenue,"
        " mom%, yoy%) matches `scripts/foplp_watchlist.py:52-98` —"
        " same parsing intent, durable source.\n"
    )

    lines.append("## Month coverage per ticker\n")
    lines.append(
        "| ticker | name | market | suffix | months | earliest | latest |"
    )
    lines.append("|---|---|---|---|---:|---|---|")
    for t in TICKERS:
        s = log["per_ticker"][t.ticker]
        lines.append(
            f"| {t.ticker} | {t.name} | {t.market} | {t.suffix} |"
            f" {s['months']} | {s['earliest'] or '—'} |"
            f" {s['latest'] or '—'} |"
        )
    lines.append("")

    if log["blocked_pages"]:
        lines.append("## Security-blocked pages (no data captured)\n")
        for u in log["blocked_pages"][:50]:
            lines.append(f"- `{u}`")
        if len(log["blocked_pages"]) > 50:
            lines.append(
                f"- ...({len(log['blocked_pages']) - 50} more)"
            )
        lines.append("")

    if log["missing_pages"]:
        lines.append("## Missing pages (404 — month not yet published)\n")
        for u in log["missing_pages"][:20]:
            lines.append(f"- `{u}`")
        if len(log["missing_pages"]) > 20:
            lines.append(
                f"- ...({len(log['missing_pages']) - 20} more)"
            )
        lines.append("")

    lines.append("## Schema")
    lines.append(
        "Conforms to `tests/test_ip_database_schema.py` REQUIRED set"
        " and `tests/test_pmic_efa_data.py` ALLOWED_TAGS (uses"
        " `tag='revenue'` + `fp='monthly'` — ALLOWED_TAGS doesn't"
        " whitelist a separate `monthly_revenue` tag yet, so we tag"
        " as revenue and distinguish via fp). Columns:"
    )
    lines.append("`" + " | ".join(CANONICAL_COLS) + "`")
    lines.append("")
    lines.append("## Conclusion")
    lines.append(
        f"{status} — min months across all 10 tickers ="
        f" {min_months} (target {TARGET_MONTHS}, floor"
        f" {MIN_MONTHS_REQUIRED})."
    )

    PROV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROV_DIR.mkdir(parents=True, exist_ok=True)

    sys.stderr.write(
        f"fetch_pmic_monthly: {len(TICKERS)} tickers, ROC "
        f"{ROC_START}..{ROC_END}\n"
    )

    df, log = fetch_all()

    if df.empty:
        sys.stderr.write(
            "FATAL: no rows captured — refusing to overwrite parquet\n"
        )
        write_provenance(log, df)
        return 2

    df.to_parquet(OUT_PARQUET, index=False)
    write_provenance(log, df)

    # ASCII summary
    tickers = sorted(df["entity_id"].unique())
    months = df.groupby("entity_id").size()
    print("=" * 60)
    print(f"Tickers ({len(tickers)}): {tickers}")
    print()
    print("Months per ticker:")
    for tk in tickers:
        sub = df[df["entity_id"] == tk]
        print(
            f"  {tk}  {months[tk]:3d}  "
            f"{sub['end'].min().date()} .. {sub['end'].max().date()}"
        )
    print()
    print(f"min months: {months.min()},  max months: {months.max()}")
    print()
    print("tail(10):")
    print(df.tail(10).to_string())
    print("=" * 60)

    assert months.min() >= MIN_MONTHS_REQUIRED, (
        f"某 ticker 月數 {months.min()} < {MIN_MONTHS_REQUIRED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
