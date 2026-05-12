"""
foplp_watchlist.py — FOPLP 供應鏈財報追蹤

Usage:
  python3 scripts/foplp_watchlist.py            # 完整分析
  python3 scripts/foplp_watchlist.py --update   # 更新財報 + 分析
  python3 scripts/foplp_watchlist.py --quick    # 只看最新股價和估值

Companies tracked:
  3481  群創光電   Electronic Components   (FOPLP 封裝廠, SpaceX 客戶)
  6664  群翊       Specialty Machinery     (FOPLP 設備供應商)
  3711  日月光投控  Semiconductors          (OSAT, K28 FOPLP 建線中)
  3264  欣銓       Semiconductors          (OSAT, 先進封裝測試)
  6286  力成科技   Semiconductors          (OSAT, COF/驅動IC, yfinance用IMOS)
"""

import sys
import os
import subprocess
import urllib.request
import urllib.parse
import json
from datetime import datetime, date

import yfinance as yf
import pandas as pd

WATCHLIST = [
    {"ticker": "3481", "name": "群創光電",   "yf_sym": "3481.TW",  "role": "FOPLP 封裝廠 (SpaceX)"},
    {"ticker": "6664", "name": "群翊",       "yf_sym": "6664.TWO", "role": "FOPLP 設備供應商"},
    {"ticker": "3711", "name": "日月光投控", "yf_sym": "3711.TW",  "role": "OSAT 龍頭 (K28建線)"},
    {"ticker": "3264", "name": "欣銓",       "yf_sym": "3264.TWO", "role": "先進封裝測試"},
    {"ticker": "6286", "name": "力成科技",   "yf_sym": "IMOS",     "role": "COF/驅動IC封測 (NASDAQ雙掛)"},
]

# Earnings season windows (月份)
EARNINGS_MONTHS = {
    "Q4/年報": [3, 4],    # 3-4月公布
    "Q1":      [5],        # 5月公布
    "Q2":      [8],        # 8月公布
    "Q3":      [11],       # 11月公布
}

def get_current_earnings_season():
    m = date.today().month
    for season, months in EARNINGS_MONTHS.items():
        if m in months:
            return season
    return None


def fetch_monthly_revenue(ticker: str, listed: str = "sii") -> list[dict]:
    """
    從公開資訊觀測站（MOPS）抓取月營收。
    listed: 'sii' = 上市(TWSE), 'otc' = 上櫃(OTC)
    回傳: [{year, month, revenue_k, mom_pct, yoy_pct}, ...]
    """
    url = "https://mops.twse.com.tw/mops/web/ajax_t05st10_ifrs"
    data = urllib.parse.urlencode({
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "co_id": ticker,
        "TYPEK": listed,
    }).encode()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://mops.twse.com.tw/mops/web/t05st10_ifrs",
    }
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        # Parse HTML table — extract rows with revenue data
        rows = []
        import re
        # Find all <tr> rows with numeric data
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", raw, re.S)
        for tr in trs:
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            tds = [re.sub(r"<[^>]+>", "", td).strip().replace(",", "") for td in tds]
            # Expect: year, month, revenue, mom%, yoy%, accumulated, acc_yoy%
            if len(tds) >= 5 and tds[0].isdigit() and tds[1].isdigit():
                try:
                    rows.append({
                        "year": int(tds[0]) + 1911,  # ROC to AD
                        "month": int(tds[1]),
                        "revenue_m": round(int(tds[2]) / 1000, 2) if tds[2] else None,  # 千元→百萬
                        "mom_pct": float(tds[3]) if tds[3] not in ("", "--", "N/A") else None,
                        "yoy_pct": float(tds[4]) if tds[4] not in ("", "--", "N/A") else None,
                    })
                except (ValueError, IndexError):
                    continue
        return rows[:12]  # 最近12個月
    except Exception as e:
        return []


def print_monthly_revenue_table():
    """抓取並顯示所有追蹤公司的月營收"""
    listed_map = {"3481": "sii", "6664": "otc", "3711": "sii", "3264": "otc", "6286": "sii"}
    print("\n━━━ 月營收追蹤（公開資訊觀測站）━━━")
    for co in WATCHLIST:
        if co["ticker"] == "6286":
            print(f"\n  {co['ticker']} {co['name']}: 請至 MOPS 查詢（或用 IMOS 在 yfinance）")
            continue
        rows = fetch_monthly_revenue(co["ticker"], listed_map.get(co["ticker"], "sii"))
        if not rows:
            print(f"\n  {co['ticker']} {co['name']}: 無法取得月營收（MOPS 查無資料）")
            continue
        latest = rows[0]
        prev   = rows[1] if len(rows) > 1 else {}
        print(f"\n  {co['ticker']} {co['name']}")
        print(f"  {'年月':<8} {'營收(百萬)':>10} {'月增%':>8} {'年增%':>8}")
        print(f"  {'-'*38}")
        for r in rows[:6]:
            ym   = f"{r['year']}/{r['month']:02d}"
            rev  = f"{r['revenue_m']:.0f}" if r['revenue_m'] else "N/A"
            mom  = f"{r['mom_pct']:+.1f}%" if r['mom_pct'] is not None else "N/A"
            yoy  = f"{r['yoy_pct']:+.1f}%" if r['yoy_pct'] is not None else "N/A"
            print(f"  {ym:<8} {rev:>10} {mom:>8} {yoy:>8}")


def fetch_snapshot():
    """抓取所有公司的最新市場快照"""
    rows = []
    for co in WATCHLIST:
        try:
            t = yf.Ticker(co["yf_sym"])
            info = t.info
            price    = info.get("currentPrice") or info.get("regularMarketPrice", 0)
            prev     = info.get("previousClose", 0)
            chg_pct  = ((price - prev) / prev * 100) if prev else 0
            mkt_cap  = info.get("marketCap", 0)
            pe       = info.get("trailingPE", None)
            pb       = info.get("priceToBook", None)
            rev_ttm  = info.get("totalRevenue", None)
            rows.append({
                "代碼":   co["ticker"],
                "公司":   co["name"],
                "角色":   co["role"],
                "現價":   f"{price:.1f}",
                "漲跌%":  f"{chg_pct:+.2f}%",
                "市值(億)": f"{mkt_cap/1e8:.0f}" if mkt_cap else "N/A",
                "P/E":    f"{pe:.1f}" if pe else "N/A",
                "P/B":    f"{pb:.1f}" if pb else "N/A",
            })
        except Exception as e:
            rows.append({
                "代碼": co["ticker"], "公司": co["name"], "角色": co["role"],
                "現價": "ERR", "漲跌%": str(e)[:30],
                "市值(億)": "-", "P/E": "-", "P/B": "-",
            })
    return pd.DataFrame(rows)


def fetch_revenue_trend(yf_sym: str, quarters: int = 6):
    """抓取最近幾季營收趨勢"""
    try:
        t = yf.Ticker(yf_sym)
        q = t.quarterly_financials
        if q is None or q.empty:
            return None
        rev_row = [r for r in q.index if "Revenue" in str(r) or "revenue" in str(r).lower()]
        if not rev_row:
            return None
        rev = q.loc[rev_row[0]].sort_index(ascending=False).head(quarters)
        return rev
    except Exception:
        return None


def update_financials():
    """呼叫 update_financials.py 更新財報"""
    tickers = [co["ticker"] for co in WATCHLIST if co["ticker"] != "6286"]
    print(f"\n[更新財報] 執行 update_financials.py for {', '.join(tickers)}...")
    script = os.path.join(os.path.dirname(__file__), "update_financials.py")
    result = subprocess.run(
        [sys.executable, script] + tickers,
        capture_output=True, text=True
    )
    print(result.stdout[-2000:] if result.stdout else "(no output)")
    if result.returncode != 0:
        print(f"[WARN] {result.stderr[:500]}")
    print("[NOTE] 6286 力成: 請手動確認 (yfinance 用 IMOS ticker)")


def print_earnings_calendar():
    """顯示財報行事曆"""
    today = date.today()
    season = get_current_earnings_season()
    print("\n━━━ 財報行事曆 ━━━")
    if season:
        print(f"  ⚡ 現在是 {season} 財報季！")
    for s, months in EARNINGS_MONTHS.items():
        months_str = "/".join(f"{m}月" for m in months)
        marker = " ← 現在" if season == s else ""
        print(f"  {s:<8} 公布時間：{months_str}{marker}")
    print(f"\n  月營收公告：每月10日前（下次: {today.replace(day=10) if today.day < 10 else today.replace(month=today.month%12+1, day=10)}）")


def main():
    update = "--update" in sys.argv
    quick  = "--quick" in sys.argv

    print("=" * 65)
    print("  FOPLP 供應鏈監控")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 65)

    if update:
        update_financials()

    print("\n━━━ 最新市場快照 ━━━")
    df = fetch_snapshot()
    print(df.to_string(index=False))

    print_monthly_revenue_table()

    if not quick:
        print("\n━━━ 季度營收趨勢（yfinance）━━━")
        for co in WATCHLIST:
            rev = fetch_revenue_trend(co["yf_sym"])
            if rev is not None:
                print(f"\n  {co['ticker']} {co['name']} (單位: NTD/USD)")
                for dt, val in rev.items():
                    bar = "█" * min(int(abs(val) / 1e9), 30) if val else ""
                    print(f"    {str(dt)[:7]}  {val/1e9:8.2f}B  {bar}")
            else:
                print(f"\n  {co['ticker']} {co['name']}: 無法取得季度資料")

    print_earnings_calendar()

    print("\n━━━ 下一步佈局觀察重點 ━━━")
    print("  1. 群創 RDL-first 客戶驗證進度（目標 2026）")
    print("  2. 日月光 K28 FOPLP 產線設備進場時間")
    print("  3. 群翊楊梅二廠動工/完工里程碑")
    print("  4. TGV 雷射設備台灣供應商公告")
    print("  5. TSMC FOPLP pilot line 進度（2026 CoPoS）")
    print()


if __name__ == "__main__":
    main()
