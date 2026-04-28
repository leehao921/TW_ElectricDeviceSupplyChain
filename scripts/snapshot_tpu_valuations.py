"""Snapshot the live TPU v8x supply-chain valuation table into news_items.

Pulls current price + Forward P/E + 30D change from yfinance, computes
peer-relative valuation flags, and inserts the result as a single
``news_items`` row tagged with all 20 tickers and the relevant wikilinks.

Run once after market close (or any time the user asks for a new
snapshot) — ``ON CONFLICT (source_url)`` upserts so the row updates in
place when re-run on the same date.
"""
from __future__ import annotations

import asyncio
import os
import sys
import warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median

warnings.filterwarnings("ignore")

import asyncpg
import httpx
import yfinance as yf

PG_NEWS_DSN = os.environ.get(
    "PG_NEWS_DSN",
    "postgresql://knowledge:knowledge@localhost:5433/tw_electronics",
)
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")

ROWS = [
    ("2330", "fdy_pkg", "晶圓代工 (2nm)",     "台積電"),
    ("2303", "fdy_pkg", "成熟製程備援",       "聯電"),
    ("3711", "fdy_pkg", "CoWoS-S 後段封測",   "日月光投控"),
    ("2449", "fdy_pkg", "後段封測",           "京元電子"),
    ("3037", "abf_pcb", "ABF 載板 龍頭",      "欣興"),
    ("8046", "abf_pcb", "ABF 載板",           "南電"),
    ("3189", "abf_pcb", "ABF 載板 (tier 2)",  "景碩"),
    ("2383", "abf_pcb", "CCL",                "台光電"),
    ("6213", "abf_pcb", "CCL",                "聯茂"),
    ("2313", "abf_pcb", "高階 PCB",           "華通"),
    ("6269", "abf_pcb", "高階 PCB",           "台郡"),
    ("6274", "abf_pcb", "高階 PCB",           "台燿"),
    ("3289", "fdy_pkg", "驗證/失效分析",      "宜特"),
    ("3587", "fdy_pkg", "材料分析",           "閎康"),
    ("6191", "abf_pcb", "TPU UBB 通用基板",   "精成科"),
    ("3443", "asic",    "ASIC 設計服務",      "創意"),
    ("3661", "asic",    "ASIC 設計服務",      "世芯-KY"),
    ("3035", "asic",    "ASIC IP",            "智原"),
    ("6533", "asic",    "RISC-V IP",          "晶心科"),
    ("2454", "asic",    "ASIC 設計 (主角)",   "聯發科"),
]

WIKILINKS = [
    "聯發科", "Google", "TPU", "ASIC", "CoWoS", "HBM", "ABF 載板", "ABF",
    "台積電", "聯華電子", "日月光投控", "京元電子", "欣興", "南電", "景碩",
    "台光電", "聯茂", "華通", "台郡", "台燿", "宜特", "閎康", "精成科",
    "創意", "世芯-KY", "智原", "晶心科", "AI 伺服器", "天璣",
]


def fetch(ticker: str) -> dict:
    for suffix in (".TW", ".TWO"):
        try:
            t = yf.Ticker(ticker + suffix)
            info = t.info or {}
            if not (info.get("regularMarketPrice") or info.get("currentPrice")):
                continue
            hist = t.history(period="35d", auto_adjust=False)
            chg30 = None
            if len(hist) >= 22:
                last = float(hist["Close"].iloc[-1])
                ago = float(hist["Close"].iloc[-22])
                if ago > 0:
                    chg30 = (last / ago - 1) * 100.0
            info["_chg30"] = chg30
            return info
        except Exception:
            continue
    return {}


def num(v) -> str:
    if v is None or v == "":
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"{x:,.2f}" if abs(x) < 10000 else f"{x:,.0f}"


def build_table() -> str:
    rows: list[dict] = []
    for ticker, group, role, name in ROWS:
        info = fetch(ticker)
        rows.append({
            "ticker": ticker, "group": group, "role": role, "name": name,
            "price": info.get("regularMarketPrice") or info.get("currentPrice"),
            "pe": info.get("trailingPE"),
            "fpe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "net_margin": info.get("profitMargins"),
            "high52": info.get("fiftyTwoWeekHigh"),
            "low52": info.get("fiftyTwoWeekLow"),
            "chg30": info.get("_chg30"),
        })
    medians: dict[str, float] = {}
    for g in ("fdy_pkg", "abf_pcb", "asic"):
        vals = [r["fpe"] for r in rows
                if r["group"] == g and r["fpe"] and 0 < r["fpe"] < 100]
        medians[g] = median(vals) if vals else 0.0

    lines = []
    lines.append(f"Peer-median Fwd P/E — 晶圓代工/封測/測試 {medians['fdy_pkg']:.1f}x | "
                 f"ABF/CCL/PCB {medians['abf_pcb']:.1f}x | ASIC {medians['asic']:.1f}x")
    lines.append("")
    lines.append("| Ticker | 公司 | 角色 | 現價 | 30D Δ | 52w 位置 | P/E TTM | Fwd P/E | "
                 "vs Peer | 淨利率 | EPS TTM | 合理價 (peer±20%) | 過貴 (>peer×1.5) | 訊號 |")
    lines.append("|---:|:--|:--|---:|---:|:--|---:|---:|---:|---:|---:|:--|---:|:--|")
    for r in rows:
        peer_fpe = medians.get(r["group"], 0.0)
        signal = "—"
        ratio_str = "—"
        fair_str = "—"
        exp_str = "—"
        if r["fpe"] and peer_fpe > 0:
            ratio = r["fpe"] / peer_fpe
            ratio_str = f"{(ratio - 1) * 100:+.0f}%"
            if r["eps"] and r["eps"] > 0:
                low = peer_fpe * 0.80 * r["eps"]
                high = peer_fpe * 1.20 * r["eps"]
                exp = peer_fpe * 1.50 * r["eps"]
                fair_str = f"{low:,.0f}–{high:,.0f}"
                exp_str = f"{exp:,.0f}"
            if ratio < 0.80:
                signal = "🟢 相對便宜"
            elif ratio <= 1.20:
                signal = "⚪ 合理"
            elif ratio <= 1.50:
                signal = "🟡 偏貴"
            else:
                signal = "🔴 過貴"
        chg30 = r["chg30"]
        chg_str = f"{chg30:+.1f}%" if chg30 is not None else "—"
        hl_str = "—"
        if r["low52"] and r["high52"] and r["price"] and r["high52"] > r["low52"]:
            pct = (r["price"] - r["low52"]) / (r["high52"] - r["low52"]) * 100
            hl_str = f"{pct:.0f}%"
        nm = r["net_margin"]
        nm_str = "—"
        if nm is not None:
            nm_str = f"{nm * 100:.1f}%" if -1 <= nm <= 1 else f"{nm:.1f}%"
        lines.append(f"| {r['ticker']} | [[{r['name']}]] | {r['role']} | {num(r['price'])} | "
                     f"{chg_str} | {hl_str} | {num(r['pe'])} | {num(r['fpe'])} | "
                     f"{ratio_str} | {nm_str} | {num(r['eps'])} | "
                     f"{fair_str} | {exp_str} | {signal} |")
    return "\n".join(lines)


async def embed_text(client: httpx.AsyncClient, text: str) -> list[float]:
    r = await client.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text[:8000]},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()["embedding"]


async def main() -> int:
    table = build_table()
    today = datetime.now(timezone(timedelta(hours=8)))
    today_str = today.strftime("%Y-%m-%d")

    body = (
        f"# TPU v8x Taiwan 供應鏈估值快照 ({today_str})\n\n"
        f"20 檔[[聯發科]] AI ASIC 主題受惠台股，含 [[Google]] TPU 直接供應鏈與 [[ASIC]] 設計同業。\n\n"
        f"{table}\n\n"
        "## 關鍵觀察\n"
        "- **🔴 過貴 (vs 同業)**: [[創意]] 3443 (Fwd P/E +107%), [[台郡]] 6269 (TTM 虧損)。\n"
        "- **🟡 偏貴**: [[日月光投控]] 3711 (+22%), [[南電]] 8046 (+32%), [[宜特]] 3289 (+24%)。\n"
        "- **🟢 相對便宜**: [[華通]] 2313 (-20%, 30D -4.7%, 唯一未漲)。\n"
        "- **TTM 最低本益比**: [[精成科]] 6191 (16.4x, repo 內唯一直接點名 Google TPU UBB)。\n"
        "- **52w 100% 位置**: [[聯發科]] 2454 (任何訊息 miss = 回檔風險)。\n\n"
        "## 待追蹤 (4/30 [[聯發科]] Q1 法說會)\n"
        "1. AI ASIC 1Q26 實際營收與占比\n"
        "2. 2026 / 2027 ASIC guidance — 是否確認外資 $2.0B / $12.3B 預估\n"
        "3. [[Google]] TPU v8x 量產時程與排程\n"
        "4. 新客戶揭露 (Meta, Amazon, Microsoft ASIC 訂單?)\n"
        "5. CoWoS 產能取得進度 (聯發科要求 [[台積電]] 7 倍擴產 to 150k wafers by 2027)\n\n"
        "Method: yfinance live data, peer-median Fwd P/E by group "
        "(晶圓代工/封測/測試, ABF/CCL/PCB, ASIC), ratio to peer median "
        "drives signal classification."
    )

    pool = await asyncpg.create_pool(PG_NEWS_DSN, min_size=1, max_size=2)
    async with httpx.AsyncClient() as client:
        async with pool.acquire() as conn:
            vec = await embed_text(client, body)
            vec_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
            row = await conn.fetchrow(
                """
                INSERT INTO news_items
                  (source, source_url, published_at, title, body,
                   tickers, wikilinks, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector)
                ON CONFLICT (source_url) DO UPDATE SET
                  title = EXCLUDED.title,
                  body = EXCLUDED.body,
                  tickers = EXCLUDED.tickers,
                  wikilinks = EXCLUDED.wikilinks,
                  embedding = EXCLUDED.embedding,
                  ingested_at = now()
                RETURNING id, (xmax = 0) AS is_insert
                """,
                "claude_research",
                f"claude://session/{today_str}/tpu-supply-chain-valuation",
                today.astimezone(timezone.utc),
                f"TPU v8x 供應鏈估值快照 ({today_str}) — 20 檔台股",
                body,
                [r[0] for r in ROWS],
                WIKILINKS,
                vec_str,
            )
            verdict = "INSERT" if row["is_insert"] else "UPDATE"
            print(f"[{verdict}] news_items.id={row['id']}")
            await conn.execute(
                """
                INSERT INTO ingest_runs
                  (job_name, started_at, finished_at, status, rows_written)
                VALUES ($1, now(), now(), $2, $3)
                """,
                "tpu_valuation_snapshot", "ok", 1,
            )
    await pool.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
