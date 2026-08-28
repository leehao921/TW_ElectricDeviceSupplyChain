#!/usr/bin/env python3
"""每日市場級訊號掃描 (17:50) — 今日多方/空方名單 + T+N 自我校驗追蹤.

名單家族與分級以 docs/signal_registry.md 為準 (2026-08-27 驗證後):
- 空方: S2v2 投降/陰跌型 (margin×volr, 最強候選) · S1 處置解除賣超 (VALIDATED)
- 過熱觀察: S3 乖離 98pct — 驗證顯示牛市為動能非反轉, 僅 2026H2 型 regime 供空方
- 多方: L1 處置解除買超 (VALIDATED) · L4 竭盡候選 (NO-EDGE — 僅供左側 confluence)
名單股自動記 T+5/T+20 (state), 命中統計進週報。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
STATE_PATH = REPO / "data" / "signal_scan_state.json"
HISTORY_PATH = REPO / "data" / "signal_scan_history.json"
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")
MAX_PER_LIST = 8


def scan_margin_volume(conn, as_of) -> tuple[list, list]:
    """S2v2: 融資急減 bot10% × 量能分型 → (投降型, 陰跌型)."""
    df = pd.read_sql("""
      WITH last2 AS (SELECT DISTINCT date FROM margin_daily ORDER BY date DESC LIMIT 1)
      SELECT m.symbol, m.fin_balance, m.fin_prev FROM margin_daily m JOIN last2 ON last2.date=m.date
      WHERE m.symbol ~ '^[1-9][0-9]{3}$' AND m.fin_prev >= 500 AND m.fin_balance IS NOT NULL""", conn)
    if df.empty:
        return [], []
    df["g"] = (df.fin_balance - df.fin_prev) / df.fin_prev
    px = pd.read_sql("""SELECT symbol, ts::date d, close, volume FROM stock_daily_ohlcv
                        WHERE ts >= now() - interval '45 days' ORDER BY 1,2""",
                     conn, parse_dates=["d"])
    wv = px.pivot(index="d", columns="symbol", values="volume")
    volr = (wv / wv.rolling(20).mean()).iloc[-1]
    df = df.set_index("symbol")
    df["volr"] = volr.reindex(df.index)
    q = df.g.rank(pct=True)
    cap = df[(q <= 0.1) & (df.volr > 2)].sort_values("g")
    thin = df[(q <= 0.1) & (df.volr < 0.8)].sort_values("g")
    fmt = lambda d0: [(s, f"融資{r.g*100:+.1f}% volr{r.volr:.1f}") for s, r in d0.head(MAX_PER_LIST).iterrows()]  # noqa: E731
    return fmt(cap), fmt(thin)


def scan_disposition(as_of) -> tuple[list, list]:
    """S1/L1: 3 日內解除的處置股按進場前外資 20D 分邊."""
    st = json.loads((REPO / "data" / "disposition_tracking_state.json").read_text()) \
        if (REPO / "data" / "disposition_tracking_state.json").exists() else {}
    longs, shorts = [], []
    for sym, e in st.get("tracked", {}).items():
        end = e.get("disp_end")
        if not end or e.get("release_date"):
            continue
        days = (date.fromisoformat(end) - date.fromisoformat(as_of)).days
        if 0 <= days <= 3:
            f20 = e.get("foreign_20d_at_enter") or 0
            item = (sym, f"解除{end} 外資20D{f20:+.1f}億")
            (longs if f20 > 0 else shorts).append(item)
    return longs[:MAX_PER_LIST], shorts[:MAX_PER_LIST]


def scan_overheat(conn) -> list:
    """S3 過熱觀察 (regime 條件型): 乖離 vs 自身 252 日 98pct — 僅觀察名單."""
    px = pd.read_sql("""SELECT symbol, ts::date d, close FROM stock_daily_ohlcv
                        WHERE symbol ~ '^[1-9][0-9]{3}$' ORDER BY 1,2""",
                     conn, parse_dates=["d"])
    close = px.pivot(index="d", columns="symbol", values="close")
    dev = close / close.rolling(20).mean() - 1
    if len(dev) < 260:
        return []
    thr = dev.iloc[:-1].rolling(252, min_periods=252).quantile(0.98).iloc[-1]
    today = dev.iloc[-1]
    hot = today[(today > thr) & thr.notna()].sort_values(ascending=False)
    return [(s, f"乖離{v*100:+.1f}%") for s, v in hot.head(MAX_PER_LIST).items()]


def classify_fear_greed(dev20, dfin_5d, dshort_5d, dsbl_5d) -> tuple:
    """別人恐懼我貪婪: 恐懼區=價弱+空壓結構(左側買點), 貪婪區=過熱+籌碼擁擠(收割區).

    恐懼 ≠ 單純下跌 — 要有人在空它 (借券/融券增或散戶融資投降) 才構成錯價候選。
    貪婪 ≠ 單純上漲 — 要有擁擠腿 (融資追價或法人借券對沖增) 才構成收割訊號。
    """
    if dev20 is None:
        return None, ""
    legs = []
    if dev20 <= -0.05:
        if (dsbl_5d or 0) > 0:
            legs.append(f"借券+{dsbl_5d/1e3:,.0f}千股")
        if (dshort_5d or 0) > 0:
            legs.append(f"融券+{dshort_5d:,.0f}張")
        if (dfin_5d or 0) < 0:
            legs.append(f"融資{dfin_5d:,.0f}張")
        if legs:
            return "fear", f"乖離{dev20*100:+.1f}% · " + "/".join(legs)
    elif dev20 >= 0.10:
        if (dfin_5d or 0) > 0:
            legs.append(f"融資+{dfin_5d:,.0f}張")
        if (dsbl_5d or 0) > 0:
            legs.append(f"借券+{dsbl_5d/1e3:,.0f}千股")
        if legs:
            return "greed", f"乖離{dev20*100:+.1f}% · " + "/".join(legs)
    return None, ""


def watch_universe() -> list:
    """恐懼/貪婪儀表的掃描池: 持股 + 買入清單 + position-watch 觸發標的."""
    syms = set()
    for fname, extract in (
        ("portfolio_holdings.json", lambda d: [h.get("ticker") for h in d.get("holdings", [])]),
        ("buy_list_state.json", lambda d: [p.get("ticker") for p in d.get("picks", [])]),
        ("position_triggers.json", lambda d: [t.get("symbol") for t in d.get("triggers", [])]),
    ):
        f = REPO / "data" / fname
        if not f.exists():
            continue
        try:
            for s in extract(json.loads(f.read_text())):
                s = str(s or "")
                if len(s) == 4 and s.isdigit() and s[0] != "0":  # 排除 ETF (00xxx)
                    syms.add(s)
        except Exception:
            continue
    return sorted(syms)


def scan_fear_greed(conn, symbols: list) -> tuple[list, list]:
    """持股+觀察池逐檔 恐懼(左側買點候選)/貪婪(收割區) 標註."""
    if not symbols:
        return [], []
    df = pd.read_sql("""
      WITH d5 AS (SELECT DISTINCT date FROM margin_daily ORDER BY date DESC LIMIT 5)
      SELECT symbol,
             max(fin_balance) FILTER (WHERE date=(SELECT max(date) FROM d5))
               - max(fin_balance) FILTER (WHERE date=(SELECT min(date) FROM d5)) AS dfin,
             max(short_balance) FILTER (WHERE date=(SELECT max(date) FROM d5))
               - max(short_balance) FILTER (WHERE date=(SELECT min(date) FROM d5)) AS dshort,
             max(sbl_balance) FILTER (WHERE date=(SELECT max(date) FROM d5))
               - max(sbl_balance) FILTER (WHERE date=(SELECT min(date) FROM d5)) AS dsbl
      FROM margin_daily WHERE date IN (SELECT date FROM d5) AND symbol = ANY(%(syms)s)
      GROUP BY symbol""", conn, params={"syms": symbols}).set_index("symbol")
    px = pd.read_sql("""SELECT symbol, ts::date d, close FROM stock_daily_ohlcv
                        WHERE ts >= now() - interval '45 days' AND symbol = ANY(%(syms)s)
                        ORDER BY 1,2""", conn, params={"syms": symbols}, parse_dates=["d"])
    close = px.pivot(index="d", columns="symbol", values="close")
    dev = (close / close.rolling(20).mean() - 1).iloc[-1]
    fear, greed = [], []
    for sym in symbols:
        m = df.loc[sym] if sym in df.index else None
        zone, desc = classify_fear_greed(
            dev.get(sym),
            float(m.dfin) if m is not None and pd.notna(m.dfin) else 0,
            float(m.dshort) if m is not None and pd.notna(m.dshort) else 0,
            float(m.dsbl) if m is not None and pd.notna(m.dsbl) else 0)
        if zone == "fear":
            fear.append((sym, desc))
        elif zone == "greed":
            greed.append((sym, desc))
    return fear, greed


def update_tracking(state: dict, listed: dict, as_of: str, close_fn, nth_fn) -> list:
    """名單股 T+5/T+20 追蹤 (沿用 warrant tracker 語意)."""
    tracked = state.setdefault("tracked", {})
    for family, items in listed.items():
        for sym, _ in items:
            key = f"{family}:{sym}:{as_of}"
            if any(k.startswith(f"{family}:{sym}:") and
                   (date.fromisoformat(as_of) - date.fromisoformat(k.split(":")[2])).days < 10
                   for k in tracked):
                continue
            c = close_fn(sym, as_of)
            if c:
                tracked[key] = {"family": family, "symbol": sym, "enter_date": as_of,
                                "enter_close": c, "post": {"t5": None, "t20": None}}
    graduated = []
    for key, e in list(tracked.items()):
        if e["enter_date"] == as_of:
            continue
        for n, k in ((5, "t5"), (20, "t20")):
            if e["post"][k] is None:
                px = nth_fn(e["symbol"], e["enter_date"], n)
                if px:
                    e["post"][k] = round((px / e["enter_close"] - 1) * 100, 2)
        if e["post"]["t20"] is not None:
            graduated.append(e)
            del tracked[key]
    return graduated


def main() -> int:
    import psycopg2
    from warrant_flow_rank import load_labels
    from disposition_daily_fetch import _nth_close_after
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    as_of = date.today().isoformat()
    labels = load_labels()
    lab = lambda s: f"{s} {labels[s]['name']}" if s in labels and labels[s].get("name") else s  # noqa: E731

    cap, thin = scan_margin_volume(conn, as_of)
    disp_l, disp_s = scan_disposition(as_of)
    hot = scan_overheat(conn)
    fear, greed = scan_fear_greed(conn, watch_universe())

    def close_fn(sym, d):
        with conn.cursor() as cur:
            cur.execute("""SELECT close FROM stock_daily_ohlcv WHERE symbol=%s AND ts::date<=%s
                           ORDER BY ts DESC LIMIT 1""", (sym, d))
            r = cur.fetchone()
        return float(r[0]) if r and r[0] else None

    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {"tracked": {}}
    history = json.loads(HISTORY_PATH.read_text()) if HISTORY_PATH.exists() else []
    listed = {"S2v2_cap": cap, "S2v2_thin": thin, "S1_disp": disp_s, "L1_disp": disp_l}
    graduated = update_tracking(state, listed, as_of,
                                close_fn, lambda s, d, n: _nth_close_after(conn, s, d, n))
    history.extend(graduated)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2))

    def sec(title, items, note=""):
        if not items:
            return [f"### {title}", "（今日無）", ""]
        return [f"### {title}{note}", *[f"- **{lab(s)}** {d}" for s, d in items], ""]

    lines = [f"# 每日訊號掃描 {as_of}", "",
             "分級依 docs/signal_registry.md（2026-08-27 系統性驗證後）", "",
             "## 空方名單", ""]
    lines += sec("S2v2 投降型（融資急減×爆量）", cap, " — 最強空候選（-2.16%/5D 初測）")
    lines += sec("S2v2 陰跌型（融資急減×縮量）", thin, " — -1.84%/5D 初測")
    lines += sec("S1 即將解除·外資賣超（VALIDATED）", disp_s)
    lines += ["## 多方名單", ""]
    lines += sec("L1 即將解除·外資買超（VALIDATED）", disp_l)
    lines += ["## 過熱觀察（S3 — regime 條件型，牛市=動能勿逕空）", ""]
    lines += sec("乖離 98 分位", hot)
    lines += ["## 恐懼/貪婪儀表（持股+觀察池 — 別人恐懼我貪婪）", ""]
    lines += sec("😱 恐懼區（價弱+空壓 = 左側買點候選，需疊基本面確認）", fear)
    lines += sec("🤑 貪婪區（過熱+籌碼擁擠 = 收割區候選）", greed)
    done_t5 = [h for h in history if h["post"].get("t5") is not None]
    lines += ["## 名單自我校驗（畢業樣本）", "",
              f"- 累積 {len(history)} 筆；t5 有值 {len(done_t5)} 筆（命中統計見週五總帳）", "",
              "*源: signal_scan.py 17:50 · 不構成交易指令*"]
    md = "\n".join(lines)
    out = REPO / "analysis" / f"signal_scan_{as_of}.md"
    out.write_text(md)
    print(md[:1200])
    try:
        import redis
        n_short = len(cap) + len(thin) + len(disp_s)
        n_long = len(disp_l)
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "signal_scan", "topic": "signal-scan",
            "tags": "signals,daily-scan", "as_of": as_of,
            "msg": f"訊號掃描 {as_of}: 空方 {n_short} 檔 (投降{len(cap)}/陰跌{len(thin)}/處置賣超{len(disp_s)}) · "
                   f"多方 {n_long} 檔 (處置買超) · 過熱觀察 {len(hot)} 檔 · "
                   f"恐懼區 {len(fear)} / 貪婪區 {len(greed)} (持股池)",
            "report_path": f"analysis/{out.name}"})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
