"""
Embeddable protocol — the contract between pipeline stages and the vector index.

The ChromaDB store layer depends ONLY on this protocol. It never imports Chunk
or AtomicNote directly. This ensures both types flow through the same indexer
without any changes to store.py when AtomicNote is introduced in v0.7.0.

Implementing types (current and planned):
  - Chunk       (membuilder/parser/models.py)    ← v0.3.0
  - AtomicNote  (membuilder/synthesizer/models.py) ← v0.7.0

Contract:
  id       — stable, unique identifier; used as the ChromaDB document ID.
             Must be deterministic so re-indexing the same content produces
             the same ID, enabling safe idempotent upsert.

  text     — the string to embed. Should be semantically rich — typically
             a composite of heading + content, optionally breadcrumb-prefixed.
             Embedder will truncate if needed; the property should return full text.

  metadata — flat dict of scalar values only (str, int, float, bool).
             ChromaDB does not support nested objects or lists.
             Lists (e.g. breadcrumb) must be joined to a string before returning.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embeddable(Protocol):
    """
    Structural protocol for objects that can be embedded and stored in the
    vector index. Uses runtime_checkable so isinstance() works for validation.
    """

    @property
    def id(self) -> str:
        """Stable unique identifier (used as ChromaDB document ID)."""
        ...

    @property
    def text(self) -> str:
        """
        Full text to embed. Semantically rich composite — heading, breadcrumb,
        and content. The Embedder handles truncation; this property returns
        the complete string.
        """
        ...

    @property
    def metadata(self) -> dict:
        """
        Flat scalar metadata for ChromaDB filtering and retrieval context.
        No nested dicts, no lists — ChromaDB requires scalar values only.
        """
        ...
