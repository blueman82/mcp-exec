"""Tests for Azure Embeddings Client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.agent.embeddings.azure_embeddings_client import (
    AzureEmbeddingsClient,
)


@pytest.fixture
def mock_secrets_manager():
    manager = AsyncMock()
    manager.get_azure_openai_lb_api_key.return_value = "test-key-123"
    return manager


@pytest.fixture
def client(mock_secrets_manager):
    return AzureEmbeddingsClient(secrets_manager=mock_secrets_manager)


class TestInitialize:
    @pytest.mark.asyncio
    async def test_initialize_sets_api_key(self, client, mock_secrets_manager):
        await client.initialize()
        assert client._api_key == "test-key-123"
        assert client._session is not None
        await client.cleanup()

    @pytest.mark.asyncio
    async def test_initialize_missing_key_raises(self, mock_secrets_manager):
        mock_secrets_manager.get_azure_openai_lb_api_key.return_value = ""
        client = AzureEmbeddingsClient(secrets_manager=mock_secrets_manager)
        with pytest.raises(ValueError, match="Azure OpenAI API key"):
            await client.initialize()


class TestEmbedTexts:
    @pytest.mark.asyncio
    async def test_empty_texts_returns_empty(self, client):
        result = await client.embed_texts([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_single_text(self, client):
        fake_embedding = [0.1] * 1536
        client._api_key = "test"
        client._session = MagicMock()

        with patch.object(client, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = [fake_embedding]
            result = await client.embed_texts(["hello world"])

        assert len(result) == 1
        assert result[0] == fake_embedding

    @pytest.mark.asyncio
    async def test_embed_query_returns_single_vector(self, client):
        fake_embedding = [0.5] * 1536
        client._api_key = "test"

        with patch.object(client, "embed_texts", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [fake_embedding]
            result = await client.embed_query("what happened?")

        assert result == fake_embedding


class TestCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_closes_session(self, client, mock_secrets_manager):
        await client.initialize()
        assert client._session is not None
        await client.cleanup()
