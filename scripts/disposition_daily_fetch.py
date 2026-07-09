"""disposition_daily_fetch.py — Daily fetch of TWSE + TPEx disposition (處置) stocks.

Fires 08:35 Mon-Fri (before buy-list-daily @ 08:50) via launchd
`com.lulala.disposition-daily`.

Data sources (both verified 2026-07-05, no auth):
    TWSE: https://www.twse.com.tw/rwd/zh/announcement/punish?response=json&yy={ROC}&mm={MM}
    TPEx: https://www.tpex.org.tw/openapi/v1/tpex_disposal_information

Writes `data/disposition_current.json` (overwritten daily) with currently
active disposition periods. Cross-references portfolio picks/watch
(from `data/buy_list_state.json`) and BB follow-through tracked
(from `data/bb_followthrough_state.json`); if intersection non-empty,
pushes digest to claude:inbox topic=disposition-alert.

CLI:
    python scripts/disposition_daily_fetch.py            # live
    python scripts/disposition_daily_fetch.py --dry-run  # no state write, no push
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "data" / "disposition_current.json"
BUY_LIST_STATE = REPO / "data" / "buy_list_state.json"
BB_STATE = REPO / "data" / "bb_followthrough_state.json"

TRACK_STATE_PATH = REPO / "data" / "disposition_tracking_state.json"
TRACK_HISTORY_PATH = REPO / "data" / "disposition_tracking_history.json"
POST_TRACK_DAYS = 20      # graduate at T+20 after release
MIN_STATS_SAMPLES = 10    # below this, show "樣本累積中"

INBOX_STREAM = "claude:inbox"
UA = "Mozilla/5.0"


# ------------------------------------------------------------------ #
# TWSE / TPEx fetch
# ------------------------------------------------------------------ #
def _get_json(url: str, timeout: int = 15) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"[err] fetch {url}: {e}", file=sys.stderr)
        return None


def fetch_twse_punish(year_ce: int, month: int) -> list[list]:
    roc = year_ce - 1911
    url = f"https://www.twse.com.tw/rwd/zh/announcement/punish?response=json&yy={roc}&mm={month:02d}"
    data = _get_json(url)
    if not data or "data" not in data:
        return []
    return data.get("data", [])


def fetch_tpex_disposal() -> list[dict]:
    url = "https://www.tpex.org.tw/openapi/v1/tpex_disposal_information"
    data = _get_json(url)
    if not data or not isinstance(data, list):
        return []
    return data


# ------------------------------------------------------------------ #
# ROC date parsing
# ------------------------------------------------------------------ #
def roc_slash_to_iso(s: str) -> str | None:
    """115/06/24 → 2026-06-24."""
    s = s.strip()
    m = re.match(r"^(\d{2,3})/(\d{2})/(\d{2})$", s)
    if not m:
        return None
    return f"{int(m.group(1))+1911}-{m.group(2)}-{m.group(3)}"


def roc_compact_to_iso(s: str) -> str | None:
    """1150706 → 2026-07-06."""
    s = s.strip()
    if not s.isdigit() or len(s) not in (7,):
        return None
    return f"{int(s[:3])+1911}-{s[3:5]}-{s[5:7]}"


def parse_twse_period(period_str: str) -> tuple[str, str] | None:
    """115/06/24～115/07/07 → (2026-06-24, 2026-07-07)."""
    for sep in ("～", "~"):
        if sep in period_str:
            a, b = period_str.split(sep, 1)
            iso_a = roc_slash_to_iso(a)
            iso_b = roc_slash_to_iso(b)
            if iso_a and iso_b:
                return iso_a, iso_b
    return None


def parse_tpex_period(period_str: str) -> tuple[str, str] | None:
    """1150706~1150717 → (2026-07-06, 2026-07-17)."""
    for sep in ("~", "～"):
        if sep in period_str:
            a, b = period_str.split(sep, 1)
            iso_a = roc_compact_to_iso(a)
            iso_b = roc_compact_to_iso(b)
            if iso_a and iso_b:
                return iso_a, iso_b
    return None


# ------------------------------------------------------------------ #
# Aggregate & filter
# ------------------------------------------------------------------ #
def collect_active(today_iso: str) -> tuple[dict[str, dict], int, int]:
    """Return {ticker: entry}, twse_raw, tpex_raw counts."""
    active: dict[str, dict] = {}
    today = date.today()

    # TWSE: fetch current + previous month to cover cross-month periods
    curr_yy, curr_mm = today.year, today.month
    prev_yy, prev_mm = (curr_yy, curr_mm - 1) if curr_mm > 1 else (curr_yy - 1, 12)
    twse_rows = fetch_twse_punish(curr_yy, curr_mm) + fetch_twse_punish(prev_yy, prev_mm)

    for row in twse_rows:
        if len(row) < 8:
            continue
        ticker = str(row[2]).strip()
        # only 4-digit numeric (skip warrants)
        if not (ticker.isdigit() and len(ticker) == 4):
            continue
        period = parse_twse_period(str(row[6]))
        if not period:
            continue
        start_iso, end_iso = period
        if not (start_iso <= today_iso <= end_iso):
            continue
        # keep the one with latest start (in case of multiple periods same ticker)
        prev = active.get(ticker)
        if prev and prev["start"] > start_iso:
            continue
        active[ticker] = {
            "name": str(row[3]).strip(),
            "start": start_iso,
            "end": end_iso,
            "condition": str(row[5]).strip(),
            "action": str(row[7]).strip(),
            "source": "TWSE",
        }

    # TPEx: single endpoint returns current + recent
    tpex_rows = fetch_tpex_disposal()
    for r in tpex_rows:
        ticker = str(r.get("SecuritiesCompanyCode", "")).strip()
        if not (ticker.isdigit() and len(ticker) == 4):
            continue
        period = parse_tpex_period(str(r.get("DispositionPeriod", "")))
        if not period:
            continue
        start_iso, end_iso = period
        if not (start_iso <= today_iso <= end_iso):
            continue
        prev = active.get(ticker)
        if prev and prev["start"] > start_iso:
            continue
        active[ticker] = {
            "name": str(r.get("CompanyName", "")).strip(),
            "start": start_iso,
            "end": end_iso,
            "condition": str(r.get("DisposalCondition", "")).strip()[:60],
            "action": str(r.get("DispositionReasons", "")).strip()[:60],
            "source": "TPEx",
        }

    return active, len(twse_rows), len(tpex_rows)


# ------------------------------------------------------------------ #
# State I/O
# ------------------------------------------------------------------ #
def save_state(active: dict, twse_n: int, tpex_n: int, path: Path) -> None:
    payload = {
        "as_of": date.today().isoformat(),
        "fetched_at": datetime.now().astimezone().isoformat(),
        "active": active,
        "raw_count_twse": twse_n,
        "raw_count_tpex": tpex_n,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


# ------------------------------------------------------------------ #
# Cross-reference portfolio + BB follow-through
# ------------------------------------------------------------------ #
def cross_reference(active: dict[str, dict]) -> tuple[list, list, list]:
    """Return (picks_hits, watches_hits, bb_hits)."""
    picks_hits = []
    watches_hits = []
    bb_hits = []

    buy_state = load_json(BUY_LIST_STATE) or {}
    for p in buy_state.get("picks", []):
        t = p.get("ticker")
        if t in active:
            picks_hits.append((p, active[t]))
    for w in buy_state.get("watch_list", []):
        t = w.get("ticker")
        if t in active:
            watches_hits.append((w, active[t]))

    bb_state = load_json(BB_STATE) or {}
    for t, entry in bb_state.get("tracked", {}).items():
        if t in active:
            bb_hits.append((t, entry, active[t]))

    return picks_hits, watches_hits, bb_hits


# ------------------------------------------------------------------ #
# Digest & push
# ------------------------------------------------------------------ #
def build_digest(active: dict, picks_hits: list, watches_hits: list, bb_hits: list,
                 twse_n: int, tpex_n: int) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# ⚠️ 處置股 巡檢 {now}"]
    lines.append(f"**Active {len(active)} 檔** (TWSE 抓 {twse_n} 筆、TPEx 抓 {tpex_n} 筆)")
    lines.append("")

    if picks_hits:
        lines.append(f"## 🚨 Portfolio Picks 中處置 ({len(picks_hits)} 檔)")
        for p, d in picks_hits:
            days_left = (date.fromisoformat(d["end"]) - date.today()).days
            lines.append(
                f"- **{p['ticker']} {p['name']}** (T{p.get('tier','?')} {p.get('weight_pct','?')}%) — "
                f"{d['start']}~{d['end']} ({days_left}d) · {d['action']} · **{d['condition']}** [{d['source']}]"
            )
        lines.append("")

    if watches_hits:
        lines.append(f"## ⚠️ Portfolio Watch 中處置 ({len(watches_hits)} 檔)")
        for w, d in watches_hits:
            days_left = (date.fromisoformat(d["end"]) - date.today()).days
            lines.append(
                f"- **{w['ticker']} {w['name']}** — {d['start']}~{d['end']} ({days_left}d) · {d['action']} [{d['source']}]"
            )
        lines.append("")

    if bb_hits:
        lines.append(f"## 📊 BB 追蹤中處置 ({len(bb_hits)} 檔) — signal 不可信")
        for t, entry, d in bb_hits:
            days_left = (date.fromisoformat(d["end"]) - date.today()).days
            lines.append(
                f"- **{t} {entry.get('name','?')}** BB D+{entry.get('days_tracked',0)} 累計{entry.get('cumret_pct',0):+.1f}% — "
                f"處置 {d['start']}~{d['end']} ({days_left}d) · **量能失真、BB signal 不可信**"
            )
        lines.append("")

    if not (picks_hits or watches_hits or bb_hits):
        lines.append("_✅ Portfolio + BB tracked 無檔子在處置期間_")
        lines.append("")

    # Full list (compact)
    lines.append(f"## 📋 全處置名單 ({len(active)} 檔)")
    for t, d in sorted(active.items(), key=lambda x: x[1]["end"]):
        days_left = (date.fromisoformat(d["end"]) - date.today()).days
        lines.append(f"- {t} {d['name']} ({d['source']}): {d['start']}~{d['end']} ({days_left}d 剩)")

    lines.append("")
    lines.append(f"*源: scripts/disposition_daily_fetch.py · state {STATE_PATH.name}*")
    return "\n".join(lines)


def push_inbox(msg: str) -> bool:
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.xadd(INBOX_STREAM, {"topic": "disposition-alert", "msg": msg,
                              "tags": "twse,tpex,disposition,daily,alert"})
        return True
    except Exception as e:
        print(f"[err] inbox push failed: {e}", file=sys.stderr)
        return False


# ------------------------------------------------------------------ #
# Lifecycle tracking — enter → during → release → post → history
# ------------------------------------------------------------------ #
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}


def count_to_n(action_label: str | None) -> int:
    """Map '第二次處置' → 2. Non-count text or None → 1."""
    if not action_label:
        return 1
    import re as _re
    m = _re.search(r"第([一二三四五六七八九])次處置", action_label)
    if not m:
        return 1
    return _CN_NUM.get(m.group(1), 1)


def record_entry(ticker: str, disp: dict, market: dict, as_of: str) -> dict:
    """Assemble a new tracking-state entry at disposition entry."""
    close = market.get("enter_close")
    return {
        "ticker": ticker, "name": disp.get("name", ""),
        "enter_date": as_of, "disp_start": disp.get("start"), "disp_end": disp.get("end"),
        "condition": disp.get("condition"), "count_label": disp.get("action"),
        "count_n": count_to_n(disp.get("action")), "source": disp.get("source"),
        "runup_5d_pct": market.get("runup_5d_pct"), "runup_20d_pct": market.get("runup_20d_pct"),
        "foreign_5d_at_enter": market.get("foreign_5d"), "foreign_20d_at_enter": market.get("foreign_20d"),
        "enter_close": close,
        "during": [{"d": as_of, "close": close, "cumret_pct": 0.0, "foreign_1d": market.get("foreign_1d")}],
        "release_date": None, "release_close": None,
        "post": {"t1": None, "t5": None, "t20": None},
    }


def append_during(entry: dict, snap: dict, as_of: str) -> None:
    """Append a during-disposition daily snapshot. No-op if as_of already recorded (idempotent)."""
    if any(s["d"] == as_of for s in entry["during"]):
        return
    base = entry["enter_close"]
    close = snap.get("close")
    cumret = round((close - base) / base * 100, 2) if base and close else None
    entry["during"].append({"d": as_of, "close": close, "cumret_pct": cumret,
                            "foreign_1d": snap.get("foreign_1d")})


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true", help="No state write, no push")
    p.add_argument("--state", default=str(STATE_PATH))
    args = p.parse_args()

    today_iso = date.today().isoformat()
    active, twse_n, tpex_n = collect_active(today_iso)
    print(f"[info] active disposition: {len(active)} (TWSE raw {twse_n}, TPEx raw {tpex_n})", file=sys.stderr)

    picks_hits, watches_hits, bb_hits = cross_reference(active)
    print(f"[info] picks hit: {len(picks_hits)}, watch hit: {len(watches_hits)}, bb tracked hit: {len(bb_hits)}", file=sys.stderr)

    digest = build_digest(active, picks_hits, watches_hits, bb_hits, twse_n, tpex_n)
    print(digest)

    if args.dry_run:
        print("\n[dry-run] state NOT saved, inbox NOT pushed", file=sys.stderr)
        return 0

    save_state(active, twse_n, tpex_n, Path(args.state))
    print(f"[ok] state saved to {args.state}", file=sys.stderr)

    # Push inbox only if there's a portfolio/BB intersection
    if picks_hits or watches_hits or bb_hits:
        push_inbox(digest)
        print("[ok] pushed to claude:inbox topic=disposition-alert", file=sys.stderr)
    else:
        print("[skip] no portfolio/BB intersection, not pushing", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
