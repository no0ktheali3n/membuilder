# Changelog

All notable changes to membuilder are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.3.1] - 2026-02-24

### Added
- `membuilder/protocols.py` — four runtime-checkable protocols: `Crawler`, `Chunker`, `Embedder`, `VectorStore` with shared data types (`RawPage`, `Chunk`, `EmbeddedChunk`, `SearchResult`, `UpsertResult`)
- `membuilder/adapters/` — adapter layer wrapping all concrete dependencies behind protocol interfaces
- `membuilder/adapters/vector_store/milvus.py` — `MilvusVectorStore` adapter supporting Milvus Lite (local) and Milvus server (production) via URI
- `membuilder/config.py` — `MembuilderConfig` loads `membuilder.yaml` and instantiates correct adapters via factory methods
- `membuilder.yaml` — top-level config file driving the full pipeline (crawler, chunker, embedder, vector store, vault)
- `scripts/validate_idempotency.py` — real-data validation script confirming deterministic chunk IDs and idempotent upsert
- `scripts/validate_store_parity.py` — cross-backend ranking comparison script (defer on Windows; requires Linux/CI for Milvus Lite)

### Changed
- `MarkdownChunker` now accepts `domain` at construction time and emits all required metadata keys: `url`, `breadcrumb`, `chunk_index`, `domain`, `crawled_at`, `tags`, `heading`
- Chunk IDs are now deterministic: `sha256(url + "::" + chunk_index)[:16]` — previously random UUIDs
- `RawPage` dataclass extended with `crawled_at: str` (ISO 8601)
- `pyproject.toml` updated with `pymilvus` dependency and `setuptools` package discovery scoped to `membuilder*`

### Fixed
- `MarkdownChunker` now returns a single-chunk fallback for pages below LlamaIndex's minimum content threshold — previously returned empty list, silently dropping short pages from the index

### Notes
- Milvus Lite tests skipped on Windows (`milvus-lite` is Linux/macOS only). Full Milvus test coverage runs in CI on Linux.
- Idempotency validated against 100 pages of Kubernetes corpus (1,776 chunks). Second run confirmed zero new inserts via stable collection count.
- Full corpus re-embed recommended after this release to populate enriched metadata fields in existing collections.

---

## [0.3.0] - 2026-02-23

### Added
- `membuilder/index/protocol.py` — `Embeddable` protocol (`id`, `text`, `metadata`) — the abstraction layer that decouples the ChromaDB store from any specific document type. Both `Chunk` (v0.3.0) and `AtomicNote` (v0.7.0) implement it.
- `membuilder/index/embedder.py` — batched embedding pipeline via LiteLLM with exponential backoff retry, progress display, truncation safety (32k char limit), and cost estimation for known models
- `membuilder/index/store.py` — ChromaDB interface with idempotent upsert (re-running on the same chunk file is safe), collection-agnostic design (depends on `Embeddable`, not `Chunk`)
- `membuilder/config.py` — centralised settings with env var overrides: `MEMBUILDER_EMBEDDING_MODEL`, `MEMBUILDER_SYNTHESIS_MODEL`, `OLLAMA_API_BASE`. No hardcoded model names anywhere in the codebase.
- `scripts/index.py` — CLI entry point: `--dry-run` flag for cost estimation without API calls, `--collection` and `--chroma-dir` overrides
- `scripts/inspect_index.py` — index validation tooling: collection stats, 100% coverage check against source chunk file, 5-query retrieval spot-check with scored results and previews

### Changed
- `membuilder/__init__.py` — bumped `__version__` to `0.3.0`
- `pyproject.toml` — bumped version to `0.3.0`, added `litellm`, `chromadb` dependencies
- `membuilder/parser/models.py` — `Chunk` now implements `Embeddable` protocol

### Data Quality (Kubernetes docs reference run)
- 9,783 chunks embedded, 0 failures
- 8 items truncated to 32,000 chars (oversized reference tables — expected)
- 9,783 records upserted to ChromaDB in 8.3s
- Retrieval spot-check: all 5 test queries returned semantically correct top results
- Score range: 0.77–0.84 cosine similarity — healthy signal across concept, task, and tutorial content
- Embed time: 53 min on CPU (local Ollama, qwen3-embedding:4b) — one-time cost, collection is persistent

---

## [0.2.0] - 2026-02-23

### Added
- `membuilder/parser/chunker.py` — heading-aware markdown chunker using LlamaIndex `MarkdownNodeParser`
- `membuilder/parser/metadata.py` — URL-to-breadcrumb derivation with slug humanisation
- `membuilder/parser/models.py` — `Chunk` dataclass with deterministic `chunk_id` (MD5 of url + index)
- `scripts/parse.py` — CLI entry point for the parse pipeline
- `scripts/inspect_chunks.py` — chunk validation with size distribution, section breakdown, and tiered anomaly detection
- Content cleaning — strips K8s anchor links (`## Heading[ ](url)`) from markdown before chunking
- Minimum chunk length filter (100 chars) — discards heading stubs with no body
- Secondary paragraph-based splitter for chunks exceeding 6,000 chars

### Changed
- `membuilder/__init__.py` — bumped `__version__` to `0.2.0`
- `pyproject.toml` — bumped version to `0.2.0`, added `llama-index-core` dependency
- Python interpreter updated from 3.11 to 3.12

### Data Quality (Kubernetes docs reference run)
- 9,783 chunks produced from 773 pages
- 25 pages skipped (empty/near-empty, no content to chunk)
- Median chunk size: 614 chars — well within embedding model sweet spot
- 0 tiny chunks after filter
- 52 oversized chunks (0.5%) — flat reference tables, acceptable

---

## [0.1.0] - 2026-02-22

### Added
- `membuilder/crawler/crawler.py` — async BFS documentation crawler using crawl4ai
  - Stays within seed URL path scope
  - Configurable concurrency and rate limiting
  - CSS selector support for content extraction (`.td-content` for K8s docs)
  - Filters print views, binary files, and non-HTML content
  - Rich progress output
- `membuilder/crawler/checkpoint.py` — JSONL-based checkpoint manager with resume support
- `membuilder/crawler/models.py` — `CrawledPage` dataclass
- `scripts/crawl.py` — CLI entry point with `--max-pages`, `--concurrency`, `--rate-limit` flags
- `scripts/inspect_checkpoint.py` — crawl validation with tiered anomaly detection:
  - Truly empty, near-empty, and thin page categories
  - Large reference vs large suspect page categories
  - Very large page detection (CSS selector miss indicator)
  - Non-HTML content detection
  - Missing title detection
  - Critical vs warning verdict
- `scripts/patch_titles.py` — post-hoc title extraction from markdown headings
- `scripts/debug_title.py` — single-page crawl for metadata debugging
- `.gitignore`, `.env` template, `CHANGELOG.md`, `README.md`

### Data Quality (Kubernetes docs reference run)
- 798 pages crawled, 0 failures
- Median page size: 7,904 chars after CSS selector content extraction
- 3 critical issues (2 non-HTML feeds, 1 oversized spec page)
- 45 warnings (empty section indexes, dense reference pages)