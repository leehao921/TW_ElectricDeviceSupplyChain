"""div_buy 純函式測試 — 00406A 除息日半自動買入 (2026-09-30)"""
import sys
from datetime import date, time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import div_buy as db  # noqa: E402

CFG = {"enabled": True, "max_lots": 2, "items": [{"ticker": "00406A", "lots": 1}]}
ROWS = [
    {"Date": "1151005", "Code": "00406A", "Name": "主動中信台灣收益", "Exdividend": "息", "CashDividend": ""},
    {"Date": "1151008", "Code": "00400A", "Name": "主動國泰動能高息", "Exdividend": "息", "CashDividend": "0.08"},
    {"Date": "1151105", "Code": "00406A", "Name": "主動中信台灣收益", "Exdividend": "息", "CashDividend": "0.05"},
]
TODAY = date(2026, 10, 5)


# --- 解析 ---

def test_parse_roc_date():
    assert db.parse_roc_date("1151005") == date(2026, 10, 5)
    assert db.parse_roc_date("1150101") == date(2026, 1, 1)


def test_find_ex_events_filters_ticker_and_parses_dividend():
    ev = db.find_ex_events(ROWS, "00406A")
    assert ev == [(date(2026, 10, 5), None), (date(2026, 11, 5), 0.05)]  # 未公布配息 → None


def test_find_ex_events_ignores_rights_only():
    rows = [{"Date": "1151005", "Code": "00406A", "Exdividend": "權", "CashDividend": ""}]
    assert db.find_ex_events(rows, "00406A") == []


# --- token ---

def test_token_roundtrip():
    tok = db.make_token("00406A", date(2026, 10, 5))
    assert tok == "00406A-20261005"
    assert db.parse_token(tok) == ("00406A", date(2026, 10, 5))


def test_parse_token_rejects_garbage():
    with pytest.raises(ValueError):
        db.parse_token("00406A")
    with pytest.raises(ValueError):
        db.parse_token("00406A-2026105")


# --- 參考價 ---

def test_tick_size_etf():
    assert db.tick_size(9.85) == 0.01
    assert db.tick_size(111.3) == 0.05


def test_estimate_ref_price():
    assert db.estimate_ref(9.85, 0.05) == pytest.approx(9.80)
    assert db.estimate_ref(9.85, None) is None


def test_ref_sane_requires_below_prev_close():
    assert db.ref_sane(9.80, prev_close=9.85, cash_div=None) is True
    assert db.ref_sane(9.85, prev_close=9.85, cash_div=None) is False  # 合約檔未更新除息
    assert db.ref_sane(9.90, prev_close=9.85, cash_div=None) is False


def test_ref_sane_within_one_tick_of_estimate():
    assert db.ref_sane(9.80, prev_close=9.85, cash_div=0.05) is True
    assert db.ref_sane(9.81, prev_close=9.85, cash_div=0.05) is True   # 1 tick 容忍
    assert db.ref_sane(9.70, prev_close=9.85, cash_div=0.05) is False  # 偏離過大


def test_ref_sane_without_prev_close_fails_closed():
    assert db.ref_sane(9.80, prev_close=None, cash_div=None) is False


# --- confirm guards ---

def _guards(**kw):
    args = dict(token="00406A-20261005", today=TODAY, now=time(9, 0), config=CFG,
                state={}, ex_events=[(TODAY, None)])
    args.update(kw)
    return db.confirm_guards(**args)


def test_guards_clean():
    assert _guards() == []


def test_guards_reject_wrong_day():
    assert any("今天" in e for e in _guards(today=date(2026, 10, 2)))


def test_guards_reject_unknown_ticker():
    errs = _guards(token="0050-20261005")
    assert any("config" in e for e in errs)


def test_guards_reject_disabled():
    assert any("enabled" in e for e in _guards(config={**CFG, "enabled": False}))


def test_guards_reject_duplicate():
    state = {"orders": {"00406A-20261005": {"status": "placed"}}}
    assert any("已下過" in e for e in _guards(state=state))


def test_guards_allow_retry_after_failed_attempt():
    state = {"orders": {"00406A-20261005": {"status": "failed"}}}
    assert _guards(state=state) == []


def test_guards_reject_outside_session():
    assert any("時段" in e for e in _guards(now=time(8, 10)))
    assert any("時段" in e for e in _guards(now=time(13, 30)))


def test_guards_reject_not_ex_date_per_twse():
    assert any("TWT48U" in e for e in _guards(ex_events=[(date(2026, 11, 5), None)]))


def test_guards_reject_lots_over_cap():
    cfg = {**CFG, "items": [{"ticker": "00406A", "lots": 3}]}
    assert any("max_lots" in e for e in _guards(config=cfg))


# --- check 訊息分流 ---

def test_check_plan_today_and_preview():
    state = {}
    msgs = db.check_plan(date(2026, 10, 1), CFG, {"00406A": [(date(2026, 10, 5), None)]}, state)
    assert [m["kind"] for m in msgs] == ["preview"]
    assert msgs[0]["token"] == "00406A-20261005"
    # 同一 token 只預告一次
    again = db.check_plan(date(2026, 10, 2), CFG, {"00406A": [(date(2026, 10, 5), None)]}, state)
    assert again == []
    today = db.check_plan(date(2026, 10, 5), CFG, {"00406A": [(date(2026, 10, 5), None)]}, state)
    assert [m["kind"] for m in today] == ["today"]


def test_check_plan_ignores_far_future_and_past():
    ev = {"00406A": [(date(2026, 11, 5), None), (date(2026, 9, 1), None)]}
    assert db.check_plan(date(2026, 10, 5), CFG, ev, {}) == []


def test_check_plan_disabled_is_silent():
    ev = {"00406A": [(date(2026, 10, 5), None)]}
    assert db.check_plan(date(2026, 10, 5), {**CFG, "enabled": False}, ev, {}) == []


# --- 下單參數 (fake api) ---

class _Const:
    class Action: Buy = "Buy"
    class StockPriceType: LMT = "LMT"
    class OrderType: ROD = "ROD"
    class StockOrderLot: Common = "Common"
    class StockOrderCond: Cash = "Cash"


class FakeApi:
    stock_account = "ACCT"

    def __init__(self):
        self.placed = None

    def Order(self, **kw):
        return kw

    def place_order(self, contract, order):
        self.placed = (contract, order)
        return "TRADE"


def test_submit_order_builds_limit_rod_cash_common():
    api = FakeApi()
    trade = db.submit_order(api, _Const, contract="C", price=9.80, lots=1)
    assert trade == "TRADE"
    contract, order = api.placed
    assert contract == "C"
    assert order == dict(price=9.80, quantity=1, action="Buy", price_type="LMT",
                         order_type="ROD", order_lot="Common", order_cond="Cash",
                         account="ACCT")
