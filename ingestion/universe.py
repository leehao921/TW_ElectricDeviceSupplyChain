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
    "Software - Infrastructure",
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


def all_tickers(repo_root: Optional[Path] = None) -> set[str]:
    """Alias of :func:`electronics_tickers`. Used by per-ticker collectors."""
    return electronics_tickers(repo_root)


def ticker_name(ticker: str, repo_root: Optional[Path] = None) -> Optional[str]:
    """Return the Chinese company name for ``ticker``, or None if unknown."""
    key = str(repo_root) if repo_root else ""
    return _scan_cached(key).get(ticker)


# Suffixes Taiwan ADRs/foreign-listed names carry that articles often drop.
# "臻鼎-KY" appears in news as both "臻鼎-KY" and bare "臻鼎"; matching both
# closes the largest single coverage gap in the news ingest pipeline.
_NAME_SUFFIXES = ("-KY", "-DR", "*-KY", "-KY*")


def name_to_ticker(repo_root: Optional[Path] = None) -> dict[str, str]:
    """Return ``{company_name: ticker}`` including suffix-stripped aliases.

    e.g. for ``4985_臻鼎-KY.md`` the map contains both ``臻鼎-KY → 4985``
    and ``臻鼎 → 4985``. Used by the NER pass so news articles that name
    the company without printing the ticker still get tagged.

    When two tickers would collide on the same alias (e.g. two ``臻鼎``
    files exist), first-seen wins to avoid silent overwrites — but the
    full unstripped name always takes priority over a stripped alias.
    """
    key = str(repo_root) if repo_root else ""
    out: dict[str, str] = {}
    for ticker, name in _scan_cached(key).items():
        out[name] = ticker
    for ticker, name in _scan_cached(key).items():
        for suf in _NAME_SUFFIXES:
            if name.endswith(suf):
                bare = name[: -len(suf)]
                if bare and bare not in out:
                    out[bare] = ticker
    return out
