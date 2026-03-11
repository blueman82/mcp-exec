"""Tests for ChromaDB vector store."""

from unittest.mock import MagicMock

import pytest

from packages.agent.embeddings.vector_store import ChromaVectorStore


@pytest.fixture
def mock_collection():
    collection = MagicMock()
    collection.count.return_value = 0
    return collection


@pytest.fixture
def store(mock_collection):
    store = ChromaVectorStore()
    store._collection = mock_collection
    store._client = MagicMock()
    return store


class TestAddDocuments:
    @pytest.mark.asyncio
    async def test_add_empty_does_nothing(self, store, mock_collection):
        await store.add_documents([], [])
        mock_collection.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_documents_calls_upsert(self, store, mock_collection):
        docs = [
            {"id": "doc1", "text": "hello", "metadata": {"channel_id": "C1"}},
        ]
        embeddings = [[0.1] * 1536]

        await store.add_documents(docs, embeddings)
        mock_collection.upsert.assert_called_once_with(
            ids=["doc1"],
            documents=["hello"],
            embeddings=embeddings,
            metadatas=[{"channel_id": "C1"}],
        )


class TestQuery:
    @pytest.mark.asyncio
    async def test_query_returns_formatted_results(self, store, mock_collection):
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["text1", "text2"]],
            "metadatas": [[{"channel_id": "C1"}, {"channel_id": "C1"}]],
            "distances": [[0.1, 0.3]],
        }

        results = await store.query([0.1] * 1536, "C1", top_k=5)
        assert len(results) == 2
        assert results[0]["id"] == "id1"
        assert results[0]["distance"] == 0.1

    @pytest.mark.asyncio
    async def test_query_empty_results(self, store, mock_collection):
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        results = await store.query([0.1] * 1536, "C1")
        assert results == []


class TestDeleteByChannel:
    @pytest.mark.asyncio
    async def test_delete_calls_collection(self, store, mock_collection):
        await store.delete_by_channel("C123")
        mock_collection.delete.assert_called_once_with(where={"channel_id": "C123"})


class TestNotInitialized:
    @pytest.mark.asyncio
    async def test_query_raises_when_not_initialized(self):
        store = ChromaVectorStore()
        with pytest.raises(RuntimeError, match="not initialized"):
            await store.query([0.1] * 10, "C1")

    @pytest.mark.asyncio
    async def test_add_raises_when_not_initialized(self):
        store = ChromaVectorStore()
        with pytest.raises(RuntimeError, match="not initialized"):
            await store.add_documents([{"id": "x", "text": "y", "metadata": {}}], [[0.1]])
