"""
Chunker — splits CrawledPage markdown into structured, metadata-enriched chunks.

Strategy:
  1. Filter pages below MIN_CONTENT_LENGTH (empty/near-empty — not worth indexing)
  2. Use LlamaIndex MarkdownNodeParser for heading-aware splitting
  3. Fall back to paragraph splitting for pages with no headings
  4. Enrich every chunk with URL, breadcrumb, heading, position metadata
"""

import re
from pathlib import Path

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TimeElapsedColumn, TextColumn

from membuilder.crawler.models import CrawledPage
from membuilder.parser.metadata import url_to_breadcrumb
from membuilder.parser.models import Chunk, make_chunk_id

console = Console()

MIN_CHUNK_LENGTH = 100      # discard heading stubs below this
MAX_CHUNK_LENGTH = 6_000    # secondary split threshold

# Pages shorter than this are skipped — empty section indexes, JS failures etc.
MIN_CONTENT_LENGTH = 500

# LlamaIndex MarkdownNodeParser — splits on headings, preserves hierarchy
_parser = MarkdownNodeParser()

def _clean_content(text: str) -> str:
    """Strip K8s anchor links from heading lines in content body."""
    return re.sub(r"(\#{1,6}\s+.+?)\[[\s\S]*?\]\([\s\S]*?\)", r"\1", text, flags=re.MULTILINE)


def _clean_heading(heading: str) -> str:
    """Strip markdown heading syntax and K8s anchor links from heading text."""
    heading = re.sub(r"^#{1,6}\s+", "", heading)
    heading = re.sub(r"\s*\[[\s\S]*", "", heading)
    return heading.strip()


def _extract_heading(node_text: str, page_title: str) -> str:
    """
    Pull the heading from a chunk's text content.
    MarkdownNodeParser includes the heading at the top of each node.
    Falls back to page title if no heading found.
    """
    first_line = node_text.strip().split("\n")[0]
    if first_line.startswith("#"):
        return _clean_heading(first_line)
    return page_title


def _strip_url_prefix(url: str) -> str:
    """
    Derive the breadcrumb strip prefix from the URL's domain + /docs root.

    Examples:
        kubernetes.io/docs/concepts/... → strip "/docs"
        docs.python.org/3/library/...  → strip "/3"
    """
    from urllib.parse import urlparse
    path = urlparse(url).path
    segments = [s for s in path.split("/") if s]
    # Use first path segment as the strip prefix (e.g. "docs", "3", "en")
    if segments:
        return "/" + segments[0]
    return ""

def _split_large_chunk(chunk: Chunk) -> list[Chunk]:
    """Split a chunk that exceeds MAX_CHUNK_LENGTH by paragraph boundaries."""
    if len(chunk.content) <= MAX_CHUNK_LENGTH:
        return [chunk]

    paragraphs = chunk.content.split("\n\n")
    parts = []
    current = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > MAX_CHUNK_LENGTH and current:
            parts.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        parts.append("\n\n".join(current))

    return [
        Chunk(
            chunk_id=make_chunk_id(chunk.source_url, chunk.chunk_index * 1000 + i),
            source_url=chunk.source_url,
            page_title=chunk.page_title,
            heading=chunk.heading,
            breadcrumb=chunk.breadcrumb,
            content=part.strip(),
            chunk_index=chunk.chunk_index * 1000 + i,
            total_chunks=chunk.total_chunks,
            depth=chunk.depth,
            crawled_at=chunk.crawled_at,
        )
        for i, part in enumerate(parts)
        if part.strip()
    ]

def chunk_page(page: CrawledPage) -> list[Chunk]:
    """
    Chunk a single CrawledPage into a list of Chunk objects.
    Returns empty list if page is below minimum content threshold.
    """
    if len(page.markdown) < MIN_CONTENT_LENGTH:
        return []

    # Clean anchor junk before chunking
    clean_markdown = _clean_content(page.markdown)

    strip_prefix = _strip_url_prefix(page.url)
    breadcrumb = url_to_breadcrumb(page.url, strip_prefix)

    # Wrap in LlamaIndex Document for parsing
    doc = Document(
        text=clean_markdown,
        metadata={
            "source_url": page.url,
            "page_title": page.title,
        }
    )

    nodes = _parser.get_nodes_from_documents([doc])

    # If parser returns no nodes (no headings), treat whole page as one chunk
    if not nodes:
        return [
            Chunk(
                chunk_id=make_chunk_id(page.url, 0),
                source_url=page.url,
                page_title=page.title,
                heading=page.title,
                breadcrumb=breadcrumb,
                content=clean_markdown.strip(),
                chunk_index=0,
                total_chunks=1,
                depth=page.depth,
                crawled_at=page.crawled_at,
            )
        ]

    chunks = []
    for i, node in enumerate(nodes):
        content = node.get_content().strip()
        if not content:
            continue

        heading = _extract_heading(content, page.title)

        for i, node in enumerate(nodes):
            content = node.get_content().strip()
            if not content or len(content) < MIN_CHUNK_LENGTH:    # ← filter tiny
                continue

            heading = _extract_heading(content, page.title)
            chunk = Chunk(
                chunk_id=make_chunk_id(page.url, i),
                source_url=page.url,
                page_title=page.title,
                heading=heading,
                breadcrumb=breadcrumb,
                content=content,
                chunk_index=i,
                total_chunks=len(nodes),
                depth=page.depth,
                crawled_at=page.crawled_at,
            )
            # Secondary split for large chunks
            chunks.extend(_split_large_chunk(chunk))               # ← split large

        return chunks


def chunk_pages(pages: list[CrawledPage]) -> list[Chunk]:
    """
    Chunk a list of CrawledPages with progress display.
    Skips pages below MIN_CONTENT_LENGTH.
    """
    all_chunks: list[Chunk] = []
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Chunking pages...", total=len(pages))

        for page in pages:
            chunks = chunk_page(page)
            if not chunks:
                skipped += 1
            else:
                all_chunks.extend(chunks)
            progress.advance(task)

    console.print(
        f"\n[green]✓ Chunking complete.[/green] "
        f"[bold]{len(all_chunks)}[/bold] chunks from "
        f"[bold]{len(pages) - skipped}[/bold] pages "
        f"([yellow]{skipped}[/yellow] skipped)."
    )

    return all_chunks