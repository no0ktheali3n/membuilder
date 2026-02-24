"""
ChromaVectorStore — adapter wrapping the existing ChromaDB VectorStore to
satisfy the VectorStore protocol.

Manages a single named collection internally. Translates between the
protocol's EmbeddedChunk/SearchResult types and ChromaDB's internal
representations. No chromadb types leak past this boundary.

Score normalization (v0.3.1):
    ChromaDB returns cosine *distance* in [0, 2] (lower = more similar).
    This adapter converts it to cosine *similarity* via `1 - distance`,
    giving a score in [-1, 1] where higher = more similar. This makes
    SearchResult.score direction consistent with MilvusVectorStore.
"""

from __future__ import annotations

from membuilder.protocols import (
    EmbeddedChunk,
    SearchResult,
    UpsertResult,
    Chunk,
)
from membuilder.index.store import VectorStore as _ChromaStore


class ChromaVectorStore:
    """
    VectorStore adapter backed by ChromaDB.

    Wraps the existing VectorStore implementation and manages one collection.
    All operations are async (ChromaDB is synchronous internally; the async
    wrapper keeps the interface consistent with the protocol).

    SearchResult.score is cosine similarity in [-1, 1], higher = more similar.

    Args:
        path:            Directory for ChromaDB persistence.
        collection_name: Name of the ChromaDB collection to use.
        embedding_model: Model string stored in collection metadata for
                         provenance (passed through to ChromaDB metadata).
    """

    def __init__(
        self,
        path: str,
        collection_name: str,
        embedding_model: str = "",
    ) -> None:
        self._store = _ChromaStore(path=path)
        self._collection = self._store.get_or_create_collection(
            name=collection_name,
            embedding_model=embedding_model,
        )

    async def upsert(self, chunks: list[EmbeddedChunk]) -> UpsertResult:
        """
        Upsert embedded chunks into the collection.

        ChromaDB upsert is idempotent — same ID overwrites, no duplicates.
        Because ChromaDB doesn't distinguish inserts from updates in its
        return value, inserted=total and updated=0 is an approximation.
        """
        items = [ec.chunk for ec in chunks]
        embeddings = [ec.embedding for ec in chunks]
        total = self._store.upsert(self._collection, items, embeddings)
        return UpsertResult(inserted=total, updated=0, errors=0)

    async def query(
        self,
        embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """
        Query by vector similarity, returning top_k results.

        Score is cosine similarity in [-1, 1]; higher = more similar.
        Converted from ChromaDB's cosine distance via: similarity = 1 - distance.
        This normalization makes score direction consistent with MilvusVectorStore.
        """
        results = self._store.query(
            self._collection,
            query_embedding=embedding,
            n_results=top_k,
            where=filters,
        )
        return [
            SearchResult(
                chunk=Chunk(
                    id=r["id"],
                    text=r["document"],
                    metadata=r["metadata"],
                ),
                # ChromaDB cosine distance ∈ [0, 2]; similarity = 1 − distance
                score=1.0 - r["distance"],
            )
            for r in results
        ]

    async def delete(self, ids: list[str]) -> None:
        """Delete chunks by ID."""
        self._collection.delete(ids=ids)

    async def count(self) -> int:
        """Return the number of chunks in the collection."""
        return self._collection.count()
