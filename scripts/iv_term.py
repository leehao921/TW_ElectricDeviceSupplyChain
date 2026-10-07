"""iv_term.py — IV 期限表: 把各到期 ATM IV 換成「跟前一到期差」與「±1σ 點數區間」。

用戶 2026-10-07: 原本 `curve 1007:18.2 / 1012:16.3 / …` 看不出到期之間的差、也看不出換成
價格是多少點。每到期一行,手機 Discord code block 40 字寬內:

    IV 期限 · TXF 50,111
    到期   天  IV   差  ±1σ 區間
    10/07  1 18.1    —  438 49.4-50.3k

σ點 = F × IV × √(距結算天數 / 365),結算 = 到期日 13:30 (TPE);區間以該到期 forward 為中心
(無 forward 用參考價)。Plan: docs/plans/2026-10-06-discord-mobile-layout.md
"""
from __future__ import annotations

import math
from datetime import datetime, time

SETTLE = time(13, 30)
SHAPE_MIN = 1.0          # vol-pt: 凹陷/凸起/倒掛 判定門檻


def _days_to_settle(expiry: str, now: datetime) -> float:
    settle = datetime.combine(datetime.strptime(expiry, "%Y%m%d").date(), SETTLE)
    return max((settle - now).total_seconds() / 86400, 0.0)


def iv_term_lines(curve, forwards: dict, ref: tuple, now: datetime) -> list:
    """curve [(YYYYMMDD, atm_iv%)] 依到期排序 → 表格行 list;空 curve → []。
    ref = (標籤, 價格),無 forward 的到期以 ref 價格為中心。"""
    if not curve:
        return []
    label, ref_px = ref
    lines = ["IV 期限 · %s %s" % (label, format(ref_px, ",.0f")),
             "到期   天  IV   差  ±1σ 區間"]
    prev = None
    for exp, iv in curve:
        f = forwards.get(exp) or ref_px
        days = _days_to_settle(exp, now)
        sigma = f * iv / 100 * math.sqrt(max(days, 0.01) / 365)
        diff = "—" if prev is None else "%+.1f" % (iv - prev)
        lines.append("%s %2d %4.1f %4s %4d %.1f-%.1fk" % (
            exp[4:6] + "/" + exp[6:], round(days), iv, diff, round(sigma),
            (f - sigma) / 1000, (f + sigma) / 1000))
        prev = iv
    ivs = [iv for _, iv in curve]
    tag = [e[4:6] + "/" + e[6:] for e, _ in curve]
    if len(ivs) >= 2 and ivs[0] - ivs[1] >= SHAPE_MIN:
        lines.append("⚠ 前端倒掛 %s > %s (%+.1f)" % (tag[0], tag[1], ivs[0] - ivs[1]))
    for i in range(1, len(ivs) - 1):
        lo, hi = min(ivs[i - 1], ivs[i + 1]), max(ivs[i - 1], ivs[i + 1])
        if ivs[i] <= lo - SHAPE_MIN:
            lines.append("⚠ %s 低於前後 → 凹陷" % tag[i])
        elif ivs[i] >= hi + SHAPE_MIN:
            lines.append("⚠ %s 高於前後 → 凸起(事件?)" % tag[i])
    return lines
