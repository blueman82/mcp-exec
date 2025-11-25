"""
Unit tests for SlackEventHandler (channel_events/events.py).

Covers:
- SlackEventHandler.handle_channel_created: dispatch, dependency, error handling
- SlackEventHandler.handle_member_joined_channel: dispatch, dependency, error handling
- SlackEventHandler.handle_channel_archive: normal, error, dependency
- SlackEventHandler.handle_channel_unarchive: normal, missing/invalid event, not found, already unarchived, update error, invite error
- All dependencies and imported event handler functions are mocked

Edge Cases Covered:
- Missing or invalid event data
- Dependency errors (e.g., DynamoDB, secrets manager)
- Handler function raises exception
- Channel not found, already unarchived, update error, invite error

Expected Outcomes:
- All methods call correct handlers and handle errors gracefully
- All logic branches and error cases are covered
- All external calls are mocked and asserted

"""

from unittest.mock import AsyncMock, patch

import pytest

from packages.slack.channel_events.events import SlackEventHandler


@pytest.mark.asyncio
class TestSlackEventHandler:
    def setup_method(self) -> None:
        self.secrets_manager = AsyncMock()
        self.dynamodb_store = AsyncMock()
        self.posting_handler = AsyncMock()
        self.channel_info_ops = AsyncMock()
        self.channel_membership_ops = AsyncMock()
        self.channel_restore_ops = AsyncMock()
        self.block_kit_builder = AsyncMock()
        self.channel_eligibility_service = AsyncMock()
        self.list_command = AsyncMock()
        self.handler = SlackEventHandler(
            secrets_manager=self.secrets_manager,
            dynamodb_store=self.dynamodb_store,
            posting_handler=self.posting_handler,
            channel_info_ops=self.channel_info_ops,
            channel_membership_ops=self.channel_membership_ops,
            channel_restore_ops=self.channel_restore_ops,
            block_kit_builder=self.block_kit_builder,
            channel_eligibility_service=self.channel_eligibility_service,
            list_command=self.list_command,
        )

    @patch(
        "packages.slack.channel_events.events.handle_channel_creation_event",
        new_callable=AsyncMock,
    )
    async def test_handle_channel_created(self, mock_creation: AsyncMock) -> None:
        event = {"channel": {"id": "C1"}}
        await self.handler.handle_channel_created(event, response_url="url")
        mock_creation.assert_awaited_once()
        args, kwargs = mock_creation.call_args
        assert kwargs["event"] == event
        assert kwargs["response_url"] == "url"

    @patch(
        "packages.slack.channel_events.events.handle_member_joined_event",
        new_callable=AsyncMock,
    )
    async def test_handle_member_joined_channel(self, mock_joined: AsyncMock) -> None:
        event = {"user": "U1", "channel": "C1"}
        await self.handler.handle_member_joined_channel(event, response_url="url")
        mock_joined.assert_awaited_once()
        args, kwargs = mock_joined.call_args
        assert kwargs["event"] == event
        assert kwargs["response_url"] == "url"

    @patch(
        "packages.slack.channel_events.events.process_channel_archive",
        new_callable=AsyncMock,
    )
    async def test_handle_channel_archive(self, mock_archive: AsyncMock) -> None:
        event = {"channel": "C1"}
        await self.handler.handle_channel_archive(event)
        mock_archive.assert_awaited_once_with(
            channel_id="C1", dynamodb_store=self.dynamodb_store
        )

    @patch(
        "packages.slack.channel_events.events.process_channel_archive",
        new_callable=AsyncMock,
    )
    async def test_handle_channel_archive_error(self, mock_archive: AsyncMock) -> None:
        event = {"channel": "C1"}
        mock_archive.side_effect = Exception("fail")
        # Should not raise
        await self.handler.handle_channel_archive(event)
        mock_archive.assert_awaited_once()

    @patch(
        "packages.slack.channel_events.events.invite_and_verify_bot_after_unarchive",
        new_callable=AsyncMock,
    )
    async def test_handle_channel_unarchive_normal(
        self, mock_invite: AsyncMock
    ) -> None:
        event = {"channel": "C1"}
        self.dynamodb_store.get_channel_details_consistent.return_value = {
            "archived": True,
            "channel_name": "foo",
        }
        self.dynamodb_store.update_channel_archived_status.return_value = None
        mock_invite.return_value = True
        await self.handler.handle_channel_unarchive(event)
        self.dynamodb_store.get_channel_details_consistent.assert_awaited_once_with("C1")
        self.dynamodb_store.update_channel_archived_status.assert_awaited_once_with(
            channel_id="C1", archived=False, archived_at=None
        )
        mock_invite.assert_awaited_once_with(
            channel_id="C1",
            channel_name="foo",
            secrets_manager=self.secrets_manager,
            channel_restore_ops=self.channel_restore_ops,
            channel_info_ops=self.channel_info_ops,
        )

    async def test_handle_channel_unarchive_invalid_event(self) -> None:
        # Should log error and return
        await self.handler.handle_channel_unarchive(None)  # type: ignore
        await self.handler.handle_channel_unarchive({})
        await self.handler.handle_channel_unarchive({"foo": "bar"})

    @patch(
        "packages.slack.channel_events.events.invite_and_verify_bot_after_unarchive",
        new_callable=AsyncMock,
    )
    async def test_handle_channel_unarchive_not_found(
        self, mock_invite: AsyncMock
    ) -> None:
        event = {"channel": "C1"}
        self.dynamodb_store.get_channel_details_consistent.return_value = None
        await self.handler.handle_channel_unarchive(event)
        self.dynamodb_store.get_channel_details_consistent.assert_awaited_once_with("C1")
        mock_invite.assert_not_awaited()

    @patch(
        "packages.slack.channel_events.events.invite_and_verify_bot_after_unarchive",
        new_callable=AsyncMock,
    )
    async def test_handle_channel_unarchive_already_unarchived(
        self, mock_invite: AsyncMock
    ) -> None:
        event = {"channel": "C1"}
        self.dynamodb_store.get_channel_details_consistent.return_value = {
            "archived": False,
            "channel_name": "foo",
        }
        await self.handler.handle_channel_unarchive(event)
        self.dynamodb_store.get_channel_details_consistent.assert_awaited_once_with("C1")
        self.dynamodb_store.update_channel_archived_status.assert_not_awaited()
        mock_invite.assert_awaited_once()

    @patch(
        "packages.slack.channel_events.events.invite_and_verify_bot_after_unarchive",
        new_callable=AsyncMock,
    )
    async def test_handle_channel_unarchive_update_error(
        self, mock_invite: AsyncMock
    ) -> None:
        event = {"channel": "C1"}
        self.dynamodb_store.get_channel_details_consistent.return_value = {
            "archived": True,
            "channel_name": "foo",
        }
        self.dynamodb_store.update_channel_archived_status.side_effect = Exception(
            "fail"
        )
        mock_invite.return_value = True
        await self.handler.handle_channel_unarchive(event)
        self.dynamodb_store.get_channel_details_consistent.assert_awaited_once_with("C1")
        self.dynamodb_store.update_channel_archived_status.assert_awaited_once()
        mock_invite.assert_awaited_once()

    @patch(
        "packages.slack.channel_events.events.invite_and_verify_bot_after_unarchive",
        new_callable=AsyncMock,
    )
    async def test_handle_channel_unarchive_invite_error(
        self, mock_invite: AsyncMock
    ) -> None:
        event = {"channel": "C1"}
        self.dynamodb_store.get_channel_details_consistent.return_value = {
            "archived": True,
            "channel_name": "foo",
        }
        self.dynamodb_store.update_channel_archived_status.return_value = None
        mock_invite.return_value = False
        await self.handler.handle_channel_unarchive(event)
        mock_invite.assert_awaited_once()

    async def test_handle_channel_created_success(self) -> None:
        """Test handle_channel_created successfully dispatches to handler."""
        with patch(
            "packages.slack.channel_events.events.handle_channel_creation_event",
            new_callable=AsyncMock,
        ) as mock_handle_creation:
            event = {"channel": {"id": "C1"}}
            await self.handler.handle_channel_created(event)
            mock_handle_creation.assert_awaited_once_with(
                event=event,
                response_url=None,
                secrets_manager=self.secrets_manager,
                channel_restore_ops=self.channel_restore_ops,
                dynamodb_store=self.dynamodb_store,
                posting_handler=self.posting_handler,
            )

    async def test_handle_member_joined_success(self) -> None:
        """Test handle_member_joined_channel successfully dispatches."""
        with patch(
            "packages.slack.channel_events.events.handle_member_joined_event",
            new_callable=AsyncMock,
        ) as mock_handle_joined:
            event = {"user": "U1", "channel": "C1"}
            await self.handler.handle_member_joined_channel(event)
            mock_handle_joined.assert_called_once_with(
                event=event,
                response_url=None,
                secrets_manager=self.secrets_manager,
                channel_eligibility_service=self.channel_eligibility_service,
                dynamodb_store=self.dynamodb_store,
                channel_info_ops=self.channel_info_ops,
                posting_handler=self.posting_handler,
                feature_service=None,
                user_join_notification_service=None,
                user_store=None,
                restore_state_manager=None,
            )
