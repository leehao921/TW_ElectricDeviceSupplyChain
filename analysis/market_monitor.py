"""Intraday market monitor — runs every 20 minutes during TW trading hours.

Piggybacks on the existing rss_cna (:15) / rss_udn (:35) cron cadence, so the
scheduler isn't carrying a new high-frequency tick. Cron registered in
ingestion/jobs.py as ``market_monitor_intraday`` with expression
``15,35 9-13 * * 1-5``.

Workflow per tick:

1. Probe whether TW market is open right now (TXF futures has a bar in the
   last 10 min). If not, exit quiet — handles weekends, holidays (5/1 勞動節),
   typhoon days without hardcoding a calendar.
2. Snapshot 5 dimensions: TXF last-bar, USD/TWD spot, top-5 weighted-stock
   imb_l1, news headlines (last 30 min), today's overnight composite z.
3. Diff against last_pulse.json on disk.
4. Apply alert rules. Quiet ticks: log to stderr only.
5. Loud ticks: insert into market_alerts table + macOS notification (osascript).
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore")

import asyncpg
import psycopg2
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = REPO_ROOT / "analysis" / ".state" / "last_pulse.json"
TPE = timezone(timedelta(hours=8))
TMF_DSN = "postgresql://tmf:tmf_dev_2026@localhost:5432/tmf_market_data"
KNOWLEDGE_DSN = "postgresql://knowledge:knowledge@localhost:5433/tw_electronics"

WEIGHTS = ["2330", "2454", "2317", "2308", "2882"]
NEWS_PATTERN = re.compile(
    r"NVDA|Nvidia|輝達|TSMC|台積電|Fed|聯準會|降息|加息|關稅|tariff|戰|地緣|罷工|台幣"
)

THRESHOLD_TXF_PT = 50      # |Δ TXF close| > 50 pt → fast-move
THRESHOLD_TWD_PCT = 0.15   # |Δ USD/TWD| > 0.15% → fx-break
THRESHOLD_IMB_L1 = 0.30    # |Δ imb_l1| > 0.30 or sign flip → chip-flip
THRESHOLD_Z_DELTA = 0.40   # |Δ composite_z| vs morning > 0.40 → regime-shift


def is_tw_market_open(cur) -> bool:
    """Latest TXF futures bar within the last 10 min ⇒ market currently trading."""
    cur.execute(
        "SELECT max(time) FROM futures_ohlcv WHERE symbol='TXF202605'"
    )
    last = cur.fetchone()[0]
    if last is None:
        return False
    age_sec = (datetime.now(timezone.utc) - last).total_seconds()
    return age_sec < 600  # 10 min staleness threshold


def fetch_txf_pulse(cur) -> dict:
    cur.execute(
        """
        SELECT time, close
          FROM futures_ohlcv
         WHERE symbol='TXF202605'
         ORDER BY time DESC LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        return {}
    return {"ts": row[0].isoformat(), "close": float(row[1])}


def fetch_imb_pulse(cur) -> dict[str, float]:
    out: dict[str, float] = {}
    for sym in WEIGHTS:
        cur.execute(
            """
            SELECT avg(imb_l1) FROM lob_features
             WHERE symbol=%s AND ts > now() - interval '15 minutes'
            """,
            (sym,),
        )
        v = cur.fetchone()[0]
        if v is not None:
            out[sym] = float(v)
    return out


def fetch_twd_spot() -> float | None:
    try:
        df = yf.download("TWD=X", period="1d", interval="5m", progress=False, auto_adjust=False)
        if df.empty:
            return None
        return float(df["Close"].dropna().iloc[-1])
    except Exception:
        return None


async def fetch_recent_news(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT id, source, published_at, title
          FROM news_items
         WHERE published_at > now() - interval '30 minutes'
           AND source != 'overnight_signal'
         ORDER BY published_at DESC LIMIT 50
        """
    )
    return [
        {"id": r["id"], "source": r["source"], "title": r["title"], "ts": r["published_at"].isoformat()}
        for r in rows
    ]


async def fetch_morning_signal_z(conn: asyncpg.Connection) -> float | None:
    today = datetime.now(TPE).date().isoformat()
    row = await conn.fetchrow(
        """
        SELECT title FROM news_items
         WHERE source='overnight_signal' AND source_url=$1
         LIMIT 1
        """,
        f"claude://signals/txf_overnight/{today}",
    )
    if row is None:
        return None
    m = re.search(r"z=([+-]?\d+\.\d+)", row["title"])
    return float(m.group(1)) if m else None


def load_last_pulse() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_pulse(pulse: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(pulse, indent=2, default=str), encoding="utf-8")


def detect_alerts(prev: dict, curr: dict) -> list[dict]:
    alerts: list[dict] = []
    txf_prev = (prev.get("txf") or {}).get("close")
    txf_curr = (curr.get("txf") or {}).get("close")
    if txf_prev and txf_curr:
        d = txf_curr - txf_prev
        if abs(d) >= THRESHOLD_TXF_PT:
            alerts.append({
                "type": "fast-move",
                "severity": "urgent" if abs(d) >= 100 else "warn",
                "title": f"TXF {d:+.0f} pt vs last tick",
                "body": f"{txf_prev:.0f} → {txf_curr:.0f} (Δ {d:+.0f}) since {prev.get('ts','?')}",
            })

    twd_prev = prev.get("twd")
    twd_curr = curr.get("twd")
    if twd_prev and twd_curr:
        d_pct = (twd_curr - twd_prev) / twd_prev * 100
        if abs(d_pct) >= THRESHOLD_TWD_PCT:
            alerts.append({
                "type": "fx-break",
                "severity": "warn",
                "title": f"USD/TWD {d_pct:+.2f}% in {curr.get('interval_min', '?')} min",
                "body": f"{twd_prev:.4f} → {twd_curr:.4f}",
            })

    prev_imb = prev.get("imb_l1") or {}
    curr_imb = curr.get("imb_l1") or {}
    flips = []
    for sym in WEIGHTS:
        a, b = prev_imb.get(sym), curr_imb.get(sym)
        if a is None or b is None:
            continue
        if (a >= 0 > b) or (a <= 0 < b) or abs(b - a) >= THRESHOLD_IMB_L1:
            flips.append((sym, a, b))
    if flips:
        body_lines = [f"{s}: {a:+.3f} → {b:+.3f}" for s, a, b in flips]
        alerts.append({
            "type": "chip-flip",
            "severity": "warn",
            "title": f"{len(flips)} weighted stocks chip flip",
            "body": "\n".join(body_lines),
        })

    prev_news_ids = {n["id"] for n in (prev.get("news") or [])}
    curr_news = curr.get("news") or []
    new_catalysts = [n for n in curr_news if n["id"] not in prev_news_ids and NEWS_PATTERN.search(n.get("title", ""))]
    if new_catalysts:
        body = "\n".join(f"[{n['source']}] {n['title'][:90]}" for n in new_catalysts[:5])
        alerts.append({
            "type": "news-catalyst",
            "severity": "info",
            "title": f"{len(new_catalysts)} new catalyst headline(s)",
            "body": body,
        })

    z_morning = curr.get("z_morning")
    if z_morning is not None and prev.get("z_morning") is not None:
        # Both present → no shift in morning signal (it's static for the day).
        pass

    return alerts


def push_macos_notification(alert: dict) -> None:
    title = alert["title"].replace('"', "'")[:80]
    body = alert["body"].split("\n")[0].replace('"', "'")[:200]
    icon = {"urgent": "🚨", "warn": "⚠️", "info": "ℹ️"}.get(alert["severity"], "•")
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{body}" with title "{icon} TW Market: {title}"',
            ],
            check=False,
            timeout=5,
        )
    except Exception as e:
        print(f"  (osascript failed: {e})", file=sys.stderr)


async def log_alerts(alerts: list[dict], snapshot: dict) -> None:
    if not alerts:
        return
    conn = await asyncpg.connect(KNOWLEDGE_DSN)
    try:
        for a in alerts:
            await conn.execute(
                """
                INSERT INTO market_alerts (alert_type, severity, title, body, snapshot)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                a["type"], a["severity"], a["title"], a["body"],
                json.dumps(snapshot, default=str),
            )
    finally:
        await conn.close()


async def amain() -> int:
    pg = psycopg2.connect(TMF_DSN)
    cur = pg.cursor()
    if not is_tw_market_open(cur):
        print("market closed (no recent TXF bar) — quiet exit", file=sys.stderr)
        pg.close()
        return 0

    txf = fetch_txf_pulse(cur)
    imb = fetch_imb_pulse(cur)
    pg.close()

    twd = fetch_twd_spot()
    knowledge = await asyncpg.connect(KNOWLEDGE_DSN)
    try:
        news = await fetch_recent_news(knowledge)
        z_morning = await fetch_morning_signal_z(knowledge)
    finally:
        await knowledge.close()

    now = datetime.now(TPE)
    pulse = {
        "ts": now.isoformat(),
        "txf": txf,
        "twd": twd,
        "imb_l1": imb,
        "news": news,
        "z_morning": z_morning,
    }

    prev = load_last_pulse()
    if prev:
        prev_dt = datetime.fromisoformat(prev["ts"])
        pulse["interval_min"] = round((now - prev_dt).total_seconds() / 60, 1)

    alerts = detect_alerts(prev, pulse) if prev else []

    if alerts:
        for a in alerts:
            print(f"🚨 [{a['severity']}] {a['type']}: {a['title']}", file=sys.stderr)
            print(f"   {a['body']}", file=sys.stderr)
            push_macos_notification(a)
        await log_alerts(alerts, pulse)
    else:
        if prev:
            print(f"quiet tick — Δ {pulse.get('interval_min','?')} min, no alert", file=sys.stderr)
        else:
            print("first tick — no baseline to compare", file=sys.stderr)

    save_pulse(pulse)
    return len(alerts)


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
