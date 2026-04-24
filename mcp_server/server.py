"""FastMCP stdio server exposing 10 research tools over the TW coverage."""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_server.tools import graph, market, news, reports

app = FastMCP("tw-electronics-research")


@app.tool()
async def list_tickers(
    sector: str | None = None, theme: str | None = None
) -> list[dict]:
    """List tickers, optionally filtered by sector folder or theme file."""
    return await reports.list_tickers(sector=sector, theme=theme)


@app.tool()
async def get_report(ticker: str) -> str:
    """Return the full Markdown report for a ticker."""
    return await reports.get_report(ticker)


@app.tool()
async def get_theme_cohort(theme: str) -> list[dict]:
    """Return tickers in a theme, grouped by 上游/中游/下游/相關公司."""
    return await reports.get_theme_cohort(theme)


@app.tool()
async def find_tickers_exposed_to(wikilink: str) -> list[str]:
    """Find tickers whose reports mention the given wikilink target."""
    return await graph.find_tickers_exposed_to(wikilink)


@app.tool()
async def get_supply_chain(ticker: str, depth: int = 2) -> dict:
    """Return the supply-chain neighborhood around `ticker` up to `depth` hops."""
    return await graph.get_supply_chain(ticker, depth=depth)


@app.tool()
async def get_recent_news(ticker: str, days: int = 7) -> list[dict]:
    """Return recent news mentioning `ticker`."""
    return await news.get_recent_news(ticker, days=days)


@app.tool()
async def search_news_semantic(query: str, k: int = 10) -> list[dict]:
    """Semantic cosine search over the news corpus."""
    return await news.search_news_semantic(query, k=k)


@app.tool()
async def get_mops_disclosures(ticker: str, days: int = 30) -> list[dict]:
    """Return recent MOPS filings for `ticker`."""
    return await news.get_mops_disclosures(ticker, days=days)


@app.tool()
async def get_price_history(ticker: str, days: int = 30) -> list[dict]:
    """Return daily OHLCV bars for `ticker`."""
    return await market.get_price_history(ticker, days=days)


@app.tool()
async def get_institutional_flow(ticker: str, days: int = 5) -> list[dict]:
    """Return recent institutional flow rows for `ticker`."""
    return await market.get_institutional_flow(ticker, days=days)


if __name__ == "__main__":
    app.run()
