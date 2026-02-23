from dataclasses import dataclass, field
import hashlib


@dataclass
class Chunk:
    chunk_id: str           # deterministic hash of source_url + chunk_index
    source_url: str
    page_title: str
    heading: str            # nearest heading above this chunk
    breadcrumb: list[str]   # ["Concepts", "Workloads", "Pods"]
    content: str
    chunk_index: int        # position within the source page
    total_chunks: int       # total chunks for this page
    depth: int              # crawl depth of source page
    crawled_at: str

    # ------------------------------------------------------------------
    # Embeddable protocol implementation (membuilder/index/protocol.py)
    # The index layer depends on these three properties only — never on
    # the Chunk dataclass directly. AtomicNote (v0.7.0) will implement
    # the same protocol, flowing through the same indexer unchanged.
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        """Stable unique ID for ChromaDB (same as chunk_id)."""
        return self.chunk_id

    @property
    def text(self) -> str:
        """
        Composite embedding text: breadcrumb path + heading + content.

        Providing hierarchical context alongside the raw content gives the
        embedding model richer signal — "Concepts > Workloads > Pods" +
        "Pod Lifecycle" + body text embeds more distinctly than body text alone.
        """
        parts: list[str] = []
        if self.breadcrumb:
            parts.append(" > ".join(self.breadcrumb))
        if self.heading:
            parts.append(self.heading)
        parts.append(self.content)
        return "\n\n".join(parts)

    @property
    def metadata(self) -> dict:
        """
        Flat scalar metadata dict for ChromaDB storage and filtering.

        ChromaDB requires all metadata values to be scalar (str, int, float,
        bool). breadcrumb (list[str]) is joined to a single string here.
        """
        return {
            "source_url": self.source_url,
            "page_title": self.page_title,
            "heading": self.heading,
            "breadcrumb": " > ".join(self.breadcrumb),
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "depth": self.depth,
            "crawled_at": self.crawled_at,
        }

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_url": self.source_url,
            "page_title": self.page_title,
            "heading": self.heading,
            "breadcrumb": self.breadcrumb,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "depth": self.depth,
            "crawled_at": self.crawled_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        return cls(**d)


def make_chunk_id(source_url: str, chunk_index: int) -> str:
    raw = f"{source_url}::{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()