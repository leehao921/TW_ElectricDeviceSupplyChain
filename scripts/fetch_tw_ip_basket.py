#!/usr/bin/env python3
"""Fetch TW IP / ASIC service basket (5 tickers) — quarterly financials & valuations
from yfinance, plus 90-day cumulative institutional flow from trading-timescaledb.

Tickers (Golden Rule #2: filename is ground truth):
  3529  力旺      (eMemory)        NVM IP (OTP/MTP)
  6531  愛普      (AP Memory)      客製化 DRAM IP
  6533  晶心科    (Andes Tech)     RISC-V CPU core IP
  3443  創意      (GUC)            TSMC ASIC service
  3661  世芯-KY   (Alchip)         Amazon Trainium ASIC service

Outputs (canonical long-format schema):
  data/ip_database/tw_ip_basket_quarterly.parquet
  data/ip_database/tw_ip_basket_flow.parquet

Schema columns (both parquets):
  end | entity_id | entity_name | tag | val | val_unit
  fp  | form      | accn        | source_url | source_date

Allowed partial failure: if Postgres is unreachable, yfinance pulls still run and
the quarterly parquet is still produced; flow parquet is skipped and the reason
is logged to data/ip_database/_provenance/tw_ip_basket.md.
"""

from __future__ import annotations

import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# yfinance is noisy with deprecation / non-fatal HTTP warnings — suppress.
warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "ip_database"
PROV_DIR = OUT_DIR / "_provenance"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PROV_DIR.mkdir(parents=True, exist_ok=True)

QUARTERLY_OUT = OUT_DIR / "tw_ip_basket_quarterly.parquet"
FLOW_OUT = OUT_DIR / "tw_ip_basket_flow.parquet"
PROV_FILE = PROV_DIR / "tw_ip_basket.md"

# --------------------------------------------------------------------------- #
# Ticker registry — name MUST match Pilot_Reports filename (Golden Rule #2).
# Each entry: (ticker_4digit, traditional-chinese-name).
# yfinance suffix: TWSE = .TW, TPEX/OTC = .TWO. We try .TW first, then .TWO.
# --------------------------------------------------------------------------- #
TICKERS: list[tuple[str, str]] = [
    ("3529", "力旺"),
    ("6531", "愛普"),
    ("6533", "晶心科"),
    ("3443", "創意"),
    ("3661", "世芯-KY"),
]

# Set of tags we want from yfinance.quarterly_financials index labels.
# Map yfinance row label -> (tag, val_unit, derived?)
QUARTERLY_ROW_MAP = {
    "Total Revenue": ("revenue", "TWD", False),
    "Operating Revenue": ("operating_revenue", "TWD", False),
    "Gross Profit": ("gross_profit", "TWD", False),
    "Operating Income": ("operating_income", "TWD", False),
    "Net Income": ("net_income", "TWD", False),
}

# Static valuation tags pulled from .info on the snapshot date.
INFO_TAG_MAP = {
    "trailingPE": ("pe_ttm", "x"),
    "priceToBook": ("pb", "x"),
    "dividendYield": ("yield", "pct"),
    "marketCap": ("mv", "TWD"),
    "regularMarketPrice": ("price", "TWD"),
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

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "tmf_market_data",
    "user": "tmf",
    "password": "tmf_dev_2026",
    "connect_timeout": 5,
}

# --------------------------------------------------------------------------- #
# yfinance helpers
# --------------------------------------------------------------------------- #
def _quarter_to_fp(end: pd.Timestamp) -> str:
    """Map calendar quarter-end to fiscal-period label."""
    m = end.month
    if m == 3:
        return "Q1"
    if m == 6:
        return "Q2"
    if m == 9:
        return "Q3"
    if m == 12:
        return "FY"  # Q4 is end-of-FY for TW issuers
    return "Qx"


def _resolve_ticker(yf, ticker_id: str) -> tuple[str, "object", dict]:
    """Try .TW then .TWO. Return (yahoo_symbol, Ticker_obj, info_dict).

    A symbol is considered valid if `info` returns a marketCap OR a
    regularMarketPrice (some delisted/OTC symbols return both None even when
    the 404 is for a sibling field). Raise ValueError if both fail.
    """
    last_err = None
    for suffix in (".TW", ".TWO"):
        yahoo_sym = f"{ticker_id}{suffix}"
        try:
            t = yf.Ticker(yahoo_sym)
            info = t.info or {}
            if info.get("marketCap") or info.get("regularMarketPrice"):
                return yahoo_sym, t, info
            last_err = f"empty info for {yahoo_sym}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{yahoo_sym}: {e}"
    raise ValueError(f"yfinance: no valid suffix for {ticker_id} ({last_err})")


def fetch_yfinance_rows(
    fetch_date: datetime,
) -> tuple[list[dict], list[str]]:
    """Return (canonical_rows, error_messages)."""
    import yfinance as yf  # local import — keeps script optional-deps friendly

    fetch_iso = fetch_date.strftime("%Y-%m-%d")
    rows: list[dict] = []
    errors: list[str] = []

    for ticker_id, entity_name in TICKERS:
        try:
            yahoo_sym, t, info = _resolve_ticker(yf, ticker_id)
        except ValueError as e:
            sys.stderr.write(f"WARN: {e}\n")
            errors.append(str(e))
            continue

        source_url = f"https://finance.yahoo.com/quote/{yahoo_sym}"
        accn = f"yfinance:{fetch_iso}"

        # --- Static valuation snapshot (today) ---
        for info_key, (tag, val_unit) in INFO_TAG_MAP.items():
            val = info.get(info_key)
            if val is None:
                continue
            try:
                val_f = float(val)
            except (TypeError, ValueError):
                continue
            # yfinance returns dividendYield already in percent (e.g. 0.62 == 0.62%)
            rows.append({
                "end": pd.Timestamp(fetch_date.date()),
                "entity_id": ticker_id,
                "entity_name": entity_name,
                "tag": tag,
                "val": val_f,
                "val_unit": val_unit,
                "fp": "static",
                "form": "yfinance",
                "accn": accn,
                "source_url": source_url,
                "source_date": pd.Timestamp(fetch_date),
            })

        # --- Quarterly fundamentals (last 4-8 quarters) ---
        try:
            qf = t.quarterly_financials
        except Exception as e:  # noqa: BLE001
            errors.append(f"{yahoo_sym} quarterly_financials: {e}")
            qf = pd.DataFrame()

        if qf is not None and not qf.empty:
            # Defensive: drop duplicate row labels (rare yfinance edge case where
            # the same line item appears twice — keeps `.at` scalar).
            if qf.index.has_duplicates:
                qf = qf[~qf.index.duplicated(keep="first")]
            # qf columns are Timestamps (quarter-end), rows are line items
            for q_end in qf.columns:
                q_ts = pd.Timestamp(q_end)
                fp_label = _quarter_to_fp(q_ts)
                for row_label, (tag, val_unit, _) in QUARTERLY_ROW_MAP.items():
                    if row_label not in qf.index:
                        continue
                    raw = qf.at[row_label, q_end]
                    if pd.isna(raw):
                        continue
                    rows.append({
                        "end": q_ts,
                        "entity_id": ticker_id,
                        "entity_name": entity_name,
                        "tag": tag,
                        "val": float(raw),
                        "val_unit": val_unit,
                        "fp": fp_label,
                        "form": "yfinance",
                        "accn": accn,
                        "source_url": source_url,
                        "source_date": pd.Timestamp(fetch_date),
                    })

            # Derived margins (gross_margin, operating_margin) — preserve 0% / negative
            # by computing per quarter when both numerator and revenue present.
            for q_end in qf.columns:
                q_ts = pd.Timestamp(q_end)
                fp_label = _quarter_to_fp(q_ts)
                rev = qf.at["Total Revenue", q_end] if "Total Revenue" in qf.index else None
                if rev is None or pd.isna(rev) or rev == 0:
                    continue
                if "Gross Profit" in qf.index:
                    gp = qf.at["Gross Profit", q_end]
                    if pd.notna(gp):
                        rows.append({
                            "end": q_ts,
                            "entity_id": ticker_id,
                            "entity_name": entity_name,
                            "tag": "gross_margin",
                            "val": float(gp) / float(rev) * 100.0,
                            "val_unit": "pct",
                            "fp": fp_label,
                            "form": "yfinance",
                            "accn": accn,
                            "source_url": source_url,
                            "source_date": pd.Timestamp(fetch_date),
                        })
                if "Operating Income" in qf.index:
                    oi = qf.at["Operating Income", q_end]
                    if pd.notna(oi):
                        rows.append({
                            "end": q_ts,
                            "entity_id": ticker_id,
                            "entity_name": entity_name,
                            "tag": "operating_margin",
                            "val": float(oi) / float(rev) * 100.0,
                            "val_unit": "pct",
                            "fp": fp_label,
                            "form": "yfinance",
                            "accn": accn,
                            "source_url": source_url,
                            "source_date": pd.Timestamp(fetch_date),
                        })
        else:
            errors.append(f"{yahoo_sym}: quarterly_financials empty")

        sys.stderr.write(f"OK yfinance: {ticker_id} ({entity_name}) -> {yahoo_sym}\n")

    return rows, errors


# --------------------------------------------------------------------------- #
# Postgres flow helper
# --------------------------------------------------------------------------- #
FLOW_SQL = """
SELECT symbol,
       SUM(foreign_net) / 1000.0 AS foreign_lots,
       SUM(trust_net)   / 1000.0 AS trust_lots,
       SUM(total_net)   / 1000.0 AS total_lots
FROM institutional_stock
WHERE symbol IN %s
  AND date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY symbol;
"""


def fetch_flow_rows(
    fetch_date: datetime,
) -> tuple[list[dict], list[str]]:
    """Return (canonical_rows, error_messages). Empty rows = DB unreachable."""
    errors: list[str] = []
    try:
        import psycopg2  # local import — allows yfinance-only run
    except ImportError as e:
        errors.append(f"psycopg2 not installed: {e}")
        sys.stderr.write(f"WARN: {errors[-1]}\n")
        return [], errors

    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:  # noqa: BLE001
        errors.append(f"DB connect failed: {e}")
        sys.stderr.write(f"WARN: {errors[-1]}\n")
        return [], errors

    rows: list[dict] = []
    fetch_iso = fetch_date.strftime("%Y-%m-%d")
    name_map = {tid: nm for tid, nm in TICKERS}
    symbols = tuple(name_map.keys())

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(FLOW_SQL, (symbols,))
                results = cur.fetchall()
    except Exception as e:  # noqa: BLE001
        errors.append(f"DB query failed: {e}")
        sys.stderr.write(f"WARN: {errors[-1]}\n")
        return [], errors
    finally:
        conn.close()

    accn = f"tmf_db:{fetch_iso}"
    for symbol, foreign_lots, trust_lots, total_lots in results:
        entity_name = name_map.get(symbol, "?")
        # tag/val triples per row
        triples = (
            ("foreign_net_lots", foreign_lots, "lots"),
            ("trust_net_lots", trust_lots, "lots"),
            ("total_net_lots", total_lots, "lots"),
        )
        for tag, raw, unit in triples:
            if raw is None:
                continue
            rows.append({
                "end": pd.Timestamp(fetch_date.date()),
                "entity_id": symbol,
                "entity_name": entity_name,
                "tag": tag,
                "val": float(raw),
                "val_unit": unit,
                "fp": "static",
                "form": "institutional_stock",
                "accn": accn,
                "source_url": "tmf_db://institutional_stock",
                "source_date": pd.Timestamp(fetch_date),
            })

    # Note missing symbols (data not in DB for 90d window)
    seen = {r[0] for r in results}
    for tid in name_map:
        if tid not in seen:
            errors.append(f"{tid}: no institutional_stock rows in 90d window")

    return rows, errors


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


def _write_provenance(
    fetch_date: datetime,
    quarterly_rows: int,
    flow_rows: int,
    yfinance_errors: list[str],
    flow_errors: list[str],
) -> None:
    fetch_iso = fetch_date.strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    lines = [
        "# TW IP / ASIC service basket — provenance",
        "",
        f"**Fetch run:** {fetch_iso}",
        "",
        "## Tickers",
        "",
        "| ticker | name | role |",
        "|---|---|---|",
        "| 3529 | 力旺 | NVM IP (OTP/MTP) |",
        "| 6531 | 愛普 | 客製化 DRAM IP |",
        "| 6533 | 晶心科 | RISC-V CPU core IP |",
        "| 3443 | 創意 | TSMC ASIC service |",
        "| 3661 | 世芯-KY | Amazon Trainium ASIC service |",
        "",
        "## Sources",
        "",
        "- **yfinance** — quarterly_financials + .info snapshot. Suffix .TW preferred, .TWO fallback.",
        "- **trading-timescaledb** — `institutional_stock` table on localhost:5432/tmf_market_data; 90-day cumulative foreign/trust/total net.",
        "",
        "## Output rows",
        "",
        f"- `tw_ip_basket_quarterly.parquet`: {quarterly_rows} rows",
        f"- `tw_ip_basket_flow.parquet`: {flow_rows} rows",
        "",
        "## Warnings / errors",
        "",
    ]
    if not yfinance_errors and not flow_errors:
        lines.append("- (none — clean run)")
    else:
        for e in yfinance_errors:
            lines.append(f"- yfinance: {e}")
        for e in flow_errors:
            lines.append(f"- flow:     {e}")
    lines.append("")
    PROV_FILE.write_text("\n".join(lines), encoding="utf-8")


def _print_ascii_summary(qdf: pd.DataFrame, fdf: pd.DataFrame) -> None:
    print()
    print("=" * 72)
    print("TW IP / ASIC SERVICE BASKET — fetch summary")
    print("=" * 72)

    # Static valuation snapshot
    if not qdf.empty:
        snap = qdf[qdf["fp"] == "static"]
        if not snap.empty:
            print("\n[Valuation snapshot]")
            print(f"{'ticker':<8} {'name':<10} {'MV (B TWD)':>12} "
                  f"{'PE':>10} {'PB':>8} {'Yield %':>8} {'Price':>8}")
            print("-" * 72)
            for tid, name in TICKERS:
                sub = snap[snap["entity_id"] == tid]
                if sub.empty:
                    print(f"{tid:<8} {name:<10} {'n/a':>12}")
                    continue

                def _get(tag: str) -> float | None:
                    r = sub[sub["tag"] == tag]
                    return float(r.iloc[0]["val"]) if not r.empty else None

                mv = _get("mv")
                pe = _get("pe_ttm")
                pb = _get("pb")
                dy = _get("yield")
                px = _get("price")

                def _fmt(x: float | None, scale: float = 1.0, width: int = 10) -> str:
                    if x is None:
                        return f"{'n/a':>{width}}"
                    return f"{x*scale:>{width},.2f}"

                print(f"{tid:<8} {name:<10} "
                      f"{_fmt(mv, 1/1e9, 12)} "
                      f"{_fmt(pe, 1.0, 10)} "
                      f"{_fmt(pb, 1.0, 8)} "
                      f"{_fmt(dy, 1.0, 8)} "
                      f"{_fmt(px, 1.0, 8)}")

        # Latest revenue quarter per ticker
        rev = qdf[(qdf["tag"] == "revenue") & (qdf["fp"] != "static")]
        if not rev.empty:
            print("\n[Latest quarterly revenue (M TWD)]")
            print(f"{'ticker':<8} {'name':<10} {'q_end':<12} {'fp':<4} {'revenue':>14}")
            print("-" * 56)
            for tid, name in TICKERS:
                sub = rev[rev["entity_id"] == tid].sort_values("end")
                if sub.empty:
                    print(f"{tid:<8} {name:<10} {'n/a':<12}")
                    continue
                last = sub.iloc[-1]
                print(f"{tid:<8} {name:<10} "
                      f"{last['end'].strftime('%Y-%m-%d'):<12} "
                      f"{last['fp']:<4} "
                      f"{last['val']/1e6:>14,.1f}")

    # 90d institutional flow
    if not fdf.empty:
        print("\n[90-day cumulative institutional flow (lots, 1 lot = 1,000 shares)]")
        print(f"{'ticker':<8} {'name':<10} {'foreign':>14} {'trust':>14} {'total':>14}")
        print("-" * 64)
        for tid, name in TICKERS:
            sub = fdf[fdf["entity_id"] == tid]
            if sub.empty:
                print(f"{tid:<8} {name:<10} {'n/a':>14}")
                continue

            def _get(tag: str) -> float:
                r = sub[sub["tag"] == tag]
                return float(r.iloc[0]["val"]) if not r.empty else 0.0

            print(f"{tid:<8} {name:<10} "
                  f"{_get('foreign_net_lots'):>14,.1f} "
                  f"{_get('trust_net_lots'):>14,.1f} "
                  f"{_get('total_net_lots'):>14,.1f}")
    else:
        print("\n[flow]  no rows produced — see _provenance/tw_ip_basket.md")
    print()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    fetch_date = datetime.now(timezone.utc)

    yf_rows, yf_errors = fetch_yfinance_rows(fetch_date)
    flow_rows, flow_errors = fetch_flow_rows(fetch_date)

    qdf = _to_dataframe(yf_rows)
    fdf = _to_dataframe(flow_rows)

    if not qdf.empty:
        qdf.to_parquet(QUARTERLY_OUT, index=False)
        sys.stderr.write(f"Wrote {QUARTERLY_OUT} ({len(qdf)} rows)\n")
    else:
        sys.stderr.write("WARN: quarterly dataframe empty — parquet not written\n")

    if not fdf.empty:
        fdf.to_parquet(FLOW_OUT, index=False)
        sys.stderr.write(f"Wrote {FLOW_OUT} ({len(fdf)} rows)\n")
    else:
        sys.stderr.write("WARN: flow dataframe empty — parquet not written\n")

    _write_provenance(fetch_date, len(qdf), len(fdf), yf_errors, flow_errors)
    _print_ascii_summary(qdf, fdf)

    # exit 0 even with partial failure (spec: allowed partial failure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
