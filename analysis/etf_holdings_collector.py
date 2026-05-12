"""主動型 ETF 月度持股 + 共識度收集器.

每月 16 日由 cron 自動執行（主動 ETF 月公告後），:
1. 掃描 00980A-00999A 全部主動型 ETF
2. 拉每檔 top 10 持股 (yfinance funds_data)
3. 寫入 etf_holdings table（每日快照保留歷史）
4. 計算 etf_consensus（共識度指標）

執行也支援手動: python3 analysis/etf_holdings_collector.py [--all]
"""
from __future__ import annotations

import asyncio
import sys
import warnings
from datetime import date, datetime, timezone, timedelta
from collections import defaultdict

warnings.filterwarnings("ignore")

import asyncpg
import yfinance as yf

DB_DSN = "postgresql://knowledge:knowledge@localhost:5433/tw_electronics"
TPE = timezone(timedelta(hours=8))


def discover_active_etfs() -> list[str]:
    """Brute-scan 00980A-00999A and return live tickers (those with price data)."""
    found: list[str] = []
    for n in range(980, 1000):
        sym = f"00{n}A.TW"
        try:
            info = yf.Ticker(sym).info
            if info.get("regularMarketPrice") and (info.get("totalAssets") or 0) > 0:
                found.append(sym)
        except Exception:
            pass
    return found


def fetch_etf_holdings(sym: str) -> dict | None:
    try:
        t = yf.Ticker(sym)
        info = t.info
        fd = t.funds_data
        top = fd.top_holdings
        if top is None or top.empty:
            return None
        rows = []
        for rank, (tk, row) in enumerate(top.iterrows(), start=1):
            rows.append({
                "ticker": tk,
                "name": row.get("Name"),
                "pct": float(row.get("Holding Percent", 0)),
                "rank": rank,
            })
        return {
            "etf_ticker": sym.replace(".TW", ""),
            "etf_name": info.get("longName") or info.get("shortName") or sym,
            "etf_aum_b": (info.get("totalAssets") or 0) / 1e9,
            "holdings": rows,
        }
    except Exception as e:
        print(f"  ! {sym}: {e}", file=sys.stderr)
        return None


async def upsert_holdings(conn, snapshot_date: date, etf_data: dict) -> int:
    rows = []
    for h in etf_data["holdings"]:
        rows.append((
            snapshot_date,
            etf_data["etf_ticker"],
            etf_data["etf_name"],
            etf_data["etf_aum_b"],
            h["ticker"],
            h["name"],
            h["pct"],
            h["rank"],
        ))
    await conn.executemany(
        """
        INSERT INTO etf_holdings
            (snapshot_date, etf_ticker, etf_name, etf_aum_b,
             holding_ticker, holding_name, holding_pct, rank)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (snapshot_date, etf_ticker, holding_ticker)
        DO UPDATE SET holding_pct = EXCLUDED.holding_pct,
                      rank = EXCLUDED.rank,
                      etf_aum_b = EXCLUDED.etf_aum_b,
                      fetched_at = now()
        """, rows,
    )
    return len(rows)


async def compute_consensus(conn, snapshot_date: date) -> int:
    """Aggregate per-ticker consensus across all ETFs in this snapshot."""
    # First clear existing consensus rows for this date (idempotent re-runs)
    await conn.execute(
        "DELETE FROM etf_consensus WHERE snapshot_date = $1", snapshot_date
    )

    # Aggregate: count ETFs, avg/max pct, weighted by ETF AUM
    rows = await conn.fetch(
        """
        SELECT holding_ticker AS ticker,
               (array_agg(holding_name) FILTER (WHERE holding_name IS NOT NULL))[1] AS name,
               count(DISTINCT etf_ticker) AS n_etfs,
               avg(holding_pct) AS avg_pct,
               max(holding_pct) AS max_pct,
               sum(holding_pct * etf_aum_b) AS weighted_aum
          FROM etf_holdings
         WHERE snapshot_date = $1
         GROUP BY holding_ticker
        """,
        snapshot_date,
    )

    if not rows:
        return 0

    # Compute normalized consensus score (0-100):
    #   score = 0.5 * (n_etfs / max_n) + 0.5 * (weighted / max_weighted)
    max_n = max(r["n_etfs"] for r in rows)
    max_w = max(float(r["weighted_aum"]) for r in rows)

    inserts = []
    for r in rows:
        n_norm = r["n_etfs"] / max_n if max_n else 0
        w_norm = float(r["weighted_aum"]) / max_w if max_w else 0
        score = (n_norm * 0.5 + w_norm * 0.5) * 100
        inserts.append((
            snapshot_date, r["ticker"], r["name"],
            r["n_etfs"], float(r["avg_pct"]), float(r["max_pct"]),
            float(r["weighted_aum"]), score,
        ))

    await conn.executemany(
        """
        INSERT INTO etf_consensus
            (snapshot_date, ticker, name, n_etfs, avg_pct, max_pct, weighted_aum, consensus_score)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, inserts,
    )
    return len(inserts)


async def main() -> int:
    today = datetime.now(TPE).date()
    print(f"[etf_holdings] snapshot_date={today}", file=sys.stderr)

    etfs = discover_active_etfs()
    print(f"[etf_holdings] discovered {len(etfs)} active ETFs", file=sys.stderr)

    conn = await asyncpg.connect(DB_DSN)
    total_rows = 0
    skipped: list[str] = []
    try:
        for sym in etfs:
            data = fetch_etf_holdings(sym)
            if not data or not data["holdings"]:
                skipped.append(sym)
                continue
            n = await upsert_holdings(conn, today, data)
            total_rows += n
            print(f"  ✓ {data['etf_ticker']} ({data['etf_name'][:30]}) → {n} holdings", file=sys.stderr)

        n_consensus = await compute_consensus(conn, today)
        print(f"\n[etf_holdings] DONE — {total_rows} holding rows + {n_consensus} consensus rows", file=sys.stderr)
        if skipped:
            print(f"  skipped (no holdings published): {skipped}", file=sys.stderr)
    finally:
        await conn.close()
    return total_rows


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
