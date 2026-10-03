# BB follow-through 加入葛蘭碧 B3/B2 觀察標籤

**日期:** 2026-10-03 · **依據:** `analysis/bb_granville_verify_2026-10-03.md`

## 背景

用戶想把「小哥版葛蘭碧」(月線方向 / 價量 / 爆量換手 / 主力籌碼) 加進 BB tracer。依 signal registry 紀律先驗證 136 筆 BB Buy:
四標籤皆無可驗證 edge (10 次檢定無一過 Bonferroni 0.005; 回升/價漲量增方向反而較差)。
唯一候選: **B3 站穩上揚月線 vs B2 假跌破後站回**, T+20 超額 +8.7pt, 日內區塊 permutation p=0.041 → 觀察級。

## 做法

1. `scripts/bb_followthrough_track.py`
   - 純函式 `granville_tag(closes) -> str | None`: 輸入進場日 (含) 以前收盤序列 (舊→新, ≥25 筆), 口徑與驗證腳本完全一致:
     - MA20 5 日斜率 = (MA20[t] − MA20[t−5]) / MA20[t−5]
     - 斜率 > 0 且 收盤 > MA20: 前 5 日 (t−5..t−1) 任一收盤 < 當日 MA20 → `B2`, 否則 `B3`
     - 斜率 ≤ 0 且 收盤 > MA20 → `S2`; 其餘 → `below`; 資料不足 → None
   - `fetch_closes(conn, ticker, as_of, n=30)` 讀 `stock_daily_ohlcv`
   - `add_new_breakouts` 進場時寫 `entry["granville"]`
   - digest 顯示資訊標籤 (📐 B3 站穩月線 / 📐 B2 假跌破後站回 / 📐 S2 突破下彎月線, 標「觀察」)
   - **不寫入 `rules_hit`** (不影響既有 Rule 1–5 與命中率統計)
   - `graduate_stale` 寫 history 時帶 `granville` 欄位 → 供重驗
2. `docs/signal_registry.md`: 新增 L2a 葛蘭碧 B3/B2 (觀察) 與 L2b 小哥版四標籤 (NO-EDGE)

## 重驗條件

B3 / B2 各累積 T+20 n ≥ 60 時重驗; 升級門檻 = 日內區塊 p < 0.01 且方向不變; 否則降為 NO-EDGE。

## 測試

`tests/test_bb_granville.py`: B3 / B2 / S2 / below / 資料不足、entry 帶 granville、digest 顯示、history 帶欄位、rules_hit 不受影響。
