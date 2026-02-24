"""
Crawl4AICrawler — adapter wrapping DocCrawler to satisfy the Crawler protocol.

Converts crawl4ai / CrawledPage internals into protocol RawPage objects.
No crawl4ai or CrawledPage types leak past this boundary.
"""

from __future__ import annotations
from typing import AsyncIterator

from membuilder.protocols import RawPage
from membuilder.crawler.crawler import DocCrawler


class Crawl4AICrawler:
    """
    Crawler adapter backed by crawl4ai.

    Wraps DocCrawler and yields RawPage objects as an async generator,
    preserving the existing BFS crawl + checkpointing behaviour.
    """

    def __init__(
        self,
        checkpoint_dir: str = "data/checkpoints",
        max_pages: int = 2000,
        concurrency: int = 5,
        rate_limit_delay: float = 0.5,
    ) -> None:
        self._crawler = DocCrawler(
            checkpoint_dir=checkpoint_dir,
            max_pages=max_pages,
            concurrency=concurrency,
            rate_limit_delay=rate_limit_delay,
        )

    async def crawl(self, url: str) -> AsyncIterator[RawPage]:
        """
        Crawl from url, yielding one RawPage per successfully crawled page.

        Delegates to DocCrawler.crawl() for the actual crawl, then converts
        the returned CrawledPage list to RawPage objects. No CrawledPage or
        crawl4ai types are exposed to callers.

        crawled_at is set directly on RawPage (not buried in metadata) so the
        Chunker can surface it in Chunk.metadata without additional lookups.
        """
        pages = await self._crawler.crawl(url)
        for page in pages:
            yield RawPage(
                url=page.url,
                content=page.markdown,
                metadata={
                    "title": page.title,
                    "depth": page.depth,
                },
                crawled_at=page.crawled_at,
            )
