"""Unit tests for access validation.

Tests the AccessValidator class with mocked SecretsManager.
Verifies whitelist authorization logic.
"""

import json
from unittest.mock import AsyncMock

import pytest

from asksplunk.auth.validator import AccessValidator
from asksplunk.secrets import SecretsManager


class TestAccessValidator:
    """Test access validation against authorized user whitelist."""

    @pytest.fixture
    def mock_secrets_client_with_users(self):
        """Mock aioboto3 client returning authorized user list."""
        client = AsyncMock()
        client.get_secret_value = AsyncMock(
            return_value={
                "SecretString": json.dumps(
                    {
                        "bot_token": "xoxb-test-123456",
                        "app_token": "xapp-test-789012",
                        "authorised_slack_user_ids": '["W7MGASQ2K", "W5H6R82Q6", "WDHGPEL2K"]',
                    }
                )
            }
        )
        return client

    @pytest.fixture
    def mock_secrets_client_empty_users(self):
        """Mock aioboto3 client returning empty user list."""
        client = AsyncMock()
        client.get_secret_value = AsyncMock(
            return_value={
                "SecretString": json.dumps(
                    {
                        "bot_token": "xoxb-test-123456",
                        "app_token": "xapp-test-789012",
                        "authorised_slack_user_ids": "[]",
                    }
                )
            }
        )
        return client

    @pytest.fixture
    def mock_secrets_client_no_key(self):
        """Mock aioboto3 client returning secret without user list key."""
        client = AsyncMock()
        client.get_secret_value = AsyncMock(
            return_value={
                "SecretString": json.dumps(
                    {
                        "bot_token": "xoxb-test-123456",
                        "app_token": "xapp-test-789012",
                    }
                )
            }
        )
        return client

    @pytest.mark.asyncio
    async def test_authorized_user_returns_true(self, mock_secrets_client_with_users):
        """is_authorized should return True for user in whitelist."""
        async with SecretsManager(client=mock_secrets_client_with_users) as manager:
            validator = AccessValidator(manager)
            result = await validator.is_authorized("W7MGASQ2K")

            assert result is True

    @pytest.mark.asyncio
    async def test_unauthorized_user_returns_false(self, mock_secrets_client_with_users):
        """is_authorized should return False for user not in whitelist."""
        async with SecretsManager(client=mock_secrets_client_with_users) as manager:
            validator = AccessValidator(manager)
            result = await validator.is_authorized("UNKNOWN_USER")

            assert result is False

    @pytest.mark.asyncio
    async def test_empty_user_list_denies_all(self, mock_secrets_client_empty_users):
        """is_authorized should return False when user list is empty."""
        async with SecretsManager(client=mock_secrets_client_empty_users) as manager:
            validator = AccessValidator(manager)
            result = await validator.is_authorized("W7MGASQ2K")

            assert result is False

    @pytest.mark.asyncio
    async def test_missing_key_returns_empty_list(self, mock_secrets_client_no_key):
        """is_authorized should return False when key is missing from secret."""
        async with SecretsManager(client=mock_secrets_client_no_key) as manager:
            validator = AccessValidator(manager)
            result = await validator.is_authorized("W7MGASQ2K")

            assert result is False

    @pytest.mark.asyncio
    async def test_bypasses_cache_for_freshness(self, mock_secrets_client_with_users):
        """get_authorised_slack_user_ids should fetch fresh from AWS each time."""
        async with SecretsManager(client=mock_secrets_client_with_users) as manager:
            validator = AccessValidator(manager)

            # Make multiple authorization checks
            await validator.is_authorized("W7MGASQ2K")
            await validator.is_authorized("W5H6R82Q6")
            await validator.is_authorized("UNKNOWN_USER")

            # Should call AWS each time (bypasses cache)
            assert mock_secrets_client_with_users.get_secret_value.call_count == 3

    @pytest.mark.asyncio
    async def test_handles_list_instead_of_json_string(self):
        """Should handle authorised_slack_user_ids as list directly."""
        client = AsyncMock()
        client.get_secret_value = AsyncMock(
            return_value={
                "SecretString": json.dumps(
                    {
                        "bot_token": "xoxb-test-123456",
                        "app_token": "xapp-test-789012",
                        "authorised_slack_user_ids": ["W7MGASQ2K", "W5H6R82Q6"],
                    }
                )
            }
        )

        async with SecretsManager(client=client) as manager:
            validator = AccessValidator(manager)
            result = await validator.is_authorized("W7MGASQ2K")

            assert result is True

    @pytest.mark.asyncio
    async def test_handles_aws_error_gracefully(self):
        """Should return False when AWS call fails (fail secure)."""
        client = AsyncMock()
        client.get_secret_value = AsyncMock(side_effect=Exception("AWS error"))

        async with SecretsManager(client=client) as manager:
            validator = AccessValidator(manager)
            result = await validator.is_authorized("W7MGASQ2K")

            assert result is False
