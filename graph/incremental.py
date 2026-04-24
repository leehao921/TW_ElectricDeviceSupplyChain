"""News-driven incremental writer for the supply-chain graph.

Intended to be called by an ingestion/scheduler layer (Unit 7) once per
news item. The gate: ingest only when the item is obviously supply-chain
relevant — either multiple tickers appear together, or a canonical
supply-chain verb is present.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

SUPPLY_CHAIN_VERB_RE = re.compile(r"供貨|採購|代工|出貨|委外|獨家|中標|得標|合作")
_TICKER_SPLIT_RE = re.compile(r"[,\s]+")
_TEXT_KEYS = ("title", "summary", "content", "body")


def _extract_tickers(news_item: dict) -> list[str]:
    tickers = news_item.get("tickers") or []
    if isinstance(tickers, str):
        return [t for t in _TICKER_SPLIT_RE.split(tickers) if t]
    return list(tickers)


def _is_supply_chain_relevant(news_item: dict) -> bool:
    if len(_extract_tickers(news_item)) >= 2:
        return True
    text_blob = " ".join(
        v for k in _TEXT_KEYS if isinstance((v := news_item.get(k)), str) and v
    )
    return bool(SUPPLY_CHAIN_VERB_RE.search(text_blob))


def _episode_body(news_item: dict) -> str:
    title = news_item.get("title") or ""
    summary = news_item.get("summary") or news_item.get("content") or news_item.get("body") or ""
    tickers = _extract_tickers(news_item)
    published = news_item.get("published_at") or news_item.get("date") or ""
    source = news_item.get("source") or ""

    lines = [f"News: {title}"]
    if tickers:
        lines.append(f"Tickers: {', '.join(tickers)}")
    if source:
        lines.append(f"Source: {source}")
    if published:
        lines.append(f"Published: {published}")
    if summary:
        lines.append("")
        lines.append(summary)
    return "\n".join(lines)


def _reference_time(news_item: dict) -> datetime:
    raw = news_item.get("published_at") or news_item.get("date")
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
    return datetime.now()


async def ingest_news_as_episode(news_item: dict) -> dict[str, Any]:
    """Ingest a single news_items row as a Graphiti episode if relevant.

    Returns a small status dict describing what happened. Does not raise on
    relevance-gate failures — those return ``{"status": "skipped", ...}``.
    """
    if not _is_supply_chain_relevant(news_item):
        return {"status": "skipped", "reason": "not supply-chain relevant"}

    from graph.client import GROUP_ID, get_client  # local import keeps module importable without deps
    from graphiti_core.nodes import EpisodeType

    client = await get_client()
    news_id = news_item.get("id") or news_item.get("uuid") or "unknown"
    name = f"news:{news_id}"
    try:
        episode = await client.add_episode(
            name=name,
            episode_body=_episode_body(news_item),
            source=EpisodeType.text,
            source_description="news: Taiwan electronics supply-chain news",
            reference_time=_reference_time(news_item),
            group_id=GROUP_ID,
        )
        return {
            "status": "ingested",
            "name": name,
            "episode_uuid": getattr(episode, "uuid", str(episode)),
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "name": name, "error": str(e)}
