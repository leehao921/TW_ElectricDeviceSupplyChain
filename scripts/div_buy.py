#!/usr/bin/env python3
"""除息日半自動買入 — 00406A 等月配 ETF 在除息日以除息參考價買入 (2026-09-30)

用戶決策: 半自動 (推播 + 用戶一行指令確認才送單)、固定張數、限價 = 除息參考價 ROD。
  check    launchd com.lulala.div-buy Mon-Fri 08:20 — TWT48U 找除息日, 今天/預告推 inbox topic=div-buy
  confirm  用戶手動: div_buy.py confirm 00406A-20261005 [--dry-run]
股票專用 API key 在 ~/.config/shioaji/stock.env (0600); CA 沿用 nautilus .env (同身分證)。
計畫: docs/plans/2026-09-30-div-buy-00406a.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time as _time
from datetime import date, datetime, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO / "data" / "div_buy_config.json"
STATE_PATH = REPO / "data" / "div_buy_state.json"
STOCK_ENV = Path.home() / ".config" / "shioaji" / "stock.env"
NAUTILUS_ENV = Path.home() / "Documents" / "coding" / "nautilus-shioaji" / ".env"
TWT48U_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL"
DB = dict(host="localhost", port=5432, dbname="tmf_market_data",
          user="tmf", password="tmf_dev_2026")
SESSION_OPEN, SESSION_CLOSE = time(8, 30), time(13, 25)  # 盤前委託 08:30 起; 13:25 前留收盤撮合
PREVIEW_DAYS = 4  # 週五要能預告下週一


# ---------- 純函式 ----------

def parse_roc_date(s: str) -> date:
    """TWT48U 民國日期 '1151005' → date(2026, 10, 5)."""
    s = s.strip()
    return date(int(s[:-4]) + 1911, int(s[-4:-2]), int(s[-2:]))


def find_ex_events(rows: list[dict], ticker: str) -> list[tuple[date, float | None]]:
    """抽出標的的除息事件 [(除息日, 每股現金股利 or None 未公布)], 依日期排序."""
    out = []
    for r in rows:
        if r.get("Code") != ticker or "息" not in (r.get("Exdividend") or ""):
            continue
        raw = (r.get("CashDividend") or "").strip()
        out.append((parse_roc_date(r["Date"]), float(raw) if raw else None))
    return sorted(out)


def make_token(ticker: str, d: date) -> str:
    return f"{ticker}-{d:%Y%m%d}"


def parse_token(tok: str) -> tuple[str, date]:
    m = re.fullmatch(r"([0-9A-Z]+)-(\d{8})", tok)
    if not m:
        raise ValueError(f"token 格式錯誤: {tok!r} (應為 00406A-20261005)")
    return m.group(1), datetime.strptime(m.group(2), "%Y%m%d").date()


def tick_size(price: float) -> float:
    """TWSE ETF 升降單位: 未滿 50 元 0.01, 50 元以上 0.05."""
    return 0.01 if price < 50 else 0.05


def estimate_ref(prev_close: float, cash_div: float | None) -> float | None:
    if cash_div is None:
        return None
    raw = prev_close - cash_div
    tick = tick_size(raw)
    return round(round(raw / tick) * tick, 2)


def ref_sane(ref: float, prev_close: float | None, cash_div: float | None) -> bool:
    """參考價必須已反映除息: < 前日收盤; 配息已公布時與估算差 ≤ 1 tick. 缺前收 → fail closed."""
    if prev_close is None or ref >= prev_close:
        return False
    est = estimate_ref(prev_close, cash_div)
    return est is None or abs(ref - est) <= tick_size(ref) + 1e-9


def _item(config: dict, ticker: str) -> dict | None:
    return next((i for i in config.get("items", []) if i["ticker"] == ticker), None)


def confirm_guards(token: str, today: date, now: time, config: dict, state: dict,
                   ex_events: list[tuple[date, float | None]]) -> list[str]:
    """下單前所有擋點 (登入前檢查). 回傳錯誤清單, [] = 可下單."""
    try:
        ticker, d = parse_token(token)
    except ValueError as e:
        return [str(e)]
    errs = []
    if d != today:
        errs.append(f"token 日期 {d} 不是今天 {today}")
    if not config.get("enabled"):
        errs.append("config enabled=false (kill switch)")
    item = _item(config, ticker)
    if item is None:
        errs.append(f"{ticker} 不在 config items")
    elif item["lots"] > config.get("max_lots", 1):
        errs.append(f"lots {item['lots']} 超過 max_lots {config.get('max_lots', 1)}")
    if today not in [e[0] for e in ex_events]:
        errs.append(f"TWT48U 未列 {ticker} 於 {today} 除息")
    if state.get("orders", {}).get(token, {}).get("status") == "placed":
        errs.append(f"{token} 已下過單 (冪等擋)")
    if not (SESSION_OPEN <= now <= SESSION_CLOSE):
        errs.append(f"不在下單時段 {SESSION_OPEN:%H:%M}–{SESSION_CLOSE:%H:%M}")
    return errs


def check_plan(today: date, config: dict, events: dict[str, list], state: dict) -> list[dict]:
    """決定要推哪些訊息: 今天除息 → today; 1–PREVIEW_DAYS 天內 → preview (每 token 一次)."""
    if not config.get("enabled"):
        return []
    previewed = state.setdefault("previewed", [])
    msgs = []
    for item in config.get("items", []):
        for d, div in events.get(item["ticker"], []):
            tok = make_token(item["ticker"], d)
            gap = (d - today).days
            if gap == 0:
                msgs.append({"kind": "today", "token": tok, "ticker": item["ticker"],
                             "date": d, "cash_div": div, "lots": item["lots"]})
            elif 0 < gap <= PREVIEW_DAYS and tok not in previewed:
                previewed.append(tok)
                msgs.append({"kind": "preview", "token": tok, "ticker": item["ticker"],
                             "date": d, "cash_div": div, "lots": item["lots"]})
    return msgs


def submit_order(api, const, contract, price: float, lots: int):
    """現股整股限價 ROD 買進."""
    order = api.Order(
        price=price, quantity=lots,
        action=const.Action.Buy,
        price_type=const.StockPriceType.LMT,
        order_type=const.OrderType.ROD,
        order_lot=const.StockOrderLot.Common,
        order_cond=const.StockOrderCond.Cash,
        account=api.stock_account,
    )
    return api.place_order(contract, order)


# ---------- I/O ----------

def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def fetch_twt48u() -> list[dict]:
    import requests
    r = requests.get(TWT48U_URL, timeout=20)
    r.raise_for_status()
    return r.json()


def prev_close(ticker: str, before: date) -> float | None:
    import psycopg2
    with psycopg2.connect(**DB) as conn, conn.cursor() as cur:
        cur.execute("SELECT close_price FROM institutional_stock WHERE symbol=%s "
                    "AND date < %s AND close_price > 0 ORDER BY date DESC LIMIT 1",
                    (ticker, before))
        row = cur.fetchone()
    return float(row[0]) if row else None


def push_inbox(msg: str, as_of: str, tags: str) -> None:
    print(msg)
    try:
        import redis
        redis.Redis().xadd("claude:inbox", {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from": "div_buy", "topic": "div-buy", "tags": tags,
            "as_of": as_of, "msg": msg})
    except Exception as e:
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)


def login_stock():
    """股票 key 登入 + 啟用 CA. 同身分證 5 連線上限 (daemon 佔 4) → 451 backoff."""
    import shioaji as sj
    from dotenv import dotenv_values
    keys = dotenv_values(STOCK_ENV)
    ca = {**dotenv_values(NAUTILUS_ENV), **keys}
    api = sj.Shioaji(simulation=False)
    for attempt in range(1, 5):
        try:
            api.login(api_key=keys["SHIOAJI_STOCK_API_KEY"],
                      secret_key=keys["SHIOAJI_STOCK_SECRET_KEY"])
            break
        except Exception as e:  # noqa: BLE001
            if "451" not in str(e) or attempt == 4:
                raise
            print(f"[login] 451 too many connections, retry {attempt}/3 in 20s", file=sys.stderr)
            _time.sleep(20)
    if api.stock_account is None or not getattr(api.stock_account, "signed", False):
        api.logout()
        raise RuntimeError("股票帳戶不存在或未簽署 (stock_account signed=False)")
    api.activate_ca(ca_path=str(ca["CA_CERT_PATH"]), ca_passwd=ca["CA_PASSWORD"])
    return api, sj.constant


def cmd_check() -> int:
    today = date.today()
    config = _load_json(CONFIG_PATH, {})
    state = _load_json(STATE_PATH, {})
    rows = fetch_twt48u()
    events = {i["ticker"]: find_ex_events(rows, i["ticker"]) for i in config.get("items", [])}
    msgs = check_plan(today, config, events, state)
    _save_json(STATE_PATH, state)
    for m in msgs:
        div = f"每股配息 {m['cash_div']}" if m["cash_div"] is not None else "配息金額未公布"
        pc = prev_close(m["ticker"], m["date"])
        est = estimate_ref(pc, m["cash_div"]) if pc else None
        est_s = f"估算除息參考價 {est}" if est else "參考價待開盤前確認"
        cmd = f"cd {REPO} && .venv/bin/python scripts/div_buy.py confirm {m['token']}"
        if m["kind"] == "today":
            msg = (f"🟢 今天 {m['ticker']} 除息 — 買入 {m['lots']} 張待你確認\n"
                   f"{div} · 前收 {pc} · {est_s}\n"
                   f"限價 = Shioaji 除息參考價, ROD (08:30–13:25 確認)\n"
                   f"確認指令: {cmd}\n先演練: 加 --dry-run")
            push_inbox(msg, str(today), "div-buy,today")
        else:
            msg = (f"📅 預告: {m['ticker']} {m['date']:%m/%d} ({m['date']:%a}) 除息, 計畫買 {m['lots']} 張\n"
                   f"{div} · 當天 08:20 會再推確認指令")
            push_inbox(msg, str(today), "div-buy,preview")
    if not msgs:
        print(f"div_buy check {today}: 無事件")
    return 0


def cmd_confirm(token: str, dry_run: bool) -> int:
    now = datetime.now()
    config = _load_json(CONFIG_PATH, {})
    state = _load_json(STATE_PATH, {})
    ticker, _ = parse_token(token) if re.fullmatch(r"[0-9A-Z]+-\d{8}", token) else (token, None)
    ex_events = find_ex_events(fetch_twt48u(), ticker)
    errs = confirm_guards(token, now.date(), now.time(), config, state, ex_events)
    if errs:
        print("❌ 不下單:\n  " + "\n  ".join(errs))
        return 2
    item = _item(config, ticker)
    cash_div = dict(ex_events).get(now.date())
    pc = prev_close(ticker, now.date())
    api, const = login_stock()
    try:
        contract = api.Contracts.Stocks[ticker]
        ref = float(contract.reference)
        if not ref_sane(ref, pc, cash_div):
            msg = (f"❌ {token} 中止: 參考價 {ref} 未通過除息檢查 (前收 {pc}, 配息 {cash_div}) "
                   f"— 合約檔可能尚未更新, 稍後再試")
            push_inbox(msg, str(now.date()), "div-buy,aborted")
            return 3
        if dry_run:
            print(f"[dry-run] 會下單: 買 {ticker} {item['lots']} 張 @ {ref} LMT ROD 現股 "
                  f"(前收 {pc}, 配息 {cash_div})")
            return 0
        rec = {"ts": now.isoformat(timespec="seconds"), "price": ref, "lots": item["lots"]}
        try:
            trade = submit_order(api, const, contract, ref, item["lots"])
            api.update_status(api.stock_account)
            rec.update(status="placed", order_id=trade.order.id, seqno=trade.order.seqno,
                       broker_status=str(trade.status.status))
            ok = "Failed" not in rec["broker_status"]
            if not ok:
                rec["status"] = "failed"
                rec["msg"] = getattr(trade.status, "msg", "")
        except Exception as e:  # noqa: BLE001
            rec.update(status="failed", error=str(e))
            ok = False
        state.setdefault("orders", {})[token] = rec
        _save_json(STATE_PATH, state)
        if ok:
            msg = (f"✅ {ticker} 除息日買單已送出: {item['lots']} 張 @ {ref} ROD "
                   f"(委託書 {rec.get('seqno')}, 狀態 {rec['broker_status']})")
        else:
            msg = f"🚨 {ticker} 除息日買單失敗: {rec.get('error') or rec.get('msg')} ({rec.get('broker_status', '')})"
        push_inbox(msg, str(now.date()), "div-buy," + ("placed" if ok else "failed"))
        return 0 if ok else 4
    finally:
        api.logout()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    c = sub.add_parser("confirm")
    c.add_argument("token")
    c.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return cmd_check() if a.cmd == "check" else cmd_confirm(a.token, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
