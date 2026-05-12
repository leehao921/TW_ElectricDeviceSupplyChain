"""Google Trends 搜尋熱度 vs 股價走勢比對 — 自動化 cron 版本.

每日 17:30 TPE 跑（gt_daily 17:00 完成後 30 分鐘），比對:
  - 過去 4 日搜尋熱度動量 (recent vs prior 4d)
  - 過去 4 日股價變化
  - 找出「搜尋暴衝但股價未動」(可能領先) 或「股價漲但搜尋未跟上」(被動上漲)

輸出: news_items 一筆 source='claude_research', source_url=
  claude://research/gt_price_compare/<date>

判讀邏輯:
  ✓ 搜尋 + 股價同向 → 散戶情緒已 priced in
  ⚠️ 搜尋暴衝、股價未動 → 散戶剛開始注意，可能落後布局
  🚨 股價漲、搜尋未動 → 法人或主力推升，散戶尚未追
  🔻 兩者皆跌 → 退潮確認
"""
from __future__ import annotations

import asyncio
import sys
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore")

import asyncpg
import pandas as pd
import yfinance as yf

DB_DSN = "postgresql://knowledge:knowledge@localhost:5433/tw_electronics"
TPE = timezone(timedelta(hours=8))

# Map: search keyword → ticker for stock-price pulling
KEYWORD_TO_TICKER = {
    "台積電": "2330.TW",
    "台達電": "2308.TW",
    "聯發科": "2454.TW",
    "鴻海": "2317.TW",
    "日月光投控": "3711.TW",
    "富邦金": "2881.TW",
    "廣達": "2382.TW",
    "國泰金": "2882.TW",
    "中信金": "2891.TW",
    "中華電": "2412.TW",
    "中興電": "1513.TW",
}

# Themes have no ticker — track only search momentum
THEMES = ["AI 資料中心", "半導體"]


async def fetch_search_data(window_days: int = 8) -> dict[str, dict]:
    """Pull last `window_days` of daily google trends scores per keyword."""
    end = datetime.now(TPE).date()
    start = end - timedelta(days=window_days + 1)
    out: dict[str, dict] = {}

    conn = await asyncpg.connect(DB_DSN)
    try:
        keywords = list(KEYWORD_TO_TICKER.keys()) + THEMES
        for kw in keywords:
            rows = await conn.fetch(
                """
                SELECT ts::date AS d, score
                  FROM google_trends_daily
                 WHERE keyword=$1 AND geo='TW' AND granularity='daily'
                   AND ts::date >= $2 AND ts::date <= $3
                 ORDER BY ts
                """,
                kw, start, end,
            )
            if len(rows) < 4:
                out[kw] = {"recent_avg": None, "prior_avg": None, "today": None,
                           "momentum_pct": None, "n": len(rows)}
                continue
            scores = [r["score"] for r in rows]
            recent = scores[-4:]
            prior = scores[-8:-4] if len(scores) >= 8 else scores[:-4]
            r_avg = sum(recent) / len(recent)
            p_avg = sum(prior) / len(prior) if prior else r_avg
            mom = ((r_avg - p_avg) / p_avg * 100) if p_avg > 0 else 0
            out[kw] = {
                "recent_avg": round(r_avg, 1),
                "prior_avg": round(p_avg, 1),
                "today": scores[-1],
                "momentum_pct": round(mom, 1),
                "n": len(rows),
            }
    finally:
        await conn.close()
    return out


def fetch_price_data() -> dict[str, dict]:
    """Pull last 8 trading days for each ticker; return 4d momentum."""
    out: dict[str, dict] = {}
    tickers = list(KEYWORD_TO_TICKER.values())
    df = yf.download(tickers, period="14d", auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"]
    else:
        close = df[["Close"]]
        close.columns = [tickers[0]]

    for kw, ticker in KEYWORD_TO_TICKER.items():
        if ticker not in close.columns:
            out[kw] = {"price_4d_pct": None, "today_close": None}
            continue
        s = close[ticker].dropna()
        if len(s) < 5:
            out[kw] = {"price_4d_pct": None, "today_close": None}
            continue
        last = float(s.iloc[-1])
        ref = float(s.iloc[-5]) if len(s) >= 5 else float(s.iloc[0])
        pct = (last - ref) / ref * 100
        out[kw] = {
            "price_4d_pct": round(pct, 2),
            "today_close": round(last, 2),
            "ref_4d_ago": round(ref, 2),
        }
    return out


def classify_signal(search_mom: float | None, price_pct: float | None) -> tuple[str, str]:
    """Return (icon, label) based on the 4-quadrant matrix."""
    if search_mom is None or price_pct is None:
        return ("?", "資料不足")
    THR_S = 30  # 搜尋動量 ±30%
    THR_P = 2   # 股價 ±2%
    if abs(search_mom) < THR_S and abs(price_pct) < THR_P:
        return ("⚪", "中性盤整")
    if search_mom >= THR_S and price_pct >= THR_P:
        return ("✅", "同向上漲 (情緒已 priced)")
    if search_mom < -THR_S and price_pct < -THR_P:
        return ("🔻", "同向退潮")
    if search_mom >= THR_S and abs(price_pct) < THR_P:
        return ("⚠️", "搜尋衝 但股價未動 (散戶才追)")
    if abs(search_mom) < THR_S and price_pct >= THR_P:
        return ("🚨", "股價漲 搜尋未動 (法人推升)")
    if search_mom >= THR_S and price_pct < -THR_P:
        return ("📉", "搜尋衝 但股價跌 (散戶被套)")
    if search_mom < -THR_S and price_pct >= THR_P:
        return ("🤔", "搜尋退潮 但股價漲 (主力獨撐)")
    return ("·", "(其他)")


def render_report(search_data: dict, price_data: dict) -> str:
    today = datetime.now(TPE).strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Google Trends vs 股價 — 比對報告 ({today} TPE)",
        "",
        "資料區間: 過去 4 日 search momentum vs 4 日股價變化",
        "",
        "## 主題搜尋動量",
        "",
        "| 主題 | 4D 平均 | 前 4D 平均 | 動量 % | 訊號 |",
        "|---|---:|---:|---:|---|",
    ]
    for theme in THEMES:
        d = search_data.get(theme, {})
        recent = d.get("recent_avg")
        prior = d.get("prior_avg")
        mom = d.get("momentum_pct")
        recent_s = f"{recent}" if recent is not None else "n/a"
        prior_s = f"{prior}" if prior is not None else "n/a"
        mom_s = f"{mom:+.1f}%" if mom is not None else "n/a"
        if mom is not None and abs(mom) >= 30:
            icon = "🔥" if mom > 0 else "🔻"
        else:
            icon = "⚪"
        lines.append(f"| {theme} | {recent_s} | {prior_s} | {mom_s} | {icon} |")

    lines += [
        "",
        "## 權值股 + 中興電 — 搜尋熱度 vs 股價交叉",
        "",
        "| Ticker | 公司 | 搜尋動量 | 股價 4D% | 收盤 | 訊號 | 解讀 |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for kw, ticker in KEYWORD_TO_TICKER.items():
        s = search_data.get(kw, {})
        p = price_data.get(kw, {})
        sm = s.get("momentum_pct")
        pp = p.get("price_4d_pct")
        close = p.get("today_close")
        sm_s = f"{sm:+.1f}%" if sm is not None else "n/a"
        pp_s = f"{pp:+.2f}%" if pp is not None else "n/a"
        close_s = f"{close}" if close is not None else "n/a"
        icon, label = classify_signal(sm, pp)
        ticker_short = ticker.replace(".TW", "")
        lines.append(
            f"| {ticker_short} | {kw} | {sm_s} | {pp_s} | {close_s} | {icon} | {label} |"
        )

    # Highlight notable signals
    notable_alerts = []
    notable_lead = []  # 搜尋衝但股價未動 (lead indicator)
    notable_main = []  # 股價漲但搜尋未動 (法人推升)
    for kw, ticker in KEYWORD_TO_TICKER.items():
        s = search_data.get(kw, {})
        p = price_data.get(kw, {})
        sm = s.get("momentum_pct")
        pp = p.get("price_4d_pct")
        if sm is None or pp is None:
            continue
        if sm >= 30 and abs(pp) < 2:
            notable_lead.append((kw, ticker.replace(".TW", ""), sm, pp))
        if abs(sm) < 30 and pp >= 2:
            notable_main.append((kw, ticker.replace(".TW", ""), sm, pp))

    if notable_lead:
        lines += [
            "",
            "## 🔍 重要訊號 — 搜尋暴衝但股價未動 (散戶剛追、可能落後布局)",
            "",
        ]
        for kw, t, sm, pp in notable_lead:
            lines.append(f"- **{t} {kw}**: 搜尋動量 {sm:+.1f}%、股價僅 {pp:+.2f}% — 散戶剛上車")

    if notable_main:
        lines += [
            "",
            "## 🚨 重要訊號 — 股價漲但搜尋未跟 (法人/主力推升、散戶未追)",
            "",
        ]
        for kw, t, sm, pp in notable_main:
            lines.append(f"- **{t} {kw}**: 股價 {pp:+.2f}%、搜尋僅 {sm:+.1f}% — 法人主導行情")

    lines += [
        "",
        "## 判讀備忘",
        "",
        "- 🔥 搜尋暴衝且股價漲: 情緒已 priced in，**追進去風險高**",
        "- ⚠️ 搜尋衝但股價未動: 散戶剛上車，**可能還有上漲空間**（lead indicator）",
        "- 🚨 股價漲但搜尋未動: 法人/主力推升，**散戶尚未追**（最強多頭結構）",
        "- 🔻 兩者皆跌: 退潮確認，**避開**",
        "",
        f"_資料源: google_trends_daily 表 + yfinance 即時。下次 fire: 明日 17:30 TPE_",
    ]
    return "\n".join(lines)


async def main() -> int:
    today = datetime.now(TPE)
    today_str = today.strftime("%Y-%m-%d")

    print(f"[gt_compare] {today.isoformat()} fetching ...", file=sys.stderr)
    search_data = await fetch_search_data()
    price_data = fetch_price_data()
    body = render_report(search_data, price_data)

    title = f"[GT-Price 比對] 搜尋熱度 vs 股價 ({today_str})"
    url = f"claude://research/gt_price_compare/{today_str}"

    conn = await asyncpg.connect(DB_DSN)
    try:
        r = await conn.fetchrow(
            """
            INSERT INTO news_items (source, source_url, published_at, title, body, tickers, wikilinks)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (source_url) DO UPDATE SET
              title = EXCLUDED.title, body = EXCLUDED.body, ingested_at = now()
            RETURNING id
            """,
            "claude_research", url, today,
            title, body,
            list({v.replace(".TW","") for v in KEYWORD_TO_TICKER.values()}),
            ["GoogleTrends","sentiment","散戶熱度"] + list(THEMES),
        )
        print(f"[gt_compare] DONE — id={r['id']}", file=sys.stderr)
    finally:
        await conn.close()

    # Also print to stdout for cron logs
    print(body)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
