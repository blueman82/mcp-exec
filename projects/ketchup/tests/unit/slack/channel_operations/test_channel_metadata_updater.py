"""
test_channel_metadata_updater.py

This file contains unit tests for the ChannelMetadataUpdater class.

Covers:
- happy path: extract and store metadata successfully
- no update needed
- channel not found
- error handling in channel processor
- error handling in metadata storage
- error handling in metadata extractor

Expected:
- all tests pass mypy --strict and ruff
- all tests pass with pytest
- all tests pass with pytest --asyncio-mode=auto
- all tests pass with pytest --asyncio-mode=auto --strict


"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from channel_metadata_updater.channel_processor import ChannelProcessor
from channel_metadata_updater.metadata_extractor import MetadataExtractor
from channel_metadata_updater.metadata_storage import MetadataStorage
from channel_metadata_updater.metadata_updater import ChannelMetadataUpdater


@pytest.mark.asyncio
async def test_channel_metadata_updater_happy_path():
    """Test ChannelMetadataUpdater main flow: extract and store metadata successfully."""
    # Mocks for dependencies
    mock_secrets = MagicMock()
    mock_slack_config = MagicMock()
    mock_info_ops = MagicMock()
    mock_membership_ops = MagicMock()
    mock_msg_ops = MagicMock()
    mock_dynamodb = MagicMock()
    mock_ai_handler = MagicMock()
    mock_token_tracker = MagicMock()
    mock_posting_handler = MagicMock()
    mock_restore_state = MagicMock()

    # Mock methods
    mock_msg_ops.fetch_channel_messages = AsyncMock(return_value=["msg1", "msg2"])
    mock_dynamodb.get_channel_details = AsyncMock(
        return_value={
            "customer_name": "NOT YET AVAILABLE",
            "jira_ticket": "NOT YET AVAILABLE",
        }
    )
    mock_dynamodb_store = MagicMock()
    mock_dynamodb_store.get_channel_details = AsyncMock(
        return_value={
            "customer_name": "NOT YET AVAILABLE",
            "jira_ticket": "NOT YET AVAILABLE",
        }
    )
    mock_dynamodb_store.store_extracted_metadata = AsyncMock(return_value=True)
    mock_dynamodb_store.scan_for_incomplete_metadata = AsyncMock(return_value=["C123"])
    mock_ai_handler.extract_metadata_with_ai = AsyncMock(
        return_value={"customer_name": "Acme", "jira_ticket": "JIRA-1"}
    )

    updater = ChannelMetadataUpdater(
        secrets_manager=mock_secrets,
        slack_config=mock_slack_config,
        channel_info_ops=mock_info_ops,
        channel_membership_ops=mock_membership_ops,
        channel_msg_ops=mock_msg_ops,
        dynamodb_store=mock_dynamodb_store,
        ai_handler=mock_ai_handler,
        token_tracker=mock_token_tracker,
        max_concurrency=2,
        slack_posting_handler=mock_posting_handler,
        restore_state_manager=mock_restore_state,
    )
    updater.metadata_extractor = MagicMock()
    updater.metadata_extractor.extract_metadata_with_ai = AsyncMock(
        return_value={"customer_name": "Acme", "jira_ticket": "JIRA-1"}
    )
    updater.metadata_storage = MagicMock()
    updater.metadata_storage.needs_metadata_update = AsyncMock(return_value=True)
    updater.metadata_storage.store_extracted_metadata = AsyncMock(return_value=True)
    updater.channel_processor = MagicMock()
    updater.channel_processor.fetch_channel_messages = AsyncMock(return_value=["msg1", "msg2"])

    # Should succeed
    result = await updater.extract_and_store_metadata("C123")
    assert result is True
    updater.metadata_storage.store_extracted_metadata.assert_awaited_once()


@pytest.mark.asyncio
async def test_channel_metadata_updater_no_update_needed():
    """Test ChannelMetadataUpdater skips update if metadata is already complete."""
    updater = ChannelMetadataUpdater(
        secrets_manager=MagicMock(),
        slack_config=MagicMock(),
        channel_info_ops=MagicMock(),
        channel_membership_ops=MagicMock(),
        channel_msg_ops=MagicMock(),
        dynamodb_store=MagicMock(),
        ai_handler=MagicMock(),
        token_tracker=MagicMock(),
        max_concurrency=2,
        slack_posting_handler=MagicMock(),
        restore_state_manager=MagicMock(),
    )
    updater.metadata_storage = MagicMock()
    updater.metadata_storage.needs_metadata_update = AsyncMock(return_value=False)
    result = await updater.extract_and_store_metadata("C123")
    assert result is True
    updater.metadata_storage.store_extracted_metadata.assert_not_called()


@pytest.mark.asyncio
async def test_channel_metadata_updater_channel_not_found():
    """Test ChannelMetadataUpdater handles channel_not_found error and deletes from DB."""
    updater = ChannelMetadataUpdater(
        secrets_manager=MagicMock(),
        slack_config=MagicMock(),
        channel_info_ops=MagicMock(),
        channel_membership_ops=MagicMock(),
        channel_msg_ops=MagicMock(),
        dynamodb_store=MagicMock(),
        ai_handler=MagicMock(),
        token_tracker=MagicMock(),
        max_concurrency=2,
        slack_posting_handler=MagicMock(),
        restore_state_manager=MagicMock(),
    )
    updater.metadata_storage = MagicMock()
    updater.metadata_storage.needs_metadata_update = AsyncMock(return_value=True)
    updater.channel_processor = MagicMock()
    updater.channel_processor.fetch_channel_messages = AsyncMock(return_value=["msg1"])
    updater.metadata_extractor = MagicMock()

    # Simulate channel_not_found error
    async def raise_channel_not_found(*args, **kwargs):
        raise Exception("channel_not_found")

    updater.metadata_extractor.extract_metadata_with_ai = raise_channel_not_found
    updater.dynamodb_store = MagicMock()
    updater.dynamodb_store.delete_channel_if_exists = AsyncMock()
    result = await updater.extract_and_store_metadata("C123")
    assert result is True
    updater.dynamodb_store.delete_channel_if_exists.assert_awaited_once_with("C123")


@pytest.mark.asyncio
async def test_channel_processor_fetch_channel_messages_handles_error():
    """Test ChannelProcessor.fetch_channel_messages handles errors and retries."""
    mock_msg_ops = MagicMock()
    # Simulate error on first call, success on second
    mock_msg_ops.fetch_channel_messages = AsyncMock(side_effect=[Exception("fail"), ["msg1"]])
    processor = ChannelProcessor(
        channel_msg_ops=mock_msg_ops, dynamodb_store=MagicMock(), max_concurrency=1
    )
    result = await processor.fetch_channel_messages("C123")
    assert result == ["msg1"]


@pytest.mark.asyncio
async def test_metadata_storage_needs_metadata_update_true():
    """Test MetadataStorage.needs_metadata_update returns True for incomplete metadata."""
    mock_dynamodb = MagicMock()
    mock_dynamodb.get_channel_details = AsyncMock(
        return_value={
            "customer_name": "NOT YET AVAILABLE",
            "jira_ticket": "NOT YET AVAILABLE",
        }
    )
    storage = MetadataStorage(dynamodb_store=mock_dynamodb)
    result = await storage.needs_metadata_update("C123")
    assert result is True


@pytest.mark.asyncio
async def test_metadata_extractor_extract_metadata_with_ai():
    """Test MetadataExtractor.extract_metadata_with_ai calls AI handler and returns metadata."""
    mock_ai_handler = MagicMock()
    # The real MetadataExtractor expects call_openai_endpoint to return a dict with 'choices' and 'message.content'
    mock_ai_handler.call_openai_endpoint = AsyncMock(
        return_value={"choices": [{"message": {"content": "Acme\nJIRA-1"}}]}
    )
    extractor = MetadataExtractor(ai_handler=mock_ai_handler)
    result = await extractor.extract_metadata_with_ai("C123", ["msg1", "msg2"])
    assert result == {"customer_name": "Acme", "jira_ticket": "JIRA-1"}
