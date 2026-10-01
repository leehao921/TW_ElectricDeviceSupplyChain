"""產業全景 treemap 彙總 — 2026-09-30 (docs/plans/2026-09-30-sector-treemap.md)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sector_treemap as st  # noqa: E402


def _q(code, ind, prev, close, shares, value=1_000):
    return {"code": code, "name": f"n{code}", "industry_code": ind, "prev_close": prev,
            "close": close, "change": close - prev, "shares": shares, "trade_value": value}


# market cap (prev): A 1000×100=100k, B 500×100=50k, C 200×100=20k, D 300×100=30k → W=200k
ROWS = [
    _q("A", "24", 100, 102, 1000, value=900),   # +2%
    _q("B", "24", 100, 99, 500, value=300),     # -1%
    _q("C", "24", 100, 105, 200, value=50),     # +5%
    _q("D", "17", 100, 101, 300, value=200),    # +1%
]
INDEX = {"IX": {"close": 20100.0, "change_pts": 100.0, "change_pct": 0.5},
         "24": {"close": 1012.0, "change_pts": 12.0, "change_pct": 1.2}}


def test_contribution_points_and_market_residual():
    m = st.build_market(ROWS, INDEX, top_n=2)
    # prev index 20000; contrib_i = shares·Δ / W · 20000
    semi = {s["code"]: s for s in m["sectors"]}["24"]
    a = {x["code"]: x for x in semi["members"]}["A"]
    assert a["contrib_pts"] == pytest.approx(1000 * 2 / 200_000 * 20000)       # 200
    total = sum(s["contrib_pts"] for s in m["sectors"])
    assert total == pytest.approx((2000 - 500 + 1000 + 300) / 200_000 * 20000)  # 280
    assert m["index"]["chg_pts"] == 100.0
    assert m["residual_pts"] == pytest.approx(total - 100.0)


def test_sector_weighted_return_trade_value_and_official():
    semi = {s["code"]: s for s in st.build_market(ROWS, INDEX, top_n=2)["sectors"]}["24"]
    assert semi["wret"] == pytest.approx((2000 - 500 + 1000) / 170_000 * 100)
    assert semi["trade_value"] == 1250
    assert semi["official_ret"] == 1.2
    assert semi["name"] == "半導體業"


def test_other_members_backed_out_from_official_index():
    semi = {s["code"]: s for s in st.build_market(ROWS, INDEX, top_n=2)["sectors"]}["24"]
    oth = semi["other"]["contrib"]          # top 2 by |contrib|: A (200), C (100) → other = B (-50)
    assert oth["codes"] == ["B"] and oth["ret_method"] == "official_backout"
    # (1.2%·170k − (2%·100k + 5%·20k)) / 50k
    assert oth["ret"] == pytest.approx((0.012 * 170_000 - (2000 + 1000)) / 50_000 * 100)
    # plugging it back reproduces the official sector return
    wsum = 2000 + 1000 + oth["ret"] / 100 * 50_000
    assert wsum / 170_000 * 100 == pytest.approx(1.2)


def test_other_ranked_by_trade_value_is_separate():
    semi = {s["code"]: s for s in st.build_market(ROWS, INDEX, top_n=2)["sectors"]}["24"]
    assert semi["other"]["value"]["codes"] == ["C"]          # A 900, B 300 top by value
    assert [m["code"] for m in semi["members"]][:1] == ["A"]


def test_other_falls_back_to_members_without_official_index():
    rows = ROWS + [_q("E", "17", 100, 97, 100)]
    fin = {s["code"]: s for s in st.build_market(rows, INDEX, top_n=1)["sectors"]}["17"]
    oth = fin["other"]["contrib"]
    assert oth["ret_method"] == "members" and oth["codes"] == ["E"]
    assert oth["ret"] == pytest.approx(-3.0)


def test_no_other_when_sector_fits_in_top_n():
    fin = {s["code"]: s for s in st.build_market(ROWS, INDEX, top_n=5)["sectors"]}["17"]
    assert fin["other"]["contrib"] is None


def test_tdr_and_missing_shares_excluded_from_index_weight():
    rows = ROWS + [_q("9110", "91", 10, 11, 10_000_000), _q("X", "24", 100, 150, None)]
    m = st.build_market(rows, INDEX, top_n=2)
    assert "91" not in {s["code"] for s in m["sectors"]}
    semi = {s["code"]: s for s in m["sectors"]}["24"]
    assert "X" not in {x["code"] for x in semi["members"]}
    assert m["excluded"] == {"tdr": 1, "no_shares": 1}


def test_official_return_uses_index_points_not_rounded_pct():
    # 塑膠 9/30: other = 1% of sector weight → the 2-dp rounded % is amplified ~100×.
    # 415.31 close, +14.57 pts → 3.6343…%, published as 3.64
    idx = {**INDEX, "24": {"close": 415.31, "change_pts": 14.57, "change_pct": 3.64}}
    semi = {s["code"]: s for s in st.build_market(ROWS, idx, top_n=2)["sectors"]}["24"]
    assert semi["official_ret"] == pytest.approx(14.57 / (415.31 - 14.57) * 100)


# ── 15:35 routine: standalone page + inbox summary (headless claude has no Artifact tool) ──

def test_standalone_embeds_data_and_skeleton():
    page = "<title>台股產業全景</title><script>fetch('data.json')</script>"
    html = st.render_standalone(page, {"date": "2026-09-30", "markets": {}})
    assert html.startswith("<!doctype html>") and '<meta charset="utf-8">' in html
    assert 'window.__SECTOR_DATA__={"date":"2026-09-30"' in html
    assert html.index("__SECTOR_DATA__") < html.index("fetch(")     # data defined before page script


def test_standalone_escapes_script_close_in_names():
    html = st.render_standalone("<p></p>", {"date": "d", "markets": {"x": "</script><b>"}})
    assert "</script><b>" not in html


def test_summary_line_top_sectors_by_contribution():
    m = st.build_market(ROWS, INDEX, top_n=2)
    line = st.summary_line({"date": "2026-09-30", "markets": {"TWSE": m}})
    assert line.startswith("2026-09-30 加權 +100.00 點")
    assert "半導體業 +" in line and "主力 nA" in line
