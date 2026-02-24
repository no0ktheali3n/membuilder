"""
Central configuration — all model names come from environment variables.

Every module that makes an LLM or embedding call imports from here.
No model strings are hardcoded anywhere else in the codebase.

Pattern for new modules:
    from membuilder.config import EMBEDDING_MODEL, SYNTHESIS_MODEL

Set overrides in .env or shell environment:
    MEMBUILDER_EMBEDDING_MODEL=ollama/nomic-embed-text
    MEMBUILDER_SYNTHESIS_MODEL=claude-sonnet-4-6

This makes the project deployable against any LiteLLM-compatible provider
(OpenAI, Ollama, vLLM, internal proxies) with a single config change and
zero code changes. LiteLLM is the sole routing layer for all LLM and
embedding calls — no native provider SDKs or LlamaIndex LLM abstractions.

v0.3.1 adds MembuilderConfig — a YAML-driven config that instantiates the
correct protocol adapters. See membuilder.yaml for an example.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Embedding model
# Used by: membuilder/index/embedder.py, scripts/index.py, scripts/inspect_index.py
# ---------------------------------------------------------------------------

EMBEDDING_MODEL: str = os.getenv(
    "MEMBUILDER_EMBEDDING_MODEL",
    "text-embedding-3-small",
)

# ---------------------------------------------------------------------------
# Synthesis model
# Used by: membuilder/query/engine.py (v0.4.0), membuilder/synthesizer/ (v0.5.0),
#          membuilder/vault/claude_md.py (v0.6.0)
# Declared here now so v0.4.0+ can import it without introducing a new pattern.
# ---------------------------------------------------------------------------

SYNTHESIS_MODEL: str = os.getenv(
    "MEMBUILDER_SYNTHESIS_MODEL",
    "claude-sonnet-4-6",
)


# ---------------------------------------------------------------------------
# YAML-driven pipeline config (v0.3.1)
# ---------------------------------------------------------------------------

@dataclass
class EmbedderConfig:
    provider: str        # ollama, openai, cohere, etc.
    model: str


@dataclass
class VectorStoreConfig:
    backend: str = "chroma"     # chroma, milvus
    path: str = "./data"
    uri: str | None = None      # for milvus server; overrides path if set


@dataclass
class VaultConfig:
    profile: str = "knowledge"  # knowledge | work | research | creative (v0.6.0)
    domain: str = ""
    output: str = "./vault"


@dataclass
class MembuilderConfig:
    """
    Full pipeline configuration loaded from membuilder.yaml.

    Provides factory methods (build_*) that instantiate the correct protocol
    adapters based on the config. Swap providers by editing membuilder.yaml —
    no code changes required.
    """
    crawler: str = "crawl4ai"
    chunker: str = "markdown"
    embedder: EmbedderConfig = field(
        default_factory=lambda: EmbedderConfig(provider="ollama", model="qwen3:4b")
    )
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    vault: VaultConfig = field(default_factory=VaultConfig)

    # ------------------------------------------------------------------
    # Loader
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str | Path = "membuilder.yaml") -> MembuilderConfig:
        """Load config from a YAML file and return a MembuilderConfig instance."""
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        embedder_raw = raw.get("embedder", {})
        vs_raw = raw.get("vector_store", {})
        vault_raw = raw.get("vault", {})

        return cls(
            crawler=raw.get("crawler", "crawl4ai"),
            chunker=raw.get("chunker", "markdown"),
            embedder=EmbedderConfig(
                provider=embedder_raw.get("provider", "ollama"),
                model=embedder_raw.get("model", "qwen3:4b"),
            ),
            vector_store=VectorStoreConfig(
                backend=vs_raw.get("backend", "chroma"),
                path=vs_raw.get("path", "./data"),
                uri=vs_raw.get("uri"),
            ),
            vault=VaultConfig(
                profile=vault_raw.get("profile", "knowledge"),
                domain=vault_raw.get("domain", ""),
                output=vault_raw.get("output", "./vault"),
            ),
        )

    # ------------------------------------------------------------------
    # Adapter factories
    # ------------------------------------------------------------------

    def build_embedder(self):
        """Instantiate the configured Embedder adapter."""
        from membuilder.adapters.embedder import LiteLLMEmbedder
        return LiteLLMEmbedder(
            model=f"{self.embedder.provider}/{self.embedder.model}",
        )

    def build_vector_store(self, dimension: int):
        """Instantiate the configured VectorStore adapter."""
        if self.vector_store.backend == "chroma":
            from membuilder.adapters.vector_store.chroma import ChromaVectorStore
            return ChromaVectorStore(
                path=self.vector_store.path,
                collection_name=self.vault.domain or "default",
                embedding_model=f"{self.embedder.provider}/{self.embedder.model}",
            )
        elif self.vector_store.backend == "milvus":
            from membuilder.adapters.vector_store.milvus import MilvusVectorStore
            uri = self.vector_store.uri or f"{self.vector_store.path}/milvus.db"
            return MilvusVectorStore(
                uri=uri,
                collection_name=self.vault.domain or "default",
                dimension=dimension,
            )
        else:
            raise ValueError(f"Unknown vector_store backend: {self.vector_store.backend!r}")

    def build_chunker(self):
        """Instantiate the configured Chunker adapter, wired to vault.domain."""
        from membuilder.adapters.chunker import MarkdownChunker
        return MarkdownChunker(domain=self.vault.domain)

    def build_crawler(self):
        """Instantiate the configured Crawler adapter."""
        from membuilder.adapters.crawler import Crawl4AICrawler
        return Crawl4AICrawler()
