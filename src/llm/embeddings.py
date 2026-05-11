"""
Gemini text-embedding-004 wrapper.

Used for ingesting the general_kb_entry table and embedding user queries
at retrieval time. Supports both the modern `google-genai` SDK and the
legacy `google.generativeai` package — same pattern as src/llm/client.py.

Public API:
    async embed_document(text: str) -> list[float]      # for indexing
    async embed_query(text: str) -> list[float]         # for similarity search
    async embed_documents(texts: list[str]) -> list[list[float]]    # batched
"""

import asyncio
from typing import Literal

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIM = 768


class _EmbeddingClient:
    """Lazy-init wrapper around whichever Gemini SDK is available."""

    def __init__(self) -> None:
        self._sdk_mode: str | None = None
        self._client = None
        self._legacy = None

    def _ensure_initialised(self) -> None:
        if self._sdk_mode is not None:
            return
        api_key = settings.google_api_key
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not configured — embedding requires Gemini API access."
            )
        try:
            from google import genai
            self._client = genai.Client(api_key=api_key)
            self._sdk_mode = "genai"
            return
        except ImportError:
            pass
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            self._legacy = legacy_genai
            self._sdk_mode = "legacy"
            return
        except ImportError as exc:
            raise RuntimeError(
                "No Gemini SDK installed — pip install google-genai (preferred) "
                "or google-generativeai."
            ) from exc

    async def embed(
        self,
        text: str,
        task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"],
    ) -> list[float]:
        self._ensure_initialised()
        if self._sdk_mode == "genai":
            return await asyncio.to_thread(self._embed_genai, text, task_type)
        return await asyncio.to_thread(self._embed_legacy, text, task_type)

    def _embed_genai(self, text: str, task_type: str) -> list[float]:
        from google.genai import types
        response = self._client.models.embed_content(  # type: ignore[union-attr]
            model=f"models/{EMBEDDING_MODEL}",
            contents=text,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        # The new SDK returns ContentEmbedding objects with `.values`.
        emb = response.embeddings[0]
        values = getattr(emb, "values", None) or emb["values"]  # type: ignore[index]
        return list(values)

    def _embed_legacy(self, text: str, task_type: str) -> list[float]:
        response = self._legacy.embed_content(  # type: ignore[union-attr]
            model=f"models/{EMBEDDING_MODEL}",
            content=text,
            task_type=task_type,
        )
        # Legacy SDK returns a dict with "embedding": list[float]
        emb = response["embedding"]
        return list(emb)


_client = _EmbeddingClient()


async def embed_document(text: str) -> list[float]:
    """Embed an indexable KB entry. Use this for ingestion."""
    if not text.strip():
        raise ValueError("Cannot embed empty text")
    return await _client.embed(text, task_type="RETRIEVAL_DOCUMENT")


async def embed_query(text: str) -> list[float]:
    """Embed a user query for similarity search."""
    if not text.strip():
        raise ValueError("Cannot embed empty text")
    return await _client.embed(text, task_type="RETRIEVAL_QUERY")


async def embed_documents(texts: list[str], concurrency: int = 4) -> list[list[float]]:
    """Embed a batch of documents concurrently, bounded by *concurrency*."""
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(t: str) -> list[float]:
        async with semaphore:
            return await embed_document(t)

    return await asyncio.gather(*(_one(t) for t in texts))
