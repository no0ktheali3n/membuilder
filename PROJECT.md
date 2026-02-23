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
[indexer v1]    LiteLLM embeddings → ChromaDB (raw chunks)              ← 🔄 v0.3.0
  ↓
[query v1]      LlamaIndex semantic search                              ← ⏳ v0.4.0
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
├── parser/           ✅ v0.2.0  — chunker, metadata, models
├── index/            🔄 v0.3.0  — embedder.py, store.py
├── query/            ⏳ v0.4.0  — engine.py, semantic.py | v0.7.0 graph.py
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
| Vector Store | ChromaDB | Persistent, local |
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
| v0.3.0 | Indexer v1 | LiteLLM embeddings, ChromaDB persistence, `Embeddable` protocol | 🔄 Next |
| v0.4.0 | Query v1 | LlamaIndex semantic search, FastAPI stub, basic query CLI | ⏳ |
| v0.5.0 | Synthesizer | Concept extraction, atomic notes, wiki-link resolution, MOC generation | ⏳ |
| v0.6.0 | Vault Writer | Obsidian vault output, CLAUDE.md, INDEX.md, vault validator | ⏳ |
| v0.7.0 | Query v2 + Indexer v2 | Re-embed vault files, graph traversal, hybrid retrieval | ⏳ |
| v0.8.0 | API | Full FastAPI — vault CRUD, async job management, query endpoints | ⏳ |
| v0.9.0 | UI | Streamlit prototype, then Next.js v1 | ⏳ |

---

## Status

> Update this section at the start/end of each session.

**Current version:** v0.2.0  
**Active sprint:** v0.3.0 — Indexer  
**Blocked on:** Nothing  
**Last updated:** 2026-02-23

### Completed This Session
- Reviewed deepwiki-open (AsyncFuncAI) — confirmed not overlapping with membuilder's scope
- Established AdalFlow vs ChromaDB+LlamaIndex decision (ChromaDB wins for our use case)
- Ingested Heinrich's vault philosophy article + OpenClaw/Obsidian video transcript
- Expanded project vision: membuilder is a domain vault factory, not just a RAG index
- Revised full architecture to include synthesizer + vault writer layers
- Created this PROJECT.md as central source of truth

### Next Session Start
- Begin v0.3.0: `membuilder/index/embedder.py` + `membuilder/index/store.py`
- Design `Embeddable` protocol first — both `Chunk` (v0.3.0) and `AtomicNote` (v0.7.0) must implement it
- Add `scripts/index.py` CLI entry point

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

---

## Key Design Constraints

**`Embeddable` protocol (critical for v0.3.0):**  
The ChromaDB layer must not be coupled to the `Chunk` dataclass. Both `Chunk` (parser output) and `AtomicNote` (synthesizer output) need to flow through the same indexer. Define a protocol with `id: str`, `text: str`, `metadata: dict` — both implement it.

**Vault note quality bar:**  
A note is only useful if it can be linked from elsewhere and still make sense in isolation. Notes should be composable. Named as claims or concepts, not topics ("quality is the hard part" not "thoughts on quality"). MOC breadcrumb trails let agents orient without reading everything.

**Agent orientation pattern:**  
Agents load `INDEX.md` first (all notes, one line each), then navigate to the relevant MOC, then follow wiki-links to build understanding. This is the read pattern we design for — not just "find the most similar chunk."

**No vendor lock-in:**  
Vault output is plain markdown files with YAML frontmatter. No database required to read it. Any LLM with file access can consume it. ChromaDB is an acceleration layer, not the source of truth.

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

---

## Session Notes

> Running log — prepend new entries, keep last 5 sessions.

### 2026-02-23
- Full project sync after scope expansion
- Established vault vision as core differentiator
- Revised architecture, roadmap, ADRs documented above
- v0.3.0 is next: embedder + ChromaDB with `Embeddable` protocol
- PROJECT.md created as central source of truth