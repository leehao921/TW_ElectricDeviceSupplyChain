"""事件窗口 IV 監控 (2026-10-15) — plan: docs/plans/2026-10-15-event-window-iv.md"""
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import event_calendar as ec  # noqa: E402
import event_window as ew  # noqa: E402
from iv_term import implied_event_move  # noqa: E402

HOL = {date(2026, 10, 9), date(2026, 10, 10)}

# ── 1. macro → calendar ─────────────────────────────────────────────
MACRO = [
    {"id": "CPI-2026-10-14", "kind": "CPI", "label": "CPI 通膨", "at": "2026-10-14T20:30:00+08:00"},
    {"id": "FOMC-2026-10-28", "kind": "FOMC", "label": "FOMC 利率決議", "at": "2026-10-29T02:00:00+08:00"},
    {"id": "TSMC_EARN-2026-07-16", "kind": "TSMC_EARN", "label": "台積電法說", "at": "2026-07-16T14:00:00+08:00"},
    {"id": "TW_EARN_2317-2026-11-12", "kind": "TW_EARN_2317", "label": "鴻海法說", "at": "2026-11-12T14:00:00+08:00"},
    {"id": "X-1", "kind": "UNKNOWN", "label": "x", "at": "2026-10-01T10:00:00+08:00"},
]


def test_macro_rows_map_kinds_to_calendar():
    rows = {r["symbol"]: r for r in ec.macro_rows(MACRO)}
    assert rows["CPI"] == {"date": "2026-10-14", "time": "20:30", "type": "macro", "name": "CPI 通膨",
                           "symbol": "CPI", "impact": "index", "source": "nautilus:CPI-2026-10-14", "detail": ""}
    assert rows["FOMC"]["date"] == "2026-10-29" and rows["FOMC"]["time"] == "02:00"   # 台北日期
    assert rows["2330"]["type"] == "earnings" and rows["2330"]["impact"] == "index"
    assert rows["2317"]["type"] == "earnings"
    assert "UNKNOWN" not in rows


def test_insert_missing_keeps_mops_rows(tmp_path):
    p = tmp_path / "cal.csv"
    mops = {"date": "2026-07-16", "time": "14:00", "type": "earnings", "name": "台積電", "symbol": "2330",
            "impact": "index", "source": "mops:u9", "detail": "線上法說會"}
    ec.upsert(p, [mops])
    assert ec.insert_missing(p, ec.macro_rows(MACRO)) == 3            # CPI, FOMC, 2317 新增;2330 已有
    row = next(r for r in ec.load_events(p) if r["symbol"] == "2330")
    assert row["source"] == "mops:u9"


# ── 2. 交易時段 / reaction / pre 時刻 ─────────────────────────────────
def test_reaction_in_night_session_is_release_itself():
    assert ew.reaction_time(datetime(2026, 10, 14, 20, 30), HOL) == datetime(2026, 10, 14, 20, 30)


def test_after_close_event_reacts_at_night_open():
    assert ew.reaction_time(datetime(2026, 10, 15, 14, 0), HOL) == datetime(2026, 10, 15, 15, 0)


def test_after_midnight_fomc_in_night_tail():
    assert ew.reaction_time(datetime(2026, 10, 29, 2, 0), HOL) == datetime(2026, 10, 29, 2, 0)


def test_holiday_morning_event_waits_for_next_trading_day():
    # 10/09 (補假) 08:00 → 10/09 無日盤、10/09 無夜盤 → 10/12 08:45
    assert ew.reaction_time(datetime(2026, 10, 9, 8, 0), HOL) == datetime(2026, 10, 12, 8, 45)


def test_pre_time_uses_last_tradable_minute_for_after_close_event():
    assert ew.pre_time(datetime(2026, 10, 15, 14, 0), HOL) == datetime(2026, 10, 15, 13, 15)
    assert ew.pre_time(datetime(2026, 10, 14, 20, 30), HOL) == datetime(2026, 10, 14, 20, 0)


# ── 3. 定價幅度 ──────────────────────────────────────────────────────
NOW = datetime(2026, 10, 14, 20, 15)
CURVE = [("20261016", 29.1), ("20261021", 21.4)]
FWD = {"20261016": 48850.0, "20261021": 48850.0}


def test_implied_event_move_cpi_example():
    m = implied_event_move(CURVE, FWD, ("TXF", 48850.0), NOW, datetime(2026, 10, 14, 20, 30), HOL)
    assert m["expiry"] == "20261016"
    assert m["pts"] == pytest.approx(484, abs=15)
    assert m["pct"] == pytest.approx(0.99, abs=0.03)


def test_implied_event_move_none_when_no_expiry_after_event():
    assert implied_event_move(CURVE, FWD, ("TXF", 48850.0), NOW, datetime(2026, 12, 1, 9, 0), HOL) is None


# ── 4. 反應分類 / outcome ─────────────────────────────────────────────
def test_classify_continuation_down():
    # 10/14 CPI +5分: 實際 -240 vs 定價 484, 週選 IV +0.9, PCR +0.33
    assert ew.classify_reaction(-240, 484, 0.9, 0.33) == "延續(跌)"


def test_classify_digestion_on_iv_crush():
    assert ew.classify_reaction(-300, 484, -0.8, 0.10) == "消化"


def test_classify_mixed_when_pcr_disagrees():
    assert ew.classify_reaction(-240, 484, 0.9, -0.05) == "混合"


def test_classify_small_move_is_mixed():
    assert ew.classify_reaction(-50, 484, 0.9, 0.3) == "混合"


def test_classify_without_implied_uses_price_scale():
    assert ew.classify_reaction(+300, None, 0.7, -0.2, px=48800) == "延續(漲)"


def test_outcome():
    # +5 分跌到 48,705 (前 48,945), +60 分 48,450 → 再跌 255 ≥ 0.1×484 → continued
    assert ew.outcome(48945, 48705, 48450, 484) == "continued"
    assert ew.outcome(48945, 48705, 48900, 484) == "reversed"
    assert ew.outcome(48945, 48705, 48720, 484) == "flat"


# ── 5. 訊息 (手機 ≤40 寬) / log ──────────────────────────────────────
def test_messages_fit_mobile():
    import discord_forward as d
    pre = ew.pre_message("CPI 通膨", datetime(2026, 10, 14, 20, 30),
                         {"expiry": "20261016", "pts": 484, "pct": 0.99}, ["台積電法說"])
    post = ew.post_message("CPI 通膨", 5, -240, 484, 0.9, 0.33, "延續(跌)")
    assert "±484" in pre and "台積電法說" in pre
    assert "-240" in post and "延續(跌)" in post
    for ln in (pre + "\n" + post).split("\n"):
        assert d._disp_width(ln) <= 40, ln


def test_log_upsert_merges_stages(tmp_path):
    p = tmp_path / "log.csv"
    ew.log_upsert(p, "2026-10-14|CPI", {"kind": "CPI", "implied_pts": "484"})
    ew.log_upsert(p, "2026-10-14|CPI", {"class_5": "延續(跌)"})
    rows = ew.load_log(p)
    assert len(rows) == 1 and rows[0]["implied_pts"] == "484" and rows[0]["class_5"] == "延續(跌)"


def test_event_window_routes_to_trading():
    import discord_forward as d
    assert d.route_topic({"topic": "event-window"}) == "trading"


def test_study_groups_by_class_and_refuses_small_n():
    import event_window_study as s
    rows = ([{"class_15": "延續(跌)", "outcome_60": "continued", "data_quality": "ok"}] * 3
            + [{"class_15": "消化", "outcome_60": "reversed", "data_quality": "pre_fix"}] * 2
            + [{"class_15": "混合", "outcome_60": "flat", "data_quality": "ok"}]
            + [{"class_15": "資料不足", "outcome_60": "", "data_quality": "pre_fix"}])
    res = s.study(rows, stage="15", min_n=20)
    assert res["n"] == 6                                       # 資料不足/無 outcome 排除
    assert res["groups"]["延續"]["hit"] == 1.0                 # 延續 → continued
    assert res["groups"]["消化"]["hit"] == 1.0                 # 消化 → reversed
    assert res["base_continued"] == pytest.approx(0.5)
    assert res["verdict"] == "樣本不足,不下結論"


def test_baseline_is_last_tradable_minute_before_event():
    # 10/15 台積電 14:00 盤後: 休市 13:45-15:00 無資料 → 基準取日盤最後一分 13:44 (原用 14:59 → 空值)
    assert ew.baseline_time(datetime(2026, 10, 15, 14, 0), HOL) == datetime(2026, 10, 15, 13, 44)
    assert ew.baseline_time(datetime(2026, 10, 14, 20, 30), HOL) == datetime(2026, 10, 14, 20, 29)
