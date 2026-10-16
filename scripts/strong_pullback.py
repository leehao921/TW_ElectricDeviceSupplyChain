#!/usr/bin/env python3
"""strong_pullback.py — Martin 強勢股整理回測: 日線掃描 + 回測 (plan 2026-10-16).

Step 1  強勢 (21/63/126 日報酬 ≥30% 且全池前 25%) + 整理轉強 (BB squeeze + 低點墊高
        + 站上不下彎的 EMA9/21);頭頭低底底低且壓在下彎 EMA21 下 → 剔除
Step 2  支撐疊合 (EMA21/EMA50/AVWAP/前期 swing high/未補缺口 ≥3 個落在 1.5% 帶內)
        + 站上後第一次回測
Step 3  日線代理觸發: T+1 突破 T 高點進場,停損 T 低點
Step 4  3R 出一半,其餘收盤跌破 EMA9 出 (最長 30 日);成本 0.585% 以 R 扣除

CLI:
    python scripts/strong_pullback.py scan [--as-of YYYY-MM-DD] [--push]
    python scripts/strong_pullback.py backtest [--out analysis/xxx.md]

純訊號層,不下單。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")

MOM_HORIZONS = (21, 63, 126)        # 約 1/3/6 個月
MOM_MIN_RET = 30.0                  # %
MOM_TOP_FRAC = 0.25                 # 全池前 25%
MIN_TURNOVER_20D = 5e7              # 20D 平均成交值 ≥ 0.5 億
BB_BBW_PCT = 30                     # 與 smart_money_analysis.BB_BBW_PCT 同口徑
BB_WINDOW = 60
BB_MIN_SQUEEZE_DAYS = 4             # 前 7 日 ≥4 日擠壓
ANCHOR_LOOKBACK = 40
SWING_K = 5
SWING_LOOKBACK = 120
GAP_LOOKBACK = 60
# Martin 原意 1.5%/3 位疊合; 2025-07→2026-10 回測僅 5~15 事件 (無法評估), v1 放寬到
# 2.5%/2 位 + 觀察名單有效 10 日, 網格結果見 backtest 報告。
ZONE_BAND_PCT = 2.5
ZONE_MIN_MEMBERS = 2
SETUP_WINDOW = 10                   # step1 通過後, 10 個交易日內等回測
LEVEL_MAX_BELOW_PCT = 15.0          # 支撐位離收盤超過 15% 不算
APPROACH_PCT = 3.0                  # 掃描: 收盤離 zone 上緣 ≤3% 列 setup
COST_PCT = 0.585                    # 公定來回: 0.1425%×2 + 證交稅 0.3%


# --------------------------------------------------------------------------- #
# step 1a — 強勢排名 (pure)
# --------------------------------------------------------------------------- #
def momentum_pass(close: pd.DataFrame, min_ret: float = MOM_MIN_RET,
                  top_frac: float = MOM_TOP_FRAC,
                  horizons: tuple[int, ...] = MOM_HORIZONS) -> pd.DataFrame:
    """任一期間報酬 ≥ min_ret% 且該期間排名在全池前 top_frac → True."""
    out = pd.DataFrame(False, index=close.index, columns=close.columns)
    for h in horizons:
        ret = (close / close.shift(h) - 1) * 100
        pct = ret.rank(axis=1, pct=True)
        out |= (ret >= min_ret) & (pct > 1 - top_frac)
    return out


# --------------------------------------------------------------------------- #
# 指標 (pure)
# --------------------------------------------------------------------------- #
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """EMA9/21/50 + BB squeeze flag (BBW ≤ 自身 60 根 30 分位, 前 7 根 ≥4 根)."""
    ind = df.copy()
    for n in (9, 21, 50):
        ind[f"ema{n}"] = ind["Close"].ewm(span=n, adjust=False).mean()
    sma = ind["Close"].rolling(20).mean()
    std = ind["Close"].rolling(20).std(ddof=0)
    ind["bbw"] = 4 * std / sma * 100
    thr = ind["bbw"].rolling(BB_WINDOW, min_periods=30).quantile(BB_BBW_PCT / 100)
    low_bbw = (ind["bbw"] <= thr) & thr.notna()
    ind["squeezed"] = low_bbw.astype(int).shift(1).rolling(7).sum() >= BB_MIN_SQUEEZE_DAYS
    return ind


def anchored_vwap(df: pd.DataFrame, anchor_pos: int) -> pd.Series:
    """自 anchor_pos 起的成交量加權均價 (typical price = (H+L+C)/3); 之前為 NaN."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    pv = (tp * df["Volume"]).iloc[anchor_pos:].cumsum()
    v = df["Volume"].iloc[anchor_pos:].cumsum()
    return (pv / v).reindex(df.index)


def find_anchor(df: pd.DataFrame, lookback: int = ANCHOR_LOOKBACK) -> int:
    """整理區階段高點: 近 lookback 根最高 High 的位置."""
    start = max(0, len(df) - lookback)
    return start + int(np.argmax(df["High"].to_numpy()[start:]))


# --------------------------------------------------------------------------- #
# step 1b — 整理轉強 (pure)
# --------------------------------------------------------------------------- #
def stage1_frame(ind: pd.DataFrame) -> pd.DataFrame:
    """逐日 step-1b 各條件 (向量化, 只用當日以前資料)."""
    recent_low = ind["Low"].rolling(10).min()
    prior_low = ind["Low"].shift(10).rolling(20).min()
    recent_high = ind["High"].rolling(10).max()
    prior_high = ind["High"].shift(10).rolling(20).max()
    f = pd.DataFrame(index=ind.index)
    f["higher_low"] = recent_low > prior_low
    f["squeezed"] = ind["squeezed"].astype(bool)
    f["above"] = (ind["Close"] > ind["ema9"]) & (ind["Close"] > ind["ema21"])
    f["rising"] = (ind["ema9"] >= ind["ema9"].shift(5)) & (ind["ema21"] >= ind["ema21"].shift(5))
    f["downtrend"] = ((recent_high < prior_high) & (recent_low < prior_low)
                      & (ind["Close"] < ind["ema21"]) & (ind["ema21"] < ind["ema21"].shift(5)))
    f["pass"] = (f["higher_low"] & f["squeezed"] & f["above"] & f["rising"] & ~f["downtrend"])
    return f


def setup_active(s1: pd.Series, window: int = SETUP_WINDOW) -> pd.Series:
    """step1 最近 window 根內曾通過 → 仍在觀察名單 (等回測)."""
    return s1.astype(int).rolling(window, min_periods=1).max().astype(bool)


def higher_low(ind: pd.DataFrame) -> bool:
    return bool(stage1_frame(ind)["higher_low"].iloc[-1])


def consolidation_state(ind: pd.DataFrame) -> dict:
    row = stage1_frame(ind).iloc[-1]
    return {k: bool(v) for k, v in row.items()}


# --------------------------------------------------------------------------- #
# step 2 — 支撐位 (pure)
# --------------------------------------------------------------------------- #
def swing_highs(df: pd.DataFrame, k: int = SWING_K) -> pd.Series:
    """左右各 k 根都不高於自己的 High (需右側 k 根已發生)."""
    h = df["High"]
    peak = h.rolling(2 * k + 1, center=True).max()
    return h[(h == peak) & peak.notna()]


def unfilled_gaps(df: pd.DataFrame, lookback: int = GAP_LOOKBACK) -> list[float]:
    """向上跳空 (Low[i] > High[i-1]) 且之後 Low 從未 ≤ High[i-1] → 回傳缺口下緣."""
    sub = df.iloc[-lookback:]
    hi, lo = sub["High"].to_numpy(), sub["Low"].to_numpy()
    out = []
    for i in range(1, len(sub)):
        level = hi[i - 1]
        if lo[i] > level and not (lo[i + 1:] <= level).any():
            out.append(float(level))
    return out


def support_levels(ind: pd.DataFrame) -> dict[str, float]:
    """以最後一根為基準的候選支撐位 (EMA21/EMA50/AVWAP/前期高點/未補缺口)."""
    close = float(ind["Close"].iloc[-1])
    floor = close * (1 - LEVEL_MAX_BELOW_PCT / 100)
    levels = {"ema21": float(ind["ema21"].iloc[-1]), "ema50": float(ind["ema50"].iloc[-1])}
    anchor = find_anchor(ind)
    if anchor < len(ind) - 1:          # 錨在今天 = 沒有整理區
        levels["avwap"] = float(anchored_vwap(ind, anchor).iloc[-1])
    sh = swing_highs(ind.iloc[-SWING_LOOKBACK:])
    below = sh[(sh < close) & (sh >= floor)]
    if len(below):
        levels["prior_high"] = float(below.max())
    gaps = [g for g in unfilled_gaps(ind) if floor <= g < close]
    if gaps:
        levels["gap"] = max(gaps)
    return {k: v for k, v in levels.items() if np.isfinite(v) and floor <= v < close}


def confluence_zone(levels: dict[str, float], close: float,
                    band_pct: float = ZONE_BAND_PCT,
                    min_members: int = ZONE_MIN_MEMBERS) -> dict | None:
    """收盤下方 ≥min_members 個支撐位落在 band_pct% 帶內 → 最靠近股價的那一群."""
    items = sorted((v, k) for k, v in levels.items() if np.isfinite(v) and v < close)
    best = None
    for i in range(len(items)):
        j = i
        while j + 1 < len(items) and (items[j + 1][0] / items[i][0] - 1) * 100 <= band_pct:
            j += 1
        group = items[i:j + 1]
        if len(group) < min_members:
            continue
        cand = {"low": group[0][0], "high": group[-1][0], "members": [k for _, k in group]}
        if best is None or len(group) > len(best["members"]) or (
                len(group) == len(best["members"]) and cand["high"] > best["high"]):
            best = cand
    return best


def is_first_retest(df: pd.DataFrame, zone_low: float, zone_high: float,
                    lookback: int = 30, touch_tol: float = 0.005) -> bool:
    """今日 low 觸 zone 且收盤守住 zone_low,且自最近一次收在 zone 下方之後沒回測過."""
    today = df.iloc[-1]
    if not (today["Low"] <= zone_high * (1 + touch_tol) and today["Close"] >= zone_low):
        return False
    hist = df.iloc[-lookback - 1:-1]
    below = np.flatnonzero(hist["Close"].to_numpy() < zone_low)
    if len(below) == 0:
        return False                   # 視窗內沒有「從下方站上」的過程
    since = hist.iloc[below[-1] + 1:]
    return not (since["Low"] <= zone_high * (1 + touch_tol)).any()


# --------------------------------------------------------------------------- #
# step 3/4 — 交易模擬 (pure)
# --------------------------------------------------------------------------- #
def simulate_trade(df: pd.DataFrame, signal_pos: int, cost_pct: float = COST_PCT,
                   partial_r: float = 3.0, max_hold: int = 30) -> dict | None:
    """T=signal_pos; T+1 突破 T 高點進場 (價=max(開盤, T 高)),停損 T 低點.

    出場: 觸 partial_r 出一半; 其餘收盤 < EMA9 (進場隔日起) 或停損或 max_hold 日。
    跳空開在停損下 → 以開盤價出。進場當日先判停損 (保守)。
    """
    nxt = signal_pos + 1
    if nxt >= len(df):
        return None
    o, h, l, c = (df[col].to_numpy() for col in ("Open", "High", "Low", "Close"))
    ema9 = df["ema9"].to_numpy()
    if h[nxt] <= h[signal_pos]:
        return None
    entry = max(o[nxt], h[signal_pos])
    stop = l[signal_pos]
    risk = entry - stop
    if risk <= 0:
        return None
    target = entry + partial_r * risk

    legs: list[tuple[float, float]] = []   # (weight, exit_px)
    remaining, reason, exit_pos = 1.0, "open", None
    last = min(len(df) - 1, nxt + max_hold)
    for j in range(nxt, last + 1):
        if j > nxt and o[j] <= stop:
            legs.append((remaining, o[j])); remaining, reason = 0.0, "gap_stop"
        elif l[j] <= stop:
            legs.append((remaining, stop)); remaining, reason = 0.0, "stop"
        if remaining == 0:
            exit_pos = j
            break
        if remaining == 1.0 and h[j] >= target:
            px = o[j] if (j > nxt and o[j] >= target) else target
            legs.append((0.5, px)); remaining = 0.5
        if j > nxt and c[j] < ema9[j]:
            legs.append((remaining, c[j])); remaining, reason, exit_pos = 0.0, "ema9", j
            break
    if remaining > 0:
        legs.append((remaining, c[last]))
        exit_pos = last
        reason = "time" if last == nxt + max_hold else "open"

    r_gross = sum(w * (px - entry) / risk for w, px in legs)
    cost_r = cost_pct / 100 * entry / risk
    return {"entry": float(entry), "stop": float(stop), "stop_pct": float(risk / entry * 100),
            "r_gross": float(r_gross), "r_net": float(r_gross - cost_r),
            "exit_reason": reason, "hold_days": int(exit_pos - nxt),
            "entry_date": df.index[nxt]}


def trade_stats(trades: pd.DataFrame) -> dict:
    r = trades["r_net"].dropna()
    if r.empty:
        return {"n": 0}
    return {"n": int(len(r)), "win_rate": float((r > 0).mean()),
            "mean_r": float(r.mean()), "median_r": float(r.median()),
            "total_r": float(r.sum())}


# --------------------------------------------------------------------------- #
# DB glue
# --------------------------------------------------------------------------- #
def load_panel(conn, start: str = "2025-01-01") -> dict[str, pd.DataFrame]:
    px = pd.read_sql(
        """SELECT symbol, (ts AT TIME ZONE 'Asia/Taipei')::date d,
                  open, high, low, close, volume
           FROM stock_daily_ohlcv
           WHERE symbol ~ '^[1-9][0-9]{3}$' AND ts >= %s ORDER BY 1, 2""",
        conn, params=(start,), parse_dates=["d"])  # psycopg2 直連, 同 signal_backtest
    out = {}
    for sym, g in px.groupby("symbol"):
        g = g.set_index("d").sort_index()
        g.index.name = None
        out[sym] = g.rename(columns={"open": "Open", "high": "High", "low": "Low",
                                     "close": "Close", "volume": "Volume"})[
            ["Open", "High", "Low", "Close", "Volume"]].astype(float)
    return out


def _themes():
    try:
        import smart_money_analysis as sm
        return sm.build_theme_map(), sm.build_ticker_name_map()
    except Exception as e:  # noqa: BLE001 — 題材註記非必要
        print(f"[warn] theme map unavailable: {e}", file=sys.stderr)
        return {}, {}


def universe_filters(panel: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    close = pd.DataFrame({s: d["Close"] for s, d in panel.items()})
    turnover = pd.DataFrame({s: d["Close"] * d["Volume"] for s, d in panel.items()})
    liquid = turnover.rolling(20).mean() >= MIN_TURNOVER_20D
    return momentum_pass(close) & liquid, close


def theme_clusters(stage_ok: pd.Series, theme_map: dict[str, set[str]],
                   min_members: int = 3) -> dict[str, list[str]]:
    """同一題材 ≥min_members 檔同時通過 step 1 → {theme: [tickers]}."""
    ok = set(stage_ok[stage_ok].index)
    return {t: sorted(m & ok) for t, m in theme_map.items() if len(m & ok) >= min_members}


# --------------------------------------------------------------------------- #
# scan
# --------------------------------------------------------------------------- #
def scan(as_of: date | None = None) -> str:
    import psycopg2
    conn = psycopg2.connect(**DB)
    try:
        panel = load_panel(conn, "2025-01-01")
    finally:
        conn.close()
    mom, close = universe_filters(panel)
    d = pd.Timestamp(as_of) if as_of else close.index[-1]
    d = close.index[close.index <= d][-1]
    theme_map, name_map = _themes()

    watch, setups, ok = [], [], {}
    for sym, df in panel.items():
        df = df[df.index <= d]
        if len(df) < 130 or df.index[-1] != d:
            ok[sym] = False
            continue
        ind = add_indicators(df)
        s1 = stage1_frame(ind)["pass"] & mom[sym].reindex(ind.index).fillna(False)
        ok[sym] = bool(s1.iloc[-1])
        if not setup_active(s1).iloc[-1]:
            continue
        c = float(ind["Close"].iloc[-1])
        zone = confluence_zone(support_levels(ind), c)
        row = {"sym": sym, "name": name_map.get(sym, ""), "close": c,
               "ret63": (c / float(df["Close"].iloc[-64]) - 1) * 100}
        if zone:
            dist = (c / zone["high"] - 1) * 100
            row.update(zone=zone, dist=dist)
            if dist <= APPROACH_PCT:
                setups.append(row)
                continue
        watch.append(row)

    clusters = theme_clusters(pd.Series(ok), theme_map)
    lines = [f"# 強勢整理回測 scan — {d.date()}", "",
             f"Step1 近 {SETUP_WINDOW} 日通過 {len(watch) + len(setups)} 檔 | 支撐疊合 ≤{APPROACH_PCT}%: {len(setups)} 檔", ""]
    if setups:
        lines += ["## 🎯 Setup (盯分鐘圖: 下探回升 + 突破前K高)", "",
                  "| 代號 | 名稱 | 收盤 | 支撐區 | 疊合 | 距離 | 63D% |", "|---|---|---:|---|---|---:|---:|"]
        for r in sorted(setups, key=lambda r: r["dist"]):
            z = r["zone"]
            lines.append(f"| {r['sym']} | {r['name']} | {r['close']:.2f} | {z['low']:.2f}–{z['high']:.2f} | "
                         f"{'/'.join(z['members'])} | {r['dist']:.1f}% | {r['ret63']:+.0f}% |")
        lines.append("")
    if watch:
        lines += ["## 👀 Step1 觀察 (整理轉強, 尚未接近疊合支撐)", "",
                  " / ".join(f"{r['sym']} {r['name']}" for r in sorted(watch, key=lambda r: -r["ret63"])), ""]
    if clusters:
        lines += ["## 🔥 題材同步 (≥3 檔通過 step 1)", ""]
        lines += [f"- {t}: {', '.join(m)}" for t, m in sorted(clusters.items(), key=lambda x: -len(x[1]))]
        lines.append("")
    lines.append("*日線篩選;進場需分鐘圖觸發。純訊號層,非交易指令。*")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# backtest
# --------------------------------------------------------------------------- #
def find_events(inds: dict[str, pd.DataFrame], mom: pd.DataFrame,
                band_pct: float = ZONE_BAND_PCT, min_members: int = ZONE_MIN_MEMBERS,
                window: int = SETUP_WINDOW) -> pd.DataFrame:
    """逐日 point-in-time: T-1 仍在觀察名單 + 疊合 zone (以 T-1 資料計) → T 第一次回測."""
    rows = []
    for sym, ind in inds.items():
        if len(ind) < 130 or sym not in mom.columns:
            continue
        s1 = stage1_frame(ind)["pass"] & mom[sym].reindex(ind.index).fillna(False)
        for pos in np.flatnonzero(setup_active(s1, window).to_numpy()[:-1]):
            t = pos + 1
            if pos < 130:
                continue
            hist = ind.iloc[:pos + 1]
            zone = confluence_zone(support_levels(hist), float(hist["Close"].iloc[-1]),
                                   band_pct, min_members)
            if zone and is_first_retest(ind.iloc[:t + 1], zone["low"], zone["high"]):
                rows.append({"symbol": sym, "date": ind.index[t], "pos": t,
                             "members": "/".join(zone["members"])})
    return pd.DataFrame(rows)


def evaluate(inds, mom, close, theme_map, band_pct=ZONE_BAND_PCT,
             min_members=ZONE_MIN_MEMBERS, window=SETUP_WINDOW) -> dict:
    import signal_backtest as sb

    events = sb.decluster(find_events(inds, mom, band_pct, min_members, window))
    mkt = {h: ((close.shift(-h) / close - 1) * 100).median(axis=1) for h in (5, 20)}
    trades, fwd, no_trigger = [], {5: [], 20: []}, 0
    for _, e in events.iterrows():
        t = simulate_trade(inds[e["symbol"]], int(e["pos"]))
        if t:
            # 題材同步: 事件前一日同題材 ≥3 檔通過強勢篩選 (只用 step 1a, 避免全池重算 1b)
            prev = close.index[close.index.get_loc(e["date"]) - 1]
            hot = any(e["symbol"] in m for m in theme_clusters(mom.loc[prev], theme_map).values())
            trades.append({**t, "symbol": e["symbol"], "signal_date": e["date"],
                           "hot_theme": hot, "members": e["members"]})
        else:
            no_trigger += 1
        for h in (5, 20):
            r = sb.forward_ret(close, e["symbol"], e["date"], h)
            m = mkt[h].get(e["date"])
            if r is not None and pd.notna(m):
                fwd[h].append({"ret": r, "mkt": m, "date": e["date"]})
    ev_stats = {}
    for h in (5, 20):
        st = sb.event_stats(pd.DataFrame(fwd[h])) if fwd[h] else {"n": 0}
        st["grade"] = sb.grade_daily(st)
        ev_stats[h] = st
    return {"events": events, "trades": pd.DataFrame(trades), "no_trigger": no_trigger,
            "ev_stats": ev_stats}


def _fmt_trades(st: dict) -> str:
    if not st.get("n"):
        return "n=0"
    return (f"n={st['n']} | 勝率 {st['win_rate']:.0%} | 平均 {st['mean_r']:+.2f}R | "
            f"中位 {st['median_r']:+.2f}R | 合計 {st['total_r']:+.1f}R")


def _fmt_event(h: int, st: dict) -> str:
    if not st.get("n"):
        return f"T+{h}: n=0 → {st['grade']}"
    return (f"T+{h}: n={st['n']} 中位 {st['median']:+.2f}% 超額中位 {st['excess_median']:+.2f}% "
            f"beat {st['hit_beat']:.0%} → **{st['grade']}**")


GRID = [(1.5, 3, 1), (1.5, 2, 1), (2.5, 2, 5), (2.5, 2, 10), (2.5, 2, 20), (1.5, 3, 10), (2.5, 3, 10)]


def backtest(out_path: Path) -> str:
    import psycopg2

    conn = psycopg2.connect(**DB)
    try:
        panel = load_panel(conn, "2025-01-01")
    finally:
        conn.close()
    mom, close = universe_filters(panel)
    theme_map, _ = _themes()
    inds = {s: add_indicators(d) for s, d in panel.items() if len(d) >= 130}

    res = evaluate(inds, mom, close, theme_map)
    tr = res["trades"]
    closed = tr[tr["exit_reason"] != "open"] if len(tr) else tr
    lines = [f"# 強勢整理回測 backtest — {date.today()}", "",
             f"資料: stock_daily_ohlcv {close.index[0].date()} → {close.index[-1].date()}, "
             f"{close.shape[1]} 檔 (可評估區間約 2025-07 起)。",
             f"預設: zone 帶寬 {ZONE_BAND_PCT}% / ≥{ZONE_MIN_MEMBERS} 位 / 觀察名單 {SETUP_WINDOW} 日。",
             f"事件 (同股 10 日 de-cluster) {len(res['events'])} → 未觸發 (T+1 沒破 T 高) "
             f"{res['no_trigger']} → 成交 {len(tr)} → 已結束 {len(closed)}", "",
             "## 交易層 (日線代理觸發, 扣成本 0.585% 換算 R)", ""]
    if len(closed):
        sub8 = closed[closed["stop_pct"] <= 8]
        lines += [f"- 停損 ≤8%: {_fmt_trades(trade_stats(sub8))}",
                  f"- 停損 ≤3% (Martin 規格): {_fmt_trades(trade_stats(closed[closed.stop_pct <= 3]))}",
                  f"- 題材同步: {_fmt_trades(trade_stats(sub8[sub8.hot_theme]))}",
                  f"- 非題材同步: {_fmt_trades(trade_stats(sub8[~sub8.hot_theme]))}",
                  f"- 停損距離 10/50/90 分位: "
                  + " / ".join(f"{v:.1f}%" for v in closed['stop_pct'].quantile([.1, .5, .9])),
                  f"- 出場原因: {closed['exit_reason'].value_counts().to_dict()}", "",
                  "### 半年分段 (停損 ≤8%)", ""]
        sub8 = sub8.assign(half=sub8.signal_date.dt.year.astype(str) + "H"
                           + ((sub8.signal_date.dt.month > 6) + 1).astype(str))
        lines += [f"- {hf}: {_fmt_trades(trade_stats(g))}" for hf, g in sub8.groupby("half")]
        lines.append("")
    lines += ["## 事件層 (T 收盤 → T+h, 對同日全池中位)", ""]
    lines += [f"- {_fmt_event(h, res['ev_stats'][h])}" for h in (5, 20)]
    lines += ["", "## 參數網格 (全部列出, 非挑選)", "",
              "| 帶寬 | 位數 | 名單日 | 事件 | 成交(≤8%) | 勝率 | 平均R | T+20 超額中位 | beat | 分級 |",
              "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for band, mm, w in GRID:
        g = evaluate(inds, mom, close, theme_map, band, mm, w)
        t = g["trades"]
        t = t[(t.exit_reason != "open") & (t.stop_pct <= 8)] if len(t) else t
        st, e20 = trade_stats(t) if len(t) else {"n": 0}, g["ev_stats"][20]
        lines.append(
            f"| {band} | {mm} | {w} | {len(g['events'])} | {st['n']} | "
            + (f"{st['win_rate']:.0%} | {st['mean_r']:+.2f} | " if st["n"] else "— | — | ")
            + (f"{e20['excess_median']:+.2f}% | {e20['hit_beat']:.0%} | {e20['grade']} |"
               if e20.get("n") else f"— | — | {e20['grade']} |"))
    lines += ["", "*日線代理觸發 (T+1 破 T 高),停損 T 低;3R 出半、EMA9 追蹤;非交易指令。*"]
    text = "\n".join(lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text + "\n")
    if len(tr):
        tr.to_csv(out_path.with_suffix(".csv"), index=False)
    return text


def push_inbox(msg: str) -> None:
    import subprocess
    from datetime import datetime
    subprocess.run(["redis-cli", "XADD", "claude:inbox", "*",
                    "ts", datetime.now().isoformat(timespec="seconds"),
                    "from", "strong_pullback", "topic", "strong-pullback",
                    "tags", "signal,pullback", "as_of", str(date.today()), "msg", msg],
                   check=True, capture_output=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--as-of", type=date.fromisoformat)
    s.add_argument("--push", action="store_true")
    b = sub.add_parser("backtest")
    b.add_argument("--out", type=Path,
                   default=REPO / "analysis" / f"strong_pullback_backtest_{date.today()}.md")
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        text = scan(a.as_of)
        print(text)
        if a.push:
            push_inbox(text)
    else:
        print(backtest(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
