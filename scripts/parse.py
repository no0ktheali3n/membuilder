"""
CLI: parse checkpoint into structured chunks and save to disk.

Usage:
    uv run python scripts/parse.py
    uv run python scripts/parse.py --checkpoint-dir data/checkpoints --output-dir data/chunks
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from membuilder.crawler.checkpoint import CheckpointManager
from membuilder.parser.chunker import chunk_pages
from rich.console import Console

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(description="Parse crawl checkpoint into chunks.")
    parser.add_argument("--checkpoint-dir", default="data/checkpoints")
    parser.add_argument("--output-dir", default="data/chunks")
    return parser.parse_args()


def main():
    args = parse_args()

    checkpoint_dir = Path(args.checkpoint_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find most recent checkpoint
    files = sorted(checkpoint_dir.glob("*.jsonl"))
    if not files:
        console.print("[red]No checkpoint files found.[/red]")
        sys.exit(1)

    checkpoint_path = files[-1]
    run_id = checkpoint_path.stem
    console.print(f"\n[bold cyan]membuilder parser[/bold cyan]")
    console.print(f"  Checkpoint : {checkpoint_path}")

    # Load pages
    from membuilder.crawler.models import CrawledPage
    pages = []
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                p = CrawledPage.from_dict(__import__("json").loads(line))
                if p.status == "ok":
                    pages.append(p)

    console.print(f"  Pages loaded: {len(pages)}\n")

    # Chunk
    chunks = chunk_pages(pages)

    # Save to JSONL
    output_path = output_dir / f"{run_id}_chunks.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")

    console.print(f"\n[bold]Chunks saved to:[/bold] {output_path}")
    console.print(f"\n[bold]Sample — first 3 chunks:[/bold]")
    for chunk in chunks[:3]:
        console.print(f"\n  [cyan]{chunk.heading}[/cyan]")
        console.print(f"  Page    : {chunk.page_title}")
        console.print(f"  URL     : {chunk.source_url}")
        console.print(f"  Crumb   : {' > '.join(chunk.breadcrumb)}")
        console.print(f"  Chunk   : {chunk.chunk_index + 1}/{chunk.total_chunks}")
        console.print(f"  Length  : {len(chunk.content):,} chars")
        console.print(f"  Preview : {chunk.content[:200].strip()!r}")


if __name__ == "__main__":
    main()