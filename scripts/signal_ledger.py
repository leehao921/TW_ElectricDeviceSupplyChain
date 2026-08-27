#!/usr/bin/env python3
"""訊號總帳 — 每週五 19:50 彙整多/空訊號家族的現況與滾動命中率.

目錄: docs/signal_registry.md。各家族數據取自既有 tracker 產物
(bb_followthrough / disposition / warrant history + margin_daily 橫斷面重算),
不重複實作追蹤邏輯 — 本腳本只做彙整與分級快照。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")


def _load(p: str):
    f = REPO / "data" / p
    return json.loads(f.read_text()) if f.exists() else None


def bb_stats() -> str:
    h = _load("bb_followthrough_history.json") or []
    done = [e for e in h if e.get("final_status")]
    if not done:
        return "L2 BB squeeze: 無畢業樣本"
    win = sum(1 for e in done if e["final_status"] in ("confirmed", "波段", "graduated")
              and (e.get("cumret_pct") or 0) > 0)
    return f"L2 BB squeeze: 畢業 {len(done)}, 正報酬收場 {win}/{len(done)}"


def disposition_stats() -> str:
    h = _load("disposition_tracking_history.json") or _load("disposition_history.json") or []
    st = _load("disposition_tracking_state.json") or {}
    tracked = st.get("tracked", {})
    done = [e for e in (h + list(tracked.values()))
            if e.get("post", {}).get("t5") is not None]
    if not done:
        return "L1/S1 處置解除: 無 t5 樣本"
    buy = [e for e in done if (e.get("foreign_20d_at_enter") or 0) > 0]
    sell = [e for e in done if (e.get("foreign_20d_at_enter") or 0) <= 0]
    def _m(g):
        vals = sorted(e["post"]["t5"] for e in g)
        return vals[len(vals) // 2] if vals else None
    return (f"L1/S1 處置解除 (live): 買超組 n={len(buy)} t5中位 {_m(buy)}% · "
            f"賣超組 n={len(sell)} t5中位 {_m(sell)}%")


def warrant_stats() -> str:
    h = _load("warrant_flow_history.json") or []
    out = []
    for side, cond in (("佈多", lambda x: x > 0), ("佈空", lambda x: x < 0)):
        done = [e for e in h if e.get("side") == ("long" if side == "佈多" else "short")
                and e.get("post", {}).get("t5") is not None]
        hit = sum(1 for e in done if cond(e["post"]["t5"]))
        out.append(f"{side} {hit}/{len(done)}")
    return f"L6/S5 權證榜 T+5 命中: {' · '.join(out)}"


def margin_deciles(conn) -> str:
    import pandas as pd
    m = pd.read_sql("""SELECT date, symbol, fin_balance, fin_prev FROM margin_daily
      WHERE symbol ~ '^[1-9][0-9]{3}$' AND fin_prev >= 500 AND fin_balance IS NOT NULL""",
                    conn, parse_dates=["date"])
    m["growth"] = (m.fin_balance - m.fin_prev) / m.fin_prev
    px = pd.read_sql("SELECT symbol, ts::date d, close FROM stock_daily_ohlcv ORDER BY 1,2",
                     conn, parse_dates=["d"])
    wide = px.pivot(index="d", columns="symbol", values="close")
    fwd5 = wide.shift(-5) / wide - 1
    rows = []
    for d, g in m.groupby("date"):
        if d not in fwd5.index:
            continue
        g = g.set_index("symbol")
        f = fwd5.loc[d].reindex(g.index).dropna()
        g = g.loc[f.index]
        if len(g) < 300:
            continue
        q = g.growth.rank(pct=True)
        rows.append(dict(top=f[q >= 0.9].median() * 100, bot=f[q <= 0.1].median() * 100,
                         mkt=f.median() * 100))
    if not rows:
        return "L7/S2 融資增速: 樣本不足"
    r = pd.DataFrame(rows)
    return (f"L7/S2 融資增速 (n={len(r)} 日): top10% {r.top.mean():+.2f}%/5D vs "
            f"bot10% {r.bot.mean():+.2f}% (大盤 {r.mkt.mean():+.2f}%) · "
            f"價差 {(r.top - r.bot).mean():+.2f}%")


def gauges(conn) -> list[str]:
    out = []
    with conn.cursor() as cur:
        cur.execute("""SELECT date, round(vix_w::numeric,1), round(vix_30d::numeric,1),
                       round(wm_spread::numeric,1), round(vrp_30d::numeric,1)
                       FROM vix_daily WHERE vix_30d IS NOT NULL ORDER BY date DESC LIMIT 1""")
        r = cur.fetchone()
        if r:
            out.append(f"IV 結構 ({r[0]}): 週 {r[1]} / 月30 {r[2]} / 倒掛 {r[3]} / VRP30 {r[4]}")
        cur.execute("""SELECT count(*) FILTER (WHERE score < 0), count(*)
                       FROM warrant_flow_daily WHERE date=(SELECT max(date) FROM warrant_flow_daily)""")
        s, n = cur.fetchone()
        out.append(f"權證面: 最新日 {n} 檔中 {s} 檔淨佈空能量")
    try:
        import redis
        import json as _j
        h = redis.Redis(decode_responses=True).hgetall("h:agent:pb_lights")
        lights = [_j.loads(v).get("light") for k, v in h.items() if not k.startswith("_")]
        red = sum(1 for x in lights if x == "RED")
        out.append(f"P/B 廣度: {red}/{len(lights)} RED ({red / max(len(lights), 1) * 100:.0f}%)")
    except Exception:
        pass
    return out


def main() -> int:
    import psycopg2
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    as_of = date.today().isoformat()
    lines = [f"# 訊號總帳週報 {as_of}", "",
             "目錄與分級: docs/signal_registry.md (L=做多 S=做空家族)", "",
             "## 家族滾動追蹤", ""]
    for fn in (disposition_stats, bb_stats, warrant_stats):
        try:
            lines.append("- " + fn())
        except Exception as e:
            lines.append(f"- [err] {fn.__name__}: {e}")
    try:
        lines.append("- " + margin_deciles(conn))
    except Exception as e:
        lines.append(f"- [err] margin: {e}")
    lines += ["", "## 系統性儀表", ""]
    lines += ["- " + g for g in gauges(conn)]
    lines += ["", "## 研究隊列", "",
              "- S3 skew +15m 樣本外 (10 月) · S4 VRP 對齊重跑 (vrp_30d 累積中) · 融資訊號滿季確認 (10 月底)",
              "", "*源: signal_ledger.py 週五 19:50 · 分級異動請改 docs/signal_registry.md*"]
    md = "\n".join(lines)
    out = REPO / "analysis" / f"signal_ledger_{as_of}.md"
    out.write_text(md)
    print(md)
    try:
        import redis
        summary = " | ".join(l[2:] for l in lines if l.startswith("- "))[:800]
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "signal_ledger", "topic": "signal-ledger",
            "tags": "signals,weekly", "as_of": as_of,
            "msg": f"訊號總帳週報: {summary}",
            "report_path": f"analysis/{out.name}"})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
