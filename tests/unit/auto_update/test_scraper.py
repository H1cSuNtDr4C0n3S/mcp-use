import asyncio
import pytest

from mcp_use.auto_update.scraper import DocumentationScraper


def test_scraper_normalizes_html_headings():
    async def fake_fetch(url: str) -> str:  # noqa: ARG001 - fixture style helper
        return """
        <html>
            <body>
                <h1>Tool Choice</h1>
                <p>Use the <code>tool_choice</code> field to control function calling.</p>
            </body>
        </html>
        """

    scraper = DocumentationScraper(fetcher=fake_fetch)
    snapshot = asyncio.run(scraper.scrape("gpt-x", "https://example.com"))

    assert snapshot.model == "gpt-x"
    assert snapshot.get_section("tool choice")
    assert "tool_choice" in snapshot.raw_text
    assert "Use the" in snapshot.raw_text
