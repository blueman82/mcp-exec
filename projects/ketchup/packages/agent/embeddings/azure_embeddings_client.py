"""Azure OpenAI Embeddings Client for Ketchup Agent."""

import asyncio
from typing import List, Optional

import aiohttp

from packages.core.constants import (
    AZURE_OPENAI_EMBEDDINGS_ENDPOINT,
    EMBEDDINGS_API_VERSION,
)
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

EMBEDDING_BATCH_SIZE = 16
MAX_CONCURRENT_REQUESTS = 2
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 1.0


class AzureEmbeddingsClient:
    """Async client for Azure OpenAI text-embedding-ada-002."""

    def __init__(self, secrets_manager):
        self._secrets_manager = secrets_manager
        self._api_key: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._endpoint = f"{AZURE_OPENAI_EMBEDDINGS_ENDPOINT}?api-version={EMBEDDINGS_API_VERSION}"

    async def initialize(self) -> None:
        """Initialize API key and HTTP session."""
        self._api_key = await self._secrets_manager.get_azure_openai_lb_api_key()
        if not self._api_key:
            raise ValueError("Azure OpenAI API key not found in secrets")
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
        )
        logger.info("AzureEmbeddingsClient initialized")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts, batching into groups of 16.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each 1536-dim float list).
        """
        if not texts:
            return []

        all_embeddings: List[Optional[List[float]]] = [None] * len(texts)
        batches = [
            texts[i : i + EMBEDDING_BATCH_SIZE] for i in range(0, len(texts), EMBEDDING_BATCH_SIZE)
        ]

        batch_tasks = []
        for batch_idx, batch in enumerate(batches):
            batch_tasks.append(self._embed_batch(batch, batch_idx, all_embeddings))

        await asyncio.gather(*batch_tasks)

        # Verify all embeddings were populated
        for i, emb in enumerate(all_embeddings):
            if emb is None:
                raise RuntimeError(f"Embedding for text at index {i} was not computed")

        return all_embeddings  # type: ignore

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single query text.

        Args:
            query: The query string to embed.

        Returns:
            1536-dimensional embedding vector.
        """
        results = await self.embed_texts([query])
        return results[0]

    async def _embed_batch(
        self,
        batch: List[str],
        batch_idx: int,
        results: List[Optional[List[float]]],
    ) -> None:
        """Embed a single batch with retry logic."""
        async with self._semaphore:
            start_idx = batch_idx * EMBEDDING_BATCH_SIZE
            backoff = INITIAL_BACKOFF_SECONDS

            for attempt in range(MAX_RETRIES):
                try:
                    embeddings = await self._call_api(batch)
                    for i, emb in enumerate(embeddings):
                        results[start_idx + i] = emb
                    return
                except EmbeddingRateLimitError:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(
                            "Rate limited on batch %d, retrying in %.1fs (attempt %d/%d)",
                            batch_idx,
                            backoff,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        await asyncio.sleep(backoff)
                        backoff *= 2
                    else:
                        raise
                except EmbeddingAPIError as e:
                    if attempt < MAX_RETRIES - 1 and e.retryable:
                        logger.warning(
                            "Retryable error on batch %d: %s, retrying in %.1fs",
                            batch_idx,
                            e,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        backoff *= 2
                    else:
                        raise

    async def _call_api(self, texts: List[str]) -> List[List[float]]:
        """Make a single API call to the embeddings endpoint."""
        if not self._session or self._session.closed:
            raise RuntimeError("Client not initialized. Call initialize() first.")

        headers = {
            "Content-Type": "application/json",
            "api-key": self._api_key,
        }
        payload = {"input": texts}

        async with self._session.post(self._endpoint, headers=headers, json=payload) as response:
            if response.status == 429:
                raise EmbeddingRateLimitError("Azure OpenAI rate limit exceeded")
            if response.status >= 500:
                body = await response.text()
                raise EmbeddingAPIError(f"Server error {response.status}: {body}", retryable=True)
            if response.status >= 400:
                body = await response.text()
                raise EmbeddingAPIError(f"Client error {response.status}: {body}", retryable=False)

            data = await response.json()
            # Azure returns: {"data": [{"embedding": [...], "index": 0}, ...]}
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]

    async def cleanup(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("AzureEmbeddingsClient session closed")


class EmbeddingRateLimitError(Exception):
    """Raised when Azure OpenAI returns 429."""

    pass


class EmbeddingAPIError(Exception):
    """Raised on API errors."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable
