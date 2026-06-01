"""Phase 3.1: Fetch 13 Asia index series + 10 FX pairs from yfinance.

Saves raw parquet (untouched yfinance output) for Phase 3.2 validation. The
validator handles per-symbol time-zone localisation to TWT.

Run: python3 scripts/fetch_asia_panel.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

INDICES = {
    "N225": "^N225",
    # TOPIX: ^TPX no longer returns data on yfinance; use 1306.T (NEXT FUNDS
    # TOPIX ETF, 1:1 tracker) as a proxy that preserves return correlation.
    "TPX": "1306.T",
    "KS11": "^KS11",
    "KQ11": "^KQ11",
    "TWII": "^TWII",
    "SSE": "000001.SS",
    "CSI300": "000300.SS",
    "SZSE": "399001.SZ",
    # ChiNext: 399006.SZ yfinance feed broken; use 159915.SZ (ChiNext ETF) proxy.
    "CHINEXT": "159915.SZ",
    "HSI": "^HSI",
    "STI": "^STI",
    "NSEI": "^NSEI",
    "AXJO": "^AXJO",
}
FX = {
    "DXY": "DX-Y.NYB",
    "USDJPY": "JPY=X",
    "USDKRW": "KRW=X",
    "USDTWD": "TWD=X",
    # CNH=X yfinance feed broken; use CNY=X (onshore Yuan) as proxy.
    "USDCNH": "CNY=X",
    "USDHKD": "HKD=X",
    "USDSGD": "SGD=X",
    "USDINR": "INR=X",
    "AUDUSD": "AUDUSD=X",
    "AUDJPY": "AUDJPY=X",
}


def _bulk_fetch(symbol_map: dict[str, str], start: str, end: str) -> pd.DataFrame:
    syms = list(symbol_map.values())
    df = yf.download(
        syms,
        start=start,
        end=end,
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    return df


def _per_ticker_fallback(yf_symbol: str) -> pd.DataFrame:
    try:
        h = yf.Ticker(yf_symbol).history(period="3y", auto_adjust=False)
        return h
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] history() fallback failed for {yf_symbol}: {exc}", file=sys.stderr)
        return pd.DataFrame()


def fetch_panel(symbol_map: dict[str, str], label: str, start: str, end: str) -> dict[str, pd.DataFrame]:
    """Return {alias: DataFrame[O,H,L,C,V]} with one retry per empty ticker."""
    print(f"[fetch] {label} bulk download ({len(symbol_map)} symbols)...")
    bulk = _bulk_fetch(symbol_map, start, end)
    out: dict[str, pd.DataFrame] = {}
    for alias, yfsym in symbol_map.items():
        try:
            sub = bulk[yfsym] if isinstance(bulk.columns, pd.MultiIndex) else bulk
        except KeyError:
            sub = pd.DataFrame()
        sub = sub.dropna(how="all") if not sub.empty else sub
        if sub.empty:
            print(f"  [retry] {alias}={yfsym} empty -> trying Ticker.history()")
            time.sleep(2)
            sub = _per_ticker_fallback(yfsym)
        if sub.empty:
            print(f"  [GAP] {alias}={yfsym} still empty after retry")
            out[alias] = pd.DataFrame()
            continue
        sub = sub.rename(columns=str.lower)
        keep = [c for c in ["open", "high", "low", "close", "volume"] if c in sub.columns]
        out[alias] = sub[keep].copy()
        print(f"  [ok] {alias} rows={len(sub)} range={sub.index.min().date()}->{sub.index.max().date()}")
    return out


def save_panel(panel: dict[str, pd.DataFrame], outpath: Path) -> None:
    frames = []
    for alias, df in panel.items():
        if df.empty:
            continue
        d = df.copy()
        d["symbol"] = alias
        d = d.reset_index().rename(columns={"index": "date", "Date": "date"})
        if "date" not in d.columns:
            d = d.rename(columns={d.columns[0]: "date"})
        frames.append(d)
    if not frames:
        print(f"  [skip] empty panel -> {outpath}")
        return
    big = pd.concat(frames, ignore_index=True)
    big.to_parquet(outpath, index=False)
    print(f"  saved {outpath} rows={len(big)} size={outpath.stat().st_size:,} bytes")


def main() -> None:
    start, end = "2023-05-15", "2026-05-16"
    idx_panel = fetch_panel(INDICES, "INDICES", start, end)
    save_panel(idx_panel, RAW_DIR / "asia_indices_raw.parquet")
    fx_panel = fetch_panel(FX, "FX", start, end)
    save_panel(fx_panel, RAW_DIR / "asia_fx_raw.parquet")
    print("\n[done] raw panel saved.")


if __name__ == "__main__":
    main()
