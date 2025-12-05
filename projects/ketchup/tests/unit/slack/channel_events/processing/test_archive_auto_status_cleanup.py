"""
Unit tests specifically for auto-status cleanup functionality in archive_processor.py

Tests:
- Verify all auto-status fields are cleaned up when channel is archived
- Ensure cleanup failure doesn't block archive operation
- Test edge cases and error scenarios
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.processing.archive_processor as archive_processor


def create_mock_dynamodb_store():
    """Create a properly mocked DynamoDB store with all required async operations."""
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

    return store


@pytest.mark.asyncio
class TestArchiveAutoStatusCleanup:
    """Test class focused on auto-status cleanup during channel archiving."""

    @patch("time.time", return_value=1234567890)
    async def test_successful_auto_status_cleanup(self, mock_time):
        """Test successful cleanup of all auto-status fields."""
        # Arrange
        dynamodb_store = create_mock_dynamodb_store()
        dynamodb_store.get_channel_details_consistent.return_value = {
            "archived": False,
            "channel_id": "C12345",
            "channel_name": "test-channel",
            # Pre-existing auto-status data
            "auto_status_last_content": "Previous weekly status update",
            "auto_status_last_message_ts": "1734567890.123456",
            "auto_status_last_post_ts": "1734567890.654321",
            "auto_status_attempt_count": 2,
            "auto_status_enabled": True,
            "auto_status_last_run": 1734567800,
        }

        # Act
        await archive_processor.process_channel_archive("C12345", dynamodb_store)

        # Assert - channel should be archived
        dynamodb_store.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C12345", archived=True, archived_at=1234567890
        )

        # Assert - auto-status fields should be cleaned
        dynamodb_store.update_channel_fields.assert_awaited_once_with(
            channel_id="C12345",
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
    async def test_cleanup_with_partial_auto_status_fields(self, mock_time):
        """Test cleanup when channel has only some auto-status fields."""
        # Arrange
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(
            return_value={
                "archived": False,
                "channel_id": "C23456",
                # Only some auto-status fields present
                "auto_status_enabled": True,
                "auto_status_last_message_ts": "1734567890.123456",
            }
        )
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Act
        await archive_processor.process_channel_archive("C23456", dynamodb_store)

        # Assert - cleanup should still set all fields
        dynamodb_store.update_channel_fields.assert_awaited_once_with(
            channel_id="C23456",
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
    async def test_cleanup_failure_logged_but_archive_succeeds(self, mock_time):
        """Test that cleanup failure is logged but doesn't prevent archive."""
        # Arrange
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(return_value={"archived": False})
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock(
            side_effect=Exception("DynamoDB throttling error")
        )

        # Act - should not raise exception
        await archive_processor.process_channel_archive("C34567", dynamodb_store)

        # Assert - archive should complete
        dynamodb_store.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C34567", archived=True, archived_at=1234567890
        )
        # Assert - cleanup was attempted
        dynamodb_store.update_channel_fields.assert_awaited_once()

    @patch("time.time", return_value=1234567890)
    async def test_cleanup_with_empty_existing_values(self, mock_time):
        """Test cleanup when auto-status fields already have empty/zero values."""
        # Arrange
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(
            return_value={
                "archived": False,
                "auto_status_last_content": "",
                "auto_status_last_message_ts": "0",
                "auto_status_last_post_ts": "",
                "auto_status_attempt_count": 0,
                "auto_status_enabled": False,
                "auto_status_last_run": 0,
            }
        )
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Act
        await archive_processor.process_channel_archive("C45678", dynamodb_store)

        # Assert - cleanup should still be called (idempotent operation)
        dynamodb_store.update_channel_fields.assert_awaited_once_with(
            channel_id="C45678",
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

    async def test_no_cleanup_when_channel_not_found(self):
        """Test that cleanup is not attempted when channel doesn't exist."""
        # Arrange
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(return_value=None)
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Act
        await archive_processor.process_channel_archive("C56789", dynamodb_store)

        # Assert - no operations should be performed
        dynamodb_store.update_channel_archived_status.assert_not_awaited()
        dynamodb_store.update_channel_fields.assert_not_awaited()

    async def test_no_cleanup_when_channel_already_archived(self):
        """Test that cleanup is not attempted when channel is already archived."""
        # Arrange
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(
            return_value={
                "archived": True,
                "auto_status_enabled": True,
                "auto_status_last_content": "Should not be cleaned",
            }
        )
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Act
        await archive_processor.process_channel_archive("C67890", dynamodb_store)

        # Assert - no operations should be performed
        dynamodb_store.update_channel_archived_status.assert_not_awaited()
        dynamodb_store.update_channel_fields.assert_not_awaited()

    @patch("time.time", return_value=1234567890)
    async def test_cleanup_resets_message_timestamp_to_zero_string(self, mock_time):
        """Verify that auto_status_last_message_ts is reset to string "0"."""
        # Arrange
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(
            return_value={
                "archived": False,
                "auto_status_last_message_ts": "1734567890.123456",  # Slack timestamp format
            }
        )
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Act
        await archive_processor.process_channel_archive("C78901", dynamodb_store)

        # Assert - verify the field is reset to "0" (string)
        call_args = dynamodb_store.update_channel_fields.call_args
        assert call_args[1]["updates"]["auto_status_last_message_ts"] == "0"
        assert isinstance(call_args[1]["updates"]["auto_status_last_message_ts"], str)

    @patch("time.time", return_value=1234567890)
    async def test_trust_endorsement_cleanup_success(self, mock_time):
        """Test successful cleanup of trust endorsement data during archive."""
        # Arrange
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(return_value={"archived": False})
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Mock trust operations
        mock_trust_ops = AsyncMock()
        mock_trust_ops.cleanup_channel_trust_data = AsyncMock(return_value=True)
        dynamodb_store.trust_ops = mock_trust_ops

        # Act
        await archive_processor.process_channel_archive("C12345", dynamodb_store)

        # Assert - trust cleanup was called
        mock_trust_ops.cleanup_channel_trust_data.assert_awaited_once_with("C12345")

    @patch("time.time", return_value=1234567890)
    async def test_trust_endorsement_cleanup_failure_logged(self, mock_time):
        """Test that trust cleanup failure is logged but doesn't prevent archive."""
        # Arrange
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(return_value={"archived": False})
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Mock trust operations with failure
        mock_trust_ops = AsyncMock()
        mock_trust_ops.cleanup_channel_trust_data = AsyncMock(
            side_effect=Exception("Trust cleanup failed")
        )
        dynamodb_store.trust_ops = mock_trust_ops

        # Act - should not raise exception
        await archive_processor.process_channel_archive("C23456", dynamodb_store)

        # Assert - archive should complete despite trust cleanup failure
        dynamodb_store.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C23456", archived=True, archived_at=1234567890
        )
        # Assert - auto-status cleanup should still work
        dynamodb_store.update_channel_fields.assert_awaited_once()
        # Assert - trust cleanup was attempted
        mock_trust_ops.cleanup_channel_trust_data.assert_awaited_once_with("C23456")

    @patch("time.time", return_value=1234567890)
    async def test_trust_endorsement_cleanup_returns_false(self, mock_time):
        """Test when trust cleanup returns False (no error but unsuccessful)."""
        # Arrange
        dynamodb_store = MagicMock()
        dynamodb_store.get_channel_details_consistent = AsyncMock(return_value={"archived": False})
        dynamodb_store.update_channel_archived_status = AsyncMock()
        dynamodb_store.update_channel_fields = AsyncMock()

        # Mock trust operations returning False
        mock_trust_ops = AsyncMock()
        mock_trust_ops.cleanup_channel_trust_data = AsyncMock(return_value=False)
        dynamodb_store.trust_ops = mock_trust_ops

        # Act
        await archive_processor.process_channel_archive("C34567", dynamodb_store)

        # Assert - archive should complete
        dynamodb_store.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C34567", archived=True, archived_at=1234567890
        )
        # Assert - trust cleanup was attempted
        mock_trust_ops.cleanup_channel_trust_data.assert_awaited_once_with("C34567")

    @patch("time.time", return_value=1234567890)
    async def test_archive_with_cleanup(self, mock_time):
        """Test archiving with successful cleanup of all operations (trust_ops + feedback_ops)."""
        # Arrange
        dynamodb_store = create_mock_dynamodb_store()
        dynamodb_store.get_channel_details_consistent.return_value = {
            "archived": False,
            "auto_status_enabled": True,
            "auto_status_last_content": "Previous status",
        }

        # Act
        await archive_processor.process_channel_archive("C12345", dynamodb_store)

        # Assert - archive completed
        dynamodb_store.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C12345", archived=True, archived_at=1234567890
        )

        # Assert - auto-status fields cleanup
        dynamodb_store.update_channel_fields.assert_awaited_once_with(
            channel_id="C12345",
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

        # Assert - trust cleanup called
        dynamodb_store.trust_ops.cleanup_channel_trust_data.assert_awaited_once_with("C12345")

        # Assert - feedback cleanup called
        dynamodb_store.feedback_ops.cleanup_channel_feedback_data.assert_awaited_once_with("C12345")

    @patch("time.time", return_value=1234567890)
    async def test_archive_partial_cleanup(self, mock_time):
        """Test archiving with partial cleanup success (trust succeeds, feedback fails)."""
        # Arrange
        dynamodb_store = create_mock_dynamodb_store()
        dynamodb_store.get_channel_details_consistent.return_value = {
            "archived": False,
            "auto_status_enabled": True,
        }

        # Mock trust ops to succeed and feedback ops to fail
        dynamodb_store.trust_ops.cleanup_channel_trust_data.return_value = True
        dynamodb_store.feedback_ops.cleanup_channel_feedback_data.side_effect = Exception(
            "Feedback cleanup failed"
        )

        # Act - should not raise exception
        await archive_processor.process_channel_archive("C23456", dynamodb_store)

        # Assert - archive still completed
        dynamodb_store.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C23456", archived=True, archived_at=1234567890
        )

        # Assert - auto-status cleanup still worked
        dynamodb_store.update_channel_fields.assert_awaited_once()

        # Assert - trust cleanup was attempted and succeeded
        dynamodb_store.trust_ops.cleanup_channel_trust_data.assert_awaited_once_with("C23456")

        # Assert - feedback cleanup was attempted (but failed)
        dynamodb_store.feedback_ops.cleanup_channel_feedback_data.assert_awaited_once_with("C23456")

    @patch("time.time", return_value=1234567890)
    async def test_archive_cleanup_failures(self, mock_time):
        """Test archiving when all cleanup operations fail but archive still succeeds."""
        # Arrange
        dynamodb_store = create_mock_dynamodb_store()
        dynamodb_store.get_channel_details_consistent.return_value = {
            "archived": False,
            "auto_status_enabled": True,
        }

        # Mock all cleanup operations to fail
        dynamodb_store.update_channel_fields.side_effect = Exception("Auto-status cleanup failed")
        dynamodb_store.trust_ops.cleanup_channel_trust_data.side_effect = Exception(
            "Trust cleanup failed"
        )
        dynamodb_store.feedback_ops.cleanup_channel_feedback_data.side_effect = Exception(
            "Feedback cleanup failed"
        )

        # Act - should not raise exception
        await archive_processor.process_channel_archive("C34567", dynamodb_store)

        # Assert - archive still completed despite all cleanup failures
        dynamodb_store.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C34567", archived=True, archived_at=1234567890
        )

        # Assert - all cleanup operations were attempted
        dynamodb_store.update_channel_fields.assert_awaited_once()
        dynamodb_store.trust_ops.cleanup_channel_trust_data.assert_awaited_once_with("C34567")
        dynamodb_store.feedback_ops.cleanup_channel_feedback_data.assert_awaited_once_with("C34567")
