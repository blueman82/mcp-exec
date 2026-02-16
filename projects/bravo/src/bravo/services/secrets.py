"""AWS Secrets Manager integration with caching.

Provides async retrieval of Slack tokens, LLM credentials, and database
secrets from AWS Secrets Manager with configurable cache TTL.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Self

import aioboto3


class SecretsManager:
    """Manages retrieval of secrets from AWS Secrets Manager with caching.

    Fetches Bravo secrets (Slack, LLM, database) with configurable cache TTL
    to reduce API calls. Must be used as async context manager.

    Attributes:
        region: AWS region for Secrets Manager.
        cache_ttl: Cache time-to-live in seconds.
    """

    def __init__(self, region: str = "eu-west-1", cache_ttl: int = 3600, profile: str | None = None) -> None:
        """Initialize SecretsManager.

        Args:
            region: AWS region (default: eu-west-1).
            cache_ttl: Cache time-to-live in seconds (default: 3600 = 60 minutes).
            profile: AWS profile name (default: None, uses default credential chain).
        """
        self.region = region
        self.cache_ttl = cache_ttl
        self.profile = profile
        self._client: Any | None = None
        self._client_context: Any | None = None
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_timestamps: dict[str, datetime] = {}
        self._raw_cache: dict[str, str] = {}
        self._raw_cache_timestamps: dict[str, datetime] = {}

    async def __aenter__(self) -> Self:
        """Create aioboto3 client on context entry."""
        if not self._client:
            session = aioboto3.Session(profile_name=self.profile)
            self._client_context = session.client("secretsmanager", region_name=self.region)
            self._client = await self._client_context.__aenter__()
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        """Close aioboto3 client on context exit."""
        if self._client_context:
            try:
                await self._client_context.__aexit__(exc_type, exc_val, exc_tb)
            finally:
                self._client = None
                self._client_context = None

    async def _get_secret(self, secret_name: str) -> dict[str, Any]:
        """Retrieve secret from AWS Secrets Manager with caching.

        Args:
            secret_name: Name of the secret in AWS Secrets Manager.

        Returns:
            Dict containing secret data parsed from JSON.

        Raises:
            RuntimeError: If called outside async context manager.
        """
        if secret_name in self._cache:
            elapsed = datetime.now(UTC) - self._cache_timestamps[secret_name]
            if elapsed < timedelta(seconds=self.cache_ttl):
                return self._cache[secret_name]

        if not self._client:
            raise RuntimeError(
                "SecretsManager must be used as async context manager. "
                "Use: async with SecretsManager() as sm: ..."
            )

        response = await self._client.get_secret_value(SecretId=secret_name)
        secret_data: dict[str, Any] = json.loads(response["SecretString"])

        self._cache[secret_name] = secret_data
        self._cache_timestamps[secret_name] = datetime.now(UTC)

        return secret_data

    async def get_slack_secrets(self) -> dict[str, str]:
        """Retrieve Slack secrets from ``bravo/slack``."""
        return await self._get_secret("bravo/slack")

    async def get_llm_secrets(self) -> dict[str, str]:
        """Retrieve LLM secrets from ``bravo/llm``."""
        return await self._get_secret("bravo/llm")

    async def get_database_secrets(self) -> dict[str, str]:
        """Retrieve database secrets from ``bravo/database``."""
        return await self._get_secret("bravo/database")

    async def get_raw_secret(self, secret_name: str) -> str:
        """Retrieve a plain-string secret from AWS Secrets Manager with caching.

        Unlike ``_get_secret`` which parses JSON, this returns the raw
        ``SecretString`` value directly.

        Args:
            secret_name: Name of the secret in AWS Secrets Manager.

        Returns:
            Raw secret string.

        Raises:
            RuntimeError: If called outside async context manager.
        """
        if secret_name in self._raw_cache:
            elapsed = datetime.now(UTC) - self._raw_cache_timestamps[secret_name]
            if elapsed < timedelta(seconds=self.cache_ttl):
                return self._raw_cache[secret_name]

        if not self._client:
            raise RuntimeError(
                "SecretsManager must be used as async context manager. "
                "Use: async with SecretsManager() as sm: ..."
            )

        response = await self._client.get_secret_value(SecretId=secret_name)
        secret_string: str = response["SecretString"]

        self._raw_cache[secret_name] = secret_string
        self._raw_cache_timestamps[secret_name] = datetime.now(UTC)
        return secret_string
