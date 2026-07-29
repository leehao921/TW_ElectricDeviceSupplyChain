# -*- coding: utf-8 -*-
"""Tests for scripts/news_pulse.py — Phase 2 新聞標註 + 族群同步 (pure layers only)."""
import datetime as dt
import importlib.util
import sys
from pathlib import Path

_MOD = Path(__file__).resolve().parents[1] / "scripts" / "news_pulse.py"
_spec = importlib.util.spec_from_file_location("news_pulse", _MOD)
np_ = importlib.util.module_from_spec(_spec)
sys.modules["news_pulse"] = np_
_spec.loader.exec_module(np_)


# ------------------------------------------------------------------ #
# entity maps from Pilot_Reports fixtures
# ------------------------------------------------------------------ #
def _mk_reports(tmp_path):
    d = tmp_path / "Semiconductors"
    d.mkdir(parents=True)
    (d / "2330_台積電.md").write_text(
        "# 2330 - [[台積電]]\n晶圓代工 [[CoWoS]] 與 [[矽光子]] 佈局\n", encoding="utf-8")
    (d / "3017_奇鋐.md").write_text(
        "# 3017 - [[奇鋐]]\n[[AI 伺服器]] 散熱 [[液冷]]\n", encoding="utf-8")
    (d / "2455_全新.md").write_text(
        "# 2455 - [[全新]]\n[[磊晶]] 供應 [[VCSEL]]\n", encoding="utf-8")
    return tmp_path


class TestEntityMaps:
    def test_ticker_names_from_filenames(self, tmp_path):
        m = np_.build_ticker_names(_mk_reports(tmp_path))
        assert m["台積電"] == "2330"
        assert m["奇鋐"] == "3017"
        assert m["全新"] == "2455"

    def test_ticker_themes_and_reverse(self, tmp_path):
        t2th, th2t = np_.build_ticker_themes(_mk_reports(tmp_path))
        assert "CoWoS" in t2th["2330"]
        # 公司自己的名字不算 theme
        assert "台積電" not in t2th["2330"]
        assert th2t["AI 伺服器"] == {"3017"}


# ------------------------------------------------------------------ #
# ticker extraction — 2-char title-only + blocklist, >=3-char full text
# ------------------------------------------------------------------ #
_NAMES = {"台積電": "2330", "奇鋐": "3017", "全新": "2455", "研華": "2395"}


class TestExtractTickers:
    def test_3char_name_matches_in_body(self):
        got = np_.extract_tickers("盤後速報", "台積電緊急疏散人員", _NAMES)
        assert got == {"2330"}

    def test_2char_name_title_only(self):
        assert np_.extract_tickers("研華法說會", "", _NAMES) == {"2395"}
        # 2 字名只在內文出現 → 不匹配
        assert np_.extract_tickers("盤後盤點", "研華與台達電", _NAMES) == set()

    def test_blocklisted_ambiguous_name_never_matches(self):
        # 「全新」是常用詞 — 即使在標題也不匹配
        assert np_.extract_tickers("全新產線啟用", "", _NAMES) == set()

    def test_multiple(self):
        got = np_.extract_tickers("台積電、奇鋐同創高", "", _NAMES)
        assert got == {"2330", "3017"}


# ------------------------------------------------------------------ #
# theme extraction — ASCII boundary rule
# ------------------------------------------------------------------ #
_ENTITIES = {"CoWoS", "液冷", "AI 伺服器", "AI", "HBM"}


class TestExtractThemes:
    def test_chinese_substring(self):
        got = np_.extract_themes("液冷進入下一階段", "", _ENTITIES)
        assert "液冷" in got

    def test_ascii_needs_boundary(self):
        # "FAIRCHILD" 不可誤中 "AI"
        assert "AI" not in np_.extract_themes("FAIRCHILD 出貨", "", _ENTITIES)
        assert "AI" in np_.extract_themes("AI 需求強勁", "", _ENTITIES)
        assert "HBM" in np_.extract_themes("HBM4 認證通過", "", _ENTITIES)

    def test_mixed(self):
        got = np_.extract_themes("CoWoS 產能與液冷需求", "", _ENTITIES)
        assert {"CoWoS", "液冷"} <= got


# ------------------------------------------------------------------ #
# tagging — MOPS ticker passthrough
# ------------------------------------------------------------------ #
class TestTagItems:
    def test_mops_keeps_own_ticker_and_adds_matched_themes(self):
        items = [{"news_uid": "twse_mops:x", "source": "twse_mops", "source_tier": 1,
                  "ticker": "2330", "title": "公告本公司 CoWoS 擴產", "body": None}]
        tagged = np_.tag_items(items, _NAMES, _ENTITIES)
        assert tagged[0]["tickers"] == {"2330"}
        assert "CoWoS" in tagged[0]["themes"]

    def test_cnyes_dict_extraction(self):
        items = [{"news_uid": "cnyes:1", "source": "cnyes", "source_tier": 2,
                  "ticker": None, "title": "台積電液冷布局", "body": "供應鏈受惠"}]
        tagged = np_.tag_items(items, _NAMES, _ENTITIES)
        assert tagged[0]["tickers"] == {"2330"}
        assert "液冷" in tagged[0]["themes"]


# ------------------------------------------------------------------ #
# pulse — counting + insufficient-history gate
# ------------------------------------------------------------------ #
def _tagged(theme, n, tier=2):
    return [{"news_uid": "u%d" % i, "source_tier": tier, "tickers": set(),
             "themes": {theme}} for i in range(n)]


class TestThemePulse:
    def test_counts_by_theme_and_tier(self):
        tagged = _tagged("液冷", 3, tier=2) + _tagged("液冷", 2, tier=1)
        pulses = np_.theme_pulse(tagged, history={}, min_history=20)
        p = {x["theme"]: x for x in pulses}["液冷"]
        assert p["count"] == 5
        assert p["tier1"] == 2 and p["tier2"] == 3

    def test_insufficient_history_gates_z(self):
        hist = {"液冷": {"2026-07-%02d" % d: 1 for d in range(24, 29)}}  # n=5
        pulses = np_.theme_pulse(_tagged("液冷", 4), history=hist, min_history=20)
        p = pulses[0]
        assert p["z"] is None
        assert "insufficient-history(n=5)" in p["z_note"]

    def test_sufficient_history_computes_z(self):
        hist = {"液冷": {"d%02d" % i: 2 for i in range(25)}}  # n=25, mean=2, std=0
        pulses = np_.theme_pulse(_tagged("液冷", 2), history=hist, min_history=20)
        # std=0 (degenerate) → z gated to None, 不能假裝有分布
        assert pulses[0]["z"] is None
        hist2 = {"液冷": dict(("d%02d" % i, (i % 3)) for i in range(25))}
        p2 = np_.theme_pulse(_tagged("液冷", 9), history=hist2, min_history=20)[0]
        assert p2["z"] is not None and p2["z"] > 0
        assert "n=25" in p2["z_note"]


# ------------------------------------------------------------------ #
# cluster breadth (pure)
# ------------------------------------------------------------------ #
class TestClusterConfirm:
    def test_breadth_counts_and_otc_disclosure(self):
        members = {"2330", "3017", "8996"}
        price_5d = {"2330": 3.2, "3017": -1.0}       # 8996 = OTC, 無價格
        flow_5d = {"2330": 5.5e8, "3017": -2e8, "8996": 1e8}
        c = np_.cluster_confirm(members, price_5d, flow_5d)
        assert c["price_up"] == 1 and c["price_n"] == 2
        assert c["flow_pos"] == 2 and c["flow_n"] == 3
        assert c["no_price_data"] == ["8996"]


# ------------------------------------------------------------------ #
# report render
# ------------------------------------------------------------------ #
class TestRender:
    def test_report_has_sections_and_verification(self):
        pulses = [{"theme": "液冷", "count": 5, "tier1": 2, "tier2": 3,
                   "z": None, "z_note": "insufficient-history(n=5)",
                   "headlines": ["液冷進入下一階段"],
                   "cluster": {"price_up": 1, "price_n": 2, "flow_pos": 2,
                               "flow_n": 3, "no_price_data": ["8996"]}}]
        md = np_.render_report(dt.date(2026, 7, 29), pulses, total_items=100,
                               tagged_items=60)
        assert "題材脈衝" in md
        assert "insufficient-history(n=5)" in md
        assert "Verification log" in md
        assert "液冷" in md
