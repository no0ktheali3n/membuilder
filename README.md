# membuilder

A self-building AI knowledge engine that transforms documentation sites into structured, queryable knowledge bases. Point it at any docs URL and it crawls, parses, chunks, and indexes the content into a navigable reference system with AI-powered search.  Inspired by DeepWiki.

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
Metadata enrichment (url, breadcrumb, title, timestamp)
  ↓
Embeddings (OpenAI / Ollama via LiteLLM)
  ↓
ChromaDB (persistent, on disk)
  ↓
LlamaIndex Query Engine + LiteLLM router
  ↓
FastAPI backend
  ↓
UI (Streamlit prototype → Next.js v1)
```

---

## Directory Structure

```
membuilder/
├── pyproject.toml
├── uv.lock
├── .env                          # API keys, config (gitignored)
├── .gitignore
├── .python-version               # Python 3.12
├── CHANGELOG.md
├── README.md
│
├── membuilder/                   # Main package
│   ├── __init__.py               # Exposes __version__
│   ├── config.py                 # Settings, env vars, constants
│   │
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── crawler.py            # crawl4ai orchestration, BFS crawl logic
│   │   ├── checkpoint.py         # JSONL disk persistence, resume support
│   │   └── models.py             # CrawledPage dataclass
│   │
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── chunker.py            # MarkdownNodeParser, heading hierarchy, content cleaning
│   │   ├── metadata.py           # URL-to-breadcrumb derivation
│   │   └── models.py             # Chunk dataclass
│   │
│   ├── index/
│   │   ├── __init__.py
│   │   ├── embedder.py           # Embedding pipeline (planned)
│   │   └── store.py              # ChromaDB interface (planned)
│   │
│   ├── query/
│   │   ├── __init__.py
│   │   └── engine.py             # LlamaIndex query engine + LiteLLM (planned)
│   │
│   └── api/
│       ├── __init__.py
│       └── main.py               # FastAPI app (planned)
│
├── ui/
│   └── app.py                    # Streamlit prototype (planned)
│
├── data/                         # Gitignored
│   ├── checkpoints/              # Per-crawl JSONL checkpoint files
│   ├── chunks/                   # Per-crawl JSONL chunk files
│   └── chroma/                   # Persistent ChromaDB on disk (planned)
│
├── evals/
│   └── k8s_questions.json        # Retrieval eval question set (planned)
│
└── scripts/
    ├── crawl.py                  # CLI: crawl a documentation site
    ├── parse.py                  # CLI: parse checkpoint into chunks
    ├── index.py                  # CLI: embed + load into ChromaDB (planned)
    ├── query.py                  # CLI: quick query test (planned)
    ├── inspect_checkpoint.py     # CLI: validate and inspect crawl output
    ├── inspect_chunks.py         # CLI: validate and inspect chunk output
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
| Vector Store | ChromaDB | Persistent, local |
| Query | LlamaIndex + LiteLLM | Model-agnostic query engine |
| API | FastAPI | Async, production-ready |
| UI (proto) | Streamlit | Fast iteration |
| UI (v1) | Next.js + Shadcn | Planned |

---

## Setup

```bash
# Install dependencies
uv add crawl4ai python-dotenv pydantic rich llama-index-core

# First-time browser setup (downloads Chromium for crawl4ai)
uv run crawl4ai-setup
```

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_key_here
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

### 3. Parse checkpoint into chunks

Reads the checkpoint, filters low-quality pages, splits each page's markdown into heading-aware chunks, enriches with metadata, and saves to JSONL.

```bash
uv run python scripts/parse.py
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--checkpoint-dir` | `data/checkpoints` | Checkpoint input directory |
| `--output-dir` | `data/chunks` | Chunk output directory |

**Output:** `data/chunks/<run_id>_chunks.jsonl` — one chunk per line with full metadata.

---

### 4. Inspect and validate chunk output

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

### 5. Debug metadata (development)

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

**Secondary splitting:** Chunks exceeding 6,000 chars are split further on paragraph boundaries. Dense reference pages (API specs, metrics tables) that don't split cleanly on headings are handled this way. Chunks that can't be split by paragraph (flat tables) are left as-is — at 0.5% of total they're acceptable.

**Breadcrumb derivation:** Built from the URL path by stripping the docs root segment and humanising slugs. `kubernetes.io/docs/concepts/workloads/pods/` → `["Concepts", "Workloads", "Pods"]`. Used for navigation context in the query layer.

---

## Crawler Design Notes

**CSS selector:** The crawler targets `.td-content` on Kubernetes docs to extract only the article body, excluding the full left-sidebar navigation tree that would otherwise bloat every page to 100k+ chars. Different sites will need different selectors — this is configurable in `crawler.py`.

**Link scoping:** Only links within the seed URL's path prefix are followed. This prevents crawling into external sites, other language versions, or unrelated sections.

**Checkpointing:** Every page is written to disk immediately after fetch. If the crawl fails at page 600, re-running resumes from page 601. The JSONL format means each line is an independent record — partial files are safe to read.

**Known limitations:**
- JS-rendered pages that load after `domcontentloaded` may return empty or minimal content (e.g. the Kubernetes glossary). These are flagged by `inspect_checkpoint.py`.
- Non-HTML content (JSON feeds, XML sitemaps) that appears under the docs path will be crawled but return empty markdown. Filter these with `NON_HTML_EXTENSIONS` in the crawler or via `inspect_checkpoint.py` output.

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
| Embedding + ChromaDB | 🔄 Next |
| Query engine | ⏳ Planned |
| FastAPI backend | ⏳ Planned |
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