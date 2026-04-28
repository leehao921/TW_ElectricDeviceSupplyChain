"""Graph-layer tools: wikilink exposure + supply-chain neighborhood.

v1 implementation uses Markdown grep against Pilot_Reports/. A graph-backed
path (FalkorDB via Graphiti) is attempted for `get_supply_chain` and falls
back to a Markdown-extracted neighborhood if the graph is unreachable.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import reports as _reports

FALKORDB_HOST = os.environ.get("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.environ.get("FALKORDB_PORT", "6380"))
GRAPHITI_GROUP_ID = os.environ.get("GRAPHITI_GROUP_ID", "tw-electronics")

_WIKILINK_RE = re.compile(r"\[\[([^\]\n|]+?)(?:\|[^\]\n]+)?\]\]")


def _normalize_wikilink(s: str) -> str:
    return s.strip().lower().replace(" ", "").replace("_", "")


async def find_tickers_exposed_to(wikilink: str) -> list[str]:
    """Return tickers whose reports mention the given wikilink target."""
    target = _normalize_wikilink(wikilink)
    hits: list[str] = []
    for ticker, _, _, path in _reports.iter_report_files():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in _WIKILINK_RE.finditer(text):
            if _normalize_wikilink(match.group(1)) == target:
                hits.append(ticker)
                break
    return hits


def _extract_neighbors(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _WIKILINK_RE.finditer(text):
        name = m.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


async def _markdown_neighborhood(ticker: str, depth: int) -> dict:
    """Build a neighborhood dict by following wikilinks through report files."""
    report_index: dict[str, Path] = {
        t: path for t, _, _, path in _reports.iter_report_files()
    }
    if ticker not in report_index:
        return {"error": f"No report found for ticker {ticker}", "source": "markdown"}

    visited: set[str] = set()
    frontier: list[tuple[str, int]] = [(ticker, 0)]
    nodes: list[dict] = []
    edges: list[dict] = []

    while frontier:
        current, d = frontier.pop(0)
        if current in visited or d > depth:
            continue
        visited.add(current)

        path = report_index.get(current)
        if path is None:
            nodes.append({"id": current, "type": "entity", "depth": d})
            continue

        text = path.read_text(encoding="utf-8")
        nodes.append({"id": current, "type": "ticker", "depth": d})
        for neighbor in _extract_neighbors(text):
            edges.append({"from": current, "to": neighbor})
            if d + 1 <= depth and neighbor not in visited:
                frontier.append((neighbor, d + 1))

    return {"source": "markdown", "nodes": nodes, "edges": edges}


async def get_supply_chain(ticker: str, depth: int = 2) -> dict:
    """Return the supply-chain neighborhood around `ticker` up to `depth` hops.

    Tries a FalkorDB-backed query first; falls back to Markdown extraction.
    """
    try:
        from falkordb import FalkorDB  # type: ignore
    except ImportError:
        return await _markdown_neighborhood(ticker, depth)

    try:
        db = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
        graph = db.select_graph(GRAPHITI_GROUP_ID)
        query = (
            "MATCH path = (n {ticker: $ticker})-[*1..%d]-(m) "
            "RETURN path LIMIT 200"
        ) % max(1, int(depth))
        result = graph.query(query, {"ticker": ticker})
        rows = [list(r) for r in (result.result_set or [])]
        return {"source": "falkordb", "rows": rows}
    except Exception as e:  # graph unreachable or query failed
        fallback = await _markdown_neighborhood(ticker, depth)
        fallback["graph_error"] = str(e)
        return fallback
