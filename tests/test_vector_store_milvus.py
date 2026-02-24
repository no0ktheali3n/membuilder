"""
Milvus vector store smoke test — exercises the full upsert/query/delete/count
cycle using Milvus Lite (no server required).

Uses 3-dimensional embeddings for speed. The test is skipped automatically
if pymilvus is not installed.
"""

import pytest
import asyncio

from membuilder.protocols import EmbeddedChunk, Chunk


pytestmark = pytest.mark.asyncio


@pytest.fixture
def milvus_store(tmp_path):
    pymilvus = pytest.importorskip("pymilvus", reason="pymilvus not installed")
    from membuilder.adapters.vector_store.milvus import MilvusVectorStore
    return MilvusVectorStore(
        uri=str(tmp_path / "milvus_test.db"),
        collection_name="smoke_test",
        dimension=3,
    )


@pytest.fixture
def sample_chunks():
    return [
        EmbeddedChunk(
            chunk=Chunk(
                id="chunk_001",
                text="Pods are the smallest deployable units in Kubernetes.",
                metadata={
                    "url": "https://kubernetes.io/docs/concepts/workloads/pods/",
                    "chunk_index": 0,
                    "breadcrumb": ["Concepts", "Workloads"],  # list[str]
                    "tags": ["concepts", "workloads"],        # list[str]
                    "domain": "kubernetes",
                    "crawled_at": "2026-02-24T00:00:00+00:00",
                    "heading": "Pods",
                },
            ),
            embedding=[0.1, 0.2, 0.3],
        ),
        EmbeddedChunk(
            chunk=Chunk(
                id="chunk_002",
                text="A Deployment provides declarative updates for Pods.",
                metadata={
                    "url": "https://kubernetes.io/docs/concepts/workloads/deployments/",
                    "chunk_index": 0,
                    "breadcrumb": ["Concepts", "Workloads"],
                    "tags": ["concepts", "workloads"],
                    "domain": "kubernetes",
                    "crawled_at": "2026-02-24T00:00:00+00:00",
                    "heading": "Deployments",
                },
            ),
            embedding=[0.4, 0.5, 0.6],
        ),
        EmbeddedChunk(
            chunk=Chunk(
                id="chunk_003",
                text="Services expose Pods as a network service.",
                metadata={
                    "url": "https://kubernetes.io/docs/concepts/services-networking/service/",
                    "chunk_index": 0,
                    "breadcrumb": ["Concepts", "Services"],
                    "tags": ["concepts", "services"],
                    "domain": "kubernetes",
                    "crawled_at": "2026-02-24T00:00:00+00:00",
                    "heading": "Services",
                },
            ),
            embedding=[0.7, 0.8, 0.9],
        ),
    ]


async def test_upsert_returns_result(milvus_store, sample_chunks):
    result = await milvus_store.upsert(sample_chunks)
    assert result.errors == 0


async def test_count_reflects_upsert(milvus_store, sample_chunks):
    await milvus_store.upsert(sample_chunks)
    count = await milvus_store.count()
    assert count == len(sample_chunks)


async def test_query_returns_results(milvus_store, sample_chunks):
    await milvus_store.upsert(sample_chunks)
    results = await milvus_store.query(embedding=[0.1, 0.2, 0.3], top_k=2)
    assert len(results) > 0
    # Nearest to [0.1, 0.2, 0.3] should be chunk_001
    assert results[0].chunk.id == "chunk_001"


async def test_delete_reduces_count(milvus_store, sample_chunks):
    await milvus_store.upsert(sample_chunks)
    await milvus_store.delete(["chunk_001"])
    count = await milvus_store.count()
    assert count == len(sample_chunks) - 1


async def test_upsert_is_idempotent(milvus_store, sample_chunks):
    """Re-upserting the same chunks must not duplicate records."""
    await milvus_store.upsert(sample_chunks)
    await milvus_store.upsert(sample_chunks)
    count = await milvus_store.count()
    assert count == len(sample_chunks)
