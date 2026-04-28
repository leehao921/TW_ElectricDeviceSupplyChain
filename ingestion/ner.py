"""Named-entity extraction over free text.

Pulls out 4-digit Taiwan stock tickers and known wikilink vocabulary terms.
Both lists preserve first-seen order and are de-duplicated.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .config import settings

_TICKER_RE = re.compile(r"\b\d{4}\b")
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _wikilinks_path(repo_root: Optional[Path]) -> Path:
    return (repo_root or settings.repo_root) / "WIKILINKS.md"


@lru_cache(maxsize=4)
def _load_vocab_cached(root_str: str) -> frozenset[str]:
    root = Path(root_str) if root_str else None
    path = _wikilinks_path(root)
    if not path.is_file():
        return frozenset()
    text = path.read_text(encoding="utf-8")
    return frozenset(_WIKILINK_RE.findall(text))


def load_wikilink_vocab(repo_root: Optional[Path] = None) -> set[str]:
    """Return the set of all wikilink terms found in ``WIKILINKS.md``."""
    key = str(repo_root) if repo_root else ""
    return set(_load_vocab_cached(key))


def _unique_in_order(items):
    seen: set = set()
    result: list = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


class NerResult(dict):
    """Mapping with ``tickers`` / ``wikilinks`` exposed as attributes too.

    Lets older call sites use ``result["tickers"]`` (test_shared.py) while
    new ones use ``result.tickers`` (test_rss.py, _rss_base.py).
    """

    @property
    def tickers(self) -> list[str]:
        return self["tickers"]

    @property
    def wikilinks(self) -> list[str]:
        return self["wikilinks"]


def extract(
    text: str,
    *,
    ticker_set: Optional[set[str]] = None,
    wikilink_vocab: Optional[set[str]] = None,
) -> "NerResult":
    """Extract tickers and wikilink vocab terms from ``text``.

    - ``tickers``: 4-digit runs, filtered by ``ticker_set`` when provided.
    - ``wikilinks``: substring matches (case-sensitive) of every term in
      ``wikilink_vocab``; if no vocab is given, returns terms already
      wrapped in ``[[...]]`` inside the text.
    """
    tickers_raw = _TICKER_RE.findall(text or "")
    if ticker_set is not None:
        tickers_raw = [t for t in tickers_raw if t in ticker_set]
    tickers = _unique_in_order(tickers_raw)

    if wikilink_vocab is None:
        wikilinks = _unique_in_order(_WIKILINK_RE.findall(text or ""))
    else:
        # Check longer terms first so "ABF 載板" wins over "ABF" when both match.
        ordered_terms = sorted(wikilink_vocab, key=len, reverse=True)
        hits: list[tuple[int, str]] = []
        for term in ordered_terms:
            if not term:
                continue
            start = 0
            while True:
                idx = text.find(term, start)
                if idx == -1:
                    break
                hits.append((idx, term))
                start = idx + len(term)
        hits.sort(key=lambda pair: pair[0])
        wikilinks = _unique_in_order(term for _, term in hits)

    return NerResult(tickers=tickers, wikilinks=wikilinks)
