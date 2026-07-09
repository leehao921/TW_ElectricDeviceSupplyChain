"""Offline unit tests for pb_lights_publish (pure functions + main dry-run)."""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import pb_lights_publish as plp  # noqa: E402

STATE_PATH = REPO_ROOT / "data" / "buy_list_state.json"


# --------------------------------------------------------------------- #
# load_universe
# --------------------------------------------------------------------- #
def test_load_universe_unions_dedups_real_state():
    universe = plp.load_universe(STATE_PATH)
    assert len(universe) >= 40
    assert len(universe) == len(set(universe))  # no dups
    assert "2408" in universe
    assert "2330" in universe


def test_load_universe_handles_dict_and_str_entries(tmp_path):
    state = {
        "picks": [{"ticker": "1111"}, {"ticker": "2222"}],
        "watch_list": ["3333", {"ticker": "2222"}],  # str + dict + dup
        "avoid_list": [{"ticker": "4444"}],
    }
    p = tmp_path / "s.json"
    p.write_text(json.dumps(state), encoding="utf-8")
    universe = plp.load_universe(p)
    assert universe == ["1111", "2222", "3333", "4444"]


# --------------------------------------------------------------------- #
# build_light_records
# --------------------------------------------------------------------- #
def _fake_light_fn(records_by_ticker):
    def fn(ticker, latest_close=None, today=None):
        rec = dict(records_by_ticker[ticker])
        rec["ticker"] = ticker
        return rec
    return fn


def test_build_light_records_never_drops_and_marks_na():
    universe = ["1111", "2222", "3333"]
    closes = {"1111": 10.0, "3333": 30.0}  # 2222 missing
    fn = _fake_light_fn({
        "1111": {"light": "RED", "pb_current": 5.0, "percentile": 90.0,
                 "asof": "2026-07-09", "source": "x"},
        "2222": {"light": "GREEN", "pb_current": 1.0, "percentile": 10.0,
                 "asof": "2026-07-09", "source": "x"},
        "3333": {"light": "N/A", "pb_current": None, "percentile": None,
                 "asof": "2026-07-09", "source": "thin"},
    })
    recs = plp.build_light_records(universe, closes, fn, "2026-07-09")
    assert len(recs) == len(universe)  # never drops
    by = {r["ticker"]: r for r in recs}
    assert by["1111"]["light"] == "RED"
    # missing close -> N/A regardless of fn
    assert by["2222"]["light"] == "N/A"
    # engine N/A kept as N/A
    assert by["3333"]["light"] == "N/A"


# --------------------------------------------------------------------- #
# records_to_hash_mapping
# --------------------------------------------------------------------- #
def test_records_to_hash_mapping_valid_json_and_meta():
    recs = [
        {"ticker": "1111", "light": "RED", "pb_current": 5.0,
         "percentile": 90.0, "asof": "2026-07-09", "source": "x"},
        {"ticker": "2222", "light": "N/A", "pb_current": None,
         "percentile": None, "asof": "2026-07-09", "source": "y"},
    ]
    m = plp.records_to_hash_mapping(recs, "2026-07-09T08:35:00")
    assert m["_count"] == "2"
    assert m["_updated"] == "2026-07-09T08:35:00"
    assert all(isinstance(v, str) for v in m.values())
    for tk in ("1111", "2222"):
        parsed = json.loads(m[tk])  # valid JSON round-trip
        assert set(parsed) == {"light", "pb_current", "percentile", "asof", "source"}


# --------------------------------------------------------------------- #
# build_inbox_summary
# --------------------------------------------------------------------- #
def test_build_inbox_summary_counts_and_lists():
    recs = [
        {"ticker": "1111", "light": "RED"},
        {"ticker": "2222", "light": "RED"},
        {"ticker": "3333", "light": "YELLOW"},
        {"ticker": "4444", "light": "N/A"},
    ]
    s = plp.build_inbox_summary(recs, "2026-07-09")
    assert "2 RED" in s
    assert "1 YELLOW" in s
    assert "1 N/A" in s
    assert "1111" in s and "2222" in s  # RED tickers listed
    assert "3333" in s  # YELLOW ticker listed
    # <=3 N/A: count only, no N/A: line
    assert "N/A:" not in s


def test_build_inbox_summary_lists_na_when_elevated():
    # >3 N/A tickers -> list them so coverage drops are diagnosable
    recs = [{"ticker": f"90{i:02d}", "light": "N/A"} for i in range(5)]
    recs.append({"ticker": "1111", "light": "RED"})
    s = plp.build_inbox_summary(recs, "2026-07-09")
    assert "5 N/A" in s
    assert "N/A: " in s
    for i in range(5):
        assert f"90{i:02d}" in s  # every N/A ticker listed


# --------------------------------------------------------------------- #
# main --dry-run touches no redis
# --------------------------------------------------------------------- #
class _Boom:
    def hset(self, *a, **k):
        raise AssertionError("hset must not be called in dry-run")

    def xadd(self, *a, **k):
        raise AssertionError("xadd must not be called in dry-run")

    def delete(self, *a, **k):
        raise AssertionError("delete must not be called in dry-run")


def test_main_dry_run_no_redis(monkeypatch):
    monkeypatch.setattr(plp, "fetch_latest_closes",
                        lambda universe: {t: 10.0 for t in universe})
    monkeypatch.setattr(plp.pb_percentile, "pb_light",
                        lambda ticker, latest_close=None, today=None: {
                            "ticker": ticker, "light": "GREEN",
                            "pb_current": 1.0, "percentile": 10.0,
                            "asof": "2026-07-09", "source": "fake"})
    monkeypatch.setattr(plp, "make_redis_client", lambda: _Boom())
    rc = plp.main(["--dry-run", "--today", "2026-07-09"])
    assert rc == 0


# --------------------------------------------------------------------- #
# main degrades (does not crash) when Redis is down
# --------------------------------------------------------------------- #
class _RedisDown:
    def delete(self, *a, **k):
        raise ConnectionError("redis down")

    def hset(self, *a, **k):
        raise ConnectionError("redis down")

    def xadd(self, *a, **k):
        raise ConnectionError("redis down")


def test_main_redis_down_degrades(monkeypatch):
    monkeypatch.setattr(plp, "fetch_latest_closes",
                        lambda universe: {t: 10.0 for t in universe})
    monkeypatch.setattr(plp.pb_percentile, "pb_light",
                        lambda ticker, latest_close=None, today=None: {
                            "ticker": ticker, "light": "GREEN",
                            "pb_current": 1.0, "percentile": 10.0,
                            "asof": "2026-07-09", "source": "fake"})
    monkeypatch.setattr(plp, "make_redis_client", lambda: _RedisDown())
    # must NOT raise; digest already printed; returns nonzero
    rc = plp.main(["--today", "2026-07-09"])
    assert rc == 1
