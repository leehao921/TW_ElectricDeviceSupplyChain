#!/usr/bin/env python3
"""ASCII 數據監控儀表 — TXO 對沖牆 + P/C + VIX 家族 + 法人 + 訊號面 → Discord.

自有數據版的 GEX 對沖牆概念圖 (OI 基準): 近月 TXO 每履約價 Put/Call OI 雙向條,
標 Call Wall / Put Wall / 現價箭頭。搭配 vix_daily、futures_oi_daily、
institutional_stock、margin_market_daily、signal_scan 狀態組成整版。
推送: claude:inbox topic=dashboard, msg 用 ``` 包住 → discord-forward 以
monospace code block 呈現。所有內容為分析標註, 不構成交易指令。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")
BAR_W = 12
STEP = 100          # 履約價間距 (近月 TXO)
SPAN = 800          # 現價 ± 範圍


def hbar(v: float, vmax: float, width: int) -> str:
    """量值 → 橫條; 非零最少給細條 ▏."""
    if v <= 0 or vmax <= 0:
        return ""
    n = int(round(v / vmax * width))
    return "█" * n if n > 0 else "▏"


def pc_ratio(oi: dict) -> float:
    """Put OI 總量 / Call OI 總量 × 100."""
    p = sum(d.get("P", 0) for d in oi.values())
    c = sum(d.get("C", 0) for d in oi.values())
    return p / c * 100 if c else float("nan")


def wall_rows(oi: dict, spot: float, width: int = BAR_W, zg: float | None = None) -> list:
    """OI 對沖牆: Put 條 | 履約價 | Call 條, 標 PW/CW/ZG/現價◀."""
    strikes = sorted(oi, reverse=True)
    vmax = max(max(d.get("P", 0), d.get("C", 0)) for d in oi.values()) or 1
    cw = max(oi, key=lambda k: oi[k].get("C", 0))
    pw = max(oi, key=lambda k: oi[k].get("P", 0))
    nearest = min(strikes, key=lambda k: abs(k - spot))
    zg_row = min(strikes, key=lambda k: abs(k - zg)) if zg is not None else None
    rows = []
    for k in strikes:
        p, c = oi[k].get("P", 0), oi[k].get("C", 0)
        left = hbar(p, vmax, width).rjust(width)
        right = hbar(c, vmax, width).ljust(width)
        tag = " CW" if k == cw else (" PW" if k == pw else "")
        if k == zg_row:
            tag += " ZG"
        arrow = "◀" if k == nearest else " "
        rows.append(f"{left}│{k:>5}│{right}{arrow}{tag}")
    return rows


def build(conn) -> str:
    import pandas as pd
    cur = conn.cursor()

    # ---- 現價/指數
    cur.execute("""SELECT last(close, bucket) FROM ohlcv_1m_txf
                   WHERE symbol='TXF' AND bucket >= now() - interval '3 days'""")
    txf = float(cur.fetchone()[0] or 0)
    cur.execute("""SELECT close FROM asia_index_daily WHERE symbol='TWII'
                   ORDER BY ts DESC LIMIT 1""")
    r = cur.fetchone()
    twii = float(r[0]) if r else None
    cur.execute("""SELECT ts::date, close FROM stock_daily_ohlcv WHERE symbol='2330'
                   ORDER BY ts DESC LIMIT 5""")
    tsm = [float(x[1]) for x in cur.fetchall()]
    tsmc, tsmc_ma5 = (tsm[0], sum(tsm) / len(tsm)) if tsm else (None, None)

    # ---- TXO 近月 OI 牆
    cur.execute("""SELECT min(expiry) FROM option_oi_daily
                   WHERE underlying='TX' AND settle_date=(SELECT max(settle_date)
                   FROM option_oi_daily) AND expiry >= now()::date""")
    front = cur.fetchone()[0]
    cur.execute("""SELECT strike, cp, sum(open_interest) FROM option_oi_daily
                   WHERE underlying='TX' AND expiry=%s
                     AND settle_date=(SELECT max(settle_date) FROM option_oi_daily)
                   GROUP BY strike, cp""", (front,))
    oi_full: dict[int, dict] = {}
    oi_all: dict[int, dict] = {}
    for k, cp, v in cur.fetchall():
        k = int(float(k))
        oi_full.setdefault(k, {})[cp[0].upper()] = int(v)
        if abs(k - txf) <= SPAN and k % STEP == 0:
            oi_all.setdefault(k, {})[cp[0].upper()] = int(v)
    pcr = pc_ratio(oi_full)          # P/C 用全鏈 (慣例口徑), 牆圖才用 ±SPAN 窗
    cw = max(oi_all, key=lambda k: oi_all[k].get("C", 0)) if oi_all else None
    pw = max(oi_all, key=lambda k: oi_all[k].get("P", 0)) if oi_all else None

    # ---- GEX (盤中 iv_strikes gamma × OI, 復用 options_quant §3.1)
    gex_total = gex_flip = gex_zone = None
    try:
        front_txt = front.strftime("%Y%m%d")
        strikes_df = pd.read_sql("""
          SELECT DISTINCT ON (strike, call_put) strike, call_put, gamma
          FROM iv_strikes WHERE time >= now()::date AND expiry = %(e)s
          ORDER BY strike, call_put, time DESC""", conn, params={"e": front_txt})
        oi_df = pd.read_sql("""
          SELECT strike, cp, open_interest, settle_date FROM option_oi_daily
          WHERE underlying='TX' AND expiry = %(e)s
            AND settle_date = (SELECT max(settle_date) FROM option_oi_daily)""",
                            conn, params={"e": front})
        from options_quant import analyze_gex
        m = analyze_gex(strikes_df, oi_df, txf)["metrics"]
        gex_total, gex_flip, gex_zone = m["total_gex"], m["flip"], m["zone"]
    except Exception as e:
        print(f"[warn] GEX layer failed: {e}", file=sys.stderr)

    # ---- VIX 家族
    cur.execute("""SELECT vix, vix_30d, rv_21d, vrp_30d, vix_w, wm_spread
                   FROM vix_daily ORDER BY date DESC LIMIT 1""")
    vix, v30, rv, vrp, vw, wm = [round(float(x), 1) if x is not None else None
                                 for x in (cur.fetchone() or [None] * 6)]

    # ---- 法人
    cur.execute("""SELECT participant_type, net_oi FROM futures_oi_daily
                   WHERE underlying='TXF'
                     AND settle_date=(SELECT max(settle_date) FROM futures_oi_daily)""")
    foi = dict(cur.fetchall())
    cur.execute("""SELECT sum(foreign_net * close_price) / 1e8 FROM institutional_stock
                   WHERE date=(SELECT max(date) FROM institutional_stock)""")
    fspot = float(cur.fetchone()[0] or 0)
    cur.execute("""SELECT date, fin_value_kilo_ntd / 1e5 FROM margin_market_daily
                   ORDER BY date DESC LIMIT 2""")
    mg = cur.fetchall()
    fin_now = float(mg[0][1]) if mg else None
    fin_chg = (float(mg[0][1]) - float(mg[1][1])) if len(mg) == 2 else None

    # ---- 訊號面 (今日日掃 + 恐懼/貪婪)
    today = date.today().isoformat()
    fams: dict[str, int] = {}
    try:
        st = json.loads((REPO / "data" / "signal_scan_state.json").read_text())
        for e in st.get("tracked", {}).values():
            if e.get("enter_date") == today:
                fams[e["family"]] = fams.get(e["family"], 0) + 1
    except Exception:
        pass
    fear = greed = "–"
    rp = REPO / "analysis" / f"signal_scan_{today}.md"
    if rp.exists():
        txt = rp.read_text()
        fear = str(txt.count("\n- ", txt.find("😱"), txt.find("🤑"))) \
            if "😱" in txt and "🤑" in txt else "0"
        greed = str(txt.count("\n- ", txt.find("🤑"), txt.find("## 名單自我校驗"))) \
            if "🤑" in txt else "0"

    gate_px = "🟢" if txf >= 39385 else "🔴"
    gate_iv = "🟢" if (wm is None or wm <= 2) else "🔴"
    pcr_tag = "偏多" if pcr > 110 else ("偏空" if pcr < 90 else "中性")

    L = []
    L.append(f"╔══ TW 監控儀表 {today} {datetime.now():%H:%M} ══╗")
    L.append(f" TXF {txf:,.0f} · 加權 {twii:,.0f}" + (f" · 台積電 {tsmc:,.0f}"
             f"(5MA {tsmc_ma5:,.0f})" if tsmc else ""))
    L.append("")
    L.append(f"── TXO 近月 OI 對沖牆 (到期 {front}) ──")
    L.append(f"{'Put OI':>{BAR_W}}│ 履約 │Call OI")
    L += wall_rows(oi_all, txf, zg=gex_flip)
    L.append(f" P/C(OI) {pcr:.1f}% {pcr_tag} · CallWall {cw:,} · PutWall {pw:,}")
    if gex_total is not None:
        zone_txt = "磁吸(pinning)" if gex_zone == "pinning" else "放大(expansion)"
        L.append(f" GEX {gex_total/1e8:+,.0f}億/1% · ZeroGamma "
                 + (f"{gex_flip:,.0f}" if gex_flip else "n/a") + f" · {zone_txt}")
    L.append("")
    L.append("── 波動率 ──")
    L.append(f" VIX {vix} · CM30 {v30} · RV21 {rv} · VRP {vrp:+.1f}")
    L.append(f" 週選 {vw} · 週/月 {wm:+.1f} ({'倒掛🚨' if wm and wm > 2 else '正常'})")
    L.append("")
    L.append("── 法人/融資 ──")
    L.append(f" TXF淨OI: 外資 {foi.get('外資', 0):+,} · 投信 {foi.get('投信', 0):+,} 口")
    L.append(f" 現貨外資 {fspot:+,.0f} 億 · 大盤融資 {fin_now:,.0f} 億"
             + (f" ({fin_chg:+,.0f})" if fin_chg is not None else ""))
    L.append("")
    L.append("── 訊號/Gate ──")
    L.append(f" 日掃新名單: {', '.join(f'{k}×{v}' for k, v in fams.items()) or '無'}")
    L.append(f" 恐懼區 {fear} · 貪婪區 {greed} (持股池)")
    L.append(f" Regime: 39,385 {gate_px} · IV倒掛 {gate_iv}")
    L.append("╚═ 分析標註 · 不構成交易指令 ═╝")
    return "\n".join(L)


def main() -> int:
    import psycopg2
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    board = build(conn)
    print(board)
    try:
        import redis
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "ascii_dashboard", "topic": "dashboard",
            "tags": "dashboard,ascii", "as_of": date.today().isoformat(),
            "msg": f"```\n{board}\n```"})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
