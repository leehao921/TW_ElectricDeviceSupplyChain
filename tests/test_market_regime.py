# -*- coding: utf-8 -*-
"""Tests for scripts/market_regime.py — 量能 regime gate (alpha #4)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import market_regime as mr  # noqa: E402


def _rows(vals_taiex):
    # vals_taiex: [(date, value兆, taiex)]
    return [{"date": d, "value": v * 1e12, "taiex": t} for d, v, t in vals_taiex]


class TestParseFmtqik:
    def test_roc_date_and_commas(self):
        raw = {"data": [["115/08/04", "11,340,636,777", "1,087,045,875,836",
                         "4,751,347", "43,360.66", "-25.75"]]}
        rows = mr.parse_fmtqik(raw)
        assert rows == [{"date": "2026-08-04", "value": 1087045875836.0,
                         "taiex": 43360.66}]

    def test_empty_or_missing_data(self):
        assert mr.parse_fmtqik({}) == []
        assert mr.parse_fmtqik({"data": []}) == []


class TestClassify:
    def test_normal(self):
        rows = _rows([("2026-08-0%d" % i, 1.3, 44000) for i in range(1, 6)])
        out = mr.classify_regime(rows, line=39385)
        assert out["regime"] == "normal"
        assert out["turnover_5d"] == 1.3e12

    def test_low_volume(self):
        rows = _rows([("2026-08-0%d" % i, 0.85, 44000) for i in range(1, 6)])
        out = mr.classify_regime(rows, line=39385)
        assert out["regime"] == "low_volume"

    def test_broken_overrides_low_volume(self):
        rows = _rows([("2026-08-0%d" % i, 0.7, 39000) for i in range(1, 6)])
        out = mr.classify_regime(rows, line=39385)
        assert out["regime"] == "broken"

    def test_uses_last_5_only(self):
        rows = _rows([("2026-07-2%d" % i, 3.0, 44000) for i in range(1, 5)]
                     + [("2026-08-0%d" % i, 0.8, 44000) for i in range(1, 6)])
        out = mr.classify_regime(rows, line=39385)
        assert out["regime"] == "low_volume"


class TestBanner:
    def test_normal_no_banner(self):
        assert mr.banner({"regime": "normal"}) is None

    def test_low_volume_banner(self):
        b = mr.banner({"regime": "low_volume", "turnover_5d": 0.87e12,
                       "taiex": 44559.0, "line": 39385})
        assert "量縮" in b and "0.87" in b and "降權" in b

    def test_broken_banner(self):
        b = mr.banner({"regime": "broken", "turnover_5d": 0.7e12,
                       "taiex": 39000.0, "line": 39385})
        assert "已破" in b


class TestGetRegimeCache:
    def test_cache_hit_no_fetch(self, tmp_path, monkeypatch):
        cache = tmp_path / "regime.json"
        cached = {"as_of": mr.today_str(), "regime": "normal", "turnover_5d": 1.2e12,
                  "taiex": 44000.0, "line": 39385}
        cache.write_text(json.dumps(cached), encoding="utf-8")
        monkeypatch.setattr(mr, "fetch_months", lambda: (_ for _ in ()).throw(AssertionError("should not fetch")))
        assert mr.get_regime(cache_path=cache) == cached

    def test_stale_cache_refetches(self, tmp_path, monkeypatch):
        cache = tmp_path / "regime.json"
        cache.write_text(json.dumps({"as_of": "2020-01-01", "regime": "normal"}), encoding="utf-8")
        monkeypatch.setattr(mr, "fetch_months",
                            lambda: _rows([("2026-08-0%d" % i, 1.5, 44000) for i in range(1, 6)]))
        out = mr.get_regime(cache_path=cache)
        assert out["regime"] == "normal"
        assert out["as_of"] == mr.today_str()
        assert json.loads(cache.read_text(encoding="utf-8"))["regime"] == "normal"

    def test_fetch_failure_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mr, "fetch_months", lambda: (_ for _ in ()).throw(RuntimeError("net down")))
        assert mr.get_regime(cache_path=tmp_path / "none.json") is None
