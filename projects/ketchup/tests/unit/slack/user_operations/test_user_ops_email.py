"""
Unit tests for SlackUserOps email-to-Slack lookup functionality.

Covers:
- SlackUserOps.get_slack_id_by_email: 3-level lookup (memory, DynamoDB, Slack API)
- SlackUserOps._fetch_slack_id_by_email_internal: API call and error handling
- All dependencies (UserStore, SlackConfig) are mocked

Edge Cases Covered:
- Invalid email input (None, empty, non-string)
- Email found in memory cache
- Email found in DynamoDB cache
- Email requires Slack API lookup
- Email not found in any source
- DynamoDB cache error (should fallback to API)
- Slack API error handling
- Email normalization (lowercase, strip)

Expected Outcomes:
- get_slack_id_by_email returns correct Slack ID for all scenarios
- Caching works correctly at both memory and DynamoDB levels
- Errors are handled gracefully with appropriate fallbacks
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.user_operations.user_ops import SlackUserOps


@pytest.mark.asyncio
class TestSlackUserOpsEmail:
    def setup_method(self) -> None:
        self.mock_user_store = AsyncMock()
        self.mock_slack_config = MagicMock()
        self.ops = SlackUserOps(
            user_store=self.mock_user_store,
            slack_config=self.mock_slack_config,
            max_concurrent_requests=2,
        )
        self.ops._email_to_slack_cache = {}

    # ==================== Input Validation Tests ====================

    async def test_get_slack_id_by_email_none_input(self) -> None:
        """Test that None input returns None."""
        result = await self.ops.get_slack_id_by_email(None)
        assert result is None
        self.mock_user_store.get_email_to_slack_mapping.assert_not_awaited()

    async def test_get_slack_id_by_email_empty_string(self) -> None:
        """Test that empty string input returns None."""
        result = await self.ops.get_slack_id_by_email("")
        assert result is None
        self.mock_user_store.get_email_to_slack_mapping.assert_not_awaited()

    async def test_get_slack_id_by_email_non_string(self) -> None:
        """Test that non-string input returns None."""
        result = await self.ops.get_slack_id_by_email(12345)  # type: ignore
        assert result is None
        self.mock_user_store.get_email_to_slack_mapping.assert_not_awaited()

    # ==================== Memory Cache Tests ====================

    async def test_get_slack_id_by_email_memory_cache_hit(self) -> None:
        """Test that memory cache hit returns cached value without DB/API calls."""
        self.ops._email_to_slack_cache = {"test@example.com": "U12345"}

        result = await self.ops.get_slack_id_by_email("test@example.com")

        assert result == "U12345"
        self.mock_user_store.get_email_to_slack_mapping.assert_not_awaited()

    async def test_get_slack_id_by_email_memory_cache_case_insensitive(self) -> None:
        """Test that email lookup is case-insensitive (normalized to lowercase)."""
        self.ops._email_to_slack_cache = {"test@example.com": "U12345"}

        result = await self.ops.get_slack_id_by_email("TEST@EXAMPLE.COM")

        assert result == "U12345"

    async def test_get_slack_id_by_email_memory_cache_strips_whitespace(self) -> None:
        """Test that email lookup strips whitespace."""
        self.ops._email_to_slack_cache = {"test@example.com": "U12345"}

        result = await self.ops.get_slack_id_by_email("  test@example.com  ")

        assert result == "U12345"

    # ==================== DynamoDB Cache Tests ====================

    async def test_get_slack_id_by_email_dynamodb_cache_hit(self) -> None:
        """Test that DynamoDB cache hit returns cached value without API call."""
        self.mock_user_store.get_email_to_slack_mapping.return_value = "U67890"

        result = await self.ops.get_slack_id_by_email("test@example.com")

        assert result == "U67890"
        self.mock_user_store.get_email_to_slack_mapping.assert_awaited_once_with("test@example.com")
        # Verify memory cache was updated
        assert self.ops._email_to_slack_cache["test@example.com"] == "U67890"

    async def test_get_slack_id_by_email_dynamodb_cache_miss(self) -> None:
        """Test that DynamoDB cache miss triggers Slack API lookup."""
        self.mock_user_store.get_email_to_slack_mapping.return_value = None
        self.mock_user_store.store_email_to_slack_mapping.return_value = True

        with patch.object(
            self.ops, "_fetch_slack_id_by_email_internal", new=AsyncMock()
        ) as mock_fetch:
            mock_fetch.return_value = "U99999"

            result = await self.ops.get_slack_id_by_email("test@example.com")

            assert result == "U99999"
            self.mock_user_store.get_email_to_slack_mapping.assert_awaited_once()
            mock_fetch.assert_awaited_once_with("test@example.com")
            self.mock_user_store.store_email_to_slack_mapping.assert_awaited_once_with(
                "test@example.com", "U99999"
            )

    async def test_get_slack_id_by_email_dynamodb_error_fallback_to_api(self) -> None:
        """Test that DynamoDB error falls back to Slack API."""
        self.mock_user_store.get_email_to_slack_mapping.side_effect = Exception("DB error")
        self.mock_user_store.store_email_to_slack_mapping.return_value = True

        with patch.object(
            self.ops, "_fetch_slack_id_by_email_internal", new=AsyncMock()
        ) as mock_fetch:
            mock_fetch.return_value = "U11111"

            result = await self.ops.get_slack_id_by_email("test@example.com")

            assert result == "U11111"
            mock_fetch.assert_awaited_once()

    # ==================== Slack API Tests ====================

    async def test_get_slack_id_by_email_api_success(self) -> None:
        """Test successful Slack API lookup and caching."""
        self.mock_user_store.get_email_to_slack_mapping.return_value = None
        self.mock_user_store.store_email_to_slack_mapping.return_value = True

        with patch.object(
            self.ops, "_fetch_slack_id_by_email_internal", new=AsyncMock()
        ) as mock_fetch:
            mock_fetch.return_value = "U22222"

            result = await self.ops.get_slack_id_by_email("test@example.com")

            assert result == "U22222"
            # Verify both caches were updated
            assert self.ops._email_to_slack_cache["test@example.com"] == "U22222"
            self.mock_user_store.store_email_to_slack_mapping.assert_awaited_once()

    async def test_get_slack_id_by_email_api_not_found(self) -> None:
        """Test when Slack API doesn't find the user."""
        self.mock_user_store.get_email_to_slack_mapping.return_value = None

        with patch.object(
            self.ops, "_fetch_slack_id_by_email_internal", new=AsyncMock()
        ) as mock_fetch:
            mock_fetch.return_value = None

            result = await self.ops.get_slack_id_by_email("notfound@example.com")

            assert result is None
            # Verify cache was NOT updated with None
            assert "notfound@example.com" not in self.ops._email_to_slack_cache
            self.mock_user_store.store_email_to_slack_mapping.assert_not_awaited()

    async def test_get_slack_id_by_email_db_store_failure_still_returns_result(self) -> None:
        """Test that DynamoDB store failure doesn't affect the return value."""
        self.mock_user_store.get_email_to_slack_mapping.return_value = None
        self.mock_user_store.store_email_to_slack_mapping.side_effect = Exception("DB write error")

        with patch.object(
            self.ops, "_fetch_slack_id_by_email_internal", new=AsyncMock()
        ) as mock_fetch:
            mock_fetch.return_value = "U33333"

            result = await self.ops.get_slack_id_by_email("test@example.com")

            # Should still return the result despite DB error
            assert result == "U33333"
            # Memory cache should still be updated
            assert self.ops._email_to_slack_cache["test@example.com"] == "U33333"

    # ==================== Internal API Method Tests ====================

    async def test_fetch_slack_id_by_email_internal_success(self) -> None:
        """Test successful Slack API call for email lookup."""
        self.ops.config = MagicMock()
        self.ops.config.get_api_base_url.return_value = "http://api"
        self.ops.config.get_headers.return_value = {"Authorization": "token"}

        mock_response = {
            "status": 200,
            "headers": {},
            "body": b'{"ok": true, "user": {"id": "U44444", "name": "testuser"}}',
        }

        with patch.object(self.ops, "_make_api_request", new=AsyncMock(return_value=mock_response)):
            result = await self.ops._fetch_slack_id_by_email_internal("test@example.com")

            assert result == "U44444"

    async def test_fetch_slack_id_by_email_internal_user_not_found(self) -> None:
        """Test Slack API returns users_not_found error."""
        self.ops.config = MagicMock()
        self.ops.config.get_api_base_url.return_value = "http://api"
        self.ops.config.get_headers.return_value = {"Authorization": "token"}

        mock_response = {
            "status": 200,
            "headers": {},
            "body": b'{"ok": false, "error": "users_not_found"}',
        }

        with patch.object(self.ops, "_make_api_request", new=AsyncMock(return_value=mock_response)):
            result = await self.ops._fetch_slack_id_by_email_internal("notfound@example.com")

            assert result is None

    async def test_fetch_slack_id_by_email_internal_api_error(self) -> None:
        """Test Slack API returns an error."""
        self.ops.config = MagicMock()
        self.ops.config.get_api_base_url.return_value = "http://api"
        self.ops.config.get_headers.return_value = {"Authorization": "token"}

        mock_response = {
            "status": 200,
            "headers": {},
            "body": b'{"ok": false, "error": "invalid_auth"}',
        }

        with patch.object(self.ops, "_make_api_request", new=AsyncMock(return_value=mock_response)):
            result = await self.ops._fetch_slack_id_by_email_internal("test@example.com")

            assert result is None

    async def test_fetch_slack_id_by_email_internal_exception(self) -> None:
        """Test Slack API call throws exception."""
        self.ops.config = MagicMock()
        self.ops.config.get_api_base_url.return_value = "http://api"
        self.ops.config.get_headers.return_value = {"Authorization": "token"}

        with patch.object(
            self.ops, "_make_api_request", new=AsyncMock(side_effect=Exception("Network error"))
        ):
            result = await self.ops._fetch_slack_id_by_email_internal("test@example.com")

            assert result is None

    async def test_fetch_slack_id_by_email_internal_ok_but_no_id(self) -> None:
        """Test Slack API returns ok but no user ID in response."""
        self.ops.config = MagicMock()
        self.ops.config.get_api_base_url.return_value = "http://api"
        self.ops.config.get_headers.return_value = {"Authorization": "token"}

        mock_response = {
            "status": 200,
            "headers": {},
            "body": b'{"ok": true, "user": {"name": "testuser"}}',  # Missing "id"
        }

        with patch.object(self.ops, "_make_api_request", new=AsyncMock(return_value=mock_response)):
            result = await self.ops._fetch_slack_id_by_email_internal("test@example.com")

            assert result is None

    # ==================== Full Flow Integration Tests ====================

    async def test_full_flow_new_email_lookup(self) -> None:
        """Test complete flow: cache miss -> DB miss -> API success -> caching."""
        # Start with empty caches
        self.ops._email_to_slack_cache = {}
        self.mock_user_store.get_email_to_slack_mapping.return_value = None
        self.mock_user_store.store_email_to_slack_mapping.return_value = True

        with patch.object(
            self.ops, "_fetch_slack_id_by_email_internal", new=AsyncMock()
        ) as mock_fetch:
            mock_fetch.return_value = "U55555"

            # First lookup - should go to API
            result1 = await self.ops.get_slack_id_by_email("new@example.com")
            assert result1 == "U55555"
            mock_fetch.assert_awaited_once()

            # Second lookup - should hit memory cache
            mock_fetch.reset_mock()
            self.mock_user_store.get_email_to_slack_mapping.reset_mock()

            result2 = await self.ops.get_slack_id_by_email("new@example.com")
            assert result2 == "U55555"
            mock_fetch.assert_not_awaited()
            self.mock_user_store.get_email_to_slack_mapping.assert_not_awaited()
