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


# ---------------------------------------------------------------- cross flags
def test_format_flags_merges_module_tags():
    flags = sf.format_flags("2330", warrant_long={"2330"}, warrant_short=set(),
                            scan_families={"2330": ["S2v2_cap"]},
                            pb_lights={"2330": "RED"})
    assert "權證佈多" in flags and "S2v2_cap" in flags and "P/B:RED" in flags


def test_format_flags_empty_when_no_hits():
    assert sf.format_flags("9999", warrant_long=set(), warrant_short=set(),
                           scan_families={}, pb_lights={}) == ""


# ---------------------------------------------------------------- options env
def test_options_env_lines_vrp_guidance():
    # VRP 薄/負 → 保險便宜, 建議 put 對沖優先於期貨蓋板
    row = {"vix": 24.6, "vix_30d": 27.3, "rv_21d": 24.7, "vrp_30d": 2.7,
           "vix_w": 23.7, "wm_spread": -3.7, "iv_skew_25d": -1.2, "term_slope": 0.5}
    lines = sf.options_env_lines(row)
    txt = "\n".join(lines)
    assert "27.3" in txt and "VRP" in txt
    thin = sf.options_env_lines({**row, "vrp_30d": -4.0})
    assert any("保險便宜" in ln for ln in thin)


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
