#!/usr/bin/env python3
"""LPPLS 台股泡沫偵測 Phase 1 驗證研究 orchestrator。

用法:
  .venv/bin/python scripts/lppls_study.py                 # 主跑 window=100 r2=0.7 + HPO
  .venv/bin/python scripts/lppls_study.py --no-hpo        # 只跑主參數
  .venv/bin/python scripts/lppls_study.py --window 80 --r2 0.75

產出: analysis/lppls_study_<today>.md（含通過準則判定 + Verification log）
Read-only vs trading-timescaledb。警戒燈定位，無 trade directives。
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lppls import confirmation  # noqa: E402
from scripts.lppls.db import load_daily_closes, load_taiex
from scripts.lppls.index_builder import (
    CANDIDATES, CORE, build_index, select_components, validate_vs_taiex,
)
from scripts.lppls.walkforward import (
    detect_drawdowns, evaluate, walk_forward, with_signal,
)

HPO_WINDOWS = range(70, 141, 10)
HPO_R2 = [0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
CONFIRM_SINCE = dt.date(2026, 7, 1)   # confirmation 資料齊備後才回填


def fmt(x, pct=False, nd=3):
    if x is None:
        return "N/A"
    return f"{x:.1%}" if pct else f"{x:.{nd}f}"


def run(window: int, r2_min: float, step: int, do_hpo: bool, out_path: Path):
    lines = []
    today = dt.date.today()

    # 1. 指數建構
    closes = load_daily_closes(set(CORE) | set(CANDIDATES))
    comps, weights = select_components(closes)
    index_s = build_index(closes, weights)
    taiex = load_taiex()
    corr, n_overlap = validate_vs_taiex(index_s, taiex)
    proxy_ok = corr > 0.95

    lines += [
        f"# LPPLS 台股泡沫偵測 — Phase 1 驗證研究 ({today})", "",
        "**定位:** 泡沫警戒燈（不做空、無 trade directives）。"
        "Spec: docs/superpowers/specs/2026-08-27-lppls-tw-bubble-detection-design.md", "",
        "## 1. 自建電子權值指數", "",
        f"- 成分 {len(comps)} 檔: {', '.join(comps)}",
        "- 權重前五: " + ", ".join(
            f"{s} {w:.1%}" for s, w in
            sorted(weights.items(), key=lambda kv: -kv[1])[:5]),
        f"- 期間: {index_s.index[0]} → {index_s.index[-1]}（{len(index_s)} 交易日）",
        f"- vs TAIEX 日報酬相關: **{corr:.4f}**（重疊 {n_overlap} 日，門檻 0.95 → "
        f"{'合格' if proxy_ok else '不合格'}）", "",
    ]
    if not proxy_ok:
        lines.append("> ⚠️ proxy 不合格 — 以下結果僅供參考，應擴大成分股重跑。")
        lines.append("")

    # 2. 事件集
    events = detect_drawdowns(index_s, threshold=0.05)
    lines += ["## 2. 回檔事件集（滾動高點回落 ≥5%）", ""]
    if events:
        lines.append("| 前高日 | 觸發日 | 觸發時深度 | 最大深度 |")
        lines.append("|---|---|---|---|")
        lines += [f"| {e['peak_date']} | {e['trigger_date']} | "
                  f"{e['depth_at_trigger']:.1%} | {e['depth']:.1%} |"
                  for e in events]
    else:
        lines.append("期間內無 ≥5% 回檔事件 — 準則 1 無法評估。")
    lines.append("")

    # 3. 主參數 walk-forward
    wf_raw = walk_forward(index_s, window=window, step=step)
    wf = with_signal(wf_raw, r2_min=r2_min)
    res = evaluate(index_s, wf, events)
    sig_rows = wf[wf["signal"]]
    lines += [f"## 3. Walk-forward（window={window}, step={step}, R²≥{r2_min}）", "",
              f"- 擬合次數 {len(wf)}，qualifies {int(wf['qualifies'].sum())}，"
              f"訊號 {res['n_signals']}（可評估 {res['n_signals_evaluable']}）", ""]
    if not sig_rows.empty:
        lines.append("| 訊號日 | R² | tc(日) | m | ω |")
        lines.append("|---|---|---|---|---|")
        lines += [f"| {d} | {r.r2:.3f} | {r.tc_days:.0f} | {r.m:.2f} | {r.omega:.1f} |"
                  for d, r in sig_rows.iterrows()]
        lines.append("")

    # 4. 通過準則判定
    c1 = (res["capture_rate_capturable"] is not None
          and res["capture_rate_capturable"] >= 0.5)
    c2 = res["fp_rate"] is not None and res["fp_rate"] < 0.5
    c3 = (res["mw_pvalue"] is not None and res["mw_pvalue"] < 0.1
          and res["sig_fwd_median"] is not None
          and res["nosig_fwd_median"] is not None
          and res["sig_fwd_median"] < res["nosig_fwd_median"])
    verdict = "通過 → 進 Phase 2" if (c1 and c2 and c3) else "未通過 → 誠實負結果收檔"
    lines += [
        "## 4. 事前通過準則判定", "",
        "| 準則 | 實測 | 門檻 | 判定 |", "|---|---|---|---|",
        f"| 1. 回檔捕捉率（capturable） | {fmt(res['capture_rate_capturable'], pct=True)}"
        f"（{res['captured_capturable']}/{res['n_events_capturable']}；"
        f"全事件 {fmt(res['capture_rate'], pct=True)} = {res['captured']}/{res['n_events']}） "
        f"| ≥50% | {'✅' if c1 else '❌'} |",
        f"| 2. False positive 率 | {fmt(res['fp_rate'], pct=True)} | <50% "
        f"| {'✅' if c2 else '❌'} |",
        f"| 3. 訊號日 fwd20 劣化 | 中位數 {fmt(res['sig_fwd_median'], pct=True)} vs "
        f"{fmt(res['nosig_fwd_median'], pct=True)}, MW p={fmt(res['mw_pvalue'])} "
        f"| p<0.1 且中位數較低 | {'✅' if c3 else '❌'} |",
        "", f"**判定: {verdict}**", "",
        f"- 穩健性: 非重疊子樣本 MW p={fmt(res['mw_pvalue_nonoverlap'])}"
        f"（訊號 n={res['n_signals_nonoverlap']}）— 主 p 值因 forward 視窗重疊"
        "（step=5 vs horizon=20）偏 anti-conservative，兩者並列判讀。",
        "- 捕捉語意: 訊號落在前高日與觸發日之間也計入捕捉（trigger-date 定義）。",
    ]
    if res["n_signals_evaluable"] < 10:
        lines.append(f"- ⚠️ 低樣本警告: 可評估訊號僅 {res['n_signals_evaluable']} 個，"
                     "MW 檢定力弱，判定信心有限。")
    lines += [
        "", "> 誠實警告: 399 交易日樣本、事件數 "
        f"{res['n_events']} 次，統計力天生有限；本判定不可過度外推。", "",
    ]

    # 5. HPO
    if do_hpo:
        lines += ["## 5. HPO 敏感度（各格 = capturable捕捉率;FP率;訊號數）", "",
                  "| window \\ R² | " + " | ".join(f"{r}" for r in HPO_R2) + " |",
                  "|" + "---|" * (len(HPO_R2) + 1)]
        for wnd in HPO_WINDOWS:
            raw = wf_raw if wnd == window else walk_forward(index_s, window=wnd,
                                                            step=step)
            cells = []
            for r2t in HPO_R2:
                r = evaluate(index_s, with_signal(raw, r2_min=r2t), events)
                cells.append(f"{fmt(r['capture_rate_capturable'], pct=True)};"
                             f"{fmt(r['fp_rate'], pct=True)};{r['n_signals']}")
            lines.append(f"| {wnd} | " + " | ".join(cells) + " |")
        lines.append("")

    # 6. Confirmation 回填（近期訊號 dry-run，不進準則）
    # Note: sig_rows.index entries are datetime.date objects (from load_daily_closes
    # pivot using psycopg2 ts::date → python datetime.date). CONFIRM_SINCE is also
    # datetime.date, so the comparison d >= CONFIRM_SINCE is date-to-date: correct.
    recent = [d for d in sig_rows.index if d >= CONFIRM_SINCE]
    lines += ["## 6. Confirmation 分層回填（dry-run，不進通過準則）", ""]
    if recent:
        for d in recent:
            pos = index_s.index.get_loc(d)
            ret5 = float(index_s.iloc[pos] / index_s.iloc[max(0, pos - 5)] - 1.0)
            agg = confirmation.confirm(d, comps, ret5)
            lines.append(f"- {d}: **{agg['label']}**（{agg['total']}/"
                         f"{agg['n_available']}）— "
                         + ", ".join(f"{k}={'∅' if v is None else v['score']}"
                                     for k, v in agg["layers"].items()))
    else:
        lines.append(f"{CONFIRM_SINCE} 後無訊號日，無可回填樣本。")
    lines += ["", "## Verification log", "",
              "- 本報告數字皆由本 script 對 DB 實算產出；分布性措辭（若有）依 "
              "Golden Rule 0 另跑 scripts/verify_flow_zscore.py 佐證。",
              f"- 產出指令: `.venv/bin/python scripts/lppls_study.py --window {window} "
              f"--r2 {r2_min}`", ""]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入 {out_path}")
    print(f"判定: {verdict}")


def main():
    ap = argparse.ArgumentParser(
        description="LPPLS 台股泡沫偵測 Phase 1 驗證研究")
    ap.add_argument("--window", type=int, default=100)
    ap.add_argument("--r2", type=float, default=0.7)
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--no-hpo", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = Path(args.out) if args.out else Path(
        f"analysis/lppls_study_{dt.date.today()}.md")
    run(args.window, args.r2, args.step, not args.no_hpo, out)


if __name__ == "__main__":
    main()
