"""sf_pairs_weekly 純函式測試 — 配對/價位/追蹤 (plan 2026-08-28-sf-pairs-weekly)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sf_pairs_weekly as sf  # noqa: E402


# ---------------------------------------------------------------- build_pairs
def _cand(sym, ind, score):
    return {"symbol": sym, "industry": ind, "score": score}


def test_build_pairs_prefers_same_industry():
    longs = [_cand("2330", "半導體", 3.0), _cand("2603", "航運", 2.0)]
    shorts = [_cand("2303", "半導體", -3.0), _cand("2609", "航運", -2.0)]
    pairs = sf.build_pairs(longs, shorts, max_pairs=5)
    got = {(p["long"]["symbol"], p["short"]["symbol"], p["kind"]) for p in pairs}
    assert ("2330", "2303", "同鏈對偶") in got
    assert ("2603", "2609", "同鏈對偶") in got


def test_build_pairs_falls_back_to_cross_industry():
    longs = [_cand("2330", "半導體", 3.0)]
    shorts = [_cand("2609", "航運", -2.0)]
    pairs = sf.build_pairs(longs, shorts, max_pairs=5)
    assert len(pairs) == 1
    assert pairs[0]["kind"] == "跨產業β"


def test_build_pairs_industry_diversity_cap():
    # 同一產業最多 2 組
    longs = [_cand(f"1{i:03d}", "半導體", 5 - i) for i in range(4)]
    shorts = [_cand(f"2{i:03d}", "半導體", -5 + i) for i in range(4)]
    pairs = sf.build_pairs(longs, shorts, max_pairs=5)
    semi = [p for p in pairs if p["long"]["industry"] == "半導體"
            and p["short"]["industry"] == "半導體"]
    assert len(semi) <= 2


# ---------------------------------------------------------------- levels
def test_leg_levels_long_and_short_mirror():
    lv = sf.leg_levels(close=100.0, atr=4.0, side="long")
    assert lv == {"entry": 100.0, "stop": 94.0, "tp": 110.0}
    sv = sf.leg_levels(close=100.0, atr=4.0, side="short")
    assert sv == {"entry": 100.0, "stop": 106.0, "tp": 90.0}


# ---------------------------------------------------------------- tracking
def _pair(pid="P1", enter="2026-08-21"):
    return {"id": pid, "enter_date": enter, "kind": "同鏈對偶",
            "long": {"symbol": "2330", "entry": 100.0, "stop": 94.0, "tp": 110.0},
            "short": {"symbol": "2303", "entry": 50.0, "stop": 53.0, "tp": 45.0}}


def test_evaluate_pair_stop_hit_on_long_leg():
    closes = {"2330": 93.0, "2303": 50.0}   # 多腿收盤破停損
    st = sf.evaluate_pair(_pair(), closes, trading_days_held=3)
    assert st["status"] == "stopped"
    # spread = long 報酬 + 空腿反向報酬
    assert abs(st["spread_ret"] - (-7.0 + 0.0)) < 1e-9


def test_evaluate_pair_tp_via_spread():
    closes = {"2330": 106.0, "2303": 47.0}  # +6% & 空腿 +6% → spread +12% ≥ +8%
    st = sf.evaluate_pair(_pair(), closes, trading_days_held=3)
    assert st["status"] == "tp"


def test_evaluate_pair_expiry_after_20d():
    closes = {"2330": 101.0, "2303": 49.5}
    st = sf.evaluate_pair(_pair(), closes, trading_days_held=20)
    assert st["status"] == "expired"
    st2 = sf.evaluate_pair(_pair(), closes, trading_days_held=19)
    assert st2["status"] == "active"
