"""Tests for the Markdown section-and-bullet parser in graph.bootstrap."""

from __future__ import annotations

from pathlib import Path

import pytest

from graph.bootstrap import (
    _bullets,
    _split_sections,
    collect_reports,
    parse_report,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TSMC_REPORT = REPO_ROOT / "Pilot_Reports" / "Semiconductors" / "2330_台積電.md"


def test_split_sections_extracts_h2_headings() -> None:
    md = "# Title\n\n## A\nalpha\n\n## B\nbeta\nbeta2\n\n## C\n"
    sections = _split_sections(md)
    assert "A" in sections and "B" in sections and "C" in sections
    assert sections["A"] == "alpha"
    assert sections["B"] == "beta\nbeta2"
    assert sections["C"] == ""


def test_bullets_captures_bold_prefix_label() -> None:
    body = (
        "**上游 (設備/原料):**\n"
        "- **設備:** [[ASML]], [[Applied Materials]].\n"
        "- **材料:** [[環球晶]], [[Shin-Etsu]].\n"
        "\n"
        "**下游應用:**\n"
        "- **主要平台:** HPC, Smartphone.\n"
    )
    bullets = _bullets(body)
    # Each bullet should carry a label containing the parent section bold prefix.
    labels = [b[0] for b in bullets]
    texts = [b[1] for b in bullets]
    assert any("上游" in (lbl or "") for lbl in labels)
    assert any("下游" in (lbl or "") for lbl in labels)
    assert any("ASML" in t for t in texts)
    assert any("HPC" in t for t in texts)


def test_bullets_handles_h3_labels() -> None:
    body = (
        "### 主要客戶\n"
        "- [[Apple]] (>20%)\n"
        "- [[NVIDIA]]\n"
        "\n"
        "### 主要供應商\n"
        "- [[ASML]]\n"
    )
    bullets = _bullets(body)
    labels = {b[0] for b in bullets}
    assert "主要客戶" in labels
    assert "主要供應商" in labels


@pytest.mark.skipif(not TSMC_REPORT.exists(), reason="TSMC fixture missing")
def test_parse_tsmc_report_populates_all_buckets() -> None:
    parsed = parse_report(TSMC_REPORT)
    assert parsed.ticker == "2330"
    assert parsed.company_name == "台積電"
    assert parsed.sector == "Semiconductors"

    assert parsed.upstream, "upstream bullets expected"
    assert any("ASML" in b for b in parsed.upstream)
    assert parsed.downstream, "downstream bullets expected"
    assert any("NVIDIA" in b or "AMD" in b or "iPhone" in b for b in parsed.downstream)

    assert parsed.customers, "customers expected"
    assert any("Apple" in b for b in parsed.customers)
    assert parsed.suppliers, "suppliers expected"
    assert any("ASML" in b for b in parsed.suppliers)


@pytest.mark.skipif(not TSMC_REPORT.exists(), reason="TSMC fixture missing")
def test_episode_body_contains_all_labels() -> None:
    parsed = parse_report(TSMC_REPORT)
    body = parsed.to_episode_body()
    assert body.startswith("2330 (台積電) supply chain")
    for marker in ("Upstream:", "Midstream:", "Downstream:", "Major customers:", "Major suppliers:"):
        assert marker in body


def test_collect_reports_honors_limit() -> None:
    reports = collect_reports(sector="Semiconductors", limit=2)
    assert len(reports) <= 2
    for r in reports:
        assert r.ticker.isdigit()
        assert r.sector == "Semiconductors"
