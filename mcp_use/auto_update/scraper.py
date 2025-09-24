"""Utilities for collecting documentation about new tool calling formats."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Awaitable, Callable, Iterable

import aiohttp


@dataclass(slots=True)
class DocumentationSnapshot:
    """Represents a normalized version of scraped documentation."""

    model: str
    url: str
    raw_text: str
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sections: dict[str, str] = field(default_factory=dict)

    def get_section(self, name: str) -> str | None:
        """Return a documentation section by its normalized name."""

        key = name.lower().strip()
        return self.sections.get(key)


class _PlainTextExtractor(HTMLParser):
    """Very small HTML to plain text converter."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:  # noqa: D401 - required override
        if data:
            self._parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: D401
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:  # noqa: D401
        if tag in {"p", "div", "li", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def get_text(self) -> str:
        return "".join(self._parts)


class DocumentationScraper:
    """Fetch and normalize documentation pages."""

    def __init__(self, fetcher: Callable[[str], Awaitable[str]] | None = None) -> None:
        self._fetcher = fetcher

    async def scrape(self, model: str, url: str) -> DocumentationSnapshot:
        """Scrape documentation for a given model and return a snapshot."""

        raw = await self._fetch(url)
        text = self._normalize_text(raw)
        sections = self._split_sections(text)
        return DocumentationSnapshot(model=model, url=url, raw_text=text, sections=sections)

    def scrape_sync(self, model: str, url: str) -> DocumentationSnapshot:
        """Synchronous wrapper for environments without an event loop."""

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            raise RuntimeError("scrape_sync cannot be called from a running event loop")

        return asyncio.run(self.scrape(model, url))

    async def _fetch(self, url: str) -> str:
        if self._fetcher is not None:
            return await self._fetcher(url)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                if "charset=" in content_type:
                    return await response.text()
                return await response.text(encoding="utf-8")

    def _normalize_text(self, raw: str) -> str:
        if "<" in raw and ">" in raw:
            parser = _PlainTextExtractor()
            parser.feed(raw)
            text = parser.get_text()
        else:
            text = raw

        text = unescape(text)
        text = re.sub(r"\r\n|\r", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ 	]{2,}", " ", text)
        return text.strip()

    def _split_sections(self, text: str) -> dict[str, str]:
        headings = self._iter_headings(text)
        sections: dict[str, str] = {}
        for heading, content in headings:
            sections[heading] = content.strip()
        if not sections:
            sections["body"] = text
        return sections

    def _iter_headings(self, text: str) -> Iterable[tuple[str, str]]:
        pattern = re.compile(r"(?im)^(#{1,3}|[A-Z][A-Za-z0-9\s]{0,60})\n", re.MULTILINE)
        matches = list(pattern.finditer(text))
        if not matches:
            return []
        results: list[tuple[str, str]] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            heading = match.group(0).strip().lower().lstrip("# ")
            content = text[start:end].strip()
            if content:
                results.append((heading, content))
        return results

