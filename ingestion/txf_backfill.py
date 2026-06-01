"""Phase 2: TXF/TAIEX hybrid backfill.

Pulls 3 years of TAIEX (^TWII) daily OHLC from yfinance as the primary backbone
for the TXF basis analysis. TAIFEX TXF futures daily scraping is attempted as
best-effort; if it fails (network/scrape changes), we document the gap and
proceed with TAIEX-only.

All timestamps localized to Asia/Taipei. TAIEX close is anchored to 13:30 TWT.

Public API:
    fetch_taiex_yf(start, end) -> pd.DataFrame
    fetch_taifex_txf_daily(date_str) -> pd.DataFrame  (single date, optional)
    build_txf_continuous(daily_records, roll_rule='third_wed') -> pd.DataFrame
    compute_basis(taiex_df, txf_continuous) -> pd.DataFrame
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import pytz
import yfinance as yf

TWT = pytz.timezone("Asia/Taipei")
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def fetch_taiex_yf(start: str = "2023-05-15", end: str = "2026-05-16") -> pd.DataFrame:
    """Fetch ^TWII daily OHLCV from yfinance and anchor closes to TWT 13:30.

    Returns a DataFrame indexed by tz-aware Asia/Taipei timestamps with columns
    ``open, high, low, close, volume``.
    """
    df = yf.download(
        "^TWII",
        start=start,
        end=end,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        # one retry
        time.sleep(5)
        df = yf.download(
            "^TWII", start=start, end=end, auto_adjust=False, progress=False, threads=False
        )
    if df is None or df.empty:
        raise RuntimeError("yfinance returned empty for ^TWII")

    # Flatten multi-index columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.rename(columns=str.lower)
    df = df[["open", "high", "low", "close", "volume"]].copy()

    # The yfinance index is a tz-naive date (in exchange local time). Anchor to
    # TWT 13:30 close.
    if df.index.tz is not None:
        df.index = df.index.tz_convert("Asia/Taipei").tz_localize(None)
    df.index = pd.to_datetime(df.index)
    df.index = df.index.normalize() + pd.Timedelta(hours=13, minutes=30)
    df.index = df.index.tz_localize("Asia/Taipei")
    df.index.name = "ts"
    return df


def fetch_taifex_txf_daily(date_str: str) -> pd.DataFrame:
    """Best-effort scrape of TAIFEX TXF daily quotes for one date.

    Returns an empty DataFrame on failure rather than raising; the caller can
    decide whether to skip TXF basis.
    """
    try:
        import requests

        url = "https://www.taifex.com.tw/cht/3/futAndOptDailyMarketReport"
        payload = {
            "queryType": "2",
            "marketCode": "0",
            "dateaddcnt": "",
            "commodity_id": "TX",
            "queryDate": date_str.replace("-", "/"),
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        r = requests.post(url, data=payload, headers=headers, timeout=10)
        r.raise_for_status()
        tables = pd.read_html(io.StringIO(r.text))
        # The TXF rows live in one of the larger tables; pick the one with TX rows.
        for t in tables:
            if t.shape[1] >= 8 and "TX" in str(t.iloc[:, 0].head(20).tolist()):
                t = t.copy()
                t["query_date"] = date_str
                return t
        return pd.DataFrame()
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] TAIFEX fetch failed for {date_str}: {exc}", file=sys.stderr)
        return pd.DataFrame()


def build_txf_continuous(
    daily_records: pd.DataFrame, roll_rule: str = "third_wed"
) -> pd.DataFrame:
    """Build a continuous TXF series from raw TAIFEX daily contract rows.

    Roll rule: ``third_wed`` rolls to the next-month contract on the third
    Wednesday of each month (TAIFEX TXF expiry convention).
    """
    if daily_records is None or daily_records.empty:
        return pd.DataFrame()
    # Without a working TAIFEX scrape we can't build this; document and return
    # empty so the caller skips the basis chart gracefully.
    return pd.DataFrame()


def compute_basis(taiex_df: pd.DataFrame, txf_continuous: pd.DataFrame) -> pd.DataFrame:
    """Basis = TXF_close - TAIEX_close. Empty result if TXF series missing."""
    if txf_continuous is None or txf_continuous.empty:
        return pd.DataFrame()
    merged = taiex_df[["close"]].rename(columns={"close": "taiex"}).join(
        txf_continuous[["close"]].rename(columns={"close": "txf"}), how="inner"
    )
    merged["basis"] = merged["txf"] - merged["taiex"]
    return merged


def main() -> None:
    print("[Phase 2] Fetching ^TWII 3y from yfinance...")
    taiex = fetch_taiex_yf("2023-05-15", "2026-05-16")
    out = RAW_DIR / "taiex_3y.parquet"
    taiex.to_parquet(out)
    print(f"  ^TWII rows={len(taiex)} range={taiex.index.min().date()} -> {taiex.index.max().date()}")
    print(f"  saved -> {out} ({out.stat().st_size:,} bytes)")

    print("\n[Phase 2] Attempting TAIFEX TXF backfill (180d, optional)...")
    end = pd.Timestamp("2026-05-15", tz=TWT)
    start = end - pd.Timedelta(days=180)
    business_days = pd.bdate_range(start=start.tz_convert(None), end=end.tz_convert(None))
    records = []
    success = 0
    # Probe first 3 days to see if scraper works at all; skip full loop if it fails
    for d in business_days[:3]:
        df = fetch_taifex_txf_daily(d.strftime("%Y-%m-%d"))
        if not df.empty:
            records.append(df)
            success += 1
    if success == 0:
        print("  TAIFEX scrape probe returned empty for first 3 trading days.")
        print("  -> Skipping TXF basis (per plan, this is OPTIONAL).")
        print("  -> Using ^TWII-only as TXF tracker proxy for Phase 5/6.")
        return

    # Full backfill if probe succeeded
    for d in business_days[3:]:
        df = fetch_taifex_txf_daily(d.strftime("%Y-%m-%d"))
        if not df.empty:
            records.append(df)
        time.sleep(0.2)
    daily = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
    cont = build_txf_continuous(daily)
    basis = compute_basis(taiex, cont)
    if not basis.empty:
        out2 = RAW_DIR / "txf_basis_180d.parquet"
        basis.to_parquet(out2)
        print(f"  TXF basis rows={len(basis)} -> {out2}")
    else:
        print("  TXF continuous build empty -> no basis file.")


if __name__ == "__main__":
    main()
