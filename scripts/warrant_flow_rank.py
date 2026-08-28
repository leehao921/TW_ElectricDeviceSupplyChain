#!/usr/bin/env python3
"""權證資金流排行 + 後續價量追蹤 (v1: 上市).

流程: (1) docker exec 觸發 database repo 的 warrant_flow_daily collector (幂等)
      (2) 讀 warrant_flow_daily 最新日 → 佈空/佈多 Top N
      (3) 追蹤: 進榜 (top10) 即記錄 enter_close, 之後填 T+1/T+5/T+20
          (用歷史第 N 個交易日收盤, 沿用 disposition record_post 修正後的語意)
      (4) 寫 analysis/warrant_flow_<date>.md + 推 inbox topic=warrant-flow

score 為內外盤 proxy (認購±成交值 − 認售±成交值), 單位: 元; 顯示用萬。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "data" / "warrant_flow_state.json"
HISTORY_PATH = REPO / "data" / "warrant_flow_history.json"
OUT_DIR = REPO / "analysis"
TOP_N_SHOW = 15
TOP_N_TRACK = 10

DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")


# --------------------------------------------------------------------------- #
# pure functions
# --------------------------------------------------------------------------- #
MAX_THEMES_SHOWN = 3


def label(t: str, labels: dict | None) -> str:
    """'3008' → '3008 大立光' (無對映回裸代號) — 與其他 routine 輸出口徑一致."""
    info = (labels or {}).get(t)
    return f"{t} {info['name']}" if info and info.get("name") else t


def label_detail(t: str, labels: dict | None) -> str:
    """報告表格用: 名稱 + 產業 + 題材 (最多 3 個)."""
    info = (labels or {}).get(t)
    if not info:
        return "—"
    parts = [info.get("name") or "—"]
    if info.get("sector"):
        parts.append(info["sector"])
    themes = (info.get("themes") or [])[:MAX_THEMES_SHOWN]
    if themes:
        parts.append("/".join(themes))
    return " · ".join(parts)


def load_labels() -> dict:
    """ticker → {name, sector, themes[]} — Pilot_Reports 檔名 + themes/ 成分 + 持倉檔 fallback."""
    import glob
    import os
    import re as _re
    labels: dict[str, dict] = {}
    for fp in glob.glob(str(REPO / "Pilot_Reports" / "*" / "*.md")):
        m = _re.match(r"(\d{4})_(.+)\.md$", os.path.basename(fp))
        if m:
            labels[m.group(1)] = {"name": m.group(2),
                                  "sector": os.path.basename(os.path.dirname(fp)),
                                  "themes": []}
    for fp in glob.glob(str(REPO / "themes" / "*.md")):
        theme = os.path.basename(fp)[:-3].replace("_", " ")
        if theme == "README":
            continue
        for tk in set(_re.findall(r"\*\*(\d{4}) ", open(fp).read())):
            if tk in labels:
                labels[tk]["themes"].append(theme)
    try:  # 非電子股 fallback 1: 持倉檔名稱
        hp = json.loads((REPO / "data" / "portfolio_holdings.json").read_text())
        for x in hp.get("holdings", []):
            labels.setdefault(str(x.get("ticker")), {"name": x.get("name", ""),
                                                     "sector": "", "themes": []})
    except Exception:
        pass
    # 非電子股 fallback 2: 常見跨產業標的 (OHLCV 日更名單內的航運等)
    for tk, nm, sec in (("2603", "長榮", "航運"), ("2609", "陽明", "航運"),
                        ("2615", "萬海", "航運"), ("2610", "華航", "航空"),
                        ("2618", "長榮航", "航空"), ("1303", "南亞", "塑化"),
                        ("6505", "台塑化", "塑化"), ("2882", "國泰金", "金融"),
                        ("2881", "富邦金", "金融"), ("2891", "中信金", "金融")):
        labels.setdefault(tk, {"name": nm, "sector": sec, "themes": []})
    return labels


def rank_top(rows: list[dict], n: int, side: str) -> list[dict]:
    if side == "short":
        return sorted([r for r in rows if r["score"] < 0],
                      key=lambda r: r["score"])[:n]
    return sorted([r for r in rows if r["score"] > 0],
                  key=lambda r: -r["score"])[:n]


def update_tracking(state: dict, shorts: list[dict], longs: list[dict],
                    as_of: str, close_fn, nth_close_fn) -> list[dict]:
    """進榜記錄 + T+N 回填 + t20 畢業. 回傳本輪畢業名單."""
    tracked = state.setdefault("tracked", {})
    for side, ranks in (("short", shorts), ("long", longs)):
        for r in ranks:
            u = r["underlying"]
            if u in tracked:
                continue
            c = close_fn(u, as_of)
            if not c:
                continue
            tracked[u] = {"side": side, "enter_date": as_of, "enter_close": c,
                          "score_at_enter": r["score"],
                          "post": {"t1": None, "t5": None, "t20": None}}
    graduated = []
    for u, e in list(tracked.items()):
        if e["enter_date"] == as_of:
            continue
        base = e["enter_close"]
        for nn, key in ((1, "t1"), (5, "t5"), (20, "t20")):
            if e["post"].get(key) is None:
                px = nth_close_fn(u, e["enter_date"], nn)
                if px:
                    e["post"][key] = round((px / base - 1) * 100, 2)
        if e["post"].get("t20") is not None:
            graduated.append({"ticker": u, **e})
            del tracked[u]
    return graduated


def hit_stats(history: list[dict]) -> dict:
    """佈空榜 T+5 下跌 / 佈多榜 T+5 上漲 = 命中."""
    out = {}
    for side, cond in (("short", lambda x: x < 0), ("long", lambda x: x > 0)):
        done = [h for h in history
                if h.get("side") == side and h.get("post", {}).get("t5") is not None]
        out[side] = (sum(1 for h in done if cond(h["post"]["t5"])), len(done))
    return out


def render_summary(as_of: str, shorts: list[dict], longs: list[dict],
                   hits: dict, labels: dict | None = None) -> str:
    def fmt(rows):
        return " / ".join(f"{label(r['underlying'], labels)} {r['score']/1e4:+,.0f}萬"
                          for r in rows[:5])
    s_hit = hits.get("short", (0, 0))
    l_hit = hits.get("long", (0, 0))
    lines = [f"權證資金流 {as_of} (上市, 內外盤 proxy)",
             f"佈空 top: {fmt(shorts)}",
             f"佈多 top: {fmt(longs)}"]
    if s_hit[1] or l_hit[1]:
        lines.append(f"歷史命中 (T+5): 佈空榜跌 {s_hit[0]}/{s_hit[1]} · 佈多榜漲 {l_hit[0]}/{l_hit[1]}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #
def run_collector(as_of: str) -> None:
    """收當日 + 重收前一交易日 (冪等) — TPEx OpenAPI 快照更新晚於 17:40,
    當日 run 常只併到 TWSE;隔日重收自動補齊 TPEx 段 (2026-08-25 實災 423→695 檔)."""
    from datetime import timedelta
    d = date.fromisoformat(as_of)
    prev = d - timedelta(days=3 if d.weekday() == 0 else 1)
    for target in (prev.isoformat(), as_of):
        try:
            subprocess.run(
                ["docker", "exec", "-e", "PYTHONPATH=/opt/tmf:/opt/tmf/src",
                 "tmf-stock-daily-collector", "python",
                 "scripts/collectors/warrant_flow_daily.py", "--date", target],
                check=True, capture_output=True, timeout=180)
        except Exception as e:
            print(f"[warn] collector {target} failed ({e})", file=sys.stderr)


def load_rows(conn, as_of: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("""SELECT underlying, score, call_value, put_value, n_call, n_put
                       FROM warrant_flow_daily WHERE date=%s""", (as_of,))
        return [dict(underlying=r[0], score=int(r[1]), call_value=int(r[2]),
                     put_value=int(r[3]), n_call=r[4], n_put=r[5])
                for r in cur.fetchall()]


def make_price_fns(conn):
    def close_fn(t, d):
        with conn.cursor() as cur:
            cur.execute("""SELECT close FROM stock_daily_ohlcv
                           WHERE symbol=%s AND ts::date<=%s ORDER BY ts DESC LIMIT 1""", (t, d))
            r = cur.fetchone()
        return float(r[0]) if r and r[0] else None

    def nth_close_fn(t, d, n):
        with conn.cursor() as cur:
            cur.execute("""SELECT close FROM stock_daily_ohlcv
                           WHERE symbol=%s AND ts::date>%s ORDER BY ts ASC LIMIT %s""", (t, d, n))
            rows = [x[0] for x in cur.fetchall()]
        return float(rows[n - 1]) if len(rows) >= n else None
    return close_fn, nth_close_fn


def push_inbox(msg: str, report_path: str) -> None:
    try:
        import redis
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "warrant_flow", "topic": "warrant-flow",
            "tags": "warrant,flow", "as_of": datetime.now().strftime("%Y-%m-%d"),
            "msg": msg, "report_path": report_path})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)


def find_missing_ohlcv(conn, tickers: list[str], as_of: str, tolerance_days: int = 1) -> list[str]:
    """近 tolerance_days 內無任何 OHLCV 列的 tickers — 非電子處置股日更缺口偵測.
    tolerance=3 曾造成滾動缺口 (8/24-25 有舊列 → 8/26-27 洞不觸發補抓, 2026-08-28 實例);
    tolerance=1 讓落後 1 日即重補 (14 日 upsert, 過度觸發無害)."""
    missing = []
    with conn.cursor() as cur:
        for t in tickers:
            cur.execute("""SELECT count(*) FROM stock_daily_ohlcv
                           WHERE symbol=%s AND ts >= %s::date - %s""",
                        (t, as_of, tolerance_days))
            if cur.fetchone()[0] == 0:
                missing.append(t)
    return missing


def heal_ohlcv_coverage(conn, as_of: str) -> None:
    """處置追蹤股若無日更 (非電子股不在 collector universe) → 臨時名單補近 10 日.
    2026-08-25: 4556/2491/7610/8021 解除日收盤缺列 → release_close 無法自癒的根因."""
    try:
        st = json.loads((REPO / "data" / "disposition_tracking_state.json").read_text())
        tickers = sorted(st.get("tracked", {}).keys())
    except Exception:
        return
    missing = find_missing_ohlcv(conn, tickers, as_of)
    if not missing:
        return
    print(f"[heal] OHLCV 缺口補抓: {missing}", file=sys.stderr)
    try:
        lst = "\\n".join(missing)
        subprocess.run(["docker", "exec", "tmf-stock-daily-collector", "sh", "-c",
                        f"printf '{lst}\\n' > /tmp/heal_tickers.txt"],
                       check=True, capture_output=True, timeout=30)
        from datetime import timedelta
        start = (date.fromisoformat(as_of) - timedelta(days=14)).isoformat()
        subprocess.run(["docker", "exec", "-e", "PYTHONPATH=/opt/tmf:/opt/tmf/src",
                        "tmf-stock-daily-collector", "python",
                        "scripts/collectors/stock_daily_ohlcv.py",
                        "--tickers-file", "/tmp/heal_tickers.txt",
                        "--start-date", start, "--end-date", as_of],
                       check=True, capture_output=True, timeout=300)
    except Exception as e:
        print(f"[warn] OHLCV heal failed: {e}", file=sys.stderr)


def main() -> int:
    as_of = date.today().isoformat()
    run_collector(as_of)
    import psycopg2
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    heal_ohlcv_coverage(conn, as_of)
    rows = load_rows(conn, as_of)
    if not rows:  # 休市日: 用最近一日
        with conn.cursor() as cur:
            cur.execute("SELECT max(date) FROM warrant_flow_daily")
            last = cur.fetchone()[0]
        if not last:
            print("[error] no data"); return 1
        as_of = last.isoformat()
        rows = load_rows(conn, as_of)
    shorts = rank_top(rows, TOP_N_SHOW, "short")
    longs = rank_top(rows, TOP_N_SHOW, "long")

    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {"tracked": {}}
    history = json.loads(HISTORY_PATH.read_text()) if HISTORY_PATH.exists() else []
    close_fn, nth_close_fn = make_price_fns(conn)
    graduated = update_tracking(state, shorts[:TOP_N_TRACK], longs[:TOP_N_TRACK],
                                as_of, close_fn, nth_close_fn)
    history.extend(graduated)
    hits = hit_stats(history)

    labels = load_labels()
    lines = [f"# 權證資金流排行 {as_of}", "",
             "score = 認購±成交值 − 認售±成交值 (內外盤 proxy, 萬元); 負 = 佈空能量", "",
             "## 佈空 Top 15", "",
             "| 標的 | score(萬) | 認售成交值(萬) | 檔數(購/售) | 產業 · 題材鏈 |",
             "|---|---|---|---|---|"]
    for r in shorts:
        lines.append(f"| **{label(r['underlying'], labels)}** | {r['score']/1e4:+,.0f} | "
                     f"{r['put_value']/1e4:,.0f} | {r['n_call']}/{r['n_put']} | "
                     f"{label_detail(r['underlying'], labels)} |")
    lines += ["", "## 佈多 Top 15", "",
              "| 標的 | score(萬) | 認購成交值(萬) | 檔數(購/售) | 產業 · 題材鏈 |",
              "|---|---|---|---|---|"]
    for r in longs:
        lines.append(f"| **{label(r['underlying'], labels)}** | {r['score']/1e4:+,.0f} | "
                     f"{r['call_value']/1e4:,.0f} | {r['n_call']}/{r['n_put']} | "
                     f"{label_detail(r['underlying'], labels)} |")
    if state["tracked"]:
        lines += ["", f"## 追蹤中 ({len(state['tracked'])})", ""]
        for u, e in sorted(state["tracked"].items()):
            p = e["post"]
            lines.append(f"- **{label(u, labels)}** [{e['side']}] {e['enter_date']} @{e['enter_close']} · "
                         f"T+1 {p['t1'] if p['t1'] is not None else '—'}% · "
                         f"T+5 {p['t5'] if p['t5'] is not None else '—'}% · T+20 {p['t20'] if p['t20'] is not None else '—'}%")
    s_hit, l_hit = hits.get("short", (0, 0)), hits.get("long", (0, 0))
    lines += ["", f"## 歷史命中 (畢業樣本 {len(history)})",
              f"- 佈空榜 T+5 收跌: {s_hit[0]}/{s_hit[1]} · 佈多榜 T+5 收漲: {l_hit[0]}/{l_hit[1]}", "",
              "*源: warrant_flow_daily (TWSE MI_INDEX 0999/0999P) · v1 上市 only*"]

    out = OUT_DIR / f"warrant_flow_{as_of}.md"
    out.write_text("\n".join(lines))
    msg = render_summary(as_of, shorts, longs, hits, labels=labels)
    print(msg)
    push_inbox(msg, f"analysis/warrant_flow_{as_of}.md")
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
