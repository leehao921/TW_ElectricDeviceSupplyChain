# LPPLS 台股泡沫偵測 Phase 1 驗證研究 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以自建電子權值指數（`stock_daily_ohlcv` 399 交易日）擬合 LPPLS，walk-forward 驗證泡沫警戒力，依事前準則判定是否進 Phase 2 routine。

**Architecture:** 四模組 — `scripts/lppls/` 下的 fitter（純價格 LPPLS 擬合＋物理約束）、index_builder（市值權重 Laspeyres 指數）、walkforward（回檔事件偵測＋通過準則評估）、confirmation（四層旁證計分，pure scorer 與 DB loader 分離）；`scripts/lppls_study.py` CLI 串接並產出 `analysis/` 研究報告。擬合核心以合成序列 TDD（已知參數生成 → 擬合須還原）。

**Tech Stack:** Python 3.12（`.venv`，uv-managed）、numpy/pandas/scipy、psycopg2（read-only vs tmf_market_data）、pytest。

**Spec:** `docs/superpowers/specs/2026-08-27-lppls-tw-bubble-detection-design.md`

---

## File Structure

| 檔案 | 職責 |
|---|---|
| `scripts/lppls/__init__.py` | 空檔，套件宣告 |
| `scripts/lppls/fitter.py` | LPPLS 方程式、design matrix、加權 OLS、grid+Nelder-Mead、物理約束、合成序列生成 |
| `scripts/lppls/db.py` | DB 連線（沿用 options_quant DB_CONFIG）＋日線/TAIEX loaders |
| `scripts/lppls/index_builder.py` | 成分選取（CORE＋市值前段補足）、市值權重解析（Pilot_Reports）、定基指數、TAIEX 驗證 |
| `scripts/lppls/walkforward.py` | 回檔事件偵測、walk-forward 引擎、三條通過準則評估 |
| `scripts/lppls/confirmation.py` | 四層 confirmation：pure scorer（可測）＋ DB loader |
| `scripts/lppls_study.py` | CLI orchestrator，產 `analysis/lppls_study_<date>.md` |
| `tests/test_lppls_fitter.py` | 擬合核心測試（合成序列參數還原） |
| `tests/test_lppls_index.py` | 指數建構測試（合成 closes，monkeypatch 市值） |
| `tests/test_lppls_walkforward.py` | 事件偵測＋評估邏輯測試 |
| `tests/test_lppls_confirmation.py` | 四層 pure scorer 測試 |

慣例：tests 經 `tests/conftest.py` 已可 `from scripts.lppls.X import ...`。DB loader 不寫單元測試（thin SQL wrapper），由 Task 8 實際執行時驗證。

---

### Task 1: 環境準備

**Files:** 無程式碼變更。

- [ ] **Step 1: 安裝 scipy**

```bash
uv pip install --python .venv/bin/python scipy
.venv/bin/python -c "import scipy; print(scipy.__version__)"
```
Expected: 印出版本號（≥1.11）。

- [ ] **Step 2: 安裝 ETH lppls 套件（cross-check 用，允許失敗）**

```bash
uv pip install --python .venv/bin/python lppls || echo "SKIP: lppls package unavailable"
```
Expected: 成功印版本或印 SKIP。失敗不阻擋 — Task 7 會據此跳過 cross-check 並在報告註記。

---

### Task 2: LPPLS 擬合核心 (`fitter.py`)

**Files:**
- Create: `scripts/lppls/__init__.py`（空檔）
- Create: `scripts/lppls/fitter.py`
- Test: `tests/test_lppls_fitter.py`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_lppls_fitter.py
import numpy as np
import pytest

from scripts.lppls.fitter import (
    design_matrix, exp_weights, fit_linear, fit, is_signal, make_synthetic, LpplsFit,
)

N, TC, M, W = 100, 120.0, 0.5, 8.0
A, B, C1, C2 = 10.3, -0.05, 0.001, 0.001  # damping: m|B|=0.025 >= w*C=0.0113


def test_design_matrix_shape_and_columns():
    t = np.arange(N, dtype=float)
    X = design_matrix(t, TC, M, W)
    assert X.shape == (N, 4)
    assert np.allclose(X[:, 0], 1.0)                      # bias
    assert np.allclose(X[:, 1], (TC - t) ** M)            # power law
    assert np.allclose(X[:, 2], (TC - t) ** M * np.cos(W * np.log(TC - t)))
    assert np.allclose(X[:, 3], (TC - t) ** M * np.sin(W * np.log(TC - t)))


def test_exp_weights_upweight_recent():
    w = exp_weights(100, half_life=50.0)
    assert w[-1] == 1.0
    assert np.isclose(w[-51] / w[-1], 0.5, atol=1e-9)
    assert np.all(np.diff(w) > 0)


def test_linear_params_recovered_noiseless():
    prices = make_synthetic(N, TC, M, W, A, B, C1, C2, noise=0.0)
    t = np.arange(N, dtype=float)
    X = design_matrix(t, TC, M, W)
    Z = fit_linear(np.log(prices), X, exp_weights(N))
    assert np.allclose(Z, [A, B, C1, C2], atol=1e-6)


def test_full_fit_recovers_nonlinear_params():
    prices = make_synthetic(N, TC, M, W, A, B, C1, C2, noise=0.0005)
    f = fit(prices)
    assert abs(f.tc - TC) <= 5.0
    assert abs(f.m - M) <= 0.15
    assert abs(f.omega - W) <= 0.5
    assert f.r2 > 0.95
    assert f.qualifies


def test_positive_B_disqualifies():
    f = LpplsFit(A=10.0, B=0.02, C1=0.0, C2=0.0, tc=110.0, m=0.5, omega=8.0,
                 r2=0.99, sse=0.0, refined=True)
    f.apply_constraints()
    assert not f.qualifies
    assert "B>=0" in f.reasons


def test_damping_violation_disqualifies():
    # m|B| = 0.005 < w*C = 8*0.1 = 0.8
    f = LpplsFit(A=10.0, B=-0.01, C1=0.1, C2=0.0, tc=110.0, m=0.5, omega=8.0,
                 r2=0.99, sse=0.0, refined=True)
    f.apply_constraints()
    assert "damping violated" in f.reasons


def test_is_signal_requires_tc_within_30_and_r2():
    good = LpplsFit(A=10.0, B=-0.05, C1=0.001, C2=0.0, tc=N - 1 + 20, m=0.5,
                    omega=8.0, r2=0.85, sse=0.0, refined=True)
    good.apply_constraints()
    assert is_signal(good, N, r2_min=0.7)
    far = LpplsFit(A=10.0, B=-0.05, C1=0.001, C2=0.0, tc=N - 1 + 45, m=0.5,
                   omega=8.0, r2=0.85, sse=0.0, refined=True)
    far.apply_constraints()
    assert not is_signal(far, N, r2_min=0.7)
    lowr2 = LpplsFit(A=10.0, B=-0.05, C1=0.001, C2=0.0, tc=N - 1 + 20, m=0.5,
                     omega=8.0, r2=0.5, sse=0.0, refined=True)
    lowr2.apply_constraints()
    assert not is_signal(lowr2, N, r2_min=0.7)


def test_flat_series_no_signal():
    prices = np.full(100, 30000.0)
    f = fit(prices)
    assert not is_signal(f, 100, r2_min=0.7)
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
.venv/bin/python -m pytest tests/test_lppls_fitter.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.lppls'`

- [ ] **Step 3: 實作**

```bash
touch scripts/lppls/__init__.py
```

```python
# scripts/lppls/fitter.py
"""LPPLS 擬合核心 — 純價格，標準 Sornette calibration。

ln p(t) = A + B(tc-t)^m + C1(tc-t)^m cos(w ln(tc-t)) + C2(tc-t)^m sin(w ln(tc-t))

t 以交易日為單位 0..N-1；tc > N-1（視窗外的未來臨界日）。
線性參數 (A,B,C1,C2) 以加權 OLS normal equation 解；非線性 (tc,m,w) grid seed
+ Nelder-Mead 精修。物理約束：0<m<1、6<=w<=13、tc 在 60 交易日內、B<0、
damping m|B| >= w|C|。
"""
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

OMEGA_MIN, OMEGA_MAX = 6.0, 13.0
M_MIN, M_MAX = 0.01, 0.99
TC_MAX_AHEAD = 60       # tc 上限：視窗末端後 60 交易日
SIGNAL_TC_WITHIN = 30   # 訊號條件：tc 在 30 交易日內


@dataclass
class LpplsFit:
    A: float
    B: float
    C1: float
    C2: float
    tc: float
    m: float
    omega: float
    r2: float
    sse: float
    refined: bool
    reasons: list = field(default_factory=list)

    @property
    def C(self) -> float:
        return float(np.hypot(self.C1, self.C2))

    @property
    def qualifies(self) -> bool:
        return not self.reasons

    def days_to_tc(self, n: int) -> float:
        return self.tc - (n - 1)

    def apply_constraints(self) -> "LpplsFit":
        self.reasons = []
        if self.B >= 0:
            self.reasons.append("B>=0")
        if not (M_MIN < self.m < M_MAX):
            self.reasons.append("m out of range")
        if not (OMEGA_MIN <= self.omega <= OMEGA_MAX):
            self.reasons.append("omega out of range")
        if self.m * abs(self.B) < self.omega * self.C:
            self.reasons.append("damping violated")
        return self


def design_matrix(t: np.ndarray, tc: float, m: float, omega: float) -> np.ndarray:
    dt = tc - t
    f = dt ** m
    logdt = np.log(dt)
    return np.column_stack([
        np.ones_like(t), f, f * np.cos(omega * logdt), f * np.sin(omega * logdt),
    ])


def exp_weights(n: int, half_life: float = 50.0) -> np.ndarray:
    k = np.arange(n)
    return 0.5 ** ((n - 1 - k) / half_life)


def fit_linear(y: np.ndarray, X: np.ndarray, w: np.ndarray) -> np.ndarray:
    Xw = X * w[:, None]
    Z, *_ = np.linalg.lstsq(X.T @ Xw, X.T @ (w * y), rcond=None)
    return Z


def _sse(y, X, w):
    Z = fit_linear(y, X, w)
    resid = y - X @ Z
    return float(np.sum(w * resid ** 2)), Z


def fit(prices, half_life: float = 50.0, refine: bool = True) -> LpplsFit:
    """prices: 1-D 原始價格（非 log）。回傳套用約束後的 LpplsFit。"""
    y = np.log(np.asarray(prices, dtype=float))
    n = len(y)
    t = np.arange(n, dtype=float)
    w = exp_weights(n, half_life)

    def objective(p):
        tc, m, omega = p
        if not (n - 1 < tc <= n - 1 + TC_MAX_AHEAD):
            return 1e12
        if not (M_MIN <= m <= M_MAX):
            return 1e12
        if not (OMEGA_MIN <= omega <= OMEGA_MAX):
            return 1e12
        X = design_matrix(t, tc, m, omega)
        sse, _ = _sse(y, X, w)
        return sse

    seeds = [
        (tc, m, omega)
        for tc in np.arange(n - 1 + 5.0, n - 1 + TC_MAX_AHEAD + 1.0, 5.0)
        for m in np.arange(0.1, 1.0, 0.1)
        for omega in np.arange(OMEGA_MIN, OMEGA_MAX + 0.1, 1.0)
    ]
    best_sse, best = min(((objective(s), s) for s in seeds), key=lambda x: x[0])
    refined = False
    if refine:
        res = minimize(objective, np.array(best), method="Nelder-Mead",
                       options=dict(xatol=1e-3, fatol=1e-9, maxiter=2000))
        if res.success and res.fun < best_sse:
            best, best_sse, refined = tuple(res.x), float(res.fun), True

    tc, m, omega = (float(v) for v in best)
    X = design_matrix(t, tc, m, omega)
    sse, Z = _sse(y, X, w)
    A, B, C1, C2 = (float(v) for v in Z)
    ybar = float(np.average(y, weights=w))
    ss_tot = float(np.sum(w * (y - ybar) ** 2))
    r2 = 1.0 - sse / ss_tot if ss_tot > 0 else 0.0
    return LpplsFit(A, B, C1, C2, tc, m, omega, r2, sse, refined).apply_constraints()


def is_signal(fit_result: LpplsFit, n: int, r2_min: float = 0.7) -> bool:
    return (fit_result.qualifies and fit_result.r2 >= r2_min
            and fit_result.days_to_tc(n) <= SIGNAL_TC_WITHIN)


def make_synthetic(n, tc, m, omega, A=10.3, B=-0.05, C1=0.001, C2=0.001,
                   noise=0.0, seed=42):
    """由已知參數生成合成 LPPLS 價格序列（測試/驗證用）。"""
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=float)
    X = design_matrix(t, tc, m, omega)
    y = X @ np.array([A, B, C1, C2]) + rng.normal(0.0, noise, n)
    return np.exp(y)
```

- [ ] **Step 4: 跑測試確認通過**

```bash
.venv/bin/python -m pytest tests/test_lppls_fitter.py -v
```
Expected: 8 passed。若 `test_full_fit_recovers_nonlinear_params` 不穩，檢查 grid seed 是否涵蓋 tc=120（n-1+5..n-1+60 含 119/124，Nelder-Mead 應收斂至 120±5）。

- [ ] **Step 5: Commit**

```bash
git add scripts/lppls/__init__.py scripts/lppls/fitter.py tests/test_lppls_fitter.py
git commit -m "feat(lppls): LPPLS 擬合核心 — 加權OLS線性解+grid/NM非線性+Sornette物理約束

合成序列 TDD：已知參數生成 → 擬合須還原 (tc±5, m±0.15, ω±0.5)"
```

---

### Task 3: DB loaders 與指數建構 (`db.py`, `index_builder.py`)

**Files:**
- Create: `scripts/lppls/db.py`
- Create: `scripts/lppls/index_builder.py`
- Test: `tests/test_lppls_index.py`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_lppls_index.py
import numpy as np
import pandas as pd
import pytest

from scripts.lppls import index_builder
from scripts.lppls.index_builder import (
    CORE, select_components, build_index, validate_vs_taiex,
)


def _closes(n=400, symbols=None, seed=7):
    symbols = symbols or (CORE + ["3034", "3008"])
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-02", periods=n)
    data = {s: 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
            for s in symbols}
    return pd.DataFrame(data, index=dates)


FAKE_CAPS = {s: 1_000_000.0 - i * 10_000 for i, s in enumerate(CORE)}
FAKE_CAPS.update({"3034": 900_000.0, "3008": 800_000.0})


def test_select_components_core_plus_supplement(monkeypatch):
    monkeypatch.setattr(index_builder, "load_market_caps", lambda tickers: dict(FAKE_CAPS))
    closes = _closes()
    comps, weights = select_components(closes, n_supplement=2)
    assert set(CORE).issubset(comps)
    assert "3034" in comps and "3008" in comps
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_select_components_raises_on_missing_core_cap(monkeypatch):
    caps = {k: v for k, v in FAKE_CAPS.items() if k != "2330"}
    monkeypatch.setattr(index_builder, "load_market_caps", lambda tickers: caps)
    with pytest.raises(ValueError, match="2330"):
        select_components(_closes(), n_supplement=2)


def test_select_components_drops_short_history(monkeypatch):
    monkeypatch.setattr(index_builder, "load_market_caps", lambda tickers: dict(FAKE_CAPS))
    closes = _closes()
    closes.iloc[:50, closes.columns.get_loc("3008")] = np.nan  # 350 < 390 天
    comps, _ = select_components(closes, n_supplement=2, min_days=390)
    assert "3008" not in comps


def test_build_index_base_100_and_weighting():
    dates = pd.bdate_range("2025-01-02", periods=3)
    closes = pd.DataFrame({"AAA": [100.0, 110.0, 121.0],
                           "BBB": [200.0, 200.0, 200.0]}, index=dates)
    idx = build_index(closes, {"AAA": 0.6, "BBB": 0.4})
    assert np.isclose(idx.iloc[0], 100.0)
    assert np.isclose(idx.iloc[1], (0.6 * 1.1 + 0.4 * 1.0) * 100)


def test_validate_vs_taiex_perfect_proxy():
    closes = _closes(n=200, symbols=["AAA"])
    idx = build_index(closes, {"AAA": 1.0})
    corr, n = validate_vs_taiex(idx, closes["AAA"] * 3.0)
    assert corr > 0.999
    assert n > 100
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
.venv/bin/python -m pytest tests/test_lppls_index.py -v
```
Expected: FAIL — `ModuleNotFoundError` 或 `ImportError`。

- [ ] **Step 3: 實作**

```python
# scripts/lppls/db.py
"""trading-timescaledb read-only loaders（DB_CONFIG 沿用 options_quant 慣例）。"""
import os
import warnings

import pandas as pd
import psycopg2

warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")

DB_CONFIG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5432")),
    user=os.environ.get("DB_USER", "tmf"),
    password=os.environ.get("DB_PASSWORD", "tmf_dev_2026"),
    dbname=os.environ.get("DB_NAME", "tmf_market_data"),
)


def connect():
    return psycopg2.connect(**DB_CONFIG)


def load_daily_closes(symbols) -> pd.DataFrame:
    """date × symbol 的收盤價寬表。"""
    sql = ("SELECT ts::date AS date, symbol, close FROM stock_daily_ohlcv "
           "WHERE symbol = ANY(%s) ORDER BY 1")
    with connect() as conn:
        df = pd.read_sql(sql, conn, params=(list(symbols),))
    return df.pivot(index="date", columns="symbol", values="close")


def load_taiex() -> pd.Series:
    sql = "SELECT date, close FROM taiex_ema_daily ORDER BY date"
    with connect() as conn:
        return pd.read_sql(sql, conn).set_index("date")["close"]
```

```python
# scripts/lppls/index_builder.py
"""電子權值加權指數 — 市值權重 snapshot、Laspeyres 定基 100。

成分 = CORE（OFI 追蹤的 10 檔電子權值）＋ CANDIDATES 依市值取前 n_supplement 檔。
市值來源：Pilot_Reports metadata `**市值:** N 百萬台幣`（filename ground truth）。
"""
import re
from pathlib import Path

import pandas as pd

CORE = ["2330", "2317", "2454", "2308", "3711", "2382", "2379", "2303", "2357", "3231"]
CANDIDATES = ["3034", "3008", "3037", "2345", "3017", "6669", "2327", "2408",
              "2409", "3481", "3661", "6415"]
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "Pilot_Reports"
MCAP_RE = re.compile(r"\*\*市值:\*\*\s*([\d,]+)\s*百萬台幣")


def load_market_caps(tickers) -> dict:
    caps = {}
    for md in REPORTS_DIR.glob("*/*.md"):
        tk = md.name.split("_")[0]
        if tk in tickers and tk not in caps:
            m = MCAP_RE.search(md.read_text(encoding="utf-8"))
            if m:
                caps[tk] = float(m.group(1).replace(",", ""))
    return caps


def select_components(closes: pd.DataFrame, n_supplement: int = 8,
                      min_days: int = 390):
    """回傳 (成分list, 正規化權重dict)。CORE 缺市值即 raise（資料完整性）。"""
    caps = load_market_caps(set(CORE) | set(CANDIDATES))
    ok = {s for s in closes.columns if closes[s].notna().sum() >= min_days}
    comps = [s for s in CORE if s in ok]
    missing_caps = [s for s in comps if s not in caps]
    if missing_caps:
        raise ValueError(f"CORE 成分缺市值 metadata: {missing_caps}")
    supp = sorted((s for s in CANDIDATES if s in ok and s in caps),
                  key=lambda s: caps[s], reverse=True)[:n_supplement]
    comps += supp
    total = sum(caps[s] for s in comps)
    return comps, {s: caps[s] / total for s in comps}


def build_index(closes: pd.DataFrame, weights: dict, max_ffill: int = 5) -> pd.Series:
    """index_t = Σ w_i × (P_it / P_i0) × 100；停牌 forward-fill 上限 max_ffill 日。"""
    px = closes[list(weights)].ffill(limit=max_ffill).dropna()
    rel = px / px.iloc[0]
    return (rel * pd.Series(weights)).sum(axis=1) * 100.0


def validate_vs_taiex(index_s: pd.Series, taiex_s: pd.Series):
    """重疊區間日報酬相關。合格門檻 0.95（spec）。"""
    df = pd.concat([index_s.rename("idx"), taiex_s.rename("taiex")], axis=1).dropna()
    r = df.pct_change().dropna()
    return float(r["idx"].corr(r["taiex"])), len(r)
```

- [ ] **Step 4: 跑測試確認通過**

```bash
.venv/bin/python -m pytest tests/test_lppls_index.py -v
```
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add scripts/lppls/db.py scripts/lppls/index_builder.py tests/test_lppls_index.py
git commit -m "feat(lppls): 電子權值指數建構 — CORE 10檔+市值前段補足, Laspeyres 定基, TAIEX 驗證"
```

---

### Task 4: Walk-forward 與通過準則 (`walkforward.py`)

**Files:**
- Create: `scripts/lppls/walkforward.py`
- Test: `tests/test_lppls_walkforward.py`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_lppls_walkforward.py
import numpy as np
import pandas as pd

from scripts.lppls.fitter import make_synthetic
from scripts.lppls.walkforward import (
    detect_drawdowns, walk_forward, with_signal, evaluate,
)


def _series(values, start="2025-01-02"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


def test_detect_drawdowns_single_event():
    vals = list(np.linspace(100, 120, 50)) + list(np.linspace(120, 108, 10))  # -10%
    events = detect_drawdowns(_series(vals), threshold=0.05)
    assert len(events) == 1
    assert events[0]["depth"] >= 0.05


def test_detect_drawdowns_no_double_count_until_recovery():
    vals = (list(np.linspace(100, 120, 50)) + list(np.linspace(120, 105, 10))
            + list(np.linspace(105, 110, 10)) + list(np.linspace(110, 100, 10)))
    events = detect_drawdowns(_series(vals), threshold=0.05)
    assert len(events) == 1  # 未收復前高 120，同一事件不重算


def test_detect_drawdowns_flat_no_events():
    assert detect_drawdowns(_series([100.0] * 60), threshold=0.05) == []


def test_walk_forward_bubble_series_emits_signal_before_crash():
    bubble = make_synthetic(160, tc=165.0, m=0.5, omega=8.0, noise=0.0005)
    crash = bubble[-1] * np.linspace(0.99, 0.85, 15)
    s = _series(np.concatenate([bubble, crash]))
    wf = with_signal(walk_forward(s, window=100, step=5), r2_min=0.7)
    crash_start = s.index[160]
    assert wf.loc[:crash_start, "signal"].any()


def test_walk_forward_flat_series_no_signal():
    s = _series([100.0] * 200)
    wf = with_signal(walk_forward(s, window=100, step=5), r2_min=0.7)
    assert not wf["signal"].any()


def test_evaluate_criteria_shapes():
    bubble = make_synthetic(160, tc=165.0, m=0.5, omega=8.0, noise=0.0005)
    crash = bubble[-1] * np.linspace(0.99, 0.85, 15)
    tail = crash[-1] * np.ones(25)  # 留 forward-return 空間
    s = _series(np.concatenate([bubble, crash, tail]))
    wf = with_signal(walk_forward(s, window=100, step=5), r2_min=0.7)
    events = detect_drawdowns(s, threshold=0.05)
    result = evaluate(s, wf, events)
    assert result["n_events"] == len(events)
    assert 0.0 <= result["capture_rate"] <= 1.0
    assert result["n_signals"] >= 1
    for key in ("fp_rate", "sig_fwd_median", "nosig_fwd_median", "mw_pvalue"):
        assert key in result
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
.venv/bin/python -m pytest tests/test_lppls_walkforward.py -v
```
Expected: FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 實作**

```python
# scripts/lppls/walkforward.py
"""Walk-forward 引擎＋回檔事件偵測＋事前通過準則評估（spec §3）。

準則（寫死，不得事後放寬）:
  1. >=5% 回檔事件中，至少半數事前 30 交易日內有 LPPLS 訊號
  2. False positive（訊號後 20 日內未跌 >3%）比率 < 50%
  3. 訊號日 20 日 forward return 劣於無訊號日（中位數 + Mann-Whitney U one-sided）
"""
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from scripts.lppls.fitter import SIGNAL_TC_WITHIN, fit


def detect_drawdowns(series: pd.Series, threshold: float = 0.05):
    """滾動高點回落 >= threshold 的事件；觸發後直到收復前高不重複計。"""
    events, peak, peak_date, armed = [], -np.inf, None, True
    for date, px in series.items():
        if px >= peak:
            peak, peak_date, armed = px, date, True
        elif armed and (peak - px) / peak >= threshold:
            events.append(dict(peak_date=peak_date, trigger_date=date,
                               depth=(peak - px) / peak))
            armed = False
    return events


def walk_forward(series: pd.Series, window: int = 100, step: int = 5,
                 half_life: float = 50.0) -> pd.DataFrame:
    """每 step 日 refit 一次，回傳原始擬合表（不含 signal 欄，由 with_signal 套）。"""
    rows = []
    for end in range(window, len(series) + 1, step):
        win = series.iloc[end - window:end]
        f = fit(win.values, half_life=half_life)
        rows.append(dict(date=series.index[end - 1], r2=f.r2,
                         tc_days=f.days_to_tc(window), m=f.m, omega=f.omega,
                         B=f.B, qualifies=f.qualifies, refined=f.refined))
    return pd.DataFrame(rows).set_index("date")


def with_signal(wf: pd.DataFrame, r2_min: float = 0.7) -> pd.DataFrame:
    out = wf.copy()
    out["signal"] = (out["qualifies"] & (out["r2"] >= r2_min)
                     & (out["tc_days"] <= SIGNAL_TC_WITHIN))
    return out


def forward_return(series: pd.Series, date, horizon: int = 20):
    """(期末報酬, 期間最低點報酬)；不足 horizon 日回傳 (None, None)。"""
    pos = series.index.get_loc(date)
    fwd = series.iloc[pos + 1: pos + 1 + horizon]
    if len(fwd) < horizon:
        return None, None
    p0 = series.iloc[pos]
    return float(fwd.iloc[-1] / p0 - 1.0), float(fwd.min() / p0 - 1.0)


def evaluate(series: pd.Series, wf: pd.DataFrame, events,
             lookback: int = 30, horizon: int = 20) -> dict:
    sig_dates = set(wf.index[wf["signal"]])
    captured = 0
    for ev in events:
        pos = series.index.get_loc(ev["trigger_date"])
        window_dates = set(series.index[max(0, pos - lookback):pos])
        if sig_dates & window_dates:
            captured += 1
    fp = tot = 0
    sig_fwd, nosig_fwd = [], []
    for d in wf.index:
        r_end, r_min = forward_return(series, d, horizon)
        if r_end is None:
            continue
        if d in sig_dates:
            tot += 1
            if r_min > -0.03:
                fp += 1
            sig_fwd.append(r_end)
        else:
            nosig_fwd.append(r_end)
    mw_pvalue = None
    if len(sig_fwd) >= 3 and len(nosig_fwd) >= 3:
        mw_pvalue = float(mannwhitneyu(sig_fwd, nosig_fwd,
                                       alternative="less").pvalue)
    return dict(
        n_events=len(events), captured=captured,
        capture_rate=(captured / len(events)) if events else None,
        n_signals=int(wf["signal"].sum()), n_signals_evaluable=tot,
        fp_rate=(fp / tot) if tot else None,
        sig_fwd_median=float(np.median(sig_fwd)) if sig_fwd else None,
        nosig_fwd_median=float(np.median(nosig_fwd)) if nosig_fwd else None,
        mw_pvalue=mw_pvalue,
    )
```

- [ ] **Step 4: 跑測試確認通過**

```bash
.venv/bin/python -m pytest tests/test_lppls_walkforward.py -v
```
Expected: 6 passed。`test_walk_forward_bubble_series_emits_signal_before_crash` 是合成泡沫的端到端檢驗；若 fail，先確認 make_synthetic 的 tc=165 落在 refit 日的 30 天訊號窗內。

- [ ] **Step 5: Commit**

```bash
git add scripts/lppls/walkforward.py tests/test_lppls_walkforward.py
git commit -m "feat(lppls): walk-forward 引擎+回檔事件偵測+三條事前通過準則評估"
```

---

### Task 5: Confirmation 四層 (`confirmation.py`)

**Files:**
- Create: `scripts/lppls/confirmation.py`
- Test: `tests/test_lppls_confirmation.py`

設計：每層拆 pure scorer（吃 pandas 物件、可單元測試）＋ DB loader（thin SQL，不做單元測試）。

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_lppls_confirmation.py
import numpy as np
import pandas as pd

from scripts.lppls.confirmation import (
    score_margin, score_institutional, score_iv, score_ofi, aggregate,
)


def _s(values):
    return pd.Series(values, index=pd.bdate_range("2026-07-01", periods=len(values)))


def test_score_margin_accelerating_leverage():
    fin = _s(list(np.linspace(3000, 3050, 20)) + list(np.linspace(3060, 3300, 10)))
    assert score_margin(fin)["score"] == 1        # 近 5 日增速 z > 1


def test_score_margin_flat_and_short_history():
    assert score_margin(_s([3000.0] * 30))["score"] == 0
    assert score_margin(_s([3000.0] * 5)) is None  # < 10 筆


def test_score_institutional_buy_then_sell():
    fnet = _s([1e9] * 17 + [-2e9, -1e9, -1e9])    # 20日累計買超但近3日轉賣
    assert score_institutional(fnet)["score"] == 1
    steady = _s([1e9] * 20)
    assert score_institutional(steady)["score"] == 0


def test_score_iv_inverted_term_or_low_vrp():
    """term_slope 倒掛定義 Near>Far → slope POSITIVE = backwardation = stress。"""
    vrp = _s([5.0] * 30)
    # slope > 0 → Near>Far 倒掛 → score 1
    assert score_iv(term_slope_latest=+0.5, vrp_series=vrp)["score"] == 1
    # low vrp regardless of slope (slope < 0 = contango, normal)
    low_vrp = _s([5.0] * 29 + [-3.0])
    assert score_iv(term_slope_latest=-0.5, vrp_series=low_vrp)["score"] == 1
    # slope < 0 (contango/normal) + normal vrp → score 0
    assert score_iv(term_slope_latest=-0.5, vrp_series=vrp)["score"] == 0


def test_score_ofi_price_up_flow_fading():
    fading = _s([0.5, 0.4, 0.3, 0.1, -0.1])
    assert score_ofi(fading, index_ret5=0.03)["score"] == 1
    assert score_ofi(fading, index_ret5=-0.02)["score"] == 0
    rising = _s([0.1, 0.2, 0.3, 0.4, 0.5])
    assert score_ofi(rising, index_ret5=0.03)["score"] == 0


def test_aggregate_labels():
    full = {"margin": {"score": 1}, "inst": {"score": 1},
            "iv": {"score": 1}, "ofi": {"score": 1}}
    assert aggregate(full)["label"] == "強警戒"
    mid = {"margin": {"score": 1}, "inst": {"score": 1},
           "iv": {"score": 0}, "ofi": {"score": 0}}
    assert aggregate(mid)["label"] == "中性"
    weak = {"margin": {"score": 0}, "inst": None,
            "iv": {"score": 0}, "ofi": {"score": 1}}
    agg = aggregate(weak)
    assert agg["label"] == "降級"
    assert agg["n_available"] == 3
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
.venv/bin/python -m pytest tests/test_lppls_confirmation.py -v
```
Expected: FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 實作**

```python
# scripts/lppls/confirmation.py
"""四層泡沫 confirmation（spec §4）— pure scorer 與 DB loader 分離。

層次: margin(融資增速)/inst(法人高檔調節)/iv(IV結構)/ofi(價漲流衰竭)。
各層 None = 資料不足，不計入分母。標籤: 全滿=強警戒, >=一半=中性, 其餘=降級。
"""
import numpy as np
import pandas as pd

from scripts.lppls.db import connect

# ---------- pure scorers ----------

def score_margin(fin_series: pd.Series):
    """融資餘額 5 日增速 z-score > 1 → 正回饋加速中。"""
    if len(fin_series) < 10:
        return None
    chg5 = fin_series.diff(5).dropna()
    if len(chg5) < 5 or chg5.std() == 0:
        return dict(score=0, z=0.0)
    z = float((chg5.iloc[-1] - chg5.mean()) / chg5.std())
    return dict(score=int(z > 1.0), z=z)


def score_institutional(fnet_series: pd.Series):
    """20 日累計外資買超 > 0 且近 3 日轉賣 → 高檔調節。"""
    if len(fnet_series) < 20:
        return None
    cum20 = float(fnet_series.tail(20).sum())
    last3 = float(fnet_series.tail(3).sum())
    return dict(score=int(cum20 > 0 and last3 < 0), cum20=cum20, last3=last3)


def score_iv(term_slope_latest, vrp_series: pd.Series, skew_series: pd.Series = None):
    """term slope 倒掛(Near>Far, slope>0) 或 VRP 落入自身 20% 分位以下 或 skew 陡化(> 自身 80% 分位)。

    term_slope 定義（上游 option_sentiment_math.compute_term_spread）:
        term_slope = Near ATM IV − Far ATM IV
        POSITIVE → Near > Far → backwardation（壓力/倒掛）
        NEGATIVE → Near < Far → contango（正常）
    """
    if term_slope_latest is None and (vrp_series is None or vrp_series.empty):
        return None
    # slope > 0 → Near>Far 倒掛 (backwardation) → stress signal
    inverted = term_slope_latest is not None and term_slope_latest > 0
    vrp_low = False
    if vrp_series is not None and vrp_series.notna().sum() >= 10:
        vrp_low = bool(vrp_series.iloc[-1] < vrp_series.quantile(0.2))
    skew_steep = False
    if skew_series is not None and skew_series.notna().sum() >= 10:
        skew_steep = bool(skew_series.iloc[-1] > skew_series.quantile(0.8))
    return dict(score=int(inverted or vrp_low or skew_steep),
                inverted=inverted, vrp_low=vrp_low, skew_steep=skew_steep)


def score_ofi(ofi_daily: pd.Series, index_ret5: float):
    """指數 5 日漲但成分 OFI 分數 5 日斜率轉負 → 買方衰竭背離。"""
    if len(ofi_daily) < 5:
        return None
    tail = ofi_daily.tail(5)
    slope = float(np.polyfit(np.arange(len(tail)), tail.values, 1)[0])
    return dict(score=int(index_ret5 > 0 and slope < 0), slope=slope,
                index_ret5=float(index_ret5))


def aggregate(layers: dict):
    avail = {k: v for k, v in layers.items() if v is not None}
    total = sum(v["score"] for v in avail.values())
    n = len(avail)
    if n and total == n:
        label = "強警戒"
    elif n and total >= n / 2:
        label = "中性"
    else:
        label = "降級"
    return dict(total=total, n_available=n, label=label, layers=layers)

# ---------- DB loaders（thin，Task 8 實跑驗證） ----------

def load_margin(asof) -> pd.Series:
    sql = ("SELECT date, sum(fin_value_kilo_ntd) AS fin FROM margin_market_daily "
           "WHERE date <= %s GROUP BY date ORDER BY date")
    with connect() as conn:
        return pd.read_sql(sql, conn, params=(asof,)).set_index("date")["fin"]


def load_institutional(asof, components) -> pd.Series:
    sql = ("SELECT date, sum(foreign_net * close_price) AS fnet "
           "FROM institutional_stock WHERE symbol = ANY(%s) AND date <= %s "
           "GROUP BY date ORDER BY date")
    with connect() as conn:
        return pd.read_sql(sql, conn,
                           params=(list(components), asof)).set_index("date")["fnet"]


def load_iv(asof):
    sql = ("SELECT date, term_slope, vrp_30d FROM vix_daily "
           "WHERE date <= %s ORDER BY date")
    with connect() as conn:
        df = pd.read_sql(sql, conn, params=(asof,)).set_index("date")
    if df.empty:
        return None, pd.Series(dtype=float)
    ts_series = df["term_slope"].dropna()
    latest = float(ts_series.iloc[-1]) if not ts_series.empty else None
    return latest, df["vrp_30d"].dropna()


def load_ofi_daily(asof, components) -> pd.Series:
    sql = ("SELECT ts::date AS date, avg(value) AS ofi FROM stock_ofi "
           "WHERE signal_type = 'ofi_score' AND symbol = ANY(%s) "
           "AND ts::date <= %s GROUP BY 1 ORDER BY 1")
    with connect() as conn:
        return pd.read_sql(sql, conn,
                           params=(list(components), asof)).set_index("date")["ofi"]


def confirm(asof, components, index_ret5: float):
    """LPPLS 訊號日的四層旁證總評。"""
    term_slope, vrp = load_iv(asof)
    layers = dict(
        margin=score_margin(load_margin(asof)),
        inst=score_institutional(load_institutional(asof, components)),
        iv=score_iv(term_slope, vrp),
        ofi=score_ofi(load_ofi_daily(asof, components), index_ret5),
    )
    return aggregate(layers)
```

- [ ] **Step 4: 跑測試確認通過**

```bash
.venv/bin/python -m pytest tests/test_lppls_confirmation.py -v
```
Expected: 6 passed。

- [ ] **Step 5: Commit**

```bash
git add scripts/lppls/confirmation.py tests/test_lppls_confirmation.py
git commit -m "feat(lppls): 四層 confirmation — 融資增速/法人調節/IV結構/OFI背離, pure scorer 可測"
```

---

### Task 6: CLI orchestrator (`lppls_study.py`)

**Files:**
- Create: `scripts/lppls_study.py`

CLI 是 orchestration 膠水（各組件已有測試），不另寫單元測試；以 `--help` smoke test＋Task 8 實跑驗證。

> **修訂（Task 4 review 後，實跑前）:** 準則 1 分母改用 *capturable* 事件（lookback 視窗與 walk-forward 覆蓋區重疊者）— window=100 前的事件本來就無訊號可捕捉，計入分母會系統性壓低捕捉率。報告同時並列全事件 capture_rate 以昭公信。準則 3 主判定仍用 pre-registered 的重疊樣本 MW p，但必列非重疊子樣本 p 作穩健性對照。此修訂於研究實跑（Task 8）前定案，非事後放寬。下方程式碼區塊為原始版本，實際實作以 `scripts/lppls_study.py` 為準。

- [ ] **Step 1: 實作**

```python
#!/usr/bin/env python3
# scripts/lppls_study.py
"""LPPLS 台股泡沫偵測 Phase 1 驗證研究 orchestrator。

用法:
  .venv/bin/python scripts/lppls_study.py                 # 主跑 window=100 r2=0.7 + HPO
  .venv/bin/python scripts/lppls_study.py --no-hpo        # 只跑主參數
  .venv/bin/python scripts/lppls_study.py --window 80 --r2 0.75

產出: analysis/lppls_study_<today>.md（含通過準則判定 + Verification log）
Read-only vs trading-timescaledb。警戒燈定位，無 trade directives。
"""
import argparse
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.lppls import confirmation
from scripts.lppls.db import load_daily_closes, load_taiex
from scripts.lppls.index_builder import (
    CANDIDATES, CORE, build_index, select_components, validate_vs_taiex,
)
from scripts.lppls.walkforward import (
    detect_drawdowns, evaluate, walk_forward, with_signal,
)

HPO_WINDOWS = range(70, 141, 10)
HPO_R2 = [0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
CONFIRM_SINCE = dt.date(2026, 7, 1)   # confirmation 資料齊備後才回填


def fmt(x, pct=False, nd=3):
    if x is None:
        return "N/A"
    return f"{x:.1%}" if pct else f"{x:.{nd}f}"


def run(window: int, r2_min: float, step: int, do_hpo: bool, out_path: Path):
    lines = []
    today = dt.date.today()

    # 1. 指數建構
    closes = load_daily_closes(set(CORE) | set(CANDIDATES))
    comps, weights = select_components(closes)
    index_s = build_index(closes, weights)
    taiex = load_taiex()
    corr, n_overlap = validate_vs_taiex(index_s, taiex)
    proxy_ok = corr > 0.95

    lines += [
        f"# LPPLS 台股泡沫偵測 — Phase 1 驗證研究 ({today})", "",
        "**定位:** 泡沫警戒燈（不做空、無 trade directives）。"
        "Spec: docs/superpowers/specs/2026-08-27-lppls-tw-bubble-detection-design.md", "",
        "## 1. 自建電子權值指數", "",
        f"- 成分 {len(comps)} 檔: {', '.join(comps)}",
        "- 權重前五: " + ", ".join(
            f"{s} {w:.1%}" for s, w in
            sorted(weights.items(), key=lambda kv: -kv[1])[:5]),
        f"- 期間: {index_s.index[0]} → {index_s.index[-1]}（{len(index_s)} 交易日）",
        f"- vs TAIEX 日報酬相關: **{corr:.4f}**（重疊 {n_overlap} 日，門檻 0.95 → "
        f"{'合格' if proxy_ok else '不合格'}）", "",
    ]
    if not proxy_ok:
        lines.append("> ⚠️ proxy 不合格 — 以下結果僅供參考，應擴大成分股重跑。")

    # 2. 事件集
    events = detect_drawdowns(index_s, threshold=0.05)
    lines += ["## 2. 回檔事件集（滾動高點回落 ≥5%）", ""]
    if events:
        lines.append("| 前高日 | 觸發日 | 觸發時深度 |")
        lines.append("|---|---|---|")
        lines += [f"| {e['peak_date']} | {e['trigger_date']} | {e['depth']:.1%} |"
                  for e in events]
    else:
        lines.append("期間內無 ≥5% 回檔事件 — 準則 1 無法評估。")
    lines.append("")

    # 3. 主參數 walk-forward
    wf_raw = walk_forward(index_s, window=window, step=step)
    wf = with_signal(wf_raw, r2_min=r2_min)
    res = evaluate(index_s, wf, events)
    sig_rows = wf[wf["signal"]]
    lines += [f"## 3. Walk-forward（window={window}, step={step}, R²≥{r2_min}）", "",
              f"- 擬合次數 {len(wf)}，qualifies {int(wf['qualifies'].sum())}，"
              f"訊號 {res['n_signals']}（可評估 {res['n_signals_evaluable']}）", ""]
    if not sig_rows.empty:
        lines.append("| 訊號日 | R² | tc(日) | m | ω |")
        lines.append("|---|---|---|---|---|")
        lines += [f"| {d} | {r.r2:.3f} | {r.tc_days:.0f} | {r.m:.2f} | {r.omega:.1f} |"
                  for d, r in sig_rows.iterrows()]
        lines.append("")

    # 4. 通過準則判定
    c1 = res["capture_rate"] is not None and res["capture_rate"] >= 0.5
    c2 = res["fp_rate"] is not None and res["fp_rate"] < 0.5
    c3 = (res["mw_pvalue"] is not None and res["mw_pvalue"] < 0.1
          and res["sig_fwd_median"] is not None
          and res["nosig_fwd_median"] is not None
          and res["sig_fwd_median"] < res["nosig_fwd_median"])
    verdict = "通過 → 進 Phase 2" if (c1 and c2 and c3) else "未通過 → 誠實負結果收檔"
    lines += [
        "## 4. 事前通過準則判定", "",
        "| 準則 | 實測 | 門檻 | 判定 |", "|---|---|---|---|",
        f"| 1. 回檔捕捉率 | {fmt(res['capture_rate'], pct=True)}"
        f"（{res['captured']}/{res['n_events']}） | ≥50% | {'✅' if c1 else '❌'} |",
        f"| 2. False positive 率 | {fmt(res['fp_rate'], pct=True)} | <50% "
        f"| {'✅' if c2 else '❌'} |",
        f"| 3. 訊號日 fwd20 劣化 | 中位數 {fmt(res['sig_fwd_median'], pct=True)} vs "
        f"{fmt(res['nosig_fwd_median'], pct=True)}, MW p={fmt(res['mw_pvalue'])} "
        f"| p<0.1 且中位數較低 | {'✅' if c3 else '❌'} |",
        "", f"**判定: {verdict}**", "",
        "> 誠實警告: 399 交易日樣本、事件數 "
        f"{res['n_events']} 次，統計力天生有限；訊號數 {res['n_signals']} 少時 "
        "Mann-Whitney 檢定力低。本判定不可過度外推。", "",
    ]

    # 5. HPO
    if do_hpo:
        lines += ["## 5. HPO 敏感度（capture / FP，各格 = 捕捉率;FP率;訊號數）", "",
                  "| window \\ R² | " + " | ".join(f"{r}" for r in HPO_R2) + " |",
                  "|" + "---|" * (len(HPO_R2) + 1)]
        for wnd in HPO_WINDOWS:
            raw = wf_raw if wnd == window else walk_forward(index_s, window=wnd,
                                                            step=step)
            cells = []
            for r2t in HPO_R2:
                r = evaluate(index_s, with_signal(raw, r2_min=r2t), events)
                cells.append(f"{fmt(r['capture_rate'], pct=True)};"
                             f"{fmt(r['fp_rate'], pct=True)};{r['n_signals']}")
            lines.append(f"| {wnd} | " + " | ".join(cells) + " |")
        lines.append("")

    # 6. Confirmation 回填（近期訊號 dry-run，不進準則）
    recent = [d for d in sig_rows.index if d >= CONFIRM_SINCE]
    lines += ["## 6. Confirmation 分層回填（dry-run，不進通過準則）", ""]
    if recent:
        for d in recent:
            pos = index_s.index.get_loc(d)
            ret5 = float(index_s.iloc[pos] / index_s.iloc[max(0, pos - 5)] - 1.0)
            agg = confirmation.confirm(d, comps, ret5)
            lines.append(f"- {d}: **{agg['label']}**（{agg['total']}/"
                         f"{agg['n_available']}）— "
                         + ", ".join(f"{k}={'∅' if v is None else v['score']}"
                                     for k, v in agg["layers"].items()))
    else:
        lines.append(f"{CONFIRM_SINCE} 後無訊號日，無可回填樣本。")
    lines += ["", "## Verification log", "",
              "- 本報告數字皆由本 script 對 DB 實算產出；分布性措辭（若有）依 "
              "Golden Rule 0 另跑 scripts/verify_flow_zscore.py 佐證。",
              f"- 產出指令: `.venv/bin/python scripts/lppls_study.py --window {window} "
              f"--r2 {r2_min}`", ""]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入 {out_path}")
    print(f"判定: {verdict}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--window", type=int, default=100)
    ap.add_argument("--r2", type=float, default=0.7)
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--no-hpo", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = Path(args.out) if args.out else Path(
        f"analysis/lppls_study_{dt.date.today()}.md")
    run(args.window, args.r2, args.step, not args.no_hpo, out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

```bash
.venv/bin/python scripts/lppls_study.py --help
```
Expected: 印出 usage 與參數說明，exit 0。

- [ ] **Step 3: 全套測試迴歸**

```bash
.venv/bin/python -m pytest tests/test_lppls_fitter.py tests/test_lppls_index.py tests/test_lppls_walkforward.py tests/test_lppls_confirmation.py -v
```
Expected: 25 passed。

- [ ] **Step 4: Commit**

```bash
git add scripts/lppls_study.py
git commit -m "feat(lppls): study CLI — 指數建構→事件集→walk-forward→準則判定→HPO→confirmation回填"
```

---

### Task 7: ETH lppls 套件 cross-check

**Files:**
- Create: `scripts/lppls/crosscheck.py`

- [ ] **Step 1: 實作（套件缺席時優雅跳過）**

```python
# scripts/lppls/crosscheck.py
"""以 ETH `lppls` pip 套件對同一序列 cross-check 自家 fitter 的 tc。

用法: .venv/bin/python -m scripts.lppls.crosscheck
套件未安裝 → 印 SKIP 訊息, exit 0（報告據此註記）。
"""
import sys

import numpy as np

from scripts.lppls.fitter import fit, make_synthetic


def main():
    try:
        from lppls import lppls as eth_lppls
    except ImportError:
        print("SKIP: lppls 套件未安裝，cross-check 略過（報告註記）")
        return 0

    prices = make_synthetic(100, tc=120.0, m=0.5, omega=8.0, noise=0.0005)
    ours = fit(prices)

    t = np.arange(100, dtype=float)
    model = eth_lppls.LPPLS(observations=np.array([t, np.log(prices)]))
    tc_eth, m_eth, w_eth, *_ = model.fit(max_searches=25)

    diff = abs(ours.tc - tc_eth)
    print(f"ours: tc={ours.tc:.1f} m={ours.m:.2f} w={ours.omega:.1f}")
    print(f"eth : tc={tc_eth:.1f} m={m_eth:.2f} w={w_eth:.1f}")
    print(f"tc 差異 {diff:.1f} 交易日 → {'OK (<10)' if diff < 10 else '⚠️ 檢查實作'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 執行並記錄輸出**

```bash
.venv/bin/python -m scripts.lppls.crosscheck
```
Expected: 兩邊 tc 差異 <10 交易日印 OK；或印 SKIP。輸出全文貼入 Task 8 報告的 Verification log。若差異 ≥10：先檢查 ETH 套件的 t 定義（calendar ordinal vs index）再比對，仍異常則暫停並回報用戶。

- [ ] **Step 3: Commit**

```bash
git add scripts/lppls/crosscheck.py
git commit -m "feat(lppls): ETH lppls 套件 tc cross-check（缺套件優雅跳過）"
```

---

### Task 8: 執行研究、撰寫報告、判定

**Files:**
- Create: `analysis/lppls_study_<today>.md`（由 script 產出後人工補充）
- Modify: `docs/plans/2026-08-27-lppls-tw-bubble-detection.md`（勾選完成）

- [ ] **Step 1: 主跑**

```bash
.venv/bin/python scripts/lppls_study.py 2>&1 | tail -20
```
Expected: 印出「報告已寫入 analysis/lppls_study_<date>.md」與判定行。若 DB 連線失敗照 MCP Debugging SOP 排查（config → env → service）。

- [ ] **Step 2: 審閱報告品質**

檢查產出報告：
1. proxy 相關 >0.95（不合格 → 調整 `n_supplement` 加大成分重跑，記錄兩版相關）
2. 事件集數量與日期合理（對照 taiex_ema_daily 已知走勢）
3. 三條準則判定行都有實數（無 N/A 判定為✅的情況）
4. HPO 表 48 格完整
5. cross-check 輸出（Task 7）貼入 Verification log 段

- [ ] **Step 3: 人工補充報告結論**

在報告末尾加「## 結論與後續」段：判定通過 → 列 Phase 2 routine 設計要點（收盤後 refit、confirmation score、inbox topic=lppls、watchdog 納管）；未通過 → 寫明哪條準則敗在哪、誠實負結果、是否值得改參數重試（僅可作為新研究，不得回頭改本次準則）。

- [ ] **Step 4: Commit 報告**

```bash
git add analysis/lppls_study_*.md docs/plans/2026-08-27-lppls-tw-bubble-detection.md
git commit -m "feat(study): LPPLS 電子權值指數泡沫警戒驗證 — <通過/未通過>三條事前準則

capture=<X>%, FP=<Y>%, MW p=<Z>; 指數 vs TAIEX corr=<C>"
```

（commit message 中的占位值以實跑結果代入。）

- [ ] **Step 5: 收尾**

依 `superpowers:verification-before-completion`：全套 pytest 綠、報告存在、判定明確，才回報完成。若通過準則 → 與用戶確認後另開 Phase 2 spec；未通過 → 依 vault 維護工作流把負結果摘要寫入 `vault/log.md` 並推 inbox。
