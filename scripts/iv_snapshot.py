#!/usr/bin/env python3
"""iv_snapshot.py — 盤中每 30 分鐘推 IV 期限表 + 前月 ATM 變化到 claude:inbox (→ Discord #guyu)。

用戶 2026-10-12: 線上看 IV 變化 — 選 Grafana (tw-iv-live) + Discord 定時快照。
gex-regime 只在事件時推;本 routine 固定節奏,手機看 IV 走勢。
launchd com.lulala.iv-snapshot 09:00-13:30 每 :00/:30;休市/假日 (iv_strikes 不新鮮) 靜默。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

DAY_WINDOW = ("09:00", "13:35")


def _chg(now: float, then) -> str:
    return "n/a" if then is None else "%+.1f" % (now - then)


def snapshot_header(front: str, iv_now: float, iv_30m, iv_open) -> str:
    """前月 ATM 現值 + 30 分鐘變化 + 開盤以來變化 (vol-pt)。"""
    return "前月 %s ATM %.1f%% · 30分 %s · 開盤來 %s" % (
        front, iv_now, _chg(iv_now, iv_30m), _chg(iv_now, iv_open))


def _front_iv(cur):
    """前月 = 距結算 ≥5 天的最近 TXO 月選 → (MM/DD, 現值, 30 分前, 今日 08:46-08:50)。"""
    cur.execute("""SELECT min(expiry) FROM iv_metrics WHERE product_code='TXO'
                   AND time > now() - interval '1 hour'
                   AND to_date(expiry,'YYYYMMDD') >= (now() AT TIME ZONE 'Asia/Taipei')::date + 5""")
    exp = cur.fetchone()[0]
    if not exp:
        return None

    def avg(cond):
        cur.execute("SELECT avg(atm_iv)*100 FROM iv_metrics WHERE product_code='TXO' "
                    "AND expiry=%s AND " + cond, (exp,))
        v = cur.fetchone()[0]
        return float(v) if v is not None else None

    now_ = avg("time > now() - interval '2 min'")
    ago = avg("time BETWEEN now() - interval '32 min' AND now() - interval '28 min'")
    opn = avg("(time AT TIME ZONE 'Asia/Taipei')::date = (now() AT TIME ZONE 'Asia/Taipei')::date "
              "AND (time AT TIME ZONE 'Asia/Taipei')::time BETWEEN '08:46' AND '08:50'")
    return exp[4:6] + "/" + exp[6:], now_, ago, opn


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="印出不推送,且不檢查交易時段")
    args = ap.parse_args(argv)

    import psycopg2
    from ascii_dashboard import DB
    from gex_regime_monitor import iv_block, iv_curve, latest_forwards, market_live

    now = datetime.now()
    hm = now.strftime("%H:%M")
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    if not args.dry_run and (not (DAY_WINDOW[0] <= hm <= DAY_WINDOW[1]) or not market_live(cur)):
        return 0                                       # 非日盤 / 休市靜默

    cur.execute("""SELECT last(close, bucket) FROM ohlcv_1m_txf
                   WHERE symbol='TXF' AND bucket >= now() - interval '3 days'""")
    spot = float(cur.fetchone()[0] or 0)
    block = iv_block(iv_curve(conn, spot), latest_forwards(conn), spot, now)
    front = _front_iv(cur)
    head = snapshot_header(*front) if front and front[1] is not None else "前月 ATM n/a"
    msg = "%s\n%s\n(分析標註·不構成交易指令)" % (head, block)
    if args.dry_run:
        print(msg)
        return 0
    import redis
    redis.Redis().xadd("claude:inbox", {
        "ts": now.strftime("%Y-%m-%d %H:%M"), "from": "iv_snapshot", "topic": "iv-snapshot",
        "tags": "iv,snapshot", "as_of": date.today().isoformat(), "msg": msg})
    return 0


if __name__ == "__main__":
    sys.exit(main())
