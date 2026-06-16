"""
smart_money_analysis.py — 三大法人 N 日累計淨買 by Sector × Theme.

Pulls `institutional_stock` from trading-timescaledb, converts share-count net
buys to 億 TWD (with yfinance OTC close fallback), aggregates by Pilot_Reports
sector and themes/ supply chain, and renders a Markdown report.

Usage:
    python scripts/smart_money_analysis.py
    python scripts/smart_money_analysis.py --as-of 2026-06-15 --window 20
    python scripts/smart_money_analysis.py --window 5 --top-tickers 10
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date as dtdate
from pathlib import Path

import pandas as pd
import psycopg2

# --------------------------------------------------------------------------- #
# Paths & config
# --------------------------------------------------------------------------- #
REPO = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO / "Pilot_Reports"
THEMES_DIR = REPO / "themes"
CACHE_DIR = REPO / ".cache"
DEFAULT_OUT_DIR = REPO / "analysis"

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "tmf_market_data",
    "user": "tmf",
    "password": os.environ.get("TMF_PG_PASSWORD", "tmf_dev_2026"),
    "connect_timeout": 5,
}

INSTITUTIONS = ["foreign_net", "trust_net", "dealer_net"]
INST_ZH = {"foreign_net": "外資", "trust_net": "投信", "dealer_net": "自營"}
SKIP_THEMES = {"README"}

TICKER_BOLD_RE = re.compile(r"\*\*(\d{4})\s")  # **2330 台積電** in theme files
FILENAME_TICKER_RE = re.compile(r"^(\d{4})_")  # 2330_台積電.md


# --------------------------------------------------------------------------- #
# Data layer
# --------------------------------------------------------------------------- #
def latest_data_date(conn) -> dtdate:
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(date) FROM institutional_stock")
        return cur.fetchone()[0]


def trading_days(conn, as_of: dtdate, window: int) -> list[dtdate]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT date FROM institutional_stock
            WHERE date <= %s
            ORDER BY date DESC LIMIT %s
            """,
            (as_of, window),
        )
        return sorted(r[0] for r in cur.fetchall())


def load_flow(conn, start_date: dtdate, end_date: dtdate) -> pd.DataFrame:
    sql = """
    SELECT date, symbol, foreign_net, trust_net, dealer_net, close_price
    FROM institutional_stock
    WHERE date BETWEEN %s AND %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (start_date, end_date))
        rows = cur.fetchall()
    df = pd.DataFrame(
        rows,
        columns=["date", "symbol", "foreign_net", "trust_net", "dealer_net", "close_price"],
    )
    for c in INSTITUTIONS:
        df[c] = df[c].astype("float64")
    df["close_price"] = df["close_price"].astype("float64")
    return df


def load_futures_oi(conn, start_date: dtdate, end_date: dtdate) -> pd.DataFrame:
    """Pull TXF/MXF/TMF 三大法人 OI for the window. Returns one row per
    (settle_date, underlying, participant_type) with net_oi (snapshot) and
    trade_net (daily flow). Empty DataFrame if futures_oi_daily has no
    coverage in the window."""
    sql = """
    SELECT settle_date, underlying, participant_type, long_oi, short_oi, net_oi, trade_net
    FROM futures_oi_daily
    WHERE settle_date BETWEEN %s AND %s
    ORDER BY settle_date, underlying, participant_type
    """
    with conn.cursor() as cur:
        cur.execute(sql, (start_date, end_date))
        rows = cur.fetchall()
    return pd.DataFrame(
        rows,
        columns=["settle_date", "underlying", "participant_type",
                 "long_oi", "short_oi", "net_oi", "trade_net"],
    )


# --------------------------------------------------------------------------- #
# Coverage maps (sector + theme)
# --------------------------------------------------------------------------- #
def build_sector_map() -> dict[str, str]:
    sm: dict[str, str] = {}
    for sector_dir in REPORTS_DIR.iterdir():
        if not sector_dir.is_dir():
            continue
        for md in sector_dir.glob("*.md"):
            m = FILENAME_TICKER_RE.match(md.name)
            if m:
                sm[m.group(1)] = sector_dir.name
    return sm


def build_theme_map() -> dict[str, set[str]]:
    tm: dict[str, set[str]] = defaultdict(set)
    for md in THEMES_DIR.glob("*.md"):
        theme = md.stem
        if theme in SKIP_THEMES:
            continue
        for line in md.read_text(encoding="utf-8").splitlines():
            for m in TICKER_BOLD_RE.finditer(line):
                tm[theme].add(m.group(1))
    return dict(tm)


def build_ticker_name_map() -> dict[str, str]:
    nm: dict[str, str] = {}
    for sector_dir in REPORTS_DIR.iterdir():
        if not sector_dir.is_dir():
            continue
        for md in sector_dir.glob("*.md"):
            stem = md.stem  # "2330_台積電"
            if "_" in stem:
                tk, name = stem.split("_", 1)
                if re.fullmatch(r"\d{4}", tk):
                    nm[tk] = name
    return nm


# --------------------------------------------------------------------------- #
# OTC close fallback (yfinance)
# --------------------------------------------------------------------------- #
def fetch_otc_closes(otc_tickers: list[str], as_of: dtdate) -> dict[str, float]:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / f"otc_close_{as_of}.json"
    cache: dict[str, float] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())

    missing = [tk for tk in otc_tickers if tk not in cache]
    if missing:
        try:
            import yfinance as yf
        except ImportError:
            print("[warn] yfinance not installed — OTC TWD valuations will be 0", file=sys.stderr)
            return cache
        print(f"[info] yfinance fetch for {len(missing)} OTC tickers...", file=sys.stderr)
        for tk in missing:
            try:
                h = yf.Ticker(f"{tk}.TWO").history(period="5d", auto_adjust=False)
                cache[tk] = float(h["Close"].iloc[-1]) if not h.empty else 0.0
            except Exception as exc:  # pylint: disable=broad-except
                print(f"[warn] yfinance {tk}.TWO failed: {exc}", file=sys.stderr)
                cache[tk] = 0.0
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return cache


def attach_twd(df: pd.DataFrame, as_of: dtdate, universe: set[str]) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    otc_in_universe = df.loc[
        (df["close_price"] == 0) & df["symbol"].isin(universe), "symbol"
    ].unique().tolist()
    otc_close = fetch_otc_closes(otc_in_universe, as_of)

    df["close_eff"] = df.apply(
        lambda r: otc_close.get(r["symbol"], 0.0) if r["close_price"] == 0 else r["close_price"],
        axis=1,
    )
    for inst in INSTITUTIONS:
        df[f"{inst}_twd"] = df[inst] * df["close_eff"] / 1e8  # 億 TWD
    return df, {"otc_fetched": len(otc_in_universe), "otc_zero": sum(1 for v in otc_close.values() if v == 0)}


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def per_ticker_window_sum(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("symbol", as_index=False).agg(
        foreign=("foreign_net_twd", "sum"),
        trust=("trust_net_twd", "sum"),
        dealer=("dealer_net_twd", "sum"),
        days=("date", "nunique"),
    )
    agg["total"] = agg["foreign"] + agg["trust"] + agg["dealer"]
    return agg


def aggregate_sector(per_ticker: pd.DataFrame, sector_map: dict[str, str]) -> pd.DataFrame:
    pt = per_ticker.copy()
    pt["sector"] = pt["symbol"].map(sector_map)
    pt = pt.dropna(subset=["sector"])
    g = pt.groupby("sector", as_index=False).agg(
        n_tickers=("symbol", "count"),
        外資=("foreign", "sum"),
        投信=("trust", "sum"),
        自營=("dealer", "sum"),
    )
    g["三大合計"] = g["外資"] + g["投信"] + g["自營"]
    return g.sort_values("外資", ascending=False).reset_index(drop=True)


def aggregate_theme(per_ticker: pd.DataFrame, theme_map: dict[str, set[str]]) -> pd.DataFrame:
    pt_idx = per_ticker.set_index("symbol")
    rows = []
    for theme, tickers in theme_map.items():
        sub = pt_idx.reindex(list(tickers)).dropna(how="all")
        rows.append({
            "theme": theme,
            "n_tickers": len(sub),
            "外資": sub["foreign"].sum(),
            "投信": sub["trust"].sum(),
            "自營": sub["dealer"].sum(),
            "三大合計": sub["foreign"].sum() + sub["trust"].sum() + sub["dealer"].sum(),
        })
    return pd.DataFrame(rows).sort_values("外資", ascending=False).reset_index(drop=True)


def divergence_rows(group_df: pd.DataFrame, group_col: str, min_abs: float = 5.0) -> pd.DataFrame:
    """Rows where 外資 and 投信 have opposite signs and both |x| > min_abs (億)."""
    sub = group_df.copy()
    sub["divergence"] = sub["外資"] * sub["投信"] < 0
    sub = sub[sub["divergence"]]
    sub = sub[(sub["外資"].abs() > min_abs) & (sub["投信"].abs() > min_abs)]
    sub["abs_score"] = sub["外資"].abs() + sub["投信"].abs()
    return sub.sort_values("abs_score", ascending=False)[[group_col, "外資", "投信", "自營", "n_tickers"]]


def top_tickers_in_group(
    per_ticker: pd.DataFrame,
    group_members: list[str],
    n: int,
    name_map: dict[str, str],
) -> pd.DataFrame:
    sub = per_ticker[per_ticker["symbol"].isin(group_members)].copy()
    sub["name"] = sub["symbol"].map(name_map).fillna("")
    sub["三大合計"] = sub["foreign"] + sub["trust"] + sub["dealer"]
    return sub.sort_values("foreign", ascending=False).head(n)[
        ["symbol", "name", "foreign", "trust", "dealer", "三大合計"]
    ]


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def fmt(v: float) -> str:
    return f"{v:+,.1f}" if pd.notna(v) else "—"


def render_sector_table(df: pd.DataFrame) -> str:
    lines = [
        "| Sector | n | 外資 (億) | 投信 (億) | 自營 (億) | 三大合計 (億) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in df.iterrows():
        lines.append(
            f"| {r['sector']} | {r['n_tickers']} | {fmt(r['外資'])} | "
            f"{fmt(r['投信'])} | {fmt(r['自營'])} | {fmt(r['三大合計'])} |"
        )
    return "\n".join(lines)


def render_theme_table(df: pd.DataFrame) -> str:
    lines = [
        "| Theme | n | 外資 (億) | 投信 (億) | 自營 (億) | 三大合計 (億) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in df.iterrows():
        lines.append(
            f"| {r['theme']} | {r['n_tickers']} | {fmt(r['外資'])} | "
            f"{fmt(r['投信'])} | {fmt(r['自營'])} | {fmt(r['三大合計'])} |"
        )
    return "\n".join(lines)


def render_div_table(df: pd.DataFrame, group_col: str) -> str:
    if df.empty:
        return "*無顯著分歧 (外資/投信 同向或單方 < 5 億)*"
    lines = [
        f"| {group_col} | 外資 (億) | 投信 (億) | 自營 (億) | n |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, r in df.iterrows():
        lines.append(
            f"| {r[group_col]} | {fmt(r['外資'])} | {fmt(r['投信'])} | "
            f"{fmt(r['自營'])} | {r['n_tickers']} |"
        )
    return "\n".join(lines)


def aggregate_futures_oi(fut: pd.DataFrame, start_date: dtdate, end_date: dtdate) -> pd.DataFrame:
    """Return one row per (underlying, participant_type) with:
       - net_oi_start, net_oi_end (snapshot endpoints)
       - net_oi_change = end - start (positioning shift)
       - trade_net_sum = sum of daily flows (cumulative directional trades)
    All values in lots."""
    if fut.empty:
        return fut
    starts = fut.sort_values("settle_date").drop_duplicates(["underlying", "participant_type"], keep="first")
    ends = fut.sort_values("settle_date").drop_duplicates(["underlying", "participant_type"], keep="last")
    flow = fut.groupby(["underlying", "participant_type"], as_index=False)["trade_net"].sum()
    flow = flow.rename(columns={"trade_net": "trade_net_sum"})

    out = ends[["underlying", "participant_type", "net_oi"]].rename(columns={"net_oi": "net_oi_end"})
    out = out.merge(
        starts[["underlying", "participant_type", "net_oi"]].rename(columns={"net_oi": "net_oi_start"}),
        on=["underlying", "participant_type"],
    )
    out = out.merge(flow, on=["underlying", "participant_type"])
    out["net_oi_change"] = out["net_oi_end"] - out["net_oi_start"]
    underlying_order = {"TXF": 0, "MXF": 1, "TMF": 2}
    part_order = {"外資": 0, "投信": 1, "自營商": 2}
    out["_uo"] = out["underlying"].map(underlying_order)
    out["_po"] = out["participant_type"].map(part_order)
    return out.sort_values(["_uo", "_po"]).drop(columns=["_uo", "_po"]).reset_index(drop=True)


def render_futures_panel(fut_agg: pd.DataFrame, start_date: dtdate, end_date: dtdate) -> str:
    if fut_agg.empty:
        return "*futures_oi_daily 在此窗口無資料 — collector 可能 stale,跳過期貨對照。*"
    lines = [
        f"窗口 {start_date} → {end_date}, 單位 = 口 (lots)。`net_oi` 為當日收盤淨部位,`Δ` 為窗口起訖差。`trade_net 累計` 為窗口內每日 trade_net 加總。",
        "",
        "| Contract | 法人 | net_oi (起) | net_oi (迄) | Δ net_oi | trade_net 累計 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for _, r in fut_agg.iterrows():
        lines.append(
            f"| {r['underlying']} | {r['participant_type']} | "
            f"{int(r['net_oi_start']):+,} | {int(r['net_oi_end']):+,} | "
            f"{int(r['net_oi_change']):+,} | {int(r['trade_net_sum']):+,} |"
        )
    return "\n".join(lines)


def futures_tldr(fut_agg: pd.DataFrame) -> str:
    """One-liner for TL;DR: TXF 外資 net OI direction over window."""
    if fut_agg.empty:
        return "- **期貨 (TXF 外資 net OI):** futures_oi_daily 此窗口無資料"
    row = fut_agg[(fut_agg["underlying"] == "TXF") & (fut_agg["participant_type"] == "外資")]
    if row.empty:
        return "- **期貨 (TXF 外資 net OI):** 資料缺漏"
    r = row.iloc[0]
    direction = "空單擴大" if r["net_oi_change"] < 0 else ("多單擴大" if r["net_oi_change"] > 0 else "持平")
    return (
        f"- **期貨 (TXF 外資 net OI):** {int(r['net_oi_start']):+,} → {int(r['net_oi_end']):+,} 口 "
        f"(Δ {int(r['net_oi_change']):+,},{direction}) — 與 spot 賣壓方向一致則互相確認"
    )


def render_top_tickers(df: pd.DataFrame) -> str:
    lines = [
        "| Ticker | 名稱 | 外資 (億) | 投信 (億) | 自營 (億) | 三大合計 (億) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for _, r in df.iterrows():
        lines.append(
            f"| {r['symbol']} | {r['name']} | {fmt(r['foreign'])} | "
            f"{fmt(r['trust'])} | {fmt(r['dealer'])} | {fmt(r['三大合計'])} |"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Verification log
# --------------------------------------------------------------------------- #
def market_daily_foreign(df: pd.DataFrame) -> list[tuple[str, float]]:
    """Return [(date_str, market-wide foreign_net 億 TWD), ...] sorted by date."""
    daily = df.groupby("date", as_index=False)["foreign_net_twd"].sum()
    daily = daily.sort_values("date")
    return [(d.isoformat(), float(v)) for d, v in zip(daily["date"], daily["foreign_net_twd"])]


def maybe_verify(group_df: pd.DataFrame, group_col: str, df_window: pd.DataFrame, as_of: dtdate) -> str:
    """Run verify_flow_zscore.py against the market-wide foreign_net of the same
    window, to give context on how extreme overall foreign flow was. We do NOT
    attempt per-sector z-score (verifier is market-wide); we cite market context
    next to any sector/theme whose foreign cumulative crosses the 200 億 attention bar."""
    extreme = group_df[group_df["外資"].abs() > 200]
    if extreme.empty:
        return "*無 σ-class 主張 (本輪所有 sector/theme 外資累計 |x| < 200 億,不需驗證)*"

    verifier = REPO / "scripts" / "verify_flow_zscore.py"
    if not verifier.exists():
        return "*verify_flow_zscore.py 不存在,跳過*"

    daily = market_daily_foreign(df_window)
    values_csv = ",".join(f"{v:.2f}" for _, v in daily)

    out = []
    out.append(
        f"**Market-wide context (TAIWAN 全市場 foreign_net, "
        f"K={len(daily)}-day window ending {as_of}):**\n"
    )
    try:
        res = subprocess.run(
            ["python3", str(verifier),
             "--metric", "foreign_net",
             f"--values={values_csv}",
             "--window", "60",
             "--as-of", str(as_of)],
            capture_output=True, text=True, timeout=60,
        )
        if res.returncode == 0:
            out.append("```\n" + res.stdout.strip() + "\n```")
        else:
            out.append(
                f"*verifier exit={res.returncode}* — stderr (first 300 chars):\n"
                f"```\n{res.stderr.strip()[:300]}\n```"
            )
    except Exception as exc:  # pylint: disable=broad-except
        out.append(f"*verifier error*: {exc}")

    out.append(
        f"\n**Sectors/Themes 觸及 200 億注意門檻 ({len(extreme)} 項):** "
        + ", ".join(f"{r[group_col]} ({fmt(r['外資'])})" for _, r in extreme.iterrows())
        + "\n\n*說明: verify_flow_zscore.py 比對市場全體外資 daily flow 的 60 日 rolling-K 日分布,"
        "並非 per-sector z-score。要做嚴格 sector-level 分布需另跑 60 天 per-sector 歷史 (deferred)。*"
    )
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: latest in DB)")
    ap.add_argument("--window", type=int, default=20)
    ap.add_argument("--top-tickers", type=int, default=5)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        as_of = pd.to_datetime(args.as_of).date() if args.as_of else latest_data_date(conn)
        dates = trading_days(conn, as_of, args.window)
        start_date = min(dates)
        print(f"[info] window: {len(dates)} trading days, {start_date} → {as_of}", file=sys.stderr)
        df = load_flow(conn, start_date, as_of)
        print(f"[info] loaded {len(df):,} rows × {df['symbol'].nunique():,} tickers", file=sys.stderr)

        sector_map = build_sector_map()
        theme_map = build_theme_map()
        name_map = build_ticker_name_map()
        universe = set(sector_map.keys()) | set().union(*theme_map.values())
        print(
            f"[info] coverage: {len(sector_map):,} sector / {len(theme_map):,} themes / "
            f"{len(universe):,} tickers in universe",
            file=sys.stderr,
        )

        df, otc_stats = attach_twd(df, as_of, universe)
        print(f"[info] OTC fallback: {otc_stats}", file=sys.stderr)

        per_ticker = per_ticker_window_sum(df)
        # Sanity: trim to tickers we cover
        per_ticker_cov = per_ticker[per_ticker["symbol"].isin(universe)].copy()
        print(
            f"[info] {len(per_ticker_cov):,} covered tickers contribute to aggregates",
            file=sys.stderr,
        )

        sector_df = aggregate_sector(per_ticker_cov, sector_map)
        theme_df = aggregate_theme(per_ticker_cov, theme_map)

        # Sanity check: sector totals reconcile with per-ticker sums
        s_total = sector_df["外資"].sum()
        pt_total = per_ticker_cov[per_ticker_cov["symbol"].isin(sector_map)]["foreign"].sum()
        assert abs(s_total - pt_total) < 0.01, f"reconcile fail: {s_total} vs {pt_total}"
        print(f"[ok] sector reconcile: {s_total:,.1f} == {pt_total:,.1f} 億", file=sys.stderr)

        sec_div = divergence_rows(sector_df, "sector")
        thm_div = divergence_rows(theme_df, "theme")

        # Top tickers in top-3 sectors (by foreign)
        top3_sec = sector_df.head(3)["sector"].tolist()
        sec_ticker_blocks = []
        for sec in top3_sec:
            members = [t for t, s in sector_map.items() if s == sec]
            top = top_tickers_in_group(per_ticker_cov, members, args.top_tickers, name_map)
            sec_ticker_blocks.append((sec, top))

        # Top tickers in top-3 themes (by foreign)
        top3_thm = theme_df.head(3)["theme"].tolist()
        thm_ticker_blocks = []
        for thm in top3_thm:
            members = list(theme_map[thm])
            top = top_tickers_in_group(per_ticker_cov, members, args.top_tickers, name_map)
            thm_ticker_blocks.append((thm, top))

        veri_log = maybe_verify(sector_df, "sector", df, as_of)

        # Futures OI panel (TXF/MXF/TMF × 三大法人 macro context)
        fut_df = load_futures_oi(conn, start_date, as_of)
        fut_agg = aggregate_futures_oi(fut_df, start_date, as_of)
        fut_days = int(fut_df["settle_date"].nunique()) if not fut_df.empty else 0
        print(f"[info] futures OI: {len(fut_df)} rows × {fut_days} settle dates", file=sys.stderr)

        # ----- Render -----
        out_path = Path(args.output) if args.output else DEFAULT_OUT_DIR / f"smart_money_{as_of}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        top_sec_row = sector_df.iloc[0]
        top_thm_row = theme_df.iloc[0]
        trust_top = sector_df.sort_values("投信", ascending=False).iloc[0]
        dealer_top = sector_df.sort_values("自營", ascending=False).iloc[0]

        report = f"""# Smart Money 20D 累計分析 — Sector × Theme

**As of:** {as_of} ({len(dates)} 個交易日, {start_date} → {as_of})
**Universe:** {len(per_ticker_cov):,} 檔已覆蓋 (Pilot_Reports 11 sectors / themes/ {len(theme_map)} 主題)
**單位:** 億 TWD (= shares × close / 10⁸)
**資料來源:** trading-timescaledb.institutional_stock
**期貨對照:** futures_oi_daily 覆蓋 {fut_days} 個交易日 ({len(fut_df)} rows)

---

## TL;DR

- **外資 sector top:** {top_sec_row['sector']} 累計 {fmt(top_sec_row['外資'])} 億
- **投信 sector top:** {trust_top['sector']} 累計 {fmt(trust_top['投信'])} 億
- **自營 sector top:** {dealer_top['sector']} 累計 {fmt(dealer_top['自營'])} 億
- **外資 theme top:** {top_thm_row['theme']} 累計 {fmt(top_thm_row['外資'])} 億 ({top_thm_row['n_tickers']} 檔)
{futures_tldr(fut_agg)}

> 三大法人視角分開呈現。同一檔可同時出現在多個 theme,所以 theme 列數合計 ≠ sector 列數合計。

---

## 1. Sector View ({len(sector_df)} sectors)

排序 by 外資 20D 累計。

{render_sector_table(sector_df)}

---

## 2. Theme View ({len(theme_df)} themes)

跨產業的供應鏈視角。同一檔可屬多個 theme。

{render_theme_table(theme_df)}

---

## 3. 三方分歧訊號 (Divergence)

外資與投信反向操作 (一買一賣,各方 |淨額| > 5 億) — 通常代表機構視角不一致,值得深究。

### Sector 級分歧
{render_div_table(sec_div, 'sector')}

### Theme 級分歧
{render_div_table(thm_div, 'theme')}

---

## 4. Top {args.top_tickers} 個股 in 外資 top-3 sectors

"""
        for sec, top in sec_ticker_blocks:
            report += f"\n### {sec}\n\n{render_top_tickers(top)}\n"

        report += f"\n---\n\n## 5. Top {args.top_tickers} 個股 in 外資 top-3 themes\n"
        for thm, top in thm_ticker_blocks:
            report += f"\n### {thm}\n\n{render_top_tickers(top)}\n"

        report += f"""
---

## 6. 期貨對照面板 (TXF / MXF / TMF × 三大法人)

期貨部位是 spot 流向的 macro 配套指標。若 spot 外資賣 + 期貨外資 net OI 空單擴大,訊號互相確認 (避險或方向一致);若反向,則 spot 可能只是換股、非整體看空。

{render_futures_panel(fut_agg, start_date, as_of)}

---

## 7. Verification Log

依 CLAUDE.md 規則 "量化主張必先驗證" — 任何「σ / 罕見 / 極端 / outlier / percentile」用詞前須驗證。

{veri_log}

---

## 8. Methodology & Caveats

- **資料窗口:** 過去 {len(dates)} 個交易日 (純交易日,自動跳過國定假日)
- **單位轉換:** `億 TWD = 法人淨股數 × close_price / 10⁸`
- **OTC 收盤價缺失補強:** institutional_stock.close_price 對 OTC 上櫃 = 0,以 yfinance `.TWO` suffix 補上 (cache: `.cache/otc_close_{as_of}.json`,本輪補 {otc_stats['otc_fetched']} 檔,其中 {otc_stats['otc_zero']} 檔 yfinance 也抓不到 → TWD=0)
- **Sector 對應:** Pilot_Reports/{{Sector}}/{{Ticker}}_*.md 檔名前 4 碼為 ticker,所在資料夾名為 sector
- **Theme 對應:** themes/*.md 內 `**XXXX 公司名**` 形式擷取 ticker
- **多重歸屬:** 一檔可同時屬多個 theme,因此 theme 表合計不可直接相加
- **Sanity check:** 自動驗證 sector 表外資合計 = 個股表外資合計 ({s_total:,.1f} 億)
- **期貨單位:** 口 (lots) — TXF 一口名義價值 ≈ TAIEX × 200 NTD,MXF ≈ TAIEX × 50,TMF ≈ TAIEX × 10。`net_oi` 是當日收盤淨部位 (snapshot);`trade_net 累計` 是窗口內每日 trade_net 加總 (flow)。窗口內期貨日期數可能與 spot 日期數不完全一致 (TAIFEX 公告時間略後於 TWSE)。
- **未涵蓋:** 選擇權未平倉、ETF 申贖、現股當沖明細

*Generated: {as_of} · `scripts/smart_money_analysis.py --as-of {as_of} --window {args.window}`*
"""

        out_path.write_text(report, encoding="utf-8")
        print(f"[ok] wrote {out_path}", file=sys.stderr)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
