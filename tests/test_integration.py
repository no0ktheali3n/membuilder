"""
Integration test — loads a membuilder.yaml fixture and verifies that
MembuilderConfig wires all components to their correct protocol adapters.

This confirms the config → adapter factory chain works end-to-end without
requiring API keys or live services.

v0.3.1 additions:
  - Verify domain is propagated from config into MarkdownChunker
  - Verify chunk IDs are deterministic (same page → same IDs every time)
  - Verify ChromaDB upsert is idempotent (count stable on second upsert)
"""

import pytest
from pathlib import Path

from membuilder.config import MembuilderConfig
from membuilder.protocols import (
    Crawler, Chunker, Embedder, VectorStore,
    RawPage, Chunk, EmbeddedChunk,
)


# ---------------------------------------------------------------------------
# Shared fixture: YAML config with a tmp ChromaDB path
# ---------------------------------------------------------------------------

FIXTURE_YAML = """\
crawler: crawl4ai

chunker: markdown

embedder:
  provider: ollama
  model: qwen3:4b

vector_store:
  backend: chroma
  path: {chroma_path}

vault:
  profile: knowledge
  domain: test-domain
  output: ./vaults/test
"""


@pytest.fixture
def config_file(tmp_path):
    chroma_path = str(tmp_path / "chroma").replace("\\", "/")
    yaml_content = FIXTURE_YAML.format(chroma_path=chroma_path)
    path = tmp_path / "membuilder.yaml"
    path.write_text(yaml_content)
    return path, tmp_path


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------

def test_from_file_parses_config(config_file):
    path, _ = config_file
    config = MembuilderConfig.from_file(path)

    assert config.crawler == "crawl4ai"
    assert config.chunker == "markdown"
    assert config.embedder.provider == "ollama"
    assert config.embedder.model == "qwen3:4b"
    assert config.vector_store.backend == "chroma"
    assert config.vault.profile == "knowledge"
    assert config.vault.domain == "test-domain"


# ---------------------------------------------------------------------------
# Protocol conformance via factory methods
# ---------------------------------------------------------------------------

def test_build_chunker_satisfies_protocol(config_file):
    path, _ = config_file
    config = MembuilderConfig.from_file(path)
    chunker = config.build_chunker()
    assert isinstance(chunker, Chunker)


def test_build_crawler_satisfies_protocol(config_file):
    path, _ = config_file
    config = MembuilderConfig.from_file(path)
    crawler = config.build_crawler()
    assert isinstance(crawler, Crawler)


def test_build_embedder_satisfies_protocol(config_file):
    path, _ = config_file
    config = MembuilderConfig.from_file(path)
    embedder = config.build_embedder()
    assert isinstance(embedder, Embedder)
    assert embedder.model_id == "ollama/qwen3:4b"


def test_build_vector_store_chroma_satisfies_protocol(config_file):
    path, _ = config_file
    config = MembuilderConfig.from_file(path)
    store = config.build_vector_store(dimension=1536)
    assert isinstance(store, VectorStore)


def test_build_vector_store_milvus_satisfies_protocol(tmp_path):
    pytest.importorskip("pymilvus", reason="pymilvus not installed")
    milvus_path = str(tmp_path / "milvus").replace("\\", "/")
    yaml_content = f"""\
crawler: crawl4ai
chunker: markdown
embedder:
  provider: ollama
  model: qwen3:4b
vector_store:
  backend: milvus
  path: {milvus_path}
vault:
  domain: test-milvus
"""
    config_path = tmp_path / "membuilder_milvus.yaml"
    config_path.write_text(yaml_content)

    config = MembuilderConfig.from_file(config_path)
    store = config.build_vector_store(dimension=3)
    assert isinstance(store, VectorStore)


def test_build_vector_store_unknown_backend_raises(config_file):
    path, tmp = config_file
    bad_yaml = """\
crawler: crawl4ai
chunker: markdown
embedder:
  provider: ollama
  model: qwen3:4b
vector_store:
  backend: qdrant
vault:
  domain: test
"""
    bad_path = tmp / "bad.yaml"
    bad_path.write_text(bad_yaml)

    config = MembuilderConfig.from_file(bad_path)
    with pytest.raises(ValueError, match="Unknown vector_store backend"):
        config.build_vector_store(dimension=1536)


# ---------------------------------------------------------------------------
# Domain propagation (v0.3.1)
# ---------------------------------------------------------------------------

def test_build_chunker_domain_is_propagated(config_file):
    """vault.domain must be passed into MarkdownChunker at construction time."""
    path, _ = config_file
    config = MembuilderConfig.from_file(path)
    chunker = config.build_chunker()
    assert chunker.domain == "test-domain", (
        f"Expected domain 'test-domain', got {chunker.domain!r}"
    )


def test_chunk_metadata_includes_domain(config_file):
    """Every Chunk produced by build_chunker() must have 'domain' in metadata."""
    path, _ = config_file
    config = MembuilderConfig.from_file(path)
    chunker = config.build_chunker()

    page = RawPage(
        url="https://example.com/docs/concepts/pods/",
        content=(
            "# Pods\n\n"
            "A Pod is the smallest deployable unit in Kubernetes.\n\n"
            "## Lifecycle\n\n"
            "Pods transition through several lifecycle phases before termination."
        ),
        metadata={"title": "Pods", "depth": 1},
        crawled_at="2026-02-24T00:00:00+00:00",
    )

    chunks = chunker.chunk(page)
    assert chunks, "Expected at least one chunk from page"
    for c in chunks:
        assert "domain" in c.metadata, "Chunk.metadata must include 'domain'"
        assert c.metadata["domain"] == "test-domain"


def test_chunk_metadata_has_all_required_keys(config_file):
    """All required Chunk.metadata keys must be present on every chunk."""
    path, _ = config_file
    config = MembuilderConfig.from_file(path)
    chunker = config.build_chunker()

    page = RawPage(
        url="https://example.com/docs/concepts/pods/",
        content=(
            "# Pods\n\n"
            "A Pod is the smallest deployable unit in Kubernetes.\n\n"
            "## Lifecycle\n\n"
            "Pods transition through several lifecycle phases before termination."
        ),
        metadata={"title": "Pods", "depth": 1},
        crawled_at="2026-02-24T00:00:00+00:00",
    )

    required_keys = {"url", "breadcrumb", "chunk_index", "domain", "crawled_at", "tags", "heading"}
    chunks = chunker.chunk(page)
    assert chunks, "Expected at least one chunk from page"
    for c in chunks:
        missing = required_keys - set(c.metadata.keys())
        assert not missing, f"Chunk missing required metadata keys: {missing}"


# ---------------------------------------------------------------------------
# Deterministic IDs (v0.3.1)
# ---------------------------------------------------------------------------

def test_chunk_ids_are_deterministic(config_file):
    """
    Same page input must always produce the same chunk IDs.
    This is required for vault back-references and idempotent upsert.
    """
    path, _ = config_file
    config = MembuilderConfig.from_file(path)
    chunker = config.build_chunker()

    page = RawPage(
        url="https://example.com/docs/concepts/pods/",
        content=(
            "# Pods\n\n"
            "A Pod is the smallest deployable unit in Kubernetes.\n\n"
            "## Lifecycle\n\n"
            "Pods transition through several lifecycle phases before termination."
        ),
        metadata={"title": "Pods", "depth": 1},
        crawled_at="2026-02-24T00:00:00+00:00",
    )

    chunks1 = chunker.chunk(page)
    chunks2 = chunker.chunk(page)

    assert len(chunks1) == len(chunks2), (
        "Same input must produce the same number of chunks"
    )
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.id == c2.id, (
            f"Chunk IDs not deterministic: {c1.id!r} != {c2.id!r}"
        )


# ---------------------------------------------------------------------------
# Upsert idempotency (v0.3.1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chroma_upsert_idempotency(config_file):
    """
    Second upsert of the exact same chunks must not change the collection count.
    This proves that IDs are deterministic and ChromaDB's upsert is truly
    insert-or-update (not insert-and-duplicate).
    """
    path, _ = config_file
    config = MembuilderConfig.from_file(path)
    store = config.build_vector_store(dimension=3)

    chunks = [
        EmbeddedChunk(
            chunk=Chunk(
                id="idem_test_001",
                text="Pods are the smallest deployable units in Kubernetes.",
                metadata={
                    "url": "https://example.com/pods",
                    "chunk_index": 0,
                    "breadcrumb": "Concepts > Workloads",
                    "domain": "test-domain",
                    "crawled_at": "2026-02-24T00:00:00+00:00",
                    "tags": "concepts,workloads",
                    "heading": "Pods",
                },
            ),
            embedding=[0.1, 0.2, 0.3],
        ),
        EmbeddedChunk(
            chunk=Chunk(
                id="idem_test_002",
                text="A Deployment manages a ReplicaSet of Pods.",
                metadata={
                    "url": "https://example.com/deployments",
                    "chunk_index": 0,
                    "breadcrumb": "Concepts > Workloads",
                    "domain": "test-domain",
                    "crawled_at": "2026-02-24T00:00:00+00:00",
                    "tags": "concepts,workloads",
                    "heading": "Deployments",
                },
            ),
            embedding=[0.4, 0.5, 0.6],
        ),
    ]

    await store.upsert(chunks)
    count_after_first = await store.count()

    # Second run — identical input, same store
    await store.upsert(chunks)
    count_after_second = await store.count()

    assert count_after_first == count_after_second, (
        f"Count changed after second upsert: {count_after_first} → {count_after_second}. "
        "Upsert is not idempotent — check chunk ID generation."
    )
