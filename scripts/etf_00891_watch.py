#!/usr/bin/env python3
"""00891 存股疊加層日巡檢 — 回檔買低帶 / 乖離 trim 帶 / 股利規則
(策略: analysis/etf_00891_strategy_20260824.md; 部位: 核心 14,220 股永不動)

帶定義 (ATH 動態):
- add1: 距 ATH -20% (股利池進場) / add2: -30% (加倍) / add3: -35% (黑天鵝質押層)
- trim: 乖離 MA200 >= +45% (歷史 P95 噴出帶) — 只賣疊加不賣核心
- 股利規則: 價 < MA200 再投入, 價 > MA200 留現金
推 inbox topic=etf-00891, 換帶事件 🚨。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "data" / "etf_00891_state.json"
ADD1, ADD2, ADD3 = -20.0, -30.0, -35.0
TRIM_DEV = 45.0

BAND_LABEL = {
    "hold": "持有區 — 核心不動",
    "add1": "🎯 -20% 買低帶 (add1): 股利池全額進場",
    "add2": "🎯 -30% 買低帶 (add2): 股利池+現金加倍",
    "add3": "🎯 -35% 黑天鵝帶 (add3): 質押權值股加碼層",
    "trim": "⚠️ 乖離 P95 噴出帶: trim 疊加部位 (核心 14,220 股不動, 需 P/B 廣度匯合確認)",
}


def classify_band(drawdown: float, dev: float) -> str:
    """drawdown = 距 ATH %, dev = 乖離 MA200 %. add 優先於 trim (深回檔時 dev 必低)."""
    if drawdown <= ADD3:
        return "add3"
    if drawdown <= ADD2:
        return "add2"
    if drawdown <= ADD1:
        return "add1"
    if dev >= TRIM_DEV:
        return "trim"
    return "hold"


def dividend_rule(price: float, ma200: float) -> str:
    return "reinvest" if price < ma200 else "hold_cash"


def detect_cross(prev_band: str | None, cur_band: str) -> str | None:
    if prev_band is None or prev_band == cur_band:
        return None
    if cur_band != "hold":
        return f"enter_{cur_band}"
    return f"exit_{prev_band}"


DIV_LABEL = {"reinvest": "配息→立即再投入 (價<MA200 折價區)",
             "hold_cash": "配息→留現金進回檔彈藥池 (價>MA200)"}


def build_msg(price: float, ath: float, drawdown: float, dev: float,
              band: str, cross: str | None, div_rule: str, ma200: float) -> str:
    alarm = "🚨 " if cross else ""
    lines = [f"{alarm}00891 {price:.2f} · 距 ATH {ath:.2f} {drawdown:+.1f}% · 乖離 MA200({ma200:.1f}) {dev:+.1f}%"]
    if cross:
        lines.append(f"換帶: {cross}")
    lines.append(BAND_LABEL[band])
    lines.append(f"股利規則: {DIV_LABEL[div_rule]}")
    nxt = []
    if band == "hold":
        nxt.append(f"add1 觸發價 {ath*(1+ADD1/100):.1f}")
        nxt.append(f"trim 觸發價 ~{ma200*(1+TRIM_DEV/100):.1f}")
    lines.append("下個行動點: " + " / ".join(nxt)) if nxt else None
    return "\n".join(lines)


def fetch() -> tuple[float, float, float, float]:
    import yfinance as yf
    c = yf.download("00891.TW", period="max", interval="1d",
                    progress=False, auto_adjust=False)["Close"].iloc[:, 0].dropna()
    price = float(c.iloc[-1])
    ath = float(c.max())
    ma200 = float(c.rolling(200).mean().iloc[-1])
    dev = (price / ma200 - 1) * 100
    return price, ath, ma200, dev


def push_inbox(msg: str, cross: str | None) -> None:
    try:
        import redis
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "etf_00891_watch", "topic": "etf-00891",
            "tags": "00891,etf,bands" + (",cross" if cross else ""),
            "as_of": datetime.now().strftime("%Y-%m-%d"), "msg": msg})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)


def main() -> int:
    price, ath, ma200, dev = fetch()
    drawdown = (price / ath - 1) * 100
    prev = None
    if STATE_PATH.exists():
        try:
            prev = json.loads(STATE_PATH.read_text()).get("band")
        except Exception:
            prev = None
    band = classify_band(drawdown, dev)
    cross = detect_cross(prev, band)
    msg = build_msg(price, ath, drawdown, dev, band, cross,
                    dividend_rule(price, ma200), ma200)
    print(msg)
    push_inbox(msg, cross)
    STATE_PATH.write_text(json.dumps(
        {"band": band, "price": price, "ath": ath, "as_of": datetime.now().isoformat()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
