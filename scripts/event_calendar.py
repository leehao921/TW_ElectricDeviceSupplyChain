#!/usr/bin/env python3
"""event_calendar.py — 法說/財報等事件日期的紀律性記錄 (plan: docs/plans/2026-10-13-event-calendar.md)

來源不手打: MOPS 重訊「法人說明會」公告 (news_items source_tier=1) body 為固定格式
    1.召開法人說明會之日期：115/10/15 2.召開法人說明會之時間：14 時 00 分 3.…地點：… 4.…擇要訊息：…
→ 解析成 data/event_calendar.csv (git 追蹤, 真相來源; upsert key = date+symbol+type)。

    python scripts/event_calendar.py sync                 # news_items → CSV (冪等)
    python scripts/event_calendar.py list [--from D --to D] [--index]
    python scripts/event_calendar.py add 2026-10-28 macro FOMC --time 02:00 --impact index
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CAL_PATH = REPO / "data" / "event_calendar.csv"
FIELDS = ["date", "time", "type", "name", "symbol", "impact", "source", "detail"]
TYPES = {"earnings", "investor_conf", "macro", "settlement"}
# 台指權值前段: 這些公司的法說/財報視為指數級事件 (IV 期限表對照用)
INDEX_MOVERS = {"2330", "2317", "2454", "2308", "2382", "2881", "2882", "2303", "3711", "2412", "2891", "2886"}

_ROC = r"(\d{3})/(\d{1,2})/(\d{1,2})"
_RE_DATE = re.compile(r"召開法人說明會之日期[:：]\s*" + _ROC)
_RE_TIME = re.compile(r"召開法人說明會之時間[:：]\s*(\d{1,2})\s*時\s*(\d{1,2})\s*分")
_RE_VENUE = re.compile(r"召開法人說明會之地點[:：]\s*(.*?)\s*4\.")
_RE_SUMMARY = re.compile(r"擇要訊息[:：]\s*(.*?)\s*5\.")
_EARNINGS_KW = re.compile(r"財務報告|財報|營運結果|業績展望|營運成果|季營運|年度營運")


def parse_mops_body(body: str):
    """MOPS 法說公告 body → {date, time, venue, summary};無日期 → None。"""
    m = _RE_DATE.search(body or "")
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    t = _RE_TIME.search(body)
    v = _RE_VENUE.search(body)
    s = _RE_SUMMARY.search(body)
    return {"date": date(y + 1911, mo, d),
            "time": "%02d:%02d" % (int(t.group(1)), int(t.group(2))) if t else "",
            "venue": v.group(1).strip() if v else "",
            "summary": re.sub(r"\s+", " ", s.group(1)).strip() if s else ""}


def classify(summary: str) -> str:
    """自辦財報/營運結果發布 → earnings;受邀/應邀參加券商活動 (即使提到財務報告) → investor_conf。"""
    if re.search(r"受邀|邀請|應邀", summary):
        return "investor_conf"
    return "earnings" if _EARNINGS_KW.search(summary) else "investor_conf"


def row_from_news(n: dict):
    p = parse_mops_body(n.get("body") or "")
    if not p or not n.get("ticker"):
        return None
    summary = re.split(r"\(?\d\)?\s*參加方式", p["summary"])[0]      # 去掉「(2)參加方式：網址」雜訊
    summary = re.sub(r"^\(1\)\s*", "", summary).strip()
    detail = " | ".join(x for x in (p["venue"], summary) if x)
    return {"date": p["date"].isoformat(), "time": p["time"], "type": classify(p["summary"]),
            "name": (n.get("company_name") or n["ticker"]).strip(), "symbol": str(n["ticker"]).strip(),
            "impact": "index" if str(n["ticker"]).strip() in INDEX_MOVERS else "stock",
            "source": "mops:%s" % n.get("news_uid", ""), "detail": detail[:200]}


def load_events(path: Path = CAL_PATH) -> list:
    if not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _key(r: dict):
    return (r["date"], r["symbol"])            # 一家公司一天一筆 (重分類時覆寫)


def upsert(path: Path, rows: list) -> int:
    """合併進 CSV (同 date+symbol 覆寫), 依 date,symbol 排序寫回;回傳新增筆數。"""
    cur = {_key(r): r for r in load_events(path)}
    added = 0
    for r in rows:
        if r["type"] not in TYPES:
            raise ValueError("bad type %r" % r["type"])
        k = _key(r)
        added += k not in cur
        cur[k] = {f: str(r.get(f, "")) for f in FIELDS}
    out = sorted(cur.values(), key=lambda r: (r["date"], r["symbol"]))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    return added


def events_between(events: list, start: date, end: date, impact=None, types=None) -> list:
    out = []
    for e in events:
        d = date.fromisoformat(e["date"])
        if start <= d <= end and (impact is None or e.get("impact") == impact) \
                and (types is None or e.get("type") in types):
            out.append(e)
    return sorted(out, key=lambda e: (e["date"], e.get("time", "")))


def event_datetime(e: dict) -> datetime:
    """事件時刻 (無時間 → 當日 13:30 視為盤中)。"""
    hm = e.get("time") or "13:30"
    return datetime.strptime(e["date"] + " " + hm, "%Y-%m-%d %H:%M")


NAUTILUS = REPO.parent / "nautilus-shioaji"
MACRO_KINDS = {"NFP", "CPI", "FOMC", "TW_EXPORT", "US_MIDTERM", "TW_ELECTION"}


def macro_rows(events: list) -> list:
    """nautilus macro_calendar.EVENTS (JSON) → calendar rows。總經 → type=macro symbol=<kind>;
    TSMC_EARN / TW_EARN_<code> → earnings (補 MOPS 收錄前的歷史法說)。"""
    out = []
    for e in events:
        kind, at = e["kind"], datetime.fromisoformat(e["at"])
        if kind in MACRO_KINDS:
            typ, sym = "macro", kind
        elif kind == "TSMC_EARN":
            typ, sym = "earnings", "2330"
        elif kind.startswith("TW_EARN_"):
            typ, sym = "earnings", kind[len("TW_EARN_"):]
        else:
            continue
        out.append({"date": at.strftime("%Y-%m-%d"), "time": at.strftime("%H:%M"), "type": typ,
                    "name": e["label"], "symbol": sym,
                    "impact": "index" if (typ == "macro" or sym in INDEX_MOVERS) else "stock",
                    "source": "nautilus:%s" % e["id"], "detail": ""})
    return out


def insert_missing(path: Path, rows: list) -> int:
    """只新增不存在的 key (不覆寫 MOPS 來源的列);回傳新增筆數。"""
    have = {_key(r) for r in load_events(path)}
    new = [r for r in rows if _key(r) not in have]
    return upsert(path, new) if new else 0


def sync_macro(path: Path = CAL_PATH) -> int:
    """以 nautilus venv 匯出 macro_calendar.EVENTS (官方來源手工維護, 一處維護) → CSV。"""
    import json
    import subprocess
    code = ("import json;from nautilus_shioaji.agent import macro_calendar as mc;"
            "print(json.dumps([{'id':e.id,'kind':e.kind,'label':e.label,"
            "'at':mc.at_taipei(e).isoformat()} for e in mc.EVENTS]))")
    out = subprocess.run([str(NAUTILUS / ".venv" / "bin" / "python"), "-c", code], cwd=NAUTILUS,
                         capture_output=True, text=True, timeout=60, check=True).stdout
    added = insert_missing(path, macro_rows(json.loads(out)))
    print("sync-macro: %d new → %s" % (added, path))
    return added


# --------------------------------------------------------------------------- #
def sync(path: Path = CAL_PATH, since_days: int = 400) -> int:
    import psycopg2
    sys.path.insert(0, str(REPO / "scripts"))
    from ascii_dashboard import DB
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("""SELECT news_uid, ticker, company_name, body FROM news_items
                   WHERE source_tier = 1 AND title ~ '法人說明會' AND body IS NOT NULL
                     AND announce_date >= %s""", (date.today() - timedelta(days=since_days),))
    rows = [r for r in (row_from_news(dict(zip(("news_uid", "ticker", "company_name", "body"), x)))
                        for x in cur.fetchall()) if r]
    added = upsert(path, rows)
    print("sync: %d filings parsed, %d new → %s" % (len(rows), added, path))
    try:
        sync_macro(path)
    except Exception as e:                       # noqa: BLE001 — 總經同步失敗不擋 MOPS
        print("[warn] sync-macro failed: %s" % e, file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync")
    ls = sub.add_parser("list")
    ls.add_argument("--from", dest="d0", default=date.today().isoformat())
    ls.add_argument("--to", dest="d1", default=(date.today() + timedelta(days=30)).isoformat())
    ls.add_argument("--index", action="store_true")
    ad = sub.add_parser("add")
    ad.add_argument("date"); ad.add_argument("type", choices=sorted(TYPES)); ad.add_argument("name")
    ad.add_argument("--symbol", default=""); ad.add_argument("--time", default="")
    ad.add_argument("--impact", default="index", choices=["index", "stock"]); ad.add_argument("--detail", default="")
    a = ap.parse_args(argv)
    if a.cmd == "sync":
        return sync()
    if a.cmd == "add":
        date.fromisoformat(a.date)
        n = upsert(CAL_PATH, [{"date": a.date, "time": a.time, "type": a.type, "name": a.name,
                               "symbol": a.symbol, "impact": a.impact, "source": "manual", "detail": a.detail}])
        print("added" if n else "updated")
        return 0
    ev = events_between(load_events(), date.fromisoformat(a.d0), date.fromisoformat(a.d1),
                        impact="index" if a.index else None)
    for e in ev:
        print("%s %5s %-13s %-10s %-6s %s" % (e["date"], e["time"], e["type"], e["name"], e["symbol"], e["detail"][:60]))
    print("%d events" % len(ev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
