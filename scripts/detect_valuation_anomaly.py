"""Detect anomalous day-over-day valuation movements.

Reads today's and the prior trading day's snapshots written by
update_valuation.py and emits one Anomaly per (ticker, rule) violation.
HIGH severity events optionally push to the claude:inbox Redis stream so
the next session boot surfaces them.

See docs/plans/2026-05-23-valuation-anomaly-detection.md for rule
definitions, thresholds, and motivation.

Usage:
    python3 scripts/detect_valuation_anomaly.py
    python3 scripts/detect_valuation_anomaly.py --date 2026-05-23
    python3 scripts/detect_valuation_anomaly.py --json
    python3 scripts/detect_valuation_anomaly.py --notify-inbox
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from valuation_snapshot import latest_snapshot_before, load_snapshot

# ---------------------------------------------------------------------------
# Rule thresholds (kept as module-level constants for easy tuning)
# ---------------------------------------------------------------------------

R1_PRICE_PCT = 7.0
R2_PE_PCT = 20.0
R2_PE_ABS = 3.0
R3_PB_PCT = 25.0
R3_PB_ABS = 0.5
R4_MKTCAP_PCT = 10.0
R4_DIVERGENCE_PP = 5.0
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}


@dataclass
class Anomaly:
    ticker: str
    rule: str
    severity: str
    message: str
    yday: dict = field(default_factory=dict)
    today: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "yday": self.yday,
            "today": self.today,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pct_change(yday_val, today_val) -> float | None:
    """Percent change yday -> today. None if either side is missing or yday is 0."""
    if yday_val in (None, 0) or today_val is None:
        return None
    try:
        return (today_val - yday_val) / abs(yday_val) * 100.0
    except (TypeError, ZeroDivisionError):
        return None


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def rule_price_jump(ticker: str, yday: dict, today: dict) -> Anomaly | None:
    pct = _pct_change(yday.get("price"), today.get("price"))
    if pct is None or abs(pct) <= R1_PRICE_PCT:
        return None
    return Anomaly(
        ticker=ticker, rule="R1", severity="HIGH",
        message=f"price moved {pct:+.2f}% "
                f"({yday.get('price')} -> {today.get('price')})",
        yday={"price": yday.get("price")},
        today={"price": today.get("price")},
    )


def rule_pe_jump(ticker: str, yday: dict, today: dict) -> Anomaly | None:
    y, t = yday.get("pe"), today.get("pe")
    if y in (None, 0) or t is None:
        return None
    pct = _pct_change(y, t)
    abs_delta = abs(t - y)
    if pct is None or abs(pct) <= R2_PE_PCT or abs_delta <= R2_PE_ABS:
        return None
    return Anomaly(
        ticker=ticker, rule="R2", severity="MEDIUM",
        message=f"P/E {pct:+.2f}% ({y} -> {t}, abs {abs_delta:+.2f})",
        yday={"pe": y}, today={"pe": t},
    )


def rule_pb_jump(ticker: str, yday: dict, today: dict) -> Anomaly | None:
    y, t = yday.get("pb"), today.get("pb")
    if y in (None, 0) or t is None:
        return None
    pct = _pct_change(y, t)
    abs_delta = abs(t - y)
    if pct is None or abs(pct) <= R3_PB_PCT or abs_delta <= R3_PB_ABS:
        return None
    return Anomaly(
        ticker=ticker, rule="R3", severity="MEDIUM",
        message=f"P/B {pct:+.2f}% ({y} -> {t}, abs {abs_delta:+.2f})",
        yday={"pb": y}, today={"pb": t},
    )


def rule_mktcap_divergence(ticker: str, yday: dict, today: dict) -> Anomaly | None:
    # Note: TWSE/TPEX bulk feeds do not expose market_cap_m, so this rule only
    # fires for the ~60 tickers/week sourced via yfinance fallback. That is
    # acceptable: capital actions for major TWSE/TPEX tickers will still trip
    # R1 (price jump) when shares-outstanding changes drive a price open gap.
    mc_pct = _pct_change(yday.get("market_cap_m"), today.get("market_cap_m"))
    if mc_pct is None or abs(mc_pct) <= R4_MKTCAP_PCT:
        return None
    px_pct = _pct_change(yday.get("price"), today.get("price"))
    # If we have no price reference, fall back to flat 0 — pure mktcap moves
    # without price moves are exactly what we want to flag.
    px_pct_eff = 0.0 if px_pct is None else px_pct
    divergence_pp = abs(mc_pct - px_pct_eff)
    if divergence_pp <= R4_DIVERGENCE_PP:
        return None
    return Anomaly(
        ticker=ticker, rule="R4", severity="HIGH",
        message=f"market cap {mc_pct:+.2f}% but price {px_pct_eff:+.2f}% "
                f"(divergence {divergence_pp:.2f}pp) — capital action suspected",
        yday={"market_cap_m": yday.get("market_cap_m"), "price": yday.get("price")},
        today={"market_cap_m": today.get("market_cap_m"), "price": today.get("price")},
    )


def rule_data_missing(ticker: str, yday: dict, today: dict) -> Anomaly | None:
    yday_has = any(yday.get(k) is not None for k in ("price", "pe", "pb"))
    today_has = any(today.get(k) is not None for k in ("price", "pe", "pb"))
    if yday_has and not today_has:
        return Anomaly(
            ticker=ticker, rule="R5", severity="HIGH",
            message="all valuation fields missing today (suspension/delist?)",
            yday={k: yday.get(k) for k in ("price", "pe", "pb")},
            today={k: today.get(k) for k in ("price", "pe", "pb")},
        )
    return None


def rule_ex_dividend(ticker: str, yday: dict, today: dict) -> Anomaly | None:
    y, t = yday.get("yield_pct"), today.get("yield_pct")
    if y is None or t is None:
        return None
    if y > 0 and t == 0:
        return Anomaly(
            ticker=ticker, rule="R6", severity="INFO",
            message=f"yield {y}% -> 0% (ex-dividend)",
            yday={"yield_pct": y}, today={"yield_pct": t},
        )
    return None


ALL_RULES = (
    rule_price_jump,
    rule_pe_jump,
    rule_pb_jump,
    rule_mktcap_divergence,
    rule_data_missing,
    rule_ex_dividend,
)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def detect_anomalies(yday_snap: dict, today_snap: dict) -> list[Anomaly]:
    yday_tickers = yday_snap.get("tickers", {})
    today_tickers = today_snap.get("tickers", {})
    common = set(yday_tickers) & set(today_tickers)
    out: list[Anomaly] = []
    for ticker in sorted(common):
        y = yday_tickers[ticker]
        t = today_tickers[ticker]
        for rule in ALL_RULES:
            anomaly = rule(ticker, y, t)
            if anomaly is not None:
                out.append(anomaly)
    out.sort(key=lambda a: (SEVERITY_ORDER[a.severity], a.ticker, a.rule))
    return out


def format_text(anomalies: list[Anomaly]) -> str:
    if not anomalies:
        return "no anomaly detected (0 events)"
    lines: list[str] = []
    last_sev = None
    for a in anomalies:
        if a.severity != last_sev:
            lines.append(f"\n=== {a.severity} ===")
            last_sev = a.severity
        lines.append(f"  [{a.rule}] {a.ticker}: {a.message}")
    return "\n".join(lines).lstrip()


def notify_inbox(anomalies: list[Anomaly]) -> int:
    """Push HIGH-severity anomalies to claude:inbox via scripts/claude_msg.py."""
    msg_script = Path(__file__).resolve().parent / "claude_msg.py"
    sent = 0
    for a in anomalies:
        if a.severity != "HIGH":
            continue
        body = f"[{a.rule}] {a.ticker}: {a.message}"
        try:
            subprocess.run(
                ["python3", str(msg_script), "send", "valuation_anomaly", body,
                 "--tags", "valuation", "anomaly", a.rule, a.ticker],
                check=True,
            )
            sent += 1
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  [WARN] failed to send {a.ticker}/{a.rule}: {e}",
                  file=sys.stderr)
    return sent


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect valuation anomalies day-over-day")
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="Today's snapshot date (YYYY-MM-DD), default = today")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON instead of text")
    parser.add_argument("--notify-inbox", action="store_true",
                        help="Push HIGH-severity anomalies to claude:inbox")
    args = parser.parse_args(argv)

    today_snap = load_snapshot(args.date)
    if today_snap is None:
        print(f"ERROR: no snapshot for {args.date}", file=sys.stderr)
        return 2

    yday_snap = latest_snapshot_before(args.date)
    if yday_snap is None:
        print(f"WARN: no prior snapshot before {args.date}; nothing to compare",
              file=sys.stderr)
        return 0

    anomalies = detect_anomalies(yday_snap, today_snap)

    if args.json:
        json.dump([a.to_dict() for a in anomalies], sys.stdout,
                  ensure_ascii=False, indent=2)
        print()
    else:
        print(f"Comparing {yday_snap['snapshot_date']} -> {today_snap['snapshot_date']}")
        print(f"({len(anomalies)} anomaly events)\n")
        print(format_text(anomalies))

    if args.notify_inbox:
        sent = notify_inbox(anomalies)
        print(f"\nPushed {sent} HIGH-severity events to claude:inbox", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
