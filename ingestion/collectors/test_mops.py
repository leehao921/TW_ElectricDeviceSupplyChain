"""Parser tests for the MOPS 重大訊息 collector.

Exercises the pure-parsing surface against the saved JSON fixtures so the
collector's row-extraction logic can be verified without network access.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ingestion.collectors import mops

FIXTURE_DIR = Path(__file__).parent / "fixtures"
LIST_FIXTURE = FIXTURE_DIR / "mops_list.json"
DETAIL_FIXTURE = FIXTURE_DIR / "mops_detail.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_parse_since_accepts_day_suffix():
    assert mops.parse_since("7d") == 7
    assert mops.parse_since("1D") == 1
    assert mops.parse_since("30d") == 30


def test_parse_since_rejects_bad_input():
    with pytest.raises(argparse.ArgumentTypeError):
        mops.parse_since("7")
    with pytest.raises(argparse.ArgumentTypeError):
        mops.parse_since("0d")
    with pytest.raises(argparse.ArgumentTypeError):
        mops.parse_since("-3d")


def test_roc_date_conversion():
    assert mops.roc_to_iso_date("115/04/22") == date(2026, 4, 22)
    assert mops.roc_to_iso_date("100/01/01") == date(2011, 1, 1)


def test_disclosure_ts_is_utc():
    ts = mops.parse_disclosure_ts("115/04/21", "17:37:18")
    # 2026-04-21 17:37:18 +08:00 -> 09:37:18 UTC.
    assert ts == datetime(2026, 4, 21, 9, 37, 18, tzinfo=timezone.utc)


def test_iter_recent_dates_is_oldest_first():
    anchor = date(2026, 4, 24)
    days = list(mops.iter_recent_dates(3, today=anchor))
    assert days == [date(2026, 4, 22), date(2026, 4, 23), date(2026, 4, 24)]


def test_parse_list_row_filters_by_universe():
    payload = _load(LIST_FIXTURE)
    rows = list(mops.iter_list_rows(payload))
    assert len(rows) == 3

    allowed = frozenset({"2330", "2454"})
    parsed = [mops.parse_list_row(r, allowed_tickers=allowed) for r in rows]
    kept = [p for p in parsed if p is not None]
    assert {p.ticker for p in kept} == {"2330", "2454"}


def test_parse_list_row_builds_expected_disclosure():
    payload = _load(LIST_FIXTURE)
    tsmc_row = next(r for r in mops.iter_list_rows(payload) if r[2] == "2330")
    disclosure = mops.parse_list_row(tsmc_row, allowed_tickers=frozenset({"2330"}))

    assert disclosure is not None
    assert disclosure.ticker == "2330"
    assert disclosure.subject.startswith("本公司代子公司")
    assert disclosure.disclosure_ts == datetime(2026, 4, 21, 9, 37, 18, tzinfo=timezone.utc)
    assert disclosure.source_url == (
        "https://mops.twse.com.tw/mops/#/web/t05st02"
        "?companyId=2330&marketKind=sii&enterDate=1150421&serialNumber=1"
    )
    assert disclosure.body is None  # body is filled by fetch_detail


def test_parse_list_row_skips_malformed_row():
    assert mops.parse_list_row(["115/04/21", "17:00:00", "2330"]) is None
    assert mops.parse_list_row(
        ["115/04/21", "17:00:00", "2330", "台積電", "subject", "not-a-dict"]
    ) is None


def test_extract_detail_fields():
    payload = _load(DETAIL_FIXTURE)
    category, body = mops.extract_detail_fields(payload)
    assert category == "29"
    assert body is not None
    assert "美國國庫券" in body


def test_extract_detail_fields_handles_empty_payload():
    assert mops.extract_detail_fields({}) == (None, None)
    assert mops.extract_detail_fields({"result": {"data": []}}) == (None, None)


def test_source_url_roundtrip():
    url = mops.build_source_url("2330", "sii", "1150421", 1)
    params = mops._parse_source_url_params(url)
    assert params == {
        "companyId": "2330",
        "marketKind": "sii",
        "enterDate": "1150421",
        "serialNumber": 1,
    }
