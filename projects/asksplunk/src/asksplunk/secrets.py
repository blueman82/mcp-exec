"""AWS Secrets Manager integration with caching.

Provides async retrieval of Slack tokens and Azure OpenAI credentials
from AWS Secrets Manager with 60-minute caching to reduce API calls.
"""

import json
from datetime import datetime, timedelta
from typing import Any

import aioboto3


class SecretsManager:
    """Manages retrieval of secrets from AWS Secrets Manager with caching.

    Fetches Slack tokens (bot_token, app_token) and Azure OpenAI credentials
    (endpoint, api_key, deployment names) with 60-minute cache TTL.

    Must be used as async context manager to ensure proper resource cleanup.

    Attributes:
        region: AWS region for Secrets Manager
        cache_ttl: Cache time-to-live in seconds (default: 3600)

    Example:
        async with SecretsManager() as manager:
            tokens = await manager.get_slack_tokens()
            config = await manager.get_azure_openai_config()
    """

    def __init__(self, client: Any | None = None, region: str = "eu-west-1", cache_ttl: int = 3600):
        """Initialize SecretsManager with optional client for testing.

        Args:
            client: Optional aioboto3 client for testing (None for production)
            region: AWS region (default: eu-west-1)
            cache_ttl: Cache time-to-live in seconds (default: 3600 = 60 minutes)

        Example:
            # Production usage
            async with SecretsManager() as manager:
                tokens = await manager.get_slack_tokens()

            # Testing usage
            async with SecretsManager(client=mock_client) as manager:
                tokens = await manager.get_slack_tokens()
        """
        self.region = region
        self.cache_ttl = cache_ttl
        self._client: Any | None = client
        self._client_context: Any | None = None  # Store context for proper cleanup
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_timestamps: dict[str, datetime] = {}

    async def __aenter__(self):
        """Async context manager entry.

        Creates aioboto3 client if not injected for testing.

        Returns:
            Self for use in async with statement

        Example:
            async with SecretsManager() as manager:
                tokens = await manager.get_slack_tokens()
        """
        if not self._client:
            session = aioboto3.Session()
            self._client_context = session.client("secretsmanager", region_name=self.region)
            self._client = await self._client_context.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources.

        Properly closes aioboto3 client connection to prevent resource leaks.
        Uses try-finally to ensure client references are cleared even if cleanup fails.

        Args:
            exc_type: Exception type if raised within context
            exc_val: Exception value if raised within context
            exc_tb: Exception traceback if raised within context

        Returns:
            None (does not suppress exceptions)
        """
        if self._client_context:
            try:
                await self._client_context.__aexit__(exc_type, exc_val, exc_tb)
            finally:
                self._client = None
                self._client_context = None

    async def _get_client(self):
        """Get secrets manager client.

        Returns:
            aioboto3 Secrets Manager client

        Raises:
            RuntimeError: If called outside async context manager

        Note:
            SecretsManager must be used as async context manager.
            Use: async with SecretsManager() as manager: ...
        """
        if not self._client:
            raise RuntimeError(
                "SecretsManager must be used as async context manager. "
                "Use: async with SecretsManager() as manager: ..."
            )
        return self._client

    async def _get_secret(self, secret_name: str) -> dict[str, Any]:
        """Retrieve secret from AWS Secrets Manager with caching.

        Checks cache validity based on TTL. If cache is valid, returns cached data.
        Otherwise fetches from AWS, updates cache, and returns fresh data.

        Args:
            secret_name: Name of the secret in AWS Secrets Manager
                        (e.g., "splunk-bot/slack-tokens")

        Returns:
            Dict containing secret data parsed from JSON

        Raises:
            ClientError: If secret retrieval fails (e.g., ResourceNotFoundException)
            json.JSONDecodeError: If secret contains malformed JSON
            RuntimeError: If called outside async context manager

        Example:
            async with SecretsManager() as manager:
                secret = await manager._get_secret("splunk-bot/slack-tokens")
                bot_token = secret["bot_token"]
        """
        # Check cache validity
        if secret_name in self._cache:
            cached_time = self._cache_timestamps[secret_name]
            time_elapsed = datetime.now() - cached_time

            if time_elapsed < timedelta(seconds=self.cache_ttl):
                # Cache still valid
                return self._cache[secret_name]

        # Cache miss or expired - fetch from AWS
        client = await self._get_client()
        response = await client.get_secret_value(SecretId=secret_name)

        # Parse JSON from secret string
        secret_data: dict[str, Any] = json.loads(response["SecretString"])

        # Update cache
        self._cache[secret_name] = secret_data
        self._cache_timestamps[secret_name] = datetime.now()

        return secret_data

    async def get_slack_tokens(self) -> dict[str, str]:
        """Retrieve Slack authentication tokens.

        Fetches bot token and app token from AWS Secrets Manager.
        Uses caching to reduce API calls.

        Returns:
            Dict with keys:
                - bot_token: Slack bot token (starts with xoxb-)
                - app_token: Slack app token (starts with xapp-)

        Raises:
            ClientError: If secret doesn't exist or access is denied
            json.JSONDecodeError: If secret contains malformed JSON
            RuntimeError: If called outside async context manager

        Example:
            async with SecretsManager() as manager:
                tokens = await manager.get_slack_tokens()
                bot_token = tokens["bot_token"]
                app_token = tokens["app_token"]
        """
        return await self._get_secret("splunk-bot/slack-tokens")

    async def get_azure_openai_config(self) -> dict[str, str]:
        """Retrieve Azure OpenAI configuration.

        Fetches endpoint, API key, and deployment names from AWS Secrets Manager.
        Uses caching to reduce API calls.

        Returns:
            Dict with keys:
                - endpoint: Azure OpenAI endpoint URL
                - api_key: Azure OpenAI API key
                - chat_deployment: GPT-5 chat deployment name
                - embedding_deployment: ADA-002 embedding deployment name

        Raises:
            ClientError: If secret doesn't exist or access is denied
            json.JSONDecodeError: If secret contains malformed JSON
            RuntimeError: If called outside async context manager

        Example:
            async with SecretsManager() as manager:
                config = await manager.get_azure_openai_config()
                endpoint = config["endpoint"]
                api_key = config["api_key"]
        """
        return await self._get_secret("splunk-bot/azure-openai")
