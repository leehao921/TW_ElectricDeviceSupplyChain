# GEX zero-gamma: 結算日前緣 + 教科書 sweep + 範圍內無翻轉 (2026-09-30)

## Context

9/30 09:57 實測 (spot 48,597) `h:agent:gex_regime` 的 ZG 47,100 不是價位意義上的 zero-gamma:

| 輸入 | 逐履約價累加穿越 (現行) | 價位 sweep (教科書) |
|---|---|---|
| 現行三腿 10/02、10/07、10/21 | 47,100 | ±2,500 內無穿越 (處處正 gamma) |
| + 當日結算 9/30 腿 | 46,400 | 47,497 / 47,672 / 47,697 |

- `compute_composite` 只取 `expiry > today`, 丟掉 13:30 才結算、OI 37,938 (三腿合計 2 倍多) 的當日腿。
- 現行 ZG = 累計 GEX 跨零的「履約價」, 不是「現價移到哪裡 dealer gamma 翻號」。
- 無穿越時回 None → regime None → 發佈 `UNKNOWN` → options_regime gate 視為 gamma_unknown 對機器多單 fail-closed。

## 變更 (scripts/gex_regime_monitor.py)

1. `select_legs(expiries, now)`: 當日到期腿在 13:30 (TPE) 前納入, 另加之後 3 個到期。
2. 純函式 `bs_gamma`、`sweep_zero_gamma(opts, spot, span=2500, step=25)`: 每個假想現價以各合約 IV/T 重算 gamma × OI × S² × 0.01 × 50 × (C+1/P−1) 加總, 取離現價最近的穿越; 無穿越回 `(None, sign)`。
3. 發佈欄位: `zg` = sweep 值 (無穿越 = ""), `zg_strike` = 舊逐履約價值, `zg_status` = `flip` | `none_in_range`。
4. `classify_regime(..., zg_status=None)`: `none_in_range` 時依 gamma 符號回 MAGNET / EXPANSION, 不再落入 UNKNOWN。其他情況語意不變。
5. `detect_events` REGIME_FLIP 文案 None-safe (zg 可為 None)。
6. `ascii_dashboard.py` 複合行傳入 `zg_status`, 並顯示兩個 ZG。

總 GEX (`total_gex`)、vol_scalar 歷史口徑不變 (仍用 iv_strikes 回報的 gamma, 但因多納入當日腿, 結算日上午量級會變大 — 已知口徑變化)。

## 不在範圍

- options_regime gate (nautilus-shioaji) 的 KNOWN 集合未含 EXPANSION → EXPANSION 仍 fail-closed 多單 (保守, 既有行為); 另案。
- txf_level_map 的 flip (08:40 位置圖) 為獨立計算, 另案。
- 賣方 dealer 符號假設 (C 正 / P 負) 未驗證。

## 驗證

- TDD: tests/test_gex_regime.py 新增 select_legs / sweep / classify no-flip / REGIME_FLIP None-safe。
- `--dry-run` 實跑對照 9/30 手算 (當日腿納入時 sweep ≈ 47,500–47,700)。
- 部署: launchd 300s 下一輪自動載入; 確認 `h:agent:gex_regime` 新欄位 + 下游 `read_options_regime` 不為 gamma_unknown。
