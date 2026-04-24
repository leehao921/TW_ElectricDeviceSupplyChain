"""Smoke tests for the ingestion shared infrastructure."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ingestion import ner, universe
from ingestion.config import Settings, settings


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_settings_loads_with_defaults():
    s = Settings()
    assert s.embedding_model == "bge-m3"
    assert s.embedding_dim == 1024
    assert s.tz == "Asia/Taipei"
    assert s.ollama_base_url.startswith("http")
    assert Path(s.repo_root).exists()


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-model")
    monkeypatch.setenv("EMBEDDING_DIM", "2048")
    s = Settings()
    assert s.embedding_model == "custom-model"
    assert s.embedding_dim == 2048


def test_electronics_tickers_size():
    tickers = universe.electronics_tickers()
    assert len(tickers) >= 900, f"expected 900+ electronics tickers, got {len(tickers)}"
    assert all(t.isdigit() and len(t) == 4 for t in tickers)


def test_electronics_tickers_includes_known():
    tickers = universe.electronics_tickers()
    for expected in ("2330", "2317", "2454", "2303"):
        assert expected in tickers, f"expected {expected} in electronics universe"


def test_ticker_to_name_matches_filename():
    mapping = universe.ticker_to_name()
    assert mapping.get("2330") == "台積電"
    assert mapping.get("2454") == "聯發科"
    assert len(mapping) == len(universe.electronics_tickers())


def test_ner_extract_basic_shape():
    text = "台積電 2330 進軍 [[CoWoS]] 與 HBM 產業。聯發科 2454 推出新款 MCU。"
    result = ner.extract(
        text,
        ticker_set=universe.electronics_tickers(),
        wikilink_vocab=ner.load_wikilink_vocab(),
    )
    assert set(result.keys()) == {"tickers", "wikilinks"}
    assert result["tickers"] == ["2330", "2454"]
    # CoWoS is in WIKILINKS.md, so it must appear.
    assert "CoWoS" in result["wikilinks"]


def test_ner_extract_filters_unknown_tickers():
    # 9999 is not an electronics ticker and must be filtered out.
    text = "9999 not valid, 2330 is valid."
    result = ner.extract(text, ticker_set=universe.electronics_tickers())
    assert "2330" in result["tickers"]
    assert "9999" not in result["tickers"]


def test_ner_extract_preserves_first_seen_order():
    text = "2454 2330 2454 2330"
    result = ner.extract(text, ticker_set=universe.electronics_tickers())
    assert result["tickers"] == ["2454", "2330"]


def test_ner_extract_without_vocab_uses_bracketed_links():
    text = "投資 [[Apple]] 與 [[台積電]] 供應鏈。"
    result = ner.extract(text, ticker_set=set())
    assert result["wikilinks"] == ["Apple", "台積電"]


def test_load_wikilink_vocab_nonempty():
    vocab = ner.load_wikilink_vocab()
    assert len(vocab) > 0
    assert "CoWoS" in vocab


def test_scheduler_dry_run_exits_cleanly():
    # Run as a subprocess so argparse runs exactly as in production.
    proc = subprocess.run(
        [sys.executable, "-m", "ingestion.scheduler", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    # Either "No jobs registered" (initial state) or "Registered jobs" header.
    assert "jobs" in proc.stdout.lower() or "registered" in proc.stdout.lower()
