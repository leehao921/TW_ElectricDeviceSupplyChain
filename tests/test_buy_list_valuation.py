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
