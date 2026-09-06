# txf-levels 結構化發布 (`h:agent:txf_levels:latest`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** `txf_level_map.py` 在 inbox 推播外新增第二 sink — Redis hash `h:agent:txf_levels:latest`，供 nautilus-shioaji 機器消費（牆→shelf clamp、gamma regime→prose frame）。整合分析裁決見 session 記錄；本計畫實作 producer 端含分析補的四個 schema 強化。

**慣例先例:** `h:agent:pb_lights`（pb-lights routine → memory-cycle 消費）。發布 fail-soft：hash 失敗不影響 inbox。

---

## Schema（hash 欄位，JSON 欄位存字串）

| 欄位 | 內容 | 備註 |
|---|---|---|
| as_of | ISO date | consumer 當日才收 |
| expires_at | 當日 13:45 TPE ISO | **非 24h** — 08:40 快照日內衰減（分析 ③） |
| spot / day_close / night_close | float 或 "" | |
| flip / gex_total | float 或 ""（UNKNOWN 時空） | |
| gamma_regime | ABOVE / BELOW / NEUTRAL / UNKNOWN | **deadband：\|spot−flip\| < 0.3%×spot → NEUTRAL**（分析 ②）；flip 缺 → UNKNOWN |
| front_expiry | ISO date | 週選到期日（分析 ①） |
| is_settle_day | "1"/"0" | front_expiry == as_of（分析 ① — consumer 結算日降權牆） |
| cw_w / cw_w_oi / pw_w / pw_w_oi | 週選 CW/PW 價位與口數 | 來自 wall_rows 同源 oi_dict |
| walls_month_json | [{strike, cp, oi}] | 月選 top walls |
| vacuum_json | [{level, age_days}] | LVN 帶；**age_days = 該 bucket 在 20 日窗內首次有量距今交易日數**（分析 ④ — 新領地薄 vs 拒絕區薄） |
| hvn_json | [{level, share}] | 20 日 top5 |
| value_area_json | {note} 或 {} | value_area_note 輸出 |
| foreign_net / trust_net | int | 期淨 OI（T-1） |
| overnight_json | {sox_chg, vix, ust10y, brent, dxy} | |
| asia_json | {N225: chg, ...} | |
| usdtwd | float | |

## Tasks

### Task 1: 核心（TDD）

**Files:** Modify `scripts/txf_level_map.py`；Test append `tests/test_txf_level_map.py`

- [ ] 純函數（先測後寫）：
  - `gamma_regime(spot, flip, deadband_pct=0.003) -> str` — 四態含 deadband、flip None → UNKNOWN、spot None → UNKNOWN
  - `bucket_age_days(bars, levels, bucket_pts=100) -> dict[int,int]` — 每 level 首次有量的 TPE 日距最後交易日的**交易日數**（用 bars 內 distinct 日排序算 rank 差，非日曆日）
  - `build_struct_payload(...) -> dict[str,str]` — 組 hash 欄位；一切輸入可 None，缺項對應 ""/UNKNOWN/"[]"；`is_settle_day` 由 front_expiry==as_of
- [ ] `_publish_struct(payload)`：redis-cli `HSET h:agent:txf_levels:latest` 多欄位（照 inbox push 的 subprocess fail-soft 慣例）＋`EXPIRE` 對齊 expires_at；失敗僅 warn
- [ ] main() 於 inbox push 後呼叫（dry-run 改為印 payload 不發）
- [ ] 測試：deadband 三態＋UNKNOWN、age_days 交易日算法（跨週末）、payload 全 None 不 crash、settle-day 旗標、JSON 欄位可 loads
- [ ] Commit

### Task 2: 驗證（controller）

- [ ] `--dry-run` 印 payload；實跑一次驗 `redis-cli HGETALL h:agent:txf_levels:latest` 欄位齊
- [ ] 週一 08:40 live 驗證清單（W37 觀察項）：hash 落地、flip 為數值非 UNKNOWN、consumer 端由 nautilus session 接手驗
- [ ] memory/vault 更新、commit

---

## 定案後記 (2026-09-06 23:00)

實作期間發現 nautilus session 已於 20:25 (f2678b8) 自行實作一版 builder，與本計畫版並存造成同 key 雙 schema。已收斂 (9260486)：
- **以 f2678b8 慣例為底**（consumer 相容）：缺省省略欄位、hvn/walls tuple 陣列、ABOVE_FLIP/BELOW_FLIP token、lvn_above/lvn_below、TTL 86400
- **疊加本計畫強化**：NEUTRAL deadband (0.3%)、vacuum_json 帶 age_days、is_settle_day、front_expiry、expires_at (13:45 advisory)、night_close
- 必在欄位：as_of / gamma_regime / is_settle_day / expires_at；其餘缺省即省略
- 已透過 claude:inbox topic=coordination 廣播 schema 契約給 nautilus session
- **教訓：跨 session 同 repo 並行開發，動共用 key 前先查 git log 近時段他人 commit**
