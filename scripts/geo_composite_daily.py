#!/usr/bin/env python3
"""地緣複合 paper-trade 儀表 — 雙軸評估 / 燈號 / 20 日自動對帳。

每日跑一次（launchd com.lulala.geo-composite Mon-Fri 18:20）；
--dry-run 只印，不寫 state，不推 inbox。

Architecture: §4.4 of analysis/geo_attribution_study_2026-08-28.md
定位：paper-trade 期間警報不構成行動建議。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# ── 路徑設置 ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.geo_attr_study import build_indicator_zoo  # noqa: E402
from scripts.lppls.confirmation import load_iv, load_margin, score_margin  # noqa: E402
from scripts.lppls.db import load_daily_closes  # noqa: E402
from scripts.lppls.index_builder import (  # noqa: E402
    CANDIDATES, CORE, build_index, select_components,
)
from scripts.lppls.walkforward import forward_return  # noqa: E402

# ── 常數 ──────────────────────────────────────────────────────────────────────
Z_THR = 2.0
STATE_PATH = REPO_ROOT / "data" / "geo_composite_state.json"
INBOX_STREAM = "claude:inbox"

# ══════════════════════════════════════════════════════════════════════════════
# Pure Functions
# ══════════════════════════════════════════════════════════════════════════════


def _z_above(val: float | None, threshold: float = Z_THR) -> bool:
    """Return True iff val is not None and strictly > threshold."""
    return val is not None and val > threshold


def evaluate_strength(z: dict[str, float | None]) -> dict:
    """Evaluate event-strength axis from z-score dict.

    Args:
        z: mapping of indicator name → current z-value (float or None).
           None is treated as not triggered.

    Returns dict with:
        regulation (bool): semi_export_vol > Z_THR OR tariff_tone > Z_THR
        rates      (bool): ust10y_surge > Z_THR
        oil        (bool): brent_shock > Z_THR AND mideast_oil_vol > Z_THR (dual confirm)
        triggered  (bool): any channel triggered
        detail     (dict): per-indicator z values for logging
    """
    regulation = (
        _z_above(z.get("gdelt_semi_export_vol")) or
        _z_above(z.get("gdelt_tariff_tone"))
    )
    rates = _z_above(z.get("ust10y_surge"))
    oil = (
        _z_above(z.get("brent_shock")) and
        _z_above(z.get("gdelt_mideast_oil_vol"))
    )
    triggered = bool(regulation or rates or oil)
    detail = {
        "gdelt_semi_export_vol": z.get("gdelt_semi_export_vol"),
        "gdelt_tariff_tone": z.get("gdelt_tariff_tone"),
        "ust10y_surge": z.get("ust10y_surge"),
        "brent_shock": z.get("brent_shock"),
        "gdelt_mideast_oil_vol": z.get("gdelt_mideast_oil_vol"),
    }
    return dict(regulation=regulation, rates=rates, oil=oil,
                triggered=triggered, detail=detail)


def evaluate_fragility(
    iv_inverted: bool,
    vrp_neg: bool,
    foreign_z: float | None,
    margin_score: int | None,
) -> dict:
    """Evaluate fragility axis.

    Args:
        iv_inverted:  term_slope > 0 (backwardation / near > far)
        vrp_neg:      latest vrp_30d < 0
        foreign_z:    z-score of foreign_sell indicator (None = unavailable)
        margin_score: output of score_margin()["score"] — 1 fires, 0/None does not

    Returns dict with:
        iv      (bool): iv_inverted OR vrp_neg
        foreign (bool): foreign_z > Z_THR
        margin  (bool): margin_score == 1
        triggered (bool): any component fired
    """
    iv = bool(iv_inverted or vrp_neg)
    foreign = _z_above(foreign_z)
    margin = bool(margin_score == 1)
    triggered = bool(iv or foreign or margin)
    return dict(iv=iv, foreign=foreign, margin=margin, triggered=triggered)


def light(strength: dict, fragility: dict) -> str:
    """Compute traffic-light signal.

    Returns:
        "紅"  — both axes triggered
        "黃"  — exactly one axis triggered
        "綠"  — neither axis triggered
    """
    s = bool(strength.get("triggered"))
    f = bool(fragility.get("triggered"))
    if s and f:
        return "紅"
    if s or f:
        return "黃"
    return "綠"


def settle_alerts(
    records: list[dict],
    index_s: pd.Series,
    asof: dt.date,
) -> list[dict]:
    """Settle pending red-light alert records that have reached 20 trading days.

    For each record where light == '紅' and 'settle' key is absent:
      - If asof is ≥ 20 trading days after the alert date (per index_s.index):
          compute forward_return(index_s, alert_date, 20).
          r_min < -0.03 → settle = "hit"
          otherwise      → settle = "false"
      - If alert_date not in index_s.index → skip (skip gracefully)
      - If < 20 trading days → leave unsettled

    Modifies records in-place and returns them.
    """
    idx_dates = list(index_s.index)  # DatetimeIndex
    idx_date_set = {d.date() if hasattr(d, "date") else d for d in idx_dates}

    for rec in records:
        if rec.get("light") != "紅":
            continue
        if "settle" in rec:
            continue  # already settled — idempotent, never overwrite

        alert_date_raw = rec["date"]
        try:
            alert_date = (
                dt.date.fromisoformat(alert_date_raw)
                if isinstance(alert_date_raw, str)
                else alert_date_raw
            )
        except (ValueError, TypeError):
            continue

        if alert_date not in idx_date_set:
            continue  # not a trading day in the index → skip

        # Find position in index_s
        try:
            pos = index_s.index.get_loc(
                pd.Timestamp(alert_date) if not isinstance(alert_date, pd.Timestamp)
                else alert_date
            )
        except KeyError:
            continue

        # Count trading days from alert to asof
        asof_ts = pd.Timestamp(asof)
        trading_days_since = sum(1 for d in idx_dates[pos + 1:] if d <= asof_ts)

        if trading_days_since < 20:
            continue  # not yet matured

        # Compute forward return from the alert date
        alert_ts = pd.Timestamp(alert_date)
        _r_end, r_min = forward_return(index_s, alert_ts, horizon=20)

        if r_min is None:
            continue  # insufficient data

        rec["settle"] = "hit" if r_min < -0.03 else "false"

    return records


# ══════════════════════════════════════════════════════════════════════════════
# State I/O
# ══════════════════════════════════════════════════════════════════════════════


def _load_state(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            return raw.get("records", [])
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_state(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def _upsert_record(records: list[dict], new_rec: dict) -> list[dict]:
    """Replace the record for the same date if it exists, otherwise append."""
    date_str = new_rec["date"]
    for i, rec in enumerate(records):
        if rec.get("date") == date_str:
            records[i] = new_rec
            return records
    records.append(new_rec)
    return records


# ══════════════════════════════════════════════════════════════════════════════
# Inbox push
# ══════════════════════════════════════════════════════════════════════════════


def _push_inbox(
    message: str,
    as_of: dt.date,
    redis_host: str = "localhost",
    redis_port: int = 6379,
) -> bool:
    """Push to claude:inbox via redis-cli subprocess. Fail-soft (warn only)."""
    import os
    from datetime import datetime as _datetime
    fields = [
        "ts", _datetime.now().astimezone().isoformat(),
        "from", "geo_composite_daily",
        "topic", "geo-composite",
        "tags", "geo,composite,daily",
        "as_of", as_of.isoformat(),
        "msg", message,
    ]
    host = os.environ.get("REDIS_HOST", redis_host)
    port = int(os.environ.get("REDIS_PORT", str(redis_port)))
    cmd = ["redis-cli", "-h", host, "-p", str(port),
           "XADD", INBOX_STREAM, "*", *fields]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"[warn] geo-composite XADD failed: {result.stderr.strip()}", file=sys.stderr)
            return False
        print(f"[info] geo-composite XADD ok, id={result.stdout.strip()}", file=sys.stderr)
        return True
    except Exception as exc:
        print(f"[warn] geo-composite inbox push error (redis down?): {exc}", file=sys.stderr)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Message builder
# ══════════════════════════════════════════════════════════════════════════════


def _build_message(
    as_of: dt.date,
    signal: str,
    strength: dict,
    fragility: dict,
    records: list[dict],
) -> str:
    """Build one-line + settle summary inbox message."""
    def _flag(v: bool | None) -> str:
        if v is None:
            return "∅"
        return "✓" if v else "✗"

    reg = _flag(strength.get("regulation"))
    rates = _flag(strength.get("rates"))
    oil = _flag(strength.get("oil"))
    iv = _flag(fragility.get("iv"))
    foreign = _flag(fragility.get("foreign"))
    margin = fragility.get("margin")
    margin_flag = "∅" if margin is None else ("✓" if margin else "✗")

    # Settle summary
    settled = [r for r in records if "settle" in r]
    hits = sum(1 for r in settled if r["settle"] == "hit")
    falses = sum(1 for r in settled if r["settle"] == "false")
    settle_str = f"對帳: {hits}hit/{falses}false"

    status_line = (
        f"geo-composite {signal} | "
        f"強度: reg{reg} rates{rates} oil{oil} | "
        f"脆弱: iv{iv} foreign{foreign} margin{margin_flag} | "
        f"{settle_str}"
    )

    if signal == "紅":
        status_line = f"🚨 PAPER-TRADE 警報(非行動建議) {status_line}"

    return status_line


# ══════════════════════════════════════════════════════════════════════════════
# Latest z-value helper
# ══════════════════════════════════════════════════════════════════════════════


def _latest_z(z_series: pd.Series) -> float | None:
    """Return the most recent non-NaN value of a z-series, or None."""
    if z_series is None or z_series.empty:
        return None
    valid = z_series.dropna()
    if valid.empty:
        return None
    return float(valid.iloc[-1])


# ══════════════════════════════════════════════════════════════════════════════
# Main orchestrator
# ══════════════════════════════════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="地緣複合 paper-trade 儀表")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print only — no state write, no inbox push")
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today)")
    args = ap.parse_args(argv)

    asof = (
        dt.date.fromisoformat(args.as_of) if args.as_of
        else dt.date.today()
    )
    print(f"[info] geo-composite as_of={asof}", file=sys.stderr)

    # 1. Build index
    print("[info] loading closes & building index …", file=sys.stderr)
    closes = load_daily_closes(set(CORE) | set(CANDIDATES))
    comps, weights = select_components(closes)
    index_s = build_index(closes, weights)
    idx0 = index_s.index[0]
    idx1 = index_s.index[-1]
    d0 = idx0.date() if hasattr(idx0, "date") else idx0
    d1 = idx1.date() if hasattr(idx1, "date") else idx1
    print(f"[info] index built: {len(index_s)} days, {d0} → {d1}", file=sys.stderr)

    # 2. Build indicator zoo
    print("[info] building indicator zoo …", file=sys.stderr)
    zoo = build_indicator_zoo(comps, index_s)

    # 3. Extract latest z values for strength axis
    z_vals: dict[str, float | None] = {name: _latest_z(s) for name, s in zoo.items()}

    strength = evaluate_strength(z_vals)
    print(f"[info] strength: {strength}", file=sys.stderr)

    # 4. Fragility inputs — IV / margin
    print("[info] loading fragility data …", file=sys.stderr)
    term_slope_latest, vrp_series, _skew = load_iv(asof)
    iv_inverted = term_slope_latest is not None and term_slope_latest > 0
    vrp_neg = (
        not vrp_series.empty and float(vrp_series.dropna().iloc[-1]) < 0
        if vrp_series is not None and not vrp_series.empty else False
    )

    margin_series = load_margin(asof)
    margin_result = score_margin(margin_series)
    margin_score_val = margin_result["score"] if margin_result is not None else None

    # Foreign z from zoo
    foreign_z = z_vals.get("foreign_sell")

    fragility = evaluate_fragility(
        iv_inverted=iv_inverted,
        vrp_neg=vrp_neg,
        foreign_z=foreign_z,
        margin_score=margin_score_val,
    )
    print(f"[info] fragility: {fragility}", file=sys.stderr)

    # 5. Traffic light
    signal = light(strength, fragility)
    print(f"[info] signal: {signal}", file=sys.stderr)

    # 6. Build new record
    new_record: dict[str, Any] = {
        "date": asof.isoformat(),
        "light": signal,
        "strength": {
            "regulation": strength["regulation"],
            "rates": strength["rates"],
            "oil": strength["oil"],
            "triggered": strength["triggered"],
        },
        "fragility": {
            "iv": fragility["iv"],
            "foreign": fragility["foreign"],
            "margin": fragility["margin"],
            "triggered": fragility["triggered"],
        },
        "z_detail": {
            k: (round(v, 4) if v is not None else None)
            for k, v in strength["detail"].items()
        },
        "fragility_detail": {
            "iv_inverted": iv_inverted,
            "vrp_neg": vrp_neg,
            "foreign_z": round(foreign_z, 4) if foreign_z is not None else None,
            "margin_score": margin_score_val,
            "term_slope": round(term_slope_latest, 4) if term_slope_latest is not None else None,
        },
    }

    # 7. State upsert + settle
    if args.dry_run:
        records = _load_state(STATE_PATH)
        _upsert_record(records, new_record)
        records = settle_alerts(records, index_s, asof)
    else:
        records = _load_state(STATE_PATH)
        _upsert_record(records, new_record)
        records = settle_alerts(records, index_s, asof)
        _save_state(STATE_PATH, records)
        print(f"[info] state written to {STATE_PATH}", file=sys.stderr)

    # 8. Build and print message
    msg = _build_message(asof, signal, strength, fragility, records)
    print("─" * 70)
    print(msg)
    print("─" * 70)

    # 9. Inbox push
    if args.dry_run:
        print("[info] dry-run: skipping inbox push", file=sys.stderr)
        return 0

    _push_inbox(msg, asof)
    return 0


if __name__ == "__main__":
    sys.exit(main())
