"""Integration tests for SecretsManager with real AWS Secrets Manager.

These tests require:
1. .env.test file with AWS_PROFILE set
2. Valid AWS credentials configured
3. Secrets created in AWS: splunk-bot/slack-tokens, splunk-bot/azure-openai
"""

import pytest

from asksplunk.secrets import SecretsManager


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_slack_tokens_from_aws():
    """Test retrieving real Slack tokens from AWS Secrets Manager."""
    async with SecretsManager() as manager:
        tokens = await manager.get_slack_tokens()

        # Verify structure
        assert "bot_token" in tokens
        assert "app_token" in tokens

        # Verify tokens start with correct prefixes
        assert tokens["bot_token"].startswith("xoxb-")
        assert tokens["app_token"].startswith("xapp-")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_azure_openai_config_from_aws():
    """Test retrieving real Azure OpenAI config from AWS Secrets Manager."""
    async with SecretsManager() as manager:
        config = await manager.get_azure_openai_config()

        # Verify structure
        assert "endpoint" in config
        assert "api_key" in config
        assert "chat_deployment" in config
        assert "embedding_deployment" in config
        assert "api_version" in config

        # Verify values are populated
        assert config["endpoint"].startswith("https://")
        assert len(config["api_key"]) > 0
        assert config["chat_deployment"] == "gpt-5"
        assert config["embedding_deployment"] == "text-embedding-ada-002"
        assert config["api_version"] == "2025-01-01-preview"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_secrets_caching():
    """Test that secrets are cached and not fetched twice."""
    async with SecretsManager(cache_ttl=60) as manager:
        # First call - fetches from AWS
        tokens1 = await manager.get_slack_tokens()

        # Second call - should return cached value
        tokens2 = await manager.get_slack_tokens()

        # Verify same object returned (cache hit)
        assert tokens1 is tokens2
