# GEX 狀態機 + Event-based 實時監控 + IV Curve Z-score — 計畫

2026-09-01。用戶需求三件：(1) ascii 儀表自動排程（之前為一次性交付未排程）；
(2) **event-based 實時監控**：監聽 iv_strikes、每 5 分鐘重算 GEX/ZG/CW/PW，
狀態改變才推送；(3) 多到期（週選/月選）IV curve + normalized Z-score 對
300d/90d/20d 歷史比較。

**數據深度現實（誠實約束）**：vix_daily 僅 57 天（2026-05-27 起）、iv_metrics 84
交易日（6/2 起）→ 300d 歷史不存在。Z-score 實作為 20d（全量）/90d（部分 n≈57）/
全樣本（標實際 n），報告一律標註 n，300d 待數據自然累積。

**紅線**：本系統只做 Signal Layer + State Controller（訊號/狀態/儀表），
**不做下單執行**。網格/突破/Wall Fade 的 Agent 執行層屬 nautilus-shioaji
（operator 自管，R44 gate 體系）；本平台輸出一律「分析標註不構成交易指令」。

## 架構（對應用戶分層設計）

### Signal Layer — `scripts/gex_regime_monitor.py`（launchd StartInterval 300s）
- 數據驅動 session gate：iv_strikes 最新列 <10 分鐘才算開盤中（自動涵蓋日/夜盤，休市靜默）
- **多到期複合 GEX**：W1/W2/M1（前 3 個到期）各自 gamma×OI 廊道 → 逐履約價加總
  → 複合 ZG（累積零穿越）/CW/PW（複合 OI 峰）/總淨 GEX
- IV curve：各到期 ATM IV（現價最近履約價 C/P 平均）→ 期限結構 + 20d/90d/全樣本 z

### State Controller — 純函式（TDD）
- `classify_regime(spot, zg, total_gex)` → MAGNET（spot>ZG 且 GEX>0）/ EXPANSION（spot<ZG 或 GEX<0）/ MIXED（訊號矛盾誠實標註）
- `vol_scalar(|net GEX|, 歷史分位)` → 0-1 縮放係數（部位規模參考值，僅輸出數字）
- `detect_events(prev, curr)` → 事件清單：REGIME_FLIP / CW_PROX（距 CW <0.2%）/
  PW_PROX / ZG_SHIFT（ZG 移動 >100 點）/ IV_Z_CROSS（|z20| 穿越 2）
- 每事件型 30 分鐘 cooldown（state file `data/gex_regime_state.json`）防 spam

### 推送
- **event-based**：僅事件發生時推 inbox topic=`gex-regime`（🚨 REGIME_FLIP / ⚡ 觸牆）
- **排程基準版**：`ascii_dashboard.py` launchd 08:30（盤前）+ 20:15（盤後）Mon-Fri，
  儀表加 IV curve 段（各到期 ATM IV + z 標註）與 regime 狀態行

## 檔案
- `scripts/gex_regime_monitor.py` + `tests/test_gex_regime.py`（新，TDD）
- `scripts/ascii_dashboard.py`（加 IV curve 段 + regime 行，複用 monitor 函式）
- `scripts/launchd/com.lulala.gex-regime.plist`（300s interval）
- `scripts/launchd/com.lulala.dashboard.plist`（08:30/20:15）

## 驗證
```bash
pytest tests/test_gex_regime.py -q
python scripts/gex_regime_monitor.py --dry-run    # 印狀態не推送
python scripts/gex_regime_monitor.py              # 首次=建立基準（推 1 次狀態確立）
launchctl kickstart gui/501/com.lulala.gex-regime # exit 0
python scripts/ascii_dashboard.py                 # IV curve 段出現
```

## 風險
- iv_strikes 240 萬列/日：查詢一律 DISTINCT ON + time >= now()-interval（sargable），5min 頻率下 DB 負載可控
- OI 為 T 日結算（盤中 GEX 用昨收 OI 近似 — 與 options_quant 同口徑，標註）
- 週選到期日當天 W1 廊道消失 → 自動滾到次週（expiry >= 明日）
