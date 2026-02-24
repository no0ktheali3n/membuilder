"""
Protocol layer — structural interfaces and shared data types for the full pipeline.

All concrete dependencies (crawl4ai, LlamaIndex, ChromaDB, Milvus) live ONLY inside
their adapter implementations. Everything downstream (Retriever, Synthesizer, Vault
Writer) depends only on these interfaces.

Use `typing.Protocol` for structural subtyping — no forced inheritance required.
Adapters just need to implement the right shape.
"""

from __future__ import annotations
from typing import Protocol, AsyncIterator, runtime_checkable
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Shared data types
# ---------------------------------------------------------------------------

@dataclass
class RawPage:
    """Raw page as yielded by a Crawler. Content is markdown text."""
    url: str
    content: str
    metadata: dict    # must include: title (str), depth (int)
    crawled_at: str   # ISO 8601 timestamp — set by the crawler at fetch time


@dataclass
class Chunk:
    """
    A text chunk ready for embedding. All metadata values are scalar (str/int)
    for compatibility with both ChromaDB and Milvus.

    Required keys in metadata (all adapters must populate these):
        url:         str  — source page URL
        breadcrumb:  str  — " > " joined path, e.g. "Concepts > Workloads > Pods"
        chunk_index: int  — position of chunk within its source page
        domain:      str  — e.g. "kubernetes"
        crawled_at:  str  — ISO 8601 timestamp from the RawPage
        tags:        str  — comma-joined lowercased breadcrumb segments,
                            e.g. "concepts,workloads,pods"
        heading:     str  — nearest parent heading for this chunk
    """
    id: str
    text: str
    metadata: dict


@dataclass
class EmbeddedChunk:
    """A Chunk paired with its embedding vector."""
    chunk: Chunk
    embedding: list[float]


@dataclass
class SearchResult:
    """A retrieved chunk with its similarity score."""
    chunk: Chunk
    score: float


@dataclass
class UpsertResult:
    """Summary of a vector store upsert operation."""
    inserted: int
    updated: int
    errors: int


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------

@runtime_checkable
class Crawler(Protocol):
    async def crawl(self, url: str) -> AsyncIterator[RawPage]:
        ...


@runtime_checkable
class Chunker(Protocol):
    def chunk(self, page: RawPage) -> list[Chunk]:
        ...


@runtime_checkable
class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    @property
    def model_id(self) -> str:
        """Unique identifier for this model — used for cache keys and provenance."""
        ...


@runtime_checkable
class VectorStore(Protocol):
    async def upsert(self, chunks: list[EmbeddedChunk]) -> UpsertResult:
        ...

    async def query(
        self,
        embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        ...

    async def delete(self, ids: list[str]) -> None:
        ...

    async def count(self) -> int:
        ...
