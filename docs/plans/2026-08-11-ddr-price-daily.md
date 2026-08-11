# DDR 現貨價每日自動更新 (取代手動月更)

**日期**: 2026-08-11　**觸發**: 用戶指示「DDR 報價找到最新資料，並且每日自動更新」

**揭露的問題**: `data/memory_cycle_inputs.yaml` 自 6/25 起一直是模板佔位值
($2.85-3.45)，實際 DRAMeXchange DDR4 現貨已 $42.5 — 手動月更機制實質失效，
S2 燈號三個月來用假數字計算。

**方案**: `scripts/ddr_price_daily.py` + launchd `com.lulala.ddr-price`
Mon-Fri 08:20 (memory-cycle 08:40 前)：
- 抓 dramexchange.com 首頁現貨表 (免費、實測可達)：DDR4 8Gb (1Gx8) 3200
  + DDR5 16Gb (2Gx8) session average 與日漲跌
- 日級落 `data/ddr_price_history.json` (idempotent)
- 自動重寫 yaml `ddr4_8gb_spot_usd` = 月均 series (當月=MTD 均)；
  ddr5 合約/MU guidance 手動欄位原樣保留
- inbox topic=ddr-price 一行日報 → Discord；watchdog 已註冊

**歷史錨點** (research agent 2026-08-11 查證，TrendForce 週報原文)：
5 月 32.40/32.40/33.60、6 月 35.12/35.90/36.00、7 月 37.14/39.80/41.10/42.08
→ seed 進 history，月均 32.8 / 35.67 / 40.03 / 42.50 (8月MTD)。

**DDR5 合約**: 絕對價付費牆內 (查證確認無免費源) → 改**指數基準**
2026Q1=100、Q2=145 (TrendForce +43~48% 中值)，QoQ 數學不變，每季手動
append 新值 = 前值 × (1+QoQ)。

**驗證**: 7 tests；live 抓取 $42.50 ✓；launchd kickstart ✓；memory-cycle
dry-run S2a +6.2% 🟢 / S2b +45% 🟢 (真數據) ✓；Discord 已收日報 ✓。
