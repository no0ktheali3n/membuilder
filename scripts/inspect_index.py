"""
CLI: inspect and validate a ChromaDB index before query layer development.

Runs three checks:
  1. Collection stats — record count, embedding model, sample IDs.
  2. Coverage report — compares indexed count against source chunk file.
  3. Retrieval spot-check — embeds 5 sample queries, shows top-3 results
     with similarity scores. This is the primary quality signal: if semantically
     similar results surface for each query, retrieval is coherent.

Usage:
    uv run python scripts/inspect_index.py
    uv run python scripts/inspect_index.py --collection my-collection
    uv run python scripts/inspect_index.py --chroma-dir data/chroma --chunks-dir data/chunks
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from membuilder.config import EMBEDDING_MODEL
from membuilder.index.embedder import Embedder
from membuilder.index.store import VectorStore

console = Console()

# ---------------------------------------------------------------------------
# Spot-check queries
# These are deliberately varied: conceptual, procedural, and reference.
# Semantic coherence test: top results should visibly relate to the query.
# ---------------------------------------------------------------------------
SPOT_CHECK_QUERIES = [
    "What is a Pod and how does it run containers?",
    "How does horizontal pod autoscaling work?",
    "Explain Kubernetes resource limits and requests for CPU and memory",
    "How do ConfigMaps and Secrets differ in how they store configuration?",
    "What happens to a Pod during a rolling deployment update?",
]


# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Inspect a ChromaDB index: stats, coverage, retrieval spot-check."
    )
    parser.add_argument(
        "--chroma-dir",
        default="data/chroma",
        help="ChromaDB directory (default: data/chroma)",
    )
    parser.add_argument(
        "--chunks-dir",
        default="data/chunks",
        help="Chunk JSONL directory for coverage comparison (default: data/chunks)",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Collection name to inspect (default: most recently created)",
    )
    parser.add_argument(
        "--n-results",
        type=int,
        default=3,
        help="Top-N results to show per spot-check query (default: 3)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def cosine_similarity_from_distance(distance: float) -> float:
    """
    Convert ChromaDB cosine distance to similarity score [0, 1].
    ChromaDB cosine distance = 1 - cosine_similarity, so:
      similarity = 1 - distance
    (ChromaDB normalises cosine distance to [0, 1], not [0, 2])
    """
    return round(1.0 - distance, 4)


def score_bar(similarity: float, width: int = 20) -> str:
    """ASCII bar representing similarity score."""
    filled = round(similarity * width)
    return "█" * filled + "░" * (width - filled)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def section_stats(store: VectorStore, collection_name: str) -> dict:
    """Print collection stats. Returns info dict."""
    console.print(Rule("[bold]1. Collection Stats[/bold]"))
    console.print()

    try:
        col = store.get_collection(collection_name)
    except Exception as e:
        console.print(f"[red]✗ Collection '{collection_name}' not found: {e}[/red]")
        sys.exit(1)

    info = store.collection_info(col)
    meta = info["metadata"]

    console.print(f"  Collection    : [bold]{info['name']}[/bold]")
    console.print(f"  Records       : [bold]{info['count']:,}[/bold]")
    console.print(f"  Embed model   : {meta.get('embedding_model', '[yellow]unknown[/yellow]')}")
    console.print(f"  Distance fn   : {meta.get('hnsw:space', 'cosine')}")
    console.print()

    # Show 3 sample IDs
    sample = col.peek(limit=3)
    if sample["ids"]:
        console.print("  Sample IDs:")
        for sid in sample["ids"]:
            console.print(f"    {sid}")
        if sample["metadatas"]:
            first_meta = sample["metadatas"][0]
            console.print(f"\n  Sample metadata (first record):")
            for k, v in first_meta.items():
                console.print(f"    {k:<15} : {str(v)[:80]}")
    console.print()

    return info


def section_coverage(
    store: VectorStore,
    collection_name: str,
    chunks_dir: Path,
) -> tuple[int, int]:
    """
    Compare indexed record count against the source chunk file.
    Returns (indexed_count, expected_count).
    """
    console.print(Rule("[bold]2. Coverage Report[/bold]"))
    console.print()

    col = store.get_collection(collection_name)
    indexed_count = col.count()

    # Find most recent chunk file
    chunk_files = sorted(chunks_dir.glob("*.jsonl"))
    if not chunk_files:
        console.print(f"  [yellow]⚠  No chunk files found in {chunks_dir} — skipping coverage check[/yellow]")
        console.print()
        return indexed_count, 0

    chunk_path = chunk_files[-1]
    expected_count = sum(1 for line in chunk_path.open("r", encoding="utf-8") if line.strip())

    coverage_pct = (indexed_count / expected_count * 100) if expected_count else 0
    bar_len = round(coverage_pct / 5)  # out of 20
    bar = "█" * bar_len + "░" * (20 - bar_len)

    console.print(f"  Source file   : {chunk_path.name}")
    console.print(f"  Expected      : {expected_count:,} chunks")
    console.print(f"  Indexed       : {indexed_count:,} records")
    console.print(f"  Coverage      : {coverage_pct:.1f}%  {bar}")

    if indexed_count == 0:
        console.print("\n  [red]✗ CRITICAL: No records in collection. Run scripts/index.py first.[/red]")
    elif coverage_pct < 95:
        gap = expected_count - indexed_count
        console.print(f"\n  [yellow]⚠  {gap:,} chunks missing from index ({100 - coverage_pct:.1f}%). "
                      "Re-run index.py if this is unexpected.[/yellow]")
    else:
        console.print("\n  [green]✓ Coverage looks complete.[/green]")

    console.print()
    return indexed_count, expected_count


def section_spot_check(
    store: VectorStore,
    collection_name: str,
    n_results: int,
) -> list[bool]:
    """
    Run spot-check queries and display top results with similarity scores.
    Returns list of bool: True if results look semantically coherent (subjective).
    """
    console.print(Rule("[bold]3. Retrieval Spot-Check[/bold]"))
    console.print()

    # Get embedding model from collection metadata
    col = store.get_collection(collection_name)
    meta = col.metadata or {}
    embed_model = meta.get("embedding_model", EMBEDDING_MODEL)

    console.print(f"  Embedding queries with: [cyan]{embed_model}[/cyan]")
    console.print(f"  Showing top {n_results} results per query")
    console.print()

    embedder = Embedder(model=embed_model, batch_size=10)
    coherence_flags: list[bool] = []

    for q_idx, query in enumerate(SPOT_CHECK_QUERIES, start=1):
        console.print(f"  [bold cyan]Query {q_idx}/{len(SPOT_CHECK_QUERIES)}:[/bold cyan] {query}")

        try:
            query_vec = embedder.embed_query(query)
            results = store.query(col, query_vec, n_results=n_results)
        except Exception as e:
            console.print(f"    [red]✗ Query failed: {e}[/red]")
            coherence_flags.append(False)
            console.print()
            continue

        if not results:
            console.print("    [yellow]⚠  No results returned.[/yellow]")
            coherence_flags.append(False)
            console.print()
            continue

        # Display results table
        table = Table(
            show_header=True,
            header_style="bold",
            box=None,
            padding=(0, 2),
            show_edge=False,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Score", width=8)
        table.add_column("Bar", width=22)
        table.add_column("Heading", style="cyan", max_width=35)
        table.add_column("Page", style="dim", max_width=35)
        table.add_column("Breadcrumb", style="dim", max_width=30)

        for rank, result in enumerate(results, start=1):
            sim = cosine_similarity_from_distance(result["distance"])
            bar = score_bar(sim)
            m = result["metadata"]
            heading = (m.get("heading") or "—")[:35]
            page = (m.get("page_title") or "—")[:35]
            crumb = (m.get("breadcrumb") or "—")[:30]

            table.add_row(
                str(rank),
                f"{sim:.4f}",
                f"[green]{bar}[/green]",
                heading,
                page,
                crumb,
            )

        # Indent the table slightly
        console.print("  ", end="")
        console.print(table)

        # Show the top result's content preview
        top = results[0]
        preview = top["document"][:300].strip().replace("\n", " ")
        console.print(f"\n    [dim]Top result preview:[/dim]")
        console.print(f"    {preview!r}")
        console.print(f"    [dim]Source: {top['metadata'].get('source_url', '—')}[/dim]")
        console.print()

        # Heuristic coherence: top result similarity > 0.3 is a reasonable bar
        top_sim = cosine_similarity_from_distance(results[0]["distance"])
        coherence_flags.append(top_sim > 0.30)

    return coherence_flags


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    console.print()
    console.print(Rule("[bold cyan]membuilder inspect-index[/bold cyan]"))
    console.print()

    store = VectorStore(path=args.chroma_dir)

    # --- Resolve collection name -------------------------------------------
    collections = store.list_collections()
    if not collections:
        console.print(f"[red]No collections found in {args.chroma_dir}. Run scripts/index.py first.[/red]")
        sys.exit(1)

    if args.collection:
        collection_name = args.collection
        if collection_name not in collections:
            console.print(f"[red]Collection '{collection_name}' not found.[/red]")
            console.print(f"Available: {', '.join(collections)}")
            sys.exit(1)
    else:
        collection_name = collections[-1]
        if len(collections) > 1:
            console.print(
                f"  [dim]Multiple collections found. Using most recent: "
                f"[bold]{collection_name}[/bold][/dim]"
            )
            console.print(f"  [dim]All: {', '.join(collections)}[/dim]")
            console.print()

    # --- Run checks --------------------------------------------------------
    info = section_stats(store, collection_name)
    indexed_count, expected_count = section_coverage(
        store, collection_name, Path(args.chunks_dir)
    )

    if indexed_count == 0:
        console.print("[red]✗ No records to query. Aborting spot-check.[/red]")
        sys.exit(1)

    coherence_flags = section_spot_check(store, collection_name, args.n_results)

    # --- Verdict -----------------------------------------------------------
    console.print(Rule("[bold]Verdict[/bold]"))
    console.print()

    issues: list[str] = []
    warnings: list[str] = []

    if indexed_count == 0:
        issues.append("Collection is empty — run scripts/index.py first")
    elif expected_count > 0:
        coverage_pct = indexed_count / expected_count * 100
        if coverage_pct < 95:
            warnings.append(f"Coverage {coverage_pct:.1f}% — {expected_count - indexed_count:,} chunks missing")

    incoherent = sum(1 for f in coherence_flags if not f)
    if incoherent == len(SPOT_CHECK_QUERIES):
        issues.append("All spot-check queries returned low-similarity results — embedding or model may be misconfigured")
    elif incoherent > 0:
        warnings.append(f"{incoherent}/{len(SPOT_CHECK_QUERIES)} spot-check queries returned low similarity scores")

    if not issues and not warnings:
        console.print("  [bold green]✓ Index looks healthy — ready for query layer (v0.4.0).[/bold green]")
    elif not issues:
        console.print(f"  [yellow]⚠  {len(warnings)} warning(s):[/yellow]")
        for w in warnings:
            console.print(f"    - {w}")
        console.print("\n  [yellow]Likely safe to proceed — review warnings above.[/yellow]")
    else:
        console.print(f"  [red]✗  {len(issues)} critical issue(s):[/red]")
        for issue in issues:
            console.print(f"    - {issue}")
        if warnings:
            console.print(f"\n  [yellow]  + {len(warnings)} warning(s):[/yellow]")
            for w in warnings:
                console.print(f"    - {w}")

    console.print()


if __name__ == "__main__":
    main()
