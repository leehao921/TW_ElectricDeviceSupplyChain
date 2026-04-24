"""Database pool, embedding client, and run logging helpers.

Thin async wrappers that collectors share:
- ``get_pool()`` returns a lazily-created ``asyncpg.Pool``.
- ``embed(text)`` hits Ollama's ``/api/embeddings`` endpoint.
- ``log_run(...)`` inserts a row into the ``ingest_runs`` table.
- ``close()`` releases the pool and HTTP client on shutdown.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from .config import settings

_pool_lock = asyncio.Lock()
_client_lock = asyncio.Lock()

_pool = None           # type: ignore[var-annotated]  # asyncpg.Pool
_http_client = None    # type: ignore[var-annotated]  # httpx.AsyncClient


async def get_pool():
    """Return a lazily-initialized asyncpg connection pool (singleton)."""
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                import asyncpg  # local import keeps optional dep lazy
                _pool = await asyncpg.create_pool(dsn=settings.pg_news_dsn)
    return _pool


async def _get_http_client():
    global _http_client
    if _http_client is None:
        async with _client_lock:
            if _http_client is None:
                import httpx
                _http_client = httpx.AsyncClient(
                    base_url=settings.ollama_base_url,
                    timeout=60.0,
                )
    return _http_client


async def embed(text: str) -> list[float]:
    """Return a 1024-dim embedding for ``text`` via Ollama."""
    client = await _get_http_client()
    response = await client.post(
        "/api/embeddings",
        json={"model": settings.embedding_model, "prompt": text},
    )
    response.raise_for_status()
    data = response.json()
    vector = data.get("embedding")
    if not isinstance(vector, list):
        raise RuntimeError(f"Ollama response missing 'embedding': {data!r}")
    return vector


async def log_run(
    job_name: str,
    status: str,
    rows_written: Optional[int],
    error: Optional[str] = None,
) -> None:
    """Insert a single row into ``ingest_runs`` describing a scheduler job."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ingest_runs (job_name, status, rows_written, error, run_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            job_name,
            status,
            rows_written,
            error,
        )


async def close() -> None:
    """Release the pool and HTTP client. Safe to call multiple times."""
    global _pool, _http_client
    if _pool is not None:
        await _pool.close()
        _pool = None
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
