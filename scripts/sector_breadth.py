#!/usr/bin/env python3
"""sector_breadth.py — 產業動能廣度儀表 (plan 2026-10-16).

動能廣度 = 產業內有收盤價的檔數中, 通過 strong_pullback 強勢篩選的比例
(21/63/126 日報酬任一 ≥30% 且全池前 25%, 20D 成交值 ≥0.5 億)。
2025-07→2026-10 檢定: 產業層 20 日 IC +0.27 (t 1.6)、60 日 +0.42, 三個半年同號 → 儀表級。

CLI:
    python scripts/sector_breadth.py               # 今日一筆 → history + 印出
    python scripts/sector_breadth.py --backfill    # 重建整段歷史
    python scripts/sector_breadth.py --validate    # 重跑 IC 檢定 (升級條件見 plan)

純儀表, 非交易指令。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

HISTORY = REPO / "data" / "sector_breadth_history.csv"
LOOKBACK = 20
SECTOR_ZH = {
    "Semiconductors": "半導體",
    "Semiconductor Equipment & Materials": "半導體設備材料",
    "Electronic Components": "電子零組件",
    "Computer Hardware": "電腦硬體",
    "Communication Equipment": "通訊設備",
    "Consumer Electronics": "消費電子",
    "Electronics & Computer Distribution": "電子通路",
    "Electrical Equipment & Parts": "電機設備",
    "Specialty Industrial Machinery": "工業機械",
    "Software - Infrastructure": "軟體",
    "Scientific & Technical Instruments": "科學儀器",
}


# --------------------------------------------------------------------------- #
# pure
# --------------------------------------------------------------------------- #
def _groups(sector_map: dict[str, str], columns) -> dict[str, list[str]]:
    cols = set(columns)
    g: dict[str, list[str]] = {}
    for tk, sec in sector_map.items():
        if tk in cols:
            g.setdefault(sec, []).append(tk)
    return g


def breadth_panel(mom: pd.DataFrame, close: pd.DataFrame,
                  sector_map: dict[str, str]) -> pd.DataFrame:
    """逐日 × 產業 動能廣度 (%); 分母 = 當日有收盤價的成員."""
    out = {}
    for sec, members in _groups(sector_map, close.columns).items():
        n = close[members].notna().sum(axis=1).replace(0, np.nan)
        out[sec] = mom[members].fillna(False).sum(axis=1) / n * 100
    return pd.DataFrame(out)


def sector_breadth(mom: pd.DataFrame, close: pd.DataFrame, sector_map: dict[str, str],
                   lookback: int = LOOKBACK) -> pd.DataFrame:
    """最後一日各產業廣度 + lookback 日前廣度與變化, 依廣度降冪."""
    panel = breadth_panel(mom, close, sector_map)
    groups = _groups(sector_map, close.columns)
    prev_i = max(0, len(panel) - 1 - lookback)
    rows = [{"sector": sec, "n": int(close[groups[sec]].iloc[-1].notna().sum()),
             "breadth": float(panel[sec].iloc[-1]),
             "breadth_prev": float(panel[sec].iloc[prev_i])} for sec in panel.columns]
    df = pd.DataFrame(rows)
    df["change"] = df["breadth"] - df["breadth_prev"]
    return df.sort_values("breadth", ascending=False).reset_index(drop=True)


def append_history(df: pd.DataFrame, path: Path, as_of: str) -> None:
    """同日覆寫 (冪等), 其他日期保留."""
    new = df[["sector", "n", "breadth"]].assign(date=as_of)[["date", "sector", "n", "breadth"]]
    if path.exists():
        old = pd.read_csv(path, dtype={"date": str})
        new = pd.concat([old[old["date"] != as_of], new])
    path.parent.mkdir(parents=True, exist_ok=True)
    new.sort_values(["date", "sector"]).to_csv(path, index=False, float_format="%.2f")


def format_line(df: pd.DataFrame, top: int = 3) -> str:
    zh = lambda s: SECTOR_ZH.get(s, s)  # noqa: E731
    head = " / ".join(f"{zh(r.sector)} {r.breadth:.1f}%({r.change:+.1f})"
                      for r in df.head(top).itertuples())
    up = df.loc[df["change"].idxmax()]
    dn = df.loc[df["change"].idxmin()]
    return (f"產業動能廣度 前{top}: {head} | 擴散最快: {zh(up.sector)} {up.change:+.1f}"
            f" | 收斂最快: {zh(dn.sector)} {dn.change:+.1f}")


# --------------------------------------------------------------------------- #
# DB glue
# --------------------------------------------------------------------------- #
def _inputs():
    import strong_pullback as sp
    import smart_money_analysis as sm
    import psycopg2
    conn = psycopg2.connect(**sp.DB)
    try:
        panel = sp.load_panel(conn, "2025-01-01")
    finally:
        conn.close()
    mom, close = sp.universe_filters(panel)
    return mom, close, sm.build_sector_map()


def today(write: bool = True) -> tuple[str, pd.DataFrame]:
    mom, close, smap = _inputs()
    df = sector_breadth(mom, close, smap)
    as_of = close.index[-1].date().isoformat()
    if write:
        append_history(df, HISTORY, as_of)
    return as_of, df


def backfill() -> int:
    mom, close, smap = _inputs()
    panel = breadth_panel(mom, close, smap).iloc[126:]     # 126 日報酬暖機後
    n = pd.DataFrame({sec: close[m].notna().sum(axis=1)
                      for sec, m in _groups(smap, close.columns).items()}).loc[panel.index]
    long = (panel.stack().rename("breadth").to_frame()
            .join(n.stack().rename("n")).reset_index()
            .rename(columns={"level_0": "date", "level_1": "sector"}))
    long["date"] = long["date"].dt.strftime("%Y-%m-%d")
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    long[["date", "sector", "n", "breadth"]].to_csv(HISTORY, index=False, float_format="%.2f")
    return len(long)


def validate() -> str:
    from scipy.stats import spearmanr
    mom, close, smap = _inputs()
    groups = _groups(smap, close.columns)
    B = breadth_panel(mom, close, smap)
    rs = pd.DataFrame({s: (close[m] / close[m].shift(63) - 1).median(axis=1) for s, m in groups.items()})
    lines = [f"產業動能廣度 IC 檢定 ({close.index[140].date()} → {close.index[-1].date()}, {len(groups)} 產業)"]
    for h in (20, 60):
        fwd = close.shift(-h) / close - 1
        um = fwd.median(axis=1)
        F = pd.DataFrame({s: fwd[m].median(axis=1) for s, m in groups.items()}).sub(um, axis=0)
        for name, X in (("RS63", rs), ("動能廣度", B)):
            ics = {}
            for d in close.index[140:len(close) - h:5]:
                x, y = X.loc[d], F.loc[d]
                ok = x.notna() & y.notna()
                if ok.sum() >= 6 and x[ok].nunique() > 1:
                    ics[d] = spearmanr(x[ok], y[ok])[0]
            ic = pd.Series(ics)
            nov = ic.iloc[::max(1, h // 5)]
            t = nov.mean() / nov.std() * np.sqrt(len(nov)) if len(nov) > 2 else float("nan")
            half = ic.index.year.astype(str) + "H" + ((ic.index.month > 6) + 1).astype(str)
            by = " ".join(f"{k}:{g.mean():+.2f}" for k, g in ic.groupby(half))
            lines.append(f"  {h}日 {name:6s} IC {ic.mean():+.3f} | 不重疊 n={len(nov)} t={t:+.2f} | {by}")
    lines.append("升級條件: 20 日動能廣度 t ≥2 且各半年同號 (plan 2026-10-16)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="不寫 history")
    a = ap.parse_args(argv)
    if a.backfill:
        print(f"wrote {backfill()} rows → {HISTORY.relative_to(REPO)}")
    elif a.validate:
        print(validate())
    else:
        as_of, df = today(write=not a.dry_run)
        print(as_of, format_line(df))
        print(df.round(1).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
