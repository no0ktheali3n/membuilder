# membuilder

A self-building AI knowledge engine that transforms documentation sites into structured, queryable knowledge bases. Point it at any docs URL and it crawls, parses, chunks, and indexes the content into a navigable reference system with AI-powered search. Inspired by DeepWiki.

Designed to be reusable across any documentation source — Kubernetes docs, internal Confluence, product docs, whitepapers, and PDFs (via Docling in future updates).

---

## Architecture

```
URL(s)
  ↓
crawl4ai (async crawler → clean markdown + metadata)
  ↓
Checkpoint to disk (JSONL per page, resume-safe)
  ↓
MarkdownNodeParser (heading-aware hierarchical chunks)
  ↓
Metadata enrichment (url, breadcrumb, title, domain, crawled_at, tags)
  ↓
Embeddable protocol (id, text, metadata — model-agnostic)
  ↓
Adapter layer (all backends behind swappable protocol interfaces)
  ↓
Embeddings (OpenAI / Ollama via LiteLLM)
  ↓
Vector store (ChromaDB or Milvus — swap via membuilder.yaml)
  ↓
LlamaIndex Query Engine + LiteLLM router
  ↓
FastAPI backend
  ↓
UI (Streamlit prototype → Next.js v1)
```

All concrete dependencies (vector stores, embedders, crawlers, chunkers) are wrapped behind runtime-checkable protocol interfaces defined in `membuilder/protocols.py`. Swapping backends requires only a config change in `membuilder.yaml` — no code changes.

---

## Directory Structure

```
membuilder/
├── pyproject.toml
├── uv.lock
├── membuilder.yaml               # Pipeline config — swap providers here
├── .env                          # API keys (gitignored)
├── .gitignore
├── .python-version               # Python 3.12
├── CHANGELOG.md
├── PROJECT.md                    # Central source of truth — architecture, roadmap, ADRs
├── README.md
│
├── membuilder/                   # Main package
│   ├── __init__.py               # Exposes __version__
│   ├── config.py                 # MembuilderConfig — loads membuilder.yaml, instantiates adapters
│   ├── protocols.py              # Runtime-checkable protocols: Crawler, Chunker, Embedder, VectorStore
│   │
│   ├── adapters/                 # Adapter layer — wraps concrete deps behind protocol interfaces
│   │   └── vector_store/
│   │       ├── chroma.py
│   │       └── milvus.py         # MilvusVectorStore — Milvus Lite (local) or server via URI
│   │
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── crawler.py            # crawl4ai orchestration, BFS crawl logic
│   │   ├── checkpoint.py         # JSONL disk persistence, resume support
│   │   └── models.py             # RawPage dataclass (with crawled_at)
│   │
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── chunker.py            # MarkdownNodeParser, heading hierarchy, content cleaning
│   │   ├── metadata.py           # URL-to-breadcrumb derivation
│   │   └── models.py             # Chunk dataclass (implements Embeddable)
│   │
│   ├── index/
│   │   ├── __init__.py
│   │   ├── protocol.py           # Embeddable protocol — id, text, metadata
│   │   ├── embedder.py           # Batched embedding pipeline via LiteLLM
│   │   └── store.py              # ChromaDB interface — collection-agnostic upsert
│   │
│   ├── query/
│   │   ├── __init__.py
│   │   └── engine.py             # LlamaIndex query engine + LiteLLM (planned v0.4.0)
│   │
│   ├── synthesizer/              # Planned v0.5.0
│   │
│   ├── vault/                    # Planned v0.6.0
│   │
│   └── api/
│       ├── __init__.py
│       └── main.py               # FastAPI app (planned v0.4.0)
│
├── ui/
│   └── app.py                    # Streamlit prototype (planned v0.9.0)
│
├── data/                         # Gitignored
│   ├── checkpoints/              # Per-crawl JSONL checkpoint files
│   ├── chunks/                   # Per-crawl JSONL chunk files
│   └── chroma/                   # Persistent ChromaDB on disk
│
├── evals/
│   └── k8s_questions.json        # Retrieval eval question set (planned)
│
└── scripts/
    ├── crawl.py                  # CLI: crawl a documentation site
    ├── parse.py                  # CLI: parse checkpoint into chunks
    ├── index.py                  # CLI: embed + load into vector store
    ├── query.py                  # CLI: quick query test (planned v0.4.0)
    ├── inspect_checkpoint.py     # CLI: validate and inspect crawl output
    ├── inspect_chunks.py         # CLI: validate and inspect chunk output
    ├── inspect_index.py          # CLI: validate index coverage + retrieval spot-check
    ├── validate_idempotency.py   # CLI: confirm deterministic IDs + idempotent upsert
    ├── validate_store_parity.py  # CLI: cross-backend ranking comparison (Linux/CI only)
    ├── patch_titles.py           # CLI: post-hoc title extraction fix
    └── debug_title.py            # CLI: one-page crawl for debugging metadata
```

---

## Stack

| Layer | Tool | Notes |
|---|---|---|
| Crawler | crawl4ai | Async, JS rendering, markdown output |
| Parser | LlamaIndex MarkdownNodeParser | Heading-aware chunking |
| Embeddings | OpenAI / Ollama | Routed via LiteLLM |
| Vector Store | ChromaDB or Milvus | Swap via `membuilder.yaml` |
| Query | LlamaIndex + LiteLLM | Model-agnostic query engine |
| API | FastAPI | Async, production-ready |
| UI (proto) | Streamlit | Fast iteration |
| UI (v1) | Next.js + Shadcn | Planned |

---

## Configuration (`membuilder.yaml`)

All pipeline components are configured via `membuilder.yaml` in the project root. Edit this file to swap providers — no code changes needed.

```yaml
crawler: crawl4ai

chunker: markdown

embedder:
  provider: ollama       # swap to: openai, cohere, anthropic, etc.
  model: qwen3:4b        # model name as LiteLLM expects it

vector_store:
  backend: chroma        # swap to: milvus
  path: ./data/chroma
  # uri:                 # milvus server only — e.g. http://localhost:19530

vault:
  profile: knowledge     # knowledge | work | research | creative (v0.6.0)
  domain: kubernetes
  output: ./vaults/kubernetes
```

### Supported vector store backends

| Backend | Config | Notes |
|---------|--------|-------|
| `chroma` | `backend: chroma` + `path:` | Default. Persistent local ChromaDB. |
| `milvus` | `backend: milvus` + `path:` | Milvus Lite (local file). **Linux/macOS only.** Use a `.db` file path. |
| `milvus` | `backend: milvus` + `uri: http://...` | Full Milvus server. `uri` takes precedence over `path`. Supported on all platforms. |

> **Note:** `milvus-lite` is not supported on Windows. Windows users should use ChromaDB or connect to a full Milvus server via `uri`.

### Supported embedder providers

Any LiteLLM-compatible provider works. Set `provider` and `model` to match:

| Provider | Config | Notes |
|----------|--------|-------|
| Ollama (local) | `provider: ollama`, `model: qwen3-embedding:4b` | Set `OLLAMA_API_BASE` in `.env` |
| OpenAI | `provider: openai`, `model: text-embedding-3-small` | Set `OPENAI_API_KEY` in `.env` |
| Cohere | `provider: cohere`, `model: embed-english-v3.0` | Set `COHERE_API_KEY` in `.env` |

---

## Setup

```bash
# Install dependencies
uv sync

# Install package in editable mode (required for script execution)
uv pip install -e .

# First-time browser setup (downloads Chromium for crawl4ai)
uv run crawl4ai-setup
```

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_key_here

# Optional: override embedding model (default: text-embedding-3-small)
# MEMBUILDER_EMBEDDING_MODEL=ollama/qwen3-embedding:4b
# OLLAMA_API_BASE=http://localhost:11434

# Optional: override synthesis model (default: claude-sonnet-4-6)
# MEMBUILDER_SYNTHESIS_MODEL=ollama/qwen2.5-coder:14b
```

---

## Usage

### 1. Crawl a documentation site

Crawls from the seed URL, stays within its path scope, and checkpoints every page to disk. Resumes automatically if interrupted.

```bash
# Full crawl
uv run python scripts/crawl.py https://kubernetes.io/docs/

# Test crawl — validate before committing to full run
uv run python scripts/crawl.py https://kubernetes.io/docs/ --max-pages 20 --concurrency 3

# Crawl a specific section only
uv run python scripts/crawl.py https://kubernetes.io/docs/concepts/
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--max-pages` | 2000 | Maximum pages to crawl |
| `--concurrency` | 5 | Concurrent browser sessions |
| `--rate-limit` | 0.5 | Seconds between batches |
| `--checkpoint-dir` | `data/checkpoints` | Where to save JSONL output |

**Scope behaviour:** The crawler stays within the seed URL's path prefix. Seeding from `/docs/` crawls all of docs. Seeding from `/docs/concepts/` crawls only concepts. External domains, binary files, print views, and non-HTML content are automatically filtered.

**Resume:** If the crawl is interrupted, re-running the same command resumes from where it stopped. The checkpoint file is never overwritten — pages are appended as they complete.

---

### 2. Inspect and validate crawl output

Analyses the checkpoint file and flags anomalies before proceeding to the parser.

```bash
uv run python scripts/inspect_checkpoint.py
```

**Output includes:**
- Page count, success/failure breakdown
- Markdown size distribution (min, max, avg, median)
- Anomaly report with tiered severity:
  - `[1a]` Truly empty pages (< 2 chars) — JS-rendered or non-HTML
  - `[1b]` Near-empty pages (2–500 chars) — broken extraction
  - `[1c]` Thin pages (500–2000 chars) — section indexes, low value
  - `[2a]` Large reference pages (50k–150k) — expected for API docs
  - `[2b]` Large non-reference pages (50k–150k) — investigate
  - `[2c]` Very large pages (> 150k) — likely CSS selector miss
  - `[3]`  Non-HTML content (JSON, XML, etc.)
  - `[4]`  Missing titles
- Title diagnostic on first 3 pages
- First page markdown preview
- Verdict: critical issues vs warnings

---

### 3. Patch titles (if needed)

If title extraction failed during the crawl (e.g. after a regex fix), this patches the checkpoint in place without re-crawling.

```bash
uv run python scripts/patch_titles.py
```

Rewrites titles by extracting the first H1/H2 heading from each page's markdown. Pages with no headings (truly empty pages) are left unchanged.

---

### 4. Parse checkpoint into chunks

Reads the checkpoint, filters low-quality pages, splits each page's markdown into heading-aware chunks, enriches with metadata, and saves to JSONL.

```bash
uv run python scripts/parse.py
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--checkpoint-dir` | `data/checkpoints` | Checkpoint input directory |
| `--output-dir` | `data/chunks` | Chunk output directory |

**Output:** `data/chunks/<run_id>_chunks.jsonl` — one chunk per line with full metadata (`url`, `breadcrumb`, `chunk_index`, `domain`, `crawled_at`, `tags`, `heading`).

---

### 5. Inspect and validate chunk output

Analyses the chunk file and flags anomalies before proceeding to the embedder.

```bash
uv run python scripts/inspect_chunks.py
```

**Output includes:**
- Total chunk count and size distribution
- Chunks per page (min, max, avg)
- Top 5 pages by chunk count
- Section distribution with visual bar chart
- Anomaly report:
  - `[1]` Tiny chunks (< 100 chars) — heading stubs with no body
  - `[2]` Large chunks (> 8,000 chars) — may affect embedding quality
  - `[3]` Missing headings — intro paragraphs before first heading
- Sample of first 3 chunks with full metadata
- Verdict

---

### 6. Embed and index chunks

Embeds all chunks and upserts them into the configured vector store. Safe to re-run — chunk IDs are deterministic, so existing records are updated, not duplicated.

```bash
# Estimate cost before committing (no API calls)
uv run python scripts/index.py --dry-run

# Full index run
uv run python scripts/index.py
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--chunks-file` | auto-detected | Path to chunks JSONL |
| `--chroma-dir` | `data/chroma` | ChromaDB persistence directory (ChromaDB backend only) |
| `--collection` | derived from chunks filename | Collection name |
| `--dry-run` | false | Estimate tokens/cost, skip embedding |

**Local Ollama:** Set `MEMBUILDER_EMBEDDING_MODEL=ollama/<model>` and `OLLAMA_API_BASE=http://localhost:11434` in `.env` to run embeddings locally at no cost. Stop any idle Ollama models before running to ensure GPU VRAM is available.

---

### 7. Inspect and validate index

Validates embedding coverage and runs a retrieval spot-check against the collection.

```bash
uv run python scripts/inspect_index.py
```

**Output includes:**
- Collection stats (record count, embedding model, distance function)
- Sample IDs and metadata
- Coverage report: indexed vs expected chunk count
- 5-query retrieval spot-check with top-3 scored results and content previews
- Verdict

---

### 8. Validate idempotency

Confirms that re-running the index pipeline on the same data produces zero new inserts — verifying deterministic chunk IDs and idempotent upsert behaviour.

```bash
uv run python scripts/validate_idempotency.py
```

Runs the index pipeline twice against the same chunk file and asserts the collection count is identical after both runs. Reports chunk ID stability and upsert behaviour.

---

### 9. Validate store parity (Linux/CI only)

Compares retrieval ranking between ChromaDB and Milvus backends to confirm result parity across a set of test queries.

```bash
uv run python scripts/validate_store_parity.py
```

> **Note:** Requires `milvus-lite`, which is Linux/macOS only. Defer this script on Windows; it runs automatically in CI on Linux.

---

### 10. Debug metadata (development)

Fetches a single page and dumps the raw crawl4ai result for inspection. Useful when diagnosing title extraction, CSS selector issues, or metadata availability.

```bash
uv run python scripts/debug_title.py
```

Edit the URL inside the script to target a specific page.

---

## Parser Design Notes

**Heading-aware chunking:** LlamaIndex `MarkdownNodeParser` splits on `#`, `##`, and `###` headings, preserving the document hierarchy. Each chunk inherits the heading above it, making retrieval context-aware — a query about "pod lifecycle" returns the specific section, not a 60k page blob.

**Content cleaning:** K8s docs appends anchor links to every heading (`## Heading[ ](url)`). These are stripped from content before chunking to prevent noise in embeddings.

**Minimum chunk length:** Chunks below 100 chars are discarded — these are heading stubs with no body content that would degrade retrieval quality.

**Single-chunk fallback:** Pages below LlamaIndex's minimum content threshold now produce a single fallback chunk rather than being silently dropped. This prevents short but valid pages from disappearing from the index.

**Secondary splitting:** Chunks exceeding 6,000 chars are split further on paragraph boundaries. Dense reference pages (API specs, metrics tables) that don't split cleanly on headings are handled this way. Chunks that can't be split by paragraph (flat tables) are left as-is — at 0.5% of total they're acceptable.

**Breadcrumb derivation:** Built from the URL path by stripping the docs root segment and humanising slugs. `kubernetes.io/docs/concepts/workloads/pods/` → `["Concepts", "Workloads", "Pods"]`. Used for navigation context in the query layer.

**Deterministic chunk IDs:** `sha256(url + "::" + chunk_index)[:16]`. Stable across re-runs — the same logical chunk always produces the same ID, enabling idempotent upsert and vault back-references.

---

## Crawler Design Notes

**CSS selector:** The crawler targets `.td-content` on Kubernetes docs to extract only the article body, excluding the full left-sidebar navigation tree that would otherwise bloat every page to 100k+ chars. Different sites will need different selectors — this is configurable in `crawler.py`.

**Link scoping:** Only links within the seed URL's path prefix are followed. This prevents crawling into external sites, other language versions, or unrelated sections.

**Checkpointing:** Every page is written to disk immediately after fetch. If the crawl fails at page 600, re-running resumes from page 601. The JSONL format means each line is an independent record — partial files are safe to read.

**Known limitations:**
- JS-rendered pages that load after `domcontentloaded` may return empty or minimal content (e.g. the Kubernetes glossary). These are flagged by `inspect_checkpoint.py`.
- Non-HTML content (JSON feeds, XML sitemaps) that appears under the docs path will be crawled but return empty markdown. Filter these with `NON_HTML_EXTENSIONS` in the crawler or via `inspect_checkpoint.py` output.

---

## Indexer Design Notes

**`Embeddable` protocol:** The vector store layer depends on `protocol.Embeddable` — not on `Chunk` directly. Any document type implementing `id: str`, `text: str`, `metadata: dict` flows through the same pipeline. This is the forward-compatibility contract for v0.7.0, when vault `AtomicNote` objects replace raw chunks as the indexer input.

**Adapter pattern:** All concrete dependencies are wrapped behind runtime-checkable protocols (`protocols.py`). `MembuilderConfig` loads `membuilder.yaml` and returns the correct adapter via factory methods. Callers never import ChromaDB or Milvus directly — swapping backends is a config-only change.

**Idempotent upsert:** Re-running `index.py` on the same chunk file is safe. Chunk IDs are deterministic (`sha256(url + "::" + chunk_index)[:16]`), so upsert produces zero net-new records on repeat runs. Validated against 1,776 chunks — stable collection count confirmed.

**Model configuration:** All model references come from env vars via `config.py`. Swapping from OpenAI to Ollama to an internal inference endpoint requires only env config changes — no code changes.

**Local embedding:** Ollama models (e.g. `qwen3-embedding:4b`) are fully supported via LiteLLM's `ollama/` prefix. GPU acceleration requires available VRAM — stop idle Ollama models before a full index run.

---

## Current Status

| Stage | Status |
|---|---|
| Crawler | ✅ Complete |
| Checkpoint / Resume | ✅ Complete |
| Data validation tooling | ✅ Complete |
| Parser / Chunker | ✅ Complete |
| Metadata enrichment (breadcrumb) | ✅ Complete |
| Chunk validation tooling | ✅ Complete |
| Embeddable protocol | ✅ Complete |
| Embedding pipeline (LiteLLM) | ✅ Complete |
| ChromaDB store | ✅ Complete |
| Index validation tooling | ✅ Complete |
| Protocol layer (v0.3.1) | ✅ Complete |
| Milvus vector store adapter | ✅ Complete |
| `membuilder.yaml` config system | ✅ Complete |
| Deterministic chunk IDs | ✅ Complete |
| Idempotency validation tooling | ✅ Complete |
| Query engine | 🔄 Next |
| FastAPI backend | ⏳ Planned |
| Synthesizer (vault) | ⏳ Planned |
| Vault writer (Obsidian) | ⏳ Planned |
| Streamlit UI | ⏳ Planned |

---

## Data Quality — Kubernetes Docs Crawl

Reference run against `https://kubernetes.io/docs/` (February 2026):

**Crawl (v0.1.0):**
```
Total pages  : 798
OK           : 798
Failed       : 0

Size distribution:
  Min    : 1 chars
  Max    : 248,580 chars
  Avg    : 14,011 chars
  Median : 7,904 chars

Critical issues : 3  (1 very large page, 2 non-HTML feeds)
Warnings        : 45 (empty section indexes, dense reference pages)
```

**Parse (v0.2.0):**
```
Total chunks : 9,783
Pages indexed: 773 (25 skipped — empty/near-empty)
Pages skipped: 25

Size distribution:
  Min    : 100 chars
  Max    : 61,944 chars
  Avg    : 1,024 chars
  Median : 614 chars

Section distribution:
  Reference  : 4,100 chunks
  Concepts   : 2,376 chunks
  Tasks      : 2,292 chunks
  Contribute :   374 chunks
  Tutorials  :   335 chunks
  Setup      :   284 chunks

Flagged      : 52 chunks (0.5%) — oversized reference tables, acceptable
```

**Index (v0.3.0):**
```
Total records : 9,783
Coverage      : 100.0%
Embed model   : ollama/qwen3-embedding:4b (local)
Distance fn   : cosine
Truncated     : 8 items (32,000 char limit — oversized reference tables)
Embed time    : 53 min (CPU-bound, one-time cost)
ChromaDB write: 8.3s

Retrieval spot-check (5 queries):
  Score range : 0.77 – 0.84 cosine similarity
  Verdict     : All queries returned semantically correct top results
```

**Idempotency validation (v0.3.1):**
```
Sample       : 100 pages / 1,776 chunks
Second run   : 0 new inserts (stable collection count confirmed)
Chunk IDs    : deterministic sha256 — consistent across re-runs
```