# Changelog

All notable changes to membuilder are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

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