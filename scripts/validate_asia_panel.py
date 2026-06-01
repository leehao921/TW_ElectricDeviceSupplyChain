"""Phase 3.2: Validate Asia panel, anchor to TWT, flag outliers, UPSERT.

Reads raw parquet from Phase 3.1, applies per-symbol TWT close mapping,
computes log returns + z-scores, flags |z|>5 outliers (kept, not deleted),
then UPSERTs into `asia_index_daily` and `fx_daily`. Also writes wide-format
panel to data/asia_market_panel.parquet for downstream covariance work.

Run: python3 scripts/validate_asia_panel.py
"""

from __future__ import annotations

import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytz

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
DATA_DIR = REPO_ROOT / "data"

TWT = pytz.timezone("Asia/Taipei")

# Database access uses `docker exec` against the trading-timescaledb container
# (per project SOP — host credentials are not provided to this agent).
DOCKER_CONTAINER = "trading-timescaledb"
PSQL_USER = "tmf"
PSQL_DB = "tmf_market_data"


def _psql_exec_sql_file(sql_path: Path) -> None:
    """Run a multi-statement SQL file via `docker exec`."""
    # Copy file into container then run with -f for streaming.
    in_container = f"/tmp/{sql_path.name}"
    subprocess.run(
        ["docker", "cp", str(sql_path), f"{DOCKER_CONTAINER}:{in_container}"],
        check=True,
    )
    subprocess.run(
        ["docker", "exec", DOCKER_CONTAINER,
         "psql", "-U", PSQL_USER, "-d", PSQL_DB, "-v", "ON_ERROR_STOP=1",
         "-q", "-f", in_container],
        check=True,
    )

# Local-close-time to TWT mapping. The yfinance index gives a tz-naive local
# date; we localize to the close datetime then convert to Asia/Taipei.
SYMBOL_TZ = {
    "N225":    ("Asia/Tokyo",     15, 0),
    "TPX":     ("Asia/Tokyo",     15, 0),
    "KS11":    ("Asia/Seoul",     15, 30),
    "KQ11":    ("Asia/Seoul",     15, 30),
    "TWII":    ("Asia/Taipei",    13, 30),
    "SSE":     ("Asia/Shanghai",  15, 0),
    "CSI300":  ("Asia/Shanghai",  15, 0),
    "SZSE":    ("Asia/Shanghai",  15, 0),
    "CHINEXT": ("Asia/Shanghai",  15, 0),
    "HSI":     ("Asia/Hong_Kong", 16, 0),
    "STI":     ("Asia/Singapore", 17, 0),
    "NSEI":    ("Asia/Kolkata",   15, 30),
    "AXJO":    ("Australia/Sydney", 16, 0),
}

# FX pairs treated as continuous quotes anchored to NY 17:00 ET; record source_close_tz='NY17ET'.
FX_SYMBOLS = ["DXY", "USDJPY", "USDKRW", "USDTWD", "USDCNH",
              "USDHKD", "USDSGD", "USDINR", "AUDUSD", "AUDJPY"]

# Known-real outliers (do not down-rank when reviewing).
OUTLIER_WHITELIST = {"2024-08-05"}  # yen carry crash

# Pre-known corporate actions in proxy tickers. yfinance returns unadjusted
# prices for our TPX proxy (1306.T NEXT FUNDS TOPIX ETF) which underwent a
# 10:1 reverse split on 2026-03-30. We forward-adjust pre-split prices by
# the split ratio so log returns are continuous.
PROXY_SPLITS = {
    "TPX": [("2026-03-30", 10.0)],  # before-this-date prices DIVIDED by 10
}


def _apply_proxy_splits(df: pd.DataFrame) -> pd.DataFrame:
    """Adjust pre-split closes for known proxy-ticker corporate actions."""
    df = df.copy()
    for sym, splits in PROXY_SPLITS.items():
        mask_sym = df["symbol"] == sym
        if not mask_sym.any():
            continue
        for date_str, ratio in splits:
            cutoff = pd.Timestamp(date_str)
            mask_pre = mask_sym & (pd.to_datetime(df["date"]) < cutoff)
            for col in ("open", "high", "low", "close"):
                if col in df.columns:
                    df.loc[mask_pre, col] = df.loc[mask_pre, col] / ratio
    return df


def _localize_index_close(df: pd.DataFrame, alias: str) -> pd.DataFrame:
    """Convert tz-naive yfinance daily index to TWT-anchored close timestamps."""
    if alias not in SYMBOL_TZ:
        return df
    src_tz, hh, mm = SYMBOL_TZ[alias]
    naive = pd.to_datetime(df["date"])
    if hasattr(naive.dt, "tz") and naive.dt.tz is not None:
        naive = naive.dt.tz_convert(None)
    local_close = naive.dt.normalize() + pd.Timedelta(hours=hh, minutes=mm)
    local = local_close.dt.tz_localize(src_tz, ambiguous="NaT", nonexistent="shift_forward")
    df = df.copy()
    df["ts"] = local.dt.tz_convert("Asia/Taipei")
    return df


def _localize_fx(df: pd.DataFrame) -> pd.DataFrame:
    """FX yfinance daily already aggregates to NY 17:00 ET; anchor there + convert."""
    naive = pd.to_datetime(df["date"])
    if hasattr(naive.dt, "tz") and naive.dt.tz is not None:
        naive = naive.dt.tz_convert(None)
    # NY 17:00 ET is the conventional FX daily close
    close = naive.dt.normalize() + pd.Timedelta(hours=17)
    local = close.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
    df = df.copy()
    df["ts"] = local.dt.tz_convert("Asia/Taipei")
    return df


def _flag_outliers(df: pd.DataFrame, group_col: str = "symbol") -> pd.DataFrame:
    """Compute log returns, z-score per symbol, flag |z|>5."""
    df = df.sort_values([group_col, "ts"]).copy()
    df["logret"] = np.log(df["close"].astype(float)).groupby(df[group_col]).diff()
    grp = df.groupby(group_col)["logret"]
    df["ret_mean"] = grp.transform("mean")
    df["ret_std"] = grp.transform("std")
    df["outlier_zscore"] = (df["logret"] - df["ret_mean"]) / df["ret_std"]
    df["outlier_flag"] = df["outlier_zscore"].abs() > 5
    return df


def _sql_lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return "NULL"
        return repr(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def upsert_indices(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    rows = []
    for _, r in df.iterrows():
        try:
            close = float(r["close"])
            if math.isnan(close):
                continue
        except (TypeError, ValueError):
            continue
        zscore = r.get("outlier_zscore")
        if pd.isna(zscore):
            zscore = None
        else:
            zscore = float(zscore)
        ts_iso = r["ts"].isoformat()
        rows.append((
            ts_iso, r["symbol"], None,
            _safe_float(r.get("open")),
            _safe_float(r.get("high")),
            _safe_float(r.get("low")),
            close,
            _safe_int(r.get("volume")),
            "yfinance",
            bool(r.get("outlier_flag", False)),
            zscore,
        ))

    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write("BEGIN;\n")
        # Chunk to keep individual statements reasonable.
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            values = ",\n".join(
                "(" + ",".join(_sql_lit(v) for v in row) + ")" for row in chunk
            )
            f.write(
                "INSERT INTO asia_index_daily "
                "(ts, symbol, exchange, open, high, low, close, volume, "
                "source, outlier_flag, outlier_zscore) VALUES\n"
                f"{values}\n"
                "ON CONFLICT (ts, symbol) DO UPDATE SET "
                "open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, "
                "close=EXCLUDED.close, volume=EXCLUDED.volume, "
                "outlier_flag=EXCLUDED.outlier_flag, "
                "outlier_zscore=EXCLUDED.outlier_zscore;\n"
            )
        f.write("COMMIT;\n")
        sql_path = Path(f.name)
    _psql_exec_sql_file(sql_path)
    sql_path.unlink(missing_ok=True)
    return len(rows)


def upsert_fx(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    rows = []
    for _, r in df.iterrows():
        try:
            close = float(r["close"])
            if math.isnan(close):
                continue
        except (TypeError, ValueError):
            continue
        ts_iso = r["ts"].isoformat()
        rows.append((
            ts_iso, r["symbol"],
            _safe_float(r.get("open")),
            _safe_float(r.get("high")),
            _safe_float(r.get("low")),
            close,
            "yfinance",
            "NY17ET",
        ))

    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write("BEGIN;\n")
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            values = ",\n".join(
                "(" + ",".join(_sql_lit(v) for v in row) + ")" for row in chunk
            )
            f.write(
                "INSERT INTO fx_daily "
                "(ts, pair, open, high, low, close, source, source_close_tz) VALUES\n"
                f"{values}\n"
                "ON CONFLICT (ts, pair, source_close_tz) DO UPDATE SET "
                "open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, "
                "close=EXCLUDED.close;\n"
            )
        f.write("COMMIT;\n")
        sql_path = Path(f.name)
    _psql_exec_sql_file(sql_path)
    sql_path.unlink(missing_ok=True)
    return len(rows)


def _safe_float(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def build_wide_panel(indices: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    """Wide panel: rows=date (naive UTC date), cols=symbol/pair, values=close."""
    idx_wide = indices.pivot_table(
        index=indices["ts"].dt.tz_convert("Asia/Taipei").dt.normalize(),
        columns="symbol",
        values="close",
        aggfunc="last",
    )
    fx_wide = fx.pivot_table(
        index=fx["ts"].dt.tz_convert("Asia/Taipei").dt.normalize(),
        columns="symbol",
        values="close",
        aggfunc="last",
    )
    wide = idx_wide.join(fx_wide, how="outer").sort_index()
    return wide


def main() -> None:
    idx_raw = pd.read_parquet(RAW_DIR / "asia_indices_raw.parquet")
    fx_raw = pd.read_parquet(RAW_DIR / "asia_fx_raw.parquet")

    print(f"[load] indices raw rows={len(idx_raw)} symbols={idx_raw['symbol'].nunique()}")
    print(f"[load] fx raw rows={len(fx_raw)} pairs={fx_raw['symbol'].nunique()}")

    # Pre-split adjust proxy tickers before TZ localisation.
    idx_raw = _apply_proxy_splits(idx_raw)

    # Localize indices per-symbol
    idx_parts = []
    for alias, sub in idx_raw.groupby("symbol"):
        idx_parts.append(_localize_index_close(sub, alias))
    indices = pd.concat(idx_parts, ignore_index=True)
    indices = _flag_outliers(indices, "symbol")

    fx = _localize_fx(fx_raw)
    fx = _flag_outliers(fx, "symbol")

    # Summary
    print("\n[summary] per-symbol counts:")
    summary = indices.groupby("symbol").agg(
        rows=("close", "size"),
        first=("ts", "min"),
        last=("ts", "max"),
        outliers=("outlier_flag", "sum"),
    )
    print(summary.to_string())
    print("\n[summary] per-pair counts:")
    fx_summary = fx.groupby("symbol").agg(
        rows=("close", "size"),
        first=("ts", "min"),
        last=("ts", "max"),
        outliers=("outlier_flag", "sum"),
    )
    print(fx_summary.to_string())

    # Show outliers
    out_rows = indices[indices["outlier_flag"]].copy()
    out_rows_fx = fx[fx["outlier_flag"]].copy()
    print(f"\n[outliers] indices flagged: {len(out_rows)}")
    if not out_rows.empty:
        print(out_rows[["ts", "symbol", "close", "logret", "outlier_zscore"]].to_string())
    print(f"\n[outliers] fx flagged: {len(out_rows_fx)}")
    if not out_rows_fx.empty:
        print(out_rows_fx[["ts", "symbol", "close", "logret", "outlier_zscore"]].to_string())

    # Build wide panel & save
    wide = build_wide_panel(indices, fx)
    out_panel = DATA_DIR / "asia_market_panel.parquet"
    wide.to_parquet(out_panel)
    print(f"\n[save] wide panel -> {out_panel} shape={wide.shape}")

    # Upsert to DB
    print("\n[db] UPSERT asia_index_daily ...")
    n_idx = upsert_indices(indices)
    print(f"  wrote {n_idx} rows")
    print("[db] UPSERT fx_daily ...")
    n_fx = upsert_fx(fx)
    print(f"  wrote {n_fx} rows")

    # Save outlier audit to parquet
    if not out_rows.empty or not out_rows_fx.empty:
        audit = pd.concat([
            out_rows.assign(kind="index"),
            out_rows_fx.assign(kind="fx"),
        ], ignore_index=True)
        audit_path = DATA_DIR / "outliers_audit.parquet"
        audit.to_parquet(audit_path)
        print(f"\n[save] outliers audit -> {audit_path}")

    print("\n[done] Phase 3.2 complete.")


if __name__ == "__main__":
    main()
