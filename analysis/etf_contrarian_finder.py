"""ETF Contrarian Finder — 找「主動 ETF 完全沒持有但基本面強」的標的.

執行邏輯:
1. 從 etf_consensus 拉最新一個 snapshot_date 的 holdings（被持有的標的）
2. 從 yfinance 掃描 ~50 檔候選台股的基本面（ROE, P/E, 殖利率, 業績成長）
3. 找出「不在 ETF 名單 + 基本面合格」的 contrarian 標的
4. 寫入 news_items source='claude_research'
5. 也輸出 stdout markdown 報告

合格標準（all 必須符合）:
- ROE > 12%
- Fwd P/E < 20x
- 殖利率 > 2.5%
- 業績成長 (rev YoY) > -10%
- 市值 > 100 億
"""
from __future__ import annotations

import asyncio
import sys
import warnings
from datetime import date, datetime, timezone, timedelta

warnings.filterwarnings("ignore")

import asyncpg
import pandas as pd
import yfinance as yf

DB_DSN = "postgresql://knowledge:knowledge@localhost:5433/tw_electronics"
TPE = timezone(timedelta(hours=8))

# 候選掃描宇宙: TAIEX top 50 + 重點中小型
CANDIDATE_TICKERS = [
    # Top 30 weighted (already mostly in ETFs)
    "2330","2308","2454","2317","3711","2881","2382","2882","2891","2412",
    "2885","2884","2886","2890","6505","1216","1303","1301","2002","2603",
    # Mid-cap candidates likely contrarian
    "1513","1519","1503","1504","2371","1514","1605","1612","1618",  # 重電/電纜
    "2609","2615","2207","9904","1227","2912",                          # 航運/內需
    "3034","2379","2360","2327","8261","6552","6515",                   # IC/被動
    "2883","2887","2880","5871","2892","5876","5880",                   # 金融
    "8996","3324","1520","2049","2031","9921","6196",                   # 機械/熱
    "3037","8046","3189","2383","6213","2313","6269","6274",            # ABF/PCB
    "3443","3661","3035","6533","6191","2454",                          # ASIC
    "1102","1227","2912","2105","9941",                                  # 內需
]


async def get_etf_held_tickers(conn) -> tuple[set[str], date]:
    row = await conn.fetchrow(
        "SELECT max(snapshot_date) AS d FROM etf_consensus"
    )
    if not row or not row["d"]:
        return set(), None
    snapshot = row["d"]
    rows = await conn.fetch(
        "SELECT ticker FROM etf_consensus WHERE snapshot_date = $1", snapshot
    )
    held = set()
    for r in rows:
        # Strip suffix like .TW / .TWO and US tickers
        tk = r["ticker"].split(".")[0]
        held.add(tk)
    return held, snapshot


def fetch_fundamentals(ticker: str) -> dict | None:
    """Try .TW first, fall back to .TWO."""
    for suffix in (".TW", ".TWO"):
        try:
            t = yf.Ticker(ticker + suffix)
            info = t.info
            if not info.get("regularMarketPrice"):
                continue
            return {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName"),
                "price": info.get("regularMarketPrice"),
                "mc_b": (info.get("marketCap") or 0) / 1e9,
                "pe_ttm": info.get("trailingPE"),
                "pe_fwd": info.get("forwardPE"),
                "roe": (info.get("returnOnEquity") or 0) * 100,
                "div_yield": info.get("dividendYield") or 0,
                "rev_yoy": (info.get("revenueGrowth") or 0) * 100,
                "earn_yoy": (info.get("earningsGrowth") or 0) * 100,
                "net_margin": (info.get("profitMargins") or 0) * 100,
                "high52": info.get("fiftyTwoWeekHigh"),
                "low52": info.get("fiftyTwoWeekLow"),
                "pos52": (((info.get("regularMarketPrice", 0) - (info.get("fiftyTwoWeekLow") or 0))
                           / max((info.get("fiftyTwoWeekHigh") or 1) - (info.get("fiftyTwoWeekLow") or 0), 1)) * 100),
                "rec": info.get("recommendationKey"),
                "target_mean": info.get("targetMeanPrice"),
            }
        except Exception:
            continue
    return None


def passes_fundamental_screen(f: dict) -> bool:
    return (
        (f.get("roe") or 0) > 12
        and 0 < (f.get("pe_fwd") or 99) < 20
        and (f.get("div_yield") or 0) > 2.5
        and (f.get("rev_yoy") or 0) > -10
        and (f.get("mc_b") or 0) > 10
    )


def render_report(
    snapshot: date, held: set[str], passed: list[dict]
) -> str:
    lines = [
        f"# 🔍 ETF Contrarian Finder — {datetime.now(TPE).date()}",
        "",
        f"**Reference snapshot:** {snapshot}",
        f"**主動 ETF 已持有的個股 (合計):** {len(held)} 檔",
        f"**通過基本面篩選的「被遺忘」候選:** {len(passed)} 檔",
        "",
        "## 🎯 主動 ETF 完全沒持有 + 基本面強",
        "",
        "| ticker | name | 價格 | 市值(B) | Fwd P/E | ROE% | 殖利率 | rev YoY | 52w位 | 法人 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for f in sorted(passed, key=lambda x: -(x.get("roe") or 0))[:30]:
        lines.append(
            f"| {f['ticker']} | {(f['name'] or '?')[:18]} | {f['price']:.1f} | "
            f"{f['mc_b']:.0f} | {(f['pe_fwd'] or 0):.1f} | "
            f"{f['roe']:.1f}% | {f['div_yield']:.2f}% | {f['rev_yoy']:+.1f}% | "
            f"{f['pos52']:.0f}% | {f.get('rec') or '-'} |"
        )

    lines += [
        "",
        "## 📌 篩選標準",
        "",
        "- ROE > 12% （獲利效率穩）",
        "- Fwd P/E < 20x （估值合理）",
        "- 殖利率 > 2.5% （real income）",
        "- rev YoY > −10% （業績不爛）",
        "- 市值 > 100 億 （流動性）",
        "- **不在主動 ETF 持股名單**",
        "",
        "→ 這些是「機構還沒大舉進場 + 基本面已經 ready」的潛在輪動標的",
    ]
    return "\n".join(lines) + "\n"


async def main() -> int:
    today = datetime.now(TPE).date()
    conn = await asyncpg.connect(DB_DSN)

    try:
        held, snapshot = await get_etf_held_tickers(conn)
        if not held:
            print("[contrarian] no etf_consensus snapshot — run etf_holdings_collector first", file=sys.stderr)
            return 0
        print(f"[contrarian] reference snapshot={snapshot}, {len(held)} held tickers", file=sys.stderr)

        # Scan candidates
        passed: list[dict] = []
        skipped = 0
        for tk in CANDIDATE_TICKERS:
            if tk in held:
                continue  # already held by ETF
            f = fetch_fundamentals(tk)
            if f is None:
                skipped += 1
                continue
            if passes_fundamental_screen(f):
                passed.append(f)

        print(f"[contrarian] passed: {len(passed)}, skipped: {skipped}", file=sys.stderr)

        body = render_report(snapshot, held, passed)
        print(body)

        # Persist into news_items
        url = f"claude://research/etf_contrarian/{today}"
        title = f"[ETF Contrarian] 主動 ETF 沒持但基本面強 ({today})"
        await conn.execute(
            """
            INSERT INTO news_items
                (source, source_url, published_at, title, body, tickers, wikilinks)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (source_url) DO UPDATE SET
                title = EXCLUDED.title, body = EXCLUDED.body, ingested_at = now()
            """,
            "claude_research", url,
            datetime.now(TPE), title, body,
            [f["ticker"] for f in passed[:30]],
            ["ETF Contrarian", "資金輪動", "主動型 ETF"],
        )
        print(f"[contrarian] wrote news_items: {url}", file=sys.stderr)
    finally:
        await conn.close()

    return len(passed)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
