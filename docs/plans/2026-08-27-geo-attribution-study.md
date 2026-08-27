# 地緣風險歸因研究 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 對 7 次回檔事件做 catalyst 標註＋指標領先/同步檢驗，依事前準則判定各指標在未來 geo-risk composite 的角色。

**Architecture:** database repo 擴充 GDELT collector 回補歷史（Phase A）；本 repo `scripts/geo_attr/` 三模組 — indicators（純 z-score 指標，TDD）、leadlag（事件窗分類＋誤報率，TDD）、loaders（thin DB/yfinance）；`scripts/geo_attr_study.py` CLI 產報告；catalyst 標註（Phase B）由 controller web research 補入終稿。復用 `scripts/lppls/` 的 index_builder（同一指數與事件集）與 walkforward.forward_return（同一 FP 語意）。

**Tech Stack:** Python 3.12（`.venv`）、pandas/numpy、psycopg2、yfinance、pytest。

**Spec:** `docs/superpowers/specs/2026-08-27-geo-attribution-study-design.md`

---

## File Structure

| 檔案 | 職責 |
|---|---|
| （database repo）`scripts/collectors/intl_events_daily.py` | 加 `--backfill START END` 模式 |
| （database repo）`config/intl_events.json` | 加 `mideast_oil` query key |
| `scripts/geo_attr/__init__.py` | 空檔 |
| `scripts/geo_attr/indicators.py` | rolling z-score（僅用過去值）＋六個指標變換 |
| `scripts/geo_attr/leadlag.py` | 事件窗分類（領先/同步/落後/沉默/資料不足）＋誤報率 |
| `scripts/geo_attr/loaders.py` | gdelt/fx/外資全序列 loaders＋Brent yfinance cache |
| `scripts/geo_attr_study.py` | CLI orchestrator，產 `analysis/geo_attribution_study_<date>.md` |
| `tests/test_geo_indicators.py` | z-score 因果性＋指標符號約定 |
| `tests/test_geo_leadlag.py` | 分類五類＋誤報率精確值 |

---

### Task 1: GDELT backfill（database repo）

**Files:**
- Modify: `/Users/lulala/Documents/coding/database/scripts/collectors/intl_events_daily.py`
- Modify: `/Users/lulala/Documents/coding/database/config/intl_events.json`

- [x] **Step 1: config 加 mideast_oil**

`config/intl_events.json` 的 `gdelt_queries` 加：
```json
"mideast_oil": "(Iran OR Hormuz) (oil OR conflict)"
```

- [x] **Step 2: collector 加 backfill 模式**

在 `intl_events_daily.py` 加（放 `collect_gdelt` 之後；沿用現有 `_get_json`/`aggregate_gdelt_daily`/`aggregate_gdelt_tone`/`store_gdelt`/`GDELT_SLEEP_S`）：

```python
def collect_gdelt_backfill(conn, config, start: str, end: str,
                           keys=None) -> int:
    """歷史回補: start/end 為 YYYY-MM-DD。~6 個月一 chunk,每 query 兩次呼叫
    (timelinevolraw + timelinetone) 帶 startdatetime/enddatetime。
    upsert 冪等,與現行 60d 窗重疊無害。單 chunk 失敗記錄續跑。"""
    import datetime as _dt
    qs = {k: v for k, v in (config.get("gdelt_queries") or {}).items()
          if keys is None or k in keys}
    s = _dt.date.fromisoformat(start)
    e = _dt.date.fromisoformat(end)
    rows, gaps = 0, []
    cur = s
    while cur < e:
        nxt = min(_dt.date(cur.year + (cur.month + 5) // 12,
                           (cur.month + 5) % 12 + 1, 1), e)
        sd = cur.strftime("%Y%m%d") + "000000"
        ed = nxt.strftime("%Y%m%d") + "000000"
        for key, query in qs.items():
            try:
                vol = _get_json(GDELT_URL, {"query": query, "mode": "timelinevolraw",
                                            "startdatetime": sd, "enddatetime": ed,
                                            "format": "json"})
                time.sleep(GDELT_SLEEP_S)
                tone = _get_json(GDELT_URL, {"query": query, "mode": "timelinetone",
                                             "startdatetime": sd, "enddatetime": ed,
                                             "format": "json"})
                vol_by_day = aggregate_gdelt_daily((vol.get("timeline") or [{}])[0].get("data"))
                tone_by_day = aggregate_gdelt_tone((tone.get("timeline") or [{}])[0].get("data"))
                rows += store_gdelt(conn, key, vol_by_day, tone_by_day)
                print(f"[backfill] {key} {cur}~{nxt}: ok")
            except Exception as e_:                  # noqa: BLE001
                print(f"[warn] backfill {key} {cur}~{nxt}: {e_}", file=sys.stderr)
                gaps.append(f"{key}:{cur}~{nxt}")
            time.sleep(GDELT_SLEEP_S)
        cur = nxt
    if gaps:
        print(f"[backfill] 缺口: {gaps}", file=sys.stderr)
    return rows
```

main/argparse 處加 `--backfill START END`＋`--keys k1,k2`（逗號分隔，預設全部）分支：走 `collect_gdelt_backfill` 後直接 return，不觸發 kalshi/manifold/heartbeat。依該檔現有 CLI 結構插入（若無 argparse 則新增最小 argparse 包住現有 main 流程，預設行為不變）。

- [x] **Step 3: 執行回補**

```bash
cd /Users/lulala/Documents/coding/database
<現有執行方式（查該 repo launchd/README 用哪個直譯器）> scripts/collectors/intl_events_daily.py \
  --backfill 2024-12-01 2026-06-01 --keys tariff,taiwan_strait,tsmc,semi_export,mideast_oil
```
預期 ~3 chunks × 5 keys × 2 calls ≈ 30 呼叫、12s 間隔 ≈ 6-7 分鐘。429 就等（`_get_json` 自帶 backoff）。

- [x] **Step 4: 驗證覆蓋**

```bash
.venv/bin/python - <<'EOF'
import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, user='tmf', password='tmf_dev_2026', dbname='tmf_market_data')
cur = conn.cursor()
cur.execute("SELECT query_key, min(date), max(date), count(*) FROM gdelt_daily GROUP BY 1 ORDER BY 1")
for r in cur.fetchall(): print(r)
EOF
```
Expected: tariff/taiwan_strait/tsmc/semi_export/mideast_oil 的 min(date) ≤ 2024-12-07、與現行段無大缺口（GDELT timeline 可能天然缺零文章日，允許）。

- [x] **Step 5: Commit（database repo）**

```bash
cd /Users/lulala/Documents/coding/database
git add scripts/collectors/intl_events_daily.py config/intl_events.json
git commit -m "feat(intl-events): GDELT --backfill 歷史回補模式 + mideast_oil query key

geo-attribution 研究需 2025-01 起 tariff/台海/中東油價文章量與 tone;
timeline API startdatetime/enddatetime 一 chunk 一呼叫,upsert 冪等與現行 60d 窗重疊無害"
```

---

### Task 2: 指標引擎 (`scripts/geo_attr/indicators.py`)

**Files:**
- Create: `scripts/geo_attr/__init__.py`（空檔）
- Create: `scripts/geo_attr/indicators.py`
- Test: `tests/test_geo_indicators.py`

- [x] **Step 1: 寫失敗測試**

```python
# tests/test_geo_indicators.py
import numpy as np
import pandas as pd

from scripts.geo_attr.indicators import (
    causal_zscore, gdelt_intensity, gdelt_tone_deterioration, brent_shock,
    twd_depreciation, foreign_sell_accel,
)


def _s(values, start="2025-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_causal_zscore_excludes_current_point():
    # 前 99 點 ~N(0,1) 固定 seed,最後一點 = 100 → z 巨大;
    # 若誤把當前點納入 baseline,std 會被自身撐大,z 明顯縮水
    rng = np.random.default_rng(0)
    s = _s(list(rng.normal(0, 1, 99)) + [100.0])
    z = causal_zscore(s, baseline=250, min_periods=60)
    assert z.iloc[-1] > 30


def test_causal_zscore_insufficient_history_nan():
    s = _s(list(np.arange(50.0)))
    z = causal_zscore(s, baseline=250, min_periods=60)
    assert z.isna().all()


def test_gdelt_intensity_spike():
    counts = _s([10.0] * 90 + [10, 10, 80, 90, 100, 120, 150, 200, 250, 300])
    z = gdelt_intensity(counts, baseline=60, min_periods=30)
    assert z.iloc[-1] > 2.0


def test_tone_deterioration_more_negative_is_higher():
    tone = _s([-1.0] * 90 + [-8.0] * 10)   # tone 驟降(更負)
    z = gdelt_tone_deterioration(tone, baseline=60, min_periods=30)
    assert z.iloc[-1] > 2.0


def test_brent_shock_absolute_both_directions():
    up = _s([70.0] * 95 + [70, 72, 76, 82, 90])      # +28%/5d
    dn = _s([70.0] * 95 + [70, 68, 64, 58, 50])      # -28%/5d
    for series in (up, dn):
        z = brent_shock(series, baseline=60, min_periods=30)
        assert z.iloc[-1] > 2.0


def test_twd_depreciation_sign():
    dep = _s([31.0] * 95 + [31.0, 31.3, 31.7, 32.2, 32.8])   # USDTWD 升=貶值
    z = twd_depreciation(dep, baseline=60, min_periods=30)
    assert z.iloc[-1] > 2.0
    app = _s([31.0] * 95 + [31.0, 30.7, 30.3, 29.8, 29.2])   # 升值 → 不觸發
    z2 = twd_depreciation(app, baseline=60, min_periods=30)
    assert z2.iloc[-1] < 0


def test_foreign_sell_accel_sign():
    sell = _s([1e8] * 95 + [-5e8, -8e8, -9e8, -1.2e9, -1.5e9])  # 轉大幅賣超
    z = foreign_sell_accel(sell, baseline=60, min_periods=30)
    assert z.iloc[-1] > 2.0
    buy = _s([1e8] * 100)
    assert abs(foreign_sell_accel(buy, baseline=60, min_periods=30).iloc[-1]) < 1.0
```

- [x] **Step 2: 跑測試確認失敗**

```bash
.venv/bin/python -m pytest tests/test_geo_indicators.py -v
```
Expected: FAIL — ModuleNotFoundError。

- [x] **Step 3: 實作**

```python
# scripts/geo_attr/indicators.py
"""地緣/宏觀指標 → causal z-score（僅用過去值,不含當前點 — 領先性檢驗的因果前提）。

符號約定: 所有指標「值越大 = 壓力越大」。
"""
import pandas as pd


def causal_zscore(s: pd.Series, baseline: int = 250,
                  min_periods: int = 60) -> pd.Series:
    """z_t = (s_t − mean(s[t−baseline, t−1])) / std(同窗)。shift(1) 排除當前點。"""
    r = s.rolling(baseline, min_periods=min_periods)
    mu = r.mean().shift(1)
    sd = r.std().shift(1)
    return (s - mu) / sd


def gdelt_intensity(count_series: pd.Series, baseline: int = 250,
                    min_periods: int = 60) -> pd.Series:
    """文章量 7 日和 z — 事件聲量爆量。"""
    return causal_zscore(count_series.rolling(7, min_periods=3).sum(),
                         baseline, min_periods)


def gdelt_tone_deterioration(tone_series: pd.Series, baseline: int = 250,
                             min_periods: int = 60) -> pd.Series:
    """(−tone) 7 日均 z — tone 越負(語調惡化)值越大。"""
    return causal_zscore((-tone_series).rolling(7, min_periods=3).mean(),
                         baseline, min_periods)


def brent_shock(close: pd.Series, baseline: int = 250,
                min_periods: int = 60) -> pd.Series:
    """|5 日報酬| z — 斷供上漲與需求崩跌皆為衝擊。"""
    return causal_zscore(close.pct_change(5).abs(), baseline, min_periods)


def twd_depreciation(usdtwd_close: pd.Series, baseline: int = 250,
                     min_periods: int = 60) -> pd.Series:
    """USDTWD 5 日升幅 z — 台幣貶值(資金撤離)為正。"""
    return causal_zscore(usdtwd_close.pct_change(5), baseline, min_periods)


def dxy_strength(dxy_close: pd.Series, baseline: int = 250,
                 min_periods: int = 60) -> pd.Series:
    """DXY 5 日升幅 z — 美元避險走強為正。"""
    return causal_zscore(dxy_close.pct_change(5), baseline, min_periods)


def foreign_sell_accel(fnet_daily: pd.Series, baseline: int = 250,
                       min_periods: int = 60) -> pd.Series:
    """(−外資淨買金額) 5 日和 z — 賣超加速為正。"""
    return causal_zscore((-fnet_daily).rolling(5, min_periods=3).sum(),
                         baseline, min_periods)
```

- [x] **Step 4: 跑測試確認通過**

```bash
.venv/bin/python -m pytest tests/test_geo_indicators.py -v
```
Expected: 7 passed。

- [x] **Step 5: Commit**

```bash
git add scripts/geo_attr/__init__.py scripts/geo_attr/indicators.py tests/test_geo_indicators.py
git commit -m "feat(geo-attr): 指標引擎 — causal z-score(不含當前點)+六指標,符號約定=壓力為正"
```

---

### Task 3: 檢驗引擎 (`scripts/geo_attr/leadlag.py`)

**Files:**
- Create: `scripts/geo_attr/leadlag.py`
- Test: `tests/test_geo_leadlag.py`

- [x] **Step 1: 寫失敗測試**

```python
# tests/test_geo_leadlag.py
import numpy as np
import pandas as pd

from scripts.geo_attr.leadlag import classify_event, false_alarm_rate

DATES = pd.bdate_range("2025-01-01", periods=200)


def _z(cross_offsets, trigger_pos=100, nan_frac=0.0):
    """z 序列: 預設 0,指定 offset(相對 trigger)處 = 3.0。"""
    vals = pd.Series(0.0, index=DATES)
    for off in cross_offsets:
        vals.iloc[trigger_pos + off] = 3.0
    if nan_frac:
        n = int(len(vals) * nan_frac)
        vals.iloc[:n] = np.nan
    return vals


def test_classify_leading():
    r = classify_event(_z([-10, -9]), DATES, DATES[100])
    assert r["category"] == "領先"
    assert r["first_cross"] == -10


def test_classify_coincident():
    assert classify_event(_z([0]), DATES, DATES[100])["category"] == "同步"
    assert classify_event(_z([-2]), DATES, DATES[100])["category"] == "同步"
    assert classify_event(_z([2]), DATES, DATES[100])["category"] == "同步"


def test_classify_lagging_and_silent():
    assert classify_event(_z([4]), DATES, DATES[100])["category"] == "落後"
    assert classify_event(_z([]), DATES, DATES[100])["category"] == "沉默"


def test_classify_boundary_minus3_is_leading():
    assert classify_event(_z([-3]), DATES, DATES[100])["category"] == "領先"


def test_classify_insufficient_data():
    z = _z([], nan_frac=0.95)   # 觀察窗內 >50% NaN
    assert classify_event(z, DATES, DATES[100])["category"] == "資料不足"


def test_false_alarm_rate_exact():
    """手算: index 200 日平盤(誤報必然:z>2 後 20 日不會跌 3%)。
    z 在 pos 50, 60 兩處 >2(非事件期);事件窗排除 pos 100±[−30,+20]。
    → 2 個警報日皆誤報 → far = 1.0, n_alerts = 2。
    另一情境: index 在 pos 60 後 10 日內崩 −10% → pos 60 非誤報,far = 0.5。"""
    index_flat = pd.Series(100.0, index=DATES)
    z = pd.Series(0.0, index=DATES)
    z.iloc[50] = 3.0
    z.iloc[60] = 3.0
    events = [dict(trigger_date=DATES[100])]
    far, n = false_alarm_rate(z, index_flat, events)
    assert (far, n) == (1.0, 2)

    # pos 65 起 −10%: pos50 的 forward 窗 51..70 含下跌(r_min=−10%<−3%)→非誤報;
    # pos60 窗 61..80 亦含 → 非誤報 → far2 = 0.0
    vals = [100.0] * 65 + [90.0] * 135
    index_drop = pd.Series(vals, index=DATES)
    far2, n2 = false_alarm_rate(z, index_drop, events)
    assert n2 == 2
    assert far2 == 0.0
```

- [x] **Step 2: 跑測試確認失敗**

```bash
.venv/bin/python -m pytest tests/test_geo_leadlag.py -v
```
Expected: FAIL — ModuleNotFoundError。

- [x] **Step 3: 實作**

```python
# scripts/geo_attr/leadlag.py
"""事件窗領先/同步分類＋誤報率（spec Phase C）。

分類(z>2 首次出現的 trigger 相對位置 first):
  first <= −3 → 領先;−2 <= first <= 2 → 同步;first >= 3 → 落後;無 → 沉默。
觀察窗 [−30, +5];窗內 z 有效值 <50% → 資料不足。
誤報率沿用 LPPLS FP 語意(forward_return 復用 walkforward)。
"""
import numpy as np
import pandas as pd

from scripts.lppls.walkforward import forward_return

Z_THR = 2.0
PRE, POST = 30, 5
LEAD_MIN = 3


def classify_event(z: pd.Series, index_dates: pd.Index, trigger_date,
                   z_thr: float = Z_THR, pre: int = PRE, post: int = POST,
                   lead_min: int = LEAD_MIN) -> dict:
    pos = index_dates.get_loc(trigger_date)
    window = index_dates[max(0, pos - pre): min(len(index_dates), pos + post + 1)]
    zw = z.reindex(window)
    if zw.notna().mean() < 0.5:
        return dict(category="資料不足", first_cross=None)
    crossed = [index_dates.get_loc(d) - pos for d, v in zw.items() if v > z_thr]
    if not crossed:
        return dict(category="沉默", first_cross=None)
    first = min(crossed)
    if first <= -lead_min:
        cat = "領先"
    elif abs(first) <= 2:
        cat = "同步"
    else:
        cat = "落後"
    return dict(category=cat, first_cross=int(first))


def false_alarm_rate(z: pd.Series, index_series: pd.Series, events,
                     z_thr: float = Z_THR, horizon: int = 20,
                     drop_thr: float = -0.03, pre: int = PRE) -> tuple:
    """非事件期 z>z_thr 的日子,後 horizon 日指數未跌逾 |drop_thr| 的比率。
    事件排除窗 = 各 trigger 的 [−pre, +horizon]。回傳 (far, n_alerts);無警報 → (None, 0)。"""
    excluded = set()
    for ev in events:
        pos = index_series.index.get_loc(ev["trigger_date"])
        lo = max(0, pos - pre)
        hi = min(len(index_series), pos + horizon + 1)
        excluded.update(index_series.index[lo:hi])
    fp = tot = 0
    for d, v in z.items():
        if v is None or not v == v or v <= z_thr or d in excluded:
            continue
        if d not in index_series.index:
            continue
        r_end, r_min = forward_return(index_series, d, horizon)
        if r_end is None:
            continue
        tot += 1
        if r_min > drop_thr:
            fp += 1
    return ((fp / tot) if tot else None, tot)
```

- [x] **Step 4: 跑測試確認通過**

```bash
.venv/bin/python -m pytest tests/test_geo_leadlag.py -v
```
Expected: 全數通過（含你修正 expected 後的 false-alarm 第二情境）。

- [x] **Step 5: Commit**

```bash
git add scripts/geo_attr/leadlag.py tests/test_geo_leadlag.py
git commit -m "feat(geo-attr): 事件窗領先/同步分類+誤報率 — 復用 lppls forward_return 保持 FP 語意一致"
```

---

### Task 4: Loaders + CLI (`loaders.py`, `geo_attr_study.py`)

**Files:**
- Create: `scripts/geo_attr/loaders.py`
- Create: `scripts/geo_attr_study.py`

loaders 為 thin wrapper 不寫單元測試（Task 5 實跑驗證）；CLI 以 `--help` smoke test。

- [x] **Step 1: 實作 loaders**

```python
# scripts/geo_attr/loaders.py
"""geo-attr 資料 loaders — gdelt/fx/外資全序列 + Brent yfinance cache。"""
import contextlib
from pathlib import Path

import pandas as pd

from scripts.lppls.db import connect

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "analysis" / "cache"


def load_gdelt(query_key: str) -> pd.DataFrame:
    sql = ("SELECT date, article_count, avg_tone FROM gdelt_daily "
           "WHERE query_key = %s ORDER BY date")
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn, params=(query_key,)).set_index("date")


def load_fx(pair: str) -> pd.Series:
    sql = "SELECT ts::date AS date, close FROM fx_daily WHERE pair = %s ORDER BY 1"
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn, params=(pair,)).set_index("date")["close"]


def load_foreign_net_value(components) -> pd.Series:
    """外資淨買金額(股數×收盤)全序列,加總成分股。"""
    sql = ("SELECT date, sum(foreign_net * close_price) AS fnet "
           "FROM institutional_stock WHERE symbol = ANY(%s) "
           "GROUP BY date ORDER BY date")
    with contextlib.closing(connect()) as conn:
        return pd.read_sql(sql, conn,
                           params=(list(components),)).set_index("date")["fnet"]


def load_brent(start="2024-12-01") -> pd.Series:
    """BZ=F 日線,cache 到 analysis/cache/brent_daily.csv(存在即直讀不重抓)。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / "brent_daily.csv"
    if cache.exists():
        df = pd.read_csv(cache, parse_dates=["date"])
        df["date"] = df["date"].dt.date
        return df.set_index("date")["close"]
    import yfinance as yf
    hist = yf.Ticker("BZ=F").history(start=start, auto_adjust=False)
    s = hist["Close"]
    s.index = [ts.date() for ts in s.index]
    s.index.name = "date"
    s.name = "close"
    s.to_frame().to_csv(cache)
    return s
```

- [x] **Step 2: 確認 yfinance 可用**

```bash
.venv/bin/python -c "import yfinance; print(yfinance.__version__)"
```
若未安裝: `uv pip install --python .venv/bin/python yfinance`。

- [x] **Step 3: 實作 CLI**

```python
#!/usr/bin/env python3
# scripts/geo_attr_study.py
"""地緣風險歸因研究 orchestrator。

用法: .venv/bin/python scripts/geo_attr_study.py
產出: analysis/geo_attribution_study_<today>.md
指標×事件矩陣 + 誤報率 + 事前準則角色判定;catalyst 標註(Phase B)由分析者於
commit 前補入 <!-- PHASE_B_CATALYST --> 標記處(最終報告不得殘留該標記)。
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from scripts.geo_attr import indicators as ind  # noqa: E402
from scripts.geo_attr import loaders  # noqa: E402
from scripts.geo_attr.leadlag import classify_event, false_alarm_rate  # noqa: E402
from scripts.lppls.db import load_daily_closes  # noqa: E402
from scripts.lppls.index_builder import (  # noqa: E402
    CANDIDATES, CORE, build_index, select_components,
)
from scripts.lppls.walkforward import detect_drawdowns  # noqa: E402

GDELT_KEYS = ["tariff", "taiwan_strait", "tsmc", "semi_export", "mideast_oil"]
QUALIFY_LEAD_SHARE = 0.5   # 事前準則: >=50% 覆蓋事件領先
QUALIFY_FAR_MAX = 0.6      # 事前準則: 誤報率 <60%


def build_indicator_zoo(comps, index_s):
    """回傳 {指標名: z-series(以 index 交易日 reindex, ffill<=3)}。"""
    zoo = {}
    for key in GDELT_KEYS:
        g = loaders.load_gdelt(key)
        if g.empty:
            zoo[f"gdelt_{key}_vol"] = pd.Series(dtype=float)
            zoo[f"gdelt_{key}_tone"] = pd.Series(dtype=float)
            continue
        zoo[f"gdelt_{key}_vol"] = ind.gdelt_intensity(g["article_count"].astype(float))
        zoo[f"gdelt_{key}_tone"] = ind.gdelt_tone_deterioration(g["avg_tone"].astype(float))
    zoo["brent_shock"] = ind.brent_shock(loaders.load_brent())
    zoo["twd_depreciation"] = ind.twd_depreciation(loaders.load_fx("USDTWD"))
    zoo["dxy_strength"] = ind.dxy_strength(loaders.load_fx("DXY"))
    zoo["foreign_sell"] = ind.foreign_sell_accel(loaders.load_foreign_net_value(comps))
    # 對齊指數交易日(來源日曆不同: GDELT 每日/Brent 海外盤/外資台股盤)
    return {name: z.reindex(index_s.index).ffill(limit=3)
            for name, z in zoo.items()}


def run(out_path: Path):
    today = dt.date.today()
    closes = load_daily_closes(set(CORE) | set(CANDIDATES))
    comps, weights = select_components(closes)
    index_s = build_index(closes, weights)
    events = detect_drawdowns(index_s, threshold=0.05)
    zoo = build_indicator_zoo(comps, index_s)

    lines = [
        f"# 地緣風險歸因研究 ({today})", "",
        "**前情:** LPPLS Phase 1 負結果 — 回檔為事件驅動。本研究檢驗外生指標的領先性。",
        "Spec: docs/superpowers/specs/2026-08-27-geo-attribution-study-design.md", "",
        f"指數: 同 LPPLS 研究 18 檔電子權值 ({index_s.index[0]} → {index_s.index[-1]},"
        f" {len(index_s)} 交易日);事件 {len(events)} 次(≥5% 回檔)。", "",
        "## 1. 事件 catalyst 標註（Phase B）", "",
        "<!-- PHASE_B_CATALYST -->", "",
        "## 2. 指標 × 事件矩陣（觀察窗 [−30,+5]，z>2 首現位置）", "",
        "| 指標 | " + " | ".join(str(e["trigger_date"]) for e in events) + " | 誤報率 (警報數) | 角色判定 |",
        "|" + "---|" * (len(events) + 3),
    ]
    verdicts = {}
    for name, z in zoo.items():
        cells, lead_count, covered = [], 0, 0
        for ev in events:
            r = classify_event(z, index_s.index, ev["trigger_date"])
            if r["category"] == "資料不足":
                cells.append("∅")
                continue
            covered += 1
            if r["category"] == "領先":
                lead_count += 1
                cells.append(f"領先{r['first_cross']}")
            elif r["category"] == "同步":
                cells.append(f"同步{r['first_cross']:+d}")
            elif r["category"] == "落後":
                cells.append(f"落後+{r['first_cross']}")
            else:
                cells.append("—")
        far, n_alerts = false_alarm_rate(z, index_s, events)
        lead_share = (lead_count / covered) if covered else None
        if covered == 0:
            role = "資料不足"
        elif (lead_share >= QUALIFY_LEAD_SHARE
              and far is not None and far < QUALIFY_FAR_MAX):
            role = "警戒"
        elif any(c.startswith(("領先", "同步")) for c in cells):
            role = "確認"
        else:
            role = "剔除"
        verdicts[name] = dict(lead_share=lead_share, far=far, role=role,
                              covered=covered)
        far_s = "N/A" if far is None else f"{far:.0%}"
        lines.append(f"| {name} | " + " | ".join(cells)
                     + f" | {far_s} ({n_alerts}) | **{role}** |")

    n_warn = sum(1 for v in verdicts.values() if v["role"] == "警戒")
    lines += [
        "", "## 3. 事前準則判定", "",
        f"- 警戒資格: ≥50% 覆蓋事件領先 ≥3 交易日 且 誤報率 <60%。",
        f"- 獲警戒角色指標數: **{n_warn}** / {len(verdicts)}。",
        "- 領先 ≠ 因果;本研究只回答「值不值得監測」,不回答「為什麼」。", "",
        "## 4. Composite 設計建議", "",
        "<!-- PHASE_B_COMPOSITE -->", "",
        "## Verification log", "",
        "- 數字由本 script 對 DB + yfinance cache 實算;z-score 為 causal(不含當前點)。",
        f"- 產出指令: `.venv/bin/python scripts/geo_attr_study.py`",
        "- 覆蓋聲明: vix_daily 僅蓋 2/7 事件(案例研究,未進矩陣);margin/Kalshi 0/7 未檢驗。", "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入 {out_path}")
    for name, v in sorted(verdicts.items(), key=lambda kv: kv[1]["role"]):
        print(f"  {name}: role={v['role']} lead_share={v['lead_share']} far={v['far']}")


def main():
    ap = argparse.ArgumentParser(description="地緣風險歸因研究")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    out = Path(a.out) if a.out else (
        repo_root / f"analysis/geo_attribution_study_{dt.date.today()}.md")
    run(out)


if __name__ == "__main__":
    main()
```

- [x] **Step 4: Smoke test + 迴歸**

```bash
env -u PYTHONPATH .venv/bin/python scripts/geo_attr_study.py --help
.venv/bin/python -m pytest tests/ -q -k "geo or lppls"
```
Expected: usage 印出 exit 0；geo+lppls 測試全綠。

- [x] **Step 5: Commit**

```bash
git add scripts/geo_attr/loaders.py scripts/geo_attr_study.py
git commit -m "feat(geo-attr): loaders(gdelt/fx/外資/Brent cache) + study CLI — 矩陣/誤報率/角色判定"
```

---

### Task 5: 實跑 + Phase B 標註 + 終稿

**Files:**
- Create: `analysis/geo_attribution_study_<today>.md`（script 產出後補標註）

- [x] **Step 1: 實跑** `.venv/bin/python scripts/geo_attr_study.py`，檢查矩陣完整（GDELT 回補後 7/7 有值、Brent/fx/外資無 ∅ 整列）。
- [x] **Step 2: Phase B catalyst 標註**（controller 親自做，需 WebSearch）：對 7 事件逐一查證驅動因子，寫入 `<!-- PHASE_B_CATALYST -->` 處成表（事件/catalyst 分類/佐證來源/confidence marker）；用戶提示的 2025 關稅與 2026-03 美伊油價在此驗證或推翻。
- [x] **Step 3: 依矩陣結果撰寫 `<!-- PHASE_B_COMPOSITE -->` 段**：獲警戒角色的指標 → composite 草案（脆弱度×事件強度雙軸）；全無領先 → 誠實負結果，建議只做同步確認儀表。併入 vix_daily 對 2026-05/2026-06 兩事件的 IV 案例觀察（spec 的案例研究義務，不進判定）。兩標記皆不得殘留。
- [x] **Step 4: Commit + vault/log.md append + inbox 推播**（同 LPPLS 收檔慣例，topic=study）。
- [x] **Step 5: verification-before-completion**：全測試綠、報告無標記殘留、判定明確，才回報完成。
