"""TPU v8x supply-chain valuation snapshot — daily upsert into ``news_items``.

Combines three live data sources:
- yfinance: price, P/E TTM, Forward P/E, EPS, net margin, 30D change, 52w hi/lo
- TWSE T86: 5-day per-stock 三大法人 for upper-board listings
- TPEX dailyTrade: 5-day 三大法人 for OTC listings (6274 / 3289 / 3587)

Builds a Markdown body classifying each ticker by peer-relative Forward P/E and
籌碼 signal (foreign 1D/5D net + total 5D), then upserts a single row keyed
by ``claude://snapshots/tpu_supply_chain/{date}``.

Designed to be called from :mod:`ingestion.scheduler` via the
``tpu_snapshot_daily`` job (16:30 Asia/Taipei, Mon-Fri). The CLI shim at
``scripts/snapshot_tpu_valuations.py`` re-invokes :func:`build_and_upsert_snapshot`
for ad-hoc runs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
import warnings
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any

warnings.filterwarnings("ignore")

import yfinance as yf

from .. import db

LOGGER = logging.getLogger("ingestion.snapshots.tpu")

# (ticker, peer_group, role, name, marketplace)
_ROWS: list[tuple[str, str, str, str, str]] = [
    ("2330", "fdy_pkg", "晶圓代工 (2nm)",     "台積電",       "TWSE"),
    ("2303", "fdy_pkg", "成熟製程備援",       "聯電",         "TWSE"),
    ("3711", "fdy_pkg", "CoWoS-S 後段封測",   "日月光投控",   "TWSE"),
    ("2449", "fdy_pkg", "後段封測",           "京元電子",     "TWSE"),
    ("3037", "abf_pcb", "ABF 載板 龍頭",      "欣興",         "TWSE"),
    ("8046", "abf_pcb", "ABF 載板",           "南電",         "TWSE"),
    ("3189", "abf_pcb", "ABF 載板 (tier 2)",  "景碩",         "TWSE"),
    ("2383", "abf_pcb", "CCL",                "台光電",       "TWSE"),
    ("6213", "abf_pcb", "CCL",                "聯茂",         "TWSE"),
    ("2313", "abf_pcb", "高階 PCB",           "華通",         "TWSE"),
    ("6269", "abf_pcb", "高階 PCB",           "台郡",         "TWSE"),
    ("6274", "abf_pcb", "高階 PCB",           "台燿",         "TPEX"),
    ("3289", "fdy_pkg", "驗證/失效分析",      "宜特",         "TPEX"),
    ("3587", "fdy_pkg", "材料分析",           "閎康",         "TPEX"),
    ("6191", "abf_pcb", "TPU UBB 通用基板",   "精成科",       "TWSE"),
    ("3443", "asic",    "ASIC 設計服務",      "創意",         "TWSE"),
    ("3661", "asic",    "ASIC 設計服務",      "世芯-KY",     "TWSE"),
    ("3035", "asic",    "ASIC IP",            "智原",         "TWSE"),
    ("6533", "asic",    "RISC-V IP",          "晶心科",       "TPEX"),
    ("2454", "asic",    "ASIC 設計 (主角)",   "聯發科",       "TWSE"),
]

_WIKILINKS = [
    "聯發科", "Google", "TPU", "ASIC", "CoWoS", "HBM", "ABF 載板", "ABF",
    "台積電", "聯華電子", "日月光投控", "京元電子", "欣興", "南電", "景碩",
    "台光電", "聯茂", "華通", "台郡", "台燿", "宜特", "閎康", "精成科",
    "創意", "世芯-KY", "智原", "晶心科", "AI 伺服器", "天璣",
]

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)"}


# ─── data fetchers ─────────────────────────────────────────────────────────


def _trading_dates_back(n: int) -> list[str]:
    """Last ``n`` weekdays as ``YYYYMMDD`` strings (newest first)."""
    out: list[str] = []
    d = date.today()
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return out


def _to_int(s: Any) -> int:
    if s is None:
        return 0
    try:
        return int(str(s).replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return 0


def _to_float(s: Any) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(str(s).replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return None


def _http_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        LOGGER.warning("http_json failed for %s: %s", url, exc)
        return {}


def _fetch_twse_t86(date_str: str, want: set[str]) -> dict[str, dict]:
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALL&response=json"
    data = _http_json(url)
    out: dict[str, dict] = {}
    for row in data.get("data", []):
        if len(row) < 19:
            continue
        code = str(row[0]).strip()
        if code in want:
            out[code] = {
                "foreign_net": _to_int(row[4]),
                "trust_net":   _to_int(row[10]),
                "dealer_net":  _to_int(row[11]),
                "total_net":   _to_int(row[18]),
            }
    return out


def _fetch_tpex_3insti(date_str: str, want: set[str]) -> dict[str, dict]:
    """Fetch TPEX 三大法人 daily breakdown.

    Date param is in ROC form (民國年/月/日, e.g. ``115/04/27``). Column
    layout (24 fields) verified against today's payload: foreign_net=col 4,
    trust_net=col 13, dealer_net=col 22 (自營商合計), total=col 23.
    """
    yyyy = int(date_str[:4])
    roc = f"{yyyy - 1911}/{date_str[4:6]}/{date_str[6:8]}"
    url = (
        "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"
        f"?type=Daily&id=&response=json&d={roc}"
    )
    data = _http_json(url)
    out: dict[str, dict] = {}
    for tbl in data.get("tables", []):
        for row in tbl.get("data", []):
            if len(row) < 24:
                continue
            code = str(row[0]).strip()
            if code in want:
                out[code] = {
                    "foreign_net": _to_int(row[4]),
                    "trust_net":   _to_int(row[13]),
                    "dealer_net":  _to_int(row[22]),
                    "total_net":   _to_int(row[23]),
                }
    return out


def _fetch_yfinance(ticker: str) -> dict:
    """Try .TW first, fall back to .TWO; include 30-day price change."""
    for suffix in (".TW", ".TWO"):
        try:
            t = yf.Ticker(ticker + suffix)
            info = t.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            if not price:
                continue
            try:
                hist = t.history(period="35d", auto_adjust=False)
            except Exception:
                hist = None
            chg30 = None
            if hist is not None and len(hist) >= 22:
                last = float(hist["Close"].iloc[-1])
                ago = float(hist["Close"].iloc[-22])
                if ago > 0:
                    chg30 = (last / ago - 1.0) * 100.0
            info["_chg30"] = chg30
            return info
        except Exception as exc:
            LOGGER.debug("yfinance %s%s failed: %s", ticker, suffix, exc)
            continue
    return {}


def _gather_institutional_flow(want_twse: set[str], want_tpex: set[str]) -> dict[str, list[tuple]]:
    """Return ``{ticker: [(date, foreign, trust, dealer, total), ...]}`` last 5 days.

    One TWSE call + one TPEX call per date (skipped when respective set empty).
    Both endpoints rate-limited at ~2 req/sec — 2.5 sec sleep between dates.
    """
    flows: dict[str, list[tuple]] = {t: [] for t in want_twse | want_tpex}
    dates = _trading_dates_back(8)  # 8 weekdays → ≥5 trading days even with holidays
    for ds in dates:
        if want_twse:
            tw = _fetch_twse_t86(ds, want_twse)
            for code, d in tw.items():
                flows[code].append((ds, d["foreign_net"], d["trust_net"],
                                    d["dealer_net"], d["total_net"]))
            asyncio_sleep_sync(2.5)
        if want_tpex:
            tp = _fetch_tpex_3insti(ds, want_tpex)
            for code, d in tp.items():
                flows[code].append((ds, d["foreign_net"], d["trust_net"],
                                    d["dealer_net"], d["total_net"]))
            asyncio_sleep_sync(2.5)
    # Trim to last 5 entries per ticker
    for code in flows:
        flows[code] = sorted(flows[code], reverse=True)[:5]
    return flows


def asyncio_sleep_sync(seconds: float) -> None:
    """Plain ``time.sleep``; named to make the blocking nature explicit."""
    import time
    time.sleep(seconds)


# ─── snapshot rendering ────────────────────────────────────────────────────


def _fmt_num(v: Any) -> str:
    if v is None or v == "":
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"{x:,.2f}" if abs(x) < 10000 else f"{x:,.0f}"


def _render_body(rows: list[dict], medians: dict[str, float], today_str: str) -> str:
    lines: list[str] = []
    lines.append(f"# TPU v8x Taiwan 供應鏈估值快照 ({today_str})")
    lines.append("")
    lines.append(f"20 檔 [[聯發科]] AI ASIC 主題受惠台股。")
    lines.append(
        f"Peer-median Forward P/E — 晶圓代工/封測/測試 {medians['fdy_pkg']:.1f}x"
        f" | ABF/CCL/PCB {medians['abf_pcb']:.1f}x | ASIC {medians['asic']:.1f}x"
    )
    lines.append("")
    lines.append(
        "| Ticker | 公司 | 角色 | 現價 | 30D Δ | 52w 位置 | P/E TTM | Fwd P/E | "
        "vs Peer | 淨利率 | EPS | 5D 外資 | 5D 投信 | 5D 總計 | 1D 外資 | 5D Px | 訊號 |"
    )
    lines.append("|---:|:--|:--|---:|---:|:--|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:--|")

    for r in rows:
        peer_fpe = medians.get(r["group"], 0.0)
        signal = "—"
        ratio_str = "—"
        if r["fpe"] and peer_fpe > 0:
            ratio = r["fpe"] / peer_fpe
            ratio_str = f"{(ratio - 1) * 100:+.0f}%"
            if ratio < 0.80:
                signal = "🟢 相對便宜"
            elif ratio <= 1.20:
                signal = "⚪ 合理"
            elif ratio <= 1.50:
                signal = "🟡 偏貴"
            else:
                signal = "🔴 過貴"

        # Augment signal with chip-flow alerts
        chip_flags: list[str] = []
        if r.get("flow_5d"):
            f5 = r["flow_5d"]
            if f5["foreign_5d"] < -2_000_000:
                chip_flags.append("外資5D連賣")
            if f5["total_5d"] < -2_000_000:
                chip_flags.append("法人連賣")
            if f5["foreign_1d"] < -5_000_000:
                chip_flags.append("外資1D大賣")
            if f5["total_5d"] > 3_000_000:
                chip_flags.append("法人強買")
        if chip_flags:
            signal = f"{signal} / " + " / ".join(chip_flags)

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

        f5 = r.get("flow_5d") or {}
        f5_for = f5.get("foreign_5d")
        f5_tr = f5.get("trust_5d")
        f5_tot = f5.get("total_5d")
        f1_for = f5.get("foreign_1d")
        f5_px = f5.get("px_chg_5d")

        def _k(v):
            return "—" if v is None else f"{v / 1000:+,.0f}"

        def _pxc(v):
            return "—" if v is None else f"{v:+.1f}%"

        lines.append(
            f"| {r['ticker']} | [[{r['name']}]] | {r['role']} | {_fmt_num(r['price'])} | "
            f"{chg_str} | {hl_str} | {_fmt_num(r['pe'])} | {_fmt_num(r['fpe'])} | "
            f"{ratio_str} | {nm_str} | {_fmt_num(r['eps'])} | "
            f"{_k(f5_for)} | {_k(f5_tr)} | {_k(f5_tot)} | {_k(f1_for)} | "
            f"{_pxc(f5_px)} | {signal} |"
        )

    lines.extend([
        "",
        "## 觀察重點",
        "- **🔴 過貴 (vs 同業)**: Fwd P/E > peer median × 1.5 或 5D 籌碼極端負向。",
        "- **籌碼面警示**: 5D 外資連賣 + 法人連賣 + 5D 跌 三條件齊備視為短線避開。",
        "- **52w 100% 位置 + 高動能**: 任何訊息 miss = 回檔風險。",
        "",
        "Method: yfinance live multiples + TWSE T86 + TPEX dailyTrade for institutional flow. "
        "Peer-median Fwd P/E by group (晶圓代工/封測/測試, ABF/CCL/PCB, ASIC). "
        "5D flows in 千股 (positive = net buy)."
    ])
    return "\n".join(lines)


# ─── main entry ────────────────────────────────────────────────────────────


async def build_and_upsert_snapshot() -> int:
    """Build today's TPU snapshot and upsert into ``news_items``.

    Returns ``1`` so the scheduler logs ``rows_written=1`` (idempotent upsert).
    """
    rows: list[dict] = []
    for ticker, group, role, name, market in _ROWS:
        info = _fetch_yfinance(ticker)
        rows.append({
            "ticker": ticker, "group": group, "role": role,
            "name": name, "market": market,
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

    # Institutional flow (sync I/O — runs in a thread to keep the scheduler async)
    want_twse = {r["ticker"] for r in rows if r["market"] == "TWSE"}
    want_tpex = {r["ticker"] for r in rows if r["market"] == "TPEX"}
    flows = await asyncio.to_thread(_gather_institutional_flow, want_twse, want_tpex)

    for r in rows:
        f = flows.get(r["ticker"]) or []
        if not f:
            continue
        f5 = {
            "foreign_5d": sum(x[1] for x in f),
            "trust_5d":   sum(x[2] for x in f),
            "dealer_5d":  sum(x[3] for x in f),
            "total_5d":   sum(x[4] for x in f),
            "foreign_1d": f[0][1],
            "total_1d":   f[0][4],
            "px_chg_5d":  None,  # left None — yfinance 30D is the proxy already
        }
        r["flow_5d"] = f5

    today = datetime.now(timezone(timedelta(hours=8)))
    today_str = today.strftime("%Y-%m-%d")
    body = _render_body(rows, medians, today_str)
    title = f"TPU v8x 供應鏈估值+籌碼快照 ({today_str}) — 20 檔台股"

    pool = await db.get_pool()
    embedding = await db.embed(body[:8000])
    vec_str = db.vector_literal(embedding)

    async with pool.acquire() as conn:
        result = await conn.fetchrow(
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
            RETURNING id
            """,
            "claude_research",
            f"claude://snapshots/tpu_supply_chain/{today_str}",
            today.astimezone(timezone.utc),
            title,
            body,
            [r[0] for r in _ROWS],
            _WIKILINKS,
            vec_str,
        )
    LOGGER.info("tpu_snapshot upserted news_items.id=%s", result["id"])
    return 1
