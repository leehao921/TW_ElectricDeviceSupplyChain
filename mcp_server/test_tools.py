"""Unit tests for MCP tools that don't require live DBs.

Covers Markdown parsing for `reports.py` and `graph.py` wikilink helpers.
DB-backed tools are tested only for their graceful-failure branch.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path


class ReportsToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "Pilot_Reports" / "Semiconductors").mkdir(parents=True)
        (self.tmp / "Pilot_Reports" / "Banks").mkdir(parents=True)
        (self.tmp / "themes").mkdir()

        (self.tmp / "Pilot_Reports" / "Semiconductors" / "2330_台積電.md").write_text(
            textwrap.dedent(
                """\
                # 2330 - [[台積電]]

                ## 業務簡介
                [[台積電]] 與 [[CoWoS]] 技術領先，客戶包含 [[Apple]]。
                """
            ),
            encoding="utf-8",
        )
        (self.tmp / "Pilot_Reports" / "Semiconductors" / "2303_聯電.md").write_text(
            "# 2303 - [[聯電]]\n[[聯電]] 競爭者。\n",
            encoding="utf-8",
        )
        (self.tmp / "Pilot_Reports" / "Banks" / "2882_國泰金.md").write_text(
            "# 2882 - [[國泰金]]\n",
            encoding="utf-8",
        )

        (self.tmp / "themes" / "CoWoS.md").write_text(
            textwrap.dedent(
                """\
                # CoWoS

                ## 上游 (1)
                - **3167 大量** (Specialty Industrial Machinery)

                ## 中游 (1)
                - **2330 台積電** (Semiconductors)

                ## 下游 (1)
                - **3131 弘塑** (Semiconductor Equipment & Materials)
                """
            ),
            encoding="utf-8",
        )

        os.environ["REPO_ROOT"] = str(self.tmp)
        # Force markdown fallback for graph tests by pointing at an unreachable port
        os.environ["FALKORDB_HOST"] = "127.0.0.1"
        os.environ["FALKORDB_PORT"] = "1"
        # Reimport with patched env
        import importlib
        from mcp_server.tools import reports, graph
        importlib.reload(reports)
        importlib.reload(graph)
        self.reports = reports
        self.graph = graph

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("REPO_ROOT", None)
        os.environ.pop("FALKORDB_HOST", None)
        os.environ.pop("FALKORDB_PORT", None)

    def run_async(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    # list_tickers
    def test_list_tickers_all(self):
        out = self.run_async(self.reports.list_tickers())
        tickers = {r["ticker"] for r in out}
        self.assertEqual(tickers, {"2303", "2330", "2882"})

    def test_list_tickers_by_sector(self):
        out = self.run_async(self.reports.list_tickers(sector="Semiconductors"))
        self.assertEqual({r["ticker"] for r in out}, {"2303", "2330"})
        self.assertTrue(all(r["sector"] == "Semiconductors" for r in out))

    def test_list_tickers_by_theme(self):
        out = self.run_async(self.reports.list_tickers(theme="CoWoS"))
        self.assertEqual({r["ticker"] for r in out}, {"2330"})

    def test_list_tickers_includes_name(self):
        out = self.run_async(self.reports.list_tickers(sector="Banks"))
        self.assertEqual(out, [{"ticker": "2882", "name": "國泰金", "sector": "Banks"}])

    # get_report
    def test_get_report_returns_markdown(self):
        text = self.run_async(self.reports.get_report("2330"))
        self.assertIn("台積電", text)
        self.assertIn("CoWoS", text)

    def test_get_report_missing_ticker(self):
        text = self.run_async(self.reports.get_report("9999"))
        self.assertIn("Error", text)

    # get_theme_cohort
    def test_get_theme_cohort_groups(self):
        cohort = self.run_async(self.reports.get_theme_cohort("CoWoS"))
        segments = {r["segment"] for r in cohort}
        self.assertEqual(segments, {"上游", "中游", "下游"})
        midstream = [r for r in cohort if r["segment"] == "中游"]
        self.assertEqual(midstream[0]["ticker"], "2330")
        self.assertEqual(midstream[0]["industry"], "Semiconductors")

    def test_get_theme_cohort_missing(self):
        out = self.run_async(self.reports.get_theme_cohort("NotATheme"))
        self.assertEqual(len(out), 1)
        self.assertIn("error", out[0])

    # graph.find_tickers_exposed_to
    def test_find_tickers_exposed_to(self):
        out = self.run_async(self.graph.find_tickers_exposed_to("CoWoS"))
        self.assertEqual(out, ["2330"])

    def test_find_tickers_exposed_to_normalizes(self):
        out = self.run_async(self.graph.find_tickers_exposed_to("  Apple  "))
        self.assertEqual(out, ["2330"])

    def test_find_tickers_exposed_to_no_match(self):
        out = self.run_async(self.graph.find_tickers_exposed_to("Nonexistent"))
        self.assertEqual(out, [])

    # graph.get_supply_chain (markdown fallback)
    def test_get_supply_chain_markdown_fallback(self):
        out = self.run_async(self.graph.get_supply_chain("2330", depth=1))
        self.assertEqual(out["source"], "markdown")
        node_ids = {n["id"] for n in out["nodes"]}
        self.assertIn("2330", node_ids)
        edge_targets = {e["to"] for e in out["edges"]}
        self.assertIn("CoWoS", edge_targets)

    def test_get_supply_chain_missing_ticker(self):
        out = self.run_async(self.graph.get_supply_chain("9999", depth=1))
        self.assertIn("error", out)


class DBErrorHandlingTest(unittest.TestCase):
    """DB-backed tools must return a clear error dict instead of crashing."""

    def setUp(self):
        # Point at an unreachable DSN
        os.environ["PG_NEWS_DSN"] = "postgresql://x:x@127.0.0.1:1/none"
        os.environ["PG_TRADING_DSN"] = "postgresql://x:x@127.0.0.1:1/none"
        import importlib
        from mcp_server.tools import news, market
        importlib.reload(news)
        importlib.reload(market)
        self.news = news
        self.market = market

    def run_async(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_news_returns_error(self):
        out = self.run_async(self.news.get_recent_news("2330", days=7))
        self.assertEqual(len(out), 1)
        self.assertIn("error", out[0])

    def test_mops_returns_error(self):
        out = self.run_async(self.news.get_mops_disclosures("2330", days=30))
        self.assertEqual(len(out), 1)
        self.assertIn("error", out[0])

    def test_price_history_returns_error(self):
        out = self.run_async(self.market.get_price_history("2330", days=30))
        self.assertEqual(len(out), 1)
        self.assertIn("error", out[0])

    def test_institutional_flow_returns_error(self):
        out = self.run_async(self.market.get_institutional_flow("2330", days=5))
        self.assertEqual(len(out), 1)
        self.assertIn("error", out[0])


if __name__ == "__main__":
    unittest.main()
