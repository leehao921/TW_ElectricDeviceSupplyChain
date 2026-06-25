"""Tests for scripts/memory_cycle_monitor.py — DRAM sell-signal monitor."""
from scripts.memory_cycle_monitor import (
    PB_THRESHOLDS,
    Inputs,
    PricePoint,
    SignalResult,
    GREEN, YELLOW, RED,
)


def test_pb_thresholds_match_spec():
    assert PB_THRESHOLDS["2408.TW"] == {"yellow": 1.8, "red": 2.5}
    assert PB_THRESHOLDS["2344.TW"] == {"yellow": 1.5, "red": 2.0}


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


from scripts.memory_cycle_monitor import compute_s1_pb


def test_s1_green_when_both_below_yellow():
    r = compute_s1_pb({"2408.TW": 1.42, "2344.TW": 1.12})
    assert r.light == GREEN


def test_s1_yellow_at_exact_threshold():
    # 2408 at 1.80 → yellow (>= threshold)
    r = compute_s1_pb({"2408.TW": 1.80, "2344.TW": 1.10})
    assert r.light == YELLOW
    # 2344 at 1.50 → yellow
    r2 = compute_s1_pb({"2408.TW": 1.10, "2344.TW": 1.50})
    assert r2.light == YELLOW


def test_s1_red_above_extreme():
    r = compute_s1_pb({"2408.TW": 2.51, "2344.TW": 1.10})
    assert r.light == RED


def test_s1_takes_worst_of_two():
    # one green, one red → RED
    r = compute_s1_pb({"2408.TW": 1.10, "2344.TW": 2.05})
    assert r.light == RED


def test_s1_na_when_value_missing():
    r = compute_s1_pb({"2408.TW": None, "2344.TW": 1.10})
    assert r.detail["2408.TW"] == "N/A"
    # but 2344 still computes → overall takes worst-known
    assert r.light in (GREEN, "N/A")  # 2344 is green; 2408 unknown → at minimum green-from-known


def test_fetch_pb_returns_value_from_info(mocker):
    fake_ticker = mocker.MagicMock()
    fake_ticker.info = {"priceToBook": 1.42}
    mocker.patch("yfinance.Ticker", return_value=fake_ticker)
    from scripts.memory_cycle_monitor import fetch_pb
    assert fetch_pb("2408.TW") == 1.42


def test_fetch_pb_returns_none_on_exception(mocker):
    mocker.patch("yfinance.Ticker", side_effect=RuntimeError("network"))
    from scripts.memory_cycle_monitor import fetch_pb
    assert fetch_pb("2408.TW") is None


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
    s1 = SignalResult(GREEN, "2408=1.42, 2344=1.12",
                      {"2408.TW": {"pb": 1.42, "light": GREEN},
                       "2344.TW": {"pb": 1.12, "light": GREEN}})
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
    s1 = SignalResult(RED, "2408=2.60", {"2408.TW": {"pb": 2.6, "light": RED}})
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


def test_main_dry_run_does_not_write_files(tmp_path, mocker, capsys):
    """--dry-run prints to stdout, writes no files, makes no Redis call."""
    # Mock yfinance — return safe defaults
    mocker.patch("scripts.memory_cycle_monitor.fetch_pb", return_value=1.42)
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
