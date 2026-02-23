from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CrawledPage:
    url: str
    title: str
    markdown: str
    crawled_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    depth: int = 0
    status: str = "ok"          # ok | failed | skipped
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "markdown": self.markdown,
            "crawled_at": self.crawled_at,
            "depth": self.depth,
            "status": self.status,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CrawledPage":
        return cls(**d)