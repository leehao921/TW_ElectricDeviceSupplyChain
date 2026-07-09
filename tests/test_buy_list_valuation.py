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


# ---------------------------------------------------------------------------
# Task 4: format_valuation
# ---------------------------------------------------------------------------
def test_format_valuation_full():
    s = bl.format_valuation(
        {"light": "RED", "pb_current": 7.2},
        {"pe": 64.22, "yield_pct": 1.33, "base_price": 4030.0},
        4030.0,
    )
    assert "P/B 7.20 🔴" in s
    assert "PE 64.2" in s
    assert "殖 1.3%" in s


def test_format_valuation_na_when_missing():
    s = bl.format_valuation({}, None, None)
    assert "P/B N/A ⚪" in s
    assert "PE N/A" in s
    assert "殖 N/A" in s


# ---------------------------------------------------------------------------
# Task 5: is_priority_trim
# ---------------------------------------------------------------------------
def _pick(stop=100.0):
    return {"ticker": "T", "stop_loss": stop, "entry_range": [110, 120], "tp1": 150}

def test_is_priority_trim_quadrants():
    # stop-break (close ≤ stop×1.02) AND RED → True
    assert bl.is_priority_trim(_pick(100), {"latest_close": 101.0}, {"light": "RED"}) is True
    # stop-break but GREEN → False
    assert bl.is_priority_trim(_pick(100), {"latest_close": 101.0}, {"light": "GREEN"}) is False
    # above stop but RED → False
    assert bl.is_priority_trim(_pick(100), {"latest_close": 130.0}, {"light": "RED"}) is False
    # N/A light → False
    assert bl.is_priority_trim(_pick(100), {"latest_close": 101.0}, {"light": "N/A"}) is False
    # no close → False
    assert bl.is_priority_trim(_pick(100), {}, {"light": "RED"}) is False


# ---------------------------------------------------------------------------
# Task 6: build_digest wiring
# ---------------------------------------------------------------------------
def test_build_digest_shows_valuation_and_priority_trim(monkeypatch):
    # a pick that is breaking stop and RED → 優先減碼; report parse stubbed
    state = {
        "version": "t", "picks": [
            {"ticker": "2454", "name": "聯發科", "tier": 1, "weight_pct": 20,
             "entry_range": [4250, 4350], "stop_loss": 4250, "tp1": 4700},
        ],
        "watch_list": [], "avoid_list": [],
    }
    snapshots = {"2454": {"latest_close": 4030.0, "f5": -100.0, "f20": 10.0, "t20": 0}}
    monkeypatch.setattr(bl, "parse_report_valuation",
                        lambda t, files=None: {"pe": 64.22, "yield_pct": 1.33, "base_price": 4030.0})
    pb_lights = {"2454": {"light": "RED", "pb_current": 7.2}}
    md = bl.build_digest(state, snapshots, {}, {}, pb_lights=pb_lights)
    assert "P/B 7.20 🔴" in md
    assert "PE 64.2" in md
    assert "🔴 優先減碼 (P/B RED)" in md


def test_build_digest_no_trim_when_green(monkeypatch):
    state = {"version": "t", "picks": [
        {"ticker": "2454", "name": "聯發科", "tier": 1, "weight_pct": 20,
         "entry_range": [4250, 4350], "stop_loss": 4250, "tp1": 4700}],
        "watch_list": [], "avoid_list": []}
    snapshots = {"2454": {"latest_close": 4030.0, "f5": 0, "f20": 0, "t20": 0}}
    monkeypatch.setattr(bl, "parse_report_valuation", lambda t, files=None: None)
    md = bl.build_digest(state, snapshots, {}, {}, pb_lights={"2454": {"light": "GREEN", "pb_current": 3.0}})
    assert "優先減碼" not in md
