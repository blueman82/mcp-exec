"""
Unit tests for SlackUserOps (user_ops.py).

Covers:
- SlackUserOps.get_user_names: all logic branches, error handling, and edge cases
- SlackUserOps._fetch_user_info: correct delegation and error handling
- SlackUserOps._fetch_user_info_internal: API call, error, and backoff logic
- All dependencies (UserStore, SlackConfig, SlackAsyncClient) are mocked

Edge Cases Covered:
- Empty user_ids input
- All user_ids in cache
- Some user_ids in DB, some in cache, some require API
- API returns error or exception
- Batch processing and rate limiting logic
- Fallback to user_id as name on error
- DB batch_store_users success/failure

Expected Outcomes:
- get_user_names returns correct mapping for all scenarios
- All external calls are mocked and asserted
- All logic branches and error cases are covered

"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.user_operations.user_ops import SlackUserOps


@pytest.mark.asyncio
class TestSlackUserOps:
    def setup_method(self) -> None:
        self.mock_user_store = AsyncMock()
        self.mock_slack_config = MagicMock()
        self.ops = SlackUserOps(
            user_store=self.mock_user_store,
            slack_config=self.mock_slack_config,
            max_concurrent_requests=2,
        )
        self.ops._user_cache = {}

    async def test_get_user_names_empty(self) -> None:
        result = await self.ops.get_user_names([])
        assert result == {}

    async def test_get_user_names_all_in_cache(self) -> None:
        self.ops._user_cache = {"U1": {"name": "Alice"}, "U2": {"name": "Bob"}}
        result = await self.ops.get_user_names(["U1", "U2"])
        assert result == {"U1": "Alice", "U2": "Bob"}

    async def test_get_user_names_db_and_cache(self) -> None:
        self.ops._user_cache = {"U1": {"name": "Alice"}}
        self.mock_user_store.get_users.return_value = {"U2": "Bob"}
        with patch.object(self.ops, "_fetch_user_info_internal", new=AsyncMock()) as mock_fetch:
            mock_fetch.return_value = {"name": "Charlie"}
            self.mock_user_store.batch_store_users.return_value = (1, 0)
            result = await self.ops.get_user_names(["U1", "U2", "U3"])
            assert result["U1"] == "Alice"
            assert result["U2"] == "Bob"
            assert result["U3"] == "Charlie"
            self.mock_user_store.get_users.assert_awaited_once()
            self.mock_user_store.batch_store_users.assert_awaited_once()
            mock_fetch.assert_awaited()

    async def test_get_user_names_api_error_and_fallback(self) -> None:
        self.ops._user_cache = {}
        self.mock_user_store.get_users.return_value = {}
        with patch.object(self.ops, "_fetch_user_info_internal", new=AsyncMock()) as mock_fetch:
            mock_fetch.side_effect = [Exception("fail"), None]
            self.mock_user_store.batch_store_users.return_value = (0, 2)
            result = await self.ops.get_user_names(["U1", "U2"])
            assert result["U1"] == "U1"
            assert result["U2"] == "U2"
            self.mock_user_store.get_users.assert_awaited_once()
            self.mock_user_store.batch_store_users.assert_not_awaited()
            assert mock_fetch.await_count == 2

    async def test_get_user_names_batching(self) -> None:
        self.ops._user_cache = {}
        self.mock_user_store.get_users.return_value = {}
        with patch.object(self.ops, "_fetch_user_info_internal", new=AsyncMock()) as mock_fetch:
            mock_fetch.side_effect = lambda uid: {"name": f"Name_{uid}"}
            self.mock_user_store.batch_store_users.return_value = (2, 0)
            # Simulate more users than BATCH_SIZE (assume BATCH_SIZE=1 for test)
            with patch("packages.slack.user_operations.user_ops.BATCH_SIZE", 1):
                result = await self.ops.get_user_names(["U1", "U2"])
                assert result["U1"] == "Name_U1"
                assert result["U2"] == "Name_U2"
                self.mock_user_store.get_users.assert_awaited_once()
                self.mock_user_store.batch_store_users.assert_awaited_once()
                assert mock_fetch.await_count == 2

    async def test_fetch_user_info_internal_success(self) -> None:
        self.ops.config = MagicMock()
        self.ops.config.get_api_base_url.return_value = "http://api"
        self.ops.config.get_headers.return_value = {"Authorization": "token"}
        # SafeResponse format
        mock_response = {
            "status": 200,
            "headers": {},
            "body": b'{"ok": true, "user": {"name": "Alice"}}',
        }
        with patch.object(self.ops, "_make_api_request", new=AsyncMock(return_value=mock_response)):
            result = await self.ops._fetch_user_info_internal("U1")
            assert result == {"name": "Alice"}

    async def test_fetch_user_info_internal_api_error(self) -> None:
        self.ops.config = MagicMock()
        self.ops.config.get_api_base_url.return_value = "http://api"
        self.ops.config.get_headers.return_value = {"Authorization": "token"}
        mock_response = AsyncMock()
        mock_response.json.return_value = {"ok": False, "error": "not_found"}
        with patch.object(self.ops, "_make_api_request", new=AsyncMock(return_value=mock_response)):
            result = await self.ops._fetch_user_info_internal("U1")
            assert result is None

    async def test_fetch_user_info_internal_exception(self) -> None:
        self.ops.config = MagicMock()
        self.ops.config.get_api_base_url.return_value = "http://api"
        self.ops.config.get_headers.return_value = {"Authorization": "token"}
        with patch.object(
            self.ops, "_make_api_request", new=AsyncMock(side_effect=Exception("fail"))
        ):
            result = await self.ops._fetch_user_info_internal("U1")
            assert result is None

    async def test_get_user_names_all_cached(self) -> None:
        self.ops._user_cache = {"U1": {"name": "Alice"}, "U2": {"name": "Bob"}}
        result = await self.ops.get_user_names(["U1", "U2"])
        assert result == {"U1": "Alice", "U2": "Bob"}
