"""Sector heatmap of quant screen passers.

Reads the CSV produced by ``screen_quant.py`` and groups passers by
``industry``, computing median YoY/OpM/PE and the highest-scoring ticker
per sector. Emits a markdown table to stdout (or to ``--out``).

Usage:
    python scripts/sector_heatmap.py --csv analysis/reports/2026-05-12_quant_screen.csv
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def median_or_dash(xs: list[float]) -> str:
    xs = [x for x in xs if x is not None]
    if not xs:
        return "—"
    return f"{statistics.median(xs):.1f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--csv", required=True, help="Screen CSV path")
    p.add_argument("--out", default=None, help="Markdown output (default stdout)")
    args = p.parse_args()

    rows = list(csv.DictReader(open(args.csv)))
    by_industry: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_industry[r["industry"] or "(missing)"].append(r)

    def fnum(s: str) -> float | None:
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    table_rows: list[tuple] = []
    for industry, items in by_industry.items():
        yoys = [fnum(r["rev_yoy_%"]) for r in items]
        opms = [fnum(r["op_margin_%"]) for r in items]
        pes  = [fnum(r["pe"]) for r in items]
        pbs  = [fnum(r["pb"]) for r in items]
        scores = [fnum(r["score"]) for r in items]
        top = max(items, key=lambda r: fnum(r["score"]) or 0)
        table_rows.append((
            industry, len(items),
            median_or_dash(yoys),
            median_or_dash(opms),
            median_or_dash(pes),
            median_or_dash(pbs),
            f"{top['ticker']} {top['name']} (s={top['score']})",
            max(scores) if scores else 0,
        ))

    table_rows.sort(key=lambda r: -(r[7] or 0))

    out = open(args.out, "w") if args.out else sys.stdout
    out.write(f"# 產業熱力圖 — 量化篩通過 {len(rows)} 檔\n\n")
    out.write("依產業中位數排序(以該產業最高分標的的 score 為排序鍵)\n\n")
    out.write("| 產業 | 通過數 | 中位 YoY% | 中位 OpM% | 中位 P/E | 中位 P/B | 該產業最高分 |\n")
    out.write("|---|---:|---:|---:|---:|---:|---|\n")
    for industry, n, yoy, opm, pe, pb, top, _ in table_rows:
        out.write(f"| {industry} | {n} | {yoy} | {opm} | {pe} | {pb} | {top} |\n")
    if args.out:
        out.close()
        print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
