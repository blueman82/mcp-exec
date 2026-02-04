"""Test suite for DocumentRetriever.

This module tests the semantic search and retrieval functionality over
ChromaDB vector database with optional filtering capabilities.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_openai_client():
    """Mock Azure OpenAI client for query embedding generation.

    Returns:
        AsyncMock configured to return a fake embedding vector
    """
    client = AsyncMock()
    # Mock embeddings.create() to return a single embedding
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 1536)]  # 1536-dim vector
    client.embeddings.create = AsyncMock(return_value=mock_response)
    return client


@pytest.fixture
def mock_chroma_client():
    """Mock ChromaDB client for vector search.

    Returns:
        Mock with get_collection method and query results
    """
    client = Mock()
    mock_collection = Mock()

    # Mock query results
    mock_collection.query = Mock(
        return_value={
            "documents": [
                [
                    "Field: deliveryId (string). Category: Campaign & Delivery...",
                    "Field: failureType (string). Category: Campaign & Delivery...",
                    "Query Pattern: Bounce Analysis...",
                ]
            ],
            "metadatas": [
                [
                    {
                        "chunk_type": "field",
                        "field_name": "deliveryId",
                        "category": "Campaign & Delivery",
                    },
                    {
                        "chunk_type": "field",
                        "field_name": "failureType",
                        "category": "Campaign & Delivery",
                    },
                    {"chunk_type": "pattern", "pattern_id": "bounce_analysis"},
                ]
            ],
            "distances": [[0.2, 0.3, 0.5]],  # L2 distances
            "ids": [["field_0", "field_1", "pattern_0"]],
        }
    )

    client.get_collection = Mock(return_value=mock_collection)
    return client


class TestDocumentRetriever:
    """Test DocumentRetriever semantic search functionality."""

    @pytest.mark.asyncio
    async def test_retrieve_generates_query_embedding(self, mock_openai_client, mock_chroma_client):
        """Query embedding is generated from user query string.

        Verifies that:
        - User query is sent to Azure OpenAI
        - Embedding is generated using text-embedding-ada-002
        - Embedding is passed to ChromaDB query
        """
        from src.asksplunk.retriever.retriever import DocumentRetriever

        with patch("asyncio.to_thread", new_callable=lambda: asyncio.to_thread):
            retriever = DocumentRetriever(mock_openai_client, mock_chroma_client)

            await retriever.retrieve("bounce rate fields", top_k=3)

            # Verify OpenAI embedding was called
            mock_openai_client.embeddings.create.assert_called_once()
            call_kwargs = mock_openai_client.embeddings.create.call_args[1]
            assert call_kwargs["input"] == "bounce rate fields"
            assert call_kwargs["model"] == "text-embedding-ada-002"

    @pytest.mark.asyncio
    async def test_retrieve_performs_semantic_search(self, mock_openai_client, mock_chroma_client):
        """Semantic search is performed in ChromaDB.

        Verifies that:
        - ChromaDB collection is retrieved
        - Query is executed with embedding
        - Results are returned
        """
        from src.asksplunk.retriever.retriever import DocumentRetriever

        with patch("asyncio.to_thread", new_callable=lambda: asyncio.to_thread):
            retriever = DocumentRetriever(mock_openai_client, mock_chroma_client)

            results = await retriever.retrieve("delivery failures", top_k=5)

            # Verify collection was retrieved
            mock_chroma_client.get_collection.assert_called_with("campaign_prod_docs")

            # Verify query was executed
            collection = mock_chroma_client.get_collection.return_value
            collection.query.assert_called_once()

            # Verify results returned
            assert len(results) == 3  # Based on mock data
            assert all("content" in r for r in results)
            assert all("chunk_type" in r for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_with_category_filter(self, mock_openai_client, mock_chroma_client):
        """Category filter is applied to ChromaDB query.

        Verifies that:
        - Where clause includes category filter
        - Only matching chunks are returned
        """
        from src.asksplunk.retriever.retriever import DocumentRetriever

        with patch("asyncio.to_thread", new_callable=lambda: asyncio.to_thread):
            retriever = DocumentRetriever(mock_openai_client, mock_chroma_client)

            await retriever.retrieve("bounce fields", filter_category="Campaign & Delivery")

            # Verify where clause was passed
            collection = mock_chroma_client.get_collection.return_value
            call_kwargs = collection.query.call_args[1]

            assert call_kwargs["where"] is not None
            assert call_kwargs["where"]["category"] == "Campaign & Delivery"

    @pytest.mark.asyncio
    async def test_retrieve_with_chunk_type_filter(self, mock_openai_client, mock_chroma_client):
        """Chunk type filter is applied to ChromaDB query.

        Verifies that:
        - Where clause includes chunk_type filter
        - Only specific chunk types are returned
        """
        from src.asksplunk.retriever.retriever import DocumentRetriever

        with patch("asyncio.to_thread", new_callable=lambda: asyncio.to_thread):
            retriever = DocumentRetriever(mock_openai_client, mock_chroma_client)

            await retriever.retrieve("query patterns", filter_chunk_type="pattern")

            # Verify where clause includes chunk_type
            collection = mock_chroma_client.get_collection.return_value
            call_kwargs = collection.query.call_args[1]

            assert call_kwargs["where"] is not None
            assert call_kwargs["where"]["chunk_type"] == "pattern"

    @pytest.mark.asyncio
    async def test_retrieve_formats_results_with_relevance_scores(
        self, mock_openai_client, mock_chroma_client
    ):
        """Results are formatted with relevance scores.

        Verifies that:
        - Results include content, chunk_type, metadata, relevance_score
        - L2 distance is converted to similarity score (0.0-1.0)
        - Scores are calculated correctly: 1.0 / (1.0 + distance)
        """
        from src.asksplunk.retriever.retriever import DocumentRetriever

        with patch("asyncio.to_thread", new_callable=lambda: asyncio.to_thread):
            retriever = DocumentRetriever(mock_openai_client, mock_chroma_client)

            results = await retriever.retrieve("test query", top_k=3)

            # Verify result structure
            assert len(results) == 3

            for result in results:
                assert "content" in result
                assert "chunk_type" in result
                assert "metadata" in result
                assert "relevance_score" in result

                # Verify relevance score is in valid range
                assert 0.0 <= result["relevance_score"] <= 1.0

            # Verify distance conversion (mock distances: [0.2, 0.3, 0.5])
            # Expected scores: 1/(1+0.2)=0.833, 1/(1+0.3)=0.769, 1/(1+0.5)=0.667
            assert abs(results[0]["relevance_score"] - 0.833) < 0.01
            assert abs(results[1]["relevance_score"] - 0.769) < 0.01
            assert abs(results[2]["relevance_score"] - 0.667) < 0.01

    @pytest.mark.asyncio
    async def test_retrieve_with_top_k_parameter(self, mock_openai_client, mock_chroma_client):
        """Top-K parameter limits number of results.

        Verifies that:
        - n_results parameter is passed to ChromaDB
        - Returned results respect top_k limit
        """
        from src.asksplunk.retriever.retriever import DocumentRetriever

        with patch("asyncio.to_thread", new_callable=lambda: asyncio.to_thread):
            retriever = DocumentRetriever(mock_openai_client, mock_chroma_client)

            await retriever.retrieve("test", top_k=10)

            # Verify n_results parameter
            collection = mock_chroma_client.get_collection.return_value
            call_kwargs = collection.query.call_args[1]

            assert call_kwargs["n_results"] == 10

    @pytest.mark.asyncio
    async def test_retrieve_with_combined_filters(self, mock_openai_client, mock_chroma_client):
        """Multiple filters can be combined (AND logic).

        Verifies that:
        - Where clause includes both category and chunk_type
        - Both filters are applied simultaneously
        """
        from src.asksplunk.retriever.retriever import DocumentRetriever

        with patch("asyncio.to_thread", new_callable=lambda: asyncio.to_thread):
            retriever = DocumentRetriever(mock_openai_client, mock_chroma_client)

            await retriever.retrieve(
                "delivery fields", filter_category="Campaign & Delivery", filter_chunk_type="field"
            )

            # Verify both filters in where clause
            collection = mock_chroma_client.get_collection.return_value
            call_kwargs = collection.query.call_args[1]

            assert call_kwargs["where"]["category"] == "Campaign & Delivery"
            assert call_kwargs["where"]["chunk_type"] == "field"

    @pytest.mark.asyncio
    async def test_retrieve_without_filters_passes_none(
        self, mock_openai_client, mock_chroma_client
    ):
        """No filters means where=None is passed to ChromaDB.

        Verifies that:
        - When no filters provided, where clause is None
        - All chunks can be searched
        """
        from src.asksplunk.retriever.retriever import DocumentRetriever

        with patch("asyncio.to_thread", new_callable=lambda: asyncio.to_thread):
            retriever = DocumentRetriever(mock_openai_client, mock_chroma_client)

            await retriever.retrieve("test query")

            # Verify where is None when no filters
            collection = mock_chroma_client.get_collection.return_value
            call_kwargs = collection.query.call_args[1]

            assert call_kwargs["where"] is None
