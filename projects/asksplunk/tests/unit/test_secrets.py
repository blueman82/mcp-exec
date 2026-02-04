"""Unit tests for AWS Secrets Manager integration.

Tests the SecretsManager class with mocked aioboto3 client.
Verifies caching, TTL expiration, and error handling.
"""

import json
from unittest.mock import AsyncMock

import pytest
from botocore.exceptions import ClientError

from asksplunk.secrets import SecretsManager


class TestSecretsManager:
    """Test AWS Secrets Manager integration with caching."""

    @pytest.fixture
    def mock_secrets_client(self):
        """Mock aioboto3 secrets manager client."""
        client = AsyncMock()
        client.get_secret_value = AsyncMock(
            return_value={
                "SecretString": json.dumps(
                    {"bot_token": "xoxb-test-123456", "app_token": "xapp-test-789012"}
                )
            }
        )
        return client

    @pytest.fixture
    def mock_azure_secrets_client(self):
        """Mock aioboto3 client for Azure OpenAI secrets."""
        client = AsyncMock()
        client.get_secret_value = AsyncMock(
            return_value={
                "SecretString": json.dumps(
                    {
                        "endpoint": "https://test.openai.azure.com/",
                        "api_key": "test-api-key-123",
                        "chat_deployment": "gpt-5-turbo",
                        "embedding_deployment": "ada-002",
                    }
                )
            }
        )
        return client

    @pytest.mark.asyncio
    async def test_get_slack_tokens_returns_dict(self, mock_secrets_client):
        """get_slack_tokens should return dict with bot_token and app_token."""
        async with SecretsManager(client=mock_secrets_client) as manager:
            tokens = await manager.get_slack_tokens()

            assert "bot_token" in tokens
            assert "app_token" in tokens
            assert tokens["bot_token"].startswith("xoxb-")
            assert tokens["app_token"].startswith("xapp-")

    @pytest.mark.asyncio
    async def test_get_azure_openai_config_returns_credentials(self, mock_azure_secrets_client):
        """get_azure_openai_config should return endpoint, api_key, and deployment names."""
        async with SecretsManager(client=mock_azure_secrets_client) as manager:
            config = await manager.get_azure_openai_config()

            assert "endpoint" in config
            assert "api_key" in config
            assert "chat_deployment" in config
            assert "embedding_deployment" in config
            assert config["endpoint"].startswith("https://")

    @pytest.mark.asyncio
    async def test_secrets_cached_for_60_minutes(self, mock_secrets_client):
        """Secrets should be cached and not re-fetched within 60 minutes."""
        async with SecretsManager(client=mock_secrets_client, cache_ttl=3600) as manager:
            # First call
            tokens1 = await manager.get_slack_tokens()
            # Second call (should use cache)
            tokens2 = await manager.get_slack_tokens()

            # Should only call AWS once
            assert mock_secrets_client.get_secret_value.call_count == 1
            # Should return same data
            assert tokens1 == tokens2

    @pytest.mark.asyncio
    async def test_cache_invalidates_after_ttl(self, mock_secrets_client):
        """Cache should be invalidated after TTL expires."""
        async with SecretsManager(client=mock_secrets_client, cache_ttl=1) as manager:
            # First call
            await manager.get_slack_tokens()

            # Wait for cache to expire
            import asyncio

            await asyncio.sleep(1.1)

            # Second call (should fetch from AWS again)
            await manager.get_slack_tokens()

            # Should call AWS twice (cache expired)
            assert mock_secrets_client.get_secret_value.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_missing_secret_gracefully(self):
        """Should raise appropriate error when secret doesn't exist."""
        client = AsyncMock()
        client.get_secret_value = AsyncMock(
            side_effect=ClientError(
                {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}},
                "GetSecretValue",
            )
        )

        async with SecretsManager(client=client) as manager:
            with pytest.raises(ClientError):
                await manager.get_slack_tokens()

    @pytest.mark.asyncio
    async def test_handles_malformed_json_in_secret(self):
        """Should raise JSONDecodeError for malformed secret data."""
        client = AsyncMock()
        client.get_secret_value = AsyncMock(return_value={"SecretString": "invalid-json{{"})

        async with SecretsManager(client=client) as manager:
            with pytest.raises(json.JSONDecodeError):
                await manager.get_slack_tokens()

    @pytest.mark.asyncio
    async def test_different_secrets_cached_separately(
        self, mock_secrets_client, mock_azure_secrets_client
    ):
        """Different secrets should be cached independently."""
        # Create a client that can return different secrets
        client = AsyncMock()

        async def mock_get_secret(SecretId):
            # NOTE: These are FAKE TEST TOKENS, not real credentials
            if SecretId == "splunk-bot/slack-tokens":
                return {
                    "SecretString": json.dumps(
                        {"bot_token": "xoxb-fake-test", "app_token": "xapp-fake-test"}
                    )
                }
            elif SecretId == "splunk-bot/azure-openai":
                return {
                    "SecretString": json.dumps(
                        {"endpoint": "https://test.openai.azure.com/", "api_key": "test-key"}
                    )
                }

        client.get_secret_value = AsyncMock(side_effect=mock_get_secret)

        async with SecretsManager(client=client) as manager:
            # Fetch both secrets
            await manager.get_slack_tokens()
            await manager.get_azure_openai_config()

            # Should call AWS twice (different secrets)
            assert client.get_secret_value.call_count == 2

            # Fetch again (should use cache)
            await manager.get_slack_tokens()
            await manager.get_azure_openai_config()

            # Should still be 2 calls (cache hit for both)
            assert client.get_secret_value.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_timestamps_updated_on_refresh(self, mock_secrets_client):
        """Cache timestamps should be updated when cache is refreshed."""
        async with SecretsManager(client=mock_secrets_client, cache_ttl=1) as manager:
            # First call
            await manager.get_slack_tokens()
            first_timestamp = manager._cache_timestamps.get("splunk-bot/slack-tokens")

            # Wait and fetch again (cache expired)
            import asyncio

            await asyncio.sleep(1.1)
            await manager.get_slack_tokens()
            second_timestamp = manager._cache_timestamps.get("splunk-bot/slack-tokens")

            # Timestamps should be different
            assert second_timestamp > first_timestamp

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_used_outside_context_manager(self):
        """Should raise RuntimeError when methods called outside async context manager."""
        manager = SecretsManager(client=None)

        with pytest.raises(RuntimeError, match="must be used as async context manager"):
            await manager.get_slack_tokens()
