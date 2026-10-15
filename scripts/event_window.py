#!/usr/bin/env python3
"""event_window.py — 事件窗口 IV 監控 (plan: docs/plans/2026-10-15-event-window-iv.md)

10/14 20:30 CPI: 事前 IV 無方向訊號,但 10/16 週選已定價 ±484 點;事後 PCR 0.58→0.92、
價跌 IV 升 → 延續到 48,338。本 routine 把這兩段變成固定流程:

  pre   (反應時刻前 30 分;盤後事件 = 最後可交易分鐘前 30 分) 推「週選定價 ±X 點」
  +5/+15 (以反應時刻為 0) 推「實際 vs 定價 + 週選 IV / PCR 反應 → 延續/消化/混合」
  +60   補 outcome (continued/reversed/flat) 進 data/event_window_log.csv

    python scripts/event_window.py            # launchd 每 60s (com.lulala.event-window)
    python scripts/event_window.py backfill   # 以歷史 iv_metrics + ticks 重播過去事件
    python scripts/event_window.py --dry-run  # 印出各事件下一階段

分析標註,不構成交易指令。事件來源 = data/event_calendar.csv (MOPS 法說 + nautilus 總經)。
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

LOG_PATH = REPO / "data" / "event_window_log.csv"
LOG_FIELDS = ["event_key", "kind", "name", "event_at", "reaction_at", "implied_expiry", "implied_pts",
              "implied_pct", "co_events", "px_pre", "px_5", "px_15", "px_60",
              "iv_w_pre", "iv_w_5", "iv_w_15", "iv_m_pre", "iv_m_5", "iv_m_15",
              "pcr_pre", "pcr_5", "pcr_15", "skew_pre", "skew_5", "skew_15",
              "class_5", "class_15", "outcome_60", "data_quality"]
DONE_KEY = "event_window:done:%s"
DONE_TTL_S = 14 * 86400
PRE_LEAD = timedelta(minutes=30)
STAGES = {"pre": None, "5": 5, "15": 15, "60": 60}
STAGE_GRACE = timedelta(minutes=10)            # 階段時刻後 10 分鐘內仍可觸發 (launchd 漏一兩次)
SIZE_FRAC = 0.3                                # |移動| ≥ 0.3 × 定價幅度 才算有反應
NO_IMPLIED_FRAC = 0.005                        # 無定價時用 0.5% 價格當幅度尺度
IV_MOVE = 0.5                                  # vol-pt
OUTCOME_FRAC = 0.1
FIX_DATE = date(2026, 10, 5)                   # IV 輸入改做市商 mid (database e3ee0fd)
DAY_OPEN, DAY_CLOSE = time(8, 45), time(13, 45)
NIGHT_OPEN, NIGHT_CLOSE = time(15, 0), time(5, 0)


# --------------------------------------------------------------------------- #
# 交易時段
# --------------------------------------------------------------------------- #
def _trading(d: date, holidays) -> bool:
    return d.weekday() < 5 and d not in holidays


def in_session(t: datetime, holidays) -> bool:
    """TAIFEX 日盤 08:45-13:45、夜盤 15:00-次日 05:00 (以開盤日為交易日)。"""
    d, tm = t.date(), t.time()
    if _trading(d, holidays) and (DAY_OPEN <= tm < DAY_CLOSE or tm >= NIGHT_OPEN):
        return True
    return tm < NIGHT_CLOSE and _trading(d - timedelta(days=1), holidays)


def reaction_time(event_at: datetime, holidays) -> datetime:
    """事件時刻在盤中 = 本身;否則下一個開盤分鐘。"""
    if in_session(event_at, holidays):
        return event_at
    t = event_at.replace(second=0, microsecond=0)
    for _ in range(7 * 24 * 60):
        t += timedelta(minutes=1)
        if in_session(t, holidays):
            return t
    return event_at


def pre_time(event_at: datetime, holidays) -> datetime:
    """事前推播時刻: 盤中事件 = 事件前 30 分;盤後事件 = 最後可交易分鐘 (含) 收盤前 30 分。"""
    if in_session(event_at, holidays):
        return event_at - PRE_LEAD
    t = event_at.replace(second=0, microsecond=0)
    for _ in range(7 * 24 * 60):
        t -= timedelta(minutes=1)
        if in_session(t, holidays):
            return t + timedelta(minutes=1) - PRE_LEAD
    return event_at - PRE_LEAD


def baseline_time(event_at: datetime, holidays) -> datetime:
    """事件前基準時刻 = 事件前最後一個可交易分鐘 (盤中事件 = 事件前 1 分;
    盤後事件如台積電 14:00 → 13:44,休市段無資料)。"""
    return pre_time(event_at, holidays) + PRE_LEAD - timedelta(minutes=1)


# --------------------------------------------------------------------------- #
# 分類 / outcome / 訊息 (純函式)
# --------------------------------------------------------------------------- #
def classify_reaction(move: float, implied, d_iv_w: float, d_pcr: float, px: float = 0.0) -> str:
    """延續: 幅度夠 + 週選 IV 升 + PCR 與價格同向;消化: 週選 IV 降 (crush);其餘混合。"""
    if d_iv_w is not None and d_iv_w <= -IV_MOVE:
        return "消化"
    scale = implied if implied else NO_IMPLIED_FRAC * px
    if not scale or abs(move) < SIZE_FRAC * scale or d_iv_w is None or d_pcr is None:
        return "混合"
    pcr_agrees = (move < 0 and d_pcr > 0) or (move > 0 and d_pcr < 0)
    if d_iv_w >= IV_MOVE and pcr_agrees:
        return "延續(跌)" if move < 0 else "延續(漲)"
    return "混合"


def outcome(px_pre: float, px_5: float, px_60: float, implied, px: float = 0.0) -> str:
    """+5 分方向在 +60 分是否延續 (≥ 0.1×定價幅度)。"""
    d5 = 1 if px_5 > px_pre else -1 if px_5 < px_pre else 0
    if d5 == 0:
        return "flat"
    scale = implied if implied else NO_IMPLIED_FRAC * (px or px_pre)
    delta = (px_60 - px_5) * d5
    if delta >= OUTCOME_FRAC * scale:
        return "continued"
    if delta <= -OUTCOME_FRAC * scale:
        return "reversed"
    return "flat"


def _mmdd_hm(t: datetime) -> str:
    return t.strftime("%m/%d %H:%M")


def pre_message(name: str, event_at: datetime, implied, co_events) -> str:
    lines = ["⏰ %s %s" % (name, _mmdd_hm(event_at))]
    if implied and implied.get("pts"):
        e = implied["expiry"]
        lines.append("→ %s/%s 定價 ±%d點 (%.2f%%)" % (e[4:6], e[6:], round(implied["pts"]), implied["pct"]))
    elif implied:
        e = implied["expiry"]
        lines.append("→ %s/%s 無額外溢價" % (e[4:6], e[6:]))
    else:
        lines.append("→ 無可對照到期")
    if co_events:
        lines.append("同到期另含: " + "、".join(co_events))
    return "\n".join(lines)


def post_message(name: str, minutes: int, move: float, implied, d_iv_w, d_pcr, cls: str) -> str:
    size = ("vs 定價 ±%d (%.2f×)" % (round(implied), abs(move) / implied)) if implied else "(無定價)"
    fmt = lambda v, f: "n/a" if v is None else format(v, f)  # noqa: E731
    return "\n".join(["📊 %s +%d分" % (name, minutes),
                      "實際 %+d %s" % (round(move), size),
                      "週選IV %s · PCR %s" % (fmt(d_iv_w, "+.1f"), fmt(d_pcr, "+.2f")),
                      "→ " + cls])


# --------------------------------------------------------------------------- #
# log
# --------------------------------------------------------------------------- #
def load_log(path: Path = LOG_PATH) -> list:
    if not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def log_delete(path: Path, key: str) -> None:
    rows = [r for r in load_log(path) if r["event_key"] != key]
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def log_upsert(path: Path, key: str, fields: dict) -> None:
    rows = {r["event_key"]: r for r in load_log(path)}
    row = rows.get(key, {f: "" for f in LOG_FIELDS})
    row["event_key"] = key
    row.update({k: ("" if v is None else str(v)) for k, v in fields.items()})
    rows[key] = row
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: r.get("reaction_at", "")))


# --------------------------------------------------------------------------- #
# 資料 (live 與 backfill 共用: 一律以時間 t 查詢)
# --------------------------------------------------------------------------- #
def _tz(t: datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%S+08")


def curve_at(cur, t: datetime):
    """t 前 5 分鐘各到期 ATM IV / forward 平均 (iv_metrics, collector 的 forward 最近履約價)。"""
    cur.execute("""SELECT expiry, avg(atm_iv)*100, avg(forward) FROM iv_metrics
                   WHERE time > %s::timestamptz - interval '5 min' AND time <= %s::timestamptz
                     AND expiry >= to_char(%s::timestamptz AT TIME ZONE 'Asia/Taipei', 'YYYYMMDD')
                   GROUP BY 1 ORDER BY 1""", (_tz(t), _tz(t), _tz(t)))
    rows = [(e, float(iv), float(f) if f else None) for e, iv, f in cur.fetchall() if iv]
    return [(e, round(iv, 2)) for e, iv, _ in rows], {e: f for e, _, f in rows if f}


def _front_monthly(cur, t: datetime):
    cur.execute("""SELECT min(expiry) FROM iv_metrics WHERE product_code='TXO'
                   AND time > %s::timestamptz - interval '1 hour' AND time <= %s::timestamptz
                   AND to_date(expiry,'YYYYMMDD') >= (%s::timestamptz AT TIME ZONE 'Asia/Taipei')::date + 5""",
                (_tz(t), _tz(t), _tz(t)))
    return cur.fetchone()[0]


def metrics_at(cur, t: datetime, weekly: str, window_min: int = 2) -> dict:
    """[t-window, t] 週選 (事件所在到期) ATM IV、前月 ATM IV / PCR / skew 平均。"""
    monthly = _front_monthly(cur, t)
    cur.execute("""SELECT
          avg(atm_iv) FILTER (WHERE expiry=%s)*100,
          avg(atm_iv) FILTER (WHERE expiry=%s)*100,
          avg(pcr_volume) FILTER (WHERE expiry=%s),
          avg(skew_25d) FILTER (WHERE expiry=%s)*100
        FROM iv_metrics WHERE time > %s::timestamptz - make_interval(mins => %s) AND time <= %s::timestamptz""",
                (weekly, monthly, monthly, monthly, _tz(t), window_min, _tz(t)))
    iv_w, iv_m, pcr, skew = cur.fetchone()
    f = lambda v: None if v is None else round(float(v), 3)  # noqa: E731
    return {"iv_w": f(iv_w), "iv_m": f(iv_m), "pcr": f(pcr), "skew": f(skew)}


def price_at(cur, t: datetime):
    """t 以前最後一筆 TXF 近月成交 (取該時段成交最多的 TXF 月合約)。"""
    cur.execute("""SELECT symbol FROM ticks WHERE symbol ~ '^TXF[A-L][0-9]$'
                   AND time > %s::timestamptz - interval '30 min' AND time <= %s::timestamptz
                   GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""", (_tz(t), _tz(t)))
    r = cur.fetchone()
    if not r:
        return None
    cur.execute("""SELECT price FROM ticks WHERE symbol=%s AND time <= %s::timestamptz
                   AND time > %s::timestamptz - interval '30 min' ORDER BY time DESC LIMIT 1""",
                (r[0], _tz(t), _tz(t)))
    p = cur.fetchone()
    return float(p[0]) if p else None


def _d(a, b):
    return None if a is None or b is None else round(a - b, 3)


# --------------------------------------------------------------------------- #
# 階段執行
# --------------------------------------------------------------------------- #
def index_events(start: date, end: date) -> list:
    from event_calendar import events_between, load_events
    return events_between(load_events(), start, end, impact="index", types={"earnings", "macro"})


def event_key(ev: dict) -> str:
    return "%s|%s" % (ev["date"], ev["symbol"])


def run_stage(cur, ev: dict, stage: str, holidays, all_events: list) -> tuple:
    """回傳 (訊息或 None, log 欄位)。"""
    from event_calendar import event_datetime
    from iv_term import implied_event_move
    at = event_datetime(ev)
    react = reaction_time(at, holidays)
    key = event_key(ev)
    prev = next((r for r in load_log() if r["event_key"] == key), {})
    base = {"kind": ev["symbol"] if ev["type"] == "macro" else "earnings_" + ev["symbol"], "name": ev["name"],
            "event_at": at.isoformat(timespec="minutes"), "reaction_at": react.isoformat(timespec="minutes"),
            "data_quality": "pre_fix" if at.date() < FIX_DATE else "ok"}
    if stage == "pre":
        t = pre_time(at, holidays)
        curve, fwd = curve_at(cur, t)
        ref = price_at(cur, t) or (next(iter(fwd.values()), 0.0))
        m = implied_event_move(curve, fwd, ("TXF", ref), t, at, holidays) if curve else None
        co = []
        if m:
            settle = datetime.combine(datetime.strptime(m["expiry"], "%Y%m%d").date(), time(13, 30))
            co = [e["name"] for e in all_events
                  if e is not ev and event_key(e) != key and at <= event_datetime(e) < settle]
        fields = dict(base, implied_expiry=(m or {}).get("expiry", ""),
                      implied_pts=round(m["pts"]) if m and m["pts"] else "",
                      implied_pct=round(m["pct"], 2) if m and m["pts"] else "",
                      co_events="、".join(co))
        return pre_message(ev["name"], at, m, co), fields

    weekly = prev.get("implied_expiry") or ""
    implied = float(prev["implied_pts"]) if prev.get("implied_pts") else None
    if not prev.get("px_pre"):                                 # 事件前基準 (最後可交易 5 分鐘)
        bt = baseline_time(at, holidays)
        b = metrics_at(cur, bt, weekly, window_min=5)
        px_pre = price_at(cur, bt + timedelta(seconds=59))
        base.update(px_pre=px_pre, iv_w_pre=b["iv_w"], iv_m_pre=b["iv_m"], pcr_pre=b["pcr"], skew_pre=b["skew"])
    else:
        px_pre = float(prev["px_pre"])
        b = {k: (float(prev[k + "_pre"]) if prev.get(k + "_pre") else None) for k in ("iv_w", "iv_m", "pcr", "skew")}
    mins = STAGES[stage]
    t = react + timedelta(minutes=mins)
    px = price_at(cur, t)
    if stage == "60":
        px5 = float(prev["px_5"]) if prev.get("px_5") else None
        oc = outcome(px_pre, px5, px, implied, px_pre) if None not in (px_pre, px5, px) else ""
        return None, dict(base, px_60=px, outcome_60=oc)
    m = metrics_at(cur, t, weekly)
    move = (px - px_pre) if None not in (px, px_pre) else None
    d_iv, d_pcr = _d(m["iv_w"], b["iv_w"]), _d(m["pcr"], b["pcr"])
    cls = classify_reaction(move, implied, d_iv, d_pcr, px_pre or 0) if move is not None else "資料不足"
    fields = dict(base, **{"px_" + stage: px, "iv_w_" + stage: m["iv_w"], "iv_m_" + stage: m["iv_m"],
                           "pcr_" + stage: m["pcr"], "skew_" + stage: m["skew"], "class_" + stage: cls})
    msg = post_message(ev["name"], mins, move or 0, implied, d_iv, d_pcr, cls)
    return msg, fields


def stage_time(ev: dict, stage: str, holidays) -> datetime:
    from event_calendar import event_datetime
    at = event_datetime(ev)
    return pre_time(at, holidays) if stage == "pre" else reaction_time(at, holidays) + timedelta(minutes=STAGES[stage])


def _push(msg: str, now: datetime) -> None:
    import redis
    redis.Redis().xadd("claude:inbox", {
        "ts": now.strftime("%Y-%m-%d %H:%M"), "from": "event_window", "topic": "event-window",
        "tags": "event,iv", "as_of": now.date().isoformat(),
        "msg": msg + "\n(分析標註·不構成交易指令)"})


def tick(now: datetime, dry_run: bool = False) -> int:
    import psycopg2
    import redis
    from ascii_dashboard import DB
    from iv_term import load_holidays
    hol = load_holidays()
    evs = index_events(now.date() - timedelta(days=4), now.date() + timedelta(days=3))
    if not evs:
        return 0
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    r = redis.Redis(decode_responses=True)
    for ev in evs:
        key = event_key(ev)
        done = r.smembers(DONE_KEY % key) or set()
        for stage in STAGES:
            st = stage_time(ev, stage, hol)
            if stage in done or not (st <= now < st + STAGE_GRACE):
                continue
            msg, fields = run_stage(cur, ev, stage, hol, evs)
            if dry_run:
                print("[dry]", key, stage, fields, "\n" + (msg or ""))
                continue
            log_upsert(LOG_PATH, key, fields)
            if msg:
                _push(msg, now)
            r.sadd(DONE_KEY % key, stage)
            r.expire(DONE_KEY % key, DONE_TTL_S)
    return 0


def backfill(start: date = date(2026, 7, 8)) -> int:
    """以歷史資料重播 start 起、已過 +60 分的事件 (不推播)。"""
    import psycopg2
    from ascii_dashboard import DB
    from iv_term import load_holidays
    hol = load_holidays()
    now = datetime.now()
    evs = index_events(start, now.date())
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    n = 0
    for ev in evs:
        if stage_time(ev, "60", hol) > now:
            continue
        log_delete(LOG_PATH, event_key(ev))                     # 重播 = 整列重算
        for stage in STAGES:
            _, fields = run_stage(cur, ev, stage, hol, evs)
            log_upsert(LOG_PATH, event_key(ev), fields)
        n += 1
        row = next(r for r in load_log() if r["event_key"] == event_key(ev))
        print("%-20s implied=%-5s +5=%-8s +15=%-8s outcome=%s %s" % (
            event_key(ev), row["implied_pts"], row["class_5"], row["class_15"], row["outcome_60"],
            row["data_quality"]))
    print("backfilled %d events → %s" % (n, LOG_PATH))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="tick", choices=["tick", "backfill"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", help="模擬時間 YYYY-MM-DDTHH:MM (搭配 --dry-run)")
    a = ap.parse_args(argv)
    if a.cmd == "backfill":
        return backfill()
    return tick(datetime.fromisoformat(a.now) if a.now else datetime.now(), dry_run=a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
