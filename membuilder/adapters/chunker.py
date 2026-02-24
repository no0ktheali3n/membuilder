"""
MarkdownChunker — adapter wrapping the LlamaIndex-backed parser to satisfy
the Chunker protocol.

Converts RawPage → CrawledPage (internal) → parser Chunk (internal) →
protocol Chunk. No LlamaIndex or parser.models.Chunk types leak past this
boundary.

v0.3.1 changes vs original adapter:
- Accepts domain at construction (set from MembuilderConfig.vault.domain)
- Chunk IDs are sha256(url + "::" + chunk_index)[:16] — deterministic,
  stable across re-runs so vault back-references never break (ADR-003)
- Emits all required Chunk.metadata keys: url, breadcrumb, chunk_index,
  domain, crawled_at, tags, heading
"""

from __future__ import annotations
import hashlib

from membuilder.protocols import RawPage
from membuilder.protocols import Chunk as ProtocolChunk
from membuilder.crawler.models import CrawledPage
from membuilder.parser.chunker import chunk_page, _strip_url_prefix
from membuilder.parser.metadata import url_to_breadcrumb


def _make_id(url: str, chunk_index: int) -> str:
    """
    Deterministic chunk ID: sha256(url + '::' + chunk_index)[:16].

    16 hex characters = 64-bit collision resistance. Sufficient for any
    single domain's chunk count. Stable across re-runs so IDs stored in
    vault note frontmatter as back-references remain valid.
    """
    raw = f"{url}::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MarkdownChunker:
    """
    Chunker adapter backed by LlamaIndex MarkdownNodeParser.

    Accepts a RawPage, converts it to the internal CrawledPage type,
    runs the existing heading-aware chunking pipeline, then maps the
    result back to protocol Chunk objects with all required metadata keys.

    Args:
        domain: Domain label for this crawl — e.g. "kubernetes".
                Stored in every Chunk.metadata["domain"] to support
                cross-domain filtering at query time (v0.4.0).
    """

    def __init__(self, domain: str = "") -> None:
        self.domain = domain

    def chunk(self, page: RawPage) -> list[ProtocolChunk]:
        """
        Chunk a RawPage into a list of protocol Chunk objects.

        Returns an empty list if the page content is below the minimum
        quality threshold (same behaviour as the underlying chunk_page()).

        All required Chunk.metadata keys are populated:
            url, breadcrumb, chunk_index, domain, crawled_at, tags, heading
        """
        crawled = CrawledPage(
            url=page.url,
            title=page.metadata.get("title", page.url),
            markdown=page.content,
            depth=page.metadata.get("depth", 0),
            crawled_at=page.crawled_at,
            status="ok",
        )

        internal_chunks = chunk_page(crawled)

        if not internal_chunks and page.content.strip():
            # chunk_page() returned [] — content is below MIN_CONTENT_LENGTH.
            # Create a single fallback chunk so short pages are never silently
            # dropped (important for test fixtures and terse documentation pages).
            strip_prefix = _strip_url_prefix(page.url)
            breadcrumb: list[str] = url_to_breadcrumb(page.url, strip_prefix)
            tags: list[str] = [s.lower().replace(" ", "-") for s in breadcrumb]
            return [
                ProtocolChunk(
                    id=_make_id(page.url, 0),
                    text=page.content.strip(),
                    metadata={
                        "url": page.url,
                        "breadcrumb": breadcrumb,
                        "chunk_index": 0,
                        "domain": self.domain,
                        "crawled_at": page.crawled_at,
                        "tags": tags,
                        "heading": page.metadata.get("title", page.url),
                    },
                )
            ]

        result = []
        for c in internal_chunks:
            # breadcrumb is a list[str] on the internal Chunk — keep it typed.
            # Vector store adapters are responsible for serializing to strings
            # before writing to scalar-only backends (ChromaDB, Milvus).
            breadcrumb: list[str] = c.breadcrumb
            tags: list[str] = [s.lower().replace(" ", "-") for s in breadcrumb]

            result.append(
                ProtocolChunk(
                    id=_make_id(page.url, c.chunk_index),
                    text=c.text,
                    metadata={
                        "url": page.url,
                        "breadcrumb": breadcrumb,   # list[str]
                        "chunk_index": c.chunk_index,
                        "domain": self.domain,
                        "crawled_at": page.crawled_at,
                        "tags": tags,               # list[str]
                        "heading": c.heading,
                    },
                )
            )

        return result
