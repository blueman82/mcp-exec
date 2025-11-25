"""
Unit tests for archive processor with consistent read functionality.

Tests that the archive processor uses consistent reads to avoid race conditions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.processing.archive_processor as archive_processor


@pytest.mark.asyncio
class TestArchiveProcessorConsistentRead:
    """Test that archive processor uses consistent reads."""

    async def test_archive_processor_uses_consistent_read(self):
        """Test that process_channel_archive uses get_channel_details_consistent."""
        # Setup
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(
            return_value={"channel_id": "C123", "archived": False, "archived_at": 0}
        )
        dynamodb_store.get_channel_details = (
            AsyncMock()
        )  # Regular method should NOT be called
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Execute
        with patch("time.time", return_value=1234567890):
            await archive_processor.process_channel_archive("C123", dynamodb_store)

        # Verify consistent read was used
        dynamodb_store.get_channel_details_consistent.assert_called_once_with("C123")
        dynamodb_store.get_channel_details.assert_not_called()  # Regular method should NOT be called

        # Verify the rest of the flow worked
        dynamodb_store.update_channel_archived_status.assert_called_once()
        dynamodb_store.update_channel_fields.assert_called_once()

    async def test_archive_processor_consistent_read_channel_not_found(self):
        """Test behavior when consistent read returns no channel."""
        # Setup
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(return_value=None)
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Execute
        await archive_processor.process_channel_archive("C404", dynamodb_store)

        # Verify
        dynamodb_store.get_channel_details_consistent.assert_called_once_with("C404")
        dynamodb_store.update_channel_archived_status.assert_not_called()
        dynamodb_store.update_channel_fields.assert_not_called()

    async def test_archive_processor_consistent_read_already_archived(self):
        """Test that consistent read prevents race condition with already archived channel."""
        # Setup - simulating a race condition where channel was just archived
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(
            return_value={
                "channel_id": "C789",
                "archived": True,  # Already archived based on consistent read
                "archived_at": 1234567800,
            }
        )
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Execute
        await archive_processor.process_channel_archive("C789", dynamodb_store)

        # Verify - should skip processing
        dynamodb_store.get_channel_details_consistent.assert_called_once_with("C789")
        dynamodb_store.update_channel_archived_status.assert_not_called()
        dynamodb_store.update_channel_fields.assert_not_called()
