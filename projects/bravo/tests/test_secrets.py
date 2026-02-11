"""Tests for AWS Secrets Manager integration and load_settings()."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bravo.config import get_settings, load_settings
from bravo.services.secrets import SecretsManager


# --- SecretsManager tests ---


def _secret_response(data: dict) -> dict:
    """Build a mock get_secret_value response."""
    return {"SecretString": json.dumps(data)}


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Clear LRU cache before each test."""
    get_settings.cache_clear()
    yield  # type: ignore[misc]
    get_settings.cache_clear()


async def test_get_slack_secrets() -> None:
    """Fetches bravo/slack secret with correct name."""
    expected = {"bot_token": "xoxb-test", "app_token": "xapp-test", "signing_secret": "secret"}
    client = AsyncMock()
    client.get_secret_value.return_value = _secret_response(expected)

    sm = SecretsManager()
    sm._client = client
    async with sm:
        result = await sm.get_slack_secrets()

    assert result == expected
    client.get_secret_value.assert_called_with(SecretId="bravo/slack")


async def test_get_llm_secrets() -> None:
    """Fetches bravo/llm secret with correct name."""
    expected = {"api_key": "key-123", "endpoint": "https://llm.example.com"}
    client = AsyncMock()
    client.get_secret_value.return_value = _secret_response(expected)

    sm = SecretsManager()
    sm._client = client
    async with sm:
        result = await sm.get_llm_secrets()

    assert result == expected
    client.get_secret_value.assert_called_with(SecretId="bravo/llm")


async def test_get_database_secrets() -> None:
    """Fetches bravo/database secret with correct name."""
    expected = {"host": "db.example.com", "password": "s3cret", "user": "bravo"}
    client = AsyncMock()
    client.get_secret_value.return_value = _secret_response(expected)

    sm = SecretsManager()
    sm._client = client
    async with sm:
        result = await sm.get_database_secrets()

    assert result == expected
    client.get_secret_value.assert_called_with(SecretId="bravo/database")


async def test_cache_hit() -> None:
    """Second call returns cached value without AWS call."""
    data = {"bot_token": "xoxb-cached", "app_token": "xapp-cached"}
    client = AsyncMock()
    client.get_secret_value.return_value = _secret_response(data)

    sm = SecretsManager()
    sm._client = client
    async with sm:
        first = await sm.get_slack_secrets()
        second = await sm.get_slack_secrets()

    assert first == second
    assert client.get_secret_value.call_count == 1


async def test_cache_expired() -> None:
    """After TTL expires, fetches fresh from AWS."""
    data = {"bot_token": "xoxb-fresh", "app_token": "xapp-fresh"}
    client = AsyncMock()
    client.get_secret_value.return_value = _secret_response(data)

    sm = SecretsManager(cache_ttl=60)
    sm._client = client
    async with sm:
        await sm.get_slack_secrets()
        sm._cache_timestamps["bravo/slack"] = datetime.now(UTC) - timedelta(seconds=120)
        await sm.get_slack_secrets()

    assert client.get_secret_value.call_count == 2


async def test_profile_passed_to_session() -> None:
    """AWS profile name is forwarded to aioboto3.Session."""
    sm = SecretsManager(profile="campaign_prod_v7")
    assert sm.profile == "campaign_prod_v7"

    with patch("bravo.services.secrets.aioboto3.Session") as mock_session:
        mock_ctx = AsyncMock()
        mock_session.return_value.client.return_value = mock_ctx
        mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        async with sm:
            pass
        mock_session.assert_called_with(profile_name="campaign_prod_v7")


# --- load_settings() tests ---


def _mock_secrets_manager(
    slack: dict | None = None,
    llm: dict | None = None,
    db: dict | None = None,
) -> MagicMock:
    """Create a mock SecretsManager class that returns given secrets."""
    instance = AsyncMock()
    instance.get_slack_secrets.return_value = slack or {}
    instance.get_llm_secrets.return_value = llm or {}
    instance.get_database_secrets.return_value = db or {}
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=instance)


async def test_aws_disabled_returns_env_settings() -> None:
    """When aws_secrets_enabled=False, no AWS calls are made."""
    with patch.dict("os.environ", {"BRAVO_AWS_SECRETS_ENABLED": "false"}, clear=False):
        settings = await load_settings()

    assert settings.aws_secrets_enabled is False


async def test_aws_enabled_hydrates_secrets() -> None:
    """When aws_secrets_enabled=True, secrets are fetched and applied."""
    mock_cls = _mock_secrets_manager(
        slack={"bot_token": "xoxb-aws", "app_token": "xapp-aws", "signing_secret": "sig-aws"},
        llm={"api_key": "key-aws", "endpoint": "https://llm-aws.example.com"},
        db={"password": "pw-aws", "user": "user-aws", "host": "db-aws.example.com"},
    )

    with (
        patch.dict("os.environ", {"BRAVO_AWS_SECRETS_ENABLED": "true"}, clear=False),
        patch("bravo.services.secrets.SecretsManager", mock_cls),
    ):
        settings = await load_settings()

    assert settings.slack.bot_token == "xoxb-aws"
    assert settings.slack.app_token == "xapp-aws"
    assert settings.slack.signing_secret == "sig-aws"
    assert settings.llm.api_key == "key-aws"
    assert settings.llm.endpoint == "https://llm-aws.example.com"
    assert settings.database.password == "pw-aws"
    assert settings.database.user == "user-aws"
    assert settings.database.host == "db-aws.example.com"


async def test_env_var_takes_precedence() -> None:
    """Env var values are not overridden by AWS values."""
    mock_cls = _mock_secrets_manager(
        slack={"bot_token": "xoxb-aws", "app_token": "xapp-aws"},
        llm={"api_key": "key-aws", "endpoint": "https://llm-aws.example.com"},
        db={"password": "pw-aws"},
    )

    env = {
        "BRAVO_AWS_SECRETS_ENABLED": "true",
        "SLACK_BOT_TOKEN": "xoxb-env",
        "LLM_API_KEY": "key-env",
        "DB_PASSWORD": "pw-env",
    }

    with (
        patch.dict("os.environ", env, clear=False),
        patch("bravo.services.secrets.SecretsManager", mock_cls),
    ):
        settings = await load_settings()

    # Env vars win via the `or` pattern
    assert settings.slack.bot_token == "xoxb-env"
    assert settings.llm.api_key == "key-env"
    assert settings.database.password == "pw-env"

    # AWS fills in the rest
    assert settings.slack.app_token == "xapp-aws"
    assert settings.llm.endpoint == "https://llm-aws.example.com"
