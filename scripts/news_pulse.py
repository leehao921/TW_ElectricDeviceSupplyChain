# -*- coding: utf-8 -*-
"""news_pulse.py — Phase 2 事件動能層: 新聞確定性標註 + 題材脈衝 + 族群同步.

讀 trading-timescaledb news_items (READ-ONLY) → 公司名/wikilink 實體字典匹配
(零 LLM) → theme 日級 pulse (歷史存 data/news_pulse_history.json) + 族群
breadth (價格 5D / 外資 5D) → analysis/news_pulse_<date>.md + inbox XADD。

Golden Rule 0: pulse z 需 MIN_HISTORY 日 baseline, 不足輸出
insufficient-history(n=X) 並禁用分布形容詞。

launchd: com.lulala.news-pulse Mon-Fri 20:35 (venv python 直跑, 勿經 bash)。
手動: python3 scripts/news_pulse.py [--date YYYY-MM-DD]
Plan: docs/plans/2026-07-29-news-pulse-phase2.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO / "Pilot_Reports"
WIKILINKS_MD = REPO / "WIKILINKS.md"
HISTORY_PATH = REPO / "data" / "news_pulse_history.json"
ANALYSIS_DIR = REPO / "analysis"

TZ_TPE = dt.timezone(dt.timedelta(hours=8))
MIN_HISTORY = 20
STD_FLOOR = 1e-9
TOP_THEMES = 12

# 2 字公司名同時是常用詞 → 永不匹配（誤報 > 漏報）
NAME_BLOCKLIST = {"全新", "大同", "東元", "中興", "力山", "光明", "太平", "民興",
                  "大眾", "百容", "永信", "合一", "三商", "南方", "得力"}

# theme 誤報源: 台灣地名(MOPS 公告地址樣板)與常見詞子串(如「重大金額」中「大金」)
THEME_BLOCKLIST = {"台北", "新北", "台中", "台南", "高雄", "桃園", "新竹", "內湖",
                   "南港", "大金", "大眾", "大同", "全新", "中興"}

# Phase 3b: 國際事件 → 本地 theme 標籤 (事件→theme 映射屬分析層, 故在此不在 collector)
EVENT_THEME_MAP = {
    "tsmc": "台積電", "semi_export": "出口管制", "tariff": "關稅",
    "taiwan_strait": "台海風險", "ai_capex": "AI 伺服器", "memory": "記憶體",
    "KXFEDDECISION": "Fed 利率", "KXTAIWANLVL4": "台海風險", "KXCHINAEUV": "出口管制",
    "will-china-launch-a-fullscale-invas": "台海風險",
    "if-china-invades-taiwan-will-be-inv": "台海風險",
    "will-the-us-be-able-to-prop-up-its": "出口管制",
    "federal-reserve-fomc-decision-in-ju": "Fed 利率",
}


def _map_event_theme(key):
    if key in EVENT_THEME_MAP:
        return EVENT_THEME_MAP[key]
    for prefix, theme in EVENT_THEME_MAP.items():
        if key.startswith(prefix):
            return theme
    return key

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)\]\]")
_FILENAME_RE = re.compile(r"^(\d{4,5})_(.+)\.md$")


# ------------------------------------------------------------------ #
# 實體層
# ------------------------------------------------------------------ #
def build_ticker_names(reports_dir):
    """{公司名: ticker} 自 Pilot_Reports 檔名。"""
    out = {}
    for p in Path(reports_dir).glob("*/*.md"):
        m = _FILENAME_RE.match(p.name)
        if m:
            out[m.group(2)] = m.group(1)
    return out


def build_ticker_themes(reports_dir):
    """({ticker: set(themes)}, {theme: set(tickers)}) 自報告內 wikilinks。
    公司自己的名字不算 theme。"""
    t2th, th2t = {}, {}
    for p in Path(reports_dir).glob("*/*.md"):
        m = _FILENAME_RE.match(p.name)
        if not m:
            continue
        ticker, own_name = m.group(1), m.group(2)
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        themes = set(_WIKILINK_RE.findall(text)) - {own_name}
        t2th[ticker] = themes
        for th in themes:
            th2t.setdefault(th, set()).add(ticker)
    return t2th, th2t


def load_theme_entities(wikilinks_md):
    text = Path(wikilinks_md).read_text(encoding="utf-8")
    return set(_WIKILINK_RE.findall(text))


# ------------------------------------------------------------------ #
# 標註層（純函數）
# ------------------------------------------------------------------ #
def _ascii_boundary_match(text, entity):
    """純 ASCII 實體: 左側非英數、右側非字母（防 FAIRCHILD 誤中 AI，
    但允許版本號後綴如 HBM4 / HBM3e 中 HBM… 右側數字放行）。"""
    for m in re.finditer(re.escape(entity), text):
        left = text[m.start() - 1] if m.start() > 0 else " "
        right = text[m.end()] if m.end() < len(text) else " "
        if not left.isalnum() and not right.isalpha():
            return True
    return False


def extract_tickers(title, body, name_map):
    title, body = title or "", body or ""
    got = set()
    for name, ticker in name_map.items():
        if name in NAME_BLOCKLIST:
            continue
        hay = title if len(name) <= 2 else (title + "\n" + body)
        if name in hay:
            got.add(ticker)
    return got


def extract_themes(title, body, entities):
    text = (title or "") + "\n" + (body or "")
    got = set()
    for e in entities:
        if e in THEME_BLOCKLIST:
            continue
        if e.isascii():
            if _ascii_boundary_match(text, e):
                got.add(e)
        elif e in text:
            got.add(e)
    return got


def tag_items(items, name_map, entities):
    tagged = []
    for it in items:
        tickers = extract_tickers(it.get("title"), it.get("body"), name_map)
        if it.get("ticker"):
            tickers.add(it["ticker"])
        tagged.append({
            "news_uid": it["news_uid"],
            "source_tier": it.get("source_tier", 2),
            "title": it.get("title", ""),
            "tickers": tickers,
            "themes": extract_themes(it.get("title"), it.get("body"), entities),
        })
    return tagged


# ------------------------------------------------------------------ #
# Pulse 層（純函數）
# ------------------------------------------------------------------ #
def theme_pulse(tagged, history, min_history=MIN_HISTORY):
    """[{theme, count, tier1, tier2, z, z_note}] 依 count 降冪。
    z gated: 歷史 < min_history 或 std 退化 → None。"""
    counts = {}
    for t in tagged:
        for th in t["themes"]:
            c = counts.setdefault(th, {"count": 0, "tier1": 0, "tier2": 0})
            c["count"] += 1
            c["tier1" if t["source_tier"] == 1 else "tier2"] += 1

    out = []
    for th, c in counts.items():
        hist_vals = list((history.get(th) or {}).values())
        n = len(hist_vals)
        z, note = None, ""
        if n < min_history:
            note = "insufficient-history(n=%d)" % n
        else:
            mean = sum(hist_vals) / n
            var = sum((v - mean) ** 2 for v in hist_vals) / n
            std = math.sqrt(var)
            if std < STD_FLOOR or not math.isfinite(std):
                note = "degenerate-baseline(n=%d)" % n
            else:
                z = (c["count"] - mean) / std
                note = "z vs %d-day baseline, n=%d" % (n, n)
        out.append({"theme": th, "count": c["count"], "tier1": c["tier1"],
                    "tier2": c["tier2"], "z": z, "z_note": note})
    out.sort(key=lambda x: (-x["count"], x["theme"]))
    return out


def intl_momentum(gdelt_rows, pm_rows, min_history=MIN_HISTORY):
    """國際事件動能 (Phase 3b, 純函數)。
    gdelt_rows: [(query_key, date, article_count, avg_tone)]
    pm_rows:    [(platform, market_id, date, prob, question, liquidity)]
    → {"gdelt": [{key, theme, today, z, tone, note}], "pm": [{...prob, delta_7d}]}
    z gated by min_history; PM delta 需 ≥7 日前有快照。"""
    by_key = {}
    for key, d, cnt, tone in gdelt_rows:
        by_key.setdefault(key, {})[d] = (cnt or 0, tone)
    out_g = []
    for key, series in by_key.items():
        days = sorted(series)
        latest = days[-1]
        today_cnt, today_tone = series[latest]
        hist = [series[d][0] for d in days[:-1]]
        n = len(hist)
        z, note = None, ""
        if n < min_history:
            note = "insufficient-history(n=%d)" % n
        else:
            mean = sum(hist) / n
            std = math.sqrt(sum((v - mean) ** 2 for v in hist) / n)
            if std < STD_FLOOR or not math.isfinite(std):
                note = "degenerate-baseline(n=%d)" % n
            else:
                z = (today_cnt - mean) / std
                note = "z vs %d-day baseline" % n
        out_g.append({"key": key, "theme": _map_event_theme(key), "today": today_cnt,
                      "tone": today_tone, "z": z, "note": note, "date": latest})
    out_g.sort(key=lambda x: -(x["z"] if x["z"] is not None else -999))

    by_mkt = {}
    for plat, mid, d, prob, q, liq in pm_rows:
        by_mkt.setdefault((plat, mid), {"q": q, "liq": liq, "series": {}})
        by_mkt[(plat, mid)]["series"][d] = prob
    out_pm = []
    for (plat, mid), rec in by_mkt.items():
        days = sorted(rec["series"])
        latest = days[-1]
        prob = rec["series"][latest]
        prior = [d for d in days if (latest - d).days >= 7]
        delta = (prob - rec["series"][prior[-1]]) if prior else None
        out_pm.append({"platform": plat, "market_id": mid,
                       "theme": _map_event_theme(mid), "prob": prob,
                       "delta_7d": delta, "question": rec["q"],
                       "liquidity": rec["liq"], "date": latest})
    out_pm.sort(key=lambda x: -abs(x["delta_7d"] if x["delta_7d"] is not None else 0))
    return {"gdelt": out_g, "pm": out_pm}


def cluster_confirm(members, price_5d, flow_5d):
    """breadth: 價格漲家數/有價格成員數, 外資買超家數/有 flow 成員數。
    無價格資料成員(OTC gap)列 no_price_data 揭露。"""
    price_avail = [t for t in members if t in price_5d]
    flow_avail = [t for t in members if t in flow_5d]
    return {
        "price_up": sum(1 for t in price_avail if price_5d[t] > 0),
        "price_n": len(price_avail),
        "flow_pos": sum(1 for t in flow_avail if flow_5d[t] > 0),
        "flow_n": len(flow_avail),
        "no_price_data": sorted(set(members) - set(price_avail)),
    }


# ------------------------------------------------------------------ #
# 報告層
# ------------------------------------------------------------------ #
def render_report(date, pulses, total_items, tagged_items):
    L = []
    L.append("# 題材脈衝 × 族群同步（news_pulse 自動產生）\n")
    L.append("**日期:** %s　**窗口新聞:** %d 則（標到題材 %d 則）\n" % (date, total_items, tagged_items))
    L.append("> **窗口 = 近 3 日**（重訊源滯後 1-2 日，窄窗會漏 tier1；連日報告間有重疊，"
             "baseline 同慣例故 z like-for-like）。tier1 = MOPS 公司自發重訊（第一手），"
             "tier2 = 媒體。z 需 %d 日 baseline。\n" % MIN_HISTORY)
    L.append("\n## 題材脈衝 Top %d\n" % TOP_THEMES)
    L.append("| 題材 | 則數 | tier1/tier2 | z | 族群價格 breadth (5D) | 族群外資 breadth (5D) |")
    L.append("|---|--:|---|---|---|---|")
    for p in pulses[:TOP_THEMES]:
        c = p.get("cluster") or {}
        zs = ("%.1f" % p["z"]) if p.get("z") is not None else "—"
        pb = "%d/%d 漲" % (c.get("price_up", 0), c.get("price_n", 0)) if c.get("price_n") else "n/a"
        fb = "%d/%d 買超" % (c.get("flow_pos", 0), c.get("flow_n", 0)) if c.get("flow_n") else "n/a"
        L.append("| %s | %d | %d/%d | %s | %s | %s |" % (
            p["theme"], p["count"], p["tier1"], p["tier2"], zs, pb, fb))
    L.append("\n## 代表標題\n")
    for p in pulses[:5]:
        for h in (p.get("headlines") or [])[:2]:
            L.append("- **[%s]** %s" % (p["theme"], h))
    L.append("\n## Verification log\n")
    for p in pulses[:TOP_THEMES]:
        L.append("- %s: count=%d, %s" % (p["theme"], p["count"], p["z_note"]))
        c = p.get("cluster") or {}
        if c.get("no_price_data"):
            L.append("  - 無價格資料成員(OTC close gap): %s" % ", ".join(c["no_price_data"]))
    L.append("- 標註為確定性字典匹配（公司名/wikilink 實體），非 LLM；未驗證分布性主張不使用分布形容詞。")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ #
# I/O 層
# ------------------------------------------------------------------ #
def _db():
    import psycopg2
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user="tmf", password=os.environ.get("DB_PASSWORD", "tmf_dev_2026"),
        dbname="tmf_market_data")


def fetch_news(conn, date):
    cur = conn.cursor()
    # 3 日滾動窗口: TWSE 重訊快照滯後 1 日、TPEx 滯後 2 日 (見 collector plan),
    # 窄窗會漏掉全部 tier1。baseline 同窗口慣例 → z like-for-like。
    cur.execute(
        "SELECT news_uid, source, source_tier, ticker, title, body "
        "FROM news_items WHERE announce_date >= %s - INTERVAL '2 days' "
        "AND announce_date <= %s", (date, date))
    rows = cur.fetchall()
    cur.close()
    return [{"news_uid": r[0], "source": r[1], "source_tier": r[2],
             "ticker": r[3], "title": r[4] or "", "body": r[5]} for r in rows]


def fetch_flow_price_5d(conn, tickers):
    """外資 5D 淨買(元) + 5D 收盤漲跌% (institutional_stock, TWSE close only)。"""
    if not tickers:
        return {}, {}
    cur = conn.cursor()
    cur.execute(
        "SELECT symbol, sum(foreign_net) AS f5, "
        "  (array_agg(close_price ORDER BY date DESC) FILTER (WHERE close_price > 0))[1] AS c0, "
        "  (array_agg(close_price ORDER BY date ASC) FILTER (WHERE close_price > 0))[1] AS c5 "
        "FROM (SELECT symbol, date, foreign_net, close_price "
        "      FROM institutional_stock WHERE symbol = ANY(%s) "
        "      AND date >= CURRENT_DATE - INTERVAL '9 days') s "
        "GROUP BY symbol", (list(tickers),))
    flow, price = {}, {}
    for sid, f5, c0, c5 in cur.fetchall():
        if f5 is not None:
            flow[sid] = float(f5)
        if c0 and c5 and float(c5) > 0:
            price[sid] = (float(c0) / float(c5) - 1.0) * 100.0
    cur.close()
    return flow, price


def fetch_intl(conn):
    """讀 gdelt_daily(60d) + prediction_markets_daily(30d), read-only。表不存在回空。"""
    cur = conn.cursor()
    try:
        cur.execute("SELECT query_key, date, article_count, avg_tone FROM gdelt_daily "
                    "WHERE date >= CURRENT_DATE - INTERVAL '65 days' ORDER BY date")
        g = cur.fetchall()
        cur.execute("SELECT platform, market_id, date, prob, question, liquidity "
                    "FROM prediction_markets_daily "
                    "WHERE date >= CURRENT_DATE - INTERVAL '30 days' ORDER BY date")
        pm = cur.fetchall()
    except Exception:                                # noqa: BLE001 — 表未建時優雅降級
        conn.rollback()
        g, pm = [], []
    cur.close()
    return g, pm


def render_intl_section(intl):
    if not intl or (not intl["gdelt"] and not intl["pm"]):
        return "\n## 國際事件動能\n\n(無資料 — intl_events collector 未產出)\n"
    L = ["\n## 國際事件動能\n"]
    if intl["gdelt"]:
        L.append("**GDELT 新聞量（日級，60d baseline）:**\n")
        L.append("| 監測 | 對應題材 | 今日則數 | z | tone |")
        L.append("|---|---|--:|---|---|")
        for g in intl["gdelt"]:
            zs = ("%.1f" % g["z"]) if g["z"] is not None else "— (%s)" % g["note"]
            tn = ("%.1f" % g["tone"]) if g["tone"] is not None else "n/a"
            L.append("| %s | %s | %d | %s | %s |" % (g["key"], g["theme"], g["today"], zs, tn))
    if intl["pm"]:
        L.append("\n**預測市場機率（Kalshi/Manifold）:**\n")
        L.append("| 市場 | 對應題材 | 機率 | Δ7d |")
        L.append("|---|---|--:|---|")
        for p in intl["pm"][:10]:
            ds = ("%+.0f pp" % (p["delta_7d"] * 100)) if p["delta_7d"] is not None else "— (首日快照)"
            L.append("| %s | %s | %.0f%% | %s |" % (
                (p["question"] or p["market_id"])[:48], p["theme"], p["prob"] * 100, ds))
    return "\n".join(L) + "\n"


def load_history():
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return {}


def save_history(history, date, pulses):
    key = date.isoformat()
    for p in pulses:
        history.setdefault(p["theme"], {})[key] = p["count"]
    HISTORY_PATH.parent.mkdir(exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")


def push_inbox(summary, date):
    import subprocess
    fields = ["ts", dt.datetime.now(TZ_TPE).isoformat(), "from", "news_pulse",
              "topic", "news-pulse", "tags", "news-pulse,daily",
              "as_of", date.isoformat(), "msg", summary]
    r = subprocess.run(["redis-cli", "XADD", "claude:inbox", "*", *fields],
                       capture_output=True, text=True, timeout=10)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    date = (dt.datetime.strptime(args.date, "%Y-%m-%d").date() if args.date
            else dt.datetime.now(TZ_TPE).date())

    name_map = build_ticker_names(REPORTS_DIR)
    _, th2t = build_ticker_themes(REPORTS_DIR)
    entities = load_theme_entities(WIKILINKS_MD)

    conn = _db()
    try:
        items = fetch_news(conn, date)
        tagged = tag_items(items, name_map, entities)
        history = load_history()
        # 當日不能進自己的 baseline
        hist_ex_today = {th: {k: v for k, v in d.items() if k != date.isoformat()}
                         for th, d in history.items()}
        pulses = theme_pulse(tagged, hist_ex_today)

        for p in pulses[:TOP_THEMES]:
            members = th2t.get(p["theme"], set())
            flow, price = fetch_flow_price_5d(conn, members)
            p["cluster"] = cluster_confirm(members, price, flow)
            p["headlines"] = [t["title"] for t in tagged if p["theme"] in t["themes"]][:3]

        g_rows, pm_rows = fetch_intl(conn)
        intl = intl_momentum(g_rows, pm_rows)
    finally:
        conn.close()

    tagged_n = sum(1 for t in tagged if t["themes"])
    md = render_report(date, pulses, len(items), tagged_n)
    md += render_intl_section(intl)
    ANALYSIS_DIR.mkdir(exist_ok=True)
    out = ANALYSIS_DIR / ("news_pulse_%s.md" % date.isoformat())
    out.write_text(md, encoding="utf-8")
    save_history(history, date, pulses)

    top = pulses[:5]
    summary = "題材脈衝 %s: " % date + "; ".join(
        "%s %d則(t1=%d)" % (p["theme"], p["count"], p["tier1"]) for p in top)
    push_inbox(summary, date)
    print("[%s] items=%d tagged=%d themes=%d → %s" % (
        dt.datetime.now(TZ_TPE).strftime("%F %T"), len(items), tagged_n,
        len(pulses), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
