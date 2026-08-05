# -*- coding: utf-8 -*-
"""Tests for scripts/disposition_backtest.py (pure layers)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from disposition_backtest import (  # noqa: E402
    forward_return,
    parse_episodes,
    roc_date,
    window_flow,
)


class TestRocDate:
    def test_basic(self):
        assert roc_date("115/08/03") == "2026-08-03"

    def test_bad(self):
        assert roc_date("garbage") is None


class TestParseEpisodes:
    FIELDS = ["編號", "公布日期", "證券代號", "證券名稱", "累計", "原因", "處置期間", "處置次數", "內容"]

    def _row(self, code, period="115/07/01～115/07/14"):
        return [1, "115/06/30", code, "測試", 1, "連續三次", period, "第一次處置", "x"]

    def test_stock_code_kept_warrant_dropped(self):
        eps = parse_episodes(self.FIELDS, [self._row("2330"), self._row("039457")])
        assert len(eps) == 1
        assert eps[0]["code"] == "2330"

    def test_period_parsed(self):
        eps = parse_episodes(self.FIELDS, [self._row("2330")])
        assert eps[0]["start"] == "2026-07-01"
        assert eps[0]["end"] == "2026-07-14"

    def test_malformed_period_skipped(self):
        eps = parse_episodes(self.FIELDS, [self._row("2330", period="whatever")])
        assert eps == []


SERIES = [("2026-07-%02d" % d, 100.0 + d) for d in range(1, 29)]  # 連續「交易日」


class TestForwardReturn:
    def test_five_day_return(self):
        r = forward_return(SERIES, "2026-07-14", horizon=5)
        # t0=07-14 close 114 → +5 個交易日 07-19 close 119
        assert abs(r - (119.0 / 114.0 - 1)) < 1e-9

    def test_release_on_non_trading_day_uses_prior(self):
        series = [(d, c) for d, c in SERIES if d != "2026-07-14"]
        r = forward_return(series, "2026-07-14", horizon=5)
        # t0 落到 07-13 (113), +5 個交易日 = 07-19 (119)
        assert abs(r - (119.0 / 113.0 - 1)) < 1e-9

    def test_insufficient_forward_days_none(self):
        assert forward_return(SERIES, "2026-07-27", horizon=5) is None


class TestWindowFlow:
    def test_sums_before_start(self):
        flows = [("2026-07-%02d" % d, float(d)) for d in range(1, 11)]
        # start 07-08 前 5 筆 = 3+4+5+6+7
        assert window_flow(flows, "2026-07-08", days=5, direction="before") == 25.0

    def test_sums_after_end(self):
        flows = [("2026-07-%02d" % d, float(d)) for d in range(1, 11)]
        # end 07-05 後 5 筆 = 6+7+8+9+10
        assert window_flow(flows, "2026-07-05", days=5, direction="after") == 40.0
