"""電子權值加權指數 — 市值權重 snapshot、定基 100 買進持有。

成分 = CORE（OFI 追蹤的 10 檔電子權值）＋ CANDIDATES 依市值取前 n_supplement 檔。
市值來源：Pilot_Reports metadata `**市值:** N 百萬台幣`（filename ground truth）。
"""
import re
from pathlib import Path

import pandas as pd

CORE = ["2330", "2317", "2454", "2308", "3711", "2382", "2379", "2303", "2357", "3231"]
CANDIDATES = ["3034", "3008", "3037", "2345", "3017", "6669", "2327", "2408",
              "2409", "3481", "3661", "6415"]
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "Pilot_Reports"
MCAP_RE = re.compile(r"\*\*市值:\*\*\s*([\d,]+)\s*百萬台幣")


def load_market_caps(tickers) -> dict:
    caps = {}
    for md in sorted(REPORTS_DIR.glob("*/*.md")):
        tk = md.name.split("_")[0]
        if tk in tickers and tk not in caps:
            m = MCAP_RE.search(md.read_text(encoding="utf-8"))
            if m:
                caps[tk] = float(m.group(1).replace(",", ""))
    return caps


def select_components(closes: pd.DataFrame, n_supplement: int = 8,
                      min_days: int = 390):
    """回傳 (成分list, 正規化權重dict)。CORE 缺市值或史料不足即 raise（資料完整性）。"""
    caps = load_market_caps(set(CORE) | set(CANDIDATES))
    ok = {s for s in closes.columns if closes[s].notna().sum() >= min_days}
    short_core = [s for s in CORE if s not in ok]
    if short_core:
        raise ValueError(f"CORE 成分史料不足 (<{min_days} 日): {short_core}")
    comps = list(CORE)
    missing_caps = [s for s in comps if s not in caps]
    if missing_caps:
        raise ValueError(f"CORE 成分缺市值 metadata: {missing_caps}")
    supp = sorted((s for s in CANDIDATES if s in ok and s in caps),
                  key=lambda s: caps[s], reverse=True)[:n_supplement]
    comps += supp
    total = sum(caps[s] for s in comps)
    return comps, {s: caps[s] / total for s in comps}


def build_index(closes: pd.DataFrame, weights: dict, max_ffill: int = 5) -> pd.Series:
    """定基買進持有指數（snapshot 市值權重套在基期）；權重取自當前市值快照，非嚴格 Laspeyres 基期量。

    index_t = Σ w_i × (P_it / P_i0) × 100；停牌 forward-fill 上限 max_ffill 日。
    """
    px = closes[list(weights)].ffill(limit=max_ffill).dropna()
    if px.empty:
        raise ValueError(
            f"無任何日期讓全部 {len(weights)} 檔成分同時有價 (ffill limit={max_ffill})")
    rel = px / px.iloc[0]
    return (rel * pd.Series(weights)).sum(axis=1) * 100.0


def validate_vs_taiex(index_s: pd.Series, taiex_s: pd.Series):
    """重疊區間日報酬相關。合格門檻 0.95（spec）。"""
    df = pd.concat([index_s.rename("idx"), taiex_s.rename("taiex")], axis=1).dropna()
    r = df.pct_change().dropna()
    return float(r["idx"].corr(r["taiex"])), len(r)
