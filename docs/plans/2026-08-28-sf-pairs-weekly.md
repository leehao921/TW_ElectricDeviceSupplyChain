# 股期多空配對週報 (sf-pairs) — 計畫

2026-08-28。用戶需求：股期（個股期貨）取代融資的可執行池中，**每週**提供可做多與做空的標的，
偏好跨產業/上下游/因子配對，含後續追蹤與停損停利提示。承接階段二「半中性」框架
（docs/plans/2026-08-27-signal-system.md 之延伸）。

## 設計

### Universe
- TAIFEX `cht/2/stockLists` HTML 解析（323 列，欄 2=證券代號、欄 4=「是股票期貨標的」、欄 7=上市/上櫃）
- 快取 `data/stock_futures_universe.json`，30 天過期自動重抓（單次請求，無 Cloudflare 風險）
- 交集 `stock_daily_ohlcv` 有近 30 日數據者

### 多空腿評分（橫斷面，透明因子）
每檔計算：外資 5D/20D 淨額（`institutional_stock.foreign_net × close_price` → 億）、
借券 5D 變化（`margin_daily.sbl_balance`，法人對沖腿）、融資 5D 變化%、乖離 MA20、ATR14。
- `score = z(f5億) + z(f20億) − z(dsbl_norm)`（外資流入 + 借券回補 = 多；反向 = 空）
- 空腿加註 S2 結構 flag（融資 5D 減 = 投降結構佐證）
- 多腿取 top 8、空腿取 bottom 8（去除彼此重疊、去除處置股）

### 配對（pure fn `build_pairs`）
- **優先同產業/同鏈**（上下游對偶 = factor-hedged pair，對齊 long/short pairing 哲學）
- 同產業無對手 → 跨產業 factor pair（標註 β pair）
- 多樣性約束：同一產業最多 2 組，pair 數 ≤5

### 停損停利（分析標註，非指令）
- 每腿：entry=週五 close；停損 = close ∓ 1.5×ATR14；停利 = close ± 2.5×ATR14（空腿鏡像）
- Pair 層：任一腿收盤價破停損 → 整組視為出場；spread 報酬 ≥ +8% 或滿 20 交易日 → 畢業

### 追蹤
- state `data/sf_pairs_state.json`（active pairs：legs/entry/levels/enter_date）
- history `data/sf_pairs_history.json`（畢業樣本：status=stopped/tp/expired + spread_ret）
- 每週更新：以日 close 檢查觸價、算 spread 報酬、產統計行（命中率/平均 spread）

### 排程
- launchd `com.lulala.sf-pairs` **每週五 20:10**（margin 18:10 + ledger 19:50 之後，數據齊）
- inbox topic=`sf-pairs` + report_path `analysis/sf_pairs_<date>.md`
- 週頻 → 不入 routine_watchdog（同 signal-ledger 慣例）

## 檔案
- `scripts/sf_pairs_weekly.py` + `tests/test_sf_pairs.py`（新，TDD）
- `scripts/launchd/com.lulala.sf-pairs.plist`

## 驗證
```bash
pytest tests/test_sf_pairs.py -q        # 純函式全綠
python scripts/sf_pairs_weekly.py       # 首份週報: universe/配對/價位完整
launchctl kickstart gui/501/com.lulala.sf-pairs   # exit 0 + inbox 收到
```

## 風險
- 股期流動性長尾：遠月/小標的成交稀 → 報告標註「近月成交量」由用戶自行檢視（DB 無股期日成交量表，v2 再接）
- 停損停利以日 close 檢查（無盤中監控）→ 已在報告 footer 明示；用戶實際進場後應同步 position_triggers
