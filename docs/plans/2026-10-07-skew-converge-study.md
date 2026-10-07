# skew 收斂作為上漲領先指標 — 日級回測 (2026-10-07)

## 動機
9/29→10/06 上漲 (+4.6%,主升段 10/02 夜盤) 前,10 月 TXO 25Δ skew 由 +1.91 (9/24) 收斂至 +0.52 (10/02),
9/30 翻負;ATM IV 同期下降、無預警。問題: 「skew 數日收斂」是否有可重複的 T+1/3/5 領先性?
與既有 S3 (盤中 skew 急變 +15m) 不重疊 — 本研究為日級。

## 方法 (scripts/skew_converge_study.py)
- 日 skew: TXO 月選前月 (DTE ≥ 5,避開到期雜訊),日盤 13:00-13:30 skew_25d 平均 (vol-pt)。
- 價格: ohlcv_1m_txf symbol=TXF 日盤 ≤13:45 最後一根收盤;報酬 close_t → close_{t+h}, h=1,3,5 交易日。
- 訊號 A: Δ3 skew = skew_t − skew_{t−3} ≤ −1.0 vol-pt;訊號 B: skew_t < 0 (call 比 put 貴)。
- de-cluster: 事件間隔 < 3 交易日只取第一個。基準 = 非事件日。
- 全樣本 Spearman(Δ3 skew, ret_{t+h})。
- 護欄: n < 20 → 「樣本不足,不下結論」;不使用分布性形容詞 (Golden Rule 0);10/05 前 IV 輸入
  有舊成交價問題 (e3ee0fd 修),結果分 10/05 前後註記。無交易指令。

## 產出
analysis/skew_converge_study_2026-10-07.md (含 Verification log);registry 視結果登記。
