"""產業全景盤中版 — Redis sector:live → 本機自動刷新頁 (2026-10-01)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sector_treemap as st  # noqa: E402
import sector_treemap_live as live  # noqa: E402

REF = {("TWSE", "2330"): {"name": "台積電", "industry_code": "24", "shares": 1000},
       ("TWSE", "2881"): {"name": "富邦金", "industry_code": "17", "shares": 500}}
SNAP = {"ts": "2026-10-01T10:31:05+08:00",
        "quotes": [{"market": "TWSE", "code": "2330", "last": 102.0, "prev": 100.0, "vol_lots": 3, "src": "trade"},
                   {"market": "TWSE", "code": "2881", "last": 99.0, "prev": 100.0, "vol_lots": 2, "src": "mid"},
                   {"market": "TWSE", "code": "9999", "last": 10.0, "prev": 10.0, "vol_lots": 1, "src": "trade"}],
        "indices": [{"market": "TWSE", "industry_code": "IX", "close": 20100.0, "prev": 20000.0},
                    {"market": "TWSE", "industry_code": "24", "close": 1012.0, "prev": 1000.0}]}


def test_live_rows_join_reference_and_estimate_value():
    rows = {r["code"]: r for r in live.live_rows(SNAP, REF)["TWSE"]}
    assert set(rows) == {"2330", "2881"}            # no reference → no shares/industry → dropped
    r = rows["2330"]
    assert (r["prev_close"], r["close"], r["change"]) == (100.0, 102.0, 2.0)
    assert r["trade_value"] == 3 * 1000 * 102.0     # 張 × 1000 × 價 (估)
    assert r["industry_code"] == "24" and r["shares"] == 1000


def test_live_index_from_snapshot():
    ix = live.live_index(SNAP)["TWSE"]
    assert ix["IX"]["change_pts"] == 100.0 and ix["IX"]["close"] == 20100.0
    assert ix["24"]["change_pct"] == pytest.approx(1.2)


def test_build_live_marks_payload():
    data = live.build_live(SNAP, REF)
    assert data["live"] is True and data["date"] == "2026-10-01 10:31:05 盤中"
    assert data["markets"]["TWSE"]["index"]["chg_pts"] == 100.0


def test_standalone_refresh_meta():
    html = st.render_standalone("<p></p>", {"date": "d", "markets": {}}, refresh_s=60)
    assert '<meta http-equiv="refresh" content="60">' in html


def test_stale_snapshot_detected():
    import datetime as dt
    now = dt.datetime(2026, 10, 1, 10, 40, tzinfo=dt.timezone(dt.timedelta(hours=8)))
    assert live.is_stale(SNAP, now, max_age_s=300) is True
    assert live.is_stale(SNAP, now, max_age_s=900) is False


def test_snapshot_without_main_index_is_not_rendered():
    # 10/01 12:02:57: MIS failures dropped the batch holding the indices → 0 indices;
    # the page was written with a null index and the summary print crashed.
    snap = {**SNAP, "indices": [i for i in SNAP["indices"] if i["industry_code"] != "IX"]}
    assert live.renderable(live.build_live(snap, REF)) is False
    assert live.renderable(live.build_live(SNAP, REF)) is True
