"""News-layer tools: pgvector news + MOPS disclosures from `tw_electronics`."""

from __future__ import annotations

import os
from typing import Any

PG_NEWS_DSN = os.environ.get(
    "PG_NEWS_DSN",
    "postgresql://knowledge:knowledge@localhost:5433/tw_electronics",
)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")


async def _connect():
    import asyncpg
    return await asyncpg.connect(PG_NEWS_DSN)


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


async def get_recent_news(ticker: str, days: int = 7) -> list[dict[str, Any]]:
    """Return news items mentioning `ticker` within the last `days` days."""
    try:
        conn = await _connect()
    except Exception as e:
        return [{"error": f"news DB unreachable: {e}"}]
    try:
        rows = await conn.fetch(
            """
            SELECT id, title, url, source, published_at, summary, tickers
            FROM news_items
            WHERE $1 = ANY(tickers)
              AND published_at > NOW() - ($2::text || ' days')::interval
            ORDER BY published_at DESC
            LIMIT 100
            """,
            ticker,
            str(int(days)),
        )
        return _rows_to_dicts(rows)
    except Exception as e:
        return [{"error": f"news query failed: {e}"}]
    finally:
        await conn.close()


async def _embed_query(query: str) -> list[float] | None:
    """Embed `query` via Ollama. Returns None on failure."""
    try:
        import httpx
    except ImportError:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": query},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("embedding")
    except Exception:
        return None


async def search_news_semantic(query: str, k: int = 10) -> list[dict[str, Any]]:
    """Semantic cosine search over `news_items.embedding` via pgvector."""
    embedding = await _embed_query(query)
    if embedding is None:
        return [{"error": "embedding service unreachable"}]
    try:
        conn = await _connect()
    except Exception as e:
        return [{"error": f"news DB unreachable: {e}"}]
    try:
        embedding_literal = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"
        rows = await conn.fetch(
            """
            SELECT id, title, url, source, published_at, summary, tickers,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM news_items
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            embedding_literal,
            int(k),
        )
        return _rows_to_dicts(rows)
    except Exception as e:
        return [{"error": f"semantic search failed: {e}"}]
    finally:
        await conn.close()


async def get_mops_disclosures(ticker: str, days: int = 30) -> list[dict[str, Any]]:
    """Return recent MOPS filings for `ticker` within the last `days` days."""
    try:
        conn = await _connect()
    except Exception as e:
        return [{"error": f"news DB unreachable: {e}"}]
    try:
        rows = await conn.fetch(
            """
            SELECT id, ticker, title, category, filed_at, url, summary
            FROM mops_disclosures
            WHERE ticker = $1
              AND filed_at > NOW() - ($2::text || ' days')::interval
            ORDER BY filed_at DESC
            LIMIT 100
            """,
            ticker,
            str(int(days)),
        )
        return _rows_to_dicts(rows)
    except Exception as e:
        return [{"error": f"mops query failed: {e}"}]
    finally:
        await conn.close()
