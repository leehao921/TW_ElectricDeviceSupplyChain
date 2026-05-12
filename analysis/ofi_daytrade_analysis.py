"""
OFI vs 當沖活躍度分析
===================
A: OFI proxy 指標 — 從 DB 的 stock_ofi 計算各股當沖活躍度代理指標
B: 外盤率代理 — 透過 Shioaji api.ticks() 計算 tick_type 外盤率，與 OFI 交叉驗證

資料來源:
- trading-timescaledb: stock_ofi (ofi_score, 每~42秒)
- Shioaji API: 歷史 tick (tick_type=1外盤, 2內盤)

使用方式:
    python analysis/ofi_daytrade_analysis.py [--symbols 2330 2317] [--days 5]
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, date

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "tmf",
    "password": "tmf_dev_2026",
    "dbname": "tmf_market_data",
}

# 20 stocks tracked in stock_ofi
DEFAULT_SYMBOLS = [
    "1101", "1216", "1301", "1303", "2002", "2303", "2308", "2317",
    "2330", "2357", "2379", "2382", "2412", "2454", "2603", "2609",
    "2881", "2882", "3231", "3711",
]

# TWSE trading days (skip weekends & 5/1 勞動節)
SKIP_DATES = {"2026-05-01"}  # 勞動節

TZ = "Asia/Taipei"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_trading_days(n_days: int) -> list[str]:
    """Return last n_days of TWSE trading dates (Mon–Fri, not holiday)."""
    result = []
    d = date.today()
    while len(result) < n_days:
        d -= timedelta(days=1)
        if d.weekday() >= 5:  # Saturday=5, Sunday=6
            continue
        if d.strftime("%Y-%m-%d") in SKIP_DATES:
            continue
        result.append(d.strftime("%Y-%m-%d"))
    return list(reversed(result))


def get_db_conn():
    return psycopg2.connect(**DB_CONFIG)


# ---------------------------------------------------------------------------
# Part A: OFI proxy metrics from DB
# ---------------------------------------------------------------------------
def fetch_ofi_data(symbols: list[str], trading_days: list[str]) -> pd.DataFrame:
    """Fetch ofi_score from stock_ofi for given symbols and dates."""
    start = trading_days[0] + " 00:00:00+08"
    end   = trading_days[-1] + " 23:59:59+08"
    placeholders = ",".join(["%s"] * len(symbols))

    sql = f"""
        SELECT
            ts AT TIME ZONE 'Asia/Taipei' AS local_ts,
            symbol,
            value AS ofi_score,
            direction
        FROM stock_ofi
        WHERE signal_type = 'ofi_score'
          AND symbol IN ({placeholders})
          AND ts >= %s AND ts <= %s
        ORDER BY symbol, ts
    """
    conn = get_db_conn()
    try:
        df = pd.read_sql(sql, conn, params=symbols + [start, end])
    finally:
        conn.close()

    df["local_ts"] = pd.to_datetime(df["local_ts"])
    df["trade_date"] = df["local_ts"].dt.date.astype(str)
    # Filter to market hours only (09:00–13:30 TSE)
    df = df[df["local_ts"].dt.time.between(
        pd.Timestamp("09:00").time(), pd.Timestamp("13:30").time()
    )]
    # Filter to actual trading days
    df = df[df["trade_date"].isin(trading_days)]
    return df


def compute_ofi_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per symbol per day:
      - flip_rate:   direction changes per hour (高 → 頻繁進出，當沖活躍代理)
      - ofi_abs_avg: average |ofi_score| (訂單流強度)
      - ofi_std:     ofi_score 標準差 (波動性)
      - ask_dom_pct: OFI > 0 的比例 (買方主導比率)
    """
    records = []
    for (sym, day), g in df.groupby(["symbol", "trade_date"]):
        g = g.sort_values("local_ts")
        scores = g["ofi_score"].values
        directions = g["direction"].values

        # flip rate: number of direction changes per hour
        flips = int((directions[:-1] != directions[1:]).sum())
        hours = max((g["local_ts"].iloc[-1] - g["local_ts"].iloc[0]).total_seconds() / 3600, 0.01)
        flip_rate = flips / hours

        records.append({
            "symbol":      sym,
            "trade_date":  day,
            "flip_rate":   round(flip_rate, 2),
            "ofi_abs_avg": round(float(np.mean(np.abs(scores))), 6),
            "ofi_std":     round(float(np.std(scores)), 6),
            "ask_dom_pct": round(float((scores > 0).mean() * 100), 1),
            "n_ticks":     len(g),
        })

    result = pd.DataFrame(records)

    # Z-score across symbols per day (to rank activity level)
    for col in ["flip_rate", "ofi_abs_avg", "ofi_std"]:
        result[f"{col}_z"] = result.groupby("trade_date")[col].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-9)
        ).round(2)

    result["daytrade_proxy"] = (
        result["flip_rate_z"] * 0.5
        + result["ofi_abs_avg_z"] * 0.3
        + result["ofi_std_z"] * 0.2
    ).round(3)

    return result.sort_values(["trade_date", "daytrade_proxy"], ascending=[True, False])


def compute_intraday_ofi_pattern(df: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """30-min bucketed average OFI to show intraday 當沖 activity pattern."""
    df = df[df["symbol"].isin(symbols)].copy()
    df["bucket"] = df["local_ts"].dt.floor("30min").dt.strftime("%H:%M")
    pattern = df.groupby(["symbol", "bucket"])["ofi_score"].agg(
        mean="mean", std="std", count="count"
    ).reset_index()
    return pattern


# ---------------------------------------------------------------------------
# Part B: Shioaji tick data → 外盤率 (daytrade activity proxy)
# ---------------------------------------------------------------------------
def fetch_shioaji_ticks(symbols: list[str], trading_days: list[str]) -> pd.DataFrame:
    """
    Use Shioaji api.ticks() to get historical ticks.
    tick_type=1 → 外盤 (buyer-aggressor), tick_type=2 → 內盤 (seller-aggressor)
    外盤率 = sum(volume where tick_type==1) / total_volume  (≈ buy pressure ratio)
    """
    try:
        import shioaji as sj
    except ImportError:
        print("[WARN] shioaji not installed, skipping Part B")
        return pd.DataFrame()

    api_key    = os.environ.get("SHIOAJI_API_KEY", "EdzqpQt54muRsVmnCLj3PaSZwHucybZiZeqwQwWAiprv")
    secret_key = os.environ.get("SHIOAJI_SECRET_KEY", "5f9FufgSMRdAKDGNPDFEa46v25NifQhjRhQDz4HWL1MV")

    import time
    print("[B] Logging in to Shioaji...")
    api = sj.Shioaji()
    api.login(api_key=api_key, secret_key=secret_key)
    time.sleep(3)  # wait for contract data to load

    records = []
    for sym in symbols:
        contract = api.Contracts.Stocks.get(sym)
        if contract is None:
            print(f"  [WARN] contract not found: {sym}")
            continue

        for day in trading_days:
            try:
                ticks = api.ticks(contract=contract, date=day)
            except Exception as e:
                print(f"  [WARN] ticks failed {sym} {day}: {e}")
                continue

            if ticks is None or not ticks.ts:
                continue

            df_t = pd.DataFrame({
                "ts":        ticks.ts,
                "price":     ticks.close,
                "volume":    ticks.volume,
                "tick_type": ticks.tick_type,
            })
            # ticks.ts is nanoseconds in local Taiwan time (UTC+8), not UTC
            df_t["ts"] = pd.to_datetime(df_t["ts"], unit="ns")

            # Market hours only
            df_t = df_t[df_t["ts"].dt.time.between(
                pd.Timestamp("09:00").time(), pd.Timestamp("13:30").time()
            )]
            if df_t.empty:
                continue

            total_vol  = df_t["volume"].sum()
            ask_vol    = df_t[df_t["tick_type"] == 1]["volume"].sum()  # 外盤
            bid_vol    = df_t[df_t["tick_type"] == 2]["volume"].sum()  # 內盤
            unknown    = df_t[df_t["tick_type"] == 0]["volume"].sum()

            # 外盤率 (買方主動比率)
            net_ask_vol = total_vol - unknown
            ask_rate    = ask_vol / net_ask_vol if net_ask_vol > 0 else 0.5

            # VWAP-weighted OFI proxy: Σ(sign * vol) / total_vol
            df_t["signed_vol"] = df_t.apply(
                lambda r: r["volume"] if r["tick_type"] == 1
                          else -r["volume"] if r["tick_type"] == 2
                          else 0, axis=1
            )
            tick_ofi_proxy = df_t["signed_vol"].sum() / total_vol if total_vol > 0 else 0

            records.append({
                "symbol":         sym,
                "trade_date":     day,
                "total_volume":   int(total_vol),
                "ask_volume":     int(ask_vol),
                "bid_volume":     int(bid_vol),
                "ask_rate_pct":   round(ask_rate * 100, 2),
                "tick_ofi_proxy": round(tick_ofi_proxy, 4),
                "n_ticks":        len(df_t),
            })
            print(f"  {sym} {day}: ask_rate={ask_rate*100:.1f}%  tick_ofi={tick_ofi_proxy:.4f}")

    api.logout()
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Cross-correlation: OFI proxy vs 外盤率
# ---------------------------------------------------------------------------
def cross_correlate(ofi_proxy: pd.DataFrame, tick_df: pd.DataFrame) -> pd.DataFrame:
    if tick_df.empty:
        return pd.DataFrame()

    merged = pd.merge(
        ofi_proxy[["symbol", "trade_date", "flip_rate", "ofi_abs_avg",
                    "ofi_std", "ask_dom_pct", "daytrade_proxy"]],
        tick_df[["symbol", "trade_date", "ask_rate_pct", "tick_ofi_proxy", "total_volume"]],
        on=["symbol", "trade_date"],
    )

    print("\n[Correlation] OFI proxy metrics vs 外盤率 (tick_type ask_rate):")
    for col in ["flip_rate", "ofi_abs_avg", "ofi_std", "ask_dom_pct", "daytrade_proxy"]:
        r = merged[col].corr(merged["ask_rate_pct"])
        print(f"  {col:20s} ↔ ask_rate_pct:  r = {r:+.3f}")

    print("\n[Correlation] OFI proxy metrics vs tick_ofi_proxy:")
    for col in ["flip_rate", "ofi_abs_avg", "daytrade_proxy"]:
        r = merged[col].corr(merged["tick_ofi_proxy"])
        print(f"  {col:20s} ↔ tick_ofi_proxy: r = {r:+.3f}")

    return merged


# ---------------------------------------------------------------------------
# Print / Report helpers
# ---------------------------------------------------------------------------
def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_ofi_summary(proxy_df: pd.DataFrame, top_n: int = 5):
    print_section("Part A — OFI 當沖活躍度代理排名 (per day)")
    for day, grp in proxy_df.groupby("trade_date"):
        print(f"\n  📅 {day}  (Top {top_n} most active / least active)")
        print(f"  {'Symbol':>8}  {'flip_rate':>10}  {'ofi_abs':>10}  {'ofi_std':>10}  "
              f"{'ask_dom%':>9}  {'proxy_z':>8}")
        print("  " + "-" * 65)
        for _, r in grp.head(top_n).iterrows():
            print(f"  {r['symbol']:>8}  {r['flip_rate']:>10.1f}  {r['ofi_abs_avg']:>10.6f}  "
                  f"{r['ofi_std']:>10.6f}  {r['ask_dom_pct']:>9.1f}  {r['daytrade_proxy']:>8.3f}")
        print("  ...")
        bottom = grp.tail(top_n)
        for _, r in bottom.iterrows():
            print(f"  {r['symbol']:>8}  {r['flip_rate']:>10.1f}  {r['ofi_abs_avg']:>10.6f}  "
                  f"{r['ofi_std']:>10.6f}  {r['ask_dom_pct']:>9.1f}  {r['daytrade_proxy']:>8.3f}")


def print_intraday_pattern(pattern_df: pd.DataFrame):
    print_section("Part A — 日內 OFI 時段分布 (30-min buckets)")
    pivot = pattern_df.pivot_table(
        index="bucket", columns="symbol", values="mean"
    ).round(6)
    print(pivot.to_string())


def print_tick_summary(tick_df: pd.DataFrame):
    print_section("Part B — Shioaji Tick 外盤率 (ask_rate) per symbol per day")
    if tick_df.empty:
        print("  (no data — Shioaji unavailable or no ticks)")
        return
    print(tick_df.sort_values(["trade_date", "ask_rate_pct"], ascending=[True, False]).to_string(index=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="OFI vs 當沖活躍度分析")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--days",    type=int,  default=5,   help="Number of trading days")
    parser.add_argument("--top",     type=int,  default=5,   help="Top N to display per day")
    parser.add_argument("--skip-shioaji", action="store_true", help="Skip Shioaji tick fetch (Part B)")
    parser.add_argument("--pattern-symbols", nargs="+", default=["2330", "2317", "2454"],
                        help="Symbols to show intraday OFI pattern for")
    args = parser.parse_args()

    trading_days = get_trading_days(args.days)
    print(f"Trading days: {trading_days}")
    print(f"Symbols ({len(args.symbols)}): {args.symbols}")

    # ---- Part A ----
    print_section("Fetching OFI data from DB...")
    ofi_df = fetch_ofi_data(args.symbols, trading_days)
    print(f"  Fetched {len(ofi_df):,} OFI records")

    proxy_df = compute_ofi_proxy(ofi_df)
    print_ofi_summary(proxy_df, top_n=args.top)

    pattern_df = compute_intraday_ofi_pattern(ofi_df, args.pattern_symbols)
    print_intraday_pattern(pattern_df)

    # ---- Part B ----
    tick_df = pd.DataFrame()
    if not args.skip_shioaji:
        print_section("Fetching Shioaji tick data...")
        tick_df = fetch_shioaji_ticks(args.symbols, trading_days)
        print_tick_summary(tick_df)

        # ---- Cross-correlation ----
        if not tick_df.empty:
            print_section("Cross-correlation: OFI proxies vs 外盤率")
            merged = cross_correlate(proxy_df, tick_df)
            if not merged.empty:
                print("\n[Top 10 highest daytrade_proxy with ask_rate]:")
                top = merged.nlargest(10, "daytrade_proxy")[
                    ["symbol", "trade_date", "daytrade_proxy", "ask_rate_pct", "tick_ofi_proxy", "total_volume"]
                ]
                print(top.to_string(index=False))

    # ---- Save CSV ----
    out_dir = "analysis/reports"
    os.makedirs(out_dir, exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    proxy_df.to_csv(f"{out_dir}/ofi_daytrade_proxy_{today}.csv", index=False)
    print(f"\n✅ Saved: {out_dir}/ofi_daytrade_proxy_{today}.csv")
    if not tick_df.empty:
        tick_df.to_csv(f"{out_dir}/tick_askrate_{today}.csv", index=False)
        print(f"✅ Saved: {out_dir}/tick_askrate_{today}.csv")


if __name__ == "__main__":
    main()
