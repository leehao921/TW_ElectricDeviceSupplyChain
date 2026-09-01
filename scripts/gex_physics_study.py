#!/usr/bin/env python3
"""GEX 物理現象檢定 — 驗證造市商對沖行為是否真的改變 TXF 價格分佈.

三檢定 (2026-09-01 spec):
1. Regime Switch: 依日開盤 ZG 分組 (S>ZG vs S<ZG), 比較 T+15/T+60 分鐘前瞻 RV
   — 日級配對 (同日兩態都出現才配對) + sign test, 控制跨日波動 regime 差異
2. Wall Pinning: 價格由下方進入 [CW-0.2%, CW) 之事件 → T+5/T+15 反轉勝率 vs 50%
   (PW 鏡像); binomial sign test
3. Fat-tail Breakout: 收盤價穿越牆外站穩 ≥3 分鐘 → 之後 60 分鐘單向延伸分佈
   (mean vs median / p90 / 勝率與盈虧比)

數據: ohlcv_1m_txf 日盤 (09:00-13:30) 2026-04-24 起 97 日;
ZG 需 gamma (iv_strikes 6/2 起 ~60 日); CW/PW 只需 OI(D-1) → 全 97 日。
日級靜態水位: ZG/CW/PW 以 D 日 09:00-09:30 gamma snapshot × D-1 結算 OI 計算,
與盤中 5min 動態版口徑不同 — 檢定的是「開盤水位是否約束全日行為」。
"""
from __future__ import annotations

import math
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")
MULTIPLIER = 50
ANNUALIZE = math.sqrt(252 * 270)      # 日盤 270 根 1-min bar


# ------------------------------------------------------------------ pure
def fwd_rv(closes: list, i: int, n: int):
    """bar i 之後 n 根 1-min log return 的年化 std; 不足 n → None."""
    seg = closes[i:i + n + 1]
    if len(seg) < n + 1:
        return None
    rets = [math.log(seg[j + 1] / seg[j]) for j in range(n)]
    m = sum(rets) / n
    var = sum((r - m) ** 2 for r in rets) / (n - 1)
    return math.sqrt(var) * ANNUALIZE


def wall_touch_events(px: list, wall: float, side: str, zone_pct=0.002,
                      lookback=5, decluster_bars=30) -> list:
    """進入牆前緣區的事件 index。CW: highs 由下進 [wall(1-z), wall);
    PW: lows 由上進 (wall, wall(1+z)] 且未跌破."""
    if side == "CW":
        lo, hi = wall * (1 - zone_pct), wall
        in_zone = lambda x: lo <= x < hi          # noqa: E731
        was_out = lambda x: x < lo                # noqa: E731
    else:
        lo, hi = wall, wall * (1 + zone_pct)
        in_zone = lambda x: lo < x <= hi          # noqa: E731
        was_out = lambda x: x > hi                # noqa: E731
    ev, last = [], -10 ** 9
    for i in range(lookback, len(px)):
        if in_zone(px[i]) and all(was_out(px[j]) for j in range(i - lookback, i)) \
                and i - last >= decluster_bars:
            ev.append(i)
            last = i
    return ev


def breakout_events(closes: list, wall: float, side: str, hold_bars=3,
                    decluster_bars=30) -> list:
    """收盤價穿越牆外站穩 hold_bars 根的確認 index; decluster_bars 內只記首次."""
    beyond = [(c > wall) if side == "CW" else (c < wall) for c in closes]
    ev = []
    run = 0
    armed = True          # 需先在牆內
    last = -10 ** 9
    for i, b in enumerate(beyond):
        if not b:
            armed = True
            run = 0
            continue
        if armed:
            run += 1
            if run >= hold_bars:
                if i - last >= decluster_bars:
                    ev.append(i)
                    last = i
                armed = False
                run = 0
    return ev


def sign_test_p(wins: int, losses: int) -> float:
    """兩尾 sign test (binomial p=0.5)."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = max(wins, losses)
    tail = sum(math.comb(n, j) for j in range(k, n + 1)) * 0.5 ** n
    return min(1.0, 2 * tail)


def tail_stats(xs: list) -> dict:
    if not xs:
        return {}
    s = sorted(xs)
    n = len(s)
    med = s[n // 2]
    return {"n": n, "mean": round(sum(s) / n, 1), "median": round(med, 1),
            "p90": round(s[min(n - 1, int(n * 0.9))], 1),
            "win_rate": round(sum(1 for x in s if x > 0) / n, 2)}


# ------------------------------------------------------------------ data
def day_levels(conn, d) -> dict:
    """D 日開盤水位: 09:00-09:30 gamma snapshot × D-1 OI → ZG; OI → CW/PW."""
    import pandas as pd
    cur = conn.cursor()
    cur.execute("""SELECT last(close, bucket) FROM ohlcv_1m_txf
                   WHERE symbol='TXF' AND bucket >= %(d)s::date + interval '9 hours'
                     AND bucket < %(d)s::date + interval '9 hours 30 minutes'""",
                {"d": d})
    r = cur.fetchone()
    spot = float(r[0]) if r and r[0] else None
    if not spot:
        return {}
    oi = pd.read_sql("""
      SELECT to_char(expiry,'YYYYMMDD') AS expiry, strike, cp, open_interest
      FROM option_oi_daily WHERE underlying='TX'
        AND settle_date = (SELECT max(settle_date) FROM option_oi_daily
                           WHERE settle_date < %(d)s)
        AND expiry > %(d)s::date ORDER BY expiry LIMIT 100000""", conn, params={"d": d})
    if oi.empty:
        return {}
    exps = sorted(oi.expiry.unique())[:3]
    oi = oi[oi.expiry.isin(exps)]
    win = oi[(oi.strike > spot - 1500) & (oi.strike < spot + 1500)]
    coi = win[win.cp == "C"].groupby("strike").open_interest.sum()
    poi = win[win.cp == "P"].groupby("strike").open_interest.sum()
    out = {"spot": spot,
           "cw": float(coi.idxmax()) if len(coi) else None,
           "pw": float(poi.idxmax()) if len(poi) else None, "zg": None}
    g = pd.read_sql("""
      SELECT DISTINCT ON (expiry, strike, call_put) expiry, strike, call_put, gamma
      FROM iv_strikes WHERE time >= %(d)s::date + interval '9 hours'
        AND time < %(d)s::date + interval '9 hours 30 minutes'
        AND expiry = ANY(%(e)s)
      ORDER BY expiry, strike, call_put, time DESC""",
                    conn, params={"d": d, "e": exps})
    if not g.empty:
        df = g.merge(oi, left_on=["expiry", "strike", "call_put"],
                     right_on=["expiry", "strike", "cp"]).dropna(
            subset=["gamma", "open_interest"])
        df = df[(df.strike > spot - 3000) & (df.strike < spot + 3000)]
        if not df.empty:
            sign = df.call_put.map({"C": 1.0, "P": -1.0})
            gex = (df.gamma * df.open_interest * MULTIPLIER * spot * spot * 0.01
                   * sign).groupby(df.strike).sum().sort_index()
            cum = gex.cumsum()
            crossings, prev = [], None
            for k, v in cum.items():
                if prev is not None and (prev < 0) != (v < 0):
                    crossings.append(float(k))
                prev = v
            if crossings:
                out["zg"] = min(crossings, key=lambda k: abs(k - spot))
    return out


def day_bars(conn, d):
    import pandas as pd
    return pd.read_sql("""
      SELECT bucket, high, low, close FROM ohlcv_1m_txf
      WHERE symbol='TXF' AND bucket >= %(d)s::date + interval '9 hours'
        AND bucket <= %(d)s::date + interval '13 hours 30 minutes'
      ORDER BY bucket""", conn, params={"d": d})


# ------------------------------------------------------------------ main
def main() -> int:
    import psycopg2
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT bucket::date FROM ohlcv_1m_txf
                   WHERE symbol='TXF' AND bucket >= '2026-04-24'
                     AND bucket::time BETWEEN '09:00' AND '13:30'
                   ORDER BY 1""")
    days = [r[0] for r in cur.fetchall()]

    rv_pairs = []                      # (day, rv_above_med, rv_below_med) ×15/60
    touch = {"CW": {"t5": [], "t15": []}, "PW": {"t5": [], "t15": []}}
    breakout_ext = {"CW": [], "PW": []}
    n_zg_days = 0

    for d in days:
        lv = day_levels(conn, d)
        if not lv:
            continue
        bars = day_bars(conn, d)
        if len(bars) < 120:
            continue
        closes = bars.close.astype(float).tolist()
        highs = bars.high.astype(float).tolist()
        lows = bars.low.astype(float).tolist()

        # 檢定 1 — ZG regime RV (需 gamma)
        if lv["zg"]:
            n_zg_days += 1
            above15, below15, above60, below60 = [], [], [], []
            for i in range(0, len(closes) - 61, 5):    # 每 5 bar 取樣降相關
                r15, r60 = fwd_rv(closes, i, 15), fwd_rv(closes, i, 60)
                (above15 if closes[i] > lv["zg"] else below15).append(r15)
                (above60 if closes[i] > lv["zg"] else below60).append(r60)
            if above15 and below15:
                med = lambda x: sorted(x)[len(x) // 2]  # noqa: E731
                rv_pairs.append((str(d), med(above15), med(below15),
                                 med(above60) if above60 else None,
                                 med(below60) if below60 else None))

        # 檢定 2 — 觸牆反轉 (CW 用 highs 由下進; PW 用 lows 鏡像)
        if lv["cw"]:
            for i in wall_touch_events(highs, lv["cw"], "CW"):
                for n, key in ((5, "t5"), (15, "t15")):
                    if i + n < len(closes):
                        touch["CW"][key].append(closes[i + n] - closes[i])
        if lv["pw"]:
            for i in wall_touch_events(lows, lv["pw"], "PW"):
                for n, key in ((5, "t5"), (15, "t15")):
                    if i + n < len(closes):
                        touch["PW"][key].append(closes[i + n] - closes[i])

        # 檢定 3 — 貫穿站穩後 T+60 順向位移 (自確認收盤起算, 無偏含虧損側)
        if lv["cw"]:
            for i in breakout_events(closes, lv["cw"], "CW"):
                if i + 60 < len(closes):
                    breakout_ext["CW"].append(closes[i + 60] - closes[i])
        if lv["pw"]:
            for i in breakout_events(closes, lv["pw"], "PW"):
                if i + 60 < len(closes):
                    breakout_ext["PW"].append(closes[i] - closes[i + 60])

    # ---- 統計
    lines = [f"# GEX 物理現象檢定 {date.today().isoformat()}", "",
             f"樣本: {len(days)} 交易日 (1-min 日盤 09:00-13:30) · "
             f"ZG 可算 {n_zg_days} 日 (gamma 自 6/2) · 水位=開盤 09:00-09:30 靜態", ""]

    # 1
    w15 = sum(1 for _, a, b, _, _ in rv_pairs if b > a)
    l15 = sum(1 for _, a, b, _, _ in rv_pairs if a > b)
    p60 = [(a, b) for _, _, _, a, b in rv_pairs if a and b]
    w60 = sum(1 for a, b in p60 if b > a)
    ratio15 = [b / a for _, a, b, _, _ in rv_pairs if a > 0]
    med_ratio15 = sorted(ratio15)[len(ratio15) // 2] if ratio15 else None
    ratio60 = [b / a for a, b in p60 if a > 0]
    med_ratio60 = sorted(ratio60)[len(ratio60) // 2] if ratio60 else None
    lines += ["## 檢定 1 — Regime Switch: RV(S<ZG) vs RV(S>ZG)", "",
              f"- 日級配對 n={len(rv_pairs)} (同日兩態並存)",
              f"- T+15: S<ZG 較大 {w15}/{w15 + l15} 日 · RV 比值中位 "
              f"{med_ratio15:.2f}x · sign-test p={sign_test_p(w15, l15):.3f}",
              f"- T+60: S<ZG 較大 {w60}/{len(p60)} 日 · 比值中位 "
              + (f"{med_ratio60:.2f}x" if med_ratio60 else "n/a")
              + f" · p={sign_test_p(w60, len(p60) - w60):.3f}",
              f"- 判準 (spec): 比值 >1.5x 且顯著 → "
              + ("**成立**" if med_ratio15 and med_ratio15 > 1.5
                 and sign_test_p(w15, l15) < 0.05 else "**不成立/弱**"), ""]

    # 2
    lines += ["## 檢定 2 — 觸牆反轉 (Wall Fade)", ""]
    for side, fav in (("CW", -1), ("PW", 1)):
        for k in ("t5", "t15"):
            xs = touch[side][k]
            if not xs:
                lines.append(f"- {side} {k}: 無事件")
                continue
            rev = sum(1 for x in xs if x * fav > 0)
            p = sign_test_p(rev, len(xs) - rev)
            med = sorted(xs)[len(xs) // 2]
            lines.append(f"- {side} {k}: n={len(xs)} 反轉勝率 {rev / len(xs):.0%} "
                         f"(p={p:.3f}) · 位移中位 {med:+.0f} 點")
    lines.append("")

    # 3
    lines += ["## 檢定 3 — 貫穿站穩後 T+60 順向位移 (自確認收盤起算, 含虧損側)", ""]
    for side in ("CW", "PW"):
        st = tail_stats(breakout_ext[side])
        if st:
            skew = "右偏(肥尾)" if st["mean"] > st["median"] else "無明顯肥尾"
            lines.append(f"- {side} 突破: n={st['n']} · mean {st['mean']:+} vs "
                         f"median {st['median']:+} → {skew} · p90 {st['p90']:+} 點 · "
                         f"順向勝率 {st['win_rate']:.0%}")
        else:
            lines.append(f"- {side} 突破: 無事件")
    lines += ["", "## Verification log", "",
              f"- 取樣: 每 5 bar 取 1 點降序列相關; RV 年化 √(252×270)",
              "- 水位為開盤靜態 (09:00-09:30 snapshot × D-1 結算 OI), 非盤中動態",
              "- sign test 兩尾 binomial p=0.5; 樣本小時據實標 n, 不外推",
              "", "*分析標註 · 不構成交易指令*"]
    out = REPO / "analysis" / f"gex_physics_{date.today().strftime('%Y%m%d')}.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines))
    try:
        import redis
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "gex_physics", "topic": "gex-physics",
            "tags": "gex,validation", "as_of": date.today().isoformat(),
            "msg": f"GEX 物理檢定完成: RV配對 {len(rv_pairs)}日 · "
                   f"觸牆 CW {len(touch['CW']['t15'])}/PW {len(touch['PW']['t15'])} 事件 · "
                   f"貫穿 CW {len(breakout_ext['CW'])}/PW {len(breakout_ext['PW'])}",
            "report_path": f"analysis/{out.name}"})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
