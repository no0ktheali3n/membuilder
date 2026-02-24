# membuilder — Project Source of Truth

> Drop this file at your repo root. Paste it at the start of each dev session to sync context.  
> Update `## Status`, `## Decisions Log`, and `## Session Notes` as the project evolves.

---

## What This Is

**membuilder** is a domain vault factory — a self-building AI knowledge engine that transforms documentation sites into structured, agent-ready knowledge bases. It crawls authoritative sources, parses and synthesizes the content into an Obsidian-compatible vault (wiki-linked markdown files with MOC navigation), and indexes that vault for hybrid semantic + graph retrieval.

The output is a **domain expert vault** any AI agent can load as a persistent second brain — not just a search index, but an encoded knowledge structure that captures both *what* a domain contains and *how concepts relate*.

**Inspired by:** DeepWiki (documentation RAG), Heinrich's Obsidian vault philosophy (arscontexta), and the Ars Contexta pattern of vaults as agent cognitive architecture.

**Not:** A code documentation generator (that's deepwiki-open). A personal note-taking assistant. A chatbot.

---

## Vision

```
Point membuilder at any docs URL
       ↓
It crawls, parses, and synthesizes the content
       ↓
Produces an Obsidian-compatible domain vault:
  - Atomic concept notes (one concept = one file)
  - Wiki-links connecting related concepts
  - MOC hierarchy for agent navigation
  - CLAUDE.md teaching any agent the domain rules
  - INDEX.md for fast agent orientation
       ↓
Indexes the vault into ChromaDB for semantic search
       ↓
Any agent can query via:
  - Semantic search (vector similarity)
  - Graph traversal (wiki-link navigation)
  - Hybrid (vector hit → wiki-link expansion)
```

---

## Architecture

### Full Pipeline

```
URL(s)
  ↓
[crawler]       crawl4ai BFS — domain-scoped, checkpointed JSONL       ← ✅ v0.1.0
  ↓
[parser]        MarkdownNodeParser — heading-aware chunks + metadata    ← ✅ v0.2.0
  ↓
[indexer v1]    LiteLLM embeddings → ChromaDB (raw chunks)              ← ✅ v0.3.0
  ↓
[protocols]     Adapter layer — all backends behind swappable interfaces ← ✅ v0.3.1
  ↓
[query v1]      LlamaIndex semantic search                              ← 🔄 v0.4.0
  ↓
[synthesizer]   Concept extraction → atomic notes → wiki-links → MOCs  ← ⏳ v0.5.0
  ↓
[vault writer]  Obsidian vault output + CLAUDE.md + INDEX.md            ← ⏳ v0.6.0
  ↓
[indexer v2]    Re-embed vault files (replaces raw chunks)              ← ⏳ v0.7.0
  ↓
[query v2]      Semantic + graph traversal hybrid                       ← ⏳ v0.7.0
  ↓
[api]           FastAPI — job management, vault CRUD, query endpoints   ← ⏳ v0.8.0
  ↓
[ui]            Streamlit prototype → Next.js v1                        ← ⏳ v0.9.0
```

### Module Map

```
membuilder/
├── crawler/          ✅ v0.1.0  — crawl4ai BFS, checkpointing, models
├── parser/           ✅ v0.2.0  — chunker, metadata, models (Chunk implements Embeddable)
├── index/            ✅ v0.3.0  — protocol.py, embedder.py, store.py
├── protocols.py      ✅ v0.3.1  — Crawler, Chunker, Embedder, VectorStore protocols + shared types
├── adapters/         ✅ v0.3.1  — adapter layer; vector_store/milvus.py
├── query/            🔄 v0.4.0  — engine.py, semantic.py | v0.7.0 graph.py
├── synthesizer/      ⏳ v0.5.0  — concept.py, atomic.py, linker.py, moc.py, frontmatter.py, models.py
├── vault/            ⏳ v0.6.0  — writer.py, claude_md.py, index.py, validator.py, templates/
└── api/              ⏳ v0.8.0  — main.py
```

---

## Vault Output Schema

Every domain vault membuilder produces has this structure:

```
{domain}-vault/
├── CLAUDE.md                    # Domain system prompt — teaches agent the rules
├── INDEX.md                     # One-line description of every note
├── 00_moc/                      # Maps of Content — navigation layer
│   ├── ROOT.md                  # Top-level domain MOC
│   └── {subdomain}/
│       └── MOC.md
├── 01_concepts/                 # Atomic concept notes (one per entity)
├── 02_howto/                    # Procedural notes
├── 03_reference/                # API specs, config schemas
├── 04_relationships/            # Cross-concept relationship notes
└── .meta/
    ├── vault.yaml               # Domain, version, crawl date, source URLs
    └── build_log.jsonl
```

Note frontmatter schema:
```yaml
---
title: Pod
domain: kubernetes
subdomain: workloads
tags: [core-concept, compute, scheduling]
source: https://kubernetes.io/docs/concepts/workloads/pods/
version: "1.29"
related: [ReplicaSet, Deployment, StatefulSet, init-container]
crawled_at: 2026-02-23
---
```

---

## Stack

| Layer | Tool | Notes |
|---|---|---|
| Crawler | crawl4ai | Async, JS rendering, markdown output |
| Parser | LlamaIndex MarkdownNodeParser | Heading-aware chunking |
| Embeddings | OpenAI / Ollama via LiteLLM | Model-agnostic router |
| Vector Store | ChromaDB / Milvus via adapter | Swap via `membuilder.yaml` |
| Query | LlamaIndex + LiteLLM | Semantic search |
| Synthesizer | spaCy + LLM-assisted | Heuristic-first, LLM for ambiguity |
| API | FastAPI | Async |
| UI (proto) | Streamlit | Fast iteration |
| UI (v1) | Next.js + Shadcn | Planned |
| Package mgmt | uv | Project standard |
| Python | 3.12 | Project standard |

---

## Roadmap

| Version | Stage | Description | Status |
|---|---|---|---|
| v0.1.0 | Crawler | BFS crawl, checkpointing, validation tooling | ✅ Done |
| v0.2.0 | Parser | Heading-aware chunking, metadata, validation tooling | ✅ Done |
| v0.3.0 | Indexer v1 | Embeddable protocol, LiteLLM embeddings, ChromaDB, index validation | ✅ Done |
| v0.3.1 | Protocol layer | Runtime-checkable protocols, adapter pattern, Milvus support, deterministic chunk IDs, enriched metadata, `membuilder.yaml` config | ✅ Done |
| v0.4.0 | Query v1 | LlamaIndex semantic search, FastAPI stub, query CLI | 🔄 Next |
| v0.5.0 | Synthesizer | Concept extraction, atomic notes, wiki-link resolution, MOC generation | ⏳ |
| v0.6.0 | Vault Writer | Obsidian vault output, CLAUDE.md, INDEX.md, vault validator | ⏳ |
| v0.7.0 | Query v2 + Indexer v2 | Re-embed vault files, graph traversal, hybrid retrieval | ⏳ |
| v0.8.0 | API | Full FastAPI — vault CRUD, async job management, query endpoints | ⏳ |
| v0.9.0 | UI | Streamlit prototype, then Next.js v1 | ⏳ |

---

## Status

> Update this section at the start/end of each session.

**Current version:** v0.3.1  
**Active sprint:** v0.4.0 — Query v1  
**Blocked on:** Nothing  
**Last updated:** 2026-02-24

### Completed This Session
- Shipped v0.3.1: protocol layer, adapter pattern, Milvus support (Lite + server), deterministic chunk IDs (`sha256(url + "::" + chunk_index)[:16]`), enriched metadata fields, `membuilder.yaml` config system
- Validated idempotency against 100 Kubernetes corpus pages (1,776 chunks) — zero new inserts on second run
- Added `validate_idempotency.py` and `validate_store_parity.py` scripts

### Next Session Start
- Begin v0.4.0: `membuilder/query/engine.py` — LlamaIndex query engine wired to ChromaDB
- `scripts/query.py` — CLI for ad-hoc queries against any collection
- FastAPI stub: `membuilder/api/main.py` — single `/query` endpoint
- Design context assembly contract now (what gets passed to LLM, in what order) — v0.7.0 must extend this, not rewrite it

---

## Architecture Decision Records (ADRs)

### ADR-001: crawl4ai over Firecrawl
**Date:** 2026-02-22  
**Decision:** Use crawl4ai (free, open-source) over Firecrawl (paid API)  
**Rationale:** We need to crawl tens of thousands of pages. Per-page API costs at that scale are prohibitive. crawl4ai handles JS rendering, CSS selectors, and async batching natively.  
**Status:** Accepted

### ADR-002: ChromaDB + LlamaIndex over AdalFlow
**Date:** 2026-02-23  
**Decision:** Use ChromaDB for vector storage and LlamaIndex for query orchestration instead of AdalFlow  
**Rationale:** AdalFlow's `LocalDB` is a flat file store — no metadata filtering, degrades past ~50k docs, no proper collection management. AdalFlow's actual value prop is prompt auto-optimization (LLM-AutoDiff), which is irrelevant to our use case. ChromaDB handles millions of vectors, has first-class metadata filtering, and LlamaIndex's `MarkdownNodeParser` was built exactly for our chunking needs.  
**Status:** Accepted

### ADR-003: Vault vision — synthesizer layer
**Date:** 2026-02-23  
**Decision:** Build a synthesizer layer that converts parsed chunks into Obsidian-compatible atomic notes before indexing  
**Rationale:** Flat chunk retrieval returns semantically similar text fragments. Vault-structured retrieval returns contextually linked knowledge nodes with navigable relationships. The vault encodes domain structure (MOC hierarchy, wiki-links, concept relationships), not just content. Agents consuming vaults have cognitive architecture, not just a search engine.  
**Status:** Accepted

### ADR-004: Build RAG pipeline first, synthesizer second
**Date:** 2026-02-23  
**Decision:** Complete v0.3.0 (embedder + ChromaDB) and v0.4.0 (query v1) before building the synthesizer  
**Rationale:** The synthesizer is the highest-risk component — concept dedup quality, LLM cost at scale, MOC hierarchy correctness are all unknowns. Building a working end-to-end RAG system first gives us (a) a usable product sooner, (b) a quality baseline to compare vault-structured retrieval against, and (c) a lower-risk environment to experiment with synthesizer design. The indexer is designed with an `Embeddable` protocol so v0.7.0 can feed vault notes through the same code path without rework.  
**Status:** Accepted

### ADR-005: Heuristic-first synthesizer with LLM for ambiguity
**Date:** 2026-02-23  
**Decision:** Use spaCy/NLP heuristics as the primary path for concept extraction and atomic note splitting; invoke LLM only for conflict resolution and CLAUDE.md generation  
**Rationale:** LLM-per-page synthesis at 10k+ pages costs $10-100+ per domain build. Heading structure and NLP cover ~80% of the work at 5% of the cost. LLM quality matters most for CLAUDE.md (the agent's domain system prompt) and for disambiguation of cross-concept relationships — not for splitting a heading-structured doc into atomic notes. An `--llm-enhanced` flag will be available for users who want maximum fidelity.  
**Status:** Accepted (pending synthesizer implementation)

### ADR-006: LiteLLM as unified model router
**Date:** 2026-02-23  
**Decision:** Use LiteLLM as the routing layer for all embedding and synthesis calls rather than LlamaIndex's native provider abstractions  
**Rationale:** Production deployment targets internal org models (vLLM, internal proxies) that won't include Claude. LiteLLM's provider abstraction means one config change moves between OpenAI, Ollama, and any OpenAI-compatible internal endpoint with no code changes. All model references are env-var driven via `config.py` — no hardcoded model names anywhere in the codebase.  
**Status:** Accepted

### ADR-007: No hardcoded model names
**Date:** 2026-02-23  
**Decision:** All model references must come from environment variables via `config.py`, with sensible local-dev defaults  
**Rationale:** Production deployments will use internal org models. Hardcoding `claude-sonnet-4-6` or `text-embedding-3-small` would require code changes to deploy. Env-var driven config makes this purely operational.  
**Implementation:** `MEMBUILDER_EMBEDDING_MODEL` (default: `text-embedding-3-small`), `MEMBUILDER_SYNTHESIS_MODEL` (default: `claude-sonnet-4-6`)  
**Status:** Accepted

### ADR-008: Adapter pattern over direct dependency coupling
**Date:** 2026-02-24  
**Decision:** All concrete dependencies (vector stores, embedders, crawlers, chunkers) are wrapped behind runtime-checkable protocol interfaces defined in `membuilder/protocols.py`  
**Rationale:** Direct coupling to ChromaDB or LlamaIndex throughout the codebase would make backend swaps expensive. The adapter pattern isolates change to a single file per backend. `MembuilderConfig` loads `membuilder.yaml` and returns the correct adapter via factory methods — callers never import ChromaDB or Milvus directly.  
**Status:** Accepted

### ADR-009: Deterministic chunk IDs
**Date:** 2026-02-24  
**Decision:** Chunk IDs are `sha256(url + "::" + chunk_index)[:16]`, replacing the previous random UUIDs  
**Rationale:** Random UUIDs make idempotent upsert unreliable across re-runs — the same logical chunk gets a new ID on every parse, causing index bloat. Deterministic IDs based on content address (url + position) mean re-indexing the same corpus produces zero net-new records. This is a hard requirement for v0.6.0 Vault Writer back-references and v0.7.0 graph traversal.  
**Note:** Full corpus re-embed required after this release to backfill deterministic IDs into existing collections. Do this before beginning v0.6.0 Vault Writer work.  
**Status:** Accepted

---

## Key Design Constraints

**`Embeddable` protocol (implemented v0.3.0):**  
The ChromaDB layer depends on `protocol.Embeddable` — not on `Chunk` directly. Both `Chunk` (parser output) and `AtomicNote` (synthesizer output, v0.7.0) implement `id: str`, `text: str`, `metadata: dict`. This is the forward-compatibility contract that prevents an indexer rewrite in v0.7.0.

**Protocol + adapter layer (implemented v0.3.1):**  
All concrete dependencies are behind swappable interfaces (`protocols.py`). `MembuilderConfig` loads `membuilder.yaml` and returns correct adapters via factory methods. No caller imports ChromaDB or Milvus directly. Adding a new backend = one new adapter file.

**Deterministic chunk IDs (implemented v0.3.1):**  
`sha256(url + "::" + chunk_index)[:16]`. Required for idempotent upsert, vault back-references (v0.6.0), and graph traversal (v0.7.0). Full corpus re-embed required before v0.6.0 work begins to ensure all existing collections carry deterministic IDs.

**Milvus Lite platform constraint:**  
`milvus-lite` is Linux/macOS only. Windows users must use full Milvus server via URI, or ChromaDB. Parity validation (`validate_store_parity.py`) is deferred to CI on Linux.

**Context assembly contract (design in v0.4.0):**  
The query engine's context assembly — what gets passed to the LLM, in what order, with what framing — must be designed as an extensible contract in v0.4.0. v0.7.0 extends this (retrieved chunks + wiki-link expanded context) rather than rewriting it. Don't bake flat chunk retrieval assumptions into the synthesis prompt structure.

**Vault note quality bar:**  
A note is only useful if it can be linked from elsewhere and still make sense in isolation. Notes should be composable. Named as claims or concepts, not topics. MOC breadcrumb trails let agents orient without reading everything.

**Agent orientation pattern:**  
Agents load `INDEX.md` first (all notes, one line each), then navigate to the relevant MOC, then follow wiki-links to build understanding. This is the read pattern we design for — not just "find the most similar chunk."

**No vendor lock-in:**  
Vault output is plain markdown files with YAML frontmatter. No database required to read it. Any LLM with file access can consume it. ChromaDB/Milvus are acceleration layers, not the source of truth.

---

## Data Quality Reference (Kubernetes Docs)

Reference run against `https://kubernetes.io/docs/` — February 2026:

**Crawl (v0.1.0):**
```
Total pages  : 798 / 0 failed
Size         : min 1 / max 248,580 / avg 14,011 / median 7,904 chars
Critical     : 3  (1 oversized spec, 2 non-HTML feeds)
Warnings     : 45 (empty section indexes, dense reference pages)
```

**Parse (v0.2.0):**
```
Total chunks : 9,783 from 773 pages (25 skipped — empty/near-empty)
Size         : min 100 / max 61,944 / avg 1,024 / median 614 chars
Flagged      : 52 chunks (0.5%) — oversized reference tables, acceptable
Section dist : Reference 4,100 / Concepts 2,376 / Tasks 2,292 / Other 1,015
```

**Index (v0.3.0):**
```
Records      : 9,783 / coverage 100%
Embed model  : ollama/qwen3-embedding:4b (local, no cost)
Truncated    : 8 items (32k char limit — oversized reference tables)
Embed time   : 53 min (CPU-bound — VRAM was full, one-time cost)
DB write     : 8.3s
Spot-check   : 5/5 queries semantically correct, scores 0.77–0.84
```

**Idempotency validation (v0.3.1):**
```
Sample       : 100 pages / 1,776 chunks
Second run   : 0 new inserts (stable collection count confirmed)
Chunk IDs    : deterministic sha256 — consistent across re-runs
```

---

## Session Notes

> Running log — prepend new entries, keep last 5 sessions.

### 2026-02-24
- Shipped v0.3.1: protocol layer (`protocols.py`), adapter pattern (`adapters/`), Milvus support (Lite + server)
- Chunk IDs migrated to deterministic `sha256(url + "::" + chunk_index)[:16]` — idempotency validated
- `MarkdownChunker` enriched with full metadata: `url`, `breadcrumb`, `chunk_index`, `domain`, `crawled_at`, `tags`, `heading`
- Added single-chunk fallback for pages below LlamaIndex minimum content threshold (previously silently dropped)
- `membuilder.yaml` config system live — full pipeline driven by YAML, no code changes needed to swap backends
- Added ADR-008 (adapter pattern) and ADR-009 (deterministic chunk IDs)
- **Pending:** full corpus re-embed to backfill deterministic IDs before v0.6.0 work

### 2026-02-23
- Full project sync after scope expansion
- Established vault vision as core differentiator
- Revised architecture, roadmap, ADRs 001-007 documented
- Built and validated v0.3.0 — Embeddable protocol + LiteLLM embedder + ChromaDB store
- Embedded full Kubernetes docs corpus locally using qwen3-embedding:4b via Ollama
- Retrieval quality confirmed via spot-check: 0.77–0.84 scores, all queries correct
- PROJECT.md, README.md, CHANGELOG.md updated to reflect v0.3.0 completion
- v0.4.0 is next: query engine, query CLI, FastAPI stub