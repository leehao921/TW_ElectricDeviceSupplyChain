# TXF Level Map ＋ 亞洲市場地圖 盤前推播 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** 每交易日 08:40（buy-list 08:50 前）推播台指期關鍵位置圖＋隔夜美股／亞股 T-1／匯率地圖，inbox topic=`txf-levels`。

**Architecture:** `scripts/txf_level_map.py` 單檔：volume profile（ohlcv_1m_txf）、OI 牆（option_oi_daily 只取未到期 expiry）、GEX flip（subprocess options_quant 解析）、夜盤變動、外資期貨 OI、美股隔夜（復用 geo_attr loaders.load_yf 的 staleness cache）、亞股 T-1（asia_index_daily）、FX（fx_daily）。launchd `com.lulala.txf-level-map` Mon-Fri 08:40。

---

## 輸出格式（inbox msg 多行）

```
📍 TXF 位置圖 9/8 | 夜盤 47177 (+466, 日盤收 46711)
壓力: 47300 真空 | 47500 C牆711 | 48000 C牆1542(月)
支撐: 47000 C牆(易位) | 46650 flip | 46100-46200 HVN12.7% | 46000 P牆479(月)
外資期淨空 -82,389 口 | 投信 +76,174
🌏 隔夜: SOX +x.x% VIX 14.5 UST10Y 4.67 Brent 85.8 DXY xx.x
亞股T-1: N225 +x% KS11 +x% HSI +x% CSI300 +x% TWII +x%
```

## 計算規格（皆已於 2026-09-06 session 內驗證過查詢）

1. **夜盤**: ohlcv_1m_txf 最後 bucket close vs 最後日盤(13:45 TPE 前)收盤
2. **Volume profile**: 近 20/5 交易日 1m close×volume，100 點 bucket；HVN 前 3＋現價上下最近 LVN
3. **OI 牆**: option_oi_daily 最新 settle_date、`expiry >= 今日`（勿列已到期牆 — 9/4 教訓）、underlying='TX'、現價 ±2500 點內；近週選＋月選各取 put/call 前 3
4. **GEX flip**: `subprocess` 跑 `options_quant.py --date <T-1> --window 08:45-13:45`，regex `flip=([\d.]+)`；失敗 → 訊息標 `flip=N/A`（fail-soft）
5. **外資/投信期淨 OI**: futures_oi_daily 最新 settle_date
6. **美股隔夜**: loaders.load_yf（^SOX/^VIX/^TNX＋brent cache）— staleness 邏輯 08:40 自動重抓週五/昨日收盤；漲跌 = 最後兩筆
7. **亞股 T-1**: asia_index_daily 最新兩日 close 算 1d %（N225/KS11/HSI/CSI300/TWII/NSEI 六檔）；FX: fx_daily USDTWD/USDJPY/DXY
8. 推播失敗 fail-soft；`--dry-run` 不推播

## Tasks

### Task 1: 核心（TDD — pure functions 可測）
- [ ] tests: profile bucket/HVN/LVN 計算、OI 牆過濾（到期剔除）、夜盤切割（13:45 界）、msg 組裝含 N/A 路徑
- [ ] 實作＋`--dry-run` 實跑驗證
- [ ] Commit

### Task 2: launchd（controller）
- [ ] plist 08:40 Mon-Fri（margin-vix 模板）、bootstrap、kickstart 驗證 inbox
- [ ] watchdog registry＋test 計數 23→24、memory/vault
- [ ] Commit
