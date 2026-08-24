# Brent 85/100 每日監測 routine

## Why
2026-08-24 實測：航空(2610/2618) vs Brent 近60日相關 -0.22~-0.27（增強中）、長榮海(2603) +0.22（正相關）— 美伊地緣油價溢價同一因子反向作用於持倉(2603)與左側候選(華航)。用戶核准將 Brent 85/100 兩條線納入每日監測並定期推送。

## 設計
- `scripts/brent_watch.py`：yfinance BZ=F 日線 → 分區（<85 緩和帶 / 85-100 中性帶 / >100 升溫帶）+ 跨線偵測（state `data/brent_state.json`）+ 60 日 vs 2603/2610 相關性 → push inbox topic=`brent-watch`（跨線時 severity 升級）
- 訊息含 gate 含義：<85 → 華航 Tranche 2 門檻放寬 + 2603 階梯二輔助觸發；>100 → 華航降半碼、2603 運價順風
- launchd `com.lulala.brent-watch` Mon-Fri 08:25（盤前，接 08:35 wave）
- routine_watchdog registry 加 ("brent-watch", time(8,25), time(13,30)) → 16 checks

## TDD
classify_zone / detect_cross（含首次無 state）/ build_msg 純函式紅綠；watchdog 測試 15→16。

## 驗證
手動跑 → inbox 有 entry → discord-forward 5 分內轉發；kickstart launchd 確認 exit 0。
