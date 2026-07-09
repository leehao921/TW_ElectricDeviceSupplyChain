"""Memory cycle sell-signal monitor for 南亞科 2408 / 華邦電 2344.

See docs/superpowers/specs/2026-06-25-memory-cycle-monitor-design.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

# Light constants
GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

PB_LIGHTS_HASH = "h:agent:pb_lights"

# Spec §4 S2 thresholds
DDR5_QOQ_YELLOW_PCT = 10.0  # below this in absolute QoQ → yellow
DDR5_QOQ_RED_PCT = 5.0      # below this → red
DDR5_DECAY_YELLOW = 0.5     # 衰減 >50% → yellow when 3 quarters available


@dataclass
class PricePoint:
    """One row from the YAML price series."""
    label: str   # "2026-04" or "2026Q1"
    price: float


@dataclass
class Inputs:
    """Parsed memory_cycle_inputs.yaml."""
    last_updated: str
    notes: str
    ddr4_8gb_spot_usd: list[PricePoint] = field(default_factory=list)
    ddr5_16gb_contract_usd: list[PricePoint] = field(default_factory=list)
    mu_next_quarter_gm_guide: float | None = None
    mu_next_quarter_rev_qoq: float | None = None


@dataclass
class SignalResult:
    """One signal's computed light + human-readable value + raw detail."""
    light: str            # GREEN | YELLOW | RED | "N/A"
    value: str            # short string for report (e.g. "+10.6%")
    detail: dict[str, Any] = field(default_factory=dict)


def load_inputs(path: str | Path) -> Inputs:
    """Parse memory_cycle_inputs.yaml into an Inputs dataclass.

    Sorts price series by label (string sort works for both "2026-04" and "2026Q1").
    Raises ValueError on missing required fields.
    """
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    if "last_updated" not in raw:
        raise ValueError("YAML missing required field: last_updated")

    def _parse_series(rows: list[dict], label_key: str) -> list[PricePoint]:
        if not rows:
            return []
        pts = [PricePoint(label=str(r[label_key]), price=float(r["price"])) for r in rows]
        pts.sort(key=lambda pp: pp.label)
        return pts

    return Inputs(
        last_updated=str(raw["last_updated"]),
        notes=str(raw.get("notes", "")),
        ddr4_8gb_spot_usd=_parse_series(raw.get("ddr4_8gb_spot_usd") or [], "month"),
        ddr5_16gb_contract_usd=_parse_series(raw.get("ddr5_16gb_contract_usd") or [], "quarter"),
        mu_next_quarter_gm_guide=raw.get("mu_next_quarter_gm_guide"),
        mu_next_quarter_rev_qoq=raw.get("mu_next_quarter_rev_qoq"),
    )


def compute_s2a_ddr4(series: list[PricePoint]) -> SignalResult:
    """S2a: DDR4 8Gb 現貨價 MoM.

    Green: latest MoM ≥ 0%
    Yellow: latest MoM < 0% (single negative month)
    Red: latest 2 consecutive months MoM < 0%
    N/A: <2 data points
    """
    if len(series) < 2:
        return SignalResult(light="N/A", value="insufficient data")

    def _mom(a: PricePoint, b: PricePoint) -> float:
        return (b.price - a.price) / a.price * 100

    latest_mom = _mom(series[-2], series[-1])
    value = f"{latest_mom:+.1f}%"

    if latest_mom >= 0:
        return SignalResult(light=GREEN, value=value, detail={"mom_pct": latest_mom})

    # latest is negative; check previous month
    if len(series) >= 3:
        prev_mom = _mom(series[-3], series[-2])
        if prev_mom < 0:
            return SignalResult(
                light=RED, value=value,
                detail={"mom_pct": latest_mom, "prev_mom_pct": prev_mom},
            )

    return SignalResult(light=YELLOW, value=value, detail={"mom_pct": latest_mom})


def compute_s2b_ddr5(series: list[PricePoint]) -> SignalResult:
    """S2b: DDR5 16Gb 合約價 QoQ — dual threshold.

    With 3+ quarters (full mode):
      Green:  QoQ ≥ +10% AND decay < 50%
      Yellow: QoQ < +10% OR decay > 50%
      Red:    QoQ < +5% or negative

    With exactly 2 quarters (degraded — no decay computable):
      Green:  QoQ ≥ +10%
      Yellow: +5% ≤ QoQ < +10%
      Red:    QoQ < +5% or negative
    """
    if len(series) < 2:
        return SignalResult(light="N/A", value="insufficient data")

    def _qoq(a: PricePoint, b: PricePoint) -> float:
        return (b.price - a.price) / a.price * 100

    latest_qoq = _qoq(series[-2], series[-1])
    detail: dict[str, Any] = {"qoq_pct": latest_qoq, "decay_pct": None}

    # Compute decay if 3+ quarters available
    if len(series) >= 3:
        prev_qoq = _qoq(series[-3], series[-2])
        if prev_qoq > 0:
            decay = (prev_qoq - latest_qoq) / prev_qoq
            detail["decay_pct"] = decay * 100
            detail["prev_qoq_pct"] = prev_qoq

    # Red (absolute) — applies in both modes
    if latest_qoq < DDR5_QOQ_RED_PCT:
        return SignalResult(light=RED, value=f"{latest_qoq:+.1f}%", detail=detail)

    # Yellow checks
    if latest_qoq < DDR5_QOQ_YELLOW_PCT:
        return SignalResult(light=YELLOW, value=f"{latest_qoq:+.1f}%", detail=detail)
    if detail["decay_pct"] is not None and detail["decay_pct"] / 100 > DDR5_DECAY_YELLOW:
        return SignalResult(light=YELLOW, value=f"{latest_qoq:+.1f}%", detail=detail)

    return SignalResult(light=GREEN, value=f"{latest_qoq:+.1f}%", detail=detail)


_LIGHT_RANK = {GREEN: 0, YELLOW: 1, RED: 2}


def _worst(*lights: str) -> str:
    known = [lg for lg in lights if lg in _LIGHT_RANK]
    if not known:
        return "N/A"
    return max(known, key=_LIGHT_RANK.__getitem__)


def _bare_ticker(ticker: str) -> str:
    """Strip the yfinance market suffix to get the bare hash key ("2408.TW"→"2408")."""
    for suffix in (".TW", ".TWO"):
        if ticker.endswith(suffix):
            return ticker[: -len(suffix)]
    return ticker


def read_pb_lights(client, tickers: list[str]) -> dict[str, dict | None]:
    """Read pre-computed P/B light records from the `h:agent:pb_lights` hash.

    Maps each suffixed monitor ticker ("2408.TW") to the hash's bare field key
    ("2408"). Missing field or JSON parse error → None for that ticker.
    Returns {suffixed_ticker: record_dict | None}.
    """
    try:
        raw = client.hgetall(PB_LIGHTS_HASH) or {}
    except Exception as e:  # noqa: BLE001 — Redis unreachable → all None, fallback handles it
        print(f"[warn] read_pb_lights: h:agent:pb_lights unreachable: {e}",
              file=sys.stderr)
        raw = {}
    out: dict[str, dict | None] = {}
    for ticker in tickers:
        field_val = raw.get(_bare_ticker(ticker))
        if field_val is None:
            out[ticker] = None
            continue
        try:
            out[ticker] = json.loads(field_val)
        except (json.JSONDecodeError, TypeError):
            out[ticker] = None
    return out


def _import_pb_percentile():
    """Import the sibling engine-A module regardless of how this file was loaded.

    Works whether the monitor is run as a script (scripts/ on sys.path) or
    imported as `scripts.memory_cycle_monitor` (scripts/ not on sys.path).
    """
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import pb_percentile
    return pb_percentile


def s1_lights_with_fallback(client, tickers: list[str]) -> dict[str, dict | None]:
    """read_pb_lights + engine-A self-heal for tickers the hash is missing.

    If Component 1 (pb_lights_publish) hasn't run, the hash may lack a ticker.
    For any None record, call `pb_percentile.pb_light(<bare ticker>)` directly and
    use it when it yields a usable (non-N/A) light. Any failure → keep None.
    """
    records = read_pb_lights(client, tickers)
    for ticker, rec in records.items():
        if rec is not None:
            continue
        print(f"[warn] pb_lights hash missing {ticker}; falling back to direct "
              f"engine-A pb_light", file=sys.stderr)
        try:
            pb_percentile = _import_pb_percentile()
            fb = pb_percentile.pb_light(_bare_ticker(ticker))
            if fb and fb.get("light") != "N/A":
                # normalize field names to the hash record shape
                records[ticker] = {
                    "light": fb["light"],
                    "pb_current": fb.get("pb_current"),
                    "percentile": fb.get("percentile"),
                    "p70": fb.get("p70"),
                    "p85": fb.get("p85"),
                    "asof": fb.get("asof"),
                    "source": fb.get("source"),
                }
        except Exception:  # noqa: BLE001 — self-heal is best-effort
            records[ticker] = None
    return records


def compute_s1_pb(pb_lights: dict[str, dict | None]) -> SignalResult:
    """S1: engine-A P/B percentile lights for 2408.TW and 2344.TW.

    Consumes pre-computed light records (from the `h:agent:pb_lights` hash):
    each record is {light, pb_current, percentile, p70, p85, asof, source} or None.
    Takes the light directly (already GREEN/YELLOW/RED/N/A); stores per-ticker
    detail {pb, percentile, p70, p85, as_of, source, light}, or "N/A" when the
    record is None. Overall light is the worst-known of the two.
    """
    detail: dict[str, Any] = {}
    lights = []
    parts = []
    for ticker, rec in pb_lights.items():
        lg = rec.get("light", "N/A") if isinstance(rec, dict) else "N/A"
        if lg not in (GREEN, YELLOW, RED):
            # None record or valid JSON with missing/unknown light → N/A path
            detail[ticker] = "N/A"
            lights.append("N/A")
            parts.append(f"{ticker}=N/A")
            continue
        pb = rec.get("pb_current")
        pct = rec.get("percentile")
        detail[ticker] = {
            "pb": pb,
            "percentile": pct,
            "p70": rec.get("p70"),
            "p85": rec.get("p85"),
            "as_of": rec.get("asof"),
            "source": rec.get("source"),
            "light": lg,
        }
        lights.append(lg)
        if pb is None:
            parts.append(f"{ticker}=N/A")
        elif pct is None:
            parts.append(f"{ticker}={pb:.2f}")
        else:
            parts.append(f"{ticker}={pb:.2f}(p{pct:.0f})")

    return SignalResult(light=_worst(*lights), value=", ".join(parts), detail=detail)


def detect_monthly_weakness(closes: list[float]) -> bool:
    """Spec §4 S3: latest month close < min of prior 3 months close.

    `closes` is chronological; index -1 is latest. Need ≥4 points.
    """
    if len(closes) < 4:
        return False
    prior_3_min = min(closes[-4:-1])
    return closes[-1] < prior_3_min


def compute_s3_lights(*, mu_weak: bool, hynix_weak: bool, tw_weak: bool) -> SignalResult:
    """S3 truth table from spec §4.

    | MU  | Hynix | TW  | Light  | Note                          |
    | --- | ----- | --- | ------ | ----------------------------- |
    | not | -     | -   | GREEN  | primary signal not triggered  |
    | wk  | not   | -   | YELLOW | single-head warning           |
    | wk  | wk    | not | RED    | dual-head lead confirmed      |
    | wk  | wk    | wk  | YELLOW | lead window closed            |
    """
    detail = {"mu_weak": mu_weak, "hynix_weak": hynix_weak, "tw_weak": tw_weak}
    if not mu_weak:
        return SignalResult(light=GREEN, value="MU not weak", detail=detail)
    if not hynix_weak:
        return SignalResult(light=YELLOW, value="MU weak only", detail=detail)
    # MU + Hynix both weak
    if tw_weak:
        return SignalResult(light=YELLOW, value="lead window closed", detail=detail)
    return SignalResult(light=RED, value="MU+Hynix lead TW", detail=detail)


def fetch_monthly_closes(ticker: str, months: int = 13) -> list[float]:
    """Return last `months` of monthly close prices for `ticker`.

    Drops rows with NaN closes via .dropna(); returns [] on failure.
    Note: the current (partial) month is NOT dropped — caller's monthly-weakness
    check must tolerate the last value being mid-month if run before month-end.
    """
    import yfinance as yf
    try:
        hist = yf.Ticker(ticker).history(period=f"{months}mo", interval="1mo")
        if hist is None or hist.empty:
            return []
        closes = hist["Close"].dropna().tolist()
        return [float(c) for c in closes]
    except Exception:
        return []


def aggregate(*, s1: SignalResult, s2a: SignalResult, s2b: SignalResult, s3: SignalResult) -> dict:
    """Combine the 4 signals into overall light + candidate stage.

    Candidate stage (spec §4 S4):
      3 if any RED
      2 if S3 YELLOW
      1 if S1 or S2 (any) YELLOW
      0 otherwise
    Final stage = max(candidate, historical max from state file) — caller handles that.
    """
    s2_worst = _worst(s2a.light, s2b.light)
    overall = _worst(s1.light, s2_worst, s3.light)

    candidate = 0
    if RED in (s1.light, s2a.light, s2b.light, s3.light):
        candidate = 3
    elif s3.light == YELLOW:
        candidate = 2
    elif s1.light == YELLOW or s2_worst == YELLOW:
        candidate = 1

    return {
        "overall_light": overall,
        "trim_stage_candidate": candidate,
        "s2_combined_light": s2_worst,
    }


def advance_state(*, candidate: int, state_path: Path, today: str | None = None) -> dict:
    """Monotonic stage progression backed by JSON state file.

    Returns dict with: stage, max_stage_seen, max_stage_first_seen_at.
    """
    today = today or date.today().isoformat()
    state_path = Path(state_path)

    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        state = {"max_stage_seen": 0, "max_stage_first_seen_at": None}

    if candidate > state["max_stage_seen"]:
        state["max_stage_seen"] = candidate
        state["max_stage_first_seen_at"] = today

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))

    return {"stage": state["max_stage_seen"], **state}


LIGHT_EMOJI = {GREEN: "🟢", YELLOW: "🟡", RED: "🔴", "N/A": "⚪"}

STAGE_ACTION = {
    0: "HOLD;等下次更新",
    1: "第一段 trim 30%",
    2: "第二段 trim 40%(累計 70%)",
    3: "第三段 trim 30%(累計 100%,止損 / 全砍)",
}


def render_markdown(
    *,
    report_date: str,
    overall_light: str,
    trim_stage: int,
    max_stage_seen: int,
    next_trigger: str,
    last_updated_yaml: str,
    s1: SignalResult,
    s2a: SignalResult,
    s2b: SignalResult,
    s3: SignalResult,
) -> str:
    """Render the daily Markdown report. Pure function — no I/O."""
    emoji = LIGHT_EMOJI.get(overall_light, "⚪")
    action = STAGE_ACTION[trim_stage]

    # S1 table
    def _fmt(x, prec=2):
        return "N/A" if x is None else f"{x:.{prec}f}"

    s1_rows = []
    for ticker, label in [("2408.TW", "南亞科 2408"), ("2344.TW", "華邦電 2344")]:
        info = s1.detail.get(ticker)
        if isinstance(info, dict):
            pb = _fmt(info.get("pb"))
            pct = info.get("percentile")
            pct_str = "N/A" if pct is None else f"p{pct:.0f}"
            p70 = _fmt(info.get("p70"))
            p85 = _fmt(info.get("p85"))
            lg = LIGHT_EMOJI[info["light"]]
        else:
            pb, pct_str, p70, p85, lg = "N/A", "N/A", "N/A", "N/A", "⚪"
        s1_rows.append(f"| {label} | {pb} | {pct_str} | {p70} | {p85} | {lg} |")
    s1_table = "\n".join(s1_rows)

    # S2 detail strings
    decay = s2b.detail.get("decay_pct")
    decay_str = "N/A" if decay is None else f"{decay:.1f}%"

    # S3 detail
    s3d = s3.detail
    s3_table = "\n".join([
        f"| MU | {'轉弱' if s3d.get('mu_weak') else '站穩'} | "
        f"{LIGHT_EMOJI[RED if s3d.get('mu_weak') else GREEN]} |",
        f"| Hynix 000660.KS | {'轉弱' if s3d.get('hynix_weak') else '站穩'} | "
        f"{LIGHT_EMOJI[RED if s3d.get('hynix_weak') else GREEN]} |",
        f"| 2408 / 2344 | {'轉弱' if s3d.get('tw_weak') else '站穩'} | "
        f"{LIGHT_EMOJI[RED if s3d.get('tw_weak') else GREEN]} |",
    ])

    # Build Verification-log provenance lines from s1.detail
    pulled_at = datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")

    provenance_lines = []
    for ticker, label in [("2408.TW", "南亞科 2408"), ("2344.TW", "華邦電 2344")]:
        info = s1.detail.get(ticker)
        if isinstance(info, dict):
            pb_val = info.get("pb")
            pct = info.get("percentile")
            p70 = info.get("p70")
            p85 = info.get("p85")
            asof = info.get("as_of")
            source = info.get("source") or "N/A"
            pb_str = f"{pb_val:.2f}" if pb_val is not None else "N/A"
            pct_str = f"p{pct:.0f}" if pct is not None else "N/A"
            p70_str = f"{p70:.2f}" if p70 is not None else "N/A"
            p85_str = f"{p85:.2f}" if p85 is not None else "N/A"
            provenance_lines.append(
                f"  - {label}: P/B {pb_str} (percentile {pct_str}, "
                f"cutoffs p70={p70_str} / p85={p85_str}, source {source}, "
                f"as of {asof or 'N/A'})"
            )
    provenance_block = "\n".join(provenance_lines) if provenance_lines else "  - (no P/B data)"

    return f"""# 記憶體週期燈號 — {report_date}

**總燈號:** {emoji} {overall_light}   **Trim 進度:** {trim_stage} / 3   \
**Action:** {action}
**下一段觸發:** {next_trigger}
**Inputs YAML last_updated:** {last_updated_yaml}   **Max stage seen:** {max_stage_seen}

---

## S1 — 兩檔估值溢價
| 標的 | P/B | 歷史分位 | p70 | p85 | 燈號 |
|---|---|---|---|---|---|
{s1_table}

## S2 — DRAM 報價動能
- **S2a DDR4 8Gb 現貨 MoM:** {s2a.value} {LIGHT_EMOJI[s2a.light]}
- **S2b DDR5 16Gb 合約 QoQ:** {s2b.value};相對前季衰減 {decay_str} {LIGHT_EMOJI[s2b.light]}

## S3 — 跨市場領先訊號
| Source | 月線狀態 | 燈號 |
|---|---|---|
{s3_table}

## Verification log
- Data source: `data/memory_cycle_inputs.yaml` last_updated {last_updated_yaml}
- Data pulled at: {pulled_at}
- P/B source: `h:agent:pb_lights` (engine-A percentile; see scripts/pb_percentile.py)
- P/B provenance:
{provenance_block}
- Spec: `docs/superpowers/specs/2026-06-25-memory-cycle-monitor-design.md`

## Action
**{action}**
"""


INBOX_STREAM = "claude:inbox"


def build_inbox_summary(
    *,
    report_date: str,
    overall_light: str,
    trim_stage: int,
    s1: SignalResult,
    s2a: SignalResult,
    s2b: SignalResult,
    s3: SignalResult,
) -> str:
    """Build a SHORT inbox digest (NOT the full report). Pure function.

    Header line with overall light emoji + trim stage, one line per signal
    (S1/S2/S3) with its light + short value, and a pointer to the full report.
    ~6-10 lines.
    """
    overall_emoji = LIGHT_EMOJI.get(overall_light, "⚪")
    s2_worst = _worst(s2a.light, s2b.light)
    s2_emoji = LIGHT_EMOJI.get(s2_worst, "⚪")
    action = STAGE_ACTION[trim_stage]
    lines = [
        f"記憶體週期燈號 {report_date}",
        f"總燈號 {overall_emoji} {overall_light} · Trim {trim_stage}/3 · {action}",
        f"S1 估值溢價 {LIGHT_EMOJI.get(s1.light, '⚪')} {s1.light} — {s1.value}",
        f"S2 DRAM 報價 {s2_emoji} {s2_worst} — DDR4 {s2a.value} / DDR5 {s2b.value}",
        f"S3 跨市場領先 {LIGHT_EMOJI.get(s3.light, '⚪')} {s3.light} — {s3.value}",
        f"→ 全文 docs/analysis/memory_cycle_{report_date}.md",
    ]
    return "\n".join(lines)


def push_inbox(client, summary: str, report_date: str) -> bool:
    """Push the digest to the claude:inbox stream (topic=memory-cycle). Thin I/O."""
    try:
        client.xadd(INBOX_STREAM, {
            "topic": "memory-cycle",
            "from": "memory_cycle_monitor",
            "tags": "memory-cycle,daily",
            "as_of": report_date,
            "msg": summary,
        })
        return True
    except Exception as e:  # noqa: BLE001 — inbox push is best-effort
        print(f"[warn] inbox push failed: {e}", file=sys.stderr)
        return False


def publish_redis(*, client, hash_name: str, data: dict) -> None:
    """HSET all fields of `data` to `hash_name`. None values → empty string."""
    flat = {k: ("" if v is None else str(v)) for k, v in data.items()}
    client.hset(hash_name, mapping=flat)


def make_redis_client():
    """Standard Redis client per project convention.

    Honors env vars: REDIS_HOST (default 'localhost'), REDIS_PORT (default 6379),
    REDIS_DB (default 0). Reuses connection params from `redis-trading` MCP config.
    """
    import os
    import redis
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=int(os.environ.get("REDIS_DB", "0")),
        decode_responses=True,
    )


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = PROJECT_ROOT / "data" / "memory_cycle_inputs.yaml"
DEFAULT_STATE = PROJECT_ROOT / "data" / "memory_cycle_state.json"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "docs" / "analysis"
REDIS_HASH = "h:agent:memory_cycle"

TICKERS = ["2408.TW", "2344.TW"]


def _build_redis_payload(*, report_date, overall_light, trim_stage, max_stage_seen,
                         next_trigger, s1, s2a, s2b, s3, report_path) -> dict:
    tz = ZoneInfo("Asia/Taipei")

    def _pb_field(t, field_name):
        d = s1.detail.get(t)
        return d.get(field_name) if isinstance(d, dict) else None

    return {
        "updated_at": datetime.now(tz).isoformat(timespec="seconds"),
        "overall_light": overall_light,
        "trim_stage": trim_stage,
        "max_stage_seen": max_stage_seen,
        "next_trigger": next_trigger,
        "s1_pb_2408": _pb_field("2408.TW", "pb"),
        "s1_pb_2408_percentile": _pb_field("2408.TW", "percentile"),
        "s1_pb_2408_p70": _pb_field("2408.TW", "p70"),
        "s1_pb_2408_p85": _pb_field("2408.TW", "p85"),
        "s1_pb_2408_as_of": _pb_field("2408.TW", "as_of"),
        "s1_pb_2344": _pb_field("2344.TW", "pb"),
        "s1_pb_2344_percentile": _pb_field("2344.TW", "percentile"),
        "s1_pb_2344_p70": _pb_field("2344.TW", "p70"),
        "s1_pb_2344_p85": _pb_field("2344.TW", "p85"),
        "s1_pb_2344_as_of": _pb_field("2344.TW", "as_of"),
        "s1_light": s1.light,
        "s2a_ddr4_mom_pct": s2a.detail.get("mom_pct"),
        "s2b_ddr5_qoq_pct": s2b.detail.get("qoq_pct"),
        "s2b_ddr5_decay_pct": s2b.detail.get("decay_pct"),
        "s2_light": _worst(s2a.light, s2b.light),
        "s3_mu_monthly": YELLOW if s3.detail.get("mu_weak") else GREEN,
        "s3_hynix_monthly": YELLOW if s3.detail.get("hynix_weak") else GREEN,
        "s3_tw_monthly": YELLOW if s3.detail.get("tw_weak") else GREEN,
        "s3_light": s3.light,
        "report_path": report_path,
    }


def _suggest_next_trigger(s1: SignalResult, s2a: SignalResult, s2b: SignalResult, s3: SignalResult, *, stage: int) -> str:
    if stage == 3:
        return "全部三段已觸發 — 持倉應已歸零;state file `data/memory_cycle_state.json` 為單向,如需手動回退請編輯"
    if s2a.light == GREEN:
        return "S2a DDR4 首次負 MoM"
    if s2b.light == GREEN:
        return "S2b DDR5 QoQ 衰減 >50% 或 <+10%"
    if s1.light == GREEN:
        return "S1 任一檔 P/B 進入警戒區"
    if s3.light == GREEN:
        return "S3 MU 月線轉弱"
    return "升級至下一個 trim stage"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Memory cycle sell-signal monitor")
    parser.add_argument("--inputs", default=str(DEFAULT_INPUTS))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--dry-run", action="store_true",
                        help="Print Markdown to stdout, do not write files or push Redis")
    parser.add_argument("--no-redis", action="store_true",
                        help="Write Markdown but skip Redis push")
    parser.add_argument("--no-notify", action="store_true",
                        help="skip claude:inbox push")
    args = parser.parse_args(argv)

    # Load inputs
    try:
        inp = load_inputs(args.inputs)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: inputs YAML invalid: {e}", file=sys.stderr)
        return 1

    # Compute signals
    s2a = compute_s2a_ddr4(inp.ddr4_8gb_spot_usd)
    s2b = compute_s2b_ddr5(inp.ddr5_16gb_contract_usd)

    pb_client = make_redis_client()
    pb_lights = s1_lights_with_fallback(pb_client, TICKERS)
    if all(v is None for v in pb_lights.values()):
        print("ERROR: no P/B lights available (hash empty + fallback failed)",
              file=sys.stderr)
        return 2
    s1 = compute_s1_pb(pb_lights)

    mu_closes = fetch_monthly_closes("MU")
    hynix_closes = fetch_monthly_closes("000660.KS")
    tw_weakness_flags = []
    for t in TICKERS:
        cl = fetch_monthly_closes(t)
        if cl:
            tw_weakness_flags.append(detect_monthly_weakness(cl))
    tw_weak = any(tw_weakness_flags)
    s3 = compute_s3_lights(
        mu_weak=detect_monthly_weakness(mu_closes),
        hynix_weak=detect_monthly_weakness(hynix_closes),
        tw_weak=tw_weak,
    )

    # Aggregate
    agg = aggregate(s1=s1, s2a=s2a, s2b=s2b, s3=s3)

    # State (skipped on dry-run so test runs don't mutate disk)
    today = date.today().isoformat()
    if args.dry_run:
        stage = agg["trim_stage_candidate"]
        max_seen = stage
    else:
        state = advance_state(candidate=agg["trim_stage_candidate"],
                              state_path=Path(args.state), today=today)
        stage = state["stage"]
        max_seen = state["max_stage_seen"]

    next_trigger = _suggest_next_trigger(s1, s2a, s2b, s3, stage=stage)
    report_path = Path(args.report_dir) / f"memory_cycle_{today}.md"

    md = render_markdown(
        report_date=today,
        overall_light=agg["overall_light"],
        trim_stage=stage,
        max_stage_seen=max_seen,
        next_trigger=next_trigger,
        last_updated_yaml=inp.last_updated,
        s1=s1, s2a=s2a, s2b=s2b, s3=s3,
    )

    if args.dry_run:
        print(md)
        return 0

    # Write Markdown
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md)

    # Publish Redis (unless --no-redis)
    if not args.no_redis:
        # Build payload OUTSIDE the try so bugs in payload construction surface as real
        # tracebacks instead of being mis-attributed to a Redis failure.
        payload = _build_redis_payload(
            report_date=today, overall_light=agg["overall_light"],
            trim_stage=stage, max_stage_seen=max_seen, next_trigger=next_trigger,
            s1=s1, s2a=s2a, s2b=s2b, s3=s3, report_path=str(report_path),
        )
        try:
            client = make_redis_client()
            publish_redis(client=client, hash_name=REDIS_HASH, data=payload)
        except Exception as e:
            print(f"WARN: Redis push failed: {e}", file=sys.stderr)
            return 3

    # Push a concise digest to claude:inbox (unless --no-notify).
    # Not reached on --dry-run (which returns above).
    if not args.no_notify:
        summary = build_inbox_summary(
            report_date=today, overall_light=agg["overall_light"],
            trim_stage=stage, s1=s1, s2a=s2a, s2b=s2b, s3=s3,
        )
        if push_inbox(make_redis_client(), summary, today):
            print("[ok] pushed to claude:inbox topic=memory-cycle")

    print(f"Wrote {report_path} (overall: {agg['overall_light']}, stage {stage})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
