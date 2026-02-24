"""
Protocol conformance tests — verify each adapter satisfies its protocol via
isinstance() checks using @runtime_checkable Protocols.

These tests prove that the adapter boundary is correctly shaped: callers can
depend on the protocol without caring which concrete implementation is behind it.
"""

import sys

import pytest

from membuilder.protocols import Crawler, Chunker, Embedder, VectorStore


milvus_skip = pytest.mark.skipif(
    sys.platform == "win32",
    reason="milvus-lite is not supported on Windows",
)


def test_crawl4ai_crawler_satisfies_protocol():
    from membuilder.adapters.crawler import Crawl4AICrawler
    crawler = Crawl4AICrawler()
    assert isinstance(crawler, Crawler), (
        "Crawl4AICrawler must satisfy the Crawler protocol"
    )


def test_markdown_chunker_satisfies_protocol():
    from membuilder.adapters.chunker import MarkdownChunker
    chunker = MarkdownChunker(domain="test")
    assert isinstance(chunker, Chunker), (
        "MarkdownChunker must satisfy the Chunker protocol"
    )


def test_litellm_embedder_satisfies_protocol():
    from membuilder.adapters.embedder import LiteLLMEmbedder
    embedder = LiteLLMEmbedder(model="text-embedding-3-small")
    assert isinstance(embedder, Embedder), (
        "LiteLLMEmbedder must satisfy the Embedder protocol"
    )


def test_chroma_vector_store_satisfies_protocol(tmp_path):
    from membuilder.adapters.vector_store.chroma import ChromaVectorStore
    store = ChromaVectorStore(
        path=str(tmp_path / "chroma"),
        collection_name="test",
    )
    assert isinstance(store, VectorStore), (
        "ChromaVectorStore must satisfy the VectorStore protocol"
    )


@milvus_skip
def test_milvus_vector_store_satisfies_protocol(tmp_path):
    pymilvus = pytest.importorskip("pymilvus", reason="pymilvus not installed")
    from membuilder.adapters.vector_store.milvus import MilvusVectorStore
    store = MilvusVectorStore(
        uri=str(tmp_path / "milvus.db"),
        collection_name="test",
        dimension=3,
    )
    assert isinstance(store, VectorStore), (
        "MilvusVectorStore must satisfy the VectorStore protocol"
    )
