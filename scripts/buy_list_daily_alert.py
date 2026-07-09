"""buy_list_daily_alert.py — Daily portfolio digest 08:50 pre-open.

Reads data/buy_list_state.json (curated portfolio picks + watch/avoid),
fetches latest close + 5D/20D institutional flow, and pushes a compact
Markdown digest to claude:inbox topic=buy-list.

Pre-open focus:
    - 昨日收盤 + 距 entry/stop/TP 位置
    - 5D 外資 flow change (是否觸發 upgrade/downgrade)
    - BB Buy/Watch/Avoid status (from bb-squeeze.log 昨日 scan)
    - 三個必看 (near stop, near TP1, priority action)

CLI:
    python scripts/buy_list_daily_alert.py            # live push
    python scripts/buy_list_daily_alert.py --dry-run  # print only
    python scripts/buy_list_daily_alert.py --state PATH
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg2

from utils import find_ticker_files  # scripts/ is already on sys.path in this module

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "data" / "buy_list_state.json"
BB_LOG = Path.home() / "Library" / "Logs" / "bb-squeeze.log"

PB_LIGHTS_KEY = "h:agent:pb_lights"
PB_LIGHT_EMOJI = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢", "N/A": "⚪"}

DB_CONFIG = {
    "host": "localhost", "port": 5432, "dbname": "tmf_market_data",
    "user": "tmf", "password": os.environ.get("TMF_PG_PASSWORD", "tmf_dev_2026"),
    "connect_timeout": 5,
}

INBOX_STREAM = "claude:inbox"


def load_state(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_pb_lights(redis_client) -> dict:
    """Read h:agent:pb_lights → {ticker: record}. Fail-safe: missing/bad → skipped; redis error → {}."""
    try:
        raw = redis_client.hgetall(PB_LIGHTS_KEY)
    except Exception as e:
        print(f"[warn] load_pb_lights: {PB_LIGHTS_KEY} unreachable: {e}", file=sys.stderr)
        return {}
    out = {}
    for k, v in (raw or {}).items():
        if k.startswith("_"):
            continue
        try:
            out[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def parse_report_valuation(ticker: str, files: dict | None = None) -> dict | None:
    """From the report's 估值指標 block: {pe, yield_pct, base_price}. Missing file → None; unparseable field → None."""
    files = files if files is not None else find_ticker_files([ticker])
    fp = files.get(ticker)
    if not fp:
        return None
    text = Path(fp).read_text(encoding="utf-8", errors="replace")
    idx = text.find("估值指標")
    if idx == -1:
        return None
    header = text[idx:text.find("\n", idx)]
    mp = re.search(r"股價\s*\$([\d,]+\.?\d*)", header)
    base_price = float(mp.group(1).replace(",", "")) if mp else None
    my = re.search(r"殖利率\s*([\d.]+)%", header)
    yield_pct = float(my.group(1)) if my else None
    pe = None
    rows = [ln for ln in text[idx:].splitlines() if ln.strip().startswith("|")]
    # rows[0] header, rows[1] separator, rows[2] data
    if len(rows) >= 3:
        cells = [c.strip() for c in rows[2].strip().strip("|").split("|")]
        if cells and cells[0] not in ("N/A", ""):
            try:
                pe = float(cells[0])
            except ValueError:
                pe = None
    return {"pe": pe, "yield_pct": yield_pct, "base_price": base_price}


def recompute_valuation(report_val: dict | None, latest_close: float | None) -> dict:
    """Rescale PE (∝ price) and 殖利率 (∝ 1/price) from report base price to latest close."""
    if not report_val:
        return {"pe": None, "yield_pct": None}
    base = report_val.get("base_price")
    if not base or not latest_close:
        return {"pe": None, "yield_pct": None}
    ratio = latest_close / base
    pe = report_val.get("pe")
    y = report_val.get("yield_pct")
    return {
        "pe": pe * ratio if pe is not None else None,
        "yield_pct": y / ratio if y is not None else None,
    }


def format_valuation(pb_rec: dict | None, report_val: dict | None, latest_close: float | None) -> str:
    """Compose 'P/B 7.20 🔴 · PE 64.2 · 殖 1.3%'. P/B+light from hash; PE/殖 rescaled from report."""
    rec = pb_rec or {}
    light = rec.get("light", "N/A")
    emoji = PB_LIGHT_EMOJI.get(light, "⚪")
    pb = rec.get("pb_current")
    pb_str = f"{pb:.2f}" if isinstance(pb, (int, float)) else "N/A"
    rv = recompute_valuation(report_val, latest_close)
    pe_str = f"{rv['pe']:.1f}" if rv["pe"] is not None else "N/A"
    y_str = f"{rv['yield_pct']:.1f}%" if rv["yield_pct"] is not None else "N/A"
    return f"P/B {pb_str} {emoji} · PE {pe_str} · 殖 {y_str}"


def fetch_latest_snapshot(conn, tickers: list[str]) -> dict[str, dict]:
    """For each ticker: latest close, 5D & 20D 外資/投信/自營 flow (億 TWD)."""
    result = {}
    with conn.cursor() as cur:
        # Latest close from stock_daily_ohlcv
        cur.execute("""
            SELECT DISTINCT ON (symbol) symbol, ts::date, close, volume
              FROM stock_daily_ohlcv
             WHERE symbol = ANY(%s)
               AND ts >= (CURRENT_DATE - INTERVAL '10 days')
             ORDER BY symbol, ts DESC
        """, (tickers,))
        for sym, d, c, v in cur.fetchall():
            result[sym] = {
                "latest_date": d, "latest_close": float(c),
                "latest_volume": int(v or 0),
            }

        # 5D & 20D 三大法人 flow
        for sym in tickers:
            if sym not in result:
                result[sym] = {}
            cur.execute("SELECT DISTINCT date FROM institutional_stock WHERE date <= CURRENT_DATE AND symbol=%s ORDER BY date DESC LIMIT 20", (sym,))
            dates = [r[0] for r in cur.fetchall()]
            if not dates:
                continue
            px = result[sym].get("latest_close", 0)

            def _flow(dd):
                cur.execute("""
                    SELECT SUM(foreign_net), SUM(trust_net), SUM(dealer_net),
                           SUM(foreign_net * NULLIF(close_price,0)::float),
                           SUM(trust_net * NULLIF(close_price,0)::float),
                           SUM(dealer_net * NULLIF(close_price,0)::float)
                      FROM institutional_stock
                     WHERE symbol=%s AND date = ANY(%s)
                """, (sym, dd))
                f_sh, t_sh, d_sh, f_twd, t_twd, d_twd = cur.fetchone()
                if not f_twd or f_twd == 0:
                    return (
                        float(f_sh or 0) * px / 1e8,
                        float(t_sh or 0) * px / 1e8,
                        float(d_sh or 0) * px / 1e8,
                    )
                return float(f_twd)/1e8, float(t_twd)/1e8, float(d_twd)/1e8

            f5, t5, dl5 = _flow(dates[:5])
            f20, t20, dl20 = _flow(dates[:20])
            result[sym].update({
                "f5": f5, "t5": t5, "d5": dl5,
                "f20": f20, "t20": t20, "d20": dl20,
            })
    return result


def load_disposition(path: Path | None = None) -> dict[str, dict]:
    """Load currently active disposition entries {ticker: {name,start,end,condition,action,source}}."""
    p = path or (REPO / "data" / "disposition_current.json")
    if not p.exists():
        return {}
    try:
        with open(p) as f:
            return json.load(f).get("active", {})
    except Exception:
        return {}


def parse_bb_log(days_back: int = 3) -> dict[str, str]:
    """Parse the most recent BB Squeeze block from bb-squeeze.log.
    Returns {ticker: status} where status in {"buy", "avoid", "watch"}.
    """
    if not BB_LOG.exists():
        return {}
    try:
        text = BB_LOG.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    result: dict[str, str] = {}
    # Find most recent block
    blocks = text.split("────────────────────────────────────────────────────────────")
    for block in blocks[::-1]:  # latest first
        if "BB Squeeze 巡檢" not in block:
            continue
        # Parse Buy/Avoid/Watch sections
        current_status = None
        for line in block.split("\n"):
            line = line.strip()
            if "🟢 Buy" in line:
                current_status = "buy"
            elif "🔴 Avoid" in line:
                current_status = "avoid"
            elif "🟡 Watch" in line:
                current_status = "watch"
            elif line.startswith("• ") or line.startswith("* "):
                # e.g. "• 3605 宏致 (+5.26%, vol×6.75, 5D 外資 +4.01億)"
                parts = line[2:].split()
                if parts and parts[0].isdigit():
                    result[parts[0]] = current_status
            elif current_status == "watch" and "/" in line:
                # Watch names are slash-separated on one line: "2464 盟立 / 3115..."
                for chunk in line.split("/"):
                    chunk = chunk.strip()
                    parts = chunk.split()
                    if parts and parts[0].isdigit():
                        result[parts[0]] = "watch"
        break  # only process latest block
    return result


def _fmt_pct_from_entry(current: float, entry_range: list) -> tuple[str, float]:
    """Return (label, gap_%). Positive gap means need pullback."""
    low, high = entry_range[0], entry_range[1]
    if current < low:
        gap = (low - current) / current * 100
        return f"低於進場區 {gap:+.1f}%", gap
    elif current > high:
        gap = (current - high) / current * 100
        return f"高於進場區 {gap:+.1f}% (等回測)", gap
    else:
        return "✅ 在進場區內", 0.0


def _urgency(pick: dict, snap: dict) -> tuple[str, int]:
    """Classify each pick's urgency: 0=urgent, 1=action, 2=watch."""
    close = snap.get("latest_close")
    if close is None:
        return "?", 3
    if close <= pick["stop_loss"] * 1.02:
        return "🔴 逼近停損!", 0
    if close >= pick["tp1"] * 0.98:
        return "🟢 逼近 TP1!", 0
    entry_low, entry_high = pick["entry_range"]
    if entry_low <= close <= entry_high:
        return "🟢 在進場區", 1
    if close < entry_low:
        return "🔵 低於進場區 (可加碼)", 1
    return "⚪ 高於進場區 (等回測)", 2


def build_digest(state: dict, snapshots: dict, bb_status: dict, disposition: dict | None = None) -> str:
    disposition = disposition or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 🌅 每日買入清單 巡檢 {now}", ""]
    lines.append(f"**Portfolio version:** {state.get('version','?')} · **Picks:** {len(state['picks'])} · **Watch:** {len(state.get('watch_list',[]))} · **Avoid:** {len(state.get('avoid_list',[]))}")
    lines.append("")

    # 前置 disposition 警戒段 (若 portfolio 有處置)
    disp_picks = [(p, disposition[p["ticker"]]) for p in state["picks"] if p["ticker"] in disposition]
    disp_watches = [(w, disposition[w["ticker"]]) for w in state.get("watch_list", []) if w["ticker"] in disposition]
    if disp_picks or disp_watches:
        lines.append(f"## 🚨 處置警戒 (portfolio 中處置股 {len(disp_picks)} picks + {len(disp_watches)} watches)")
        for p, d in disp_picks:
            lines.append(f"- **{p['ticker']} {p['name']}** (T{p['tier']} {p['weight_pct']}%) — {d['start']}~{d['end']} · {d['action']} · **{d['condition']}** [{d['source']}]")
        for w, d in disp_watches:
            lines.append(f"- {w['ticker']} {w['name']} (watch) — {d['start']}~{d['end']} [{d['source']}]")
        lines.append("")

    urgent = []
    active_signal = []
    monitor = []

    for pick in state["picks"]:
        sym = pick["ticker"]
        snap = snapshots.get(sym, {})
        close = snap.get("latest_close")
        bb = bb_status.get(sym, "")
        urgency_label, urgency_rank = _urgency(pick, snap)

        # Line format
        f5 = snap.get("f5", 0); f20 = snap.get("f20", 0); t20 = snap.get("t20", 0)
        bb_marker = {"buy": "🔥 BB Buy", "avoid": "🔴 BB Avoid", "watch": "🟡 BB Watch"}.get(bb, "")
        disp = disposition.get(sym)
        disp_marker = f"⚠️ 處置中 {disp['start']}~{disp['end']}" if disp else ""
        entry_str = f"${pick['entry_range'][0]}-{pick['entry_range'][1]}"
        line = (
            f"- **{sym} {pick['name']}** (T{pick['tier']}, 權重 {pick['weight_pct']}%) — "
            f"收 ${close:.1f}" if close else f"- **{sym} {pick['name']}** — 資料 N/A"
        )
        if close:
            line += f" · Entry {entry_str} · Stop ${pick['stop_loss']} · TP1 ${pick['tp1']}"
            line += f" · 5D外資 {f5:+.1f}億 · 20D外資 {f20:+.1f}億"
            if bb_marker: line += f" · {bb_marker}"
            if disp_marker: line += f" · {disp_marker}"
            line += f" · **{urgency_label}**"

        if urgency_rank == 0:
            urgent.append(line)
        elif urgency_rank == 1:
            active_signal.append(line)
        else:
            monitor.append(line)

    if urgent:
        lines.append("## 🚨 緊急 (逼近 stop/TP)")
        lines.extend(urgent)
        lines.append("")
    if active_signal:
        lines.append("## 🎯 進場區 (可分批進場)")
        lines.extend(active_signal)
        lines.append("")
    if monitor:
        lines.append("## 👀 觀察 (等回測 or 續強)")
        lines.extend(monitor)
        lines.append("")

    # BB Buy 新訊號 in bb log
    picked_syms = {p["ticker"] for p in state["picks"]}
    watched_syms = {w["ticker"] for w in state.get("watch_list", [])}
    new_bb_buys = [t for t, s in bb_status.items() if s == "buy" and t not in picked_syms and t not in watched_syms]
    if new_bb_buys:
        lines.append("## 🆕 昨日新 BB Buy (未在 portfolio)")
        for t in new_bb_buys[:10]:
            lines.append(f"- {t} (未在 portfolio, 考慮 evaluate)")
        lines.append("")

    # Watch list quick summary — 每檔顯示 close + 5D 外資 (簡潔)
    if state.get("watch_list"):
        lines.append(f"## 📋 Watch List (無部位、等訊號) — {len(state['watch_list'])} 檔")
        for w in state["watch_list"]:
            snap = snapshots.get(w["ticker"], {})
            c = snap.get("latest_close")
            f5 = snap.get("f5")
            c_str = f"${c:.1f}" if isinstance(c, (int, float)) else "N/A"
            f5_str = f" (5D外資 {f5:+.1f}億)" if isinstance(f5, (int, float)) else ""
            lines.append(f"- **{w['ticker']} {w['name']}**: {c_str}{f5_str} — {w['reason']}")
        lines.append("")

    # Avoid list (short summary)
    if state.get("avoid_list"):
        avoid_syms = [w["ticker"] for w in state["avoid_list"]]
        lines.append(f"## 🚫 Avoid ({len(avoid_syms)}): " + " / ".join(avoid_syms))
        lines.append("")

    # Watchpoints
    if state.get("watchpoints"):
        lines.append("## 🔍 Watchpoints (今日聚焦)")
        for wp in state["watchpoints"]:
            lines.append(f"- {wp}")
        lines.append("")

    lines.append(f"*源: scripts/buy_list_daily_alert.py · state {STATE_PATH.name}*")
    return "\n".join(lines)


def push_inbox(msg: str) -> bool:
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.xadd(INBOX_STREAM, {"topic": "buy-list", "msg": msg,
                              "tags": "twse,portfolio,daily,alert"})
        return True
    except Exception as e:
        print(f"[err] inbox push failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--state", default=str(STATE_PATH))
    args = p.parse_args()

    state = load_state(Path(args.state))
    all_tickers = list({p["ticker"] for p in state["picks"]}
                       | {w["ticker"] for w in state.get("watch_list", [])})

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        snapshots = fetch_latest_snapshot(conn, all_tickers)
    finally:
        conn.close()

    bb_status = parse_bb_log()
    disposition = load_disposition()
    print(f"[info] tickers snapshotted: {len(snapshots)}, BB status: {len(bb_status)}, disposition: {len(disposition)}", file=sys.stderr)

    msg = build_digest(state, snapshots, bb_status, disposition)
    print(msg)

    if not args.dry_run:
        push_inbox(msg)
        print("[ok] pushed to claude:inbox topic=buy-list", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
