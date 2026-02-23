"""
Crawler — uses crawl4ai to recursively crawl a documentation site.

Key behaviours:
  - BFS crawl, stays within the seed URL's domain + path prefix
  - Converts each page to clean markdown via crawl4ai
  - Checkpoints every page to disk immediately after fetch (resume-safe)
  - Skips already-seen URLs on resume
  - Configurable concurrency + rate limiting
  - Rich progress output
"""

import asyncio
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .checkpoint import CheckpointManager
from .models import CrawledPage

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(url: str) -> str:
    """Turn a URL into a safe filename for the run_id."""
    return re.sub(r"[^\w]", "_", urlparse(url).netloc + urlparse(url).path)[:80]


def _extract_title(result) -> str:
    """Extract title from first H1/H2 in markdown, fall back to URL."""
    # Try markdown headings first — works even when css_selector strips <head>
    if result.markdown:
        md = result.markdown.raw_markdown or ""
        match = re.search(r"^#{1,2}\s+(.+?)(?:\s*\[[\s\S]*)?$", md, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return result.url


def _is_in_scope(url: str, base_url: str) -> bool:
    """
    Only follow links that share the same domain and path prefix as the seed URL.
    Blocks anchors, external domains, and file downloads.
    """
    parsed = urlparse(url)
    base = urlparse(base_url)

    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc != base.netloc:
        return False

    # Scope root is the seed path itself — ensure it ends with /
    scope_root = base.path if base.path.endswith("/") else base.path + "/"
    if not parsed.path.startswith(scope_root):
        return False

    # Skip print views and binary files
    if re.search(r"(_print|\.pdf|\.zip|\.tar|\.gz|\.png|\.jpg|\.svg|\.css|\.js)$", parsed.path, re.I):
        return False

    return True


def _normalise(url: str) -> str:
    """Strip fragments and trailing slashes for dedup."""
    p = urlparse(url)
    clean = p._replace(fragment="", query="")
    return clean.geturl().rstrip("/")


def _extract_links(result, base_url: str) -> list[str]:
    """Pull in-scope links out of crawl4ai result."""
    links: set[str] = set()

    raw_links = []
    if result.links:
        raw_links += [l.get("href", "") for l in result.links.get("internal", [])]

    for href in raw_links:
        if not href:
            continue
        absolute = urljoin(base_url, href)
        normalised = _normalise(absolute)
        if _is_in_scope(normalised, base_url):
            links.add(normalised)

    return list(links)


# ---------------------------------------------------------------------------
# Main Crawler
# ---------------------------------------------------------------------------

class DocCrawler:
    def __init__(
        self,
        checkpoint_dir: str | Path = "data/checkpoints",
        max_pages: int = 2000,
        concurrency: int = 5,
        rate_limit_delay: float = 0.5,   # seconds between batches
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.max_pages = max_pages
        self.concurrency = concurrency
        self.rate_limit_delay = rate_limit_delay

    async def crawl(self, seed_url: str) -> list[CrawledPage]:
        """
        Crawl from seed_url. Returns all successfully crawled pages.
        Resumes automatically if a checkpoint file already exists.
        """
        seed_url = _normalise(seed_url)
        run_id = _slugify(seed_url)
        checkpoint = CheckpointManager(self.checkpoint_dir, run_id)

        # Seed the queue — skip if already crawled in a previous run
        queue: list[tuple[str, int]] = []  # (url, depth)
        if not checkpoint.already_crawled(seed_url):
            queue.append((seed_url, 0))
        else:
            console.print(f"[yellow]Resuming crawl — {len(checkpoint.seen_urls)} pages already checkpointed.[/yellow]")

        enqueued: set[str] = set(checkpoint.seen_urls)
        enqueued.add(seed_url)

        browser_cfg = BrowserConfig(headless=True, verbose=False)
        run_cfg = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            markdown_generator=DefaultMarkdownGenerator(),
            wait_until="domcontentloaded",
            page_timeout=30000,
            css_selector=".td-content",  # Optional: focus on main content if site structure allows
        )

        total_crawled = len(checkpoint.seen_urls)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Crawling {seed_url}", total=self.max_pages, completed=total_crawled
            )

            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                while queue and total_crawled < self.max_pages:
                    # Take a batch
                    batch = queue[:self.concurrency]
                    queue = queue[self.concurrency:]

                    results = await asyncio.gather(
                        *[crawler.arun(url=url, config=run_cfg) for url, _ in batch],
                        return_exceptions=True,
                    )

                    for (url, depth), result in zip(batch, results):
                        if isinstance(result, Exception):
                            page = CrawledPage(
                                url=url,
                                title=url,
                                markdown="",
                                depth=depth,
                                status="failed",
                                error=str(result),
                            )
                            checkpoint.save(page)
                            progress.console.print(f"[red]  ✗ FAILED: {url}[/red]")
                            total_crawled += 1
                            progress.update(task, completed=total_crawled)
                            continue

                        if not result.success or not result.markdown:
                            page = CrawledPage(
                                url=url,
                                title=_extract_title(result),
                                markdown="",
                                depth=depth,
                                status="failed",
                                error="No markdown returned",
                            )
                            checkpoint.save(page)
                            total_crawled += 1
                            progress.update(task, completed=total_crawled)
                            continue

                        markdown = result.markdown.raw_markdown or result.markdown.fit_markdown or ""

                        page = CrawledPage(
                            url=url,
                            title=_extract_title(result),
                            markdown=markdown,
                            depth=depth,
                            status="ok",
                        )
                        checkpoint.save(page)
                        total_crawled += 1
                        progress.update(task, completed=total_crawled, description=f"Crawling … {url[-60:]}")

                        # Discover and enqueue new links
                        if total_crawled < self.max_pages:
                            new_links = _extract_links(result, seed_url)
                            for link in new_links:
                                if link not in enqueued:
                                    enqueued.add(link)
                                    queue.append((link, depth + 1))

                    # Rate limiting between batches
                    if queue:
                        await asyncio.sleep(self.rate_limit_delay)

        stats = checkpoint.stats()
        console.print(
            f"\n[green]✓ Crawl complete.[/green] "
            f"Pages: [bold]{stats['ok']}[/bold] ok, "
            f"[red]{stats['failed']}[/red] failed. "
            f"Checkpoint: {stats['path']}"
        )

        return [p for p in checkpoint.load_all() if p.status == "ok"]