#!/usr/bin/env python3
"""地緣風險歸因研究 orchestrator。

用法: .venv/bin/python scripts/geo_attr_study.py
產出: analysis/geo_attribution_study_<today>.md
指標×事件矩陣 + 誤報率 + 事前準則角色判定;catalyst 標註(Phase B)由分析者於
commit 前補入 <!-- PHASE_B_CATALYST --> 標記處(最終報告不得殘留該標記)。
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from scripts.geo_attr import indicators as ind  # noqa: E402
from scripts.geo_attr import loaders  # noqa: E402
from scripts.geo_attr.leadlag import classify_event, false_alarm_rate  # noqa: E402
from scripts.lppls.db import load_daily_closes  # noqa: E402
from scripts.lppls.index_builder import (  # noqa: E402
    CANDIDATES, CORE, build_index, select_components,
)
from scripts.lppls.walkforward import detect_drawdowns  # noqa: E402

GDELT_KEYS = ["tariff", "taiwan_strait", "tsmc", "semi_export", "mideast_oil"]
QUALIFY_LEAD_SHARE = 0.5   # 事前準則: >=50% 覆蓋事件領先
QUALIFY_FAR_MAX = 0.6      # 事前準則: 誤報率 <60%


def build_indicator_zoo(comps, index_s):
    """回傳 {指標名: z-series(以 index 交易日 reindex, ffill<=3)}。"""
    zoo = {}
    for key in GDELT_KEYS:
        g = loaders.load_gdelt(key)
        if g.empty:
            zoo[f"gdelt_{key}_vol"] = pd.Series(dtype=float)
            zoo[f"gdelt_{key}_tone"] = pd.Series(dtype=float)
            continue
        zoo[f"gdelt_{key}_vol"] = ind.gdelt_intensity(g["article_count"].astype(float))
        zoo[f"gdelt_{key}_tone"] = ind.gdelt_tone_deterioration(g["avg_tone"].astype(float))
    zoo["brent_shock"] = ind.brent_shock(loaders.load_brent())
    zoo["twd_depreciation"] = ind.twd_depreciation(loaders.load_fx("USDTWD"))
    zoo["dxy_strength"] = ind.dxy_strength(loaders.load_fx("DXY"))
    zoo["foreign_sell"] = ind.foreign_sell_accel(loaders.load_foreign_net_value(comps))
    zoo["ust10y_surge"] = ind.yield_surge(loaders.load_yf("^TNX", "ust10y_daily"))
    zoo["ust30y_surge"] = ind.yield_surge(loaders.load_yf("^TYX", "ust30y_daily"))
    zoo["sox_shock"] = ind.sox_shock(loaders.load_yf("^SOX", "sox_daily"))
    zoo["usvix_spike"] = ind.usvix_spike(loaders.load_yf("^VIX", "usvix_daily"))
    # 對齊指數交易日(來源日曆不同: GDELT 每日/Brent 海外盤/外資台股盤)
    aligned = {name: z.reindex(index_s.index).ffill(limit=3)
               for name, z in zoo.items()}
    # 海外盤收盤在台北時間隔日凌晨才可觀測 → shift(1) 避免領先天數虛增一日
    for name in ("brent_shock", "dxy_strength", "ust10y_surge", "ust30y_surge",
                 "sox_shock", "usvix_spike"):
        aligned[name] = aligned[name].shift(1)
    return aligned


def run(out_path: Path):
    today = dt.date.today()
    closes = load_daily_closes(set(CORE) | set(CANDIDATES))
    comps, weights = select_components(closes)
    index_s = build_index(closes, weights)
    events = detect_drawdowns(index_s, threshold=0.05)
    zoo = build_indicator_zoo(comps, index_s)

    lines = [
        f"# 地緣風險歸因研究 ({today})", "",
        "**前情:** LPPLS Phase 1 負結果 — 回檔為事件驅動。本研究檢驗外生指標的領先性。",
        "Spec: docs/superpowers/specs/2026-08-27-geo-attribution-study-design.md", "",
        f"指數: 同 LPPLS 研究 {len(comps)} 檔電子權值 ({index_s.index[0]} → {index_s.index[-1]},"
        f" {len(index_s)} 交易日);事件 {len(events)} 次(≥5% 回檔)。", "",
        "## 1. 事件 catalyst 標註（Phase B）", "",
        "<!-- PHASE_B_CATALYST -->", "",
        "## 2. 指標 × 事件矩陣（觀察窗 [−30,+5]，z>2 首現位置）", "",
        "| 指標 | " + " | ".join(str(e["trigger_date"]) for e in events) + " | 誤報率 (警報數) | 角色判定 |",
        "|" + "---|" * (len(events) + 3),
    ]
    verdicts = {}
    for name, z in zoo.items():
        cells, cats, lead_count, covered = [], [], 0, 0
        for ev in events:
            r = classify_event(z, index_s.index, ev["trigger_date"])
            cats.append(r["category"])
            if r["category"] == "資料不足":
                cells.append("∅")
                continue
            covered += 1
            if r["category"] == "領先":
                lead_count += 1
                cells.append(f"領先{r['first_cross']}")
            elif r["category"] == "同步":
                cells.append(f"同步{r['first_cross']:+d}")
            elif r["category"] == "落後":
                cells.append(f"落後+{r['first_cross']}")
            else:
                cells.append("—")
        far, n_alerts = false_alarm_rate(z, index_s, events)
        lead_share = (lead_count / covered) if covered else None
        # 零警報視為空缺真滿足 <60%(完美指標不因從不誤報而降級);見 Verification log
        far_ok = (far < QUALIFY_FAR_MAX) if far is not None else (n_alerts == 0)
        if covered == 0:
            role = "資料不足"
        elif lead_share >= QUALIFY_LEAD_SHARE and far_ok:
            role = "警戒"
        elif any(c in ("領先", "同步") for c in cats):
            role = "確認"
        else:
            role = "剔除"
        verdicts[name] = dict(lead_share=lead_share, far=far, role=role,
                              covered=covered)
        far_s = "N/A" if far is None else f"{far:.0%}"
        lines.append(f"| {name} | " + " | ".join(cells)
                     + f" | {far_s} ({n_alerts}) | **{role}** |")

    n_warn = sum(1 for v in verdicts.values() if v["role"] == "警戒")
    lines += [
        "", "## 3. 事前準則判定", "",
        "- 警戒資格: ≥50% 覆蓋事件領先 ≥3 交易日 且 誤報率 <60%。",
        f"- 獲警戒角色指標數: **{n_warn}** / {len(verdicts)}。",
        "- 領先 ≠ 因果;本研究只回答「值不值得監測」,不回答「為什麼」。", "",
        "## 4. Composite 設計建議", "",
        "<!-- PHASE_B_COMPOSITE -->", "",
        "## Verification log", "",
        "- 數字由本 script 對 DB + yfinance cache 實算;z-score 為 causal(不含當前點)。",
        "- 事前約定: 零警報(n_alerts=0)視為空缺真滿足誤報率 <60%(從不誤報不得降級)。",
        "- brent_shock/dxy_strength/ust10y_surge/ust30y_surge/sox_shock/usvix_spike 已 shift(1)"
        " — 海外盤收盤台北隔日凌晨才可觀測,避免領先天數虛增一日。",
        "- 產出指令: `.venv/bin/python scripts/geo_attr_study.py`",
        "- 覆蓋聲明: vix_daily 僅蓋 2/7 事件(案例研究,未進矩陣);margin/Kalshi 0/7 未檢驗。", "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入 {out_path}")
    for name, v in sorted(verdicts.items(), key=lambda kv: kv[1]["role"]):
        print(f"  {name}: role={v['role']} lead_share={v['lead_share']} far={v['far']}")


def main():
    ap = argparse.ArgumentParser(description="地緣風險歸因研究")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    out = Path(a.out) if a.out else (
        repo_root / f"analysis/geo_attribution_study_{dt.date.today()}.md")
    run(out)


if __name__ == "__main__":
    main()
