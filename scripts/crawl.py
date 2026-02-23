"""
CLI: run a crawl and checkpoint results to disk.

Usage:
    uv run python scripts/crawl.py https://kubernetes.io/docs/home/
    uv run python scripts/crawl.py https://kubernetes.io/docs/home/ --max-pages 50 --concurrency 3
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from membuilder.crawler.crawler import DocCrawler
from rich.console import Console

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(description="Crawl a documentation site.")
    parser.add_argument("url", help="Seed URL to crawl from")
    parser.add_argument("--max-pages", type=int, default=2000, help="Max pages to crawl (default: 2000)")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent requests (default: 5)")
    parser.add_argument("--rate-limit", type=float, default=0.5, help="Delay between batches in seconds (default: 0.5)")
    parser.add_argument("--checkpoint-dir", default="data/checkpoints", help="Checkpoint directory")
    return parser.parse_args()


async def main():
    args = parse_args()

    console.print(f"\n[bold cyan]membuilder crawler[/bold cyan]")
    console.print(f"  Seed URL   : [link]{args.url}[/link]")
    console.print(f"  Max pages  : {args.max_pages}")
    console.print(f"  Concurrency: {args.concurrency}")
    console.print(f"  Rate limit : {args.rate_limit}s between batches\n")

    crawler = DocCrawler(
        checkpoint_dir=args.checkpoint_dir,
        max_pages=args.max_pages,
        concurrency=args.concurrency,
        rate_limit_delay=args.rate_limit,
    )

    pages = await crawler.crawl(args.url)

    console.print(f"\n[bold]Sample output — first 3 pages:[/bold]")
    for page in pages[:3]:
        console.print(f"\n  [cyan]{page.title}[/cyan]")
        console.print(f"  URL   : {page.url}")
        console.print(f"  Depth : {page.depth}")
        console.print(f"  Length: {len(page.markdown):,} chars")
        console.print(f"  Preview: {page.markdown[:200].strip()!r}")


if __name__ == "__main__":
    asyncio.run(main())
