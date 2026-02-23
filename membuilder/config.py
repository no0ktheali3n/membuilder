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
"""

import os

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
