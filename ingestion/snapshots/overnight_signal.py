"""Daily TXF overnight composite signal — upsert into ``news_items``.

Combines five overnight-information components measured at TPE 08:45 each
trading morning:

- 外資 net flow on day t-1 (FinMind ``TaiwanStockTotalInstitutionalInvestors``)
- USD/TWD close-to-close return (yfinance ``TWD=X``)
- S&P 500 close-to-close return (yfinance ``^GSPC``)
- TSM ADR close-to-close return (yfinance ``TSM``)
- ^SOX close-to-close return (yfinance ``^SOX``)

Each component is z-scored against its trailing 60d distribution. The composite
is a fixed-weight linear combination producing a single z-score; |z| > 0.5
emits a directional call. Backtest 2023-01 to 2026-04 reports IC 0.42 / hit
rate 67.6%; see ``analysis/reports/overnight_signal_backtest_2026-04-29.md``.

Designed to run from :mod:`ingestion.scheduler` via the
``overnight_signal_daily`` job (08:45 Asia/Taipei, Mon-Fri) — well before the
TWSE 09:00 open so the body can be read pre-market.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
import warnings
from datetime import date, datetime, timedelta, timezone

warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf

from .. import db

LOGGER = logging.getLogger("ingestion.snapshots.overnight_signal")

YF_TICKERS = ["^TWII", "^GSPC", "^SOX", "TSM", "TWD=X"]
ZSCORE_WINDOW = 60
LOOKBACK_DAYS = 130

# Weights from plan (user spec). Backtest IC = +0.4190, hit rate = 67.65%.
# Grid-search optimum is `(0.00, -0.10, 0.40, 0.30, 0.20)` for IC = +0.5054,
# but we keep foreign_net in the linear combination to preserve a 籌碼 read in
# the output body even when its standalone IC is small.
WEIGHTS = {
    "foreign_net": 0.25,
    "usdtwd": -0.15,
    "sp500": 0.15,
    "tsm": 0.25,
    "sox": 0.20,
}

FINMIND_API = "https://api.finmindtrade.com/api/v4/data"


def _fetch_yfinance_history(start: str, end: str) -> pd.DataFrame:
    df = yf.download(
        YF_TICKERS, start=start, end=end, auto_adjust=False, progress=False
    )
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"].copy()
    else:
        close = df[["Close"]].rename(columns={"Close": YF_TICKERS[0]})
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close


def _fetch_finmind_foreign_net(start: str, end: str) -> pd.Series:
    url = f"{FINMIND_API}?{urllib.parse.urlencode({'dataset': 'TaiwanStockTotalInstitutionalInvestors', 'start_date': start, 'end_date': end})}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read().decode())
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind error: {payload.get('msg', payload)}")
    rows = payload.get("data") or []
    df = pd.DataFrame(rows)
    df = df[df["name"] == "Foreign_Investor"]
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["foreign_net"] = df["buy"].astype(float) - df["sell"].astype(float)
    return df.set_index("date")["foreign_net"].sort_index()


def _build_features(close: pd.DataFrame, foreign_net: pd.Series) -> pd.DataFrame:
    """Same alignment logic as the backtest. Returns a frame indexed on TWII
    trading dates with columns: foreign_net, usdtwd, sp500, tsm, sox."""
    ret = close.pct_change()
    twii = ret["^TWII"]

    us_cols = ["^GSPC", "^SOX", "TSM", "TWD=X"]
    us_ret = ret[us_cols].copy()
    us_ret.index = us_ret.index + pd.Timedelta(days=1)
    us_aligned = us_ret.reindex(twii.index, method="ffill").rename(
        columns={"^GSPC": "sp500", "^SOX": "sox", "TSM": "tsm", "TWD=X": "usdtwd"}
    )
    foreign_lagged = foreign_net.shift(1).reindex(twii.index, method="ffill")
    feat = pd.concat([us_aligned, foreign_lagged.rename("foreign_net")], axis=1)
    return feat.dropna()


def _zscore_latest(s: pd.Series, window: int = ZSCORE_WINDOW) -> tuple[float, float, float]:
    """Returns (raw_value_today, mean, std) for the trailing window."""
    tail = s.dropna().tail(window + 1)
    if len(tail) < 10:
        raise RuntimeError(f"insufficient history for z-score: {len(tail)} < 10")
    today_v = float(tail.iloc[-1])
    hist = tail.iloc[:-1]  # exclude today from the window mean/std
    return today_v, float(hist.mean()), float(hist.std(ddof=0))


def _direction_call(z: float) -> str:
    if z > 0.75:
        return "🟢 強多 (long bias)"
    if z > 0.25:
        return "🟢 偏多 (mild long)"
    if z < -0.75:
        return "🔴 強空 (short bias)"
    if z < -0.25:
        return "🔴 偏空 (mild short)"
    return "⚪ 中性 (flat)"


def _format_value(component: str, raw: float) -> str:
    if component == "foreign_net":
        return f"{raw / 1e8:+.2f} 億 TWD"
    return f"{raw * 100:+.3f}%"


def _render_body(today_str: str, comp: dict, composite_z: float) -> str:
    lines = [
        f"# TXF Overnight 複合訊號 ({today_str})",
        "",
        "預測 TPE 今日 (open-to-close) ^TWII 方向。"
        " 訊號於 08:45 TPE 自動生成，整合 5 個 overnight 因子。",
        "",
        "## 組成因子 (z-score vs 60d trailing)",
        "",
        "| 因子 | 今日值 | 60d 平均 | 60d std | z-score | 權重 | 貢獻 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("foreign_net", "usdtwd", "sp500", "tsm", "sox"):
        c = comp[name]
        contrib = WEIGHTS[name] * c["z"]
        lines.append(
            f"| `{name}` | {_format_value(name, c['raw'])} | "
            f"{_format_value(name, c['mean'])} | {_format_value(name, c['std'])} | "
            f"{c['z']:+.3f} | {WEIGHTS[name]:+.2f} | {contrib:+.3f} |"
        )
    lines += [
        "",
        f"## 複合 z-score = **{composite_z:+.3f}** → {_direction_call(composite_z)}",
        "",
        "## 解讀",
        "",
        f"- **z > +0.75**: 強多偏向；歷史 hit rate (backtest) 67.6%, IC 0.42。",
        f"- **z < −0.75**: 強空偏向；對應反向。",
        f"- **|z| < 0.25**: overnight 訊號中性，無顯著方向。",
        "",
        "*訊號為純量化 overnight 預測，不含 intraday 籌碼或新聞驅動。執行請結合風控與其他訊號。*",
        "",
        "_詳見 backtest 報告: `analysis/reports/overnight_signal_backtest_2026-04-29.md`_",
    ]
    return "\n".join(lines)


async def build_and_upsert_signal() -> int:
    """Build today's overnight composite and upsert into ``news_items``.

    Returns ``1`` (idempotent upsert keyed by source_url)."""
    today = datetime.now(timezone(timedelta(hours=8)))
    today_str = today.strftime("%Y-%m-%d")
    end = today.date()
    start_yf = end - timedelta(days=LOOKBACK_DAYS)

    close = _fetch_yfinance_history(start_yf.isoformat(), (end + timedelta(days=1)).isoformat())
    foreign = _fetch_finmind_foreign_net(start_yf.isoformat(), end.isoformat())
    feat = _build_features(close, foreign)
    if feat.empty:
        raise RuntimeError("no features after alignment — check data sources")

    comp: dict = {}
    for name in ("foreign_net", "usdtwd", "sp500", "tsm", "sox"):
        raw, mean, std = _zscore_latest(feat[name])
        z = (raw - mean) / std if std > 0 else 0.0
        comp[name] = {"raw": raw, "mean": mean, "std": std, "z": z}

    composite_z = sum(WEIGHTS[k] * comp[k]["z"] for k in WEIGHTS)

    body = _render_body(today_str, comp, composite_z)
    title = f"TXF Overnight 複合訊號 ({today_str}) z={composite_z:+.2f}"

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
              embedding = EXCLUDED.embedding,
              ingested_at = now()
            RETURNING id
            """,
            "overnight_signal",
            f"claude://signals/txf_overnight/{today_str}",
            today.astimezone(timezone.utc),
            title,
            body,
            ["TXF", "^TWII", "TSM", "^SOX", "^GSPC", "TWD=X"],
            ["[[台股大盤]]", "[[台指期]]", "[[費城半導體指數]]", "[[台積電 ADR]]"],
            vec_str,
        )
    LOGGER.info(
        "overnight_signal upserted news_items.id=%s composite_z=%+.3f",
        result["id"], composite_z,
    )
    return 1
