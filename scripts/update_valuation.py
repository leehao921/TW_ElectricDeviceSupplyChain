"""
update_valuation.py — Refresh ONLY the valuation multiples (估值指標) in ticker reports.

v2: Uses TWSE + TPEX bulk OpenAPI (2 requests for all ~1,958 stocks) then falls back
    to yfinance for any ticker not found. ~100x faster than pure yfinance approach.

Data sources:
  Primary  — TWSE OpenAPI (上市): price, P/E, P/B, 殖利率, 市值
             TPEX OpenAPI (上櫃): price, P/E, P/B, 殖利率
  Fallback — yfinance: EV/EBITDA, Forward P/E, P/S, and any ticker not in bulk

Usage:
  python scripts/update_valuation.py                     # ALL tickers
  python scripts/update_valuation.py 2330                # Single ticker
  python scripts/update_valuation.py 2330 2317 3034      # Multiple
  python scripts/update_valuation.py --batch 101         # By batch
  python scripts/update_valuation.py --sector Semiconductors
  python scripts/update_valuation.py --dry-run 2330      # Preview
  python scripts/update_valuation.py --no-fallback       # Skip yfinance entirely
"""

import os
import re
import sys
import time
import json
import urllib.request
from datetime import date, datetime

import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    find_ticker_files, parse_scope_args, setup_stdout,
    build_valuation_table, update_metadata,
)
from valuation_snapshot import build_snapshot, save_snapshot

# ---------------------------------------------------------------------------
# Bulk data fetchers
# ---------------------------------------------------------------------------

def _fetch_json(url: str) -> list:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [WARN] Bulk fetch failed ({url[:60]}...): {e}")
        return []


def fetch_twse_bulk() -> dict:
    """
    Fetch all TWSE (上市) stocks in 2 calls:
      1. Daily price (OHLCV, market cap proxy via TradeValue)
      2. P/E, P/B, dividendYield

    Returns dict: {ticker: {price, pe, pb, yield_pct, market_cap_m}}
    """
    price_data = _fetch_json(
        "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    )
    ratio_data = _fetch_json(
        "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"
    )

    # Build price lookup
    prices = {}
    for row in price_data:
        code = row.get("Code", "")
        try:
            prices[code] = {
                "price": float(row["ClosingPrice"]),
                "trade_value": int(row.get("TradeValue", 0)),
                "date": row.get("Date", ""),
            }
        except (ValueError, KeyError):
            continue

    # Merge ratio data
    result = {}
    for row in ratio_data:
        code = row.get("Code", "")
        if not code:
            continue
        p = prices.get(code, {})
        try:
            pe  = float(row["PEratio"])   if row.get("PEratio")  not in ("", "--", "0") else None
            pb  = float(row["PBratio"])   if row.get("PBratio")  not in ("", "--", "0") else None
            dy  = float(row["DividendYield"]) if row.get("DividendYield") not in ("", "--") else None
        except (ValueError, TypeError):
            pe = pb = dy = None

        result[code] = {
            "price":       p.get("price"),
            "pe":          pe,
            "pb":          pb,
            "yield_pct":   dy,   # already in %, e.g. 3.40
            "fiscal_q":    row.get("FiscalYearQuarter", ""),
            "market_cap_m": None,  # TWSE API doesn't give market cap directly
            "source":      "TWSE",
        }

    return result


def fetch_tpex_bulk() -> dict:
    """
    Fetch all TPEX (上櫃) stocks in 2 calls.
    Returns dict: {ticker: {price, pe, pb, yield_pct}}
    """
    price_data = _fetch_json(
        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
    )
    ratio_data = _fetch_json(
        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"
    )

    prices = {}
    for row in price_data:
        code = row.get("SecuritiesCompanyCode", "")
        try:
            prices[code] = {"price": float(row["Close"])}
        except (ValueError, KeyError):
            continue

    result = {}
    for row in ratio_data:
        code = row.get("SecuritiesCompanyCode", "")
        if not code:
            continue
        p = prices.get(code, {})
        _BAD = {"", "--", "0.00", "0", "N/A", "—", "－"}
        try:
            pe = float(row["PriceEarningRatio"]) if row.get("PriceEarningRatio") not in _BAD else None
            pb = float(row["PriceBookRatio"])    if row.get("PriceBookRatio")    not in _BAD else None
            dy = float(row["YieldRatio"])        if row.get("YieldRatio")        not in _BAD else None
        except (ValueError, TypeError):
            pe = pb = dy = None

        result[code] = {
            "price":      p.get("price"),
            "pe":         pe,
            "pb":         pb,
            "yield_pct":  dy,
            "fiscal_q":   "",
            "market_cap_m": None,
            "source":     "TPEX",
        }

    return result


def fetch_yfinance_fallback(ticker: str):
    """yfinance fallback for tickers not in bulk data, or for extra fields."""
    for suffix in [".TW", ".TWO"]:
        try:
            info = yf.Ticker(f"{ticker}{suffix}").info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if not price:
                continue

            # dividendYield from yfinance is decimal (0.034 = 3.4%) — convert correctly
            dy_raw = info.get("dividendYield")
            yield_pct = round(dy_raw * 100, 2) if dy_raw and dy_raw < 1 else dy_raw

            mkt_cap = info.get("marketCap")
            ev = info.get("enterpriseValue")

            return {
                "price":          price,
                "pe":             info.get("trailingPE"),
                "pb":             info.get("priceToBook"),
                "yield_pct":      yield_pct,
                "ps":             info.get("priceToSalesTrailing12Months"),
                "fwd_pe":         info.get("forwardPE"),
                "ev_ebitda":      info.get("enterpriseToEbitda"),
                "market_cap_m":   round(mkt_cap / 1_000_000) if mkt_cap else None,
                "enterprise_value_m": round(ev / 1_000_000) if ev else None,
                "mrq":            info.get("mostRecentQuarter"),
                "nfy":            info.get("nextFiscalYearEnd"),
                "source":         f"yfinance{suffix}",
            }
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Valuation dict builder
# ---------------------------------------------------------------------------

def build_valuation_dict(bulk: dict, ticker: str, use_fallback: bool):
    """
    Merge bulk data with optional yfinance for richer fields.
    Priority: bulk (P/E, P/B, yield) > yfinance (EV/EBITDA, Forward P/E, P/S).
    """
    b = bulk.get(ticker)

    if b is None and not use_fallback:
        return None

    yf_data = None
    if use_fallback:
        yf_data = fetch_yfinance_fallback(ticker)

    if b is None and yf_data is None:
        return None

    def _to_float(v):
        try:
            f = float(v)
            return f if f not in (float("inf"), float("-inf")) else None
        except (TypeError, ValueError):
            return None

    # Merge: bulk is authoritative for price/pe/pb/yield
    price    = _to_float((b or {}).get("price"))    or _to_float((yf_data or {}).get("price"))
    pe       = _to_float((b or {}).get("pe"))       or _to_float((yf_data or {}).get("pe"))
    pb       = _to_float((b or {}).get("pb"))       or _to_float((yf_data or {}).get("pb"))
    yield_pct= _to_float((b or {}).get("yield_pct"))or _to_float((yf_data or {}).get("yield_pct"))
    fwd_pe   = (yf_data or {}).get("fwd_pe")
    ps       = (yf_data or {}).get("ps")
    ev_ebitda= (yf_data or {}).get("ev_ebitda")
    mrq      = (yf_data or {}).get("mrq")
    nfy      = (yf_data or {}).get("nfy")

    mkt_cap_m = (b or {}).get("market_cap_m") or (yf_data or {}).get("market_cap_m")
    ev_m      = (yf_data or {}).get("enterprise_value_m")

    today = date.today().strftime("%Y-%m-%d")

    valuation = {
        "P/E (TTM)":   f"{pe:.2f}"       if pe       else "N/A",
        "Forward P/E": f"{fwd_pe:.2f}"   if fwd_pe   else "N/A",
        "P/S (TTM)":   f"{ps:.2f}"       if ps       else "N/A",
        "P/B":         f"{pb:.2f}"       if pb       else "N/A",
        "EV/EBITDA":   f"{ev_ebitda:.2f}"if ev_ebitda else "N/A",
        "_price":      f"{price:,.2f}"   if price    else None,
        "_ttm_end":    datetime.fromtimestamp(mrq).strftime("%Y-%m-%d") if mrq else None,
        "_fwd_end":    datetime.fromtimestamp(nfy).strftime("%Y-%m-%d") if nfy else None,
        "_yield_pct":  f"{yield_pct:.2f}%" if yield_pct else None,
        "_source":     (b or {}).get("source", "") + ("+" + yf_data["source"] if yf_data else ""),
    }

    return {
        "valuation":          valuation,
        "market_cap":         f"{mkt_cap_m:,.0f}" if mkt_cap_m else None,
        "enterprise_value":   f"{ev_m:,.0f}"      if ev_m      else None,
    }


# ---------------------------------------------------------------------------
# File updater
# ---------------------------------------------------------------------------

def update_file(filepath: str, ticker: str, bulk: dict,
                use_fallback: bool, dry_run: bool) -> str:
    """Returns 'updated', 'skipped', or 'error'."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    data = build_valuation_dict(bulk, ticker, use_fallback)
    if data is None:
        print(f"  {ticker}: SKIP (no data)")
        return "skipped"

    v = data["valuation"]
    new_table = build_valuation_table(v)

    # Append yield to table title if available
    if v.get("_yield_pct"):
        new_table = new_table.replace(
            "### 估值指標",
            f"### 估值指標 (殖利率 {v['_yield_pct']})",
            1
        )

    if "### 估值指標" in content:
        content = re.sub(
            r"### 估值指標.*?(?=\n### 年度)",
            new_table + "\n",
            content,
            flags=re.DOTALL,
        )
    elif "## 財務概況" in content:
        content = content.replace(
            "### 年度關鍵財務數據",
            new_table + "\n\n### 年度關鍵財務數據",
        )

    content = update_metadata(
        content,
        data.get("market_cap"),
        data.get("enterprise_value"),
    )

    src = v.get("_source", "")
    if dry_run:
        print(f"  {ticker}: WOULD UPDATE ({src})")
        return "updated"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  {ticker}: UPDATED ({src})")
    return "updated"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    setup_stdout()

    args = list(sys.argv[1:])
    dry_run     = "--dry-run"     in args; args = [a for a in args if a != "--dry-run"]
    no_fallback = "--no-fallback" in args; args = [a for a in args if a != "--no-fallback"]
    use_fallback = not no_fallback

    tickers, sector, desc = parse_scope_args(args)
    print(f"Updating valuation for {desc}...")
    files = find_ticker_files(tickers, sector)

    if not files:
        print("No matching files found.")
        return

    n = len(files)
    print(f"Found {n} files.\n")

    # --- Bulk fetch (2 requests total) ---
    print("Fetching TWSE bulk data...", end=" ", flush=True)
    twse = fetch_twse_bulk()
    print(f"{len(twse)} stocks")

    print("Fetching TPEX bulk data...", end=" ", flush=True)
    tpex = fetch_tpex_bulk()
    print(f"{len(tpex)} stocks")

    bulk = {**tpex, **twse}  # TWSE takes priority on overlap
    print(f"Bulk coverage: {len(bulk)} unique tickers\n")

    updated = failed = skipped = 0

    for ticker in sorted(files.keys()):
        in_bulk = ticker in bulk
        needs_yf = use_fallback and (not in_bulk or bulk[ticker].get("pe") is None)
        try:
            result = update_file(
                files[ticker], ticker, bulk,
                use_fallback=needs_yf,
                dry_run=dry_run,
            )
            if result == "updated":  updated += 1
            elif result == "skipped": skipped += 1
        except Exception as e:
            print(f"  {ticker}: ERROR ({e})")
            failed += 1
        # Rate-limit only when hitting yfinance
        if needs_yf:
            time.sleep(0.25)

    print(f"\nDone. Updated: {updated} | Skipped: {skipped} | Failed: {failed}")
    print(f"Bulk hits: {sum(1 for t in files if t in bulk)} / {n}")

    # Persist daily snapshot of all bulk entries (regardless of dry_run on
    # individual files) — anomaly detector reads this. Skip when scope is
    # narrow (single ticker, single sector) because partial snapshots would
    # corrupt the day-over-day comparison.
    if not dry_run and tickers is None and sector is None:
        today = date.today().strftime("%Y-%m-%d")
        snapshot = build_snapshot(bulk, snapshot_date=today)
        path = save_snapshot(snapshot)
        print(f"Snapshot written: {path} ({len(snapshot['tickers'])} tickers)")


if __name__ == "__main__":
    main()
