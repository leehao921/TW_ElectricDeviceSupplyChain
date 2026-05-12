"""Quant screen across all Pilot_Reports.

Parses each report's 估值指標 + 年度/季度 financial tables, applies hard
filters (revenue YoY growth, positive OCF/NI, valuation cap, market-cap
floor), scores survivors, and emits a ranked CSV.

Usage:
    python scripts/screen_quant.py [--out PATH] [--top N]

Filters (hard cutoffs):
    - YoY revenue growth >= 5%
    - Operating cash flow > 0
    - Net income > 0
    - P/E < 35 (when reported)
    - Operating margin > 3%
    - Market cap >= 1,500 百萬台幣

Score weights (composite, higher is better):
    - YoY rev growth  ≤ 20 pts (yoy/5, capped)
    - 3yr rev CAGR    ≤ 15 pts (cagr/2)
    - QoQ rev growth  ≤ 15 pts (yoyq/4)
    - OCF positive    +10 pts
    - Op margin       ≤ 15 pts (opm/2 when opm>5)
    - Net margin      ≤ 10 pts (nm/2 when nm>0)
    - P/E in 5~25     +10, in 25~40 +3
    - P/B < 3         +5
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "Pilot_Reports"


def _num(s: str) -> float | None:
    s = s.replace(",", "").strip()
    if s in ("", "N/A", "nan", "NaN", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_md_table(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if all(set(c) <= set("-:") for c in cells):
            continue
        rows.append(cells)
    return rows


def parse_report(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^#\s*(\d{4,5})\s*-\s*\[?\[?([^\]\n]+)\]?\]?", text, re.M)
    if not m:
        return None
    ticker, name = m.group(1), m.group(2).strip()

    sector = re.search(r"\*\*板塊:\*\*\s*(\S+)", text)
    industry = re.search(r"\*\*產業:\*\*\s*([^\n]+)", text)
    mcap = re.search(r"\*\*市值:\*\*\s*([\d,\.]+)", text)
    price = re.search(r"股價\s*\$([\d,\.]+)", text)

    val_block = re.search(r"###\s*估值指標.*?\n(.*?)\n###", text, re.S)
    pe = pb = ps = None
    if val_block:
        for ln in val_block.group(1).splitlines():
            if "|" not in ln or ln.strip().startswith("|--") or "P/E" in ln:
                continue
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) >= 5 and not cells[0].startswith("-"):
                pe = _num(cells[0])
                ps = _num(cells[2])
                pb = _num(cells[3])
                break

    ann_block = re.search(r"年度關鍵財務數據.*?\n(.*?)(?:\n###|\Z)", text, re.S)
    annual: dict[str, dict[str, float | None]] = {}
    if ann_block:
        rows = _parse_md_table(ann_block.group(1).splitlines())
        if rows:
            dates = rows[0][1:]
            for r in rows[1:]:
                label = r[0].strip()
                for i, d in enumerate(dates, 1):
                    if i < len(r):
                        annual.setdefault(label, {})[d] = _num(r[i])

    q_block = re.search(r"季度關鍵財務數據.*?\n(.*?)(?:\n##|\Z)", text, re.S)
    quarterly: dict[str, dict[str, float | None]] = {}
    if q_block:
        rows = _parse_md_table(q_block.group(1).splitlines())
        if rows:
            dates = rows[0][1:]
            for r in rows[1:]:
                label = r[0].strip()
                for i, d in enumerate(dates, 1):
                    if i < len(r):
                        quarterly.setdefault(label, {})[d] = _num(r[i])

    return {
        "ticker": ticker,
        "name": name,
        "sector": sector.group(1) if sector else "",
        "industry": industry.group(1).strip() if industry else "",
        "market_cap": _num(mcap.group(1)) if mcap else None,
        "price": _num(price.group(1)) if price else None,
        "pe": pe, "pb": pb, "ps": ps,
        "annual": annual,
        "quarterly": quarterly,
    }


def compute_metrics(r: dict) -> dict | None:
    ann = r["annual"]; q = r["quarterly"]
    rev = ann.get("Revenue", {})
    dates = sorted(rev.keys(), reverse=True)
    if len(dates) < 2 or rev[dates[0]] is None or rev[dates[1]] is None or rev[dates[1]] == 0:
        return None
    yoy = (rev[dates[0]] - rev[dates[1]]) / abs(rev[dates[1]]) * 100

    cagr = None
    if len(dates) >= 3 and rev[dates[2]] and rev[dates[2]] > 0:
        cagr = ((rev[dates[0]] / rev[dates[2]]) ** 0.5 - 1) * 100

    ocf = ann.get("Op Cash Flow", {}).get(dates[0])
    ni = ann.get("Net Income", {}).get(dates[0])
    gm = ann.get("Gross Margin (%)", {}).get(dates[0])
    om = ann.get("Operating Margin (%)", {}).get(dates[0])
    nm = ann.get("Net Margin (%)", {}).get(dates[0])

    qrev = q.get("Revenue", {})
    qdates = sorted(qrev.keys(), reverse=True)
    qoq = yoy_q = None
    if len(qdates) >= 2 and qrev[qdates[0]] and qrev[qdates[1]] and qrev[qdates[1]] != 0:
        qoq = (qrev[qdates[0]] - qrev[qdates[1]]) / abs(qrev[qdates[1]]) * 100
    if len(qdates) >= 4 and qrev[qdates[0]] and qrev[qdates[3]] and qrev[qdates[3]] != 0:
        yoy_q = (qrev[qdates[0]] - qrev[qdates[3]]) / abs(qrev[qdates[3]]) * 100

    return {
        "rev_yoy": yoy, "rev_cagr_3y": cagr, "rev_qoq": qoq, "rev_yoy_q": yoy_q,
        "ocf": ocf, "ocf_positive": ocf is not None and ocf > 0,
        "net_income": ni, "gross_margin": gm, "op_margin": om, "net_margin": nm,
        "latest_period": dates[0], "latest_q": qdates[0] if qdates else None,
    }


def score(r: dict) -> float:
    s = 0.0
    if (yoy := r.get("rev_yoy")) is not None and yoy >= 10:
        s += min(yoy / 5, 20)
    if (cagr := r.get("rev_cagr_3y")) is not None and cagr >= 5:
        s += min(cagr / 2, 15)
    if (qoy := r.get("rev_yoy_q")) is not None and qoy >= 5:
        s += min(qoy / 4, 15)
    if r.get("ocf_positive"):
        s += 10
    if (om := r.get("op_margin")) and om > 5:
        s += min(om / 2, 15)
    if (nm := r.get("net_margin")) and nm > 0:
        s += min(nm / 2, 10)
    pe = r.get("pe"); pb = r.get("pb")
    if pe is not None and 5 < pe < 25:
        s += 10
    elif pe is not None and 25 <= pe < 40:
        s += 3
    if pb is not None and pb < 3:
        s += 5
    return s


def passes_filter(r: dict) -> bool:
    if not r.get("ocf_positive"):
        return False
    if r.get("rev_yoy") is None or r["rev_yoy"] < 5:
        return False
    if r.get("net_income") is None or r["net_income"] <= 0:
        return False
    pe = r.get("pe")
    if pe is not None and pe > 35:
        return False
    if r.get("op_margin") is None or r["op_margin"] < 3:
        return False
    if r.get("market_cap") is None or r["market_cap"] < 1500:
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=None, help="CSV output path (default: stdout)")
    p.add_argument("--top", type=int, default=0, help="Limit to top N rows (0 = all)")
    args = p.parse_args()

    records = []
    for md_path in ROOT.rglob("*.md"):
        if md_path.name == "README.md":
            continue
        try:
            rec = parse_report(md_path)
            if not rec:
                continue
            m = compute_metrics(rec)
            if m:
                rec.update(m)
                records.append(rec)
        except Exception as e:
            print(f"ERR {md_path.name}: {e}", file=sys.stderr)

    print(f"PARSED {len(records)} tickers", file=sys.stderr)

    candidates = [r for r in records if passes_filter(r)]
    for r in candidates:
        r["score"] = score(r)
    candidates.sort(key=lambda x: -x["score"])
    print(f"PASSED filter: {len(candidates)}", file=sys.stderr)

    out = open(args.out, "w") if args.out else sys.stdout
    writer = csv.writer(out)
    writer.writerow([
        "rank", "ticker", "name", "industry", "mcap_M", "price",
        "rev_yoy_%", "rev_qoq_%", "rev_yoy_q_%", "cagr3_%",
        "op_margin_%", "net_margin_%", "ocf_M", "pe", "pb", "score", "latest_q",
    ])
    rows = candidates[:args.top] if args.top else candidates
    for i, r in enumerate(rows, 1):
        writer.writerow([
            i, r["ticker"], r["name"], r["industry"],
            f"{r['market_cap']:.0f}" if r.get("market_cap") else "",
            f"{r['price']:.1f}" if r.get("price") else "",
            f"{r['rev_yoy']:.1f}" if r.get("rev_yoy") is not None else "",
            f"{r['rev_qoq']:.1f}" if r.get("rev_qoq") is not None else "",
            f"{r['rev_yoy_q']:.1f}" if r.get("rev_yoy_q") is not None else "",
            f"{r['rev_cagr_3y']:.1f}" if r.get("rev_cagr_3y") is not None else "",
            f"{r['op_margin']:.1f}" if r.get("op_margin") is not None else "",
            f"{r['net_margin']:.1f}" if r.get("net_margin") is not None else "",
            f"{r['ocf']:.0f}" if r.get("ocf") is not None else "",
            f"{r['pe']:.1f}" if r.get("pe") is not None else "",
            f"{r['pb']:.2f}" if r.get("pb") is not None else "",
            f"{r['score']:.1f}",
            r.get("latest_q", ""),
        ])
    if args.out:
        out.close()
        print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
