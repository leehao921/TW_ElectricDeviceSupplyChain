# 訊號總目錄 — 做多 / 做空 家族編目

> 2026-08-27 建立。分級: **VALIDATED**（統計驗證通過）/ **WEAK**（方向存在、力度不足或樣本單一 regime）/ **NO-EDGE**（系統性檢定無超額，僅供 confluence）/ **觀察**（機制合理、累積樣本中）/ **儀表**（環境變數，非進出場訊號）。
> 2026-08-27 四家族系統性驗證（2025-01 起 400 交易日 × 938 檔，de-cluster + 同日市場中位基準）: `analysis/signal_validation_20260827.md`。
> 每日 17:50 `signal-scan` 產多空名單 + T+5/T+20 自我校驗；每週五 19:50 `signal-ledger` 彙整滾動命中率。

## 做多訊號

| # | 訊號 | 定義 | 分級 | 追蹤源 |
|---|---|---|---|---|
| L1 | 處置解除·外資買超組 | 解除前 20D 外資買超的處置股，解除後 +10D | **VALIDATED**（backtest +3.59%/勝 51%, n=492）| disposition history |
| L2 | BB squeeze Buy | 波動壓縮突破，5 日 followthrough | WEAK（波段 3/19，靠大贏家；T+1 勿當沖；2026-10-03 n=136: T+20 對 0050 超額均 -3.50%/中位 -7.12%/勝 31%）| bb_followthrough history |
| L2a | BB Buy × 葛蘭碧 B3 vs B2 | B3=站穩上揚 MA20（前 5 日未收破）vs B2=假跌破後站回 | 觀察（T+20 超額 B3−B2 +8.7pt，日內區塊 permutation p=0.041，n=29/31，未過 Bonferroni；重驗只用 2026-10-01 後進場的樣本外資料，各組 T+20 n≥60，門檻 p<0.01 且方向不變）| bb_followthrough `granville` 欄位 · `analysis/bb_granville_verify_2026-10-03.md` |
| L2b | BB Buy × 小哥版四標籤 | 月線方向回升/反彈、價漲量增、爆量換手(≥2×月均量)、法人 5D 買超 | **NO-EDGE**（10 次檢定無一過 Bonferroni；回升/價漲量增方向反而較差 = 追價負期望；爆量換手 T+20 n=4 待累積）| `analysis/bb_granville_verify_2026-10-03.md` |
| L3 | 外資結構 hedged_accumulation | 現貨 5D z>+0.5 且期貨空單 z<-0.5（吸籌+對沖）| **反向-WEAK**（backtest 該州日 → TXF +5D -2.65% vs 中性日 +1.75%，n=13 僅 126 日樣本 — 觸發後短線偏弱，勿當多方確認）| foreign_structure 日誌 |
| L4 | 左側賣壓竭盡 | 距高 -20%+ 且外資 5D 轉正（+P/B GREEN 加分）| **NO-EDGE**（市場級 n=1798 無超額 — 單獨無效，僅供左側 confluence 之一，需搭 P/B GREEN + 基本面）| signal-scan 觀察名單 |
| L5 | 錯價修復 | 基本面強+籌碼冷 → 外資週買 >3 億確認 | 觀察（華航 8/27 首例觸發）| position-watch |
| L6 | 權證佈多榜 | 認購方向能量 top10（內外盤 proxy）| 觀察（T+5 命中統計累積中）| warrant_flow history |
| L7 | 融資急增 top10% | 橫斷面融資增速前 10% | WEAK（+5D 61% 贏大盤、絕對報酬負）| margin_daily 週跑 |
| L8 | 00891 回檔帶 | 距 ATH -20/-30/-35%（存股加碼，非交易）| VALIDATED（歷史三谷全收復）| etf-00891 watch |
| L9 | 隔日沖·鎖停尾盤買 | 漲停鎖死尾盤買→隔開賣 | VALIDATED 但**不可執行**（買不到；勿追）| 回測存檔 |
| L10 | 強勢整理第一次回測 (Martin) | 1/3/6M 漲 ≥30% 前 25% + BB squeeze/低點墊高/站上 EMA9·21 → 10 日內首次觸及 EMA21/EMA50/AVWAP/前高/缺口 疊合區 → K 棒破前一根高進場 | **短線 NO-EDGE / 中長觀察**：1/5/15/60 分 K 觸發全負（5 分 K n=96 淨 -1.39R；60 分 K 解析至分鐘仍全負）。日/3 日 K + 8% 停損 + 持有 60 日轉正（1d n=41 +1.55%/筆；3d n=12 +9.78%/筆），事件層 T+60 超額 +5~11% 方向一致但 **bootstrap CI 全含 0**、3d 靠 2025H2 五筆撐起 → 不升級；**勿用分 K 緊停損進場**，需更多樣本（資料自 2025-01）| `scripts/strong_pullback.py` · `analysis/strong_pullback_{intraday,long}_2026-10-16.md` |

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

## 盤中微結構 — TXF × GEX 水位（2026-09-02 物理檢定 v3 = F 系列補齊後，analysis/gex_physics_20260902.md）

| 效應 | 檢定結果（v3 牆含週五週選 OI）| 分級 | agent 用法 |
|---|---|---|---|
| ZG regime RV 切換 | S<ZG 日 RV 較大 **8/8 日** (p=0.008，v2 28/28 同向)，比值中位 1.38x（spec 1.5x 未達）| **方向 VALIDATED / 力度弱** | EXPANSION 態 → 縮部位放寬停損；非進出場訊號 |
| PW 觸牆反彈 | t15 反轉勝率 **60%** (n=198, p=0.008)，中位 +41 點 — **跨 v2/v3 兩種牆口徑均存活** | **VALIDATED**（唯一可交易級）| 均值回歸腿：接近 PW 由上緣未破 → 反彈期望 |
| CW 觸牆壓回 | v3 修正牆位後 **50%/49% (p≈1)** — v2 的 57% 係錯誤牆位假象 | **NO-EDGE**（降級）| 勿 fade CW |
| 牆面貫穿追擊 | CW mean +14 勝率 56%（無肥尾）；PW 跌破 mean **-158** 勝率 40%（反被拉回）| **不成立** | 勿追突破；跌破 PW 偏回歸 |

> 口徑：開盤 09:00-09:30 gamma×D-1 OI 靜態水位（v3 OI 含 F 系列週五週選）、日盤 1-min、75 日。歷史 gamma 無週五腿 → ZG 配對日縮至 8 日（誠實標註）；TXU/TXV gamma 2026-09-02 起入庫，動態水位效應與滿樣本重跑屬後續題。

## 系統性風險儀表（非個股方向）

| 儀表 | 警戒定義 | 含義 |
|---|---|---|
| 週/月 IV 倒掛 | wm_spread > +2（7/29=+8.2、8/5=+10.4 級距）| 即期事件恐慌 |
| VRP30 | 厚（pct>70）賣方肥 / 薄（pct<30）保險便宜 | 買保護時點 |
| P/B 廣度 | RED 占比 >80% + DRAM S1 RED | 晚週期高熱 |
| Regime gate | 5D 量 <1 兆降權 / TAIEX <39,385 broken | 黑天鵝 playbook 啟動線 |
| 產業動能廣度 | 產業內通過強勢篩選 (1/3/6M 漲 ≥30% 前 25%) 的比例 + 20 日變化 | 輪動儀表（產業 IC 20 日 +0.27/t 1.6、60 日 +0.42，三個半年同號但未顯著；優於 63 日 RS，加 Martin 整理條件反而變弱；題材層/大盤層無效）。`scripts/sector_breadth.py`，treemap routine 每日寫 `data/sector_breadth_history.csv`；2027-04 重跑 `--validate`，t≥2 升觀察訊號 |
| Brent 85/100 | <85 緩和 / >100 升溫 | 航空 vs 海運兩腿反向 |

## 追蹤機制

- **日**：position-watch 15:10（個股觸發）、各儀表 routine（08:20-08:35）、foreign-structure 17:10、warrant 17:40、**signal-scan 17:50（市場級多空名單 S2v2/S1/L1 + S3 觀察，名單股自動 T+5/T+20 追蹤）**、margin-vix 18:10
- **週**（五 19:50）：`signal_ledger.py` 彙整各家族滾動命中率 + 活躍實例 → Discord
- **月/季**：S3 skew 樣本外（10 月）、S4 VRP 對齊重跑、融資訊號滿季確認（10 月底）
