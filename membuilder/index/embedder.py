"""
Embedding pipeline via LiteLLM.

Routes to any LiteLLM-supported embedding provider:
  OpenAI  : text-embedding-3-small (default), text-embedding-3-large, text-embedding-ada-002
  Ollama  : ollama/nomic-embed-text, ollama/mxbai-embed-large
  Others  : any model string LiteLLM recognises

The Embedder depends only on the Embeddable protocol — it never imports Chunk
or AtomicNote directly. Both flow through the same code path.

Usage:
    embedder = Embedder(model="text-embedding-3-small")
    embeddings = embedder.embed_many(chunks, console=rich_console)

    # Embed a single query string (for retrieval at query time):
    vec = embedder.embed_query("What is a Pod?")
"""

import time
from collections.abc import Sequence

import litellm
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)

from membuilder.config import EMBEDDING_MODEL
from membuilder.index.protocol import Embeddable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Safety truncation: text-embedding-3-small supports 8191 tokens (≈ 32k chars).
# We truncate at 32k to stay within all mainstream embedding model limits.
MAX_EMBED_CHARS = 32_000

# Retry config for transient API errors (rate limits, timeouts).
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds; doubles each retry

# Cost per million tokens for known models (USD). Used for pre-run estimates.
# Ollama models are free (local inference).
COST_PER_MILLION_TOKENS: dict[str, float] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
}

# Rough chars-per-token approximation for cost estimation.
CHARS_PER_TOKEN = 4


class Embedder:
    """
    Batched embedding pipeline with retry logic and progress display.

    Args:
        model:      LiteLLM model string (e.g. "text-embedding-3-small",
                    "ollama/nomic-embed-text")
        batch_size: Number of texts per API call. 200 works well for OpenAI;
                    lower (50-100) for local Ollama models.
    """

    def __init__(
        self,
        model: str = EMBEDDING_MODEL,
        batch_size: int = 200,
    ) -> None:
        self.model = model
        self.batch_size = batch_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_many(
        self,
        items: Sequence[Embeddable],
        console: Console | None = None,
    ) -> list[list[float]]:
        """
        Embed a sequence of Embeddable items with batching and progress display.

        Returns embeddings in the same order as items. Safe to call on an
        already-indexed corpus: caller controls dedup via upsert.

        Args:
            items:   Sequence of Embeddable objects (Chunk, AtomicNote, etc.)
            console: Rich Console for progress output. Creates one if None.

        Returns:
            List of embedding vectors, one per item, preserving input order.
        """
        if console is None:
            console = Console()

        total = len(items)
        all_embeddings: list[list[float]] = []
        truncated_count = 0

        with Progress(
            SpinnerColumn(),
            "[progress.description]{task.description}",
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task(
                f"  Embedding  [cyan]{self.model}[/cyan]", total=total
            )

            for i in range(0, total, self.batch_size):
                batch = items[i : i + self.batch_size]
                texts: list[str] = []

                for item in batch:
                    text = item.text
                    if len(text) > MAX_EMBED_CHARS:
                        text = text[:MAX_EMBED_CHARS]
                        truncated_count += 1
                    texts.append(text)

                embeddings = self._embed_with_retry(texts)
                all_embeddings.extend(embeddings)
                progress.advance(task, len(batch))

        if truncated_count:
            console.print(
                f"  [yellow]⚠  {truncated_count} items truncated to "
                f"{MAX_EMBED_CHARS:,} chars (embedding context limit)[/yellow]"
            )

        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a single query string for retrieval. No progress display.

        Args:
            query: The query string to embed.

        Returns:
            Embedding vector as a list of floats.
        """
        embeddings = self._embed_with_retry([query])
        return embeddings[0]

    def cost_estimate(self, items: Sequence[Embeddable]) -> dict:
        """
        Estimate token count and cost for embedding a sequence of items.
        Used by the index.py CLI for --dry-run output.

        Returns dict with: total_chars, estimated_tokens, estimated_cost_usd,
        model, cost_known (bool).
        """
        total_chars = sum(min(len(item.text), MAX_EMBED_CHARS) for item in items)
        estimated_tokens = total_chars // CHARS_PER_TOKEN
        cost_per_m = COST_PER_MILLION_TOKENS.get(self.model)
        cost_known = cost_per_m is not None

        estimated_cost = (
            (estimated_tokens / 1_000_000) * cost_per_m if cost_known else None
        )

        return {
            "model": self.model,
            "total_chars": total_chars,
            "estimated_tokens": estimated_tokens,
            "estimated_cost_usd": estimated_cost,
            "cost_known": cost_known,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        """
        Call LiteLLM embedding with exponential backoff retry on transient errors.
        Raises on non-retryable errors (auth, bad model, etc.).
        """
        delay = RETRY_BASE_DELAY

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = litellm.embedding(model=self.model, input=texts)
                # LiteLLM response.data is a list of EmbeddingObject;
                # each has an .embedding attribute (list[float]).
                return [item["embedding"] for item in response.data]

            except litellm.exceptions.RateLimitError:
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(delay)
                delay *= 2

            except litellm.exceptions.ServiceUnavailableError:
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(delay)
                delay *= 2

        # Should not reach here
        raise RuntimeError("Embedding failed after max retries")
