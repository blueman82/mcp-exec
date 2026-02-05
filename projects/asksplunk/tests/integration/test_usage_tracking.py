"""Integration tests for usage tracking feature."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from asksplunk.usage import UsageTracker


@pytest.fixture
def mock_dynamodb_table() -> AsyncMock:
    """Mock DynamoDB table with GSI support."""
    table = AsyncMock()
    table.put_item = AsyncMock()
    table.query = AsyncMock(return_value={"Count": 0})
    return table


class TestUsageTrackingIntegration:
    """Integration tests for usage tracking flow."""

    @pytest.mark.asyncio
    async def test_record_and_retrieve_usage(self, mock_dynamodb_table: AsyncMock) -> None:
        """Test full flow: record events, then retrieve count."""
        tracker = UsageTracker(table=mock_dynamodb_table)

        async with tracker:
            # Record 3 events
            await tracker.record_event()
            await tracker.record_event()
            await tracker.record_event()

            # Verify put_item called 3 times
            assert mock_dynamodb_table.put_item.call_count == 3

            # Verify no user_id in any call (privacy check)
            for call in mock_dynamodb_table.put_item.call_args_list:
                item = call[1]["Item"]
                assert "user_id" not in item
                assert "user" not in item
                assert item["entity_type"] == "USAGE"

    @pytest.mark.asyncio
    async def test_admin_retrieval_gets_count(self, mock_dynamodb_table: AsyncMock) -> None:
        """Test admin can retrieve usage count."""
        mock_dynamodb_table.query = AsyncMock(return_value={"Count": 42})
        tracker = UsageTracker(table=mock_dynamodb_table)

        async with tracker:
            now = datetime.utcnow()
            start = now - timedelta(days=7)
            count = await tracker.get_usage(start, now)

            assert count == 42
            mock_dynamodb_table.query.assert_called_once()

            # Verify GSI was queried
            call_kwargs = mock_dynamodb_table.query.call_args[1]
            assert call_kwargs["IndexName"] == "usage-by-timestamp"

    def test_admin_check(self) -> None:
        """Test admin user detection."""
        assert UsageTracker.is_admin("W7MGASQ2K") is True
        assert UsageTracker.is_admin("WDGLSLQRK") is False  # Removed from admin list
        assert UsageTracker.is_admin("U12345678") is False
