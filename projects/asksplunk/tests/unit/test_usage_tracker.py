"""Unit tests for UsageTracker.

Tests record_event, get_usage, is_admin with mocked DynamoDB table.
Verifies no user_id in put_item calls (privacy check).
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from asksplunk.usage.tracker import UsageTracker


class TestUsageTracker:
    """Test UsageTracker operations."""

    @pytest.fixture
    def mock_dynamodb_table(self) -> AsyncMock:
        """Mock aioboto3 DynamoDB table resource."""
        table = AsyncMock()
        table.put_item = AsyncMock()
        table.query = AsyncMock(return_value={"Count": 0})
        return table

    @pytest.mark.asyncio
    async def test_record_event_stores_timestamp_only(self, mock_dynamodb_table: AsyncMock) -> None:
        """record_event should store timestamp but NOT user_id (privacy)."""
        tracker = UsageTracker(table=mock_dynamodb_table)

        async with tracker:
            await tracker.record_event()

        mock_dynamodb_table.put_item.assert_called_once()
        call_args = mock_dynamodb_table.put_item.call_args[1]
        item = call_args["Item"]

        # Privacy check: NO user_id in the item
        assert "user_id" not in item
        assert "timestamp" in item
        assert "entity_type" in item
        assert item["entity_type"] == "USAGE"
        assert item["thread_id"].startswith("USAGE#")

    @pytest.mark.asyncio
    async def test_record_event_uses_iso_timestamp(self, mock_dynamodb_table: AsyncMock) -> None:
        """record_event should use ISO format timestamp with Z suffix."""
        tracker = UsageTracker(table=mock_dynamodb_table)

        async with tracker:
            await tracker.record_event()

        call_args = mock_dynamodb_table.put_item.call_args[1]
        item = call_args["Item"]

        assert item["timestamp"].endswith("Z")
        # Should be parseable as ISO format (without Z)
        datetime.fromisoformat(item["timestamp"].rstrip("Z"))

    @pytest.mark.asyncio
    async def test_get_usage_queries_gsi(self, mock_dynamodb_table: AsyncMock) -> None:
        """get_usage should query the usage-by-timestamp GSI."""
        mock_dynamodb_table.query = AsyncMock(return_value={"Count": 42})
        tracker = UsageTracker(table=mock_dynamodb_table)

        start = datetime(2025, 1, 1, 0, 0, 0)
        end = datetime(2025, 1, 31, 23, 59, 59)

        async with tracker:
            count = await tracker.get_usage(start, end)

        assert count == 42
        mock_dynamodb_table.query.assert_called_once()
        call_args = mock_dynamodb_table.query.call_args[1]

        assert call_args["IndexName"] == "usage-by-timestamp"
        assert call_args["Select"] == "COUNT"
        assert ":et" in call_args["ExpressionAttributeValues"]
        assert call_args["ExpressionAttributeValues"][":et"] == "USAGE"

    @pytest.mark.asyncio
    async def test_get_usage_returns_zero_for_empty_result(
        self, mock_dynamodb_table: AsyncMock
    ) -> None:
        """get_usage should return 0 when no events found."""
        mock_dynamodb_table.query = AsyncMock(return_value={})
        tracker = UsageTracker(table=mock_dynamodb_table)

        start = datetime(2025, 1, 1, 0, 0, 0)
        end = datetime(2025, 1, 31, 23, 59, 59)

        async with tracker:
            count = await tracker.get_usage(start, end)

        assert count == 0

    def test_is_admin_returns_true_for_admin_users(self) -> None:
        """is_admin should return True when user_id is in admin_ids list."""
        admin_ids = ["W7MGASQ2K", "WDGLSLQRK"]
        assert UsageTracker.is_admin("W7MGASQ2K", admin_ids) is True
        assert UsageTracker.is_admin("WDGLSLQRK", admin_ids) is True

    def test_is_admin_returns_false_for_non_admin_users(self) -> None:
        """is_admin should return False when user_id is not in admin_ids list."""
        admin_ids = ["W7MGASQ2K"]
        assert UsageTracker.is_admin("UXYZ12345", admin_ids) is False
        assert UsageTracker.is_admin("", admin_ids) is False
        assert UsageTracker.is_admin("random-id", admin_ids) is False

    def test_is_admin_returns_false_for_empty_admin_list(self) -> None:
        """is_admin should return False when admin_ids list is empty."""
        assert UsageTracker.is_admin("W7MGASQ2K", []) is False

    @pytest.mark.asyncio
    async def test_context_manager_raises_error_if_used_outside_context(self) -> None:
        """UsageTracker should raise RuntimeError if used outside context manager."""
        tracker = UsageTracker()

        with pytest.raises(RuntimeError) as exc_info:
            await tracker.record_event()

        assert "async context manager" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_context_manager_allows_operations_when_table_provided(
        self, mock_dynamodb_table: AsyncMock
    ) -> None:
        """UsageTracker with pre-configured table should work in context."""
        tracker = UsageTracker(table=mock_dynamodb_table)

        async with tracker:
            await tracker.record_event()

        mock_dynamodb_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_event_privacy_no_pii_fields(self, mock_dynamodb_table: AsyncMock) -> None:
        """record_event must not store any PII fields."""
        tracker = UsageTracker(table=mock_dynamodb_table)

        async with tracker:
            await tracker.record_event()

        call_args = mock_dynamodb_table.put_item.call_args[1]
        item = call_args["Item"]

        # Explicit privacy checks - ensure NO PII fields
        pii_fields = ["user_id", "user", "email", "name", "channel_id", "message", "question"]
        for field in pii_fields:
            assert field not in item, f"PII field '{field}' found in usage record"
