"""Report-layer tools: read Markdown from Pilot_Reports/ and themes/."""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(os.environ.get(
    "REPO_ROOT",
    Path(__file__).resolve().parents[2],
))
REPORTS_DIR = REPO_ROOT / "Pilot_Reports"
THEMES_DIR = REPO_ROOT / "themes"

_FILENAME_RE = re.compile(r"^(\d{4})_(.+)\.md$")
_THEME_TICKER_RE = re.compile(r"\*\*(\d{4})\s+([^*]+?)\*\*")
_SECTION_HEADER_RE = re.compile(r"^##\s+(上游|中游|下游|相關公司)")


def iter_report_files(sector: str | None = None):
    """Yield (ticker, name, sector_folder, path) for every report file."""
    if not REPORTS_DIR.exists():
        return
    sector_lc = sector.lower() if sector else None
    for sector_dir in sorted(REPORTS_DIR.iterdir()):
        if not sector_dir.is_dir():
            continue
        if sector_lc and sector_dir.name.lower() != sector_lc:
            continue
        for path in sorted(sector_dir.glob("*.md")):
            m = _FILENAME_RE.match(path.name)
            if not m:
                continue
            yield m.group(1), m.group(2), sector_dir.name, path


def _theme_path(theme: str) -> Path:
    """Resolve a theme name to its .md file (tolerant of spaces/underscores)."""
    candidates = [theme, theme.replace(" ", "_"), theme.replace("_", " ")]
    for name in candidates:
        p = THEMES_DIR / f"{name}.md"
        if p.exists():
            return p
    return THEMES_DIR / f"{theme}.md"


def _theme_tickers(theme: str) -> set[str]:
    """Extract all tickers mentioned in a theme file."""
    p = _theme_path(theme)
    if not p.exists():
        return set()
    text = p.read_text(encoding="utf-8")
    return {m.group(1) for m in _THEME_TICKER_RE.finditer(text)}


async def list_tickers(
    sector: str | None = None,
    theme: str | None = None,
) -> list[dict]:
    """Return ticker metadata, optionally filtered by sector folder or theme file."""
    theme_filter = _theme_tickers(theme) if theme else None
    results = []
    for ticker, name, sector_folder, _ in iter_report_files(sector):
        if theme_filter is not None and ticker not in theme_filter:
            continue
        results.append({"ticker": ticker, "name": name, "sector": sector_folder})
    return results


async def get_report(ticker: str) -> str:
    """Return the full Markdown content of the report for `ticker`."""
    for t, _, _, path in iter_report_files():
        if t == ticker:
            return path.read_text(encoding="utf-8")
    return f"Error: no report found for ticker {ticker}"


async def get_theme_cohort(theme: str) -> list[dict]:
    """Parse a themes/{theme}.md file and return tickers grouped by section."""
    p = _theme_path(theme)
    if not p.exists():
        return [{"error": f"Theme file not found: {p.name}"}]

    results = []
    current_section: str | None = None
    for line in p.read_text(encoding="utf-8").splitlines():
        section_match = _SECTION_HEADER_RE.match(line)
        if section_match:
            current_section = section_match.group(1)
            continue
        if current_section is None:
            continue
        ticker_match = _THEME_TICKER_RE.search(line)
        if not ticker_match:
            continue
        industry_match = re.search(r"\(([^)]+)\)\s*$", line)
        results.append({
            "ticker": ticker_match.group(1),
            "name": ticker_match.group(2).strip(),
            "segment": current_section,
            "industry": industry_match.group(1) if industry_match else None,
        })
    return results
