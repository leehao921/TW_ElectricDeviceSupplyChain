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
