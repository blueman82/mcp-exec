"""RAG retriever — embeds queries and retrieves relevant context from ChromaDB.

Uses pure cosine similarity from the vector store. No hybrid re-ranking
formula, no hardcoded weights, no recency decay functions. Timestamps
are embedded in each document's text, so the LLM reasons about temporal
relevance naturally from the context it receives.
"""

from typing import Any, Dict, List

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class Retriever:
    """Embeds user queries and retrieves relevant context."""

    def __init__(self, embeddings_client, vector_store):
        """
        Args:
            embeddings_client: AzureEmbeddingsClient instance
            vector_store: ChromaVectorStore instance
        """
        self._embeddings_client = embeddings_client
        self._vector_store = vector_store

    async def retrieve(
        self,
        query: str,
        channel_id: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant context for a query using pure semantic similarity.

        Pipeline:
        1. Embed the query using ada-002
        2. Retrieve top_k results from ChromaDB (cosine similarity, optionally filtered by channel)

        No re-ranking step — ChromaDB's cosine distance IS the relevance score.
        Timestamps are in each document's text, so the LLM handles temporal reasoning.

        Args:
            query: The user's question.
            channel_id: Filter results to this channel. None = cross-channel search.
            top_k: Number of results to return.

        Returns:
            List of context dicts with keys: id, text, metadata, score
        """
        # Embed the query
        query_embedding = await self._embeddings_client.embed_query(query)

        # Retrieve from vector store — cosine similarity, no post-processing
        candidates = await self._vector_store.query(
            query_embedding=query_embedding,
            channel_id=channel_id,
            top_k=top_k,
        )

        if not candidates:
            logger.info("No context found for channel %s", channel_id)
            return []

        # Convert cosine distance to similarity score for downstream use
        results = []
        for candidate in candidates:
            similarity = max(0.0, 1.0 - candidate.get("distance", 1.0))
            results.append(
                {
                    "id": candidate["id"],
                    "text": candidate["text"],
                    "metadata": candidate.get("metadata", {}),
                    "score": similarity,
                }
            )

        logger.info(
            "Retrieved %d results for channel %s. Top: %.3f, Bottom: %.3f",
            len(results),
            channel_id,
            results[0]["score"] if results else 0,
            results[-1]["score"] if results else 0,
        )

        return results
