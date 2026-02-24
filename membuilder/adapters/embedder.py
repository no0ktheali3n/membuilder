"""
LiteLLMEmbedder — adapter wrapping the existing Embedder to satisfy the
Embedder protocol.

Exposes a clean async embed(texts) interface. Delegates to the existing
batched, retry-safe Embedder._embed_with_retry() under the hood.
No LiteLLM types leak past this boundary.
"""

from __future__ import annotations
import asyncio

from membuilder.index.embedder import Embedder as _InnerEmbedder


class LiteLLMEmbedder:
    """
    Embedder adapter backed by LiteLLM.

    Routes embedding calls through the existing retry-safe pipeline.
    The embed() method is async — the synchronous LiteLLM call is run
    in a thread via asyncio.to_thread() to avoid blocking the event loop.

    Args:
        model: LiteLLM model string, always in "{provider}/{model}" format.
               e.g. "ollama/qwen3:4b", "openai/text-embedding-3-small"
    """

    def __init__(self, model: str) -> None:
        self._model = model
        self._inner = _InnerEmbedder(model=model)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of text strings, returning one vector per text.

        Runs the synchronous LiteLLM call off the event loop.
        Inherits batch retry logic from the underlying Embedder.
        """
        return await asyncio.to_thread(self._inner._embed_with_retry, texts)

    @property
    def model_id(self) -> str:
        """
        Unique model identifier — used for provenance in vault generation.md.

        Always in "{provider}/{model}" format so the Vault Writer can record
        which embedding model was used. Embeddings are model-tied: a vault
        embedded with one model cannot be queried with a different model's
        embeddings.
        """
        return self._model
