"""
ChromaDB vector store interface — collection-agnostic, protocol-driven.

Depends on the Embeddable protocol only. Never imports Chunk or AtomicNote.
Both v0.3.0 (Chunk) and v0.7.0 (AtomicNote) flow through this interface
without any changes to this file.

Design decisions:
  - Upsert is always used instead of add: re-running index.py on the same
    chunk file is safe and idempotent (same ID = overwrite, not duplicate).
  - Collection metadata stores the embedding_model string so inspect_index.py
    can embed queries with the correct model without the user specifying it.
  - HNSW cosine similarity: semantically appropriate for text embeddings.
  - Upserts are batched at CHROMA_UPSERT_BATCH to avoid memory issues on
    large corpora (ChromaDB has undocumented batch size limits in practice).

Usage:
    store = VectorStore(path="data/chroma")
    col = store.get_or_create_collection("k8s-chunks", embedding_model="text-embedding-3-small")
    store.upsert(col, chunks, embeddings)
    results = store.query(col, query_vec, n_results=5)
"""

from collections.abc import Sequence
from pathlib import Path

import chromadb
from chromadb.config import Settings

from membuilder.config import EMBEDDING_MODEL
from membuilder.index.protocol import Embeddable

# ChromaDB upsert batch ceiling. Stay well below any undocumented limits;
# 500 is reliable across all corpus sizes we expect.
CHROMA_UPSERT_BATCH = 500


class VectorStore:
    """
    Thin wrapper around a ChromaDB PersistentClient.

    One VectorStore instance maps to one on-disk Chroma directory. Multiple
    collections (one per domain build) can live in the same directory.

    Args:
        path: Directory for ChromaDB persistence (created if absent).
    """

    def __init__(self, path: str = "data/chroma") -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.path),
            settings=Settings(anonymized_telemetry=False),
        )

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def get_or_create_collection(
        self,
        name: str,
        embedding_model: str = EMBEDDING_MODEL,
    ) -> chromadb.Collection:
        """
        Get or create a named collection.

        Stores embedding_model in collection metadata so the inspect script
        can later embed queries using the same model without user input.
        Uses cosine distance — appropriate for normalised text embeddings.

        Args:
            name:            Collection name (must be valid ChromaDB identifier).
            embedding_model: LiteLLM model string used for embeddings.
        """
        return self.client.get_or_create_collection(
            name=name,
            metadata={
                "embedding_model": embedding_model,
                "hnsw:space": "cosine",
            },
        )

    def get_collection(self, name: str) -> chromadb.Collection:
        """Get an existing collection by name. Raises if not found."""
        return self.client.get_collection(name=name)

    def list_collections(self) -> list[str]:
        """Return names of all collections in this store."""
        return [c.name for c in self.client.list_collections()]

    def collection_info(self, collection: chromadb.Collection) -> dict:
        """Return stats dict: name, count, metadata."""
        return {
            "name": collection.name,
            "count": collection.count(),
            "metadata": collection.metadata or {},
        }

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert(
        self,
        collection: chromadb.Collection,
        items: Sequence[Embeddable],
        embeddings: list[list[float]],
    ) -> int:
        """
        Upsert items and their embeddings into ChromaDB.

        Idempotent: re-running with the same IDs overwrites existing records
        rather than creating duplicates. Safe to call repeatedly on the same
        chunk file.

        Args:
            collection: Target ChromaDB collection.
            items:      Sequence of Embeddable objects (in same order as embeddings).
            embeddings: Pre-computed embedding vectors.

        Returns:
            Total number of items upserted.

        Raises:
            AssertionError: If items and embeddings lengths differ.
        """
        if len(items) != len(embeddings):
            raise ValueError(
                f"items ({len(items)}) and embeddings ({len(embeddings)}) must be same length"
            )

        total = 0
        for i in range(0, len(items), CHROMA_UPSERT_BATCH):
            batch_items = items[i : i + CHROMA_UPSERT_BATCH]
            batch_embs = embeddings[i : i + CHROMA_UPSERT_BATCH]

            collection.upsert(
                ids=[item.id for item in batch_items],
                embeddings=batch_embs,
                documents=[item.text for item in batch_items],
                metadatas=[item.metadata for item in batch_items],
            )
            total += len(batch_items)

        return total

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        collection: chromadb.Collection,
        query_embedding: list[float],
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        """
        Query the collection by vector similarity.

        Args:
            collection:      ChromaDB collection to query.
            query_embedding: Pre-computed query vector (embed with same model).
            n_results:       Number of results to return.
            where:           Optional ChromaDB metadata filter dict.

        Returns:
            List of result dicts, sorted by ascending distance (most similar first):
              {id, document, metadata, distance}
            Distance is cosine distance [0, 2]; lower = more similar.
            Semantic similarity ≈ 1 - (distance / 2) for cosine.
        """
        kwargs: dict = dict(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where

        raw = collection.query(**kwargs)

        return [
            {
                "id": doc_id,
                "document": raw["documents"][0][i],
                "metadata": raw["metadatas"][0][i],
                "distance": raw["distances"][0][i],
            }
            for i, doc_id in enumerate(raw["ids"][0])
        ]
