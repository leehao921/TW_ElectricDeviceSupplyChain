#!/usr/bin/env python3
"""GEX 狀態機 event-based 監控 (launchd 300s) — Signal Layer + State Controller.

每 5 分鐘: iv_strikes 多到期 (W1/W2/M1) gamma × OI → 複合 GEX/ZG/CW/PW +
IV curve z-score → 狀態機 (MAGNET/EXPANSION/MIXED) → 只在事件發生時推送:
REGIME_FLIP / CW_PROX / PW_PROX / ZG_SHIFT / IV_Z_CROSS (各 30min cooldown)。

紅線: 純訊號層 — 不下單、不觸碰 nautilus 執行體系。輸出為分析標註非交易指令。
Session gate 為數據驅動: iv_strikes 最新列 <10 分鐘才視為盤中 (日/夜盤通用)。
Z-score 誠實標 n: vix_daily 僅 2026-05-27 起 (~60d), 300d 待累積。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
STATE_PATH = REPO / "data" / "gex_regime_state.json"
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")
MULTIPLIER = 50
WALL_PROX_PCT = 0.002       # 距牆 0.2%
ZG_SHIFT_PTS = 100
Z_THRESHOLD = 2.0
COOLDOWN_S = 1800
STALE_S = 600               # iv_strikes 最新列超過 10 分鐘 = 休市


# ------------------------------------------------------------------ pure
def classify_regime(spot, zg, total_gex):
    """MAGNET: spot>ZG 且 GEX>0 (逆勢對沖/壓波動); EXPANSION: spot<ZG 且 GEX<0
    (順勢對沖/放大); 矛盾 → MIXED (誠實標註, 不硬歸類)."""
    if zg is None or total_gex is None:
        return None
    above, positive = spot > zg, total_gex > 0
    if above and positive:
        return "MAGNET"
    if not above and not positive:
        return "EXPANSION"
    return "MIXED"


def vol_scalar(abs_gex, hist_abs: list):
    """|淨GEX| 的歷史分位 → 0-1 部位縮放參考值 (僅輸出數字, 不執行)."""
    if not hist_abs:
        return None
    below = sum(1 for h in hist_abs if h < abs_gex)
    return round(below / len(hist_abs), 2)


def _std(xs: list) -> float:
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0


def z_windows(value: float, history: list, windows=(20, 90, 300)) -> dict:
    """value 對各回看窗的 z-score; 歷史不足時用實際 n 並標註 (誠實原則)."""
    out = {}
    for w in windows:
        seg = history[-w:]
        n = len(seg)
        if n < 5:
            out[f"z{w}"] = {"z": None, "n": n}
            continue
        sd = _std(seg)
        m = sum(seg) / n
        out[f"z{w}"] = {"z": round((value - m) / sd, 2) if sd else None, "n": n}
    return out


def _near_wall(spot, wall):
    return wall is not None and spot and abs(spot - wall) / spot < WALL_PROX_PCT


def detect_events(prev: dict, curr: dict) -> list:
    """(型, 描述) 清單 — 只回報「狀態改變」而非狀態本身 (event-based 核心)."""
    ev = []
    if prev.get("regime") and curr.get("regime") \
            and prev["regime"] != curr["regime"]:
        ev.append(("REGIME_FLIP",
                   f"{prev['regime']} → {curr['regime']} "
                   f"(spot {curr['spot']:,.0f} vs ZG {curr['zg']:,.0f})"))
    for key, wall_key in (("CW_PROX", "cw"), ("PW_PROX", "pw")):
        was = _near_wall(prev.get("spot"), prev.get(wall_key))
        now = _near_wall(curr.get("spot"), curr.get(wall_key))
        if now and not was:
            ev.append((key, f"距 {wall_key.upper()} {curr[wall_key]:,} "
                            f"< {WALL_PROX_PCT:.1%} (spot {curr['spot']:,.0f})"))
    if prev.get("zg") and curr.get("zg") \
            and abs(curr["zg"] - prev["zg"]) > ZG_SHIFT_PTS:
        ev.append(("ZG_SHIFT", f"ZeroGamma {prev['zg']:,.0f} → {curr['zg']:,.0f}"))
    pz, cz = prev.get("z20"), curr.get("z20")
    if pz is not None and cz is not None \
            and abs(pz) < Z_THRESHOLD <= abs(cz):
        ev.append(("IV_Z_CROSS", f"IV z20 {pz:+.1f} → {cz:+.1f} (穿越 ±{Z_THRESHOLD})"))
    return ev


# ------------------------------------------------------------------ data
def market_live(cur) -> bool:
    cur.execute("SELECT extract(epoch FROM now() - max(time)) FROM iv_strikes "
                "WHERE time >= now() - interval '1 day'")
    r = cur.fetchone()
    return r[0] is not None and float(r[0]) < STALE_S


def compute_composite(conn, spot: float) -> dict:
    """前 3 個到期 (W1/W2/M1) 複合 GEX 廊道 → ZG/CW/PW/total."""
    import pandas as pd
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT expiry FROM iv_strikes
                   WHERE time >= now() - interval '1 day'
                     AND expiry > to_char(now(), 'YYYYMMDD') ORDER BY 1 LIMIT 3""")
    expiries = [r[0] for r in cur.fetchall()]
    if not expiries:
        return {}
    strikes = pd.read_sql("""
      SELECT DISTINCT ON (expiry, strike, call_put) expiry, strike, call_put, gamma, iv
      FROM iv_strikes WHERE time >= now() - interval '1 day' AND expiry = ANY(%(e)s)
      ORDER BY expiry, strike, call_put, time DESC""", conn, params={"e": expiries})
    oi = pd.read_sql("""
      SELECT to_char(expiry,'YYYYMMDD') AS expiry, strike, cp, open_interest
      FROM option_oi_daily WHERE underlying='TX'
        AND settle_date=(SELECT max(settle_date) FROM option_oi_daily)
        AND to_char(expiry,'YYYYMMDD') = ANY(%(e)s)""", conn, params={"e": expiries})
    df = strikes.merge(oi, left_on=["expiry", "strike", "call_put"],
                       right_on=["expiry", "strike", "cp"]).dropna(
        subset=["gamma", "open_interest"])
    if df.empty:
        return {}
    df = df[(df.strike > spot - 3000) & (df.strike < spot + 3000)]  # 剔深尾
    sign = df.call_put.map({"C": 1.0, "P": -1.0})
    df = df.assign(gex=df.gamma * df.open_interest * MULTIPLIER * spot * spot * 0.01 * sign)
    by_k = df.groupby("strike").gex.sum().sort_index()
    cum = by_k.cumsum()
    crossings = []
    prev_v = None
    for k, v in cum.items():
        if prev_v is not None and (prev_v < 0) != (v < 0):
            crossings.append(float(k))
        prev_v = v
    zg = min(crossings, key=lambda k: abs(k - spot)) if crossings else None  # 取最近現價的穿越
    coi = df[df.call_put == "C"].groupby("strike").open_interest.sum()
    poi = df[df.call_put == "P"].groupby("strike").open_interest.sum()
    win = lambda s: s[(s.index > spot - 1500) & (s.index < spot + 1500)]  # noqa: E731
    return {"zg": zg, "total_gex": float(by_k.sum()),
            "cw": int(win(coi).idxmax()) if len(win(coi)) else None,
            "pw": int(win(poi).idxmax()) if len(win(poi)) else None,
            "expiries": expiries}


def iv_curve(conn, spot: float) -> list:
    """各到期 ATM IV (現價最近履約價 C/P 均值) → [(expiry, atm_iv%)]."""
    import pandas as pd
    df = pd.read_sql("""
      SELECT DISTINCT ON (expiry, strike, call_put) expiry, strike, call_put, iv
      FROM iv_strikes WHERE time >= now() - interval '1 day'
        AND expiry > to_char(now(), 'YYYYMMDD')
        AND strike BETWEEN %(lo)s AND %(hi)s
      ORDER BY expiry, strike, call_put, time DESC""",
                     conn, params={"lo": spot - 300, "hi": spot + 300})
    out = []
    for exp, g in df.groupby("expiry"):
        g = g.assign(d=(g.strike - spot).abs())
        atm = g[g.d == g.d.min()]
        if len(atm) and atm.iv.notna().any():
            out.append((exp, round(float(atm.iv.mean()) * 100, 1)))
    return sorted(out)[:5]


def front_iv_history(conn) -> list:
    cur = conn.cursor()
    cur.execute("SELECT vix FROM vix_daily WHERE vix IS NOT NULL ORDER BY date")
    return [float(r[0]) for r in cur.fetchall()]


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    import psycopg2
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    if not market_live(cur) and not args.dry_run:
        return 0                                  # 休市靜默

    cur.execute("""SELECT last(close, bucket) FROM ohlcv_1m_txf
                   WHERE symbol='TXF' AND bucket >= now() - interval '3 days'""")
    spot = float(cur.fetchone()[0] or 0)
    comp = compute_composite(conn, spot)
    if not comp:
        print("[warn] no GEX data", file=sys.stderr)
        return 0
    curve = iv_curve(conn, spot)
    hist = front_iv_history(conn)
    front_atm = curve[0][1] if curve else None
    zs = z_windows(front_atm, hist) if front_atm else {}
    z20 = (zs.get("z20") or {}).get("z")
    regime = classify_regime(spot, comp["zg"], comp["total_gex"])

    curr = {"regime": regime, "spot": spot, "zg": comp["zg"],
            "cw": comp["cw"], "pw": comp["pw"], "z20": z20,
            "total_gex": comp["total_gex"],
            "ts": datetime.now().isoformat(timespec="seconds")}
    st = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    prev = st.get("curr", {})
    hist_abs = (st.get("gex_abs_hist") or [])
    scalar = vol_scalar(abs(comp["total_gex"]), hist_abs)
    events = detect_events(prev, curr) if prev else \
        [("BASELINE", f"監控啟動: {regime} · ZG {comp['zg']:,.0f}" if comp['zg'] else "監控啟動")]

    # cooldown 過濾
    now_ts = datetime.now().timestamp()
    cd = st.get("cooldown", {})
    fire = [(t, d) for t, d in events if now_ts - cd.get(t, 0) > COOLDOWN_S]

    zg_txt = f"{comp['zg']:,.0f}" if comp["zg"] else "n/a"
    line = (f"{regime or '?'} · spot {spot:,.0f} · ZG {zg_txt} · "
            f"CW {comp['cw']:,} · PW {comp['pw']:,} · "
            f"GEX {comp['total_gex']/1e8:+,.0f}億/1% (scalar {scalar}) · "
            f"IV前緣 {front_atm}% z20 {z20} · "
            f"curve {' / '.join(f'{e[-4:]}:{v}' for e, v in curve)}")
    print(("[dry] " if args.dry_run else "") + line)
    for t, d in fire:
        print(f"  EVENT {t}: {d}")

    if not args.dry_run:
        # 機器可讀 feed → nautilus agents (每次 live 都更新, 非僅事件時)
        try:
            import redis
            r = redis.Redis()
            r.hset("h:agent:gex_regime", mapping={
                "ts": curr["ts"], "spot": spot,
                "regime": regime or "UNKNOWN",
                "zg": comp["zg"] or "", "cw": comp["cw"] or "",
                "pw": comp["pw"] or "",
                "total_gex": round(comp["total_gex"], 0),
                "vol_scalar": scalar if scalar is not None else "",
                "iv_front_atm": front_atm or "", "iv_z20": z20 if z20 is not None else "",
                "expiries": ",".join(comp["expiries"]),
                "note": "signal-only; consumers must check ts freshness (<600s)"})
        except Exception as e:
            print(f"[warn] agent feed publish failed: {e}", file=sys.stderr)
        for t, _ in fire:
            cd[t] = now_ts
        hist_abs = (hist_abs + [abs(comp["total_gex"])])[-2000:]
        STATE_PATH.write_text(json.dumps(
            {"curr": curr, "cooldown": cd, "gex_abs_hist": hist_abs},
            ensure_ascii=False))
        if fire:
            try:
                import redis
                icons = {"REGIME_FLIP": "🚨", "CW_PROX": "⚡", "PW_PROX": "⚡",
                         "ZG_SHIFT": "↔️", "IV_Z_CROSS": "📈", "BASELINE": "▶️"}
                msg = " | ".join(f"{icons.get(t, '•')}{t}: {d}" for t, d in fire)
                redis.Redis().xadd("claude:inbox", {
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "from": "gex_regime", "topic": "gex-regime",
                    "tags": "gex,regime,event", "as_of": date.today().isoformat(),
                    "msg": f"{msg}\n{line}\n(分析標註·不構成交易指令)"})
            except Exception as e:
                print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
