#!/usr/bin/env python3
"""etf_coverage_report.py — read-only view over active-ETF holdings.

Reads ``etf_holdings_daily`` / ``etf_meta`` from the tmf market DB
(populated by the tmf-etf-holdings-collector) and cross-references each
constituent against this repo's 926-ticker Pilot_Reports coverage graph,
flagging which holdings are covered vs a coverage backlog.

The join lives HERE (not in the market DB) so tmf_market_data stays free
of this repo's file state — coverage is derived from the .md filenames.

Usage:
    python scripts/etf_coverage_report.py                 # all covered ETFs
    python scripts/etf_coverage_report.py 00980A 00985A   # specific ETFs
    python scripts/etf_coverage_report.py --date 2026-06-30
    python scripts/etf_coverage_report.py --backlog       # only uncovered holdings

Connection via env (defaults target the host-exposed trading-timescaledb):
    DB_HOST=localhost DB_PORT=5432 DB_USER=tmf DB_PASSWORD=tmf_dev_2026 DB_NAME=tmf_market_data
"""
import argparse
import os
import sys

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import find_ticker_files  # noqa: E402


def _connect():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USER", "tmf"),
        password=os.environ.get("DB_PASSWORD", "tmf_dev_2026"),
        dbname=os.environ.get("DB_NAME", "tmf_market_data"),
    )


def _fetch(conn, etf_codes, date):
    where = ["h.date = (SELECT max(date) FROM etf_holdings_daily x WHERE x.etf_code = h.etf_code)"]
    params = []
    if date:
        where = ["h.date = %s"]
        params.append(date)
    if etf_codes:
        where.append("h.etf_code = ANY(%s)")
        params.append(list(etf_codes))
    sql = f"""
        SELECT h.etf_code, COALESCE(m.name, ''), h.date,
               h.constituent_code, h.constituent_name, h.weight_pct, h.shares
        FROM etf_holdings_daily h
        LEFT JOIN etf_meta m ON m.etf_code = h.etf_code
        WHERE {' AND '.join(where)}
        ORDER BY h.etf_code, h.weight_pct DESC NULLS LAST
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Active-ETF holdings coverage report")
    ap.add_argument("etf_codes", nargs="*", help="ETF codes (default: all)")
    ap.add_argument("--date", help="As-of date YYYY-MM-DD (default: latest per ETF)")
    ap.add_argument("--backlog", action="store_true",
                    help="Show only uncovered constituents (coverage backlog)")
    args = ap.parse_args(argv)

    covered_tickers = set(find_ticker_files().keys())

    try:
        conn = _connect()
    except psycopg2.OperationalError as e:
        print(f"Cannot connect to tmf_market_data: {e}", file=sys.stderr)
        return 2
    try:
        try:
            rows = _fetch(conn, args.etf_codes, args.date)
        except psycopg2.Error as e:
            print(f"Query failed (has migration 011 been applied?): {e}", file=sys.stderr)
            return 2
    finally:
        conn.close()

    if not rows:
        print("No holdings found. Has the collector run? (docker compose up -d etf-holdings-collector)")
        return 1

    # group by etf
    by_etf = {}
    for etf, name, date, code, cname, weight, shares in rows:
        by_etf.setdefault((etf, name, date), []).append((code, cname, weight, shares))

    grand_uncovered = 0
    for (etf, name, date), holds in by_etf.items():
        cov = sum(1 for c, *_ in holds if c in covered_tickers)
        cov_w = sum(float(w or 0) for c, _, w, _ in holds if c in covered_tickers)
        print(f"\n=== {etf} {name}  (as of {date}) — {len(holds)} holdings, "
              f"{cov} covered ({cov_w:.1f}% weight) ===")
        for code, cname, weight, shares in holds:
            is_cov = code in covered_tickers
            if args.backlog and is_cov:
                continue
            if not is_cov:
                grand_uncovered += 1
            flag = "✓" if is_cov else "·"
            print(f"  {flag} {code:<7}{(cname or ''):<12} {float(weight or 0):6.2f}%  "
                  f"{'' if is_cov else '[no report]'}")

    if not args.backlog:
        print(f"\nCoverage backlog: {grand_uncovered} uncovered constituent rows "
              f"(run /add-ticker for high-weight ones).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
