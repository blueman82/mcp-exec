"""Unit tests for DynamoDB session manager.

Tests CRUD operations with mocked aioboto3 DynamoDB table.
Verifies TTL management, deletion verification, and privacy compliance.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from asksplunk.session import SessionDeletionError
from asksplunk.session.manager import SessionManager


class TestSessionManager:
    """Test DynamoDB session manager CRUD operations."""

    @pytest.fixture
    def mock_dynamodb_table(self):
        """Mock aioboto3 DynamoDB table resource."""
        table = AsyncMock()
        table.put_item = AsyncMock()
        table.get_item = AsyncMock(return_value={"Item": {}})
        table.update_item = AsyncMock()
        table.delete_item = AsyncMock()
        return table

    @pytest.mark.asyncio
    async def test_create_session_sets_ttl_30_minutes_future(self, mock_dynamodb_table):
        """create_session should set TTL to 30 minutes from now."""
        manager = SessionManager(table=mock_dynamodb_table)

        before = datetime.now()
        async with manager:
            await manager.create_session("thread-123", "U123", "C456", "test question")

        # Verify put_item called
        mock_dynamodb_table.put_item.assert_called_once()

        # Check TTL is approximately 30 minutes in future
        call_args = mock_dynamodb_table.put_item.call_args[1]
        item = call_args["Item"]
        ttl = datetime.fromtimestamp(item["ttl"])
        expected_ttl = before + timedelta(minutes=30)

        assert abs((ttl - expected_ttl).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_create_session_stores_initial_state(self, mock_dynamodb_table):
        """create_session should store thread_id, user_id, channel_id, and INITIALIZE state."""
        manager = SessionManager(table=mock_dynamodb_table)

        async with manager:
            session = await manager.create_session("thread-123", "U123", "C456", "test question")

        assert session["thread_id"] == "thread-123"
        assert session["user_id"] == "U123"
        assert session["channel_id"] == "C456"
        assert session["agent_state"] == "INITIALIZE"
        assert "created_at" in session
        assert "ttl" in session
        mock_dynamodb_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_session_resets_ttl(self, mock_dynamodb_table):
        """update_session should reset TTL to 30 minutes from update time."""
        manager = SessionManager(table=mock_dynamodb_table)

        # Mock get_session to return updated session
        mock_dynamodb_table.get_item = AsyncMock(
            return_value={
                "Item": {
                    "thread_id": "thread-123",
                    "agent_state": "EVALUATE",
                    "ttl": int((datetime.now() + timedelta(minutes=30)).timestamp()),
                }
            }
        )

        before = datetime.now()
        async with manager:
            await manager.update_session("thread-123", {"agent_state": "EVALUATE"})

        # Verify update_item called
        mock_dynamodb_table.update_item.assert_called_once()

        # Check that TTL was included in update
        call_args = mock_dynamodb_table.update_item.call_args[1]
        expr_values = call_args["ExpressionAttributeValues"]

        # TTL should be in the expression values
        assert ":ttl" in expr_values
        ttl = datetime.fromtimestamp(expr_values[":ttl"])
        expected_ttl = before + timedelta(minutes=30)

        assert abs((ttl - expected_ttl).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_delete_session_removes_immediately(self, mock_dynamodb_table):
        """delete_session should call delete_item immediately."""
        manager = SessionManager(table=mock_dynamodb_table)

        # Mock successful deletion (get_item returns nothing)
        mock_dynamodb_table.get_item = AsyncMock(return_value={})

        async with manager:
            await manager.delete_session("thread-123")

        # Should call delete_item
        mock_dynamodb_table.delete_item.assert_called_once_with(Key={"thread_id": "thread-123"})

    @pytest.mark.asyncio
    async def test_delete_session_verifies_deletion(self, mock_dynamodb_table):
        """delete_session should verify deletion with get_item check."""
        manager = SessionManager(table=mock_dynamodb_table)

        # First call to get_item returns empty (deleted)
        mock_dynamodb_table.get_item = AsyncMock(return_value={})

        async with manager:
            await manager.delete_session("thread-123")

        # Should call delete_item and then get_item to verify
        mock_dynamodb_table.delete_item.assert_called_once()
        mock_dynamodb_table.get_item.assert_called_once_with(Key={"thread_id": "thread-123"})

    @pytest.mark.asyncio
    async def test_delete_session_retries_if_verification_fails(self, mock_dynamodb_table):
        """delete_session should retry if verification shows item still exists."""
        manager = SessionManager(table=mock_dynamodb_table)

        # First verification shows item still exists, second shows deleted
        mock_dynamodb_table.get_item = AsyncMock(
            side_effect=[{"Item": {"thread_id": "thread-123"}}, {}]
        )

        async with manager:
            await manager.delete_session("thread-123")

        # Should call delete_item twice (initial + retry)
        assert mock_dynamodb_table.delete_item.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_session_raises_after_retry_failure(self, mock_dynamodb_table):
        """Should raise SessionDeletionError if deletion fails after retry."""
        manager = SessionManager(table=mock_dynamodb_table)

        # Both deletion attempts fail - item still exists
        mock_dynamodb_table.get_item = AsyncMock(return_value={"Item": {"thread_id": "thread-123"}})

        async with manager:
            with pytest.raises(SessionDeletionError, match="privacy violation"):
                await manager.delete_session("thread-123")

            # Should have called delete_item twice (initial + retry)
            assert mock_dynamodb_table.delete_item.call_count == 2
            # Should have called get_item twice (verify initial + verify retry)
            assert mock_dynamodb_table.get_item.call_count == 2

    @pytest.mark.asyncio
    async def test_get_session_returns_none_for_nonexistent(self, mock_dynamodb_table):
        """get_session should return None if session doesn't exist."""
        manager = SessionManager(table=mock_dynamodb_table)

        # Mock empty response
        mock_dynamodb_table.get_item = AsyncMock(return_value={})

        async with manager:
            session = await manager.get_session("nonexistent-thread")

        assert session is None
        mock_dynamodb_table.get_item.assert_called_once_with(
            Key={"thread_id": "nonexistent-thread"}
        )

    @pytest.mark.asyncio
    async def test_get_session_returns_session_if_exists(self, mock_dynamodb_table):
        """get_session should return session dict if it exists."""
        manager = SessionManager(table=mock_dynamodb_table)

        expected_session = {
            "thread_id": "thread-123",
            "user_id": "U123",
            "agent_state": "EVALUATE",
        }

        mock_dynamodb_table.get_item = AsyncMock(return_value={"Item": expected_session})

        async with manager:
            session = await manager.get_session("thread-123")

        assert session == expected_session

    @pytest.mark.asyncio
    async def test_update_session_includes_updated_at_timestamp(self, mock_dynamodb_table):
        """update_session should include updated_at timestamp."""
        manager = SessionManager(table=mock_dynamodb_table)

        mock_dynamodb_table.get_item = AsyncMock(
            return_value={
                "Item": {
                    "thread_id": "thread-123",
                    "agent_state": "EVALUATE",
                    "updated_at": datetime.now().isoformat(),
                }
            }
        )

        before = datetime.now()
        async with manager:
            await manager.update_session("thread-123", {"agent_state": "EVALUATE"})

        call_args = mock_dynamodb_table.update_item.call_args[1]
        expr_values = call_args["ExpressionAttributeValues"]

        assert ":updated_at" in expr_values
        # Verify timestamp is recent
        updated_at = datetime.fromisoformat(expr_values[":updated_at"])
        assert abs((updated_at - before).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_context_manager_raises_error_if_used_outside_context(self, mock_dynamodb_table):
        """SessionManager should raise RuntimeError if used outside context manager."""
        # Create manager WITHOUT providing mock table (to test context requirement)
        manager = SessionManager()

        with pytest.raises(RuntimeError) as exc_info:
            await manager.create_session("thread-123", "U123", "C456", "test")

        assert "async context manager" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_context_manager_allows_operations_when_table_provided(self, mock_dynamodb_table):
        """SessionManager with pre-configured table should work in context."""
        manager = SessionManager(table=mock_dynamodb_table)

        async with manager:
            session = await manager.create_session("thread-123", "U123", "C456", "test")

        assert session["thread_id"] == "thread-123"
        mock_dynamodb_table.put_item.assert_called_once()
