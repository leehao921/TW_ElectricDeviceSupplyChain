#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market_regime.py — 量能 regime gate (alpha #4, 2026-08-05 plan).

規則 (源自 2026-08-05 陳鳳馨文章分析,7/29 低點 = 去槓桿線):
  TAIEX 收盤 < line (39,385)      → broken     (去槓桿假設作廢)
  5D 均成交值 < 1.0 兆            → low_volume (量縮整理,突破訊號降權)
  否則                            → normal

模組用法 (bb_inbox_alert / buy_list_daily_alert 接線,無獨立排程):
    from market_regime import get_regime, banner
    b = banner(get_regime())      # None 或 regime 警示行,失敗安全回 None

資料源: TWSE FMTQIK (當月+上月,成交金額與 TAIEX 收盤一站取得)。
Cache: data/market_regime.json (as_of 當日直接用)。line 存 cache 可手動調。
Plan: docs/plans/2026-08-05-foreign-structure-regime.md
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

TZ_TPE = dt.timezone(dt.timedelta(hours=8))
REPO = Path(__file__).resolve().parents[1]
CACHE_PATH = REPO / "data" / "market_regime.json"
FMTQIK_URL = "https://www.twse.com.tw/exchangeReport/FMTQIK"
DEFAULT_LINE = 39385          # 2026-07-29 TWII 低點 (去槓桿完成線)
MIN_TURNOVER = 1.0e12         # 1 兆
WINDOW = 5


def today_str() -> str:
    return dt.datetime.now(TZ_TPE).date().isoformat()


# ------------------------------------------------------------------ #
# Pure
# ------------------------------------------------------------------ #
def parse_fmtqik(raw: dict) -> list:
    """FMTQIK json → [{date, value(元), taiex}] (ROC 日期、千分位)。"""
    out = []
    for row in raw.get("data") or []:
        try:
            y, m, d = row[0].split("/")
            date = "%04d-%02d-%02d" % (int(y) + 1911, int(m), int(d))
            out.append({"date": date,
                        "value": float(row[2].replace(",", "")),
                        "taiex": float(row[4].replace(",", ""))})
        except (ValueError, IndexError):
            continue
    return out


def classify_regime(rows: list, line: float = DEFAULT_LINE,
                    min_turnover: float = MIN_TURNOVER, window: int = WINDOW) -> dict:
    rows = sorted(rows, key=lambda r: r["date"])
    last = rows[-window:]
    turnover = sum(r["value"] for r in last) / len(last)
    taiex = rows[-1]["taiex"]
    if taiex < line:
        regime = "broken"
    elif turnover < min_turnover:
        regime = "low_volume"
    else:
        regime = "normal"
    return {"regime": regime, "turnover_5d": turnover, "taiex": taiex,
            "line": line, "as_of_data": rows[-1]["date"]}


def banner(regime: dict):
    """regime → 警示行 (normal/None → None)。"""
    if not regime or regime.get("regime") in (None, "normal"):
        return None
    t = (regime.get("turnover_5d") or 0) / 1e12
    if regime["regime"] == "broken":
        return ("🚨 Regime: TAIEX %s 已破去槓桿線 %s — regime 假設作廢,全面降風險"
                % ("{:,.0f}".format(regime.get("taiex", 0)),
                   "{:,}".format(int(regime.get("line", 0)))))
    return ("⚠️ Regime: 量縮整理 — 5D 均量 %.2f 兆 <1.0 兆,突破訊號降權"
            " (TAIEX %s / line %s 未破)"
            % (t, "{:,.0f}".format(regime.get("taiex", 0)),
               "{:,}".format(int(regime.get("line", 0)))))


# ------------------------------------------------------------------ #
# I/O
# ------------------------------------------------------------------ #
def fetch_months() -> list:
    """當月 + 上月 FMTQIK。"""
    import requests
    today = dt.datetime.now(TZ_TPE).date()
    first = today.replace(day=1)
    prev = (first - dt.timedelta(days=1)).replace(day=1)
    rows = []
    for d in (prev, first):
        r = requests.get(FMTQIK_URL, params={"response": "json",
                                             "date": d.strftime("%Y%m%d")}, timeout=15)
        r.raise_for_status()
        rows.extend(parse_fmtqik(r.json()))
    return rows


def get_regime(cache_path: Path = CACHE_PATH):
    """當日 cache 直接用;否則 fetch+classify+寫 cache。失敗回 None (fail-safe)。"""
    line = DEFAULT_LINE
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        line = cached.get("line", DEFAULT_LINE)
        if cached.get("as_of") == today_str():
            return cached
    except (OSError, ValueError):
        pass
    try:
        rows = fetch_months()
        if not rows:
            return None
        out = classify_regime(rows, line=line)
        out["as_of"] = today_str()
        cache_path.parent.mkdir(exist_ok=True)
        cache_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out
    except Exception as e:                           # noqa: BLE001 — gate 失敗不可擋 alert
        print("[warn] market_regime fetch failed: %s" % e, file=sys.stderr)
        return None


def main():
    r = get_regime()
    if r is None:
        print("regime unavailable")
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=1))
    b = banner(r)
    if b:
        print(b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
