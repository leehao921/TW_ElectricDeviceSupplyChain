#!/usr/bin/env python3
"""TXF 盤前位置圖 + 亞洲市場地圖 — 每日 08:40 推播 claude:inbox topic=txf-levels.

Architecture: docs/plans/2026-09-06-txf-level-map.md
  - volume profile (ohlcv_1m_txf 近 20 交易日)
  - OI 牆 (option_oi_daily 只取 expiry >= today)
  - GEX flip (subprocess options_quant.py 解析)
  - 夜盤 / 日盤切割
  - 外資 / 投信期貨淨 OI
  - 美股隔夜 (geo_attr loaders.load_yf cache)
  - 亞股 T-1 (asia_index_daily) + FX (fx_daily)
  - --dry-run: 只印，不推 inbox

Usage:
  .venv/bin/python scripts/txf_level_map.py [--dry-run] [--as-of YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytz

# ── 路徑設置 ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.lppls.db import connect  # noqa: E402
from scripts.geo_attr.loaders import load_yf  # noqa: E402

INBOX_STREAM = "claude:inbox"
TPE_TZ = pytz.timezone("Asia/Taipei")
TPE_DAY_CLOSE_HOUR = 13
TPE_DAY_CLOSE_MINUTE = 45


# ══════════════════════════════════════════════════════════════════════════════
# Pure Functions (unit-tested)
# ══════════════════════════════════════════════════════════════════════════════


def split_day_night(bars: pd.DataFrame) -> tuple:
    """bars: DataFrame[bucket(tz-aware UTC), close, volume] 最新交易日相關列。

    回傳 (day_close, night_close, night_chg)。

    Correct cross-midnight logic:
      TXF night session spans midnight: TPE 15:00 → next-morning 05:00.
      Example: Friday night bars (TPE Sat 00:00–04:59) must be classified as
      the FRIDAY night session, not Saturday day session.

    Algorithm:
      1. Find the last bar whose TPE time is in [08:45, 13:45].
         Its TPE calendar date = trading day D.
      2. day_close = last close of bars on date D with TPE time in [08:45, 13:45].
      3. night bars = all bars with UTC bucket > last day bar's UTC bucket
         AND within the night window ending at D+1 05:00 TPE.
      4. night_close = last close of night bars (None if none exist yet).
      5. night_chg = night_close − day_close (None if either is None).
    """
    if bars.empty:
        return None, None, None

    df = bars.copy()
    # Convert bucket to TPE local time
    df["tpe_dt"] = df["bucket"].dt.tz_convert(TPE_TZ)
    df["tpe_time"] = df["tpe_dt"].apply(
        lambda x: x.hour * 60 + x.minute  # minutes since midnight
    )
    df["tpe_date"] = df["tpe_dt"].dt.date

    # Day session boundary in minutes (08:45 = 525, 13:45 = 825)
    DAY_OPEN = 8 * 60 + 45   # 525 minutes
    DAY_CLOSE = TPE_DAY_CLOSE_HOUR * 60 + TPE_DAY_CLOSE_MINUTE  # 825

    # Step 1: find trading day D = date of last bar with TPE time in [08:45, 13:45]
    day_session_mask = (df["tpe_time"] >= DAY_OPEN) & (df["tpe_time"] <= DAY_CLOSE)
    day_session_bars = df[day_session_mask]

    if day_session_bars.empty:
        # No day bars at all — only night bars present
        night_close = float(df["close"].iloc[-1])
        return None, night_close, None

    # Trading day D and day_close
    last_day_bar = day_session_bars.iloc[-1]
    trading_day_D = last_day_bar["tpe_date"]
    day_session_on_D = day_session_bars[day_session_bars["tpe_date"] == trading_day_D]
    day_close = float(day_session_on_D["close"].iloc[-1])

    # Step 2: night bars = all bars after the last day bar on D
    last_day_bar_utc = last_day_bar["bucket"]
    # Night session ends at D+1 05:00 TPE
    night_end_tpe = TPE_TZ.localize(
        dt.datetime.combine(
            trading_day_D + dt.timedelta(days=1),
            dt.time(5, 0)
        )
    )
    night_mask = (
        (df["bucket"] > last_day_bar_utc) &
        (df["tpe_dt"] <= night_end_tpe)
    )
    night_bars = df[night_mask]

    night_close = float(night_bars["close"].iloc[-1]) if not night_bars.empty else None

    if night_close is not None:
        night_chg = night_close - day_close
    else:
        night_chg = None

    return day_close, night_close, night_chg


def volume_profile(bars: pd.DataFrame, bucket_pts: int = 100) -> pd.Series:
    """close//bucket_pts*bucket_pts 分組 volume 加總,回傳降冪 Series。

    bars: DataFrame with columns [close, volume].
    Returns pd.Series indexed by bucket level (float), sorted descending by volume.
    """
    df = bars.copy()
    df["level"] = (df["close"] // bucket_pts * bucket_pts).astype(float)
    profile = df.groupby("level")["volume"].sum()
    return profile.sort_values(ascending=False)


def hvn_lvn(profile: pd.Series, spot: float, top_n: int = 3) -> dict:
    """回傳 dict(hvn=[(level, share), ...前top_n], lvn_above=現價上方最近低量區 level|None,
    lvn_below=下方最近|None)。

    share = vol/total。
    LVN 定義: volume <= 25th percentile of the entire profile.
    lvn_above/below: among levels in LVN set, nearest to spot (above/below).
    """
    if profile.empty:
        return {"hvn": [], "lvn_above": None, "lvn_below": None}

    total = profile.sum()
    if total == 0:
        return {"hvn": [], "lvn_above": None, "lvn_below": None}

    # HVN: top_n levels by volume
    top = profile.nlargest(top_n)
    hvn = [(float(lvl), float(vol) / total) for lvl, vol in top.items()]

    # LVN threshold: 25th percentile of volume values
    lvn_threshold = float(profile.quantile(0.25))

    # LVN candidates: levels with volume <= 25th percentile
    lvn_levels = profile[profile <= lvn_threshold].index.tolist()

    above = [lvl for lvl in lvn_levels if lvl > spot]
    below = [lvl for lvl in lvn_levels if lvl < spot]

    lvn_above = float(min(above)) if above else None   # nearest above = smallest
    lvn_below = float(max(below)) if below else None   # nearest below = largest

    return {"hvn": hvn, "lvn_above": lvn_above, "lvn_below": lvn_below}


def annotate_ladder(rows: list[str], strikes: list[int], profile_20d: pd.Series,
                    lvn_levels: set[int], top_n: int = 5) -> list[str]:
    """在 wall_rows 產出的每列右側加掛 volume-profile 標註。
    strikes[i] 對應 rows[i] 的履約價。
    該價位所屬 100 點 bucket 若為 20 日 HVN 前 top_n → 加 ' ▤{share:.0%}';
    若屬 LVN 集合 → 加 ' ·真空'。
    其餘不動。
    """
    if profile_20d.empty:
        return list(rows)

    total = profile_20d.sum()
    if total == 0:
        return list(rows)

    # HVN: top_n levels by volume
    hvn_set = set(profile_20d.nlargest(top_n).index.tolist())

    result = []
    for i, row in enumerate(rows):
        if i >= len(strikes):
            result.append(row)
            continue
        bucket = float((strikes[i] // 100) * 100)
        if bucket in hvn_set:
            share = profile_20d[bucket] / total
            result.append(row + f" ▤{share:.0%}")
        elif strikes[i] in lvn_levels:
            result.append(row + " ·真空")
        else:
            result.append(row)
    return result


def value_area_note(profile_20d: pd.Series, ladder_lo: int, ladder_hi: int,
                    top_n: int = 5) -> str | None:
    """HVN 前 top_n 全落在梯圖 [lo, hi] 之外時,回傳價值區註記行
    (價格乖離價值區本身是關鍵交易資訊,不可因梯圖範圍而不可見);
    範圍內已有 HVN → None(梯圖已標)。"""
    if profile_20d.empty or profile_20d.sum() == 0:
        return None
    top = profile_20d.nlargest(top_n)
    if any(ladder_lo <= lvl <= ladder_hi for lvl in top.index):
        return None
    total = profile_20d.sum()
    pos = "下方" if top.index.max() < ladder_lo else "上方"
    parts = " ".join(f"{lvl:.0f}▤{v / total:.0%}"
                     for lvl, v in top.head(3).items())
    return f"價值區: {parts} (梯圖{pos})"


def oi_walls(oi: pd.DataFrame, spot: float, n: int = 3,
             expiry_ref: pd.DataFrame | None = None) -> dict:
    """oi: DataFrame[expiry, strike, cp, open_interest] (已濾未到期, 可已用 spot 範圍篩).

    近週選 = min(expiry) in oi;
    月選 = expiry with highest total open_interest sum, determined from
           `expiry_ref` when provided (unfiltered, full-strike dataset) or from
           `oi` itself (fallback).  This avoids spot-range filtering distorting
           which expiry has the most total OI.
    各 expiry 取 put/call 前 n (by open_interest, descending) from `oi`.
    回傳 dict(weekly=dict(call=[(strike, oi)...], put=[...]),
              monthly=dict(call=..., put=...))。

    cp matching is case-insensitive startswith.
    """
    empty_result: dict[str, Any] = {
        "weekly": {"call": [], "put": []},
        "monthly": {"call": [], "put": []},
    }

    if oi.empty:
        return empty_result

    df = oi.copy()
    # Ensure consistent types
    df["cp"] = df["cp"].astype(str).str.upper()

    # Weekly = nearest (min) expiry in the (filtered) oi
    expiries = sorted(df["expiry"].unique())
    if not expiries:
        return empty_result

    weekly_exp = expiries[0]

    # Monthly = expiry with highest total OI.
    # Use expiry_ref (unfiltered) when provided so the spot-range filter does not
    # distort the selection (weekly/thin expiries may have many strikes in range
    # but low aggregate OI overall).
    ref = expiry_ref if expiry_ref is not None and not expiry_ref.empty else df
    ref_norm = ref.copy()
    ref_norm["cp"] = ref_norm["cp"].astype(str).str.upper()
    total_oi_by_exp = ref_norm.groupby("expiry")["open_interest"].sum()
    # Only consider expiries that are also present in the filtered oi
    valid_expiries = set(expiries)
    total_oi_valid = total_oi_by_exp[total_oi_by_exp.index.isin(valid_expiries)]
    monthly_exp = total_oi_valid.idxmax() if not total_oi_valid.empty else weekly_exp

    def _top_n(sub: pd.DataFrame, cp_letter: str, top: int) -> list[tuple[int, int]]:
        cp_rows = sub[sub["cp"].str.startswith(cp_letter)]
        top_rows = cp_rows.nlargest(top, "open_interest")
        return [(int(r["strike"]), int(r["open_interest"]))
                for _, r in top_rows.iterrows()]

    weekly_df = df[df["expiry"] == weekly_exp]
    monthly_df = df[df["expiry"] == monthly_exp]

    return {
        "weekly": {
            "call": _top_n(weekly_df, "C", n),
            "put": _top_n(weekly_df, "P", n),
        },
        "monthly": {
            "call": _top_n(monthly_df, "C", n),
            "put": _top_n(monthly_df, "P", n),
        },
    }


def build_msg(
    as_of: dt.date,
    day_close: float | None,
    night_close: float | None,
    night_chg: float | None,
    walls: dict | None,
    flip: float | None,
    foreign_net: int | None,
    toshin_net: int | None,
    sox: float | None,
    vix: float | None,
    ust10y: float | None,
    brent: float | None,
    dxy: float | None,
    asia: dict | None,
    fx: dict | None,
    # New params (all optional, default None):
    gex_total: float | None = None,
    ladder_rows: list[str] | None = None,  # pre-built annotated ladder lines
) -> str:
    """組裝多行訊息,格式照 plan;任何缺項印 N/A 不 crash。"""

    def _fmt(v: float | None, fmt: str = ".0f", suffix: str = "") -> str:
        if v is None:
            return "N/A"
        return f"{v:{fmt}}{suffix}"

    def _fmt_signed(v: float | None, fmt: str = ".0f", suffix: str = "") -> str:
        if v is None:
            return "N/A"
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:{fmt}}{suffix}"

    # ── Line 1: header ────────────────────────────────────────────────────────
    date_str = f"{as_of.month}/{as_of.day}"
    if night_close is not None and day_close is not None:
        chg_str = _fmt_signed(night_chg, ".0f")
        header = (f"📍 TXF 位置圖 {date_str} | "
                  f"夜盤 {_fmt(night_close)} ({chg_str}, 日盤 {_fmt(day_close)})")
    elif day_close is not None:
        header = f"📍 TXF 位置圖 {date_str} | 日盤收 {_fmt(day_close)} | 夜盤 N/A"
    else:
        header = f"📍 TXF 位置圖 {date_str} | 收盤 N/A"

    # ── Line 2: 外資/投信期淨 OI + GEX ─────────────────────────────────────────
    foreign_str = (f"外資期淨 {_fmt_signed(foreign_net, ',d')}"
                   if foreign_net is not None else "外資期淨 N/A")
    toshin_str = (f"投信 {_fmt_signed(toshin_net, ',d')}"
                  if toshin_net is not None else "投信 N/A")
    flip_str = f"flip {_fmt(flip, '.0f')}" if flip is not None else "flip N/A"
    if gex_total is not None:
        gex_yi = gex_total / 1e8
        gex_str = f"GEX {gex_yi:.0f}億/1% {flip_str}"
    else:
        gex_str = flip_str
    oi_line = f"{foreign_str} | {toshin_str} | {gex_str}"

    # ── Line 3: 月牆 ──────────────────────────────────────────────────────────
    if walls:
        monthly_calls = walls.get("monthly", {}).get("call", [])
        monthly_puts = walls.get("monthly", {}).get("put", [])
        # Sort calls descending by strike, puts descending by strike (highest first)
        monthly_calls_sorted = sorted(monthly_calls, key=lambda x: x[1], reverse=True)[:2]
        monthly_puts_sorted = sorted(monthly_puts, key=lambda x: x[1], reverse=True)[:2]
        # Build display: top2 C by OI sorted descending, top2 P by OI sorted descending
        wall_parts = []
        for s, o in sorted(monthly_calls_sorted, key=lambda x: x[0], reverse=True):
            wall_parts.append(f"{s} C{o}")
        for s, o in sorted(monthly_puts_sorted, key=lambda x: x[0], reverse=True):
            wall_parts.append(f"{s} P{o}")
        monthly_line = "月牆: " + " | ".join(wall_parts) if wall_parts else "月牆: N/A"
    else:
        monthly_line = "月牆: N/A"

    # ── Ladder block ──────────────────────────────────────────────────────────
    if ladder_rows is not None and len(ladder_rows) > 0:
        ladder_block = "```\n" + "\n".join(ladder_rows) + "\n```"
    else:
        ladder_block = "```\n(梯圖無資料)\n```"

    # ── 隔夜美股 ────────────────────────────────────────────────────────────────
    sox_str = _fmt_signed(sox, ".1f", "%") if sox is not None else "SOX N/A"
    vix_str = f"VIX {_fmt(vix, '.1f')}"
    ust_str = f"UST10Y {_fmt(ust10y, '.2f')}"
    brent_str = f"Brent {_fmt(brent, '.1f')}"
    dxy_str = f"DXY {_fmt(dxy, '.1f')}"
    overnight_line = f"🌏 隔夜: SOX {sox_str} {vix_str} {ust_str} {brent_str} {dxy_str}"

    # ── 亞股 T-1 ──────────────────────────────────────────────────────────────
    asia_symbols = ["N225", "KS11", "HSI", "CSI300", "TWII", "NSEI"]
    if asia:
        asia_parts = []
        for sym in asia_symbols:
            v = asia.get(sym)
            asia_parts.append(f"{sym} {_fmt_signed(v, '.1f', '%') if v is not None else 'N/A'}")
        asia_line = "亞股T-1: " + " ".join(asia_parts)
    else:
        asia_line = "亞股T-1: N/A"

    # Append FX
    if fx:
        twd = fx.get("USDTWD")
        jpy = fx.get("USDJPY")
        dxy_fx = fx.get("DXY")
        fx_parts = []
        if twd is not None:
            fx_parts.append(f"USD/TWD {twd:.2f}")
        if jpy is not None:
            fx_parts.append(f"USD/JPY {jpy:.1f}")
        if dxy_fx is not None:
            fx_parts.append(f"DXY {dxy_fx:.1f}")
        if fx_parts:
            asia_line += " | " + " ".join(fx_parts)

    lines = [header, oi_line, monthly_line, ladder_block, overnight_line, asia_line]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# I/O Glue (not unit-tested)
# ══════════════════════════════════════════════════════════════════════════════


def _load_1m_bars(trading_days: int = 20) -> pd.DataFrame:
    """Load ohlcv_1m_txf for the last `trading_days` trading days (UTC buckets)."""
    sql = """
        SELECT bucket, symbol, open, high, low, close, volume
        FROM ohlcv_1m_txf
        WHERE bucket >= NOW() - INTERVAL '35 days'
          AND symbol = 'TXF'
        ORDER BY bucket
    """
    with contextlib.closing(connect()) as conn:
        df = pd.read_sql(sql, conn)
    if df.empty:
        return df
    # Ensure bucket is tz-aware UTC
    if df["bucket"].dt.tz is None:
        df["bucket"] = df["bucket"].dt.tz_localize("UTC")
    else:
        df["bucket"] = df["bucket"].dt.tz_convert("UTC")
    # Get distinct trading days in TPE
    df["tpe_date"] = df["bucket"].dt.tz_convert(TPE_TZ).dt.date
    # Keep last `trading_days` distinct TPE calendar days
    all_dates = sorted(df["tpe_date"].unique())
    keep_dates = set(all_dates[-trading_days:])
    return df[df["tpe_date"].isin(keep_dates)].copy()


def _load_oi(today: dt.date) -> pd.DataFrame:
    """Load option_oi_daily for latest settle_date, expiry >= today."""
    sql = """
        SELECT settle_date, expiry, strike, cp, open_interest
        FROM option_oi_daily
        WHERE underlying = 'TX'
          AND settle_date = (
              SELECT MAX(settle_date) FROM option_oi_daily WHERE underlying = 'TX'
          )
          AND expiry >= %(today)s
        ORDER BY expiry, strike
    """
    with contextlib.closing(connect()) as conn:
        df = pd.read_sql(sql, conn, params={"today": today})
    if not df.empty and "expiry" in df.columns:
        df["expiry"] = pd.to_datetime(df["expiry"]).dt.date
    return df


def _load_futures_oi() -> dict:
    """Load latest futures_oi_daily for 外資 and 投信 net_oi.

    Note: futures_oi_daily uses 'TXF' as underlying (not 'TX').
    """
    sql = """
        SELECT participant_type, net_oi
        FROM futures_oi_daily
        WHERE underlying = 'TXF'
          AND settle_date = (
              SELECT MAX(settle_date) FROM futures_oi_daily WHERE underlying = 'TXF'
          )
    """
    with contextlib.closing(connect()) as conn:
        df = pd.read_sql(sql, conn)
    result: dict[str, int | None] = {"外資": None, "投信": None}
    for _, row in df.iterrows():
        pt = str(row["participant_type"]).strip()
        if pt in result:
            result[pt] = int(row["net_oi"])
    return result


def _load_asia_index() -> dict:
    """Load asia_index_daily last two rows per symbol → 1d % change."""
    sql = """
        SELECT ts, symbol, close
        FROM asia_index_daily
        WHERE symbol = ANY(%(syms)s)
          AND ts >= CURRENT_DATE - INTERVAL '10 days'
        ORDER BY symbol, ts
    """
    symbols = ["N225", "KS11", "HSI", "CSI300", "TWII", "NSEI"]
    with contextlib.closing(connect()) as conn:
        df = pd.read_sql(sql, conn, params={"syms": symbols})
    if df.empty:
        return {}
    result: dict[str, float | None] = {}
    for sym in symbols:
        sub = df[df["symbol"] == sym].sort_values("ts")
        if len(sub) >= 2:
            prev = float(sub["close"].iloc[-2])
            last = float(sub["close"].iloc[-1])
            result[sym] = (last / prev - 1) * 100 if prev != 0 else None
        else:
            result[sym] = None
    return result


def _load_fx() -> dict:
    """Load fx_daily most recent close for USDTWD/USDJPY/DXY."""
    sql = """
        SELECT pair, close
        FROM fx_daily
        WHERE pair = ANY(%(pairs)s)
          AND ts = (SELECT MAX(ts) FROM fx_daily WHERE pair = ANY(%(pairs)s))
    """
    pairs = ["USDTWD", "USDJPY", "DXY"]
    with contextlib.closing(connect()) as conn:
        df = pd.read_sql(sql, conn, params={"pairs": pairs})
    result: dict[str, float | None] = {}
    for _, row in df.iterrows():
        result[str(row["pair"])] = float(row["close"])
    return result


def _get_gex(date: dt.date, spot: float) -> tuple[float | None, float | None, str | None]:
    """Return (total_gex, flip, zone) using ascii_dashboard.compute_gex.
    Falls back gracefully if import or DB fails.
    """
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        import psycopg2
        from ascii_dashboard import compute_gex, DB
        conn = psycopg2.connect(**DB)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""SELECT min(expiry) FROM option_oi_daily
                       WHERE underlying='TX' AND settle_date=(SELECT max(settle_date)
                       FROM option_oi_daily WHERE underlying='TX') AND expiry >= %s""", (date,))
        row = cur.fetchone()
        if row is None or row[0] is None:
            conn.close()
            return None, None, None
        front = row[0]
        total_gex, flip, zone = compute_gex(conn, spot, front)
        conn.close()
        return total_gex, flip, zone
    except Exception as exc:
        print(f"[warn] txf-level-map: _get_gex error: {exc}", file=sys.stderr)
        return None, None, None


def _load_us_overnight() -> dict:
    """Load US overnight data via geo_attr loaders.load_yf."""
    result: dict[str, float | None] = {
        "sox": None, "vix": None, "ust10y": None, "brent": None, "dxy": None,
    }
    try:
        sox_s = load_yf("^SOX", "sox_daily")
        if len(sox_s) >= 2:
            prev, last = float(sox_s.iloc[-2]), float(sox_s.iloc[-1])
            result["sox"] = (last / prev - 1) * 100 if prev != 0 else None
    except Exception as e:
        print(f"[warn] txf-level-map: SOX load error: {e}", file=sys.stderr)

    try:
        vix_s = load_yf("^VIX", "usvix_daily")
        if len(vix_s) >= 1:
            result["vix"] = float(vix_s.iloc[-1])
    except Exception as e:
        print(f"[warn] txf-level-map: VIX load error: {e}", file=sys.stderr)

    try:
        tnx_s = load_yf("^TNX", "ust10y_daily")
        if len(tnx_s) >= 1:
            result["ust10y"] = float(tnx_s.iloc[-1])
    except Exception as e:
        print(f"[warn] txf-level-map: TNX load error: {e}", file=sys.stderr)

    try:
        brent_s = load_yf("BZ=F", "brent_daily")
        if len(brent_s) >= 1:
            result["brent"] = float(brent_s.iloc[-1])
    except Exception as e:
        print(f"[warn] txf-level-map: Brent load error: {e}", file=sys.stderr)

    try:
        dxy_s = load_yf("DX-Y.NYB", "dxy_daily")
        if len(dxy_s) >= 1:
            result["dxy"] = float(dxy_s.iloc[-1])
    except Exception as e:
        print(f"[warn] txf-level-map: DXY load error: {e}", file=sys.stderr)

    return result


def _push_inbox(message: str, as_of: dt.date) -> bool:
    """Push to claude:inbox via redis-cli subprocess. Fail-soft."""
    import datetime as _datetime
    now_iso = _datetime.datetime.now().astimezone().isoformat()
    fields = [
        "ts", now_iso,
        "from", "txf-level-map",
        "topic", "txf-levels",
        "tags", "txf,levels,oi,gex,overnight",
        "as_of", as_of.isoformat(),
        "msg", message,
    ]
    host = os.environ.get("REDIS_HOST", "localhost")
    port = os.environ.get("REDIS_PORT", "6379")
    cmd = ["redis-cli", "-h", host, "-p", port, "XADD", INBOX_STREAM, "*", *fields]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"[warn] txf-level-map XADD failed: {result.stderr.strip()}", file=sys.stderr)
            return False
        print(f"[info] txf-level-map XADD ok, id={result.stdout.strip()}", file=sys.stderr)
        return True
    except Exception as exc:
        print(f"[warn] txf-level-map inbox push error: {exc}", file=sys.stderr)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TXF 盤前位置圖推播")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print only — no inbox push")
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today)")
    args = ap.parse_args(argv)

    today = (dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today())
    print(f"[info] txf-level-map as_of={today}", file=sys.stderr)

    # 1. 1m bars → split day/night + volume profile
    print("[info] loading 1m bars …", file=sys.stderr)
    try:
        bars = _load_1m_bars(trading_days=20)
    except Exception as e:
        print(f"[warn] 1m bars load error: {e}", file=sys.stderr)
        bars = pd.DataFrame()

    day_close: float | None = None
    night_close: float | None = None
    night_chg: float | None = None
    spot: float | None = None

    if not bars.empty:
        # Pass the last 2 TPE calendar days to split_day_night so it can find
        # Friday day bars even when the most recent bar is Saturday morning
        # (post-midnight night session).  split_day_night internally anchors on
        # the last bar whose TPE time is in [08:45, 13:45].
        all_dates = sorted(bars["tpe_date"].unique())
        session_dates = set(all_dates[-2:])  # last 2 calendar days
        latest_bars = bars[bars["tpe_date"].isin(session_dates)].copy()
        day_close, night_close, night_chg = split_day_night(latest_bars)
        spot = night_close if night_close is not None else day_close
        print(f"[info] day={day_close} night={night_close} chg={night_chg}", file=sys.stderr)

        # Volume profile: all 20d bars
        profile = volume_profile(bars, bucket_pts=100)
        print(f"[info] volume profile buckets={len(profile)}", file=sys.stderr)
    else:
        profile = pd.Series(dtype=float)
        print("[warn] no 1m bars found", file=sys.stderr)

    # HVN/LVN
    hvn_result: dict | None = None
    if not profile.empty and spot is not None:
        hvn_result = hvn_lvn(profile, spot=spot, top_n=3)
        print(f"[info] hvn={hvn_result['hvn'][:2]}... lvn_above={hvn_result['lvn_above']} lvn_below={hvn_result['lvn_below']}", file=sys.stderr)

    # 2. OI walls
    print("[info] loading OI walls …", file=sys.stderr)
    try:
        oi_df = _load_oi(today)
        print(f"[info] OI rows={len(oi_df)}", file=sys.stderr)
    except Exception as e:
        print(f"[warn] OI load error: {e}", file=sys.stderr)
        oi_df = pd.DataFrame()

    walls: dict | None = None
    if not oi_df.empty and spot is not None:
        # Filter ±2500 from spot for wall display, but pass full oi_df as
        # expiry_ref so monthly selection uses unfiltered total OI (avoids
        # thin near-expiry inflating OI sum within the narrow price range).
        oi_filtered = oi_df[
            (oi_df["strike"] >= spot - 2500) &
            (oi_df["strike"] <= spot + 2500)
        ].copy()
        walls = oi_walls(oi_filtered, spot=spot, n=3, expiry_ref=oi_df)
    elif not oi_df.empty:
        walls = oi_walls(oi_df, spot=47000.0, n=3)  # fallback spot

    # 3. GEX (T-1) — now uses compute_gex via _get_gex
    t1 = today - dt.timedelta(days=1)
    # Skip weekends for T-1
    while t1.weekday() >= 5:
        t1 -= dt.timedelta(days=1)
    print(f"[info] fetching GEX for T-1={t1} …", file=sys.stderr)
    total_gex, flip, zone = _get_gex(t1, spot or 47000.0)
    print(f"[info] total_gex={total_gex} flip={flip} zone={zone}", file=sys.stderr)

    # 3b. Build near-week ladder
    ladder_rows: list[str] | None = None
    try:
        scripts_dir = str(Path(__file__).resolve().parent)
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from ascii_dashboard import wall_rows as _wall_rows, STEP as _STEP, SPAN as _SPAN
        if spot is not None and not oi_df.empty:
            weekly_expiries = sorted(oi_df["expiry"].unique())
            if weekly_expiries:
                near_exp = weekly_expiries[0]
                near_df = oi_df[oi_df["expiry"] == near_exp]
                # Build oi dict for wall_rows: {strike: {P: oi, C: oi}}
                oi_dict: dict[int, dict] = {}
                for _, row_r in near_df.iterrows():
                    k = int(row_r["strike"])
                    if abs(k - spot) <= _SPAN and k % _STEP == 0:
                        oi_dict.setdefault(k, {})[str(row_r["cp"])[0].upper()] = int(row_r["open_interest"])
                if oi_dict:
                    raw_rows = _wall_rows(oi_dict, spot, zg=flip)
                    strikes_list = sorted(oi_dict.keys(), reverse=True)
                    # Build LVN set from 25th percentile of profile
                    lvn_set: set[int] = set()
                    if not profile.empty:
                        lvn_threshold = float(profile.quantile(0.25))
                        lvn_set = {int(k) for k in profile[profile <= lvn_threshold].index}
                    ladder_rows = annotate_ladder(raw_rows, strikes_list, profile, lvn_set, top_n=5)
                    note = value_area_note(profile, min(strikes_list), max(strikes_list))
                    if note:
                        ladder_rows.append(note)
                    print(f"[info] ladder built: {len(ladder_rows)} rows", file=sys.stderr)
    except Exception as e:
        print(f"[warn] ladder build error: {e}", file=sys.stderr)

    # 4. Futures OI
    print("[info] loading futures OI …", file=sys.stderr)
    try:
        futures_oi = _load_futures_oi()
        foreign_net = futures_oi.get("外資")
        toshin_net = futures_oi.get("投信")
        print(f"[info] 外資={foreign_net} 投信={toshin_net}", file=sys.stderr)
    except Exception as e:
        print(f"[warn] futures OI load error: {e}", file=sys.stderr)
        foreign_net = None
        toshin_net = None

    # 5. US overnight
    print("[info] loading US overnight …", file=sys.stderr)
    us = _load_us_overnight()

    # 6. Asia + FX
    print("[info] loading Asia index + FX …", file=sys.stderr)
    try:
        asia = _load_asia_index()
    except Exception as e:
        print(f"[warn] Asia index load error: {e}", file=sys.stderr)
        asia = {}

    try:
        fx = _load_fx()
    except Exception as e:
        print(f"[warn] FX load error: {e}", file=sys.stderr)
        fx = {}

    # 7. Build message
    msg = build_msg(
        as_of=today,
        day_close=day_close,
        night_close=night_close,
        night_chg=night_chg,
        walls=walls,
        flip=flip,
        foreign_net=foreign_net,
        toshin_net=toshin_net,
        sox=us.get("sox"),
        vix=us.get("vix"),
        ust10y=us.get("ust10y"),
        brent=us.get("brent"),
        dxy=us.get("dxy"),
        asia=asia if asia else None,
        fx=fx if fx else None,
        gex_total=total_gex,
        ladder_rows=ladder_rows,
    )

    print("─" * 70)
    print(msg)
    print("─" * 70)

    if args.dry_run:
        print("[info] dry-run: skipping inbox push", file=sys.stderr)
        return 0

    _push_inbox(msg, today)
    return 0


if __name__ == "__main__":
    sys.exit(main())
