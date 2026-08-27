#!/usr/bin/env python3
"""持倉觸發哨兵 — 停利階梯/停損/左側觸發的每日自動評估 (15:10)

起因 (2026-08-27): 2603 破 MA10、華航外資觸發成立 — 但這些紀律只寫在分析
文件裡, 無排程評估 → Discord 收不到。本哨兵讀 data/position_triggers.json,
收盤後對 stock_daily_ohlcv + institutional_stock 評估, 觸發推 🚨。
fire-once + 條件清除後重 arm (state: data/position_watch_state.json)。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRIGGERS_PATH = REPO / "data" / "position_triggers.json"
STATE_PATH = REPO / "data" / "position_watch_state.json"
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")


def evaluate(trig: dict, market: dict) -> bool | None:
    """單一觸發器評估; 標的無資料 → None (揭露不誤判)."""
    m = market.get(trig["symbol"])
    if not m:
        return None
    t = trig["type"]
    if t == "ma_break":
        ma = m.get(f"ma{trig['ma']}")
        return None if (ma is None or m.get("close") is None) else m["close"] < ma
    if t == "price_above":
        return None if m.get("close") is None else m["close"] >= trig["level"]
    if t == "price_below":
        return None if m.get("close") is None else m["close"] <= trig["level"]
    if t == "foreign_5d_above":
        f5 = m.get("foreign_5d")
        return None if f5 is None else f5 > trig["level"]
    return None


def should_fire(trig: dict, condition: bool | None, state: dict, as_of: str) -> bool:
    """fire-once: 條件為真且未 armed-fired → 發; 條件轉假 → 重 arm."""
    key = trig["id"]
    if condition is True:
        if state.get(key, {}).get("fired"):
            return False
        state[key] = {"fired": True, "date": as_of}
        return True
    if condition is False and key in state:
        state[key] = {"fired": False, "cleared": as_of}
    return False


def load_market(conn, symbols: list[str]) -> dict:
    import pandas as pd
    out: dict = {}
    px = pd.read_sql(
        "SELECT symbol, ts::date d, close FROM stock_daily_ohlcv "
        "WHERE symbol = ANY(%(s)s) ORDER BY symbol, ts", conn, params={"s": symbols})
    for sym, g in px.groupby("symbol"):
        c = g.set_index("d")["close"]
        out[sym] = {"close": float(c.iloc[-1]), "date": str(c.index[-1]),
                    "ma10": float(c.rolling(10).mean().iloc[-1]) if len(c) >= 10 else None,
                    "ma20": float(c.rolling(20).mean().iloc[-1]) if len(c) >= 20 else None}
    with conn.cursor() as cur:
        for sym in symbols:
            cur.execute("""WITH d5 AS (SELECT DISTINCT date FROM institutional_stock
                                       ORDER BY date DESC LIMIT 5)
                SELECT round((sum(foreign_net*close_price)/1e8)::numeric,1)
                FROM institutional_stock JOIN d5 USING(date)
                WHERE symbol=%s AND close_price>0""", (sym,))
            r = cur.fetchone()
            out.setdefault(sym, {})["foreign_5d"] = float(r[0]) if r and r[0] is not None else None
    return out


def main() -> int:
    if not TRIGGERS_PATH.exists():
        print("[error] no triggers config"); return 1
    cfg = json.loads(TRIGGERS_PATH.read_text())
    triggers = [t for t in cfg.get("triggers", []) if t.get("active", True)]
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    import psycopg2
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    market = load_market(conn, sorted({t["symbol"] for t in triggers}))
    as_of = date.today().isoformat()

    fired, status_lines = [], []
    for t in triggers:
        cond = evaluate(t, market)
        m = market.get(t["symbol"], {})
        desc = f"{t['symbol']} {t.get('name','')} {t['id']}"
        if cond is None:
            status_lines.append(f"⚪ {desc}: 資料不足")
            continue
        if should_fire(t, cond, state, as_of):
            fired.append(f"🚨 {desc}: {t.get('desc','觸發')} → **{t.get('action','')}** "
                         f"(收 {round(m.get('close') or 0, 2)}, MA10 {round(m.get('ma10') or 0,1)}, "
                         f"外資5D {m.get('foreign_5d')})")
        status_lines.append(f"{'🔴' if cond else '🟢'} {desc}")
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    msg_lines = [f"持倉哨兵 {as_of}"]
    msg_lines += fired if fired else ["本日無新觸發"]
    msg_lines.append("狀態: " + " · ".join(status_lines))
    msg = "\n".join(msg_lines)
    print(msg)
    try:
        import redis
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "position_watch", "topic": "position-watch",
            "tags": "positions,triggers" + (",fired" if fired else ""),
            "as_of": as_of, "msg": msg})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
