"""Tests for RAG retriever (pure cosine similarity, no re-ranking)."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.rag.retriever import Retriever


@pytest.fixture
def mock_embeddings_client():
    client = AsyncMock()
    client.embed_query.return_value = [0.1] * 1536
    return client


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    return store


@pytest.fixture
def retriever(mock_embeddings_client, mock_vector_store):
    return Retriever(
        embeddings_client=mock_embeddings_client,
        vector_store=mock_vector_store,
    )


class TestRetrieve:
    @pytest.mark.asyncio
    async def test_empty_results(self, retriever, mock_vector_store):
        mock_vector_store.query.return_value = []
        results = await retriever.retrieve("what happened?", "C123")
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_similarity_scores(self, retriever, mock_vector_store):
        mock_vector_store.query.return_value = [
            {
                "id": "doc1",
                "text": "[1.0] <@U1>: hello world",
                "metadata": {"channel_id": "C123"},
                "distance": 0.1,
            },
            {
                "id": "doc2",
                "text": "[2.0] <@U2>: hi there",
                "metadata": {"channel_id": "C123"},
                "distance": 0.5,
            },
        ]

        results = await retriever.retrieve("test", "C123")
        assert len(results) == 2
        # Cosine distance to similarity: max(0.0, 1 - distance)
        assert results[0]["score"] == pytest.approx(0.9)
        assert results[1]["score"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_passes_top_k_to_vector_store(self, retriever, mock_vector_store):
        mock_vector_store.query.return_value = []
        await retriever.retrieve("test", "C123", top_k=30)
        mock_vector_store.query.assert_called_once_with(
            query_embedding=[0.1] * 1536,
            channel_id="C123",
            top_k=30,
        )

    @pytest.mark.asyncio
    async def test_embeds_query(self, retriever, mock_embeddings_client, mock_vector_store):
        mock_vector_store.query.return_value = []
        await retriever.retrieve("my question", "C123")
        mock_embeddings_client.embed_query.assert_called_once_with("my question")

    @pytest.mark.asyncio
    async def test_no_reranking_step(self, retriever, mock_vector_store):
        """Results come straight from ChromaDB — no re-ranking formula."""
        candidates = [
            {
                "id": f"doc_{i}",
                "text": f"text {i}",
                "metadata": {},
                "distance": 0.2,
            }
            for i in range(20)
        ]
        mock_vector_store.query.return_value = candidates

        results = await retriever.retrieve("test", "C123", top_k=20)
        # All 20 returned — no secondary filtering
        assert len(results) == 20
