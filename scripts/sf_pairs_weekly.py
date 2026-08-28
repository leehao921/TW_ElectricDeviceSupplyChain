#!/usr/bin/env python3
"""股期多空配對週報 (週一 08:00 → 本週交易計畫) — 多/空腿 + 配對 + β 蓋板 + 停損停利 + 追蹤.

Universe = TAIFEX 股票期貨標的 (股期取代融資的可執行池, 保證金 ~13.5%, 無券源限制)。
評分因子透明: 外資 5D/20D 淨額 + 借券 5D 變化 (法人對沖腿)；空腿加註 S2 融資投降結構。
配對優先同產業 (上下游對偶 = factor-hedged)，跨產業標 β pair。
停損停利 = ATR14 基準 (1.5x / 2.5x)，pair 層 spread +8% 停利 / 20 交易日到期。
所有價位為分析標註, 不構成交易指令；實際進場請同步 position_triggers。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
UNIVERSE_CACHE = REPO / "data" / "stock_futures_universe.json"
STATE_PATH = REPO / "data" / "sf_pairs_state.json"
HISTORY_PATH = REPO / "data" / "sf_pairs_history.json"
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")
STOP_ATR, TP_ATR = 1.5, 2.5
SPREAD_TP_PCT, MAX_HOLD_TD = 8.0, 20
N_LEGS, MAX_PAIRS, IND_CAP = 8, 5, 2


# ------------------------------------------------------------------ universe
def fetch_universe(cache: Path = UNIVERSE_CACHE, max_age_days: int = 30) -> list:
    """TAIFEX 股票期貨標的清單 (快取 30 天)."""
    if cache.exists():
        d = json.loads(cache.read_text())
        if (date.today() - date.fromisoformat(d["as_of"])).days < max_age_days:
            return d["symbols"]
    import requests
    r = requests.get("https://www.taifex.com.tw/cht/2/stockLists", timeout=30)
    r.encoding = "utf-8"
    symbols = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S):
        cells = [re.sub(r"<[^>]+>|\s+", "", c)
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 5 and re.fullmatch(r"\d{4}", cells[2] or "") \
                and "是股票期貨標的" in cells[4]:
            symbols.append(cells[2])
    if symbols:
        cache.write_text(json.dumps(
            {"as_of": date.today().isoformat(), "symbols": sorted(set(symbols))},
            ensure_ascii=False))
        return sorted(set(symbols))
    if cache.exists():  # 抓失敗用舊快取
        return json.loads(cache.read_text())["symbols"]
    return []


# ------------------------------------------------------------------ metrics
def load_metrics(conn, syms: list) -> pd.DataFrame:
    """每檔: 外資 5/20D 億、借券/融資 5D 變化、乖離、ATR14、close."""
    inst = pd.read_sql("""
      SELECT date, symbol, foreign_net * close_price / 1e8 AS f_yi
      FROM institutional_stock WHERE date >= now()::date - 45 AND symbol = ANY(%(s)s)""",
                       conn, params={"s": syms})
    f = inst.pivot_table(index="date", columns="symbol", values="f_yi", aggfunc="sum")
    f5, f20 = f.tail(5).sum(), f.tail(20).sum()
    mg = pd.read_sql("""
      WITH d5 AS (SELECT DISTINCT date FROM margin_daily ORDER BY date DESC LIMIT 5)
      SELECT symbol,
        max(sbl_balance) FILTER (WHERE date=(SELECT max(date) FROM d5))
          - max(sbl_balance) FILTER (WHERE date=(SELECT min(date) FROM d5)) AS dsbl,
        (max(fin_balance) FILTER (WHERE date=(SELECT max(date) FROM d5))
          - max(fin_balance) FILTER (WHERE date=(SELECT min(date) FROM d5)))::float
          / NULLIF(max(fin_balance) FILTER (WHERE date=(SELECT min(date) FROM d5)), 0)
          AS dfin_pct
      FROM margin_daily WHERE date IN (SELECT date FROM d5) AND symbol = ANY(%(s)s)
      GROUP BY symbol""", conn, params={"s": syms}).set_index("symbol")
    px = pd.read_sql("""SELECT symbol, ts::date d, high, low, close
                        FROM stock_daily_ohlcv
                        WHERE ts >= now() - interval '60 days' AND symbol = ANY(%(s)s)
                        ORDER BY 1,2""", conn, params={"s": syms}, parse_dates=["d"])
    close = px.pivot(index="d", columns="symbol", values="close")
    high = px.pivot(index="d", columns="symbol", values="high")
    low = px.pivot(index="d", columns="symbol", values="low")
    tr = pd.concat([high - low, (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs()]).groupby(level=0).max()
    atr14 = tr.rolling(14).mean().iloc[-1]
    dev20 = (close / close.rolling(20).mean() - 1).iloc[-1]
    out = pd.DataFrame({"f5": f5, "f20": f20, "close": close.iloc[-1],
                        "atr14": atr14, "dev20": dev20})
    out = out.join(mg[["dsbl", "dfin_pct"]])
    return out.dropna(subset=["close", "atr14", "f5"])


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """score = z(f5) + z(f20) − z(dsbl_norm): 外資流入+借券回補=多, 反向=空."""
    z = lambda s: (s - s.mean()) / (s.std() or 1)  # noqa: E731
    dsbl_norm = (df.dsbl.fillna(0)) / (df.close * 1000)  # 股 → 概略張數規模正規化
    df = df.assign(score=z(df.f5) + z(df.f20) - z(dsbl_norm))
    df["s2_flag"] = (df.dfin_pct.fillna(0) < -0.01)
    return df.sort_values("score", ascending=False)


# ------------------------------------------------------------------ pairing
def build_pairs(longs: list, shorts: list, max_pairs: int = MAX_PAIRS) -> list:
    """優先同產業 (同鏈對偶), 其次跨產業 β; 同產業 pair 上限 IND_CAP."""
    pairs, used_l, used_s, ind_count = [], set(), set(), {}
    for lg in longs:                                     # pass 1: 同產業
        if len(pairs) >= max_pairs or lg["symbol"] in used_l:
            continue
        for sh in shorts:
            if sh["symbol"] in used_s or sh["industry"] != lg["industry"]:
                continue
            if ind_count.get(lg["industry"], 0) >= IND_CAP:
                break
            pairs.append({"long": lg, "short": sh, "kind": "同鏈對偶"})
            used_l.add(lg["symbol"]); used_s.add(sh["symbol"])
            ind_count[lg["industry"]] = ind_count.get(lg["industry"], 0) + 1
            break
    for lg in longs:                                     # pass 2: 跨產業 β
        if len(pairs) >= max_pairs or lg["symbol"] in used_l:
            continue
        for sh in shorts:
            if sh["symbol"] in used_s:
                continue
            if sh["industry"] == lg["industry"] \
                    and ind_count.get(lg["industry"], 0) >= IND_CAP:
                continue                                 # 同產業配額已滿
            pairs.append({"long": lg, "short": sh, "kind": "跨產業β"})
            used_l.add(lg["symbol"]); used_s.add(sh["symbol"])
            break
    return pairs


def leg_levels(close: float, atr: float, side: str) -> dict:
    """ATR 基準價位: 停損 1.5×ATR 逆向, 停利 2.5×ATR 順向 (空腿鏡像)."""
    sgn = 1 if side == "long" else -1
    return {"entry": round(close, 2),
            "stop": round(close - sgn * STOP_ATR * atr, 2),
            "tp": round(close + sgn * TP_ATR * atr, 2)}


# ------------------------------------------------------------------ tracking
def evaluate_pair(pair: dict, closes: dict, trading_days_held: int) -> dict:
    """日 close 檢查: 任一腿破停損=stopped → spread≥+8%=tp → 滿 20 交易日=expired."""
    lg, sh = pair["long"], pair["short"]
    lc, sc = closes.get(lg["symbol"]), closes.get(sh["symbol"])
    if lc is None or sc is None:
        return {"status": "active", "spread_ret": None}
    l_ret = (lc / lg["entry"] - 1) * 100
    s_ret = (1 - sc / sh["entry"]) * 100          # 空腿: 跌 = 正報酬
    spread = round(l_ret + s_ret, 2)
    if lc <= lg["stop"] or sc >= sh["stop"]:
        status = "stopped"
    elif spread >= SPREAD_TP_PCT:
        status = "tp"
    elif trading_days_held >= MAX_HOLD_TD:
        status = "expired"
    else:
        status = "active"
    return {"status": status, "spread_ret": spread}


def update_tracking(state: dict, conn, as_of: str) -> list:
    """檢查 active pairs 觸價/到期 → 畢業樣本."""
    graduated = []
    with conn.cursor() as cur:
        for pid, pair in list(state.get("pairs", {}).items()):
            syms = [pair["long"]["symbol"], pair["short"]["symbol"]]
            closes = {}
            for s in syms:
                cur.execute("""SELECT close FROM stock_daily_ohlcv
                               WHERE symbol=%s AND ts::date<=%s ORDER BY ts DESC LIMIT 1""",
                            (s, as_of))
                r = cur.fetchone()
                closes[s] = float(r[0]) if r and r[0] else None
            cur.execute("""SELECT count(DISTINCT ts::date) FROM stock_daily_ohlcv
                           WHERE symbol=%s AND ts::date > %s AND ts::date <= %s""",
                        (syms[0], pair["enter_date"], as_of))
            days = cur.fetchone()[0]
            ev = evaluate_pair(pair, closes, days)
            pair.update(last_check=as_of, days_held=days, **ev)
            if ev["status"] != "active":
                graduated.append(pair)
                del state["pairs"][pid]
    return graduated


# ------------------------------------------------------------------ cross flags
def format_flags(sym: str, warrant_long: set, warrant_short: set,
                 scan_families: dict, pb_lights: dict) -> str:
    """其他模塊交叉確認標籤: 權證榜/日掃名單/P-B 燈號."""
    tags = []
    if sym in warrant_long:
        tags.append("權證佈多榜")
    if sym in warrant_short:
        tags.append("權證佈空榜(反指標傾向)")
    for fam in scan_families.get(sym, []):
        tags.append(f"日掃:{fam}")
    if pb_lights.get(sym):
        tags.append(f"P/B:{pb_lights[sym]}")
    return " · ".join(tags)


def load_cross_signals(conn) -> tuple[set, set, dict, dict]:
    """權證佈多/佈空 top15 + 近 5 日日掃名單 + P/B 燈號."""
    wl, ws = set(), set()
    try:
        wf = pd.read_sql("""SELECT underlying, score FROM warrant_flow_daily
                            WHERE date = (SELECT max(date) FROM warrant_flow_daily)""", conn)
        wl = set(wf.nlargest(15, "score").underlying)
        ws = set(wf.nsmallest(15, "score").underlying)
    except Exception:
        pass
    fams: dict[str, list] = {}
    try:
        st = json.loads((REPO / "data" / "signal_scan_state.json").read_text())
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        for e in st.get("tracked", {}).values():
            if e.get("enter_date", "") >= cutoff:
                fams.setdefault(e["symbol"], []).append(e["family"])
    except Exception:
        pass
    pb: dict[str, str] = {}
    try:
        import redis
        for k, v in redis.Redis(decode_responses=True).hgetall("h:agent:pb_lights").items():
            try:
                light = json.loads(v).get("light")
            except Exception:
                light = v if v in ("RED", "YELLOW", "GREEN") else None
            if light:
                pb[k] = light
    except Exception:
        pass
    return wl, ws, fams, pb


# ------------------------------------------------------------------ options env
def options_env_lines(row: dict) -> list:
    """選擇權環境面板: VIX/VRP/skew → 對沖工具選擇指引."""
    if not row:
        return []
    vrp = row.get("vrp_30d")
    wm = row.get("wm_spread")
    out = ["## 選擇權環境（對沖工具選擇）", "",
           f"- VIX {row.get('vix', '–')} · VIX30 {row.get('vix_30d', '–')} · "
           f"RV21 {row.get('rv_21d', '–')} · **VRP30 {vrp if vrp is not None else '–'}** · "
           f"週選 {row.get('vix_w', '–')} · 週/月 {wm if wm is not None else '–'}"]
    if vrp is not None:
        if vrp < 0:
            out.append("- VRP 為負 → **保險便宜**: 蓋板優先考慮買 put（划算）而非空期貨")
        elif vrp > 8:
            out.append("- VRP 肥厚 → 保險貴: 對沖用期貨蓋板, 勿買貴的 put")
        else:
            out.append("- VRP 中性 → 期貨蓋板與 put 成本相當, 依執行便利選")
    if wm is not None and wm > 2:
        out.append(f"- 🚨 週/月 IV 倒掛 {wm:+.1f} → 即期事件恐慌, 本週計畫降槓桿執行")
    sk = row.get("iv_skew_25d")
    if sk is not None:
        out.append(f"- 25Δ skew {sk:+.1f}（負=下檔保護相對便宜）")
    out.append("")
    return out


# ------------------------------------------------------------------ hedge
def hedge_plan(conn) -> list:
    """期貨/股票對沖: 現貨持倉 β 蓋板需要的微台口數 + regime gate 現況."""
    lines = ["## 期貨/股票對沖（β 蓋板）", ""]
    try:
        hp = json.loads((REPO / "data" / "portfolio_holdings.json").read_text())
        mv = sum(h.get("market_value", 0) for h in hp.get("holdings", []))
    except Exception:
        return lines + ["（讀取持倉失敗）", ""]
    with conn.cursor() as cur:
        cur.execute("""SELECT last(close, bucket) FROM ohlcv_1m_txf
                       WHERE symbol='TXF' AND bucket >= now() - interval '7 days'""")
        r = cur.fetchone()
        txf = float(r[0]) if r and r[0] else None
        cur.execute("SELECT wm_spread FROM vix_daily WHERE wm_spread IS NOT NULL "
                    "ORDER BY date DESC LIMIT 1")
        r = cur.fetchone()
        wm = float(r[0]) if r and r[0] else None
    if not txf:
        return lines + ["（TXF 價格不可得）", ""]
    notional = txf * 10                                   # 微台 NT$10/點
    n_full = mv / notional
    gate_px = "🚨 跌破" if txf < 39385 else "✅ 之上"
    gate_iv = ("🚨 倒掛" if wm is not None and wm > 2 else
               f"✅ {wm:+.1f}" if wm is not None else "–")
    lines += [
        f"- 現貨市值 ≈ {mv/1e4:,.0f} 萬 · TXF {txf:,.0f} · 微台每口名目 ≈ {notional/1e4:,.0f} 萬",
        f"- **全蓋 ≈ {n_full:.1f} 口微台 / 半蓋 ≈ {n_full/2:.1f} 口**（β≈1 粗估，未按個股 β 加權）",
        f"- 觸發 gate: TAIEX 39,385 {gate_px}（現 {txf:,.0f}）· 週/月 IV 倒掛 {gate_iv}（>+2 亮燈）",
        "- 規則: gate 亮燈 → 蓋半至全；平時不蓋（保留牛市 β）。蓋板是防守不是交易", ""]
    return lines


# ------------------------------------------------------------------ main
def main() -> int:
    import psycopg2
    from warrant_flow_rank import load_labels
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    as_of = date.today().isoformat()
    labels = load_labels()
    universe = fetch_universe()
    if not universe:
        print("[error] 股期 universe 不可得", file=sys.stderr)
        return 1

    df = score_candidates(load_metrics(conn, universe))
    disp = set()
    dp = REPO / "data" / "disposition_current.json"
    if dp.exists():
        disp = set(json.loads(dp.read_text()).get("active", {}).keys())
    df = df[~df.index.isin(disp)]

    def cand(row_iter):
        out = []
        for sym, r in row_iter:
            lb = labels.get(sym, {})
            out.append({"symbol": sym, "name": lb.get("name", ""),
                        "industry": lb.get("sector") or "其他",
                        "score": round(float(r.score), 2),
                        "f5": round(float(r.f5), 1), "f20": round(float(r.f20), 1),
                        "dsbl": int(r.dsbl) if pd.notna(r.dsbl) else 0,
                        "s2": bool(r.s2_flag), "close": float(r.close),
                        "atr": float(r.atr14), "dev20": float(r.dev20)})
        return out

    longs = cand(df.head(N_LEGS).iterrows())
    shorts = cand(df.tail(N_LEGS).sort_values("score").iterrows())
    pairs = build_pairs(longs, shorts)

    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {"pairs": {}}
    history = json.loads(HISTORY_PATH.read_text()) if HISTORY_PATH.exists() else []
    graduated = update_tracking(state, conn, as_of)
    history.extend(graduated)

    # 本週新 pair 入追蹤 (帶價位); id = 週+序號
    for i, p in enumerate(pairs, 1):
        pid = f"{as_of}#{i}"
        state["pairs"][pid] = {
            "id": pid, "enter_date": as_of, "kind": p["kind"],
            "long": {"symbol": p["long"]["symbol"], "name": p["long"]["name"],
                     **leg_levels(p["long"]["close"], p["long"]["atr"], "long")},
            "short": {"symbol": p["short"]["symbol"], "name": p["short"]["name"],
                      **leg_levels(p["short"]["close"], p["short"]["atr"], "short")}}
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2))

    # ---- report
    wl, ws, fams, pb = load_cross_signals(conn)

    def leg_line(c, side):
        lv = leg_levels(c["close"], c["atr"], side)
        s2 = " ⚠S2融資投降" if c["s2"] and side == "short" else ""
        fl = format_flags(c["symbol"], wl, ws, fams, pb)
        fl = f"\n  ↳ 交叉: {fl}" if fl else ""
        return (f"- **{c['symbol']} {c['name']}**（{c['industry']}）score {c['score']:+.2f} · "
                f"外資5D {c['f5']:+.1f}億/20D {c['f20']:+.1f}億 · 借券5D {c['dsbl']/1000:+,.0f}千股 · "
                f"乖離 {c['dev20']*100:+.1f}%{s2}\n"
                f"  入場 {lv['entry']} / 停損 {lv['stop']} / 停利 {lv['tp']}（1.5/2.5×ATR14）{fl}")

    lines = [f"# 本週交易計畫 — 股期多空配對 {as_of}", "",
             f"Universe: TAIFEX 股期標的 {len(universe)} 檔（保證金約 13.5%，無券源限制）·",
             "評分 = z(外資5D) + z(外資20D) − z(借券5DΔ)；空腿 ⚠ = 融資 5D 減（S2 投降結構）", "",
             "## 多方腿候選（top 8）", ""]
    lines += [leg_line(c, "long") for c in longs]
    lines += ["", "## 空方腿候選（bottom 8）", ""]
    lines += [leg_line(c, "short") for c in shorts]
    lines += ["", "## 本週配對（≤5 組，優先同鏈對偶）", ""]
    for i, p in enumerate(pairs, 1):
        lines.append(f"{i}. **[{p['kind']}]** Long {p['long']['symbol']} {p['long']['name']} / "
                     f"Short {p['short']['symbol']} {p['short']['name']}"
                     f"（{p['long']['industry']} vs {p['short']['industry']}）")
    lines += ["", "  Pair 出場規則: 任一腿收盤破停損 → 整組出場；spread ≥ +8% 停利；滿 20 交易日到期", ""]

    # 選擇權環境
    env = pd.read_sql("""SELECT vix, vix_30d, rv_21d, vrp_30d, vix_w, wm_spread,
                                iv_skew_25d, term_slope
                         FROM vix_daily ORDER BY date DESC LIMIT 1""", conn)
    lines += options_env_lines(
        {k: (round(float(v), 1) if v is not None and pd.notna(v) else None)
         for k, v in env.iloc[0].items()} if not env.empty else {})

    # 處置事件腿 (S1/L1 VALIDATED — 多半無股期, 現股/事件觀察)
    try:
        from signal_scan import scan_disposition
        disp_l, disp_s = scan_disposition(as_of)
        lines += ["## 處置事件腿（S1/L1 VALIDATED · 多半無股期 → 現股執行）", ""]
        for sym, d in disp_l:
            lines.append(f"- 多方: **{sym} {labels.get(sym, {}).get('name', '')}** {d}（買超組 +3.59%/10D 基準）")
        for sym, d in disp_s:
            lines.append(f"- 空方: **{sym} {labels.get(sym, {}).get('name', '')}** {d}（賣超組 -1.73%/10D · 無券可空則僅避開）")
        if not disp_l and not disp_s:
            lines.append("（本週 3 日內無即將解除）")
        lines.append("")
    except Exception as e:
        print(f"[warn] disposition section failed: {e}", file=sys.stderr)

    lines += hedge_plan(conn)
    active = [p for p in state["pairs"].values() if p["enter_date"] != as_of]
    lines += ["## 追蹤中（上週起）", ""]
    if active:
        for p in sorted(active, key=lambda x: x["enter_date"]):
            lines.append(f"- {p['id']} Long {p['long']['symbol']}/Short {p['short']['symbol']}: "
                         f"spread {p.get('spread_ret', '–')}% · {p.get('days_held', 0)} 交易日")
    else:
        lines.append("（無）")
    done = [h for h in history if h.get("spread_ret") is not None]
    if done:
        import statistics
        wins = sum(1 for h in done if h["spread_ret"] > 0)
        lines += ["", f"## 畢業統計: n={len(done)} · 勝率 {wins}/{len(done)} · "
                      f"spread 中位 {statistics.median(h['spread_ret'] for h in done):+.1f}%"
                      f"（tp {sum(1 for h in done if h['status']=='tp')} / "
                      f"stop {sum(1 for h in done if h['status']=='stopped')} / "
                      f"expired {sum(1 for h in done if h['status']=='expired')}）"]
    lines += ["", "*源: sf_pairs_weekly.py 週一 08:00 · 價位為分析標註不構成交易指令 · "
                  "日 close 檢查無盤中監控；實際進場請同步 position_triggers*"]
    md = "\n".join(lines)
    out = REPO / "analysis" / f"sf_pairs_{as_of}.md"
    out.write_text(md)
    print(md[:1500])
    try:
        import redis
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "sf_pairs", "topic": "sf-pairs",
            "tags": "pairs,stock-futures,weekly", "as_of": as_of,
            "msg": f"股期配對週報 {as_of}: {len(pairs)} 組新配對 "
                   f"({sum(1 for p in pairs if p['kind']=='同鏈對偶')} 同鏈) · "
                   f"追蹤中 {len(active)} · 畢業 {len(graduated)}",
            "report_path": f"analysis/{out.name}"})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
