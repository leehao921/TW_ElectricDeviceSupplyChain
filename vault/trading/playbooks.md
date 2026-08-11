---
type: trading
status: active
last_updated: 2026-07-08
related: [positions.md, ../concepts/TXF.md, ../concepts/DXY.md]
tags: [playbook, rules]
---

# Trading Playbooks (Trigger-Based Rules)

Reusable conditional rules. Each playbook = **explicit trigger + action** + rationale. Per user preferences: **trigger-based exit only, no premature profit-taking**.

## TWD Defense Line Breach
**Trigger:** USD/TWD daily close > 31.80
**Action:** 立即減 TXF 倉位 50%
**Rationale:** CBC defends band 30.5-33.0; breach signals capitulation, external 資金加速撤離. See `../concepts/TXF.md` USD/TWD warning levels.
**Last triggered:** Not in 2026 history yet (band held all year)

## DXY Macro Sensitivity (regime active)

**β 口徑** (與 [[covariance_panel]] / `concepts/TXF.md` / `concepts/DXY.md` 同步, single source of truth = `data/twii_dxy_beta.parquet`):
- 3y 平均 β = **−0.37** (regime baseline, 平常水準)
- **60d β = −1.47** (2026-05-16 最新, 4× 偏離 baseline) ← 本 playbook 使用此值

**Triggers + responses (using 60d β = −1.47):**

| DXY 變動 (24h) | 預期 TXF | Action |
|---|---:|---|
| > 100.5 (+1.5%) | −2.2% | 減 50%, 停損 41,200 |
| 99.5 | −0.7% | 觀望 |
| 平 (~99) | 震盪 | 持有 |
| 98.5 | +0.7% | 加碼 |
| < 98 (−1%) | +1.5% | 突破前高加碼 |

**Playbook 啟用條件 (activation threshold, 非 β 量測值):** 60d β 保持在 **< −0.6** 即視為 regime 仍在 (距 baseline −0.37 有顯著偏離)。Re-check weekly via `data/twii_dxy_beta.parquet`。當 60d β 回到 **−0.5 或更淺** (接近 3y baseline −0.37) 時, 切換至 alpha-driven 分析 ([[KOSPI]] / [[Nikkei]] lead)。

## Basis Extreme Short
**Trigger:** TXF futures-cash basis < −500 points (vs 平常 −50 to −150)
**Action:** Short TXF mini (MXF) when 5MA bounces fail
**Rationale:** Deep basis = forward sellers dominate; 5/15 closed at −591 (year's largest discount). 5/21 為 5 月期貨結算日 → squeeze 風險上行。
**Status (2026-05-15):** Basis = −591, conditions met, but 5/19 開盤先看 DXY 確認方向

## 00763U Copper Ladder (current)
**Take-profit (already documented in `positions.md`):**
- 36.50 sell 15; 37.50 sell 25; 39.00 sell 25; 41.00 sell 25; hold 10 runner
**Stop-loss:**
- 34 / 33 / 31 (sequential 30張 / 30張 / all)
**Re-evaluate triggers:**
- DXY > 100 sustained 3 days → 通膨壓力可能反轉 → 緊縮 ladder (move 37.50 → 36.00)
- LME copper drop > 3% single day → emergency review
- China PMI < 49 → demand weakness signal

## TXF Pair Trade (散熱 cannibalization, conditional)
**Trigger:** 5/19 開盤 USD/TWD > 31.80 AND 3481 法人轉賣
**Action:** Long 鴻海 2317 / Short 高力 8996 + 奇鋐 3017 + 健策 3653 配對
**Rationale:** AI 主題集中度高的散熱中段股,在 macro risk-off 環境下會被獲利了結, 純 AI ODM (2317) 相對抗跌. Source: 2026-05 PCA pure_ai_vs_iphone_dilution basket.
**Sizing:** Long 1 unit 2317, Short 0.3 + 0.3 + 0.4 unit (notional equal)

## NVIDIA Q1 法說會 (5/21) — known catalyst
**Pre-event:** 法說前 3 日減 50% AI 概念曝險 (2330/2449/3231)
**Post-event scenarios:**
- Beat & raise → 5/22 開盤加碼 2330 / 2449 / 6669
- In-line → 持平觀察一週
- Miss → AI 概念全面減碼,長空 6669

## Intraday 期貨 OFI 高檔背離 → 下殺 (candidate, 未回測)
**Trigger:** 現貨開盤 (09:00) 後首個 5-min 窗口, TXF 成交價創當日新高 (或觸開盤區間上緣) **但** Trade-OFI (主買口−主賣口, 口徑 = `ticks` 表 `tick_type` buy/sell) 為負, 不平衡 ≤ **−5%** → 追高是被動掛單、主動單在倒貨。
**Confirmation:** 下一檢查點 (09:15/09:25) OFI 負值持續擴大 → 賣壓加速, 背離兌現機率升。
**Action:** 短空 TXF / 減多單; 停損設當日高點上方。
**口徑說明:** 期貨逐筆無 bid/ask, 無法算 Cont(2014) quote-OFI; 改用主動成交方向 delta (= Σbuy vol − Σsell vol)。正 = 主動買掌控。
**首次觀察 (2026-07-08):**
- W1 08:45 期開盤 (45–50): OFI −39 (−1.0%), 近平衡
- W2 **09:00 現開盤** (00–05): 價 45800–45960 高檔, OFI **−183 (−6.6%)** ← 背離點
- W3 **09:25** (25–30): OFI **−569 (−29.3%)**, 價 45785→45500 (−285 點) ← 兌現
- 開 45606 → 09:00 衝 45960 高 → 09:29 收 45500; **OFI 在 09:00 領先價格轉弱 ~25 min。**
- 同步權值股結構 (僅 08:45 有 OFI, 09:00 後 collector 斷): 開盤 [[台積電]]+0.47 撐盤, 但 AI 伺服器 [[廣達]]−0.23/[[緯創]]−0.18/[[台達電]]−0.12 已被主動賣 → 窄多方。
**回測 spec:** `ticks` 表 (source=shioaji, TXF 逐筆含 tick_type) 逐日算 09:00–09:05 OFI vs 是否價格新高 → 標記背離日 → 檢驗 09:05→11:00 及收盤報酬分布, 校準 imbalance 門檻。
**Caveats:** 單日 n=1, **尚未回測**; −5% 門檻為 today-anchored, 待回測校準; 開盤窗口波動高、OFI 雜訊大; golden rule 0 未觸發 (未用 σ/罕見/極端等分布形容詞, 數字為原始彙總)。

## When to break a playbook
Only when:
1. β / σ verification shows the underlying assumption no longer holds (e.g., 60d β 從 −1.47 重新接近 3y baseline −0.37; 或量測 β 跌出 < −0.6 啟用門檻)
2. Major event invalidates the regime (e.g., Fed surprise cut, Iran resolution)
3. User explicitly overrides

Otherwise: **trust the trigger, even when emotion says otherwise**.

## semi-cycle-bottom-entry — 半導體週期低點建倉 (set 2026-08-11)

**策略主張 (用戶):** 用半導體週期特性獲利,低點建倉、高點收割。工具全部已存在,缺的只是紀律化的觸發條件。

### 週期位置判讀 (2026-08-11 讀數)
| 指標 | 資料源 | 當前讀數 | 週期低點該長什麼樣 |
|---|---|---|---|
| DDR4 現貨 | ddr-price collector | 32.4→42.5 (3個月 +31%, 單邊漲) | 連跌數月後跌幅收斂 (二階導轉正) |
| DDR5 現貨 | 同上 | 8/11 單日 +25.8% | 同上 |
| P/B light | h:agent:pb_lights | 2408=9.1 / 2344=7.5 / 3006=7.6 全 RED (>2× p85) | GREEN (P/B 落回歷史 p30 以下) |
| memory cycle stage | memory_cycle_state.json | stage 3 (since 7/9) | stage 0-1 |
| 法人 20D | institutional_stock | (每日查) | 長期淨賣後首次連續回補 |

**結論: 現在是上行週期中後段 = 收割/持有段,不是建倉段。**

### 低點建倉 checklist (全部滿足 ≥5/7 才啟動)
1. P/B lights: memory 名單 (2408/2344/3006/8271) 由 RED 回到 GREEN
2. DDR 現貨連跌 ≥3 個月且單月跌幅開始收斂
3. 原廠 (Samsung/SK hynix/Micron/南亞科) 宣布減產或砍 capex — news collector 抓
4. 南亞科 GM 連兩季惡化後首次環比持平/回升
5. 目標公司庫存週轉天數見頂回落 (季報)
6. 外資 20D 由長期淨賣轉連續 2 週累積
7. 賣方共識轉「供過於求/下修」(情緒指標,反向)

### 執行紀律
- **分批 ladder 建倉**: 4 批 25%,觸發後隨 P/B 分位 p40/p30/p20/p10 加碼 — 低點無法精準抓,用分批解決
- **工具限現股/ETF** — 週期轉折以「季」計,權證 theta 以「日」計,結構性不相容。權證只允許「有明確 catalyst + 明確時限」的戰術單
- **高點收割紀律** (本段的對稱): P/B RED + 現貨價加速上漲 (如 8/11 DDR5 +25.8%) = 分批減碼建現金,現金就是下一個低點的子彈
- **對偶思考**: 建倉 memory 時對偶 short/避開 = 上一輪吃到漲價但無結構故事的二線 (參考 avoid_list 模式)
