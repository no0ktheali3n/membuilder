"""
MilvusVectorStore — adapter implementing the VectorStore protocol on top of
Milvus / Milvus Lite.

Supports both local (Milvus Lite, embedded, no server) and server deployments
via the same MilvusClient API. Switch is transparent via the uri parameter.

Local:  MilvusVectorStore(uri="./data/milvus.db")
Server: MilvusVectorStore(uri="http://localhost:19530")

Score direction (v0.3.1):
    Collection uses metric_type="COSINE". Milvus COSINE search returns cosine
    similarity directly in [-1, 1], where higher = more similar. This matches
    ChromaVectorStore's normalized score, making SearchResult.score direction
    consistent across both backends.

Requires: pymilvus >= 2.4.0  (includes Milvus Lite)
"""

from __future__ import annotations

from pymilvus import MilvusClient

from membuilder.protocols import (
    EmbeddedChunk,
    SearchResult,
    UpsertResult,
    Chunk,
)


def _serialize_metadata(metadata: dict) -> dict:
    """
    Flatten list values to comma-joined strings for Milvus compatibility.

    Milvus dynamic fields don't support list types with the simple schema API.
    breadcrumb and tags are list[str] at the protocol level; this function
    converts them to strings only at write time. The Chunk itself is unchanged.
    """
    out = {}
    for k, v in metadata.items():
        if isinstance(v, list):
            out[k] = ",".join(str(s) for s in v)
        else:
            out[k] = v
    return out


class MilvusVectorStore:
    """
    VectorStore adapter backed by Milvus / Milvus Lite.

    Supports both Milvus Lite (local, embedded) and full Milvus server.

    Local:  MilvusVectorStore(uri="./data/milvus.db")
    Server: MilvusVectorStore(uri="http://localhost:19530")

    SearchResult.score is cosine similarity in [-1, 1], higher = more similar.
    Consistent with ChromaVectorStore so the Retriever needs no per-backend logic.

    Args:
        uri:             Milvus connection URI. A file path (ending in .db)
                         uses Milvus Lite; an http:// URI connects to a server.
        collection_name: Name of the Milvus collection to use.
        dimension:       Embedding vector dimension. Must match the model used.
    """

    def __init__(self, uri: str, collection_name: str, dimension: int) -> None:
        self.client = MilvusClient(uri=uri)
        self.collection_name = collection_name
        self.dimension = dimension
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """
        Create the collection if it does not exist.

        Uses:
          - VARCHAR primary key ("id") to store deterministic sha256 chunk IDs
          - COSINE metric so scores are cosine similarity (higher = more similar),
            matching ChromaVectorStore's normalized score direction
        """
        if not self.client.has_collection(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                dimension=self.dimension,
                id_type="string",       # chunk IDs are sha256[:16] hex strings
                max_length=64,
                metric_type="COSINE",  # scores will be cosine similarity ∈ [-1, 1]
            )

    async def upsert(self, chunks: list[EmbeddedChunk]) -> UpsertResult:
        """Upsert embedded chunks into the Milvus collection."""
        data = [
            {
                "id": c.chunk.id,
                "vector": c.embedding,
                **_serialize_metadata(c.chunk.metadata),  # flatten lists → strings
                "text": c.chunk.text,
            }
            for c in chunks
        ]
        result = self.client.upsert(
            collection_name=self.collection_name,
            data=data,
        )
        # pymilvus may return an object with attributes or a dict depending on version
        if isinstance(result, dict):
            inserted = result.get("insert_count", 0)
            updated = result.get("upsert_count", 0)
        else:
            inserted = getattr(result, "insert_count", 0)
            updated = getattr(result, "upsert_count", 0)
        return UpsertResult(inserted=inserted, updated=updated, errors=0)

    async def query(
        self,
        embedding: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """
        Query by vector similarity, returning top_k results.

        Score is cosine similarity in [-1, 1]; higher = more similar.
        Milvus COSINE metric returns similarity directly — no conversion needed.
        """
        results = self.client.search(
            collection_name=self.collection_name,
            data=[embedding],
            limit=top_k,
            output_fields=["text", "url", "breadcrumb", "chunk_index"],
            filter=self._build_filter(filters) if filters else None,
        )
        return [
            SearchResult(
                chunk=Chunk(
                    id=r["id"],
                    text=r["entity"].get("text", ""),
                    metadata={k: v for k, v in r["entity"].items() if k != "text"},
                ),
                score=r["distance"],  # COSINE metric → already similarity, higher = better
            )
            for r in results[0]
        ]

    async def delete(self, ids: list[str]) -> None:
        """Delete chunks by ID."""
        self.client.delete(collection_name=self.collection_name, ids=ids)

    async def count(self) -> int:
        """Return the number of chunks in the collection."""
        return self.client.get_collection_stats(self.collection_name)["row_count"]

    def _build_filter(self, filters: dict) -> str:
        """
        Build a Milvus filter expression from a key/value dict.

        e.g. {"url": "https://example.com"} → 'url == "https://example.com"'
        Multiple keys are joined with AND.
        """
        clauses = [f'{k} == "{v}"' for k, v in filters.items()]
        return " and ".join(clauses)
