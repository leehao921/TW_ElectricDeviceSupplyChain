"""gex_regime_monitor 純函式測試 — 狀態機/事件偵測/縮放/Z (plan 2026-09-01)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import gex_regime_monitor as gm  # noqa: E402


# ---------------------------------------------------------------- regime
def test_classify_regime_magnet_and_expansion():
    assert gm.classify_regime(spot=46900, zg=46800, total_gex=5e9) == "MAGNET"
    assert gm.classify_regime(spot=46391, zg=46800, total_gex=-2e9) == "EXPANSION"


def test_classify_regime_mixed_when_signals_conflict():
    # spot > ZG 但總 GEX 為負 → 訊號矛盾, 誠實標 MIXED
    assert gm.classify_regime(spot=46900, zg=46800, total_gex=-1e9) == "MIXED"
    assert gm.classify_regime(spot=46391, zg=46800, total_gex=3e9) == "MIXED"
    assert gm.classify_regime(spot=46391, zg=None, total_gex=3e9) is None


# ---------------------------------------------------------------- vol scalar
def test_vol_scalar_percentile_of_abs_gex():
    hist = [1e9, 2e9, 3e9, 4e9]
    assert gm.vol_scalar(5e9, hist) == 1.0        # 高於全部歷史
    assert gm.vol_scalar(2.5e9, hist) == 0.5      # 中位
    assert gm.vol_scalar(0.5e9, hist) == 0.0
    assert gm.vol_scalar(3e9, []) is None         # 無歷史 → 誠實 None


# ---------------------------------------------------------------- events
def _st(regime="MAGNET", spot=46500.0, zg=46800.0, cw=47000, pw=45700, z20=0.5):
    return {"regime": regime, "spot": spot, "zg": zg, "cw": cw, "pw": pw, "z20": z20}


def test_detect_events_regime_flip():
    ev = gm.detect_events(_st(regime="MAGNET"), _st(regime="EXPANSION"))
    assert any(e[0] == "REGIME_FLIP" for e in ev)
    assert gm.detect_events(_st(), _st()) == []   # 無變化無事件


def test_detect_events_wall_proximity():
    # 距 CW 0.2% 內
    ev = gm.detect_events(_st(spot=46500), _st(spot=46910, cw=47000))
    assert any(e[0] == "CW_PROX" for e in ev)
    # 已在牆邊且維持 → 不重複發 (prev 已 prox)
    ev2 = gm.detect_events(_st(spot=46920, cw=47000), _st(spot=46930, cw=47000))
    assert not any(e[0] == "CW_PROX" for e in ev2)


def test_detect_events_zg_shift_and_z_cross():
    ev = gm.detect_events(_st(zg=46800), _st(zg=46950))
    assert any(e[0] == "ZG_SHIFT" for e in ev)    # >100 點
    ev = gm.detect_events(_st(z20=1.5), _st(z20=2.3))
    assert any(e[0] == "IV_Z_CROSS" for e in ev)  # 穿越 |2|
    assert not any(e[0] == "IV_Z_CROSS"
                   for e in gm.detect_events(_st(z20=2.3), _st(z20=2.6)))


# ---------------------------------------------------------------- session
def test_in_session_calendar_gate():
    from datetime import datetime as dt
    assert gm.in_session(dt(2026, 9, 4, 10, 30)) is True    # 週五日盤
    assert gm.in_session(dt(2026, 9, 4, 22, 0)) is True     # 週五夜盤
    assert gm.in_session(dt(2026, 9, 5, 3, 0)) is True      # 週六凌晨 = 夜盤尾
    assert gm.in_session(dt(2026, 9, 5, 13, 0)) is False    # 週六下午
    assert gm.in_session(dt(2026, 9, 6, 13, 42)) is False   # 週日 (2026-09-06 實例)
    assert gm.in_session(dt(2026, 9, 4, 14, 30)) is False   # 平日盤間空檔


# ---------------------------------------------------------------- zscore
def test_zscore_windows_honest_n():
    hist = list(range(30))                        # 30 筆歷史
    out = gm.z_windows(29.0, [float(x) for x in hist], windows=(20, 90))
    assert out["z20"]["n"] == 20
    assert out["z90"]["n"] == 30                  # 不足 90 → 用實際 n 標註
    expect = (29 - 19.5) / gm._std(list(map(float, range(10, 30))))
    assert abs(out["z20"]["z"] - expect) < 0.005   # 實作輸出 round 2 位


# ---------------------------------------------------------------- zero-gamma (2026-09-30)
# 9/30 09:57: published ZG 47,100 was the strike where cumulative GEX crosses
# zero, not a price where dealer gamma flips; the settling 9/30 leg (13:30) was
# excluded; and "no flip in range" fell through to UNKNOWN → gate fail-closed.
from datetime import datetime as _dt, timedelta as _td, timezone as _tz  # noqa: E402

_TPE = _tz(_td(hours=8))


def test_select_legs_keeps_todays_expiry_until_settlement():
    exps = ["20260930", "20261002", "20261007", "20261021", "20261118"]
    morning = _dt(2026, 9, 30, 10, 0, tzinfo=_TPE)
    assert gm.select_legs(exps, morning) == ["20260930", "20261002", "20261007", "20261021"]


def test_select_legs_drops_todays_expiry_after_settlement():
    exps = ["20260930", "20261002", "20261007", "20261021", "20261118"]
    evening = _dt(2026, 9, 30, 15, 5, tzinfo=_TPE)
    assert gm.select_legs(exps, evening) == ["20261002", "20261007", "20261021"]


def test_select_legs_ignores_past_expiries():
    exps = ["20260929", "20261002", "20261007", "20261021"]
    assert gm.select_legs(exps, _dt(2026, 9, 30, 10, 0, tzinfo=_TPE)) == \
        ["20261002", "20261007", "20261021"]


def test_bs_gamma_peaks_at_the_money_and_is_zero_when_expired():
    atm = gm.bs_gamma(48000, 48000, 7 / 365, 0.2)
    otm = gm.bs_gamma(48000, 49500, 7 / 365, 0.2)
    assert atm > otm > 0
    assert gm.bs_gamma(48000, 48000, 0, 0.2) == 0.0


def _opt(strike, cp, oi, T=7 / 365, iv=0.2):
    return {"strike": strike, "cp": cp, "T": T, "iv": iv, "oi": oi}


def test_sweep_finds_flip_between_put_and_call_mass():
    # puts (negative gamma) clustered low, calls (positive) high → gamma flips between
    opts = [_opt(47000, "P", 5000), _opt(49000, "C", 5000)]
    zg, sign = gm.sweep_zero_gamma(opts, spot=48500)
    assert zg is not None and 47000 < zg < 49000
    assert sign > 0          # at spot 48,500 the call side dominates


def test_sweep_reports_no_flip_when_gamma_one_signed():
    opts = [_opt(48000, "C", 5000), _opt(48500, "C", 3000)]
    zg, sign = gm.sweep_zero_gamma(opts, spot=48500)
    assert zg is None and sign > 0


def test_classify_no_flip_uses_gamma_sign_not_unknown():
    assert gm.classify_regime(48600, None, 2.5e9, zg_status="none_in_range") == "MAGNET"
    assert gm.classify_regime(48600, None, -2.5e9, zg_status="none_in_range") == "EXPANSION"
    # without the explicit status a missing zg is still "can't tell"
    assert gm.classify_regime(48600, None, 2.5e9) is None


def test_regime_flip_event_survives_missing_zg():
    ev = gm.detect_events(_st(regime="MIXED"), _st(regime="MAGNET", zg=None))
    flip = [d for t, d in ev if t == "REGIME_FLIP"]
    assert flip and "n/a" in flip[0]


def _frame(rows):
    import pandas as pd
    return pd.DataFrame(rows, columns=["expiry", "strike", "call_put", "gamma", "iv", "open_interest"])


def test_composite_publishes_both_zero_gammas_and_status():
    now = _dt(2026, 9, 30, 10, 0, tzinfo=_TPE)
    df = _frame([
        ("20261021", 47000, "P", 0.0004, 0.22, 5000),
        ("20261021", 49000, "C", 0.0004, 0.20, 5000),
    ])
    c = gm.composite_from_frame(df, spot=48500, now=now)
    assert c["zg_status"] == "flip"
    assert 47000 < c["zg"] < 49000                  # textbook sweep
    assert c["zg_strike"] == 49000.0                # cumulative crossing at the call strike
    assert c["expiries"] == ["20261021"]


def test_composite_no_flip_in_range():
    now = _dt(2026, 9, 30, 10, 0, tzinfo=_TPE)
    df = _frame([("20261021", 48500, "C", 0.0004, 0.20, 5000)])
    c = gm.composite_from_frame(df, spot=48500, now=now)
    assert c["zg"] is None and c["zg_status"] == "none_in_range"
    assert gm.classify_regime(48500, c["zg"], c["total_gex"], c["zg_status"]) == "MAGNET"


def test_composite_uses_time_to_13_30_settlement_for_todays_leg():
    now = _dt(2026, 9, 30, 13, 0, tzinfo=_TPE)       # 30 min before settlement
    df = _frame([("20260930", 48500, "C", 0.0004, 0.20, 5000)])
    c = gm.composite_from_frame(df, spot=48500, now=now)
    assert c["expiries"] == ["20260930"]
    assert c["zg_status"] == "none_in_range"
