"""
CLI: embed chunks and index into ChromaDB.

Reads the most recent chunk JSONL from data/chunks/, embeds each chunk via
LiteLLM, and upserts into a ChromaDB persistent collection. Re-running on
the same file is safe and idempotent — existing records are overwritten by ID,
not duplicated.

Usage:
    uv run python scripts/index.py
    uv run python scripts/index.py --model text-embedding-3-small
    uv run python scripts/index.py --model ollama/nomic-embed-text
    uv run python scripts/index.py --chunks-dir data/chunks --chroma-dir data/chroma
    uv run python scripts/index.py --collection my-collection
    uv run python scripts/index.py --dry-run
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.rule import Rule

from membuilder.config import EMBEDDING_MODEL
from membuilder.index.embedder import Embedder
from membuilder.index.store import VectorStore
from membuilder.parser.models import Chunk

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_collection_name(name: str) -> str:
    """
    Ensure the collection name is a valid ChromaDB identifier:
    3-63 chars, alphanumeric + hyphens/underscores, start/end alphanumeric.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    sanitized = sanitized.strip("-_")
    sanitized = sanitized[:63]
    if len(sanitized) < 3:
        sanitized = sanitized + "-index"
    return sanitized


def load_chunks(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(Chunk.from_dict(json.loads(line)))
    return chunks


# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Embed chunks and index into ChromaDB."
    )
    parser.add_argument(
        "--chunks-dir",
        default="data/chunks",
        help="Directory containing chunk JSONL files (default: data/chunks)",
    )
    parser.add_argument(
        "--chroma-dir",
        default="data/chroma",
        help="ChromaDB persistence directory (default: data/chroma)",
    )
    parser.add_argument(
        "--model",
        default=EMBEDDING_MODEL,
        help=(
            "LiteLLM embedding model string "
            f"(default from MEMBUILDER_EMBEDDING_MODEL env var: {EMBEDDING_MODEL!r})"
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Embedding batch size per API call (default: 200)",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="ChromaDB collection name (default: derived from chunk filename)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show cost estimate and exit without embedding or writing to ChromaDB",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    console.print()
    console.print(Rule("[bold cyan]membuilder indexer[/bold cyan]"))

    # --- Locate chunk file ---------------------------------------------------
    chunks_dir = Path(args.chunks_dir)
    files = sorted(chunks_dir.glob("*.jsonl"))
    if not files:
        console.print(f"[red]No chunk files found in {chunks_dir}[/red]")
        sys.exit(1)

    chunks_path = files[-1]
    run_id = chunks_path.stem  # e.g. "kubernetes-io_2026-02-23_chunks"

    # Derive collection name: strip trailing "_chunks" if present, sanitize
    default_collection = sanitize_collection_name(
        run_id.removesuffix("_chunks")
    )
    collection_name = sanitize_collection_name(
        args.collection if args.collection else default_collection
    )

    console.print(f"  Chunks file  : {chunks_path}")
    console.print(f"  Model        : {args.model}")
    console.print(f"  Chroma dir   : {args.chroma_dir}")
    console.print(f"  Collection   : {collection_name}")
    console.print()

    # --- Load chunks ---------------------------------------------------------
    console.print("  Loading chunks...", end=" ")
    chunks = load_chunks(chunks_path)
    console.print(f"[green]{len(chunks):,} chunks loaded[/green]")

    # --- Cost estimate -------------------------------------------------------
    embedder = Embedder(model=args.model, batch_size=args.batch_size)
    estimate = embedder.cost_estimate(chunks)

    console.print()
    console.print("  [bold]Cost estimate:[/bold]")
    console.print(f"    Total text    : {estimate['total_chars']:,} chars")
    console.print(f"    Est. tokens   : {estimate['estimated_tokens']:,}")
    if estimate["cost_known"]:
        console.print(
            f"    Est. cost     : [green]${estimate['estimated_cost_usd']:.4f} USD[/green]"
            f"  ({args.model})"
        )
    else:
        console.print(
            f"    Est. cost     : [yellow]unknown model — no cost data for '{args.model}'[/yellow]"
        )
    console.print()

    if args.dry_run:
        console.print("[yellow]--dry-run: stopping before embedding. No API calls made.[/yellow]")
        console.print()
        sys.exit(0)

    # --- Check for existing collection ---------------------------------------
    store = VectorStore(path=args.chroma_dir)
    existing = store.list_collections()
    if collection_name in existing:
        existing_col = store.get_collection(collection_name)
        existing_count = existing_col.count()
        console.print(
            f"  [yellow]⚠  Collection '{collection_name}' already exists "
            f"({existing_count:,} records). Upserting — existing records will be "
            f"overwritten by ID, not duplicated.[/yellow]"
        )
        console.print()

    # --- Embed ---------------------------------------------------------------
    console.print("  [bold]Embedding:[/bold]")
    t0 = time.monotonic()
    embeddings = embedder.embed_many(chunks, console=console)
    elapsed_embed = time.monotonic() - t0
    console.print(
        f"\n  [green]✓ {len(embeddings):,} embeddings generated "
        f"in {elapsed_embed:.1f}s[/green]"
    )
    console.print()

    # --- Upsert to ChromaDB --------------------------------------------------
    console.print("  [bold]Writing to ChromaDB:[/bold]")
    t1 = time.monotonic()
    collection = store.get_or_create_collection(
        name=collection_name,
        embedding_model=args.model,
    )
    upserted = store.upsert(collection, chunks, embeddings)
    elapsed_store = time.monotonic() - t1

    info = store.collection_info(collection)
    console.print(
        f"  [green]✓ {upserted:,} records upserted in {elapsed_store:.1f}s[/green]"
    )
    console.print(f"  Collection total: [bold]{info['count']:,}[/bold] records")
    console.print(f"  Chroma path     : {Path(args.chroma_dir).resolve()}")
    console.print()

    total_elapsed = time.monotonic() - t0
    console.print(Rule(f"[dim]Done in {total_elapsed:.1f}s[/dim]"))
    console.print()


if __name__ == "__main__":
    main()
