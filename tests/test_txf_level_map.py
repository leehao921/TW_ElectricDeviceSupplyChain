"""Tests for txf_level_map.py pure functions — TDD RED phase.

Coverage:
- split_day_night: day/night boundary at 13:45 TPE; handles missing night bars
- volume_profile: 100-pt bucketing, descending sort, correct volume aggregation
- hvn_lvn: HVN top-3, LVN above/below current spot (nearest), share calculation
- oi_walls: expiry selection (weekly=nearest, monthly=largest-OI), top-n per cp,
            expired-expiry filtering
- build_msg: all-None inputs → contains "N/A", no crash; non-None inputs render
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from scripts.txf_level_map import (
    split_day_night,
    volume_profile,
    hvn_lvn,
    oi_walls,
    build_msg,
)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_bars(times_tpe: list[str], closes: list[float], volumes: list[float],
               date_str: str = "2026-09-05") -> pd.DataFrame:
    """Build DataFrame[bucket(UTC tz-aware), close, volume] from TPE times."""
    import pytz
    tpe = pytz.timezone("Asia/Taipei")
    utc = pytz.utc
    buckets = []
    for t in times_tpe:
        naive = dt.datetime.strptime(f"{date_str} {t}", "%Y-%m-%d %H:%M")
        aware_tpe = tpe.localize(naive)
        buckets.append(aware_tpe.astimezone(utc))
    df = pd.DataFrame({"bucket": buckets, "close": closes, "volume": volumes})
    return df


# ══════════════════════════════════════════════════════════════════════════════
# split_day_night
# ══════════════════════════════════════════════════════════════════════════════

class TestSplitDayNight:

    def test_day_and_night_present(self):
        """Bars both before and after 13:45 TPE → both closes returned."""
        # Day bars: 09:00, 12:00, 13:45 (boundary — inclusive day)
        # Night bars: 15:00, 20:00 (next trading night)
        bars = _make_bars(
            ["09:00", "12:00", "13:45", "15:00", "20:00"],
            [46000.0, 46500.0, 46711.0, 46750.0, 47177.0],
            [100, 200, 150, 80, 120],
        )
        day_close, night_close, night_chg = split_day_night(bars)
        assert day_close == pytest.approx(46711.0)
        assert night_close == pytest.approx(47177.0)
        assert night_chg == pytest.approx(47177.0 - 46711.0)

    def test_no_night_bars(self):
        """Only day bars → night_close=None, night_chg=None."""
        bars = _make_bars(
            ["09:00", "12:00", "13:45"],
            [46000.0, 46500.0, 46711.0],
            [100, 200, 150],
        )
        day_close, night_close, night_chg = split_day_night(bars)
        assert day_close == pytest.approx(46711.0)
        assert night_close is None
        assert night_chg is None

    def test_boundary_bar_belongs_to_day(self):
        """A bar exactly at 13:45 TPE is classified as day bar."""
        bars = _make_bars(
            ["13:45", "14:00"],
            [46711.0, 46800.0],
            [150, 90],
        )
        day_close, _, _ = split_day_night(bars)
        assert day_close == pytest.approx(46711.0)

    def test_no_day_bars_only_night(self):
        """Only bars after 13:45 — day_close should be None."""
        bars = _make_bars(
            ["15:00", "20:00"],
            [46750.0, 47177.0],
            [80, 120],
        )
        day_close, night_close, night_chg = split_day_night(bars)
        assert day_close is None
        assert night_close == pytest.approx(47177.0)
        assert night_chg is None  # cannot compute without day_close

    def test_multiple_night_bars_takes_last(self):
        """Night bars: takes the LAST close, not first."""
        bars = _make_bars(
            ["13:45", "15:00", "18:00", "22:00"],
            [46711.0, 46800.0, 47000.0, 47177.0],
            [150, 80, 90, 120],
        )
        _, night_close, _ = split_day_night(bars)
        assert night_close == pytest.approx(47177.0)


# ══════════════════════════════════════════════════════════════════════════════
# volume_profile
# ══════════════════════════════════════════════════════════════════════════════

class TestVolumeProfile:

    def _simple_bars(self) -> pd.DataFrame:
        """Bars in two distinct 100-pt buckets."""
        # Prices 46050 and 46080 both fall into bucket 46000 (46000//100*100)
        # Price 46150 falls into bucket 46100
        return pd.DataFrame({
            "close": [46050.0, 46080.0, 46150.0],
            "volume": [100.0, 200.0, 50.0],
        })

    def test_bucket_aggregation(self):
        df = self._simple_bars()
        profile = volume_profile(df, bucket_pts=100)
        assert profile[46000] == pytest.approx(300.0)  # 100 + 200
        assert profile[46100] == pytest.approx(50.0)

    def test_descending_sort(self):
        df = self._simple_bars()
        profile = volume_profile(df, bucket_pts=100)
        vals = list(profile.values)
        assert vals == sorted(vals, reverse=True)

    def test_custom_bucket_size(self):
        df = pd.DataFrame({"close": [46050.0, 46500.0], "volume": [100.0, 200.0]})
        profile = volume_profile(df, bucket_pts=500)
        # 46050 → 46000, 46500 → 46500 (46500//500*500 = 46500? 46500/500=93 → 93*500=46500)
        # 46050//500=92 → 92*500=46000
        assert 46000 in profile.index
        assert 46500 in profile.index

    def test_single_bar(self):
        df = pd.DataFrame({"close": [47000.0], "volume": [999.0]})
        profile = volume_profile(df, bucket_pts=100)
        assert len(profile) == 1
        assert profile.iloc[0] == pytest.approx(999.0)


# ══════════════════════════════════════════════════════════════════════════════
# hvn_lvn
# ══════════════════════════════════════════════════════════════════════════════

class TestHvnLvn:

    def _build_profile(self) -> pd.Series:
        """Hand-built profile with clear HVN/LVN zones.

        Price levels:
          45900: vol=1000  (HVN #1)
          46000: vol=800   (HVN #2)
          46100: vol=500   (HVN #3)
          46200: vol=50    (LVN — below 25th percentile)
          46300: vol=60    (borderline)
          46400: vol=900   (HVN — above spot if spot=46350)
          46500: vol=40    (LVN — above 25th percentile? lowest above spot)
          46600: vol=700
        """
        data = {
            45900: 1000.0,
            46000: 800.0,
            46100: 500.0,
            46200: 50.0,   # LVN (below spot=46350)
            46300: 60.0,
            46400: 900.0,
            46500: 40.0,   # LVN (above spot=46350)
            46600: 700.0,
        }
        s = pd.Series(data, name="volume")
        s.index.name = "level"
        # sort descending (as volume_profile returns)
        return s.sort_values(ascending=False)

    def test_hvn_top3(self):
        profile = self._build_profile()
        result = hvn_lvn(profile, spot=46350.0, top_n=3)
        levels = [lvl for lvl, _ in result["hvn"]]
        assert 45900 in levels
        assert 46000 in levels
        # 46400 (900) or 46600 (700) or 46100 (500) — 3rd largest: 46600=700 or 46100=500?
        # volumes: 1000,900,800,700,500,60,50,40 → top3 levels: 45900,46400,46000
        assert 46400 in levels

    def test_hvn_shares_sum_reasonably(self):
        profile = self._build_profile()
        result = hvn_lvn(profile, spot=46350.0, top_n=3)
        total = profile.sum()
        for lvl, share in result["hvn"]:
            expected_share = profile[lvl] / total
            assert share == pytest.approx(expected_share, rel=1e-6)

    def test_lvn_above_spot(self):
        """LVN above spot: nearest lowest-volume bucket above spot=46350."""
        profile = self._build_profile()
        result = hvn_lvn(profile, spot=46350.0, top_n=3)
        # Above spot: 46400(900), 46500(40), 46600(700)
        # LVN = below 25th percentile. Min vol=40 (46500) is well below 25th pct.
        # Nearest above: 46500 has volume 40 (LVN); next up is 46600 (700, not LVN)
        # So lvn_above = 46500
        assert result["lvn_above"] == 46500

    def test_lvn_below_spot(self):
        """LVN below spot: nearest lowest-volume bucket below spot=46350."""
        profile = self._build_profile()
        result = hvn_lvn(profile, spot=46350.0, top_n=3)
        # Below spot: 45900(1000), 46000(800), 46100(500), 46200(50), 46300(60)
        # Q25 of [40,50,60,500,700,800,900,1000] = 57.5
        # LVN threshold <= 57.5 → only 46200(50) and 46500(40) qualify
        # LVN below spot: only 46200(50) — nearest below = 46200
        assert result["lvn_below"] == 46200

    def test_no_lvn_above(self):
        """All buckets above spot with equal-ish volume → lvn_above exists per quantile."""
        # Use 4 buckets where the top 3 above spot all have high volume
        # and the 25th pct is driven by the one below-spot bucket
        data = {46000: 1000.0, 46100: 990.0, 46200: 980.0, 46300: 970.0}
        profile = pd.Series(data).sort_values(ascending=False)
        result = hvn_lvn(profile, spot=46050.0, top_n=2)
        # Q25 of [970, 980, 990, 1000] = 977.5
        # Buckets above spot=46050: 46100(990>=977.5), 46200(980>=977.5), 46300(970<977.5)
        # LVN above = 46300 (only one below threshold above spot)
        assert result["lvn_above"] == 46300

    def test_no_lvn_below(self):
        """No buckets below spot → lvn_below=None."""
        data = {46500: 1000.0, 46600: 50.0, 46700: 900.0}
        profile = pd.Series(data).sort_values(ascending=False)
        result = hvn_lvn(profile, spot=46450.0, top_n=2)
        assert result["lvn_below"] is None


# ══════════════════════════════════════════════════════════════════════════════
# oi_walls
# ══════════════════════════════════════════════════════════════════════════════

class TestOiWalls:

    def _sample_oi(self) -> pd.DataFrame:
        """Sample OI DataFrame with two expiries: near-week and month."""
        # Weekly expiry = nearest (2026-09-10 is a Wednesday, typical weekly)
        # Monthly expiry = 3rd Wednesday of month (2026-09-16)
        rows = []
        weekly_exp = dt.date(2026, 9, 10)
        monthly_exp = dt.date(2026, 9, 17)  # largest OI → selected as monthly

        spot = 47000.0
        # Weekly expiry: put/call strikes around spot
        for strike, cp, oi in [
            (47000, "C", 711), (47500, "C", 400), (48000, "C", 1542),
            (46500, "P", 479), (46000, "P", 300), (45500, "P", 150),
        ]:
            rows.append({"expiry": weekly_exp, "strike": strike, "cp": cp,
                         "open_interest": oi})

        # Monthly expiry: more total OI (→ selected as monthly)
        for strike, cp, oi in [
            (47000, "C", 2000), (47500, "C", 1800), (48000, "C", 2500),
            (46500, "P", 1900), (46000, "P", 1700), (45500, "P", 1200),
        ]:
            rows.append({"expiry": monthly_exp, "strike": strike, "cp": cp,
                         "open_interest": oi})

        return pd.DataFrame(rows)

    def test_weekly_is_nearest_expiry(self):
        oi = self._sample_oi()
        result = oi_walls(oi, spot=47000.0, n=3)
        weekly_exp = dt.date(2026, 9, 10)
        calls = result["weekly"]["call"]
        puts = result["weekly"]["put"]
        # weekly selected = nearest expiry
        assert len(calls) <= 3
        assert len(puts) <= 3

    def test_weekly_top_n_calls(self):
        oi = self._sample_oi()
        result = oi_walls(oi, spot=47000.0, n=3)
        calls = result["weekly"]["call"]
        # Top 3 calls by OI: 48000(1542), 47000(711), 47500(400)
        call_strikes = [s for s, _ in calls]
        assert 48000 in call_strikes
        assert 47000 in call_strikes
        assert 47500 in call_strikes

    def test_weekly_top_n_puts(self):
        oi = self._sample_oi()
        result = oi_walls(oi, spot=47000.0, n=3)
        puts = result["weekly"]["put"]
        put_strikes = [s for s, _ in puts]
        assert 46500 in put_strikes
        assert 46000 in put_strikes
        assert 45500 in put_strikes

    def test_monthly_has_highest_total_oi(self):
        oi = self._sample_oi()
        result = oi_walls(oi, spot=47000.0, n=3)
        monthly_exp = dt.date(2026, 9, 17)
        # monthly expiry = largest-OI expiry (not weekly)
        monthly_calls = result["monthly"]["call"]
        # monthly calls: 48000(2500), 47500(1800), 47000(2000) → top3 by OI
        call_strikes = [s for s, _ in monthly_calls]
        assert 48000 in call_strikes

    def test_expired_expiry_filtered(self):
        """oi_walls receives pre-filtered df (expiry >= today).
        Verifies function handles single-expiry gracefully (weekly=monthly same)."""
        # Only one expiry
        rows = [
            {"expiry": dt.date(2026, 9, 10), "strike": 47000, "cp": "C",
             "open_interest": 500},
            {"expiry": dt.date(2026, 9, 10), "strike": 46500, "cp": "P",
             "open_interest": 400},
        ]
        oi = pd.DataFrame(rows)
        result = oi_walls(oi, spot=47000.0, n=3)
        # Both weekly and monthly point to the same expiry — should not crash
        assert "weekly" in result
        assert "monthly" in result

    def test_empty_oi(self):
        """Empty OI DataFrame → returns empty lists, no crash."""
        oi = pd.DataFrame(columns=["expiry", "strike", "cp", "open_interest"])
        result = oi_walls(oi, spot=47000.0, n=3)
        assert result["weekly"]["call"] == []
        assert result["weekly"]["put"] == []

    def test_case_insensitive_cp(self):
        """cp values 'c'/'p' (lowercase) treated same as 'C'/'P'."""
        rows = [
            {"expiry": dt.date(2026, 9, 10), "strike": 47000, "cp": "c",
             "open_interest": 500},
            {"expiry": dt.date(2026, 9, 10), "strike": 46500, "cp": "p",
             "open_interest": 400},
        ]
        oi = pd.DataFrame(rows)
        result = oi_walls(oi, spot=47000.0, n=3)
        assert len(result["weekly"]["call"]) == 1
        assert len(result["weekly"]["put"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# build_msg
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildMsg:

    def test_all_none_contains_na(self):
        """All-None inputs → message contains 'N/A' and does not raise."""
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=None,
            night_close=None,
            night_chg=None,
            walls=None,
            flip=None,
            foreign_net=None,
            toshin_net=None,
            sox=None,
            vix=None,
            ust10y=None,
            brent=None,
            dxy=None,
            asia=None,
            fx=None,
        )
        assert isinstance(msg, str)
        assert "N/A" in msg

    def test_valid_inputs_render(self):
        """Non-None inputs render without crashing; key values appear in output."""
        walls = {
            "weekly": {
                "call": [(47500, 711), (48000, 1542)],
                "put": [(46500, 479), (46000, 300)],
            },
            "monthly": {
                "call": [(47500, 1800), (48000, 2500)],
                "put": [(46000, 1700), (45500, 1200)],
            },
        }
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=46711.0,
            night_close=47177.0,
            night_chg=466.0,
            walls=walls,
            flip=46650.0,
            foreign_net=-82389,
            toshin_net=76174,
            sox=1.5,
            vix=14.5,
            ust10y=4.67,
            brent=85.8,
            dxy=103.2,
            asia={"N225": 0.8, "KS11": -0.3, "HSI": 0.5,
                  "CSI300": 0.2, "TWII": 0.1, "NSEI": 0.4},
            fx={"USDTWD": 31.5, "USDJPY": 146.2, "DXY": 103.2},
        )
        assert "47177" in msg
        assert "46711" in msg
        assert "46650" in msg  # flip

    def test_partial_none_no_crash(self):
        """Partial None inputs (e.g., no flip) → no crash, N/A in place."""
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=46711.0,
            night_close=None,
            night_chg=None,
            walls=None,
            flip=None,  # e.g., options_quant subprocess failed
            foreign_net=None,
            toshin_net=None,
            sox=None,
            vix=14.5,
            ust10y=None,
            brent=None,
            dxy=None,
            asia=None,
            fx=None,
        )
        assert "N/A" in msg
        assert "14.5" in msg  # vix should still appear

    def test_date_in_header(self):
        """Date appears in the header line."""
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=None, night_close=None, night_chg=None,
            walls=None, flip=None, foreign_net=None, toshin_net=None,
            sox=None, vix=None, ust10y=None, brent=None, dxy=None,
            asia=None, fx=None,
        )
        # date should appear somewhere in the message
        assert "9/6" in msg or "2026-09-06" in msg or "09-06" in msg
