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