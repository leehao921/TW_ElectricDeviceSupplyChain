"""Bootstrap ingester: convert Pilot_Reports Markdown into Graphiti episodes.

Scans ``Pilot_Reports/<Sector>/<Ticker>_<Name>.md``, parses the
``## 供應鏈位置`` and ``## 主要客戶及供應商`` sections into a plain-text
episode body, and calls ``graphiti.add_episode(...)``.

The parser is section-and-bullet aware: it extracts every bullet line and
flattens "上游", "中游", "下游", "主要客戶", "主要供應商" into lists with
minimal assumptions. Whatever cannot be confidently classified falls into a
generic "other" bucket so no information is silently dropped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "Pilot_Reports"

FILENAME_RE = re.compile(r"^(\d{4})_(.+)\.md$")
_LABEL_RE = re.compile(r"^\*\*([^*]+)\*\*\s*:?\s*$")
_INLINE_LABEL_RE = re.compile(r"^-\s*\*\*([^*]+)\*\*\s*:?\s*(.*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")

UPSTREAM_KEYS = ("上游",)
MIDSTREAM_KEYS = ("中游",)
DOWNSTREAM_KEYS = ("下游",)  # "下游應用" also matches via substring
CUSTOMER_KEYS = ("主要客戶", "客戶")
SUPPLIER_KEYS = ("主要供應商", "供應商")


@dataclass
class ParsedReport:
    ticker: str
    company_name: str
    sector: str
    upstream: list[str] = field(default_factory=list)
    midstream: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)
    customers: list[str] = field(default_factory=list)
    suppliers: list[str] = field(default_factory=list)
    other_supply_chain: list[str] = field(default_factory=list)

    def to_episode_body(self) -> str:
        def fmt(items: list[str]) -> str:
            return "; ".join(items) if items else "(not specified)"

        lines = [
            f"{self.ticker} ({self.company_name}) supply chain and customer/supplier relationships:",
            f"Upstream: {fmt(self.upstream)}",
            f"Midstream: {fmt(self.midstream)}",
            f"Downstream: {fmt(self.downstream)}",
            f"Major customers: {fmt(self.customers)}",
            f"Major suppliers: {fmt(self.suppliers)}",
        ]
        if self.other_supply_chain:
            lines.append(f"Other supply-chain notes: {fmt(self.other_supply_chain)}")
        return "\n".join(lines)


def _iter_report_paths(sector: str | None = None) -> Iterable[Path]:
    if not REPORTS_DIR.is_dir():
        return []
    if sector is not None:
        sector_dir = REPORTS_DIR / sector
        if not sector_dir.is_dir():
            return []
        return sorted(sector_dir.glob("*.md"))
    return sorted(REPORTS_DIR.glob("*/*.md"))


def _split_sections(markdown: str) -> dict[str, str]:
    """Split a Markdown document by H2 headings into name -> body text."""
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip()
    return sections


def _bullets(section_body: str) -> list[tuple[str | None, str]]:
    """Yield (sub_label, bullet_text) for each bullet.

    A bullet's sub_label is the nearest preceding bold prefix like
    ``**上游 (原料):**`` so callers can route bullets to the right bucket.
    """
    results: list[tuple[str | None, str]] = []
    current_label: str | None = None

    for raw in section_body.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _LABEL_RE.match(line)
        if m:
            current_label = m.group(1).strip()
            continue
        if line.startswith("### "):
            current_label = line[4:].strip()
            continue
        m = _INLINE_LABEL_RE.match(line)
        if m:
            sub_label = m.group(1).strip()
            rest = m.group(2).strip()
            effective_label = sub_label if not current_label else f"{current_label} / {sub_label}"
            if rest:
                results.append((effective_label, rest))
            else:
                current_label = sub_label
            continue
        m = _BULLET_RE.match(line)
        if m:
            results.append((current_label, m.group(1).strip()))
    return results


def _classify(label: str | None, keys: tuple[str, ...]) -> bool:
    if not label:
        return False
    return any(k in label for k in keys)


def parse_report(path: Path) -> ParsedReport:
    """Read one report file and return a ParsedReport."""
    filename = path.name
    m = FILENAME_RE.match(filename)
    if not m:
        raise ValueError(f"Filename does not match XXXX_name.md pattern: {filename}")
    ticker, name = m.group(1), m.group(2)
    sector = path.parent.name

    text = path.read_text(encoding="utf-8")
    sections = _split_sections(text)

    report = ParsedReport(ticker=ticker, company_name=name, sector=sector)

    supply_section = sections.get("供應鏈位置", "")
    for label, bullet in _bullets(supply_section):
        if _classify(label, UPSTREAM_KEYS):
            report.upstream.append(bullet)
        elif _classify(label, MIDSTREAM_KEYS):
            report.midstream.append(bullet)
        elif _classify(label, DOWNSTREAM_KEYS):
            report.downstream.append(bullet)
        else:
            report.other_supply_chain.append(bullet if not label else f"{label}: {bullet}")

    customer_section = sections.get("主要客戶及供應商", "")
    for label, bullet in _bullets(customer_section):
        if _classify(label, CUSTOMER_KEYS):
            report.customers.append(bullet)
        elif _classify(label, SUPPLIER_KEYS):
            report.suppliers.append(bullet)
        else:
            # Fall back: bullets with no label under this section are ambiguous;
            # preserve them in customers to avoid silent loss.
            report.customers.append(bullet if not label else f"{label}: {bullet}")

    return report


async def ingest(reports: list[ParsedReport], dry_run: bool) -> None:
    if dry_run:
        for r in reports:
            print(json.dumps({
                "name": r.ticker,
                "sector": r.sector,
                "episode_body": r.to_episode_body(),
            }, ensure_ascii=False))
        return

    from graph.client import GROUP_ID, get_client  # local import so --dry-run works without deps
    from graphiti_core.nodes import EpisodeType

    client = await get_client()
    for r in reports:
        try:
            await client.add_episode(
                name=r.ticker,
                episode_body=r.to_episode_body(),
                source=EpisodeType.text,
                source_description="pilot_reports: Taiwan electronics supply chain research",
                reference_time=datetime.now(),
                group_id=GROUP_ID,
            )
            print(f"[ok] {r.ticker} {r.company_name}")
        except Exception as e:  # noqa: BLE001 — one failure shouldn't stop the batch
            print(f"[err] {r.ticker} {r.company_name}: {e}")


def collect_reports(sector: str | None, limit: int | None) -> list[ParsedReport]:
    paths = list(_iter_report_paths(sector))
    if limit is not None:
        paths = paths[:limit]
    parsed: list[ParsedReport] = []
    for p in paths:
        try:
            parsed.append(parse_report(p))
        except Exception as e:  # noqa: BLE001
            print(f"[skip] {p}: {e}")
    return parsed


def _main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Pilot_Reports into Graphiti")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N reports")
    parser.add_argument("--dry-run", action="store_true", help="Print episode payloads without calling Graphiti")
    parser.add_argument("--sector", type=str, default=None, help="Process one sector only (folder name under Pilot_Reports)")
    args = parser.parse_args()

    reports = collect_reports(args.sector, args.limit)
    if not reports:
        print("No reports matched.")
        return

    asyncio.run(ingest(reports, args.dry_run))


if __name__ == "__main__":
    _main()
