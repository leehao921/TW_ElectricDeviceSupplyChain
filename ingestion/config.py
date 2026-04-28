"""Shared ingestion configuration.

Loads settings from environment variables with sensible defaults. Uses
``pydantic-settings`` when available, falling back to a plain ``dataclass``
with ``os.getenv`` so the package still imports in minimal environments
(CI, smoke tests) without the optional dependency installed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Resolve the repo root once: this file lives at <repo>/ingestion/config.py
_REPO_ROOT = Path(__file__).resolve().parent.parent

_DEFAULT_PG_DSN = "postgresql://knowledge:knowledge@localhost:5433/tw_electronics"
_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_EMBEDDING_MODEL = "bge-m3"
_DEFAULT_EMBEDDING_DIM = 1024
_DEFAULT_TZ = "Asia/Taipei"


try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        """Typed settings backed by environment variables."""

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
            case_sensitive=False,
        )

        pg_news_dsn: str = _DEFAULT_PG_DSN
        pg_trading_dsn: str = _DEFAULT_PG_DSN
        ollama_base_url: str = _DEFAULT_OLLAMA_URL
        embedding_model: str = _DEFAULT_EMBEDDING_MODEL
        embedding_dim: int = _DEFAULT_EMBEDDING_DIM
        repo_root: Path = _REPO_ROOT
        tz: str = _DEFAULT_TZ
        finmind_token: Optional[str] = None

except ImportError:  # pragma: no cover - exercised only without pydantic-settings
    from dataclasses import dataclass, field

    def _get_env(key: str, default: str) -> str:
        return os.getenv(key.upper(), default)

    @dataclass
    class Settings:  # type: ignore[no-redef]
        pg_news_dsn: str = field(default_factory=lambda: _get_env("pg_news_dsn", _DEFAULT_PG_DSN))
        pg_trading_dsn: str = field(default_factory=lambda: _get_env("pg_trading_dsn", _DEFAULT_PG_DSN))
        ollama_base_url: str = field(default_factory=lambda: _get_env("ollama_base_url", _DEFAULT_OLLAMA_URL))
        embedding_model: str = field(default_factory=lambda: _get_env("embedding_model", _DEFAULT_EMBEDDING_MODEL))
        embedding_dim: int = field(default_factory=lambda: int(_get_env("embedding_dim", str(_DEFAULT_EMBEDDING_DIM))))
        repo_root: Path = field(default_factory=lambda: Path(_get_env("repo_root", str(_REPO_ROOT))))
        tz: str = field(default_factory=lambda: _get_env("tz", _DEFAULT_TZ))
        finmind_token: Optional[str] = field(default_factory=lambda: os.getenv("FINMIND_TOKEN"))


# Module-level singleton used by other ingestion modules.
settings = Settings()
