"""
test_archive_handler.py

Unit tests for the JIRA reporter archive handler.
"""

import time
from unittest.mock import AsyncMock, Mock

import pytest

from jira_reporter.archive_handler import JiraReporterArchiveHandler


@pytest.mark.asyncio
async def test_temporarily_unarchive_channel_success():
    """Test successful temporary unarchiving of a channel."""
    # Mock dependencies
    mock_archive_ops = Mock()
    # Channel is archived
    mock_archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": True}}
    )
    mock_archive_ops.unarchive_channel = AsyncMock(return_value=True)

    mock_dynamodb = Mock()
    mock_dynamodb.update_channel_fields = AsyncMock()

    mock_bot_membership_ops = Mock()
    mock_bot_membership_ops.check_bot_channel_membership = AsyncMock(return_value=True)

    mock_secrets_manager = Mock()
    mock_secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="U12345")

    # Create handler
    handler = JiraReporterArchiveHandler(
        archive_ops=mock_archive_ops,
        dynamodb_store=mock_dynamodb,
        bot_membership_ops=mock_bot_membership_ops,
        secrets_manager=mock_secrets_manager,
    )

    # Test unarchive
    result = await handler.temporarily_unarchive_channel("C12345678")

    # Verify
    assert result is True
    mock_archive_ops.get_channel_info.assert_called_once_with("C12345678")
    mock_archive_ops.unarchive_channel.assert_called_once_with("C12345678")
    mock_dynamodb.update_channel_fields.assert_called_once()

    # Check DB update args
    update_args = mock_dynamodb.update_channel_fields.call_args[1]
    assert update_args["channel_id"] == "C12345678"
    assert update_args["updates"]["archived"] is False
    assert update_args["updates"]["temporary_unarchive"] is True
    assert update_args["updates"]["unarchive_reason"] == "jira_reporter_processing"
    assert "unarchive_timestamp" in update_args["updates"]
    assert "temp_unarchive_expiry" in update_args["updates"]


@pytest.mark.asyncio
async def test_temporarily_unarchive_channel_already_unarchived():
    """Test handling of already unarchived channel."""
    # Mock dependencies
    mock_archive_ops = Mock()
    # Channel is already unarchived
    mock_archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": False}}
    )

    mock_dynamodb = Mock()

    mock_bot_membership_ops = Mock()
    mock_secrets_manager = Mock()

    # Create handler
    handler = JiraReporterArchiveHandler(
        archive_ops=mock_archive_ops,
        dynamodb_store=mock_dynamodb,
        bot_membership_ops=mock_bot_membership_ops,
        secrets_manager=mock_secrets_manager,
    )

    # Test unarchive
    result = await handler.temporarily_unarchive_channel("C12345678")

    # Should still return True
    assert result is True


@pytest.mark.asyncio
async def test_rearchive_channel_success():
    """Test successful re-archiving of a channel."""
    # Mock dependencies
    mock_archive_ops = Mock()
    # Channel is unarchived
    mock_archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": False}}
    )
    mock_archive_ops.archive_channel = AsyncMock(return_value=True)

    mock_dynamodb = Mock()
    # Mock channel data with archived_at timestamp
    mock_dynamodb.get_channel_details = AsyncMock(return_value={"archived_at": 1234567890})
    mock_dynamodb.update_channel_fields = AsyncMock()

    mock_bot_membership_ops = Mock()
    mock_secrets_manager = Mock()

    # Create handler
    handler = JiraReporterArchiveHandler(
        archive_ops=mock_archive_ops,
        dynamodb_store=mock_dynamodb,
        bot_membership_ops=mock_bot_membership_ops,
        secrets_manager=mock_secrets_manager,
    )

    # Test rearchive
    result = await handler.rearchive_channel("C12345678")

    # Verify
    assert result is True
    mock_archive_ops.get_channel_info.assert_called_once_with("C12345678")
    # Should call archive_channel with skip_status_check=True
    mock_archive_ops.archive_channel.assert_called_once_with(
        user_id=None,
        channel_id="C12345678",
        incoming_channel=None,
        skip_status_check=True,
    )
    mock_dynamodb.update_channel_fields.assert_called_once()

    # Check DB update args
    update_args = mock_dynamodb.update_channel_fields.call_args[1]
    assert update_args["channel_id"] == "C12345678"
    assert update_args["updates"]["archived"] is True
    assert update_args["updates"]["temporary_unarchive"] is False
    assert "rearchive_timestamp" in update_args["updates"]
    # Verify original archived_at is restored
    assert update_args["updates"]["archived_at"] == 1234567890


@pytest.mark.asyncio
async def test_cleanup_stale_unarchives():
    """Test cleanup of stale unarchived channels."""
    # Mock dependencies
    mock_archive_ops = Mock()
    mock_dynamodb = Mock()

    # Set up test data with stale and fresh unarchives
    current_time = int(time.time())
    mock_channels = {
        "C11111111": {  # Stale unarchive
            "temporary_unarchive": True,
            "temp_unarchive_expiry": current_time - 100,  # Expired
        },
        "C22222222": {  # Fresh unarchive
            "temporary_unarchive": True,
            "temp_unarchive_expiry": current_time + 100,  # Not expired
        },
        "C33333333": {"temporary_unarchive": False},  # No temporary unarchive
    }

    mock_dynamodb.get_all_channel_details = AsyncMock(return_value=mock_channels)

    mock_bot_membership_ops = Mock()
    mock_secrets_manager = Mock()

    # Create handler with mocked rearchive
    handler = JiraReporterArchiveHandler(
        archive_ops=mock_archive_ops,
        dynamodb_store=mock_dynamodb,
        bot_membership_ops=mock_bot_membership_ops,
        secrets_manager=mock_secrets_manager,
    )
    handler.rearchive_channel = AsyncMock(return_value=True)

    # Run cleanup
    cleaned_count = await handler.cleanup_stale_unarchives()

    # Verify
    assert cleaned_count == 1
    handler.rearchive_channel.assert_called_once_with("C11111111")


@pytest.mark.asyncio
async def test_is_channel_archived():
    """Test checking if a channel is archived."""
    # Mock dependencies
    mock_archive_ops = Mock()
    mock_archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": True}}
    )

    mock_dynamodb = Mock()
    mock_bot_membership_ops = Mock()
    mock_secrets_manager = Mock()

    # Create handler
    handler = JiraReporterArchiveHandler(
        archive_ops=mock_archive_ops,
        dynamodb_store=mock_dynamodb,
        bot_membership_ops=mock_bot_membership_ops,
        secrets_manager=mock_secrets_manager,
    )

    # Test
    result = await handler.is_channel_archived("C12345678")

    # Verify
    assert result is True
    mock_archive_ops.get_channel_info.assert_called_once_with("C12345678")


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in archive operations."""
    # Mock dependencies with exceptions
    mock_archive_ops = Mock()
    mock_archive_ops.get_channel_info = AsyncMock(side_effect=Exception("API Error"))

    mock_dynamodb = Mock()
    mock_bot_membership_ops = Mock()
    mock_secrets_manager = Mock()

    # Create handler
    handler = JiraReporterArchiveHandler(
        archive_ops=mock_archive_ops,
        dynamodb_store=mock_dynamodb,
        bot_membership_ops=mock_bot_membership_ops,
        secrets_manager=mock_secrets_manager,
    )

    # Test - should handle exception and return False
    result = await handler.temporarily_unarchive_channel("C12345678")
    assert result is False


@pytest.mark.asyncio
async def test_rearchive_channel_already_archived():
    """Test handling of already archived channel."""
    # Mock dependencies
    mock_archive_ops = Mock()
    # Channel is already archived
    mock_archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": True}}
    )

    mock_dynamodb = Mock()
    mock_dynamodb.get_channel_details = AsyncMock(return_value={"archived_at": 1234567890})
    mock_dynamodb.update_channel_fields = AsyncMock()

    mock_bot_membership_ops = Mock()
    mock_secrets_manager = Mock()

    # Create handler
    handler = JiraReporterArchiveHandler(
        archive_ops=mock_archive_ops,
        dynamodb_store=mock_dynamodb,
        bot_membership_ops=mock_bot_membership_ops,
        secrets_manager=mock_secrets_manager,
    )

    # Test rearchive
    result = await handler.rearchive_channel("C12345678")

    # Should return True without calling archive
    assert result is True
    mock_archive_ops.get_channel_info.assert_called_once_with("C12345678")
    mock_archive_ops.archive_channel.assert_not_called()
    # But should still update DB state
    mock_dynamodb.update_channel_fields.assert_called_once()


@pytest.mark.asyncio
async def test_skip_status_check_optimization():
    """Test that skip_status_check parameter prevents redundant API calls."""
    # Mock dependencies
    mock_archive_ops = Mock()
    # Channel is unarchived
    mock_archive_ops.get_channel_info = AsyncMock(
        return_value={"ok": True, "channel": {"is_archived": False}}
    )

    # Track calls to check_channel_archived
    check_channel_archived_called = False

    async def mock_check_channel_archived(channel_id):
        nonlocal check_channel_archived_called
        check_channel_archived_called = True
        return False  # Channel is not archived

    mock_archive_ops.check_channel_archived = AsyncMock(side_effect=mock_check_channel_archived)
    mock_archive_ops.archive_channel = AsyncMock(return_value=True)

    mock_dynamodb = Mock()
    mock_dynamodb.get_channel_details = AsyncMock(return_value={"archived_at": 1234567890})
    mock_dynamodb.update_channel_fields = AsyncMock()

    mock_bot_membership_ops = Mock()
    mock_secrets_manager = Mock()

    # Create handler
    handler = JiraReporterArchiveHandler(
        archive_ops=mock_archive_ops,
        dynamodb_store=mock_dynamodb,
        bot_membership_ops=mock_bot_membership_ops,
        secrets_manager=mock_secrets_manager,
    )

    # Test rearchive which should use skip_status_check=True
    result = await handler.rearchive_channel("C12345678")

    # Verify
    assert result is True
    # Should have called get_channel_info to check status
    mock_archive_ops.get_channel_info.assert_called_once_with("C12345678")
    # Should have called archive_channel with skip_status_check=True
    mock_archive_ops.archive_channel.assert_called_once_with(
        user_id=None,
        channel_id="C12345678",
        incoming_channel=None,
        skip_status_check=True,
    )
    # check_channel_archived should NOT have been called because skip_status_check=True
    assert not check_channel_archived_called
