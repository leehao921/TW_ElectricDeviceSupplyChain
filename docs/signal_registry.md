# 訊號總目錄 — 做多 / 做空 家族編目

> 2026-08-27 建立。分級: **VALIDATED**（統計驗證通過）/ **WEAK**（方向存在、力度不足或樣本單一 regime）/ **NO-EDGE**（系統性檢定無超額，僅供 confluence）/ **觀察**（機制合理、累積樣本中）/ **儀表**（環境變數，非進出場訊號）。
> 2026-08-27 四家族系統性驗證（2025-01 起 400 交易日 × 938 檔，de-cluster + 同日市場中位基準）: `analysis/signal_validation_20260827.md`。
> 每日 17:50 `signal-scan` 產多空名單 + T+5/T+20 自我校驗；每週五 19:50 `signal-ledger` 彙整滾動命中率。

## 做多訊號

| # | 訊號 | 定義 | 分級 | 追蹤源 |
|---|---|---|---|---|
| L1 | 處置解除·外資買超組 | 解除前 20D 外資買超的處置股，解除後 +10D | **VALIDATED**（backtest +3.59%/勝 51%, n=492）| disposition history |
| L2 | BB squeeze Buy | 波動壓縮突破，5 日 followthrough | WEAK（波段 3/19，靠大贏家；T+1 勿當沖）| bb_followthrough history |
| L3 | 外資結構 hedged_accumulation | 現貨 5D z>+0.5 且期貨空單 z<-0.5（吸籌+對沖）| **反向-WEAK**（backtest 該州日 → TXF +5D -2.65% vs 中性日 +1.75%，n=13 僅 126 日樣本 — 觸發後短線偏弱，勿當多方確認）| foreign_structure 日誌 |
| L4 | 左側賣壓竭盡 | 距高 -20%+ 且外資 5D 轉正（+P/B GREEN 加分）| **NO-EDGE**（市場級 n=1798 無超額 — 單獨無效，僅供左側 confluence 之一，需搭 P/B GREEN + 基本面）| signal-scan 觀察名單 |
| L5 | 錯價修復 | 基本面強+籌碼冷 → 外資週買 >3 億確認 | 觀察（華航 8/27 首例觸發）| position-watch |
| L6 | 權證佈多榜 | 認購方向能量 top10（內外盤 proxy）| 觀察（T+5 命中統計累積中）| warrant_flow history |
| L7 | 融資急增 top10% | 橫斷面融資增速前 10% | WEAK（+5D 61% 贏大盤、絕對報酬負）| margin_daily 週跑 |
| L8 | 00891 回檔帶 | 距 ATH -20/-30/-35%（存股加碼，非交易）| VALIDATED（歷史三谷全收復）| etf-00891 watch |
| L9 | 隔日沖·鎖停尾盤買 | 漲停鎖死尾盤買→隔開賣 | VALIDATED 但**不可執行**（買不到；勿追）| 回測存檔 |

## 做空訊號

| # | 訊號 | 定義 | 分級 | 追蹤源 |
|---|---|---|---|---|
| S1 | 處置解除·外資賣超組 | 解除前外資賣超，解除後續弱 | **VALIDATED**（-1.73%/勝率僅 40%，空方比多方一致）| disposition history |
| S2 | 融資急減 × 量能形態 | 減×爆量=投降型（-2.16%/贏 20%）、減×縮量=陰跌型（-1.84%）| WEAK→觀察升級中（量能交叉後強度 3 倍，樣本小；日掃 T+5 自我校驗累積中）| signal-scan 日掃 + ledger 週跑 |
| S3 | 乖離 98pct + P/B RED | 個股乖離 MA20 歷史 98 分位 + P/B 85 分位 | **regime 條件型**（市場級 backtest n=1750: +20D 超額 **+2.32%** = 牛市動能非反轉；分段 2026H1 +2.9% vs 2026H2 -4.5% — 僅空 regime 且 P/B RED confluence 才可空；2408/貨櫃兩例屬 2026H2 型）| signal-scan 觀察名單 + pb_lights |
| S4 | 外資撤+投信頂 | 外資 20D 大賣、投信承接的弱結構 | **NO-EDGE**（市場級 n=1442 無超額且各半年符號翻轉 — 除名為進出場訊號，僅存為結構描述）| 法人流向 |
| S5 | 權證佈空榜 | 認售方向能量 top10 | 觀察（**反指標傾向**：×融資增後 +4.10% — 若滿季成立則反向讀）| warrant_flow history |
| S6 | 外資結構 distribution_cover | 現貨出+期貨空單回補 | 觀察（L3 對偶；backtest 樣本不足 n<10 未定級）| foreign_structure |
| S7 | 強勢股開盤追多 | 強勢池隔日開盤買 = 43.5% 勝率負期望 | VALIDATED（**反指標**: 勿做，或平開~小高開放空 54.7% 薄）| 回測存檔 |
| S8 | RRG 落後轉弱 | 板塊/題材 RS<0 且加速度<0 | 儀表（避開池：碳化矽/功率半導體型）| rotation 分析 |

## 系統性風險儀表（非個股方向）

| 儀表 | 警戒定義 | 含義 |
|---|---|---|
| 週/月 IV 倒掛 | wm_spread > +2（7/29=+8.2、8/5=+10.4 級距）| 即期事件恐慌 |
| VRP30 | 厚（pct>70）賣方肥 / 薄（pct<30）保險便宜 | 買保護時點 |
| P/B 廣度 | RED 占比 >80% + DRAM S1 RED | 晚週期高熱 |
| Regime gate | 5D 量 <1 兆降權 / TAIEX <39,385 broken | 黑天鵝 playbook 啟動線 |
| Brent 85/100 | <85 緩和 / >100 升溫 | 航空 vs 海運兩腿反向 |

## 追蹤機制

- **日**：position-watch 15:10（個股觸發）、各儀表 routine（08:20-08:35）、foreign-structure 17:10、warrant 17:40、**signal-scan 17:50（市場級多空名單 S2v2/S1/L1 + S3 觀察，名單股自動 T+5/T+20 追蹤）**、margin-vix 18:10
- **週**（五 19:50）：`signal_ledger.py` 彙整各家族滾動命中率 + 活躍實例 → Discord
- **月/季**：S3 skew 樣本外（10 月）、S4 VRP 對齊重跑、融資訊號滿季確認（10 月底）
