from __future__ import annotations

import asyncio
from functools import partial

import voyageai

from app.core.config import settings

# Voyage AI client is synchronous; we run it in a thread pool to avoid blocking.
_client: voyageai.Client | None = None


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
    return _client


async def embed(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using Voyage AI voyage-3 model (1024 dimensions).

    Args:
        texts: List of text strings to embed.

    Returns:
        List of 1024-dimensional embedding vectors, one per input text.
    """
    if not texts:
        return []

    loop = asyncio.get_event_loop()
    client = _get_client()

    def _embed_sync() -> list[list[float]]:
        result = client.embed(texts, model="voyage-3", input_type="document")
        return result.embeddings

    embeddings = await loop.run_in_executor(None, _embed_sync)
    return embeddings
