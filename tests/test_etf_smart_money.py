"""Tests for the pure aggregation logic of scripts/etf_smart_money.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from etf_smart_money import aggregate_consensus, rotation_delta  # noqa: E402


def test_aggregate_consensus_breadth_and_weights():
    rows = [
        ("00980A", "2330", "台積電", 9.0),
        ("00981A", "2330", "台積電", 10.0),
        ("00982A", "2454", "聯發科", 6.0),
    ]
    r = aggregate_consensus(rows)
    assert r["2330"]["n_etfs"] == 2
    assert r["2330"]["aggw"] == 19.0
    assert r["2330"]["avgw"] == 9.5
    assert r["2330"]["name"] == "台積電"
    assert r["2454"]["n_etfs"] == 1
    assert r["2454"]["aggw"] == 6.0


def test_aggregate_consensus_empty():
    assert aggregate_consensus([]) == {}


def test_rotation_delta_trim_and_exit():
    start = [
        ("00982A", "2330", "台積電", 40.0),
        ("00982A", "6442", "光聖", 7.0),   # will exit
    ]
    end = [
        ("00982A", "2330", "台積電", 30.0),  # trimmed
    ]
    d = rotation_delta(start, end)
    assert d["2330"]["delta"] == -10.0
    assert d["2330"]["n_start"] == 1 and d["2330"]["n_end"] == 1
    # 光聖 sold out -> present at start, absent at end
    assert d["6442"]["delta"] == -7.0
    assert d["6442"]["n_start"] == 1 and d["6442"]["n_end"] == 0
    assert d["6442"]["w_end"] == 0.0


def test_rotation_delta_new_position():
    start = []
    end = [("00982A", "6187", "萬潤", 3.6), ("00991A", "6187", "萬潤", 2.0)]
    d = rotation_delta(start, end)
    assert d["6187"]["n_start"] == 0 and d["6187"]["n_end"] == 2
    assert d["6187"]["w_start"] == 0.0
    assert round(d["6187"]["delta"], 1) == 5.6


class TestPushInboxReportPath:
    def _capture(self, monkeypatch):
        import subprocess
        calls = []

        class _R:
            returncode = 0
            stdout = "1-0"
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _R())
        return calls

    def test_report_path_in_fields(self, monkeypatch):
        from etf_smart_money import push_to_inbox
        calls = self._capture(monkeypatch)
        assert push_to_inbox("摘要", "2026-07-30", report_path="analysis/etf_smart_money_2026-07-30.md")
        assert "report_path" in calls[0]
        assert "analysis/etf_smart_money_2026-07-30.md" in calls[0]

    def test_no_report_path_omitted(self, monkeypatch):
        from etf_smart_money import push_to_inbox
        calls = self._capture(monkeypatch)
        assert push_to_inbox("摘要", "2026-07-30")
        assert "report_path" not in calls[0]
