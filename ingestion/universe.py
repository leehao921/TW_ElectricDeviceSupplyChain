"""Electronics ticker universe extracted from Pilot_Reports filenames.

Each report is stored at ``Pilot_Reports/<Sector>/<Ticker>_<ChineseName>.md``.
We treat the filename as ground truth (see project rule #2) and derive both
the ticker set and the ticker→name map from it.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .config import settings

# Sectors that make up the Taiwan electronics supply chain. Sum of file counts
# across these folders is ~923, matching the project's ~926 target.
ELECTRONICS_SECTORS = frozenset({
    "Semiconductors",
    "Semiconductor Equipment & Materials",
    "Electronic Components",
    "Computer Hardware",
    "Communication Equipment",
    "Consumer Electronics",
    "Electronics & Computer Distribution",
    "Electronic Gaming & Multimedia",
    "Electrical Equipment & Parts",
    "Solar",
    "Specialty Industrial Machinery",
    "Scientific & Technical Instruments",
})

_FILENAME_RE = re.compile(r"^(\d{4})_(.+)\.md$")


def _reports_dir(repo_root: Optional[Path]) -> Path:
    return (repo_root or settings.repo_root) / "Pilot_Reports"


def _iter_electronics_files(repo_root: Optional[Path]):
    base = _reports_dir(repo_root)
    for sector in ELECTRONICS_SECTORS:
        sector_dir = base / sector
        if not sector_dir.is_dir():
            continue
        for path in sector_dir.iterdir():
            if path.suffix == ".md":
                yield path


@lru_cache(maxsize=4)
def _scan_cached(root_str: str) -> dict[str, str]:
    root = Path(root_str) if root_str else None
    result: dict[str, str] = {}
    for path in _iter_electronics_files(root):
        match = _FILENAME_RE.match(path.name)
        if match:
            ticker, name = match.group(1), match.group(2)
            # First-write-wins if a ticker somehow appears twice.
            result.setdefault(ticker, name)
    return result


def electronics_tickers(repo_root: Optional[Path] = None) -> set[str]:
    """Return the set of 4-digit electronics tickers (~926 items)."""
    key = str(repo_root) if repo_root else ""
    return set(_scan_cached(key).keys())


def ticker_to_name(repo_root: Optional[Path] = None) -> dict[str, str]:
    """Return ``{"2330": "台積電", ...}`` for every electronics ticker."""
    key = str(repo_root) if repo_root else ""
    return dict(_scan_cached(key))
