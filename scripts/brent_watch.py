#!/usr/bin/env python3
"""Brent 85/100 每日監測 — 美伊地緣油價因子 gate (plan: docs/plans/2026-08-24-brent-watch.md)

背景 (2026-08-24 實測): 航空 vs Brent 60日相關 -0.22~-0.27, 長榮海 +0.22 —
同一油價因子反向作用於 2603 持倉與華航左側候選。
- <85 緩和帶: 華航 Tranche2 門檻放寬 / 2603 停利階梯二輔助觸發
- >100 升溫帶: 華航降半碼 / 2603 運價順風
推 inbox topic=brent-watch, 跨線事件 severity 升級。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "data" / "brent_state.json"
LINE_LOW, LINE_HIGH = 85.0, 100.0
CORR_WIN = 60


def classify_zone(price: float) -> str:
    if price < LINE_LOW:
        return "easing"
    if price > LINE_HIGH:
        return "escalation"
    return "neutral"


def detect_cross(prev: float | None, cur: float) -> str | None:
    """跨線偵測 — 只在穿越 85/100 時觸發, 帶內移動與首次執行不觸發."""
    if prev is None:
        return None
    if prev >= LINE_LOW and cur < LINE_LOW:
        return "cross_below_85"
    if prev <= LINE_HIGH and cur > LINE_HIGH:
        return "cross_above_100"
    if prev < LINE_LOW and cur >= LINE_LOW:
        return "cross_above_85"
    if prev > LINE_HIGH and cur <= LINE_HIGH:
        return "cross_below_100"
    return None


ZONE_LABEL = {
    "easing": "緩和帶 (<85)",
    "neutral": "中性帶 (85-100)",
    "escalation": "升溫帶 (>100)",
}

GATE_HINT = {
    "easing": "華航 Tranche2 門檻放寬 (單條件即可) · 2603 停利階梯二輔助觸發 (運價敘事降溫)",
    "neutral": "維持原 gate: 華航需雙條件 · 2603 依 MA10/MA20 階梯",
    "escalation": "華航即使觸發也降半碼 · 2603 運價順風但留意乖離",
}


def build_msg(price: float, chg1d: float, chg5d: float, zone: str,
              cross: str | None, corr: dict) -> str:
    alarm = "🚨 " if cross else ""
    cross_txt = {
        "cross_below_85": "跌破 85 — 地緣溢價收斂訊號",
        "cross_above_100": "站上 100 — 地緣升溫訊號",
        "cross_above_85": "回到 85 上 — 緩和訊號取消",
        "cross_below_100": "跌回 100 下 — 升溫訊號取消",
    }.get(cross or "", "")
    lines = [f"{alarm}Brent {price:.1f} ({chg1d:+.1f}% 1D / {chg5d:+.1f}% 5D) · {ZONE_LABEL[zone]}"]
    if cross_txt:
        lines.append(f"跨線: {cross_txt}")
    if corr:
        corr_txt = " / ".join(f"{k} {v:+.2f}" for k, v in sorted(corr.items()))
        lines.append(f"60D 相關: {corr_txt}")
    lines.append(f"Gate: {GATE_HINT[zone]}")
    return "\n".join(lines)


def fetch_prices():
    """Brent + 相關標的日線; 回傳 (price, chg1d, chg5d, corr_dict)."""
    import yfinance as yf
    data = yf.download(["BZ=F", "2603.TW", "2610.TW"], period="6mo",
                       interval="1d", progress=False, auto_adjust=False)["Close"]
    b = data["BZ=F"].dropna()
    price = float(b.iloc[-1])
    chg1d = float((b.iloc[-1] / b.iloc[-2] - 1) * 100)
    chg5d = float((b.iloc[-1] / b.iloc[-6] - 1) * 100)
    r = data.pct_change()
    corr = {}
    for tk, label in (("2603.TW", "2603"), ("2610.TW", "2610")):
        j = r[[tk, "BZ=F"]].dropna().iloc[-CORR_WIN:]
        if len(j) >= 30:
            corr[label] = float(j.corr().iloc[0, 1])
    return price, chg1d, chg5d, corr


def push_inbox(msg: str, cross: str | None) -> bool:
    try:
        import redis
        r = redis.Redis()
        r.xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "brent_watch",
            "topic": "brent-watch",
            "tags": "brent,oil,geopolitics" + (",cross" if cross else ""),
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "msg": msg,
        })
        return True
    except Exception as e:  # inbox 失敗不影響 exit code (fail-safe)
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    price, chg1d, chg5d, corr = fetch_prices()
    prev = None
    if STATE_PATH.exists():
        try:
            prev = json.loads(STATE_PATH.read_text()).get("price")
        except Exception:
            prev = None
    cross = detect_cross(prev, price)
    zone = classify_zone(price)
    msg = build_msg(price, chg1d, chg5d, zone, cross, corr)
    print(msg)
    push_inbox(msg, cross)
    STATE_PATH.write_text(json.dumps(
        {"price": price, "zone": zone, "as_of": datetime.now().isoformat()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
