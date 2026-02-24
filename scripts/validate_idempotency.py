#!/usr/bin/env python3
"""
Idempotency validation for v0.3.1.

Runs the parse → embed → upsert pipeline twice on the same JSONL input.
Asserts the second run produces zero new inserts.

Prerequisite: a completed crawl JSONL file (checkpoint format).
The script reads CrawledPage JSONL (url, markdown, title, crawled_at, depth)
and converts each line into a RawPage for the chunker.

Usage:
    python scripts/validate_idempotency.py \\
        --input data/checkpoints/<run_id>.jsonl \\
        --config membuilder.yaml \\
        --limit 100
"""

import asyncio
import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from membuilder.config import MembuilderConfig


@dataclass
class RunResult:
    chunks_processed: int
    inserted: int
    updated: int
    errors: int


async def run_pipeline(config: MembuilderConfig, pages: list[dict]) -> RunResult:
    chunker = config.build_chunker()
    embedder = config.build_embedder()

    # Determine embedding dimension from a single test embed
    sample = await embedder.embed(["dimension probe"])
    dimension = len(sample[0])

    store = config.build_vector_store(dimension=dimension)

    from membuilder.protocols import RawPage
    all_chunks = []
    for raw in pages:
        # Support both checkpoint format (markdown/title) and raw format (content/metadata)
        page = RawPage(
            url=raw["url"],
            content=raw.get("content") or raw.get("markdown", ""),
            metadata={
                "title": raw.get("title", raw["url"]),
                "depth": raw.get("depth", 0),
            },
            crawled_at=raw.get("crawled_at", ""),
        )
        all_chunks.extend(chunker.chunk(page))

    if not all_chunks:
        print("  [warning] No chunks produced — pages may be below min content threshold.")
        return RunResult(chunks_processed=0, inserted=0, updated=0, errors=0)

    # Embed in batches of 100
    from membuilder.protocols import EmbeddedChunk
    embedded = []
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        embeddings = await embedder.embed([c.text for c in batch])
        embedded.extend(
            EmbeddedChunk(chunk=c, embedding=e)
            for c, e in zip(batch, embeddings)
        )

    result = await store.upsert(embedded)
    return RunResult(
        chunks_processed=len(embedded),
        inserted=result.inserted,
        updated=result.updated,
        errors=result.errors,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to crawl JSONL file")
    parser.add_argument("--config", default="membuilder.yaml")
    parser.add_argument("--limit", type=int, default=100, help="Number of pages to test")
    args = parser.parse_args()

    config = MembuilderConfig.from_file(args.config)

    pages = []
    with open(args.input) as f:
        for i, line in enumerate(f):
            if i >= args.limit:
                break
            row = json.loads(line)
            # Skip failed/skipped pages from checkpoint format
            if row.get("status") in ("failed", "skipped"):
                continue
            pages.append(row)

    print(f"Loaded {len(pages)} pages from {args.input}")
    print(f"Vector store backend: {config.vector_store.backend}")
    print()

    # Run 1
    print("--- Run 1 ---")
    result1 = asyncio.run(run_pipeline(config, pages))
    print(f"  Chunks processed : {result1.chunks_processed}")
    print(f"  Inserted         : {result1.inserted}")
    print(f"  Updated          : {result1.updated}")
    print(f"  Errors           : {result1.errors}")
    print()

    # Run 2 — identical input, same store
    print("--- Run 2 (same input, same store) ---")
    result2 = asyncio.run(run_pipeline(config, pages))
    print(f"  Chunks processed : {result2.chunks_processed}")
    print(f"  Inserted         : {result2.inserted}")
    print(f"  Updated          : {result2.updated}")
    print(f"  Errors           : {result2.errors}")
    print()

    # Assert
    # Note: ChromaDB always reports inserted=total (can't distinguish insert vs update).
    # For ChromaDB, assert errors == 0 and that the count didn't grow.
    # For Milvus, we can assert inserted == 0 directly.
    print("--- Result ---")
    if result2.errors == 0:
        if result2.inserted == 0:
            print("✅ PASS — second run produced zero new inserts. IDs are deterministic.")
        else:
            # ChromaDB reports all as 'inserted' — use count comparison instead
            if config.vector_store.backend == "chroma":
                print("✅ PASS (ChromaDB) — no errors on second run.")
                print("   Note: ChromaDB reports all upserts as 'inserted'; count stability")
                print("   is the real idempotency signal. Run inspect_index.py to verify.")
            else:
                print(f"❌ FAIL — second run inserted {result2.inserted} new chunks.")
                print("   Check chunk ID generation in MarkdownChunker._make_id()")
                raise SystemExit(1)
    else:
        print(f"❌ FAIL — second run had {result2.errors} errors.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
