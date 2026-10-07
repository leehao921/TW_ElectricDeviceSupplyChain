"""iv_term.py — IV 期限表: 把各到期 ATM IV 換成「跟前一到期差」與「±1σ 點數區間」。

用戶 2026-10-07: 原本 `curve 1007:18.2 / 1012:16.3 / …` 看不出到期之間的差、也看不出換成
價格是多少點。每到期一行,手機 Discord code block 40 字寬內:

    IV 期限 · TXF 50,111
    到期   天  IV   差  ±1σ 區間
    10/07  1 18.1    —  438 49.4-50.3k

σ點 = F × IV × √(距結算天數 / 365),結算 = 到期日 13:30 (TPE);區間以該到期 forward 為中心
(無 forward 用參考價)。Plan: docs/plans/2026-10-06-discord-mobile-layout.md

形狀警示 (倒掛/凹陷/凸起) 以「交易日口徑」IV 比較 (2026-10-07): 日曆天 IV 會把跨週末/連假的
週選壓低、把結算前一晚的前端拉高 — 10/06 的「10/07 倒掛」「10/12 凹陷」皆為此假象
(10/09 國慶補假,10/12 只剩 3 場)。只剩結算當日一場的腿不參與判定。
「差」欄同樣用交易日口徑 (IV 欄維持日曆天原值,方便對照券商報價)。
"""
from __future__ import annotations

import importlib.util
import math
from datetime import date, datetime, time, timedelta
from pathlib import Path

SETTLE = time(13, 30)
SHAPE_MIN = 1.0          # vol-pt: 凹陷/凸起/倒掛 判定門檻
MIN_SESSIONS = 2         # 只剩結算當日一場 → 不參與形狀判定
REPO = Path(__file__).resolve().parents[1]
DB_HOLIDAYS = REPO.parent / "database" / "src" / "tmf" / "data" / "pipeline" / "tw_holidays.py"
LOCAL_HOLIDAYS = REPO / "data" / "tw_market_holidays.txt"


def load_holidays() -> set:
    """權威假日表 = database tw_holidays.py (按檔案路徑載入,避開套件 __init__ 依賴);
    失敗退回本 repo data/tw_market_holidays.txt。"""
    try:
        spec = importlib.util.spec_from_file_location("_tw_holidays", DB_HOLIDAYS)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return set(mod.TW_MARKET_HOLIDAYS)
    except Exception:
        out = set()
        if LOCAL_HOLIDAYS.exists():
            for ln in LOCAL_HOLIDAYS.read_text().splitlines():
                ln = ln.split("#", 1)[0].strip()
                if ln:
                    out.add(date.fromisoformat(ln))
        return out


def trading_sessions(expiry: str, now: datetime, holidays) -> int:
    """距結算剩幾個日盤 (含結算日;今天 13:30 前且為交易日則今天算一場)。"""
    end = datetime.strptime(expiry, "%Y%m%d").date()
    d = now.date() if now.time() < SETTLE else now.date() + timedelta(days=1)
    n = 0
    while d <= end:
        if d.weekday() < 5 and d not in holidays:
            n += 1
        d += timedelta(days=1)
    return n


def _iv_trading_basis(iv: float, cal_days: float, sessions: int) -> float:
    """同一總變異數換成交易日口徑: σ_td = σ_cal × √((日曆天/365) / (交易日/252))。"""
    return iv * math.sqrt((max(cal_days, 0.01) / 365) / (sessions / 252))


def _days_to_settle(expiry: str, now: datetime) -> float:
    settle = datetime.combine(datetime.strptime(expiry, "%Y%m%d").date(), SETTLE)
    return max((settle - now).total_seconds() / 86400, 0.0)


def iv_term_lines(curve, forwards: dict, ref: tuple, now: datetime, holidays=None) -> list:
    """curve [(YYYYMMDD, atm_iv%)] 依到期排序 → 表格行 list;空 curve → []。
    ref = (標籤, 價格),無 forward 的到期以 ref 價格為中心。"""
    if not curve:
        return []
    label, ref_px = ref
    if holidays is None:
        holidays = load_holidays()
    lines = ["IV 期限 · %s %s" % (label, format(ref_px, ",.0f")),
             "到期   天  IV   差  ±1σ 區間"]
    prev_td, legs = None, []                     # legs: 參與形狀判定 (標籤, 交易日口徑 IV)
    for exp, iv in curve:
        tag = exp[4:6] + "/" + exp[6:]
        f = forwards.get(exp) or ref_px
        days = _days_to_settle(exp, now)
        n = trading_sessions(exp, now, holidays)
        iv_td = _iv_trading_basis(iv, days, n) if n else iv
        sigma = f * iv / 100 * math.sqrt(max(days, 0.01) / 365)
        diff = "—" if prev_td is None else "%+.1f" % (iv_td - prev_td)
        lines.append("%s %2d %4.1f %4s %4d %.1f-%.1fk" % (
            tag, round(days), iv, diff, round(sigma), (f - sigma) / 1000, (f + sigma) / 1000))
        prev_td = iv_td
        if n >= MIN_SESSIONS:
            legs.append((tag, iv_td))
    tags, ivs = [t for t, _ in legs], [v for _, v in legs]
    if len(ivs) >= 2 and ivs[0] - ivs[1] >= SHAPE_MIN:
        lines.append("⚠ 前端倒掛 %s > %s (%+.1f)" % (tags[0], tags[1], ivs[0] - ivs[1]))
    for i in range(1, len(ivs) - 1):
        lo, hi = min(ivs[i - 1], ivs[i + 1]), max(ivs[i - 1], ivs[i + 1])
        if ivs[i] <= lo - SHAPE_MIN:
            lines.append("⚠ %s 低於前後 → 凹陷" % tags[i])
        elif ivs[i] >= hi + SHAPE_MIN:
            lines.append("⚠ %s 高於前後 → 凸起(事件?)" % tags[i])
    lines.append("差=交易日口徑 (排除週末/假日)")
    return lines
