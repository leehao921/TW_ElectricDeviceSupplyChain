#!/usr/bin/env python3
"""事件窗口反應分類效度 (plan: docs/plans/2026-10-15-event-window-iv.md)

data/event_window_log.csv → 依 +5/+15 分類分組,看 +60 分 outcome:
  延續 → 命中 = continued;消化 → 命中 = reversed;基準 = 全部有效事件的 continued 比例。
護欄: n<20 不下結論;無分布性形容詞;10/05 前 IV 輸入品質另計。分析標註,不構成交易指令。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

MIN_N = 20
HIT = {"延續": "continued", "消化": "reversed"}


def _group(cls: str) -> str:
    return "延續" if cls.startswith("延續") else cls


def study(rows: list, stage: str = "15", min_n: int = MIN_N) -> dict:
    valid = [r for r in rows if r.get("outcome_60") and r.get("class_" + stage) not in ("", "資料不足", None)]
    groups = {}
    for r in valid:
        g = groups.setdefault(_group(r["class_" + stage]), {"n": 0, "hits": 0, "pre_fix": 0})
        g["n"] += 1
        g["pre_fix"] += r.get("data_quality") == "pre_fix"
        g["hits"] += HIT.get(_group(r["class_" + stage])) == r["outcome_60"]
    for name, g in groups.items():
        g["hit"] = g["hits"] / g["n"] if name in HIT else None
    n = len(valid)
    return {"stage": stage, "n": n, "groups": groups,
            "base_continued": sum(r["outcome_60"] == "continued" for r in valid) / n if n else None,
            "verdict": "樣本不足,不下結論" if n < min_n else "見分組命中率 vs 基準"}


def render(results: list, rows: list) -> str:
    L = ["# 事件窗口反應分類效度 (%s)" % date.today().isoformat(), "",
         "分析標註,不構成交易指令。事件 %d 筆 (log)。" % len(rows), ""]
    for res in results:
        L += ["## +%s 分分類 → +60 分 outcome (n=%d, 判讀: %s)" % (res["stage"], res["n"], res["verdict"]),
              "基準 (全部有效事件 continued 比例): %s" % (
                  "n/a" if res["base_continued"] is None else "%.0f%%" % (res["base_continued"] * 100)), "",
              "| 分類 | n | 命中 | 命中率 | 其中 10/05 前資料 |", "|---|---|---|---|---|"]
        for name, g in sorted(res["groups"].items()):
            L.append("| %s | %d | %s | %s | %d |" % (
                name, g["n"], g["hits"] if g["hit"] is not None else "—",
                "—" if g["hit"] is None else "%.0f%%" % (g["hit"] * 100), g["pre_fix"]))
        L.append("")
    L += ["## Verification log",
          "- 來源: data/event_window_log.csv (event_window.py backfill + live)",
          "- 命中定義: 延續 → outcome_60=continued;消化 → outcome_60=reversed;混合不計命中",
          "- outcome: +5 分方向在 +60 分續行 ≥ 0.1×定價幅度 (無定價用 0.5% 價格)",
          "- n<%d 一律「樣本不足,不下結論」;未使用分布性形容詞 (Golden Rule 0 未觸發)" % MIN_N]
    return "\n".join(L) + "\n"


def main() -> int:
    from event_window import load_log
    rows = load_log()
    out = REPO / "analysis" / ("event_window_study_%s.md" % date.today().isoformat())
    text = render([study(rows, "5"), study(rows, "15")], rows)
    out.write_text(text, encoding="utf-8")
    print(out)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
