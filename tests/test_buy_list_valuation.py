from __future__ import annotations
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import buy_list_daily_alert as bl  # noqa: E402


# ---------------------------------------------------------------------------
# Task 1: load_pb_lights
# ---------------------------------------------------------------------------
class _FakeRedis:
    def __init__(self, data, boom=False):
        self._data = data
        self._boom = boom
    def hgetall(self, key):
        if self._boom:
            raise ConnectionError("redis down")
        return self._data


def test_load_pb_lights_parses_and_skips_meta():
    fake = _FakeRedis({
        "2408": '{"light":"RED","pb_current":7.2,"percentile":99,"p70":1.3,"p85":3.5,"asof":"2026-07-09","source":"cache fast-path"}',
        "_count": "50", "_updated": "2026-07-09T08:35",
    })
    out = bl.load_pb_lights(fake)
    assert set(out) == {"2408"}           # meta fields skipped
    assert out["2408"]["light"] == "RED"
    assert out["2408"]["pb_current"] == 7.2


def test_load_pb_lights_bad_json_skipped_and_redis_down_empty():
    assert bl.load_pb_lights(_FakeRedis({"2408": "{not json"})) == {}
    assert bl.load_pb_lights(_FakeRedis({}, boom=True)) == {}


# ---------------------------------------------------------------------------
# Task 2: parse_report_valuation
# ---------------------------------------------------------------------------
_REPORT_FIXTURE = """# 2454 - [[聯發科]]
## 估值概況
### 估值指標 (殖利率 1.33%) (股價 $4,030.00 as of 2026-07-08)
| P/E (TTM) | Forward P/E | P/S (TTM) |   P/B | EV/EBITDA |
|-----------|-------------|-----------|-------|-----------|
|     64.22 |         N/A |       N/A | 16.48 |       N/A |
"""

def test_parse_report_valuation_extracts_fields(tmp_path):
    fp = tmp_path / "2454_聯發科.md"
    fp.write_text(_REPORT_FIXTURE, encoding="utf-8")
    v = bl.parse_report_valuation("2454", files={"2454": str(fp)})
    assert v["pe"] == 64.22
    assert v["yield_pct"] == 1.33
    assert v["base_price"] == 4030.0


def test_parse_report_valuation_missing_file_returns_none():
    assert bl.parse_report_valuation("9999", files={}) is None


def test_parse_report_valuation_na_pe(tmp_path):
    txt = _REPORT_FIXTURE.replace("     64.22 ", "       N/A ")
    fp = tmp_path / "2454_聯發科.md"
    fp.write_text(txt, encoding="utf-8")
    v = bl.parse_report_valuation("2454", files={"2454": str(fp)})
    assert v["pe"] is None
    assert v["yield_pct"] == 1.33


# ---------------------------------------------------------------------------
# Task 3: recompute_valuation
# ---------------------------------------------------------------------------
def test_recompute_valuation_scales_by_price_ratio():
    rv = bl.recompute_valuation({"pe": 64.22, "yield_pct": 1.33, "base_price": 4030.0}, 4433.0)
    assert rv["pe"] == pytest.approx(64.22 * 4433.0 / 4030.0, rel=1e-4)   # ≈ 70.6, PE up with price
    assert rv["yield_pct"] == pytest.approx(1.33 * 4030.0 / 4433.0, rel=1e-4)  # ≈ 1.21, yield down


def test_recompute_valuation_none_inputs():
    assert bl.recompute_valuation(None, 100.0) == {"pe": None, "yield_pct": None}
    assert bl.recompute_valuation({"pe": 10, "yield_pct": 2, "base_price": None}, 100.0) == {"pe": None, "yield_pct": None}
    assert bl.recompute_valuation({"pe": 10, "yield_pct": 2, "base_price": 50.0}, None) == {"pe": None, "yield_pct": None}
