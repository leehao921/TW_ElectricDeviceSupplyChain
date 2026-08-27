"""以 ETH `lppls` pip 套件對同一序列 cross-check 自家 fitter 的 tc。

用法: .venv/bin/python -m scripts.lppls.crosscheck
套件未安裝 → 印 SKIP 訊息, exit 0（報告據此註記）。

API 說明（已驗證 lppls 版本）:
  LPPLS(observations) 接受 2×M ndarray：
    row 0 = 時間軸 t（交易日索引）
    row 1 = 觀測值（需為 log-prices；package 內部不再取 log）
  fit(max_searches, minimizer) → (tc, m, w, a, b, c, c1, c2, O, D)
  tc 以 observations[0] 的單位回傳 → 交易日索引，與自家 fitter 直接可比。
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

    # 生成合成序列（tc=120 在視窗末端 t=99 之外 21 交易日）
    prices = make_synthetic(100, tc=120.0, m=0.5, omega=8.0, noise=0.0005)
    ours = fit(prices)

    # ETH package: row 0 = 交易日索引 0..99，row 1 = log(prices)
    # 套件在 matrix_equation 內直接以 P = observations[1] 為 yi，不再取 log，
    # 故傳入 log-prices 以符合 LPPLS 模型定義。
    t = np.arange(100, dtype=float)
    log_prices = np.log(prices)
    observations = np.array([t, log_prices])

    model = eth_lppls.LPPLS(observations=observations)
    # fit() 回傳 (tc, m, w, a, b, c, c1, c2, O, D)；tc 單位同 observations[0]（交易日索引）
    tc_eth, m_eth, w_eth, *_ = model.fit(max_searches=25)

    diff = abs(ours.tc - tc_eth)
    print(f"ours: tc={ours.tc:.1f} m={ours.m:.2f} w={ours.omega:.1f}")
    print(f"eth : tc={tc_eth:.1f} m={m_eth:.2f} w={w_eth:.1f}")
    print(f"tc 差異 {diff:.1f} 交易日 → {'OK (<10)' if diff < 10 else '⚠️ 檢查實作'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
