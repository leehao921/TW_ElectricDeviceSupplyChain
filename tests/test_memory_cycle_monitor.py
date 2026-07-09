"""Tests for scripts/memory_cycle_monitor.py — DRAM sell-signal monitor."""
from scripts.memory_cycle_monitor import (
    Inputs,
    PricePoint,
    SignalResult,
    GREEN, YELLOW, RED,
)


# Reusable P/B light records (mirror the h:agent:pb_lights hash record shape)
def _pb_rec(light, pb, percentile=None, p70=None, p85=None,
            asof="2026-06-25", source="cache fast-path"):
    return {"light": light, "pb_current": pb, "percentile": percentile,
            "p70": p70, "p85": p85, "asof": asof, "source": source}


def test_signal_result_has_required_fields():
    r = SignalResult(light=GREEN, value="ok", detail={"x": 1})
    assert r.light == "GREEN"
    assert r.value == "ok"
    assert r.detail == {"x": 1}


from pathlib import Path
import pytest
from scripts.memory_cycle_monitor import load_inputs

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_inputs_full_fixture():
    inp = load_inputs(FIXTURES / "memory_cycle_full.yaml")
    assert inp.last_updated == "2026-06-25"
    assert len(inp.ddr4_8gb_spot_usd) == 4
    assert inp.ddr4_8gb_spot_usd[0].label == "2026-03"
    assert inp.ddr4_8gb_spot_usd[-1].price == 3.45
    assert len(inp.ddr5_16gb_contract_usd) == 3
    assert inp.ddr5_16gb_contract_usd[0].label == "2025Q4"
    assert inp.mu_next_quarter_gm_guide == 0.86


def test_load_inputs_minimal_fixture():
    inp = load_inputs(FIXTURES / "memory_cycle_minimal.yaml")
    assert len(inp.ddr4_8gb_spot_usd) == 2
    assert len(inp.ddr5_16gb_contract_usd) == 2
    assert inp.mu_next_quarter_gm_guide is None


def test_load_inputs_sorts_unordered_dates(tmp_path):
    p = tmp_path / "unordered.yaml"
    p.write_text("""
last_updated: 2026-06-25
notes: ""
ddr4_8gb_spot_usd:
  - {month: "2026-06", price: 3.45}
  - {month: "2026-04", price: 2.85}
  - {month: "2026-05", price: 3.12}
""")
    inp = load_inputs(p)
    labels = [pp.label for pp in inp.ddr4_8gb_spot_usd]
    assert labels == ["2026-04", "2026-05", "2026-06"]


def test_load_inputs_raises_on_missing_required_field(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("notes: 'missing last_updated'\n")
    with pytest.raises(ValueError, match="last_updated"):
        load_inputs(p)


from scripts.memory_cycle_monitor import compute_s2a_ddr4


def _ddr4(prices: list[float]) -> list[PricePoint]:
    return [PricePoint(label=f"2026-{i+1:02d}", price=p) for i, p in enumerate(prices)]


def test_s2a_green_when_positive_mom():
    r = compute_s2a_ddr4(_ddr4([3.0, 3.2, 3.45]))
    assert r.light == GREEN
    assert "+" in r.value  # e.g. "+7.8%"


def test_s2a_yellow_on_first_negative_mom():
    r = compute_s2a_ddr4(_ddr4([3.0, 3.2, 3.1]))  # latest down
    assert r.light == YELLOW


def test_s2a_red_on_two_consecutive_negative_mom():
    r = compute_s2a_ddr4(_ddr4([3.5, 3.2, 3.0]))  # two down months
    assert r.light == RED


def test_s2a_consecutive_resets_on_positive_in_between():
    # down, up, down → latest negative but not consecutive → YELLOW not RED
    r = compute_s2a_ddr4(_ddr4([3.5, 3.2, 3.4, 3.3]))
    assert r.light == YELLOW


def test_s2a_na_when_fewer_than_2_points():
    r = compute_s2a_ddr4(_ddr4([3.0]))
    assert r.light == "N/A"


from scripts.memory_cycle_monitor import compute_s2b_ddr5


def _ddr5(prices: list[float]) -> list[PricePoint]:
    quarters = ["2025Q4", "2026Q1", "2026Q2", "2026Q3"]
    return [PricePoint(label=quarters[i], price=p) for i, p in enumerate(prices)]


def test_s2b_green_strong_qoq_low_decay():
    # QoQ +21% from +20% → decay ~5% → green
    r = compute_s2b_ddr5(_ddr5([3.5, 4.2, 5.082]))  # 20% then 21%
    assert r.light == GREEN


def test_s2b_yellow_when_qoq_decays_more_than_50pct():
    # +20% → +9% → decay 55% → YELLOW
    r = compute_s2b_ddr5(_ddr5([3.5, 4.2, 4.578]))
    assert r.light == YELLOW


def test_s2b_yellow_when_qoq_below_10pct_3_quarter():
    # +21% → +8% → decay big → YELLOW
    r = compute_s2b_ddr5(_ddr5([3.5, 4.235, 4.574]))  # second QoQ ~8%
    assert r.light == YELLOW


def test_s2b_red_when_qoq_below_5pct():
    # +21% → +3% → RED (absolute threshold)
    r = compute_s2b_ddr5(_ddr5([3.5, 4.235, 4.362]))  # second QoQ ~3%
    assert r.light == RED


def test_s2b_red_on_negative_qoq():
    r = compute_s2b_ddr5(_ddr5([3.5, 4.2, 4.0]))
    assert r.light == RED


def test_s2b_degraded_2_quarter_green_at_plus_10():
    # Only 2 quarters → absolute-only mode. +21% → GREEN
    r = compute_s2b_ddr5([
        PricePoint("2026Q1", 4.20),
        PricePoint("2026Q2", 5.10),
    ])
    assert r.light == GREEN
    assert r.detail.get("decay_pct") is None  # decay unavailable


def test_s2b_degraded_2_quarter_yellow_between_5_and_10():
    r = compute_s2b_ddr5([
        PricePoint("2026Q1", 4.20),
        PricePoint("2026Q2", 4.50),  # ~7.1%
    ])
    assert r.light == YELLOW


def test_s2b_na_when_fewer_than_2_quarters():
    r = compute_s2b_ddr5([PricePoint("2026Q2", 5.10)])
    assert r.light == "N/A"


from scripts.memory_cycle_monitor import compute_s1_pb, read_pb_lights


def test_s1_green_when_both_green_records():
    r = compute_s1_pb({
        "2408.TW": _pb_rec(GREEN, 1.42, percentile=40, p70=5.0, p85=6.5),
        "2344.TW": _pb_rec(GREEN, 1.12, percentile=30, p70=4.0, p85=5.5),
    })
    assert r.light == GREEN
    assert r.detail["2408.TW"]["pb"] == 1.42
    assert r.detail["2408.TW"]["percentile"] == 40
    assert r.detail["2408.TW"]["p70"] == 5.0
    assert r.detail["2408.TW"]["p85"] == 6.5
    assert r.detail["2408.TW"]["source"] == "cache fast-path"
    assert r.detail["2408.TW"]["light"] == GREEN
    # value string carries P/B + percentile
    assert "2408.TW=1.42(p40)" in r.value


def test_s1_yellow_record():
    r = compute_s1_pb({
        "2408.TW": _pb_rec(YELLOW, 5.2, percentile=75),
        "2344.TW": _pb_rec(GREEN, 1.10, percentile=20),
    })
    assert r.light == YELLOW


def test_s1_red_record():
    r = compute_s1_pb({
        "2408.TW": _pb_rec(RED, 7.2, percentile=98, p70=5.0, p85=6.5),
        "2344.TW": _pb_rec(GREEN, 1.10, percentile=20),
    })
    assert r.light == RED


def test_s1_takes_worst_of_two():
    # one green, one red → RED
    r = compute_s1_pb({
        "2408.TW": _pb_rec(GREEN, 1.10, percentile=15),
        "2344.TW": _pb_rec(RED, 8.35, percentile=99),
    })
    assert r.light == RED


def test_s1_na_when_record_missing():
    r = compute_s1_pb({"2408.TW": None, "2344.TW": _pb_rec(GREEN, 1.10, percentile=20)})
    assert r.detail["2408.TW"] == "N/A"
    assert "2408.TW=N/A" in r.value
    # 2344 still computes → overall takes worst-known (green)
    assert r.light == GREEN


def test_s1_value_guards_none_percentile():
    # cache fast-path leaves percentile None but pb/light populated
    r = compute_s1_pb({
        "2408.TW": _pb_rec(RED, 7.2, percentile=None, p70=5.0, p85=6.5),
        "2344.TW": None,
    })
    assert r.light == RED
    assert "2408.TW=7.20" in r.value
    assert "(p" not in r.value  # no percentile suffix when None


def test_s1_record_missing_light_is_na():
    # valid-JSON record without a "light" key must not crash → treated as N/A
    r = compute_s1_pb({"2408.TW": {"pb_current": 5.0}, "2344.TW": None})
    assert r.detail["2408.TW"] == "N/A"
    assert r.detail["2344.TW"] == "N/A"
    assert "2408.TW=N/A" in r.value
    # both N/A → overall N/A (no known light)
    assert r.light == "N/A"


# --------------------------------------------------------------------- #
# read_pb_lights — Redis hash parsing
# --------------------------------------------------------------------- #
import json as _json


class _FakeHashClient:
    def __init__(self, mapping):
        self._mapping = mapping

    def hgetall(self, key):
        return dict(self._mapping)


def test_read_pb_lights_valid_json_maps_bare_key():
    rec = {"light": "RED", "pb_current": 7.2, "percentile": 98,
           "p70": 5.0, "p85": 6.5, "asof": "2026-06-25", "source": "x"}
    client = _FakeHashClient({"2408": _json.dumps(rec), "_count": "1"})
    out = read_pb_lights(client, ["2408.TW", "2344.TW"])
    # .TW suffix mapped to bare "2408" hash field
    assert out["2408.TW"] == rec
    # missing field → None
    assert out["2344.TW"] is None


def test_read_pb_lights_bad_json_returns_none():
    client = _FakeHashClient({"2408": "{not valid json"})
    out = read_pb_lights(client, ["2408.TW"])
    assert out["2408.TW"] is None


def test_read_pb_lights_two_suffix_maps_bare_key():
    rec = {"light": "GREEN", "pb_current": 1.0, "percentile": 10,
           "p70": 3.0, "p85": 4.0, "asof": "2026-06-25", "source": "x"}
    client = _FakeHashClient({"8358": _json.dumps(rec)})
    out = read_pb_lights(client, ["8358.TWO"])
    assert out["8358.TWO"] == rec


def test_read_pb_lights_redis_error_all_none():
    class _Boom:
        def hgetall(self, key):
            raise ConnectionError("redis down")
    out = read_pb_lights(_Boom(), ["2408.TW", "2344.TW"])
    assert out == {"2408.TW": None, "2344.TW": None}


# --------------------------------------------------------------------- #
# s1_lights_with_fallback — engine-A self-heal when hash missing a ticker
# --------------------------------------------------------------------- #
def test_s1_fallback_calls_engine_a_when_record_missing(mocker):
    from scripts.memory_cycle_monitor import s1_lights_with_fallback, _import_pb_percentile
    pb_percentile = _import_pb_percentile()
    # hash has 2344 but NOT 2408
    rec2344 = {"light": "GREEN", "pb_current": 1.1, "percentile": 20,
               "p70": 3.0, "p85": 4.0, "asof": "2026-06-25", "source": "hash"}
    client = _FakeHashClient({"2344": _json.dumps(rec2344)})

    def fake_light(ticker, latest_close=None, today=None):
        assert ticker == "2408"  # bare ticker passed to engine A
        return {"ticker": "2408", "light": "RED", "pb_current": 7.2,
                "percentile": 98, "p70": 5.0, "p85": 6.5,
                "asof": "2026-06-25", "source": "engine-A recompute"}

    mocker.patch.object(pb_percentile, "pb_light", side_effect=fake_light)
    out = s1_lights_with_fallback(client, ["2408.TW", "2344.TW"])
    assert out["2344.TW"] == rec2344              # kept from hash
    assert out["2408.TW"]["light"] == "RED"        # self-healed via engine A
    assert out["2408.TW"]["source"] == "engine-A recompute"


def test_s1_fallback_keeps_none_on_engine_failure(mocker):
    from scripts.memory_cycle_monitor import s1_lights_with_fallback, _import_pb_percentile
    pb_percentile = _import_pb_percentile()
    client = _FakeHashClient({})  # empty hash → both missing
    mocker.patch.object(pb_percentile, "pb_light",
                        side_effect=RuntimeError("engine boom"))
    out = s1_lights_with_fallback(client, ["2408.TW", "2344.TW"])
    assert out == {"2408.TW": None, "2344.TW": None}


from scripts.memory_cycle_monitor import detect_monthly_weakness


def test_monthly_weakness_true_when_latest_below_prior_3_min():
    # latest = 90 < min(prior 3 = [95, 100, 98]) = 95 → weak
    closes = [105, 102, 100, 95, 100, 98, 90]
    assert detect_monthly_weakness(closes) is True


def test_monthly_weakness_false_when_latest_equals_prior_3_min():
    # strict less-than → equal = not weak
    closes = [100, 102, 95, 100, 98, 95]
    assert detect_monthly_weakness(closes) is False


def test_monthly_weakness_false_when_latest_above():
    closes = [100, 95, 98, 99, 105]
    assert detect_monthly_weakness(closes) is False


def test_monthly_weakness_false_with_insufficient_data():
    # need at least 4 months (3 prior + 1 current)
    assert detect_monthly_weakness([100, 95, 90]) is False


from scripts.memory_cycle_monitor import compute_s3_lights


def test_s3_green_when_mu_not_weak():
    # MU strong → green regardless of others
    r = compute_s3_lights(mu_weak=False, hynix_weak=True, tw_weak=True)
    assert r.light == GREEN


def test_s3_yellow_when_only_mu_weak():
    r = compute_s3_lights(mu_weak=True, hynix_weak=False, tw_weak=False)
    assert r.light == YELLOW


def test_s3_red_when_mu_and_hynix_weak_tw_strong():
    r = compute_s3_lights(mu_weak=True, hynix_weak=True, tw_weak=False)
    assert r.light == RED


def test_s3_yellow_when_all_three_weak_window_closed():
    # MU + Hynix + TW all weak → lead window closed → YELLOW per spec
    r = compute_s3_lights(mu_weak=True, hynix_weak=True, tw_weak=True)
    assert r.light == YELLOW


def test_fetch_monthly_closes_returns_list(mocker):
    import pandas as pd
    fake_hist = pd.DataFrame({"Close": [100.0, 102.0, 95.0]})
    fake_ticker = mocker.MagicMock()
    fake_ticker.history.return_value = fake_hist
    mocker.patch("yfinance.Ticker", return_value=fake_ticker)
    from scripts.memory_cycle_monitor import fetch_monthly_closes
    assert fetch_monthly_closes("MU") == [100.0, 102.0, 95.0]


def test_fetch_monthly_closes_returns_empty_on_failure(mocker):
    mocker.patch("yfinance.Ticker", side_effect=RuntimeError("boom"))
    from scripts.memory_cycle_monitor import fetch_monthly_closes
    assert fetch_monthly_closes("MU") == []


from scripts.memory_cycle_monitor import aggregate, advance_state


def _sig(light: str) -> SignalResult:
    return SignalResult(light=light, value="")


def test_aggregate_all_green():
    out = aggregate(s1=_sig(GREEN), s2a=_sig(GREEN), s2b=_sig(GREEN), s3=_sig(GREEN))
    assert out["overall_light"] == GREEN
    assert out["trim_stage_candidate"] == 0


def test_aggregate_s1_yellow_gives_stage_1():
    out = aggregate(s1=_sig(YELLOW), s2a=_sig(GREEN), s2b=_sig(GREEN), s3=_sig(GREEN))
    assert out["overall_light"] == YELLOW
    assert out["trim_stage_candidate"] == 1


def test_aggregate_s3_yellow_gives_stage_2():
    out = aggregate(s1=_sig(GREEN), s2a=_sig(GREEN), s2b=_sig(GREEN), s3=_sig(YELLOW))
    assert out["overall_light"] == YELLOW
    assert out["trim_stage_candidate"] == 2


def test_aggregate_any_red_gives_stage_3():
    out = aggregate(s1=_sig(GREEN), s2a=_sig(RED), s2b=_sig(GREEN), s3=_sig(GREEN))
    assert out["overall_light"] == RED
    assert out["trim_stage_candidate"] == 3


def test_aggregate_takes_max_when_multiple():
    # S1 yellow (cand 1) + S3 yellow (cand 2) → cand 2
    out = aggregate(s1=_sig(YELLOW), s2a=_sig(GREEN), s2b=_sig(GREEN), s3=_sig(YELLOW))
    assert out["trim_stage_candidate"] == 2


def test_advance_state_creates_state_file_when_missing(tmp_path):
    state_file = tmp_path / "state.json"
    out = advance_state(candidate=1, state_path=state_file)
    assert out["stage"] == 1
    assert out["max_stage_seen"] == 1
    assert state_file.exists()


def test_advance_state_monotonic_does_not_regress(tmp_path):
    state_file = tmp_path / "state.json"
    advance_state(candidate=2, state_path=state_file)
    out = advance_state(candidate=1, state_path=state_file)
    assert out["stage"] == 2  # never goes back down


def test_advance_state_records_first_seen_at(tmp_path):
    state_file = tmp_path / "state.json"
    out = advance_state(candidate=2, state_path=state_file, today="2026-07-15")
    assert out["max_stage_first_seen_at"] == "2026-07-15"
    # second call with same candidate → first_seen_at unchanged
    out2 = advance_state(candidate=2, state_path=state_file, today="2026-08-01")
    assert out2["max_stage_first_seen_at"] == "2026-07-15"


from scripts.memory_cycle_monitor import render_markdown


def test_markdown_contains_required_sections():
    s1 = SignalResult(GREEN, "2408.TW=1.42(p40), 2344.TW=1.12(p30)",
                      {"2408.TW": {"pb": 1.42, "percentile": 40, "p70": 5.0, "p85": 6.5,
                                   "as_of": "2026-06-25", "source": "cache", "light": GREEN},
                       "2344.TW": {"pb": 1.12, "percentile": 30, "p70": 4.0, "p85": 5.5,
                                   "as_of": "2026-06-25", "source": "cache", "light": GREEN}})
    s2a = SignalResult(GREEN, "+10.6%", {"mom_pct": 10.6})
    s2b = SignalResult(GREEN, "+21.4%", {"qoq_pct": 21.4, "decay_pct": None})
    s3 = SignalResult(GREEN, "MU not weak",
                      {"mu_weak": False, "hynix_weak": False, "tw_weak": False})
    md = render_markdown(
        report_date="2026-06-25",
        overall_light=GREEN,
        trim_stage=0,
        max_stage_seen=0,
        next_trigger="S2a DDR4 首次負 MoM",
        last_updated_yaml="2026-06-25",
        s1=s1, s2a=s2a, s2b=s2b, s3=s3,
    )
    assert "記憶體週期燈號 — 2026-06-25" in md
    assert "S1 — 兩檔估值溢價" in md
    assert "S2 — DRAM 報價動能" in md
    assert "S3 — 跨市場領先訊號" in md
    assert "1.42" in md
    assert "+10.6%" in md
    assert "🟢" in md


def test_markdown_red_when_any_signal_red():
    s1 = SignalResult(RED, "2408.TW=7.20(p98)",
                      {"2408.TW": {"pb": 7.2, "percentile": 98, "p70": 5.0, "p85": 6.5,
                                   "as_of": "2026-06-25", "source": "cache", "light": RED}})
    s2a = SignalResult(GREEN, "+5%")
    s2b = SignalResult(GREEN, "+15%")
    s3 = SignalResult(GREEN, "ok")
    md = render_markdown(
        report_date="2026-06-25", overall_light=RED, trim_stage=3,
        max_stage_seen=3, next_trigger="-", last_updated_yaml="2026-06-25",
        s1=s1, s2a=s2a, s2b=s2b, s3=s3,
    )
    assert "🔴" in md
    assert "trim 30%" in md or "止損" in md


import fakeredis
from scripts.memory_cycle_monitor import publish_redis


def test_publish_redis_sets_expected_fields():
    r = fakeredis.FakeStrictRedis(decode_responses=True)
    publish_redis(
        client=r,
        hash_name="h:agent:memory_cycle",
        data={
            "updated_at": "2026-06-25T08:15:00+08:00",
            "overall_light": GREEN,
            "trim_stage": 0,
            "s1_pb_2408": 1.42,
            "report_path": "docs/analysis/memory_cycle_2026-06-25.md",
        },
    )
    out = r.hgetall("h:agent:memory_cycle")
    assert out["overall_light"] == "GREEN"
    assert out["trim_stage"] == "0"
    assert out["s1_pb_2408"] == "1.42"


def test_publish_redis_handles_none_as_empty_string():
    r = fakeredis.FakeStrictRedis(decode_responses=True)
    publish_redis(client=r, hash_name="h:test", data={"x": None})
    assert r.hget("h:test", "x") == ""


def _fake_pb_lights(**overrides):
    base = {
        "2408.TW": _pb_rec(GREEN, 1.42, percentile=40, p70=5.0, p85=6.5),
        "2344.TW": _pb_rec(GREEN, 1.12, percentile=30, p70=4.0, p85=5.5),
    }
    base.update(overrides)
    return base


def test_main_dry_run_does_not_write_files(tmp_path, mocker, capsys):
    """--dry-run prints to stdout, writes no files, makes no Redis call."""
    mocker.patch("scripts.memory_cycle_monitor.make_redis_client",
                 return_value=object())
    mocker.patch("scripts.memory_cycle_monitor.s1_lights_with_fallback",
                 return_value=_fake_pb_lights())
    mocker.patch(
        "scripts.memory_cycle_monitor.fetch_monthly_closes",
        return_value=[100.0, 102.0, 105.0, 108.0, 110.0],  # not weak
    )
    inputs_path = FIXTURES / "memory_cycle_full.yaml"
    state_path = tmp_path / "state.json"

    from scripts.memory_cycle_monitor import main
    rc = main([
        "--dry-run",
        "--inputs", str(inputs_path),
        "--state", str(state_path),
        "--report-dir", str(tmp_path / "reports"),
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "記憶體週期燈號" in captured.out
    assert not (tmp_path / "reports").exists()
    assert not state_path.exists()


import json


def test_integration_full_pipeline_writes_markdown_and_redis(tmp_path, mocker):
    """Full pipeline:
    - YAML fixture (full 3-quarter)
    - Mocked yfinance (P/B + monthly closes for MU/Hynix/2408/2344)
    - fakeredis as Redis client
    - Asserts Markdown file written + Redis hash populated
    """
    # Publish the pb_lights hash into a fakeredis instance, then let the monitor
    # read it back through its real read path (make_redis_client → read_pb_lights).
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    fake.hset("h:agent:pb_lights", mapping={
        "2408": _json.dumps(_pb_rec(GREEN, 1.42, percentile=40, p70=5.0, p85=6.5)),
        "2344": _json.dumps(_pb_rec(GREEN, 1.12, percentile=30, p70=4.0, p85=5.5)),
    })
    # All upward-trending closes → no weakness anywhere
    mocker.patch("scripts.memory_cycle_monitor.fetch_monthly_closes",
                 return_value=[100, 102, 105, 108, 110])

    # Patch Redis client factory to return the same fakeredis instance
    mocker.patch("scripts.memory_cycle_monitor.make_redis_client", return_value=fake)

    from scripts.memory_cycle_monitor import main, REDIS_HASH

    state_path = tmp_path / "state.json"
    report_dir = tmp_path / "reports"
    inputs_path = FIXTURES / "memory_cycle_full.yaml"

    rc = main([
        "--inputs", str(inputs_path),
        "--state", str(state_path),
        "--report-dir", str(report_dir),
    ])
    assert rc == 0

    # Markdown written
    md_files = list(report_dir.glob("memory_cycle_*.md"))
    assert len(md_files) == 1
    md = md_files[0].read_text()
    assert "S1 — 兩檔估值溢價" in md
    assert "1.42" in md
    assert "🟢" in md  # all-green path

    # Redis hash populated
    redis_data = fake.hgetall(REDIS_HASH)
    assert redis_data["overall_light"] == "GREEN"
    assert redis_data["trim_stage"] == "0"
    assert redis_data["s1_pb_2408"] == "1.42"
    assert redis_data["s1_pb_2408_percentile"] == "40"
    assert redis_data["s1_pb_2408_p70"] == "5.0"
    assert redis_data["s1_pb_2408_p85"] == "6.5"
    assert "memory_cycle_" in redis_data["report_path"]

    # State file created
    assert state_path.exists()
    state = json.loads(state_path.read_text())
    assert state["max_stage_seen"] == 0


def test_integration_no_redis_flag_skips_redis(tmp_path, mocker):
    # Reads still go through make_redis_client → provide a fake hash client, but
    # the WRITE path (publish_redis) must not be invoked under --no-redis.
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    fake.hset("h:agent:pb_lights", mapping={
        "2408": _json.dumps(_pb_rec(GREEN, 1.42, percentile=40, p70=5.0, p85=6.5)),
        "2344": _json.dumps(_pb_rec(GREEN, 1.12, percentile=30, p70=4.0, p85=5.5)),
    })
    mocker.patch("scripts.memory_cycle_monitor.make_redis_client", return_value=fake)
    mocker.patch("scripts.memory_cycle_monitor.fetch_monthly_closes",
                 return_value=[100, 102, 105, 108, 110])
    boom = mocker.patch("scripts.memory_cycle_monitor.publish_redis",
                        side_effect=AssertionError("publish must not run under --no-redis"))

    from scripts.memory_cycle_monitor import main
    rc = main([
        "--no-redis",
        "--inputs", str(FIXTURES / "memory_cycle_full.yaml"),
        "--state", str(tmp_path / "state.json"),
        "--report-dir", str(tmp_path / "reports"),
    ])
    assert rc == 0  # no Redis attempted, no error


def test_main_returns_1_on_invalid_yaml(tmp_path, mocker):
    """rc=1 when YAML is malformed/missing required field."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("notes: 'missing last_updated'\n")
    from scripts.memory_cycle_monitor import main
    rc = main([
        "--inputs", str(bad_yaml),
        "--state", str(tmp_path / "state.json"),
        "--report-dir", str(tmp_path / "reports"),
        "--no-redis",
    ])
    assert rc == 1


def test_main_returns_2_when_all_pb_lights_none(tmp_path, mocker):
    """rc=2 when neither the hash nor engine-A fallback yields a light."""
    mocker.patch("scripts.memory_cycle_monitor.make_redis_client",
                 return_value=object())
    mocker.patch("scripts.memory_cycle_monitor.s1_lights_with_fallback",
                 return_value={"2408.TW": None, "2344.TW": None})
    mocker.patch("scripts.memory_cycle_monitor.fetch_monthly_closes",
                 return_value=[100, 102, 105, 108, 110])
    from scripts.memory_cycle_monitor import main
    rc = main([
        "--inputs", str(FIXTURES / "memory_cycle_full.yaml"),
        "--state", str(tmp_path / "state.json"),
        "--report-dir", str(tmp_path / "reports"),
        "--no-redis",
    ])
    assert rc == 2


def test_main_returns_3_when_redis_push_fails(tmp_path, mocker):
    """rc=3 when the Redis WRITE (publish_redis) raises after markdown is written.

    Reads succeed (fake hash client with lights); only the publish path fails.
    """
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    fake.hset("h:agent:pb_lights", mapping={
        "2408": _json.dumps(_pb_rec(GREEN, 1.42, percentile=40, p70=5.0, p85=6.5)),
        "2344": _json.dumps(_pb_rec(GREEN, 1.12, percentile=30, p70=4.0, p85=5.5)),
    })
    mocker.patch("scripts.memory_cycle_monitor.make_redis_client", return_value=fake)
    mocker.patch("scripts.memory_cycle_monitor.fetch_monthly_closes",
                 return_value=[100, 102, 105, 108, 110])
    mocker.patch("scripts.memory_cycle_monitor.publish_redis",
                 side_effect=ConnectionRefusedError("simulated Redis down"))
    from scripts.memory_cycle_monitor import main
    rc = main([
        "--inputs", str(FIXTURES / "memory_cycle_full.yaml"),
        "--state", str(tmp_path / "state.json"),
        "--report-dir", str(tmp_path / "reports"),
    ])
    assert rc == 3
    # Markdown is still written before Redis fails
    md_files = list((tmp_path / "reports").glob("memory_cycle_*.md"))
    assert len(md_files) == 1


from scripts.memory_cycle_monitor import _suggest_next_trigger


def test_suggest_next_trigger_terminal_stage_returns_locked_message():
    """Stage 3 should NOT suggest a 'next' trigger — there's no further stage."""
    s1 = SignalResult(RED, "all red")
    s2a = SignalResult(GREEN, "+10%")   # would otherwise dominate the suggestion
    s2b = SignalResult(RED, "-5%")
    s3 = SignalResult(RED, "weak")
    result = _suggest_next_trigger(s1, s2a, s2b, s3, stage=3)
    assert "全部三段" in result
    assert "state file" in result.lower() or "state file" in result  # mention manual revert
    # Make sure it does NOT suggest a per-signal trigger
    assert "S2a DDR4" not in result
    assert "S2b DDR5" not in result


def test_suggest_next_trigger_non_terminal_unchanged():
    """Stages 0/1/2 retain the existing first-GREEN-wins logic."""
    s1 = SignalResult(GREEN, "")
    s2a = SignalResult(GREEN, "")
    s2b = SignalResult(GREEN, "")
    s3 = SignalResult(GREEN, "")
    assert "S2a DDR4" in _suggest_next_trigger(s1, s2a, s2b, s3, stage=0)


def test_load_inputs_ignores_stray_pb_thresholds(tmp_path):
    # pb_thresholds is no longer a recognized field; presence must not error.
    p = tmp_path / "with_stray.yaml"
    p.write_text("""
last_updated: 2026-06-25
notes: ""
pb_thresholds:
  "2408.TW": {yellow: 5.0, red: 9.0}
""")
    inp = load_inputs(p)  # must not raise
    assert not hasattr(inp, "pb_thresholds")


def test_compute_s1_pb_stores_provenance_in_detail():
    pb_lights = {
        "2408.TW": _pb_rec(GREEN, 1.42, percentile=40, p70=5.0, p85=6.5,
                           source="cache fast-path"),
        "2344.TW": _pb_rec(GREEN, 1.12, percentile=30, p70=4.0, p85=5.5),
    }
    r = compute_s1_pb(pb_lights)
    assert r.detail["2408.TW"]["pb"] == 1.42
    assert r.detail["2408.TW"]["percentile"] == 40
    assert r.detail["2408.TW"]["p70"] == 5.0
    assert r.detail["2408.TW"]["p85"] == 6.5
    assert r.detail["2408.TW"]["source"] == "cache fast-path"
    assert r.detail["2408.TW"]["light"] == GREEN


def test_markdown_verification_log_includes_pb_provenance():
    s1 = SignalResult(GREEN, "ok", {
        "2408.TW": {"pb": 7.56, "percentile": 98, "p70": 5.0, "p85": 6.5,
                    "as_of": "2026-06-25", "source": "engine-A recompute", "light": GREEN},
        "2344.TW": {"pb": 8.35, "percentile": 99, "p70": 4.0, "p85": 5.5,
                    "as_of": "2026-06-25", "source": "cache fast-path", "light": GREEN},
    })
    s2a = SignalResult(GREEN, "+10.6%", {"mom_pct": 10.6})
    s2b = SignalResult(GREEN, "+21.4%", {"qoq_pct": 21.4})
    s3 = SignalResult(GREEN, "ok", {"mu_weak": False, "hynix_weak": False, "tw_weak": False})
    md = render_markdown(
        report_date="2026-06-25", overall_light=GREEN, trim_stage=0, max_stage_seen=0,
        next_trigger="-", last_updated_yaml="2026-06-25",
        s1=s1, s2a=s2a, s2b=s2b, s3=s3,
    )
    assert "## Verification log" in md
    assert "Data pulled at" in md
    assert "h:agent:pb_lights" in md
    assert "P/B 7.56" in md
    assert "percentile p98" in md
    assert "p70=5.00" in md
    assert "p85=6.50" in md
    assert "source engine-A recompute" in md
    assert "as of 2026-06-25" in md
