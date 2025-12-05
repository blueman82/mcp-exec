"""
Unit tests for packages/slack/channel_events/processing/creation_processor.py

Covers:
- process_eligible_channel_creation
- handle_channel_creation_event
- All error and edge cases, including bot invite, metadata storage, eligibility, and error notification.

All dependencies are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.processing.creation_processor as creation_processor


@pytest.mark.asyncio
class TestProcessEligibleChannelCreation:
    @patch("packages.slack.channel_events.processing.creation_processor.ChannelMetadata")
    async def test_successful_invite_and_metadata(self, mock_metadata):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(return_value=True)
        dynamodb_store = MagicMock()
        dynamodb_store.channel_ops.store_metadata = AsyncMock()
        posting_handler = MagicMock()
        await creation_processor.process_eligible_channel_creation(
            channel_id="C1",
            channel_name="chan",
            creator_id="U1",
            event_ts="1234567890",
            response_url=None,
            secrets_manager=secrets_manager,
            channel_restore_ops=channel_restore_ops,
            dynamodb_store=dynamodb_store,
            posting_handler=posting_handler,
        )
        channel_restore_ops.invite_ketchup_to_channel.assert_awaited_once()
        dynamodb_store.channel_ops.store_metadata.assert_awaited_once()
        mock_metadata.assert_called_once()

    async def test_bot_user_id_missing(self):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value=None)
        channel_restore_ops = MagicMock()
        dynamodb_store = MagicMock()
        posting_handler = MagicMock()
        posting_handler.post_message = AsyncMock()
        await creation_processor.process_eligible_channel_creation(
            channel_id="C2",
            channel_name="chan",
            creator_id="U2",
            event_ts="1234567890",
            response_url="url",
            secrets_manager=secrets_manager,
            channel_restore_ops=channel_restore_ops,
            dynamodb_store=dynamodb_store,
            posting_handler=posting_handler,
        )
        posting_handler.post_message.assert_awaited_once()

    async def test_invite_failed(self):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(return_value=False)
        dynamodb_store = MagicMock()
        posting_handler = MagicMock()
        await creation_processor.process_eligible_channel_creation(
            channel_id="C3",
            channel_name="chan",
            creator_id="U3",
            event_ts="1234567890",
            response_url=None,
            secrets_manager=secrets_manager,
            channel_restore_ops=channel_restore_ops,
            dynamodb_store=dynamodb_store,
            posting_handler=posting_handler,
        )
        channel_restore_ops.invite_ketchup_to_channel.assert_awaited_once()
        # Should not call store_metadata
        assert not dynamodb_store.channel_ops.store_metadata.called

    @patch("packages.slack.channel_events.processing.creation_processor.ChannelMetadata")
    async def test_metadata_storage_error(self, mock_metadata):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(return_value=True)
        dynamodb_store = MagicMock()
        dynamodb_store.channel_ops.store_metadata = AsyncMock(side_effect=Exception("fail"))
        posting_handler = MagicMock()
        posting_handler.post_message = AsyncMock()
        await creation_processor.process_eligible_channel_creation(
            channel_id="C4",
            channel_name="chan",
            creator_id="U4",
            event_ts="1234567890",
            response_url="url",
            secrets_manager=secrets_manager,
            channel_restore_ops=channel_restore_ops,
            dynamodb_store=dynamodb_store,
            posting_handler=posting_handler,
        )
        posting_handler.post_message.assert_awaited_once()

    @patch("packages.slack.channel_events.processing.creation_processor.ChannelMetadata")
    async def test_event_ts_parse_error(self, mock_metadata):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(return_value=True)
        dynamodb_store = MagicMock()
        dynamodb_store.channel_ops.store_metadata = AsyncMock()
        posting_handler = MagicMock()
        await creation_processor.process_eligible_channel_creation(
            channel_id="C5",
            channel_name="chan",
            creator_id="U5",
            event_ts="bad",
            response_url=None,
            secrets_manager=secrets_manager,
            channel_restore_ops=channel_restore_ops,
            dynamodb_store=dynamodb_store,
            posting_handler=posting_handler,
        )
        dynamodb_store.channel_ops.store_metadata.assert_awaited_once()

    async def test_outer_exception(self):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_restore_ops = MagicMock()
        channel_restore_ops.invite_ketchup_to_channel = AsyncMock(side_effect=Exception("fail"))
        dynamodb_store = MagicMock()
        posting_handler = MagicMock()
        posting_handler.post_message = AsyncMock()
        await creation_processor.process_eligible_channel_creation(
            channel_id="C6",
            channel_name="chan",
            creator_id="U6",
            event_ts="1234567890",
            response_url="url",
            secrets_manager=secrets_manager,
            channel_restore_ops=channel_restore_ops,
            dynamodb_store=dynamodb_store,
            posting_handler=posting_handler,
        )
        posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
class TestHandleChannelCreationEvent:
    @patch(
        "packages.slack.channel_events.processing.creation_processor.is_new_channel_eligible",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.channel_events.processing.creation_processor.process_eligible_channel_creation",
        new_callable=AsyncMock,
    )
    async def test_eligible_channel(self, mock_process, mock_eligible):
        mock_eligible.return_value = True
        event = {
            "channel": {"id": "C1", "name": "chan", "creator": "U1"},
            "event_ts": "1234567890",
        }
        secrets_manager = MagicMock()
        channel_restore_ops = MagicMock()
        dynamodb_store = MagicMock()
        posting_handler = MagicMock()
        await creation_processor.handle_channel_creation_event(
            event,
            "url",
            secrets_manager,
            channel_restore_ops,
            dynamodb_store,
            posting_handler,
        )
        mock_process.assert_awaited_once()

    @patch(
        "packages.slack.channel_events.processing.creation_processor.is_new_channel_eligible",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.channel_events.processing.creation_processor.process_eligible_channel_creation",
        new_callable=AsyncMock,
    )
    async def test_ineligible_channel(self, mock_process, mock_eligible):
        mock_eligible.return_value = False
        event = {
            "channel": {"id": "C2", "name": "chan", "creator": "U2"},
            "event_ts": "1234567890",
        }
        secrets_manager = MagicMock()
        channel_restore_ops = MagicMock()
        dynamodb_store = MagicMock()
        posting_handler = MagicMock()
        await creation_processor.handle_channel_creation_event(
            event,
            "url",
            secrets_manager,
            channel_restore_ops,
            dynamodb_store,
            posting_handler,
        )
        mock_process.assert_not_awaited()

    async def test_missing_channel_info(self):
        event = {"channel": {"id": "C3"}, "event_ts": "1234567890"}
        secrets_manager = MagicMock()
        channel_restore_ops = MagicMock()
        dynamodb_store = MagicMock()
        posting_handler = MagicMock()
        await creation_processor.handle_channel_creation_event(
            event,
            "url",
            secrets_manager,
            channel_restore_ops,
            dynamodb_store,
            posting_handler,
        )

    @patch(
        "packages.slack.channel_events.processing.creation_processor.is_new_channel_eligible",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.channel_events.processing.creation_processor.process_eligible_channel_creation",
        new_callable=AsyncMock,
    )
    async def test_outer_exception_and_notify(self, mock_process, mock_eligible):
        mock_eligible.return_value = True
        event = {
            "channel": {"id": "C4", "name": "chan", "creator": "U4"},
            "event_ts": "1234567890",
        }
        secrets_manager = MagicMock()
        channel_restore_ops = MagicMock()
        dynamodb_store = MagicMock()
        posting_handler = MagicMock()
        posting_handler.post_message = AsyncMock()
        mock_process.side_effect = Exception("fail")
        await creation_processor.handle_channel_creation_event(
            event,
            "url",
            secrets_manager,
            channel_restore_ops,
            dynamodb_store,
            posting_handler,
        )
        posting_handler.post_message.assert_awaited_once()
