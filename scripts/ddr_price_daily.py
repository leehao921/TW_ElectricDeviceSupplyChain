#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ddr_price_daily.py — DRAMeXchange 現貨價日更 → memory_cycle 自動輸入.

背景 (2026-08-11): data/memory_cycle_inputs.yaml 的 DDR4 series 一直是
6/25 模板佔位值 ($2.85-3.45),而 DRAMeXchange 實價已 $42.5 — 手動月更
機制實質失效。本 collector 每日抓 dramexchange.com 首頁現貨表:

  1. append data/ddr_price_history.json (日級, idempotent)
  2. 以「月均 (當月=MTD 均)」重寫 yaml 的 ddr4_8gb_spot_usd series
     (手動欄位 ddr5 合約/MU guidance 原樣保留 — 合約價無免費源仍手動季更)
  3. inbox topic=ddr-price 一行日報 (→ Discord)

launchd: com.lulala.ddr-price Mon-Fri 08:20 (memory-cycle 08:40 之前)。
Plan: docs/plans/2026-08-05-foreign-structure-regime.md 後續 (用戶 8/11 指示)。
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

TZ_TPE = dt.timezone(dt.timedelta(hours=8))
REPO = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO / "data" / "ddr_price_history.json"
YAML_PATH = REPO / "data" / "memory_cycle_inputs.yaml"
DX_URL = "https://www.dramexchange.com/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

TARGET_ITEMS = ("DDR4 8Gb (1Gx8) 3200", "DDR5 16Gb (2Gx8) 4800/5600")
DDR4_ITEM = TARGET_ITEMS[0]

_TD_RE = r'<td[^>]*>\s*([\-0-9.%]+)\s*</td>'


# ------------------------------------------------------------------ #
# Pure
# ------------------------------------------------------------------ #
def parse_spot(html: str) -> dict:
    """首頁現貨表: 品項名後 5 個數字 td = high/low/high/low/均價,第 6 = 漲跌%。"""
    out = {}
    for item in TARGET_ITEMS:
        i = html.find(item)
        if i < 0:
            continue
        tds = re.findall(_TD_RE, html[i:i + 2000])[:6]
        if len(tds) < 6:
            continue
        try:
            out[item] = {"avg": float(tds[4]),
                         "chg_pct": float(tds[5].rstrip("%"))}
        except ValueError:
            continue
    return out


def monthly_series(history: dict, item: str) -> list:
    """日級 history → [(YYYY-MM, 月均)] 升冪;當月 = MTD 均。"""
    buckets = {}
    for date, items in history.items():
        rec = items.get(item)
        if rec and rec.get("avg"):
            buckets.setdefault(date[:7], []).append(float(rec["avg"]))
    return [(m, round(sum(v) / len(v), 3)) for m, v in sorted(buckets.items())]


def update_yaml_ddr4(yaml_text: str, series: list, today: str) -> str:
    """整段重寫 ddr4_8gb_spot_usd (自動維護);其餘欄位原樣保留。"""
    block = "ddr4_8gb_spot_usd:\n" + "".join(
        '  - {month: "%s", price: %s}\n' % (m, p) for m, p in series)
    out = re.sub(r"ddr4_8gb_spot_usd:\n(?:\s+- \{[^}]*\}\n)*", block, yaml_text)
    out = re.sub(r"last_updated: .*", "last_updated: %s" % today, out, count=1)
    out = re.sub(r"notes: .*",
                 'notes: "ddr4 series 由 scripts/ddr_price_daily.py 自動維護 '
                 '(DRAMeXchange 現貨月均, 當月=MTD); ddr5 合約/MU 仍手動。"',
                 out, count=1)
    return out


# ------------------------------------------------------------------ #
# I/O
# ------------------------------------------------------------------ #
def fetch_html() -> str:
    import requests
    r = requests.get(DX_URL, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


def push_inbox(msg: str, date: str) -> bool:
    import subprocess
    fields = ["ts", dt.datetime.now(TZ_TPE).isoformat(), "from", "ddr_price_daily",
              "topic", "ddr-price", "tags", "ddr,memory,daily", "as_of", date,
              "msg", msg]
    r = subprocess.run(["redis-cli", "XADD", "claude:inbox", "*", *fields],
                       capture_output=True, text=True, timeout=10)
    return r.returncode == 0


def main() -> int:
    today = dt.datetime.now(TZ_TPE).date().isoformat()
    spot = parse_spot(fetch_html())
    if not spot:
        print("[error] no spot rows parsed — DRAMeXchange 版型變更?", file=sys.stderr)
        return 1

    history = {}
    if HISTORY_PATH.exists():
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    history[today] = spot
    HISTORY_PATH.parent.mkdir(exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=1),
                            encoding="utf-8")

    series = monthly_series(history, DDR4_ITEM)
    if YAML_PATH.exists() and series:
        YAML_PATH.write_text(
            update_yaml_ddr4(YAML_PATH.read_text(encoding="utf-8"), series, today),
            encoding="utf-8")

    d4 = spot.get(DDR4_ITEM, {})
    d5 = spot.get(TARGET_ITEMS[1], {})
    msg = ("DDR 現貨 %s: DDR4 8Gb $%.2f (%+.2f%%) | DDR5 16Gb $%.2f (%+.2f%%)"
           % (today, d4.get("avg", 0), d4.get("chg_pct", 0),
              d5.get("avg", 0), d5.get("chg_pct", 0)))
    push_inbox(msg, today)
    print("[%s] %s" % (today, msg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
