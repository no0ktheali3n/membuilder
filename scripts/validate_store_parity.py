#!/usr/bin/env python3
"""
Store parity validation for v0.3.1.

Embeds the same data into ChromaDB and Milvus Lite, runs identical queries
against both, and compares top-k rankings. Ranks should match; scores will
differ in absolute value (both are cosine similarity, but ChromaDB normalizes
differently from Milvus's raw COSINE output).

Prerequisite: a completed crawl JSONL file (checkpoint or raw format).
This script embeds a sample into both backends from scratch using temp
directories — it is self-contained and leaves no persistent state.

Usage:
    python scripts/validate_store_parity.py \\
        --input data/checkpoints/<run_id>.jsonl \\
        --config membuilder.yaml \\
        --limit 200
"""

import asyncio
import argparse
import json
import tempfile
from pathlib import Path

from membuilder.config import MembuilderConfig, VectorStoreConfig
from membuilder.protocols import RawPage, EmbeddedChunk


QUERIES = [
    "how does pod scheduling work",
    "what happens when a node fails",
    "how to configure resource limits for containers",
    "difference between deployment and statefulset",
    "how does kubernetes handle service discovery",
]


async def build_store(config: MembuilderConfig, pages: list[dict], backend: str, tmp_dir: str):
    chunker = config.build_chunker()
    embedder = config.build_embedder()

    sample = await embedder.embed(["probe"])
    dimension = len(sample[0])

    # Override backend for this run
    store_config = VectorStoreConfig(backend=backend, path=tmp_dir)
    config.vector_store = store_config
    store = config.build_vector_store(dimension=dimension)

    all_chunks = []
    for raw in pages:
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
        print("  [warning] No chunks produced from input pages.")
        return store, embedder

    embedded = []
    for i in range(0, len(all_chunks), 100):
        batch = all_chunks[i:i + 100]
        embeddings = await embedder.embed([c.text for c in batch])
        embedded.extend(EmbeddedChunk(chunk=c, embedding=e) for c, e in zip(batch, embeddings))

    await store.upsert(embedded)
    print(f"  [{backend}] Upserted {len(embedded)} chunks")
    return store, embedder


async def run_parity_check(config: MembuilderConfig, pages: list[dict]):
    print(f"Embedding {len(pages)} pages into both backends...\n")

    with tempfile.TemporaryDirectory() as chroma_tmp, \
         tempfile.TemporaryDirectory() as milvus_tmp:

        chroma_store, embedder = await build_store(config, pages, "chroma", chroma_tmp)
        milvus_store, _ = await build_store(config, pages, "milvus", milvus_tmp)

        print()
        results = []
        for query in QUERIES:
            q_embedding = (await embedder.embed([query]))[0]

            chroma_hits = await chroma_store.query(q_embedding, top_k=3)
            milvus_hits = await milvus_store.query(q_embedding, top_k=3)

            chroma_ids = [r.chunk.id for r in chroma_hits]
            milvus_ids = [r.chunk.id for r in milvus_hits]
            match = chroma_ids == milvus_ids

            results.append({
                "query": query,
                "match": match,
                "chroma_top3": chroma_ids,
                "milvus_top3": milvus_ids,
                "chroma_scores": [round(r.score, 4) for r in chroma_hits],
                "milvus_scores": [round(r.score, 4) for r in milvus_hits],
            })

        return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", default="membuilder.yaml")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    config = MembuilderConfig.from_file(args.config)

    pages = []
    with open(args.input) as f:
        for i, line in enumerate(f):
            if i >= args.limit:
                break
            row = json.loads(line)
            if row.get("status") in ("failed", "skipped"):
                continue
            pages.append(row)

    print(f"Loaded {len(pages)} pages\n")

    results = asyncio.run(run_parity_check(config, pages))

    passed = 0
    failed = 0

    for r in results:
        status = "✅" if r["match"] else "⚠️ "
        print(f"{status} Query: \"{r['query']}\"")
        if not r["match"]:
            print(f"   Chroma top-3 : {r['chroma_top3']}")
            print(f"   Milvus top-3 : {r['milvus_top3']}")
        print(f"   Chroma scores: {r['chroma_scores']}")
        print(f"   Milvus scores: {r['milvus_scores']}")
        print()
        if r["match"]:
            passed += 1
        else:
            failed += 1

    print(f"--- Result: {passed}/{len(results)} queries matched ---")
    print()
    print("Score direction note: both adapters return cosine similarity (higher = better).")
    print("  ChromaDB: 1 - cosine_distance  ∈ [-1, 1]")
    print("  Milvus:   cosine similarity     ∈ [-1, 1]  (COSINE metric, direct)")
    print()

    if failed == 0:
        print("✅ PASS — Chroma and Milvus return identical top-3 rankings.")
    elif failed <= 1:
        print("⚠️  SOFT PASS — 1 query diverged. Inspect scores above; likely a tie at the boundary.")
        print("   Acceptable if diverging chunks have near-identical scores.")
    else:
        print(f"❌ FAIL — {failed} queries returned different rankings.")
        print("   Check MilvusVectorStore query logic and distance metric configuration.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
