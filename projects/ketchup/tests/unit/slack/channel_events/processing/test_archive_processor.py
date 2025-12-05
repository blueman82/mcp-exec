"""
Unit tests for packages/slack/channel_events/processing/archive_processor.py

Covers:
- process_channel_archive
- All error and edge cases, including channel not found, already archived, timestamp logic, and DB update.
- Auto-status fields cleanup when channel is archived

All dependencies are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.processing.archive_processor as archive_processor


@pytest.fixture
def mock_archive_ops():
    """Mock archive operations with proper async methods."""
    ops = AsyncMock()
    ops.archive_channel.return_value = True
    ops.get_archive_status.return_value = "archived"
    return ops


@pytest.fixture
def mock_dynamodb_store_with_ops():
    """Mock DynamoDB store with properly mocked trust_ops and feedback_ops."""
    store = MagicMock()
    store.get_channel_details_consistent = AsyncMock()
    store.update_channel_archived_status = AsyncMock()
    store.update_channel_fields = AsyncMock()

    # Mock trust operations
    store.trust_ops = AsyncMock()
    store.trust_ops.cleanup_channel_trust_data = AsyncMock(return_value=True)

    # Mock feedback operations
    store.feedback_ops = AsyncMock()
    store.feedback_ops.cleanup_channel_feedback_data = AsyncMock(return_value=True)

    # Mock channel operations for JIRA functionality
    store.channel_ops = AsyncMock()
    store.channel_ops.update_channel_fields = AsyncMock()

    return store


@pytest.mark.asyncio
class TestProcessChannelArchive:
    async def test_channel_not_found(self, mock_dynamodb_store_with_ops):
        mock_dynamodb_store_with_ops.get_channel_details_consistent.return_value = None
        await archive_processor.process_channel_archive("C1", mock_dynamodb_store_with_ops)
        mock_dynamodb_store_with_ops.update_channel_archived_status.assert_not_awaited()
        mock_dynamodb_store_with_ops.update_channel_fields.assert_not_awaited()

    async def test_channel_already_archived(self, mock_dynamodb_store_with_ops):
        mock_dynamodb_store_with_ops.get_channel_details_consistent.return_value = {
            "archived": True
        }
        await archive_processor.process_channel_archive("C2", mock_dynamodb_store_with_ops)
        mock_dynamodb_store_with_ops.update_channel_archived_status.assert_not_awaited()
        mock_dynamodb_store_with_ops.update_channel_fields.assert_not_awaited()

    @patch("time.time", return_value=1234567890)
    async def test_channel_no_archived_at_sets_new(self, mock_time, mock_dynamodb_store_with_ops):
        mock_dynamodb_store_with_ops.get_channel_details_consistent.return_value = {
            "archived": False
        }
        await archive_processor.process_channel_archive("C3", mock_dynamodb_store_with_ops)
        mock_dynamodb_store_with_ops.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C3", archived=True, archived_at=1234567890
        )
        # Verify auto-status fields cleanup
        mock_dynamodb_store_with_ops.update_channel_fields.assert_awaited_once_with(
            channel_id="C3",
            updates={
                "auto_status_last_content": "",
                "auto_status_last_message_ts": "0",
                "auto_status_last_thread_ts": "0",
                "auto_status_last_post_ts": "0",
                "auto_status_last_jira_comment_ts": "0",
                "auto_status_attempt_count": 0,
                "auto_status_enabled": False,
                "auto_status_last_run": 0,
            },
        )

    @patch("time.time", return_value=1234567890)
    async def test_channel_archived_at_zero_sets_new(self, mock_time, mock_dynamodb_store_with_ops):
        mock_dynamodb_store_with_ops.get_channel_details_consistent.return_value = {
            "archived": False,
            "archived_at": 0,
        }
        await archive_processor.process_channel_archive("C4", mock_dynamodb_store_with_ops)
        mock_dynamodb_store_with_ops.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C4", archived=True, archived_at=1234567890
        )
        # Verify auto-status fields cleanup
        mock_dynamodb_store_with_ops.update_channel_fields.assert_awaited_once_with(
            channel_id="C4",
            updates={
                "auto_status_last_content": "",
                "auto_status_last_message_ts": "0",
                "auto_status_last_thread_ts": "0",
                "auto_status_last_post_ts": "0",
                "auto_status_last_jira_comment_ts": "0",
                "auto_status_attempt_count": 0,
                "auto_status_enabled": False,
                "auto_status_last_run": 0,
            },
        )

    async def test_channel_preserves_existing_archived_at(self, mock_dynamodb_store_with_ops):
        mock_dynamodb_store_with_ops.get_channel_details_consistent.return_value = {
            "archived": False,
            "archived_at": 1111111111,
        }
        await archive_processor.process_channel_archive("C5", mock_dynamodb_store_with_ops)
        mock_dynamodb_store_with_ops.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C5", archived=True, archived_at=1111111111
        )
        # Verify auto-status fields cleanup
        mock_dynamodb_store_with_ops.update_channel_fields.assert_awaited_once_with(
            channel_id="C5",
            updates={
                "auto_status_last_content": "",
                "auto_status_last_message_ts": "0",
                "auto_status_last_thread_ts": "0",
                "auto_status_last_post_ts": "0",
                "auto_status_last_jira_comment_ts": "0",
                "auto_status_attempt_count": 0,
                "auto_status_enabled": False,
                "auto_status_last_run": 0,
            },
        )

    @patch("time.time", return_value=1234567890)
    async def test_auto_status_cleanup_failure_does_not_fail_archive(
        self, mock_time, mock_dynamodb_store_with_ops
    ):
        """Test that auto-status cleanup failure doesn't prevent channel archiving."""
        mock_dynamodb_store_with_ops.get_channel_details_consistent.return_value = {
            "archived": False
        }
        # Mock update_channel_fields to raise an exception
        mock_dynamodb_store_with_ops.update_channel_fields.side_effect = Exception("DynamoDB error")

        # Should not raise exception
        await archive_processor.process_channel_archive("C6", mock_dynamodb_store_with_ops)

        # Archive should still be successful
        mock_dynamodb_store_with_ops.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C6", archived=True, archived_at=1234567890
        )
        # Cleanup should have been attempted
        mock_dynamodb_store_with_ops.update_channel_fields.assert_awaited_once()

    @patch("time.time", return_value=1234567890)
    async def test_auto_status_fields_are_reset_correctly(
        self, mock_time, mock_dynamodb_store_with_ops
    ):
        """Test that all auto-status fields are reset to their correct default values."""
        mock_dynamodb_store_with_ops.get_channel_details_consistent.return_value = {
            "archived": False,
            "auto_status_last_content": "Previous status content",
            "auto_status_last_message_ts": "1234567890.123",
            "auto_status_last_post_ts": "1234567890.456",
            "auto_status_attempt_count": 3,
            "auto_status_enabled": True,
            "auto_status_last_run": 1234567800,
        }

        await archive_processor.process_channel_archive("C7", mock_dynamodb_store_with_ops)

        # Verify all fields are reset properly
        mock_dynamodb_store_with_ops.update_channel_fields.assert_awaited_once_with(
            channel_id="C7",
            updates={
                "auto_status_last_content": "",  # Empty string
                "auto_status_last_message_ts": "0",  # Reset to "0"
                "auto_status_last_thread_ts": "0",  # Reset to "0"
                "auto_status_last_post_ts": "0",  # Reset to "0"
                "auto_status_last_jira_comment_ts": "0",  # Reset to "0"
                "auto_status_attempt_count": 0,  # Reset to 0
                "auto_status_enabled": False,  # Disabled
                "auto_status_last_run": 0,  # Reset to 0
            },
        )
