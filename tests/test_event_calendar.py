"""事件行事曆 (2026-10-13): MOPS 法說公告 → CSV;IV 期限表對照。"""
import csv
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import event_calendar as ec  # noqa: E402
from iv_term import event_premium, iv_term_lines  # noqa: E402

TSMC = ("符合條款第四條第XX款：12 事實發生日：115/10/15 1.召開法人說明會之日期：115/10/15 "
        "2.召開法人說明會之時間：14 時 00 分  3.召開法人說明會之地點：線上法說會 "
        "4.法人說明會擇要訊息：(1)公布本公司2026年第3季財務報告及2026年第4季業績展望。(2)參加方式：請參見https://x "
        "5.其他應敘明事項：無。")
BROKER = ("符合條款第四條第XX款：12 事實發生日：115/09/18 1.召開法人說明會之日期：115/09/18 "
          "2.召開法人說明會之時間：14 時 00 分 3.召開法人說明會之地點：元大證券11樓 "
          "4.法人說明會擇要訊息：本公司受邀參加元大證券舉辦實體法人說明會，說明本公司營運概況。 5.其他應敘明事項：無")


def test_parse_mops_body_tsmc():
    p = ec.parse_mops_body(TSMC)
    assert p["date"] == date(2026, 10, 15) and p["time"] == "14:00"
    assert p["venue"] == "線上法說會"
    assert ec.classify(p["summary"]) == "earnings"


def test_parse_mops_body_broker_invite():
    p = ec.parse_mops_body(BROKER)
    assert p["date"] == date(2026, 9, 18)
    assert ec.classify(p["summary"]) == "investor_conf"


def test_broker_roadshow_mentioning_financials_is_not_earnings():
    # 台達電 11/03 東京: 「受大和國泰證券邀請…說明…財務報告」= 券商活動, 非財報發布
    assert ec.classify("本公司受大和國泰證券邀請，將於上述時間地點，向法人投資者說明本公司115年第2季之財務報告相關資訊。") == "investor_conf"


def test_parse_returns_none_without_date():
    assert ec.parse_mops_body("公告本公司法人說明會資訊") is None


def test_row_from_news_marks_index_impact_and_source():
    row = ec.row_from_news({"news_uid": "u1", "ticker": "2330", "company_name": "台積電", "body": TSMC})
    assert row == {"date": "2026-10-15", "time": "14:00", "type": "earnings", "name": "台積電",
                   "symbol": "2330", "impact": "index", "source": "mops:u1",
                   "detail": "線上法說會 | 公布本公司2026年第3季財務報告及2026年第4季業績展望。"}
    assert ec.row_from_news({"news_uid": "u2", "ticker": "1219", "company_name": "福壽", "body": BROKER})["impact"] == "stock"


def test_upsert_dedups_on_date_symbol_and_sorts(tmp_path):
    p = tmp_path / "cal.csv"
    a = {"date": "2026-10-15", "time": "14:00", "type": "earnings", "name": "台積電", "symbol": "2330",
         "impact": "index", "source": "mops:u1", "detail": "x"}
    b = dict(a, date="2026-09-18", symbol="1219", name="福壽", type="investor_conf", impact="stock")
    assert ec.upsert(p, [a, b]) == 2
    assert ec.upsert(p, [dict(a, detail="updated", type="investor_conf")]) == 0   # 同日同公司 → 覆寫 (含重分類)
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    assert [r["date"] for r in rows] == ["2026-09-18", "2026-10-15"]
    assert rows[1]["detail"] == "updated" and rows[1]["type"] == "investor_conf"


def test_events_between_filters_impact(tmp_path):
    p = tmp_path / "cal.csv"
    ec.upsert(p, [
        {"date": "2026-10-15", "time": "14:00", "type": "earnings", "name": "台積電", "symbol": "2330",
         "impact": "index", "source": "manual", "detail": ""},
        {"date": "2026-10-16", "time": "14:00", "type": "investor_conf", "name": "福壽", "symbol": "1219",
         "impact": "stock", "source": "manual", "detail": ""}])
    ev = ec.events_between(ec.load_events(p), date(2026, 10, 13), date(2026, 10, 23), impact="index")
    assert [e["name"] for e in ev] == ["台積電"]


# ── IV 期限表對照 ──────────────────────────────────────────────────────

def test_event_premium_isolates_event_variance():
    # 含事件腿 σ=1500 (3 場) vs 無事件鄰腿 σ=1625 (6 場): 每場 forward var 130,208 → 基準 390,625
    assert event_premium((3, 1500.0), (6, 1625.0)) == pytest.approx(1363.6, abs=0.5)
    assert event_premium((3, 1139.0), (6, 1625.0)) is None                # 基準 > 總變異 → 無溢價


NOW = datetime(2026, 10, 13, 16, 59)
CURVE = [("20261014", 23.9), ("20261016", 26.6), ("20261021", 22.8), ("20261023", 23.0)]
FWD = {"20261014": 48599.0, "20261016": 48599.0, "20261021": 48599.0, "20261023": 48599.0}
EV = [{"date": "2026-10-15", "time": "14:00", "type": "earnings", "name": "台積電", "symbol": "2330",
       "impact": "index"}]


def test_after_close_event_lands_in_next_expiry_not_same_day_settle():
    L = iv_term_lines(CURVE, FWD, ("TXF", 48599.0), NOW, holidays=set(), events=EV)
    ev = [ln for ln in L if ln.startswith("📅")]
    assert len(ev) == 1
    assert ev[0].startswith("📅 10/15 台積電法說 → 10/16 ")
    assert ev[0].endswith("無溢價") or "點" in ev[0]


def test_event_line_fits_mobile_width_with_premium():
    import discord_forward
    curve = [("20261016", 30.0), ("20261021", 22.8)]           # 10/16 含事件且明顯偏貴
    L = iv_term_lines(curve, FWD, ("TXF", 48599.0), NOW, holidays=set(), events=EV)
    ev = next(ln for ln in L if ln.startswith("📅"))
    assert "點" in ev and discord_forward._disp_width(ev) <= 40, ev


def test_no_events_no_line():
    L = iv_term_lines(CURVE, FWD, ("TXF", 48599.0), NOW, holidays=set(), events=[])
    assert not any(ln.startswith("📅") for ln in L)
