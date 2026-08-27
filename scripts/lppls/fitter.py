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
