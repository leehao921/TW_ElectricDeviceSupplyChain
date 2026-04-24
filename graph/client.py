"""Graphiti client wrapper for the Taiwan-electronics supply-chain graph.

Configures Graphiti against a local FalkorDB + Ollama stack, partitioned by
``group_id="tw-electronics"``. Mirrors the reference implementation at
``Knowledge_manager/mcp_servers/graphiti_server.py`` so both personal and
project namespaces share the same infrastructure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6380"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
LLM_MODEL = os.getenv("GRAPHITI_LLM_MODEL", "qwen2.5:7b")
GROUP_ID = os.getenv("GRAPHITI_GROUP_ID", "tw-electronics")

_client: Any | None = None
_client_lock = asyncio.Lock()


async def get_client() -> Any:
    """Lazy singleton for the Graphiti client."""
    global _client
    if _client is not None:
        return _client

    async with _client_lock:
        if _client is not None:
            return _client

        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.embedder import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.cross_encoder import OpenAIRerankerClient
        from graphiti_core.llm_client import LLMConfig, OpenAIClient

        llm_config = LLMConfig(
            api_key="ollama",
            base_url=f"{OLLAMA_BASE_URL}/v1",
            model=LLM_MODEL,
            small_model=LLM_MODEL,
        )

        driver = FalkorDriver(host=FALKORDB_HOST, port=FALKORDB_PORT)

        client = Graphiti(
            graph_driver=driver,
            llm_client=OpenAIClient(llm_config),
            embedder=OpenAIEmbedder(OpenAIEmbedderConfig(
                api_key="ollama",
                base_url=f"{OLLAMA_BASE_URL}/v1",
                embedding_model=EMBEDDING_MODEL,
                embedding_dim=EMBEDDING_DIM,
            )),
            cross_encoder=OpenAIRerankerClient(config=llm_config),
        )

        await client.build_indices_and_constraints()
        _client = client
        return _client


async def health_check() -> dict:
    """Probe FalkorDB and Ollama; return a simple status dict."""
    falkor_status = "error"
    try:
        import redis.asyncio as aioredis

        r = aioredis.Redis(host=FALKORDB_HOST, port=FALKORDB_PORT)
        try:
            await r.ping()
            falkor_status = "connected"
        finally:
            await r.aclose()
    except Exception:
        falkor_status = "error"

    ollama_status = "error"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5) as http:
            resp = await http.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                ollama_status = "connected"
    except Exception:
        ollama_status = "error"

    return {
        "falkor": falkor_status,
        "ollama": ollama_status,
        "group_id": GROUP_ID,
    }


def _main() -> None:
    parser = argparse.ArgumentParser(description="Graphiti client utilities")
    parser.add_argument("--health", action="store_true", help="Print health status as JSON")
    args = parser.parse_args()

    if args.health:
        result = asyncio.run(health_check())
        print(json.dumps(result))
        return

    parser.print_help()


if __name__ == "__main__":
    _main()
