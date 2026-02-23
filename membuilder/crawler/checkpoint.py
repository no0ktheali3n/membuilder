"""
Checkpoint manager — persists crawl state to JSONL so crawls can resume
after failure without re-fetching already-crawled pages.

File format: one JSON object per line, each representing a CrawledPage.
"""

import json
from pathlib import Path

from .models import CrawledPage


class CheckpointManager:
    def __init__(self, checkpoint_dir: str | Path, run_id: str):
        self.path = Path(checkpoint_dir) / f"{run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()
        self._load_existing()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def seen_urls(self) -> set[str]:
        return self._seen

    def already_crawled(self, url: str) -> bool:
        return url in self._seen

    def save(self, page: CrawledPage) -> None:
        """Append a single page to the checkpoint file atomically."""
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(page.to_dict(), ensure_ascii=False) + "\n")
        self._seen.add(page.url)

    def load_all(self) -> list[CrawledPage]:
        """Read all checkpointed pages — used by downstream pipeline stages."""
        if not self.path.exists():
            return []
        pages = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    pages.append(CrawledPage.from_dict(json.loads(line)))
        return pages

    def stats(self) -> dict:
        pages = self.load_all()
        ok = sum(1 for p in pages if p.status == "ok")
        failed = sum(1 for p in pages if p.status == "failed")
        return {"total": len(pages), "ok": ok, "failed": failed, "path": str(self.path)}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_existing(self) -> None:
        """Populate seen_urls from an existing checkpoint file (resume support)."""
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            obj = json.loads(line)
                            self._seen.add(obj["url"])
                        except (json.JSONDecodeError, KeyError):
                            continue