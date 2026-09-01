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


# ---------------------------------------------------------------- zscore
def test_zscore_windows_honest_n():
    hist = list(range(30))                        # 30 筆歷史
    out = gm.z_windows(29.0, [float(x) for x in hist], windows=(20, 90))
    assert out["z20"]["n"] == 20
    assert out["z90"]["n"] == 30                  # 不足 90 → 用實際 n 標註
    expect = (29 - 19.5) / gm._std(list(map(float, range(10, 30))))
    assert abs(out["z20"]["z"] - expect) < 0.005   # 實作輸出 round 2 位
