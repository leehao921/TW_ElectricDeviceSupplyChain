#!/usr/bin/env python3
"""融資融券 + 台股 VIX 日報 (18:10) — 觸發 collectors 後推 inbox.

- margin_daily: 大盤融資餘額 5D 趨勢 + 個股融資/融券增減 top (張)
- vix_daily: 自家 TXO 近月 IV 衍生 (官方 VIX 已停編), 水位 + 5D 變化
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")
TOP_N = 5


def top_movers(rows: list[dict], field: str, n: int = TOP_N) -> tuple[list, list]:
    """rows: {symbol, delta_fin, delta_short}; 回傳 (增 top n, 減 top n)."""
    valid = [r for r in rows if r.get(field) is not None]
    up = sorted(valid, key=lambda r: -r[field])[:n]
    down = sorted(valid, key=lambda r: r[field])[:n]
    return ([r for r in up if r[field] > 0], [r for r in down if r[field] < 0])


def render(as_of: str, fin_now: float, fin_5d_chg: float, vix: float | None,
           vix_5d_chg: float | None, fin_up: list, fin_down: list,
           short_up: list, labels: dict | None = None,
           cm30: dict | None = None) -> str:
    def name(t):
        info = (labels or {}).get(t)
        return f"{t} {info['name']}" if info and info.get("name") else t

    def fmt(rows, field):
        return " / ".join(f"{name(r['symbol'])} {r[field]:+,}" for r in rows[:3]) or "—"
    lines = [f"融資融券×VIX 日報 {as_of}"]
    lines.append(f"大盤融資餘額 {fin_now/1e5:,.0f}億 ({fin_5d_chg:+,.0f}億/5D)")
    if vix is not None:
        chg = f" ({vix_5d_chg:+.1f}/5D)" if vix_5d_chg is not None else ""
        zone = "低波動" if vix < 18 else ("常態" if vix < 25 else "高壓")
        lines.append(f"台股VIX(TXO近月IV) {vix:.1f}{chg} · {zone}")
    if cm30 and cm30.get("vix_30d") is not None:
        vrp = cm30.get("vrp_30d")
        vrp_txt = f" · VRP30 {vrp:+.1f}" if vrp is not None else ""
        pct = cm30.get("vrp_pct")
        pct_txt = f" (pct {pct:.0f}, n={cm30['n']})" if pct is not None else " (歷史<20日不予分位)"
        lines.append(f"VIX30(常數期限) {cm30['vix_30d']:.1f} · RV21 {cm30.get('rv_21d') or float('nan'):.1f}"
                     f"{vrp_txt}{pct_txt}")
    if cm30 and cm30.get("vix_w") is not None:
        wm = cm30.get("wm_spread")
        if wm is not None and wm > 2:
            struct = f"🚨 倒掛 {wm:+.1f} (即期事件恐慌, 7/29=+8.2 8/5=+10.4 級距)"
        elif wm is not None and wm > 0:
            struct = f"⚠️ 微倒掛 {wm:+.1f}"
        else:
            struct = f"正價差 {wm:+.1f} (近期平靜)" if wm is not None else ""
        lines.append(f"週選IV(最敏感) {cm30['vix_w']:.1f} · 週/月結構: {struct}")
    lines.append(f"融資增: {fmt(fin_up, 'delta_fin')} (張)")
    lines.append(f"融資減: {fmt(fin_down, 'delta_fin')} (張)")
    lines.append(f"融券增: {fmt(short_up, 'delta_short')} (張)")
    return "\n".join(lines)


def run_collectors(as_of: str) -> None:
    d = date.fromisoformat(as_of)
    prev = d - timedelta(days=3 if d.weekday() == 0 else 1)
    for args in (["scripts/collectors/margin_daily.py", "--date", prev.isoformat()],
                 ["scripts/collectors/margin_daily.py", "--date", as_of],
                 ["scripts/collectors/vix_daily.py"]):
        try:
            subprocess.run(["docker", "exec", "-e", "PYTHONPATH=/opt/tmf:/opt/tmf/src",
                            "tmf-stock-daily-collector", "python"] + args,
                           check=True, capture_output=True, timeout=180)
        except Exception as e:
            print(f"[warn] {args[0]} {args[-1]} failed: {e}", file=sys.stderr)


def main() -> int:
    as_of = date.today().isoformat()
    run_collectors(as_of)
    import psycopg2
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT max(date) FROM margin_daily")
    latest = cur.fetchone()[0]
    if not latest:
        print("[error] no margin data")
        return 1
    as_of = latest.isoformat()
    # 大盤融資餘額 (仟元→億)
    cur.execute("""SELECT date, fin_value_kilo_ntd FROM margin_market_daily
                   WHERE market='TWSE' ORDER BY date DESC LIMIT 6""")
    mk = cur.fetchall()
    fin_now = float(mk[0][1]) if mk else 0
    fin_5d = (fin_now - float(mk[-1][1])) / 1e5 if len(mk) > 1 else 0
    # VIX
    cur.execute("SELECT date, vix FROM vix_daily WHERE vix IS NOT NULL ORDER BY date DESC LIMIT 6")
    vx = cur.fetchall()
    vix = float(vx[0][1]) if vx else None
    vix5 = (vix - float(vx[-1][1])) if vx and len(vx) > 1 else None
    # CM30 對齊序列 (2026-08-27 三層錯位修復): vrp_30d percentile 經 n>=20 guard
    cur.execute("""SELECT vix_30d, rv_21d, vrp_30d, vix_w, wm_spread FROM vix_daily
                   WHERE vix_30d IS NOT NULL ORDER BY date DESC LIMIT 1""")
    row30 = cur.fetchone()
    cm30 = None
    if row30:
        cur.execute("SELECT vrp_30d FROM vix_daily WHERE vrp_30d IS NOT NULL ORDER BY date")
        hist = [float(r[0]) for r in cur.fetchall()]
        pct = None
        if len(hist) >= 20 and row30[2] is not None:
            cur_v = float(row30[2])
            pct = 100.0 * sum(1 for h in hist if h < cur_v) / len(hist)
        cm30 = {"vix_30d": float(row30[0]),
                "rv_21d": float(row30[1]) if row30[1] is not None else None,
                "vrp_30d": float(row30[2]) if row30[2] is not None else None,
                "vix_w": float(row30[3]) if row30[3] is not None else None,
                "wm_spread": float(row30[4]) if row30[4] is not None else None,
                "vrp_pct": pct, "n": len(hist)}
    # 個股增減 (今日 vs 前日餘額欄)
    cur.execute("""SELECT symbol, fin_balance - fin_prev, short_balance - short_prev
                   FROM margin_daily WHERE date=%s
                   AND symbol ~ '^[1-9][0-9]{3}$'
                   AND fin_balance IS NOT NULL AND fin_prev IS NOT NULL""", (latest,))
    rows = [dict(symbol=r[0], delta_fin=int(r[1]),
                 delta_short=int(r[2]) if r[2] is not None else None) for r in cur.fetchall()]
    fin_up, fin_down = top_movers(rows, "delta_fin")
    short_up, _ = top_movers([r for r in rows if r["delta_short"] is not None], "delta_short")

    sys.path.insert(0, str(REPO / "scripts"))
    from warrant_flow_rank import load_labels
    msg = render(as_of, fin_now, fin_5d, vix, vix5, fin_up, fin_down, short_up,
                 labels=load_labels(), cm30=cm30)
    print(msg)
    try:
        import redis
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "margin_vix", "topic": "margin-vix",
            "tags": "margin,vix", "as_of": as_of, "msg": msg})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
