# 產業全景 treemap (2026-09-30)

## 目標

加權 / 櫃買各一張產業 treemap:
- 面積可切換: **成交值** 或 **指數貢獻** (|貢獻點數|);色 = 產業**市值加權漲跌幅** (發散色: 跌綠 / 平灰 / 漲紅, 台股慣例)。
- 點產業下鑽: **主力貢獻排行** 或 **成交值排行** (前 N 檔) + **貢獻磚牆** (每檔一磚, 磚面積 ∝ |貢獻點|, 色 = 正/負)。
- 「其他成員」: 前 N 檔以外合併成一磚, 漲跌幅**由群組加權反推** — 以官方類股指數漲跌 R_s 與前 N 檔權重/報酬
  反解: `r_other = (R_s·W_s − Σ_top w_i·r_i) / (W_s − Σ_top w_i)`; 官方指數缺值時退回成員直接加權。

用戶決定 (AskUserQuestion 9/30): 日級先做、盤中第二期;呈現為 HTML artifact 頁面。

## 資料源 (9/30 21:00 實測, 子代理驗證)

| 資料 | 加權 (TWSE) | 櫃買 (TPEx) | 回補 |
|---|---|---|---|
| 全市場收盤/漲跌/成交值 | `rwd/zh/afterTrading/MI_INDEX?type=ALLBUT0999` (1,382 檔) | `www/zh-tw/afterTrading/otc?type=EW` (1,015 檔, 含發行股數) | 可 (date 參數) |
| 產業別 + 發行股數 | openapi `/v1/opendata/t187ap03_L` | openapi `/openapi/v1/mopsfin_t187ap03_O` | 僅最新 → 每日快照 |
| 類股指數收盤/漲跌 | MI_INDEX 表 0 (56 列) | `www/zh-tw/indexInfo/sectinx` (23 列, 只有點數) | 可 |
| 盤中 (二期) | MIS `getStockInfo.jsp` ≤150 檔/次; `tse_t{產業別}.tw` 類股指數 (t24 已驗) | `otc_o00.tw` | — |

地雷: 休市日回 stat OK + 空表 (以列數 gate); 民國日期; 千分位字串; TWSE 漲跌號在 HTML 標籤; "--" 未成交;
產業代碼→名稱無官方欄位需內建表; `tse_IX0024` 是鋼鐵不是半導體。
加權指數 = Σ(價 × **發行股數**) (IndexS02, 非自由流通) → 貢獻點 = `mcap_i,prev / Σmcap_prev × r_i × 前日指數`;
排除 ETF (00 開頭)、特別股、全額交割股。以 Σ貢獻 vs 官方指數漲跌點數的殘差驗算。

## 變更

### database repo (資料層 — 不在本 repo 另建 collector)
- 新 migration: `stock_quote_daily` (date, market, code, name, close, change, prev_close, volume, trade_value),
  `stock_profile_daily` (as_of, market, code, industry_code, shares_issued), `sector_index_daily`
  (date, market, industry_code, name, close, change_pts, change_pct)。
- 新 `scripts/collectors/sector_daily.py`: 沿用 `scripts/twse/market_intel.py`、`institutional_collector` 既有 MI_INDEX /
  TPEx 解析; 休市/空表不寫; TAIFEX 式間隔 (每站 ≥5 秒)。排程掛既有 collector 容器, 每交易日 15:20 (TPEx 收盤資料 ~15:00 後)。
- 回補 2026-09-01 起 (報價、類股指數); 股數用當前快照 (股本變動小, 標註近似)。

### My-TW-Coverage (分析 + 頁面)
- `scripts/sector_treemap.py`: 讀上述三表 → 每市場產業彙總 JSON:
  `{market, date, index: {prev, close, chg_pts}, residual_pts, sectors: [{code, name, trade_value, contrib_pts,
  wret, official_ret, members: [...top N], other: {n, trade_value, contrib_pts, ret, ret_method}}]}`。
- `artifacts/sector_treemap/index.html`: ECharts treemap (cdnjs), 切換鈕 (加權/櫃買、面積=成交值/貢獻、
  下鑽排行=貢獻/成交值), 右側下鑽面板 (排行表 + 貢獻磚牆), 表格檢視與 hover tooltip; dataviz 規則 (發散色驗證、無雙軸)。
- 發佈: 頁面 + `data.json` 以 Artifact files 發佈; 每日更新由 15:50 daily-synthesis headless routine 之後的一步
  重新發佈 data.json (routine 無法發佈時退回本機 `analysis/sector_treemap_<date>.html` + inbox)。

## TDD
- 解析: MI_INDEX / TPEx / t187ap03 / sectinx 真實 payload fixture → 列數、符號、"--"、民國日期、休市空表。
- 計算: 手算 3 產業 × 4 成員 → 加權報酬、貢獻點、Σ貢獻=指數變動 (合成資料殘差 0); 反推「其他成員」
  代入後群組加權報酬還原官方 R_s; W_other→0 時不除零 (退回直接加權並標 ret_method)。
- 頁面: JSON schema 測試; 渲染後截圖檢查標籤碰撞 / 手機寬度。

## 驗證
- 9/30 實算: Σ貢獻點 vs TAIEX 官方漲跌點殘差 < 5%; 半導體類加權報酬 vs 半導體類指數漲跌 %。
- 抽查台積電貢獻點 ≈ 權重 × 漲跌 × 前日指數。

## 二期 (盤中)
- MIS 輪詢全市場 (~2,400 檔 / 150 = 16 次, 每 60 秒) + `t{code}` 類股指數, 盤中 gate 疊 tw_holidays;
  新 collector 於 database repo, 寫 Redis `h:sector:live:*`; 頁面改讀即時來源 (artifact 能力另評估)。
