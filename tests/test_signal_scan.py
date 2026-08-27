"""signal_scan 純函式測試 — 名單追蹤 dedup / 畢業語意 (plan 2026-08-28 Phase C)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import signal_scan as ss  # noqa: E402


def _close_fn(px):
    return lambda sym, d: px.get(sym)


def _nth_fn(table):
    return lambda sym, enter, n: table.get((sym, n))


def test_update_tracking_enters_new_symbols():
    state = {"tracked": {}}
    listed = {"S2v2_cap": [("2330", "融資-12% volr3.1")]}
    ss.update_tracking(state, listed, "2026-08-28", _close_fn({"2330": 1000.0}), _nth_fn({}))
    key = "S2v2_cap:2330:2026-08-28"
    assert key in state["tracked"]
    e = state["tracked"][key]
    assert e["enter_close"] == 1000.0
    assert e["post"] == {"t5": None, "t20": None}


def test_update_tracking_dedup_10d_same_family():
    state = {"tracked": {"S2v2_cap:2330:2026-08-25": {
        "family": "S2v2_cap", "symbol": "2330", "enter_date": "2026-08-25",
        "enter_close": 990.0, "post": {"t5": None, "t20": None}}}}
    listed = {"S2v2_cap": [("2330", "again")]}
    ss.update_tracking(state, listed, "2026-08-28", _close_fn({"2330": 1000.0}), _nth_fn({}))
    assert len(state["tracked"]) == 1          # 10 日內同 family:symbol 不重複進場
    # 不同 family 不受 dedup 影響
    listed2 = {"S1_disp": [("2330", "解除")]}
    ss.update_tracking(state, listed2, "2026-08-28", _close_fn({"2330": 1000.0}), _nth_fn({}))
    assert "S1_disp:2330:2026-08-28" in state["tracked"]


def test_update_tracking_fills_t5_then_graduates_on_t20():
    e = {"family": "S2v2_cap", "symbol": "2330", "enter_date": "2026-08-01",
         "enter_close": 1000.0, "post": {"t5": None, "t20": None}}
    state = {"tracked": {"S2v2_cap:2330:2026-08-01": dict(e, post=dict(e["post"]))}}
    # 只有 t5 有價 → 填 t5、不畢業
    grads = ss.update_tracking(state, {}, "2026-08-28",
                               _close_fn({}), _nth_fn({("2330", 5): 1050.0}))
    assert grads == []
    assert state["tracked"]["S2v2_cap:2330:2026-08-01"]["post"]["t5"] == 5.0
    # t20 也有價 → 畢業並移出 state
    grads = ss.update_tracking(state, {}, "2026-08-28",
                               _close_fn({}), _nth_fn({("2330", 5): 1050.0, ("2330", 20): 900.0}))
    assert len(grads) == 1
    assert grads[0]["post"]["t20"] == -10.0
    assert state["tracked"] == {}


def test_update_tracking_skips_symbols_without_close():
    state = {"tracked": {}}
    listed = {"S2v2_thin": [("9999", "no px")]}
    ss.update_tracking(state, listed, "2026-08-28", _close_fn({}), _nth_fn({}))
    assert state["tracked"] == {}              # 無收盤價不進追蹤
