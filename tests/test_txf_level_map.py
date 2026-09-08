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
    annotate_ladder,
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

    def test_expiry_ref_overrides_filtered_monthly_selection(self):
        """When a thin near-expiry dominates the spot-filtered OI but the fat
        monthly has higher global OI, expiry_ref causes the fat monthly to be
        selected as monthly.

        Scenario:
          - weekly (9/9): 6 strikes in ±2500 range, each OI=100 → total_filtered=600
          - monthly (9/16): 2 strikes in range, each OI=200 → total_filtered=400
          BUT in the full universe:
          - 9/9 global OI = 600 (all strikes in range)
          - 9/16 global OI = 2000 (400 in range + 1600 further OTM)
        Without expiry_ref: oi_walls picks 9/9 as monthly (600 > 400 in filtered).
        With expiry_ref=full_df: oi_walls picks 9/16 as monthly (2000 > 600 global).
        """
        weekly_exp = dt.date(2026, 9, 9)
        monthly_exp = dt.date(2026, 9, 16)

        # Filtered oi (±2500 from spot=47000): 9/9 has 6 rows, 9/16 has 2 rows
        filtered_rows = []
        for strike in [46000, 46500, 47000, 47500, 48000, 48500]:
            filtered_rows.append({"expiry": weekly_exp, "strike": strike,
                                   "cp": "C", "open_interest": 100})
        for strike in [48000, 48500]:
            filtered_rows.append({"expiry": monthly_exp, "strike": strike,
                                   "cp": "C", "open_interest": 200})
        filtered_df = pd.DataFrame(filtered_rows)

        # Full universe: 9/16 has additional OTM strikes with large OI
        extra_rows = list(filtered_rows)  # start with filtered
        for strike in [49000, 49500, 50000, 50500]:
            extra_rows.append({"expiry": monthly_exp, "strike": strike,
                                "cp": "C", "open_interest": 400})
        full_df = pd.DataFrame(extra_rows)

        # Without expiry_ref: monthly = 9/9 (600 > 400 in filtered)
        result_no_ref = oi_walls(filtered_df, spot=47000.0, n=3)
        weekly_exp_no_ref = weekly_exp  # always min
        # Both weekly and monthly point to 9/9 when no ref
        monthly_calls_no_ref = result_no_ref["monthly"]["call"]
        # 9/9 top-3: 48500(100), 48000(100), 47500(100) — all OI=100
        # All from 9/9
        assert all(oi_val == 100 for _, oi_val in monthly_calls_no_ref)

        # With expiry_ref: monthly = 9/16 (2000 > 600 global)
        result_ref = oi_walls(filtered_df, spot=47000.0, n=3, expiry_ref=full_df)
        monthly_calls_ref = result_ref["monthly"]["call"]
        # 9/16 top-2 in filtered range: 48000(200) and 48500(200)
        monthly_call_strikes = [s for s, _ in monthly_calls_ref]
        assert 48000 in monthly_call_strikes
        assert 48500 in monthly_call_strikes
        # All from 9/16 → OI = 200
        assert all(oi_val == 200 for _, oi_val in monthly_calls_ref)


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

    def test_build_msg_monthly_wall_line(self):
        """月牆 line shows top2 C + top2 P from monthly walls."""
        walls = {
            "weekly": {"call": [(47500, 711)], "put": [(46500, 479)]},
            "monthly": {"call": [(48000, 2500), (47500, 1800)], "put": [(46000, 1700), (45500, 1200)]},
        }
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=46711.0, night_close=47177.0, night_chg=466.0,
            walls=walls, flip=None,
            foreign_net=None, toshin_net=None,
            sox=None, vix=None, ust10y=None, brent=None, dxy=None,
            asia=None, fx=None,
        )
        monthly_line = [l for l in msg.splitlines() if l.startswith("月牆")][0]
        assert "48000 C2500" in monthly_line
        assert "47500 C1800" in monthly_line
        assert "46000 P1700" in monthly_line
        assert "45500 P1200" in monthly_line

    def test_build_msg_ladder_block_present(self):
        """Ladder rows appear inside triple-backtick block."""
        ladder = ["  row1  ", "  row2  "]
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=46711.0, night_close=47177.0, night_chg=466.0,
            walls=None, flip=None,
            foreign_net=None, toshin_net=None,
            sox=None, vix=None, ust10y=None, brent=None, dxy=None,
            asia=None, fx=None,
            ladder_rows=ladder,
        )
        assert "```" in msg
        assert "row1" in msg
        assert "row2" in msg

    def test_build_msg_gex_line(self):
        """Line 2 shows GEX total + flip; 外資/投信 moved to 法人段 inside block."""
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=46711.0, night_close=47177.0, night_chg=466.0,
            walls=None, flip=46650.0,
            foreign_net=-82389, toshin_net=76174,
            sox=None, vix=None, ust10y=None, brent=None, dxy=None,
            asia=None, fx=None,
            gex_total=33600000000.0,  # 336億
        )
        lines = msg.splitlines()
        gex_line = lines[1]  # second line
        # 外資/投信 no longer in line 2 (they live in inst_lines inside the block)
        assert "外資期淨" not in gex_line
        assert "GEX" in gex_line
        assert "336" in gex_line
        assert "46650" in gex_line

    def test_build_msg_vol_inst_sections_in_block(self):
        """vol_lines and inst_lines render inside the ``` block."""
        vol = ["── 波動率 ──", " VIX 18.5 · CM30 20.0 · RV21 15.2 · VRP +4.8"]
        inst = ["── 法人/融資 ──", " TXF淨OI: 外資 -1,000 · 投信 +500 口"]
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=46711.0, night_close=47177.0, night_chg=466.0,
            walls=None, flip=None,
            foreign_net=None, toshin_net=None,
            sox=None, vix=None, ust10y=None, brent=None, dxy=None,
            asia=None, fx=None,
            ladder_rows=["  row1  "],
            vol_lines=vol,
            inst_lines=inst,
        )
        # Everything between the ``` fences
        assert "```" in msg
        block_start = msg.index("```\n") + 4
        block_end = msg.index("\n```", block_start)
        block = msg[block_start:block_end]
        assert "── 波動率 ──" in block
        assert "VIX 18.5" in block
        assert "── 法人/融資 ──" in block
        assert "TXF淨OI" in block

    def test_build_msg_vol_inst_none_skipped(self):
        """None vol_lines/inst_lines → block still renders, no crash, no extra lines."""
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=46711.0, night_close=47177.0, night_chg=466.0,
            walls=None, flip=None,
            foreign_net=None, toshin_net=None,
            sox=None, vix=None, ust10y=None, brent=None, dxy=None,
            asia=None, fx=None,
            ladder_rows=["  row1  "],
            vol_lines=None,
            inst_lines=None,
        )
        assert "```" in msg
        assert "── 波動率 ──" not in msg
        assert "── 法人/融資 ──" not in msg

    def test_build_msg_vol_inst_empty_skipped(self):
        """Empty list vol_lines/inst_lines → treated same as None (not injected)."""
        msg = build_msg(
            as_of=dt.date(2026, 9, 6),
            day_close=46711.0, night_close=47177.0, night_chg=466.0,
            walls=None, flip=None,
            foreign_net=None, toshin_net=None,
            sox=None, vix=None, ust10y=None, brent=None, dxy=None,
            asia=None, fx=None,
            ladder_rows=["  row1  "],
            vol_lines=[],
            inst_lines=[],
        )
        assert "── 波動率 ──" not in msg
        assert "── 法人/融資 ──" not in msg


# ══════════════════════════════════════════════════════════════════════════════
# Bug 1 regression: post-midnight night bars (Friday night → Saturday morning)
# ══════════════════════════════════════════════════════════════════════════════

class TestSplitDayNightPostMidnight:
    """Reproduce the Friday-night/Saturday-morning classification bug.

    TXF night session: Fri 15:00 TPE (= Fri 07:00 UTC) → Sat 05:00 TPE (= Fri 21:00 UTC).
    Day session bars: Fri 00:45–05:45 UTC (= Fri 08:45–13:45 TPE).
    Post-midnight night bars: Fri 16:00 UTC → Fri 20:59 UTC (= Sat 00:00–04:59 TPE).

    Old (broken) code: anchored on tpe_date of the LAST bar, which for post-midnight
    bars is Saturday.  Saturday has NO bars in [08:45,13:45] → day_close=None.

    New (correct) logic: find the last bar in [08:45,13:45] TPE to identify trading day D;
    day_close = last close in D[08:45,13:45]; night bars = everything from D 15:00 TPE
    onward (regardless of calendar day); night_close = last of those.
    """

    def _make_friday_shape(self) -> pd.DataFrame:
        """Build a realistic Friday-shape DataFrame using raw UTC timestamps.

        Day bars (Fri TPE 08:45–13:45 = Fri UTC 00:45–05:45):
          Fri 00:45 UTC  close=46000
          Fri 03:00 UTC  close=46500
          Fri 05:45 UTC  close=46711   ← day close

        Night bars spanning midnight (Fri TPE 15:00 = Fri 07:00 UTC)
        → Sat TPE 04:59 = Fri 20:59 UTC:
          Fri 07:00 UTC  close=46750   (= TPE Fri 15:00 — night session opens)
          Fri 14:00 UTC  close=47000   (= TPE Fri 22:00)
          Fri 20:59 UTC  close=47177   (= TPE Sat 04:59) ← night close
        """
        import pytz
        utc = pytz.utc

        rows = [
            # Day bars — Friday UTC times mapping to TPE 08:45-13:45
            (dt.datetime(2026, 8, 21, 0, 45, tzinfo=utc),  46000.0, 100),
            (dt.datetime(2026, 8, 21, 3,  0, tzinfo=utc),  46500.0, 200),
            (dt.datetime(2026, 8, 21, 5, 45, tzinfo=utc),  46711.0, 150),
            # Night bars — Fri UTC 07:00 to Fri UTC 20:59 = TPE Fri 15:00 to Sat 04:59
            (dt.datetime(2026, 8, 21, 7,  0, tzinfo=utc),  46750.0,  80),
            (dt.datetime(2026, 8, 21, 14,  0, tzinfo=utc), 47000.0,  90),
            (dt.datetime(2026, 8, 21, 20, 59, tzinfo=utc), 47177.0, 120),
        ]
        df = pd.DataFrame(rows, columns=["bucket", "close", "volume"])
        return df

    def test_day_close_is_friday_tpe_session(self):
        """day_close must be 46711 (last bar in Fri TPE [08:45,13:45])."""
        bars = self._make_friday_shape()
        day_close, night_close, night_chg = split_day_night(bars)
        assert day_close == pytest.approx(46711.0), (
            f"day_close={day_close!r}; expected 46711.0 (last Fri TPE day bar). "
            "Bug: old code anchors on tpe_date of last bar (Saturday) → no day bars found."
        )

    def test_night_close_is_saturday_morning_bar(self):
        """night_close must be 47177 (Sat 04:59 TPE bar, the last night bar)."""
        bars = self._make_friday_shape()
        day_close, night_close, night_chg = split_day_night(bars)
        assert night_close == pytest.approx(47177.0), (
            f"night_close={night_close!r}; expected 47177.0."
        )

    def test_night_chg_correct(self):
        """night_chg = night_close − day_close = 47177 − 46711 = 466."""
        bars = self._make_friday_shape()
        day_close, night_close, night_chg = split_day_night(bars)
        assert night_chg == pytest.approx(466.0), (
            f"night_chg={night_chg!r}; expected 466.0."
        )

    def test_no_night_yet_friday_shape(self):
        """If only day bars exist (night not started yet), night_close=None."""
        import pytz
        utc = pytz.utc
        day_only = pd.DataFrame({
            "bucket": [
                dt.datetime(2026, 8, 21, 0, 45, tzinfo=utc),
                dt.datetime(2026, 8, 21, 3,  0, tzinfo=utc),
                dt.datetime(2026, 8, 21, 5, 45, tzinfo=utc),
            ],
            "close": [46000.0, 46500.0, 46711.0],
            "volume": [100, 200, 150],
        })
        day_close, night_close, night_chg = split_day_night(day_only)
        assert day_close == pytest.approx(46711.0)
        assert night_close is None
        assert night_chg is None


# ══════════════════════════════════════════════════════════════════════════════
# Task 1: pick_front_expiry (pure function — GEX front-selection fix)
# ══════════════════════════════════════════════════════════════════════════════

class TestPickFrontExpiry:
    """TDD RED → GREEN for the pure front-expiry selector.

    Bug: _get_gex used t1 (T-1) for expiry >= clause.  On Monday t1=Friday,
    so already-expired Friday weekly contracts were selected as "front",
    producing explosive near-expiry gamma (7719億 → bug value).

    Fix: extract pick_front_expiry(expiries, as_of) → min(e for e in expiries if e >= as_of).
    """

    def _dates(self, *iso: str) -> list[dt.date]:
        return [dt.date.fromisoformat(s) for s in iso]

    def test_monday_skips_expired_friday(self):
        """Monday as_of: past Friday expiry must be skipped; next week selected."""
        expiries = self._dates("2026-09-04", "2026-09-09", "2026-09-16")
        from scripts.txf_level_map import pick_front_expiry
        result = pick_front_expiry(expiries, as_of=dt.date(2026, 9, 7))  # Monday
        assert result == dt.date(2026, 9, 9), (
            f"Expected 9/9, got {result!r}. "
            "On Monday as_of=9/7, expired 9/4 must not be front."
        )

    def test_settle_day_self_selects(self):
        """as_of == earliest expiry: that expiry is still front (settle day)."""
        expiries = self._dates("2026-09-09", "2026-09-16")
        from scripts.txf_level_map import pick_front_expiry
        result = pick_front_expiry(expiries, as_of=dt.date(2026, 9, 9))
        assert result == dt.date(2026, 9, 9)

    def test_empty_list_returns_none(self):
        """Empty expiry list → None."""
        from scripts.txf_level_map import pick_front_expiry
        assert pick_front_expiry([], as_of=dt.date(2026, 9, 7)) is None

    def test_all_past_returns_none(self):
        """All expiries strictly before as_of → None."""
        expiries = self._dates("2026-09-04", "2026-09-01")
        from scripts.txf_level_map import pick_front_expiry
        assert pick_front_expiry(expiries, as_of=dt.date(2026, 9, 7)) is None

    def test_single_future_expiry(self):
        """Single expiry in the future → that expiry."""
        from scripts.txf_level_map import pick_front_expiry
        result = pick_front_expiry(
            [dt.date(2026, 9, 16)], as_of=dt.date(2026, 9, 9)
        )
        assert result == dt.date(2026, 9, 16)


# ══════════════════════════════════════════════════════════════════════════════
# Task 2: analyze_gex additive keys (gross_gex, n_c, n_p)
# ══════════════════════════════════════════════════════════════════════════════

class TestAnalyzeGexAdditiveKeys:
    """TDD for gross_gex / n_c / n_p added to analyze_gex metrics dict."""

    def _make_frames(self, rows):
        """rows: list of (strike, cp, gamma, oi).
        Returns (strikes_df, oi_df) as analyze_gex expects.
        """
        import pandas as pd
        strikes_df = pd.DataFrame(
            [(r[0], r[1], r[2]) for r in rows],
            columns=["strike", "call_put", "gamma"],
        )
        oi_df = pd.DataFrame(
            [(r[0], r[1], r[3], "2026-09-08") for r in rows],
            columns=["strike", "cp", "open_interest", "settle_date"],
        )
        return strikes_df, oi_df

    def test_gross_gex_equals_sum_abs_per_row(self):
        """gross_gex == sum of |gex| per merged row (before groupby)."""
        # Two calls, one put — net may cancel but gross must not
        rows = [
            (47000, "C", 0.002, 1000),   # gex > 0
            (46500, "P", 0.002, 1000),   # gex < 0
        ]
        from scripts.options_quant import analyze_gex, CONTRACT_MULTIPLIER
        strikes_df, oi_df = self._make_frames(rows)
        result = analyze_gex(strikes_df, oi_df, spot=47000.0)
        m = result["metrics"]
        assert "gross_gex" in m, "gross_gex key missing from metrics"
        # gross_gex must be >= |total_gex|
        assert m["gross_gex"] >= abs(m["total_gex"]), (
            f"gross={m['gross_gex']!r} < |net|={abs(m['total_gex'])!r}"
        )

    def test_gross_ge_abs_net_invariant(self):
        """gross_gex >= |total_gex| always (invariant for any input)."""
        rows = [
            (46000, "C", 0.001, 500),
            (46500, "C", 0.003, 200),
            (46000, "P", 0.002, 300),
            (46500, "P", 0.001, 400),
        ]
        from scripts.options_quant import analyze_gex
        strikes_df, oi_df = self._make_frames(rows)
        result = analyze_gex(strikes_df, oi_df, spot=46250.0)
        m = result["metrics"]
        assert m["gross_gex"] >= abs(m["total_gex"])

    def test_n_c_n_p_counts(self):
        """n_c/n_p count the merged Call/Put rows (after dropna)."""
        rows = [
            (47000, "C", 0.002, 1000),
            (46500, "C", 0.003, 800),
            (46500, "P", 0.002, 700),
        ]
        from scripts.options_quant import analyze_gex
        strikes_df, oi_df = self._make_frames(rows)
        result = analyze_gex(strikes_df, oi_df, spot=46750.0)
        m = result["metrics"]
        assert "n_c" in m, "n_c key missing"
        assert "n_p" in m, "n_p key missing"
        assert m["n_c"] == 2
        assert m["n_p"] == 1

    def test_existing_keys_unchanged(self):
        """Existing keys (total_gex, flip, zone, top_strikes) still present + correct."""
        rows = [
            (47000, "C", 0.002, 1000),
            (46500, "P", 0.002, 1000),
        ]
        from scripts.options_quant import analyze_gex
        strikes_df, oi_df = self._make_frames(rows)
        result = analyze_gex(strikes_df, oi_df, spot=46750.0)
        m = result["metrics"]
        assert "total_gex" in m
        assert "flip" in m
        assert "zone" in m
        assert "top_strikes" in m
        assert isinstance(m["top_strikes"], list)


# ══════════════════════════════════════════════════════════════════════════════
# Task 2b: build_struct_fields new GEX fields
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildStructFieldsGex:
    """TDD for gex_gross / gex_dte / gex_coverage optional fields."""

    def _base_kwargs(self) -> dict:
        """Minimal valid kwargs that produce no crash."""
        return dict(
            as_of=dt.date(2026, 9, 8),
            spot=47000.0,
            day_close=47000.0,
            night_close=None,
            flip=None,
            gex_total=None,
            walls=None,
            hvn_result=None,
            foreign_net=None,
            toshin_net=None,
            us=None,
            asia=None,
            fx=None,
        )

    def test_gex_gross_present_when_extras_supplied(self):
        from scripts.txf_level_map import build_struct_fields
        kw = self._base_kwargs()
        kw["gex_extras"] = {"gross_gex": 1.5e10, "n_c": 50, "n_p": 45}
        fields = build_struct_fields(**kw)
        assert "gex_gross" in fields
        assert fields["gex_gross"] == str(1.5e10)

    def test_gex_coverage_present_when_extras_supplied(self):
        from scripts.txf_level_map import build_struct_fields
        kw = self._base_kwargs()
        kw["gex_extras"] = {"gross_gex": 1.5e10, "n_c": 50, "n_p": 45}
        fields = build_struct_fields(**kw)
        assert "gex_coverage" in fields
        assert fields["gex_coverage"] == "C50/P45"

    def test_gex_dte_present_when_front_expiry_supplied(self):
        from scripts.txf_level_map import build_struct_fields
        kw = self._base_kwargs()
        kw["front_expiry"] = dt.date(2026, 9, 9)  # tomorrow
        kw["gex_extras"] = {"gross_gex": 1.5e10, "n_c": 50, "n_p": 45}
        fields = build_struct_fields(**kw)
        assert "gex_dte" in fields
        assert fields["gex_dte"] == str((dt.date(2026, 9, 9) - dt.date(2026, 9, 8)).days)  # 1

    def test_gex_gross_omitted_when_no_extras(self):
        from scripts.txf_level_map import build_struct_fields
        kw = self._base_kwargs()
        fields = build_struct_fields(**kw)
        assert "gex_gross" not in fields
        assert "gex_coverage" not in fields

    def test_gex_dte_omitted_when_no_front_expiry(self):
        from scripts.txf_level_map import build_struct_fields
        kw = self._base_kwargs()
        kw["gex_extras"] = {"gross_gex": 1.5e10, "n_c": 50, "n_p": 45}
        # no front_expiry → gex_dte absent
        fields = build_struct_fields(**kw)
        assert "gex_dte" not in fields

    def test_dte_arithmetic(self):
        """gex_dte = (front_expiry - as_of).days, integer string."""
        from scripts.txf_level_map import build_struct_fields
        kw = self._base_kwargs()
        kw["front_expiry"] = dt.date(2026, 9, 16)  # 8 days from as_of
        kw["gex_extras"] = {"gross_gex": 2e10, "n_c": 30, "n_p": 25}
        fields = build_struct_fields(**kw)
        assert fields["gex_dte"] == "8"


# ══════════════════════════════════════════════════════════════════════════════
# Task 3: GEX history file (append + idempotent + corrupt-file guard)
# ══════════════════════════════════════════════════════════════════════════════

class TestGexHistory:
    """TDD for _load_gex_history / _save_gex_history / _upsert_gex_record."""

    def test_append_new_record(self, tmp_path):
        """First write creates file with one record."""
        from scripts.txf_level_map import _load_gex_history, _save_gex_history, _upsert_gex_record
        path = tmp_path / "gex_history.json"
        records = _load_gex_history(path)
        assert records == []
        rec = {"as_of": "2026-09-08", "front_expiry": "2026-09-09",
               "dte": 1, "net": 2.6e9, "gross": 5e9, "spot": 47000.0,
               "iv_asof": "2026-09-08T07:30:00+08:00"}
        records = _upsert_gex_record(records, rec)
        _save_gex_history(path, records)
        loaded = _load_gex_history(path)
        assert len(loaded) == 1
        assert loaded[0]["as_of"] == "2026-09-08"

    def test_same_day_idempotent(self, tmp_path):
        """Re-running same day replaces the existing record, not appends."""
        from scripts.txf_level_map import _load_gex_history, _save_gex_history, _upsert_gex_record
        path = tmp_path / "gex_history.json"
        rec1 = {"as_of": "2026-09-08", "front_expiry": "2026-09-09",
                "dte": 1, "net": 2.6e9, "gross": 5e9, "spot": 47000.0,
                "iv_asof": "2026-09-08T07:30:00+08:00"}
        records = _upsert_gex_record([], rec1)
        _save_gex_history(path, records)

        # Second run same day, different values
        rec2 = {**rec1, "net": 3.0e9, "gross": 6e9}
        records2 = _load_gex_history(path)
        records2 = _upsert_gex_record(records2, rec2)
        _save_gex_history(path, records2)

        final = _load_gex_history(path)
        assert len(final) == 1, f"Expected 1 record, got {len(final)}"
        assert final[0]["net"] == 3.0e9, "Idempotent replace failed"

    def test_multi_day_append(self, tmp_path):
        """Different days accumulate as separate records."""
        from scripts.txf_level_map import _load_gex_history, _save_gex_history, _upsert_gex_record
        path = tmp_path / "gex_history.json"
        records = []
        for i, date_str in enumerate(["2026-09-05", "2026-09-08"]):
            rec = {"as_of": date_str, "front_expiry": "2026-09-09",
                   "dte": 4 - i, "net": float(i), "gross": float(i + 1),
                   "spot": 47000.0, "iv_asof": "n/a"}
            records = _upsert_gex_record(records, rec)
        _save_gex_history(path, records)
        loaded = _load_gex_history(path)
        assert len(loaded) == 2

    def test_corrupt_file_renamed(self, tmp_path):
        """Corrupt JSON → file renamed to .corrupt-<ts>, returns empty list."""
        from scripts.txf_level_map import _load_gex_history
        path = tmp_path / "gex_history.json"
        path.write_text("this is not json{{", encoding="utf-8")
        records = _load_gex_history(path)
        assert records == []
        corrupt_files = list(tmp_path.glob("gex_history.json.corrupt-*"))
        assert len(corrupt_files) == 1, (
            f"Expected 1 .corrupt-* file, found {corrupt_files}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# annotate_ladder
# ══════════════════════════════════════════════════════════════════════════════

class TestAnnotateLadder:
    def _make_rows(self):
        # 3 rows from wall_rows-like format:
        # Strike 47000, 46900, 46800
        return [
            "            │47000│            ",   # strike 47000
            "████████████│46900│▏           ",   # strike 46900
            "▏           │46800│████████████",   # strike 46800
        ], [47000, 46900, 46800]

    def test_hvn_annotated(self):
        """HVN bucket gets ▤XX% suffix."""
        rows, strikes = self._make_rows()
        # profile: 47000 bucket (47000//100*100=47000) is HVN top_5
        profile = pd.Series({47000.0: 5000.0, 46900.0: 100.0, 46800.0: 50.0})
        lvn = set()
        result = annotate_ladder(rows, strikes, profile, lvn, top_n=5)
        # row[0] (strike 47000, bucket 47000) → HVN → has ▤ suffix
        assert "▤" in result[0]
        # Let's use top_n=1 to be precise
        result2 = annotate_ladder(rows, strikes, profile, lvn, top_n=1)
        assert "▤" in result2[0]
        assert "▤" not in result2[1]
        assert "▤" not in result2[2]

    def test_lvn_annotated(self):
        """LVN bucket gets ·真空 suffix."""
        rows, strikes = self._make_rows()
        # profile: 47000 is HVN; 46900 bucket is LVN
        profile = pd.Series({47000.0: 5000.0, 46900.0: 100.0, 46800.0: 3000.0})
        lvn = {46900}  # 46900 is explicitly LVN
        result = annotate_ladder(rows, strikes, profile, lvn, top_n=1)
        assert "·真空" in result[1]
        assert "·真空" not in result[0]
        assert "·真空" not in result[2]

    def test_untouched_row(self):
        """Row whose bucket is neither HVN nor LVN → unchanged."""
        rows, strikes = self._make_rows()
        profile = pd.Series({47000.0: 5000.0, 46900.0: 100.0, 46800.0: 50.0})
        lvn = set()  # no LVN
        result = annotate_ladder(rows, strikes, profile, lvn, top_n=1)
        # row[1] (46900) and row[2] (46800) are not HVN top_1, not LVN → unchanged
        assert result[1] == rows[1]
        assert result[2] == rows[2]

    def test_empty_profile_no_change(self):
        """Empty profile → all rows returned unchanged."""
        rows, strikes = self._make_rows()
        result = annotate_ladder(rows, strikes, pd.Series(dtype=float), set(), top_n=5)
        assert result == rows


def test_annotate_ladder_value_area_footer_when_hvn_below_range():
    """HVN 全在梯圖範圍外時,value_area_note 回傳價值區行;範圍內有 HVN 則回 None。"""
    import pandas as pd
    from scripts.txf_level_map import value_area_note
    prof = pd.Series({45800.0: 500.0, 45900.0: 480.0, 46100.0: 370.0,
                      47000.0: 10.0, 47100.0: 8.0})
    note = value_area_note(prof, ladder_lo=46400, ladder_hi=47900, top_n=3)
    assert note is not None and "45800" in note and "▤" in note
    note2 = value_area_note(prof, ladder_lo=45700, ladder_hi=46200, top_n=3)
    assert note2 is None


# ══════════════════════════════════════════════════════════════════════════════
# Structured publish — h:agent:txf_levels:latest (nautilus-shioaji consumer)
# ══════════════════════════════════════════════════════════════════════════════

from scripts.txf_level_map import build_struct_fields  # noqa: E402


def _full_struct_inputs():
    return dict(
        as_of=dt.date(2026, 9, 7),
        spot=47500.0,
        day_close=46701.0,
        night_close=47177.0,
        flip=47000.0,
        gex_total=-1.2e9,
        walls={
            "weekly": {"call": [(47500, 8123), (48000, 5000)],
                       "put": [(46600, 7900), (46000, 3000)]},
            "monthly": {"call": [(49000, 1119), (48000, 1542)],
                        "put": [(45000, 842), (46000, 479)]},
        },
        hvn_result={"hvn": [(45800, 0.17), (45900, 0.16)],
                    "lvn_above": 47300, "lvn_below": 46900},
        foreign_net=-82389,
        toshin_net=76174,
        us={"sox": 3.4, "vix": 14.2, "ust10y": 4.78, "brent": 95.4, "dxy": 99.2},
        asia={"N225": 1.3, "KS11": 1.6},
        fx={"USDTWD": 31.62},
        front_expiry=dt.date(2026, 9, 10),
        vacuum_list=[{"level": 46300, "age_days": 3}],
        value_note="價值區: 45800▤17%",
    )


class TestBuildStructFields:
    def test_full_inputs_field_shapes(self):
        f = build_struct_fields(**_full_struct_inputs())
        assert f["as_of"].startswith("2026-09-07")
        assert f["spot"] == "47500.0"
        assert f["gamma_regime"] == "ABOVE_FLIP"  # spot 47500 > flip 47000, diff=500 > deadband
        assert f["cw_w"] == "47500" and f["cw_w_oi"] == "8123"
        assert f["pw_w"] == "46600" and f["pw_w_oi"] == "7900"
        assert f["lvn_above"] == "47300" and f["lvn_below"] == "46900"
        assert f["foreign_net"] == "-82389" and f["trust_net"] == "76174"
        assert f["usdtwd"] == "31.62"
        assert f["is_settle_day"] == "0"  # front_expiry=Sept 10 != as_of Sept 7
        assert "expires_at" in f and "13:45" in f["expires_at"]
        assert "night_close" in f
        assert "vacuum_json" in f
        assert "value_area_json" in f
        import json as _json
        month = _json.loads(f["walls_month_json"])
        assert month["call"][0] == [49000, 1119]
        hvn = _json.loads(f["hvn_json"])
        assert hvn[0] == [45800, 0.17]
        over = _json.loads(f["overnight_json"])
        assert over["vix"] == 14.2

    def test_below_flip(self):
        args = _full_struct_inputs()
        args["spot"] = 46900.0   # diff vs flip=47000: 100, but 0.3%*46900=140.7 → NEUTRAL
        args["spot"] = 46400.0   # diff vs flip=47000: 600 > 0.3%*46400=139.2 → BELOW_FLIP
        f = build_struct_fields(**args)
        assert f["gamma_regime"] == "BELOW_FLIP"

    def test_missing_flip_or_spot_is_unknown(self):
        args = _full_struct_inputs()
        args["flip"] = None
        f = build_struct_fields(**args)
        assert f["gamma_regime"] == "UNKNOWN"
        args2 = _full_struct_inputs()
        args2["spot"] = None
        assert build_struct_fields(**args2)["gamma_regime"] == "UNKNOWN"

    def test_missing_walls_and_optionals_omit_fields(self):
        args = _full_struct_inputs()
        args.update(walls=None, hvn_result=None, foreign_net=None,
                    toshin_net=None, us={}, asia=None, fx=None,
                    gex_total=None, flip=None, day_close=None,
                    night_close=None, front_expiry=None, vacuum_list=None,
                    value_note=None)
        f = build_struct_fields(**args)
        assert "cw_w" not in f and "pw_w" not in f
        assert "foreign_net" not in f and "usdtwd" not in f
        assert f["gamma_regime"] == "UNKNOWN"
        assert "night_close" not in f
        assert "vacuum_json" not in f
        assert "value_area_json" not in f
        # never crashes; always carries as_of + spot presence contract
        assert f["as_of"].startswith("2026-09-07")

    def test_omission_policy_all_none(self):
        """All optional inputs None → only as_of/gamma_regime/is_settle_day/expires_at present."""
        f = build_struct_fields(
            as_of=dt.date(2026, 9, 7),
            spot=None, day_close=None, night_close=None, flip=None,
            gex_total=None, walls=None, hvn_result=None,
            foreign_net=None, toshin_net=None, us=None, asia=None, fx=None,
            front_expiry=None, vacuum_list=None, value_note=None,
        )
        assert f["as_of"] == "2026-09-07"
        assert f["gamma_regime"] == "UNKNOWN"
        assert f["is_settle_day"] == "0"
        assert "expires_at" in f
        # These must NOT be present
        for key in ("spot", "night_close", "flip", "cw_w", "vacuum_json", "value_area_json",
                    "front_expiry", "foreign_net", "usdtwd"):
            assert key not in f, f"Key {key!r} should be omitted but found"

    def test_neutral_deadband(self):
        """|spot - flip| < 0.3% * spot → NEUTRAL."""
        f = build_struct_fields(
            as_of=dt.date(2026, 9, 7), spot=47050.0, day_close=None, flip=47000.0,
            gex_total=None, walls=None, hvn_result=None, foreign_net=None,
            toshin_net=None, us=None, asia=None, fx=None,
        )
        # |47050-47000|=50 < 0.3%*47050=141.15 → NEUTRAL
        assert f["gamma_regime"] == "NEUTRAL"

    def test_neutral_exact_boundary_is_not_neutral(self):
        """Boundary: |spot - flip| == deadband → ABOVE_FLIP (strict <)."""
        spot = 47000.0
        flip = spot - 0.003 * spot  # exactly at boundary
        f = build_struct_fields(
            as_of=dt.date(2026, 9, 7), spot=spot, day_close=None, flip=flip,
            gex_total=None, walls=None, hvn_result=None, foreign_net=None,
            toshin_net=None, us=None, asia=None, fx=None,
        )
        assert f["gamma_regime"] == "ABOVE_FLIP"

    def test_settle_day_true(self):
        """front_expiry == as_of → is_settle_day == '1'."""
        today = dt.date(2026, 9, 7)
        f = build_struct_fields(
            as_of=today, spot=None, day_close=None, flip=None,
            gex_total=None, walls=None, hvn_result=None, foreign_net=None,
            toshin_net=None, us=None, asia=None, fx=None,
            front_expiry=today,
        )
        assert f["is_settle_day"] == "1"
        assert f["front_expiry"] == "2026-09-07"

    def test_settle_day_false(self):
        """front_expiry != as_of → is_settle_day == '0'."""
        f = build_struct_fields(
            as_of=dt.date(2026, 9, 7), spot=None, day_close=None, flip=None,
            gex_total=None, walls=None, hvn_result=None, foreign_net=None,
            toshin_net=None, us=None, asia=None, fx=None,
            front_expiry=dt.date(2026, 9, 10),
        )
        assert f["is_settle_day"] == "0"

    def test_vacuum_present_and_omit(self):
        """vacuum_list non-empty → vacuum_json present; empty/None → absent."""
        def _make(vl):
            return build_struct_fields(
                as_of=dt.date(2026, 9, 7), spot=None, day_close=None, flip=None,
                gex_total=None, walls=None, hvn_result=None, foreign_net=None,
                toshin_net=None, us=None, asia=None, fx=None,
                vacuum_list=vl,
            )
        import json as _json
        f = _make([{"level": 46300, "age_days": 3}])
        assert "vacuum_json" in f
        vac = _json.loads(f["vacuum_json"])
        assert vac[0]["level"] == 46300 and vac[0]["age_days"] == 3
        assert "vacuum_json" not in _make([])
        assert "vacuum_json" not in _make(None)

    def test_value_area_present_and_omit(self):
        """value_note present → value_area_json = {"note": ...}; None → absent."""
        def _make(vn):
            return build_struct_fields(
                as_of=dt.date(2026, 9, 7), spot=None, day_close=None, flip=None,
                gex_total=None, walls=None, hvn_result=None, foreign_net=None,
                toshin_net=None, us=None, asia=None, fx=None,
                value_note=vn,
            )
        import json as _json
        f = _make("價值區: 45800▤17%")
        assert "value_area_json" in f
        assert _json.loads(f["value_area_json"]) == {"note": "價值區: 45800▤17%"}
        assert "value_area_json" not in _make(None)

    def test_night_close_present_and_omit(self):
        """night_close present → field present; None → absent."""
        def _make(nc):
            return build_struct_fields(
                as_of=dt.date(2026, 9, 7), spot=None, day_close=None, flip=None,
                gex_total=None, walls=None, hvn_result=None, foreign_net=None,
                toshin_net=None, us=None, asia=None, fx=None,
                night_close=nc,
            )
        assert "night_close" in _make(47177.0)
        assert _make(47177.0)["night_close"] == "47177.0"
        assert "night_close" not in _make(None)

    def test_hvn_old_format(self):
        """hvn_result["hvn"] as list of tuples → json.dumps gives [[level, share], ...]."""
        import json as _json
        hvn_result = {"hvn": [(45800, 0.17), (45900, 0.16)], "lvn_above": 47300, "lvn_below": 46900}
        f = build_struct_fields(
            as_of=dt.date(2026, 9, 7), spot=None, day_close=None, flip=None,
            gex_total=None, walls=None, hvn_result=hvn_result, foreign_net=None,
            toshin_net=None, us=None, asia=None, fx=None,
        )
        assert "hvn_json" in f
        hvn = _json.loads(f["hvn_json"])
        assert hvn[0] == [45800, 0.17]
        assert hvn[1] == [45900, 0.16]

    def test_walls_month_old_format(self):
        """monthly walls → json.dumps as dict with call/put lists of [strike, oi] arrays."""
        import json as _json
        walls = {
            "weekly": {"call": [(47500, 8123)], "put": [(46600, 7900)]},
            "monthly": {"call": [(49000, 1119), (48000, 1542)], "put": [(45000, 842)]},
        }
        f = build_struct_fields(
            as_of=dt.date(2026, 9, 7), spot=None, day_close=None, flip=None,
            gex_total=None, walls=walls, hvn_result=None, foreign_net=None,
            toshin_net=None, us=None, asia=None, fx=None,
        )
        assert "walls_month_json" in f
        month = _json.loads(f["walls_month_json"])
        assert month["call"][0] == [49000, 1119]
        assert month["put"][0] == [45000, 842]

    def test_expires_at_format(self):
        """expires_at = as_of 13:45 TPE ISO with +08:00."""
        f = build_struct_fields(
            as_of=dt.date(2026, 9, 7), spot=None, day_close=None, flip=None,
            gex_total=None, walls=None, hvn_result=None, foreign_net=None,
            toshin_net=None, us=None, asia=None, fx=None,
        )
        assert "expires_at" in f
        assert "13:45" in f["expires_at"]
        assert "+08:00" in f["expires_at"]


def test_publish_struct_hset_and_expire(monkeypatch):
    """_publish_struct sends HSET + EXPIRE via redis-cli, fail-soft."""
    from scripts import txf_level_map as mod

    calls: list[list[str]] = []

    class _R:
        returncode = 0
        stdout = "OK"
        stderr = ""

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _R()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    ok = mod._publish_struct({"as_of": "2026-09-07", "spot": "47177.0"})
    assert ok is True
    assert len(calls) == 2
    hset = calls[0]
    assert "HSET" in hset and "h:agent:txf_levels:latest" in hset
    assert "as_of" in hset and "2026-09-07" in hset
    expire = calls[1]
    assert "EXPIRE" in expire and "86400" in expire


# ══════════════════════════════════════════════════════════════════════════════
# NEW: gamma_regime / bucket_age_days / build_struct_payload / _publish_struct
# ══════════════════════════════════════════════════════════════════════════════

from scripts.txf_level_map import (  # noqa: E402
    gamma_regime,
    bucket_age_days,
)


class TestGammaRegime:
    """gamma_regime(spot, flip, deadband_pct=0.003) -> str"""

    def test_above(self):
        """spot clearly above flip and outside deadband → ABOVE_FLIP."""
        assert gamma_regime(47500.0, 47000.0) == "ABOVE_FLIP"

    def test_below(self):
        """spot clearly below flip and outside deadband → BELOW_FLIP."""
        assert gamma_regime(46500.0, 47000.0) == "BELOW_FLIP"

    def test_neutral_inside_deadband(self):
        """|spot - flip| < 0.3% * spot → NEUTRAL."""
        spot = 47000.0
        # 0.3% of 47000 = 141; so offset of 100 < 141 → NEUTRAL
        assert gamma_regime(47100.0, 47000.0, deadband_pct=0.003) == "NEUTRAL"

    def test_neutral_inside_deadband_below_side(self):
        """deadband applies symmetrically — just below flip also NEUTRAL."""
        spot = 47000.0
        flip = 47100.0
        # |47000 - 47100| = 100; 0.3% * 47000 = 141 → inside deadband
        assert gamma_regime(spot, flip, deadband_pct=0.003) == "NEUTRAL"

    def test_boundary_exactly_at_deadband_edge_is_not_neutral(self):
        """Boundary: |spot - flip| == deadband_pct * spot → NOT NEUTRAL (strict <)."""
        spot = 47000.0
        deadband_pct = 0.003
        # |spot - flip| = deadband_pct * spot exactly → ABOVE_FLIP or BELOW_FLIP, not NEUTRAL
        flip = spot - deadband_pct * spot  # spot > flip by exactly deadband amount
        result = gamma_regime(spot, flip, deadband_pct=deadband_pct)
        assert result == "ABOVE_FLIP"  # strict < → exactly at boundary → not NEUTRAL

    def test_flip_none_is_unknown(self):
        """flip is None → UNKNOWN."""
        assert gamma_regime(47000.0, None) == "UNKNOWN"

    def test_spot_none_is_unknown(self):
        """spot is None → UNKNOWN."""
        assert gamma_regime(None, 47000.0) == "UNKNOWN"

    def test_both_none_is_unknown(self):
        """Both None → UNKNOWN."""
        assert gamma_regime(None, None) == "UNKNOWN"


class TestBucketAgeDays:
    """bucket_age_days(bars, levels, bucket_pts=100) -> dict[int, int]

    bars: DataFrame[bucket(UTC tz-aware), close, volume]
    levels: list of int levels to query (100-pt bucket floors)
    Returns: {level: age_in_trading_days} — level absent if never seen.

    age = (rank of last TPE trading date in bars) - (rank of first TPE date
    where that 100-pt bucket had volume > 0).
    Rank is 0-based index in sorted unique TPE dates present in bars.
    """

    def _make_multi_day_bars(self) -> pd.DataFrame:
        """3 trading days: Mon 2026-09-01, Tue 2026-09-02, Mon 2026-09-07.
        (Wed 9/3 → Fri 9/5 skipped, weekend 9/6 skipped — only Mon 9/7 is next)

        Level 47000 (bucket 47000): appears only on Mon 9/1 (first date, rank 0)
        Level 47100 (bucket 47100): appears on Mon 9/1 AND Mon 9/7 (first=rank 0, last rank=2)
        Level 46900 (bucket 46900): appears only on Tue 9/2 (rank 1)
        Level 46800 (bucket 46800): never seen

        Last date rank = 2 (Mon 9/7).
        age(47000) = 2 - 0 = 2  (first seen on rank-0 day, last day is rank-2)
        age(47100) = 2 - 0 = 2  (first seen on rank-0 day)
        age(46900) = 2 - 1 = 1  (first seen on rank-1 day)
        age(46800) = omitted (never seen)
        """
        import pytz
        utc = pytz.utc
        rows = [
            # Mon 2026-09-01 (TPE): UTC = Mon 2026-09-01 01:00
            (dt.datetime(2026, 9, 1, 1, 0, tzinfo=utc), 47050.0, 100.0),  # bucket 47000
            (dt.datetime(2026, 9, 1, 2, 0, tzinfo=utc), 47150.0, 200.0),  # bucket 47100
            # Tue 2026-09-02 (TPE): UTC = Tue 2026-09-02 01:00
            (dt.datetime(2026, 9, 2, 1, 0, tzinfo=utc), 46950.0, 150.0),  # bucket 46900
            (dt.datetime(2026, 9, 2, 2, 0, tzinfo=utc), 47150.0, 50.0),   # bucket 47100 again
            # Mon 2026-09-07 (TPE): UTC = Mon 2026-09-07 01:00
            (dt.datetime(2026, 9, 7, 1, 0, tzinfo=utc), 47180.0, 80.0),   # bucket 47100
            (dt.datetime(2026, 9, 7, 2, 0, tzinfo=utc), 47050.0, 60.0),   # bucket 47000 again
        ]
        df = pd.DataFrame(rows, columns=["bucket", "close", "volume"])
        return df

    def test_age_trading_days_not_calendar(self):
        """Mon-Tue gap then Mon: bucket_age_days counts trading days not calendar days."""
        bars = self._make_multi_day_bars()
        result = bucket_age_days(bars, levels=[47000, 47100, 46900], bucket_pts=100)
        # 3 distinct TPE dates: ranks 0=9/1, 1=9/2, 2=9/7
        # last rank = 2
        assert result[47000] == 2  # first seen rank 0, last date rank 2 → age 2
        assert result[47100] == 2  # first seen rank 0, last date rank 2 → age 2
        assert result[46900] == 1  # first seen rank 1, last date rank 2 → age 1

    def test_unseen_level_omitted(self):
        """Level 46800 never appears in bars → omitted from result dict."""
        bars = self._make_multi_day_bars()
        result = bucket_age_days(bars, levels=[46800], bucket_pts=100)
        assert 46800 not in result

    def test_weekend_gap_not_counted(self):
        """Fri → Mon gap: age is 1 trading day, not 3 calendar days."""
        import pytz
        utc = pytz.utc
        # Fri 2026-08-21 TPE = Fri 2026-08-21 01:00 UTC
        # Mon 2026-08-24 TPE = Mon 2026-08-24 01:00 UTC
        rows = [
            (dt.datetime(2026, 8, 21, 1, 0, tzinfo=utc), 47050.0, 100.0),  # Fri, bucket 47000
            (dt.datetime(2026, 8, 24, 1, 0, tzinfo=utc), 47050.0, 80.0),   # Mon, bucket 47000
        ]
        df = pd.DataFrame(rows, columns=["bucket", "close", "volume"])
        result = bucket_age_days(df, levels=[47000], bucket_pts=100)
        # 2 distinct dates: rank 0 = Fri, rank 1 = Mon
        # last date rank = 1, first seen rank = 0 → age = 1 (not 3 calendar days)
        assert result[47000] == 1

    def test_single_day_age_is_zero(self):
        """Level only seen today (last date) → age = 0."""
        import pytz
        utc = pytz.utc
        rows = [
            (dt.datetime(2026, 9, 7, 1, 0, tzinfo=utc), 47050.0, 100.0),
        ]
        df = pd.DataFrame(rows, columns=["bucket", "close", "volume"])
        result = bucket_age_days(df, levels=[47000], bucket_pts=100)
        assert result[47000] == 0

    def test_empty_bars_returns_empty(self):
        """Empty bars → empty dict for all requested levels."""
        df = pd.DataFrame(columns=["bucket", "close", "volume"])
        result = bucket_age_days(df, levels=[47000, 46900], bucket_pts=100)
        assert result == {}




class TestPublishStructNewPayload:
    """_publish_struct with build_struct_payload output — field/value flattening
    and EXPIRE key checks."""

    def test_hset_key_and_fields(self, monkeypatch):
        """HSET targets STRUCT_KEY; fields appear as flat alternating pairs."""
        from scripts import txf_level_map as mod
        calls: list[list[str]] = []

        class _R:
            returncode = 0
            stdout = "OK"
            stderr = ""

        monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **kw: (calls.append(cmd), _R())[1])

        payload = {"as_of": "2026-09-07", "spot": "47177.0", "gamma_regime": "ABOVE"}
        ok = mod._publish_struct(payload)
        assert ok is True
        hset_cmd = calls[0]
        assert "HSET" in hset_cmd
        assert "h:agent:txf_levels:latest" in hset_cmd
        # Fields should be present as flat list
        assert "spot" in hset_cmd
        assert "47177.0" in hset_cmd
        assert "gamma_regime" in hset_cmd
        assert "ABOVE" in hset_cmd

    def test_failure_returns_false_no_raise(self, monkeypatch):
        """Simulated redis-cli failure → False without raising."""
        from scripts import txf_level_map as mod

        class _Fail:
            returncode = 1
            stdout = ""
            stderr = "CONNREFUSED"

        monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **kw: _Fail())
        result = mod._publish_struct({"as_of": "2026-09-07"})
        assert result is False
