---
type: concept
status: living
last_updated: 2026-06-04
tags: [IP, EDA, ASIC, 矽智財, SEC, XBRL, patents]
data_sources:
  - data/ip_database/arm_rpo.parquet
  - data/ip_database/arm_revenue.parquet
  - data/ip_database/rmbs_rpo.parquet
  - data/ip_database/rmbs_revenue.parquet
  - data/ip_database/ceva_rpo.parquet
  - data/ip_database/ceva_revenue.parquet
  - data/ip_database/tw_ip_basket_quarterly.parquet
  - data/ip_database/tw_ip_basket_flow.parquet
  - data/eda_ip/snps_rpo.parquet
  - data/eda_ip/cdns_rpo.parquet
testable_claims:
  - ticker: "3443"
    window: ["2026-03-06", "2026-06-04"]
    thesis: "創意 GUC — TSMC OIP 嫡系 ASIC service, 對應 CDNS IP +22% YoY 受惠"
    assertions:
      total_net_gt: 1500
  - ticker: "3661"
    window: ["2026-03-06", "2026-06-04"]
    thesis: "世芯-KY Alchip — Amazon Trainium ASIC service, 外資主導雙引擎"
    assertions:
      foreign_net_gt: 5000
      total_net_gt: 4000
  - ticker: "6533"
    window: ["2026-03-06", "2026-06-04"]
    thesis: "晶心科 — RISC-V CPU IP, 對應 ARM RPO -7.8% 收縮的 TW 鏡像, 法人撤"
    assertions:
      total_net_lt: 0
---

# IP_Ecosystem_Database — 半導體 IP / EDA / ASIC service 動能監測

> 接續 [[Vera_Rubin_BOM]] (硬體 BOM) + [[MLCC_008004]] (被動元件) + [[Institutional_Alpha_2026-06]] (法人流向), 補上**設計層**的訂單動能監測 — IP 授權 + EDA RPO + ASIC service backlog + TW 法人交叉驗證。

## TL;DR

1. **CDNS IP segment +22% YoY** (Q1 2026 RPO $8.0B record) — 是真有機動能;法說明確點名 [[HBM]] / LPDDR / [[PCIe]] / [[SerDes]] / foundation IP
2. **SNPS Design IP -5.8% YoY** (Q2 FY26) — 表面整體 RPO +35.8% YoY 是 Ansys 併購灌出, 內生 IP 在 retreat (Q1 → Q2 = -3.5%);中國 BIS export control 點名拖累
3. **ARM Holdings RPO -7.8%** (2025/9: $2.25B → 2026/3: $2.07B) — **新發現, 跨季縮減**;P/E 100+ 估值與簽約動能不一致, 警戒
4. **Rambus** 體質健康 RPO +27% YoY, royalty XBRL segment 在 ASC606 之後失效 (僅到 2018/6)
5. **CEVA** small-cap RPO 揭露不一致, revenue 完整 (FY25 $109.6M +2.5% YoY)
6. **TW 受惠 cascade**: **[[3443_創意]] +3,147 張、[[3661_世芯-KY]] +6,794 張 (外資主導)** 雙引擎 — 對應 CDNS IP 動能
7. **[[6533_晶心科]] -1,302 張**唯一淨賣 — 對應 ARM RPO 收縮的 TW 鏡像
8. **PatentsView 已退役** (2025/2), USPTO ODP 要 ID.me 帳號才能 API key, Google Patents IP throttle → 專利動能監測目前 **gap**

---

## 1. 資料庫架構

### 1.1 落地

`data/ip_database/` (canonical schema 統一)
`data/eda_ip/` (legacy SNPS/CDNS, schema 不統一, 待 migrate)

### 1.2 Canonical Schema

| Column | Type | Notes |
|---|---|---|
| end | datetime64 | period-end |
| entity_id | str | SEC CIK 10-digit or TW ticker |
| entity_name | str | display name |
| tag | str | XBRL concept or 'price'/'revenue'/'foreign_net_lots' etc |
| val | float64 | numeric value |
| val_unit | str | "USD" / "TWD" / "lots" / "pct" / "x" |
| fp | str | "Q1"/"Q2"/"Q3"/"FY"/"static" |
| form | str | "10-Q"/"10-K"/"20-F"/"6-K"/"yfinance"/"institutional_stock" |
| accn | str | SEC accession or source identifier |
| source_url | str | re-fetch 可循 URL |
| source_date | datetime64 | when fetched |

### 1.3 Schema 強制

`tests/test_ip_database_schema.py` — pytest gate, pre-commit hook 自動跑。負值僅允許 `NEG_OK = {net_income, operating_income, gross_profit, gross_margin, operating_margin, foreign_net_lots, trust_net_lots, total_net_lots}`。

---

## 2. 資料來源驗證表 (✓ 有效 / ✗ 失效 / ⚠️ 部分)

| 來源 | Status | 詳情 |
|---|---|---|
| SEC EDGAR XBRL companyfacts (us-gaap RPO) | ✓ | 對 [[SNPS]] / [[CDNS]] / [[ARM]] / [[Rambus]] 全綠;[[CEVA]] 小型 RPO 揭露 1 row 薄 |
| SEC EDGAR XBRL — segment revenue | ⚠️ | Segment 拆解 (Design IP vs Design Automation) **不在 GAAP tag, 僅 10-Q HTML** |
| SEC EDGAR — form filter | ⚠️ | **ARM 用 20-F + 6-K 不是 10-K/10-Q** — 舊 SNPS/CDNS script hardcode {10-Q, 10-K} 對未來 foreign filer silently 漏報 (本批已 backport) |
| yfinance TW (`{ticker}.TW`) | ✓ | 4/5 通;[[3529_力旺]] 需用 `.TWO` (OTC 上櫃) |
| trading-timescaledb `institutional_stock` | ✓ | 5 tickers × 90d daily 法人 net flow 全綠 |
| PatentsView REST API | ✗ | **2025/2 退役**, redirect 到 USPTO ODP |
| USPTO ODP API | ✗ | 需 USPTO.gov 帳號 + ID.me 連結後申請 API key, 無 instant signup |
| `search.patentsview.org/api/v1/` | ✗ | DNS dead |
| Google Patents `patents.google.com/xhr/query` | ⚠️ | Brief 可用 (擷取到 SNPS 2021 = 104 grants, ARM 2021 = 370, etc), 6 retries 後 HTTP 503 throttled |
| Google Patents BigQuery free tier | ✗ | 需 GCP credentials |
| 公司 IR 頁 (investor.synopsys.com 等) | ✗ | JS-rendered, WebFetch 抓不到 |
| SEC 8-K Ex-99 earnings press release | ✓ | 純 HTML, 取代 IR JS scrape |
| 法說會 transcript | ✗ | 需 Motley Fool / SeekingAlpha 訂閱 |

---

## 3. 跨家 RPO 對拍 (USD millions)

| Quarter end | [[SNPS]] | [[CDNS]] | [[ARM]] | [[Rambus]] | [[CEVA]] |
|---|---:|---:|---:|---:|---:|
| 2025-09 | — | 7,000 | 2,246 | 24 | — |
| 2025-10 | 11,400 | — | — | — | — |
| 2025-12 | — | 7,800 | 2,148 | 35 | — |
| 2026-01 | 11,300 | — | — | — | — |
| 2026-03 | — | 8,000 | 2,071 | 31 | — |
| 2026-04 | 11,000 | — | — | — | — |

### 解讀

- **[[CDNS]] 真有機 +14% over 6 個月** — 7000 → 7800 → 8000 monotonic, 沒併購灌水
- **[[SNPS]] -3.5% QoQ** (11400 → 11300 → 11000) — Ansys 併購塞滿後反退;**Design IP segment YoY -5.8%** (中國 BIS Entity-List 拖累)
- **[[ARM]] -7.8% over 6 個月** — 新發現:**Q1 IPO 高 P/E (100+) 估值對應的 RPO 持續萎縮**, 簽約動能不支持估值
- **[[Rambus]] +27% YoY** (FY25 $707.6M) — 體質健康, 但 royalty XBRL segment 在 ASC606 (2018+) 後改 custom tag, 公開抓不到
- **[[CEVA]] revenue +2.5% YoY** (FY25 $109.6M) — DSP IP 小型穩定, 無 momentum

---

## 4. TW IP/ASIC service 法人流向 (90d 累計, lots)

| Ticker | Co | 外資 | 投信 | 總和 | 解讀 |
|---|---|---:|---:|---:|---|
| **[[3443_創意]]** | GUC | +1,140 | +2,148 | **+3,147** | ✓ 雙引擎 — TSMC OIP 嫡系 ASIC service |
| **[[3661_世芯-KY]]** | Alchip | **+7,329** | -626 | **+6,794** | ✓ 外資主導 — Amazon Trainium ASIC service |
| [[3529_力旺]] | eMemory | +4,598 | -1,452 | +3,275 | ◐ 外資強, 投信賣;NVM IP 全球 niche |
| [[6531_愛普]] | AP Memory | -4,233 | +11,630 | +7,458 | ⚠ **末段接刀** (投信硬接外資撤) |
| **[[6533_晶心科]]** | Andes | -1,339 | +33 | **-1,302** | ✗ 唯一淨賣 — RISC-V CPU IP, 對應 ARM RPO 收縮 |

### Cascade 連動驗證

```
CDNS IP segment +22% YoY (record backlog)
   ↓ (lag 2-4 quarters)
3443 創意 + 3661 世芯-KY ASIC NRE 動能 ↑
   ↓ (lag 4-8 quarters, 量產 turnkey)
3443 / 3661 turnkey 營收 ↑
```

```
ARM Holdings RPO -7.8% (簽約動能弱)
   ↓ (lag varies)
6533 晶心科 (RISC-V vs ARM CPU IP 直接對打) 動能?
   ↑ (反向)
6533 法人 -1,302 張 (亦弱)
```

**矛盾點**: ARM 弱化照理對 [[6533_晶心科]] (RISC-V 取代 ARM 敘事) 應該有利, 但實際法人也撤。可能解讀:
- 整個 CPU IP 領域 (含 ARM + RISC-V) 都在減速, 是 design start 減少而非取代故事
- 或 RISC-V 還不夠成熟接 [[NVIDIA]] / [[AMD]] / hyperscaler 量級訂單
- 待 [[6533_晶心科]] Q3 法說檢視 royalty + NRE 拆解

---

## 5. 最近季基本面 ranking (TWD 億元)

| Ticker | Co | FY25 Q4 營收 (億 TWD) | 排序 |
|---|---|---:|:-:|
| [[3443_創意]] | GUC | 124.0 | #1 |
| [[3661_世芯-KY]] | Alchip | 47.3 | #2 |
| [[6531_愛普]] | AP Memory | 18.7 | #3 |
| [[3529_力旺]] | eMemory | 10.5 | #4 |
| [[6533_晶心科]] | Andes | 4.6 | #5 |

[[3443_創意]] + [[3661_世芯-KY]] 規模合計 171 億 TWD (vs 其他 3 家合計 34 億) — TW IP 板塊**集中度極高**, ASIC service 兩家吃掉 80%+。

---

## 6. 跨概念 cross-link

- [[Vera_Rubin_BOM]] — 硬體 BOM (HBM4 / [[CoWoS]] / 008004 MLCC);**ASIC die 本身**就是 [[3443_創意]] / [[3661_世芯-KY]] 用 CDNS+SNPS IP 設計的產物
- [[MLCC_008004]] — 被動元件;與 ASIC IP 是「同 die 上不同層」, 對齊 ASIC turnkey 量產時程
- [[MLCC_008004_TW_verification]] — 提到 [[2327_國巨]] 拿 [[Kemet]] 補主動 — 同邏輯下這條 ecosystem 也應觀察 EDA 廠是否擴向「power+IP bundle」
- [[Institutional_Alpha_2026-06]] — 法人 5/12-5/29 跨產業潛力股, 已 cross-link [[3443_創意]] / [[3661_世芯-KY]] 的 testable_claims (見上面 frontmatter)
- [[FOPLP]] — 玻璃載板替代 [[ABF]];ASIC service 兩家也是 FOPLP 受惠 (高階封裝設計服務)

---

## 7. 警戒清單 (依本資料庫信號)

| Ticker | 訊號 | 強度 |
|---|---|---|
| **ARM Holdings** (US) | RPO -7.8% over 6 個月 vs P/E 100+ | ⚠⚠⚠ |
| **[[SNPS]]** | Design IP segment YoY -5.8%, 中國 export control 拖累 | ⚠⚠ |
| **[[6533_晶心科]]** | 法人 -1,302 張, ARM 弱化未轉成 RISC-V 受惠 | ⚠⚠ |
| **[[6531_愛普]]** | 外資 -4,233 投信 +11,630 末段接刀模式 | ⚠ |

---

## 8. 推薦 (本資料庫支持)

| Ticker | 訊號 | 強度 |
|---|---|---|
| **[[3661_世芯-KY]]** | 外資主導 +6,794 張, Amazon Trainium ASIC, CDNS IP receiver | ★★★★★ |
| **[[3443_創意]]** | 雙引擎 +3,147 張, TSMC OIP, 規模最大 | ★★★★ |
| **[[CDNS]]** (Cadence) | IP segment +22% YoY, RPO record, "Agentic AI" 新敘事 | ★★★★★ |
| **[[Rambus]]** (RMBS) | FY25 +27% YoY healthy, memory + interface IP | ★★★ |
| [[3529_力旺]] | 外資進但投信賣, mixed | ★★ |

---

## 9. 待修補的資料 gap (Phase 2)

1. **PatentsView 替代**: 設 USPTO ODP API key (需用戶手動 ID.me) 或 GCP BigQuery free tier
2. **Segment XBRL → 10-Q HTML 解析**: 用 lxml 抓 "Design IP" vs "Design Automation" 拆 dollar amount
3. **法說 transcript NLP**: HBM / hyperscaler / CXL 字頻 — 需 paid source
4. **SNPS / CDNS migrate**: 把 `data/eda_ip/{snps,cdns}_*.parquet` 改 schema 後搬進 `data/ip_database/`
5. **跨季 cron**: SEC 8-K 每季 + 1 個月後 → 自動 refresh

---

## 10. 來源檔案索引

`data/ip_database/`:
- `arm_rpo.parquet` (11 rows, 2023-09 to 2026-03)
- `arm_revenue.parquet` (16 rows, 2022-03 to 2026-03)
- `rmbs_rpo.parquet` (33 rows, 2018-03 to 2026-03)
- `rmbs_revenue.parquet` (198 rows, 2008-12 to 2026-03)
- `ceva_rpo.parquet` (1 row, 2018-12)
- `ceva_revenue.parquet` (141 rows, 2009-12 to 2025-12)
- `tw_ip_basket_quarterly.parquet` (198 rows, 12 tags × 5 tickers × 4 quarters)
- `tw_ip_basket_flow.parquet` (15 rows, 3 flow tags × 5 tickers, 90d window)

`data/ip_database/_provenance/`:
- `arm.md` / `rmbs.md` / `ceva.md` / `tw_ip_basket.md` / `patentsview.md`

`scripts/`:
- `fetch_arm_rpo.py` / `fetch_rmbs_rpo.py` / `fetch_ceva_rpo.py` / `fetch_tw_ip_basket.py` / `fetch_patentsview_ip.py` (✗ documented)
- `fetch_snps_rpo.py` / `fetch_cdns_rpo.py` (legacy, schema 不統一)

`tests/`:
- `test_ip_database_schema.py` — 9 tests, NEG_OK tag-aware
