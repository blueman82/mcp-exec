"""
test_archive_command.py

Unit tests for SlackArchiveCommand in packages.slack.command_processing.archive_command.

Covers:
- process_archive_params: valid, no archived channels, and error cases
- Error handling, dependency calls, and async patterns
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock

import pytest

from packages.slack.command_processing.archive_command import SlackArchiveCommand
from packages.slack.command_processing.command_parameters.models import (
    ArchiveCommandParams,
    CommandContext,
    CommandType,
)


@pytest.mark.asyncio
@pytest.mark.unit
class TestSlackArchiveCommand:
    """Unit tests for SlackArchiveCommand.process_archive_params.

    Tests valid, no archived channels, and error scenarios for the /ketchup archive command.
    """

    @pytest.fixture(autouse=True)
    def setup_handler(self) -> None:
        """Set up a SlackArchiveCommand with all dependencies mocked."""
        self.channel_info_ops = AsyncMock()
        self.slack_posting_handler = AsyncMock()
        self.archive_ops = AsyncMock()
        self.dynamodb_store = AsyncMock()
        self.block_kit_builder = AsyncMock()
        self.channel_restore_ops = AsyncMock()
        self.user_store = AsyncMock()
        self.user_store.get_user = AsyncMock()
        self.handler = SlackArchiveCommand(
            channel_info_ops=self.channel_info_ops,
            slack_posting_handler=self.slack_posting_handler,
            archive_ops=self.archive_ops,
            dynamodb_store=self.dynamodb_store,
            block_kit_builder=self.block_kit_builder,
            channel_restore_ops=self.channel_restore_ops,
            user_store=self.user_store,
        )

    @pytest.mark.asyncio
    async def test_process_archive_params_valid(self) -> None:
        """Test process_archive_params with valid ArchiveCommandParams.

        Expects correct calls to dependencies and summary block kit sent.
        """
        params = ArchiveCommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C123",
            command_text="archive",
            response_url="https://slack.com/response",
            command_type=CommandType.ARCHIVE,
            original_command="/ketchup archive",
            context=CommandContext.DIRECT_MESSAGE,
            archive_days=7,
        )
        user_id = "U123"
        incoming_channel = "C123"
        response_url = "https://slack.com/response"
        # Mock archived channels
        self.dynamodb_store.get_all_channel_details.return_value = {
            "C1": {
                "channel_name": "chan1",
                "customer_name": "cust1",
                "jira_ticket": "J1",
                "archived_at": 123,
            },
            "C2": {
                "channel_name": "chan2",
                "customer_name": "cust2",
                "jira_ticket": "J2",
                "archived_at": 456,
            },
        }
        await self.handler.process_archive_params(params, user_id, incoming_channel, response_url)
        self.slack_posting_handler.post_message.assert_any_await(
            user_id=user_id,
            channel_id=incoming_channel,
            message="Retrieving archived channels from the last 7 days... :mag:",
            response_url=response_url,
        )
        self.block_kit_builder.send_ketchup_archive_block_kit.assert_awaited()

    @pytest.mark.asyncio
    async def test_process_archive_params_no_archived_channels(self) -> None:
        """Test process_archive_params when no archived channels are found.

        Expects a message to the user about no archived channels.
        """
        params = ArchiveCommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C123",
            command_text="archive",
            response_url="https://slack.com/response",
            command_type=CommandType.ARCHIVE,
            original_command="/ketchup archive",
            context=CommandContext.DIRECT_MESSAGE,
            archive_days=3,
        )
        user_id = "U123"
        incoming_channel = "C123"
        response_url = "https://slack.com/response"
        self.dynamodb_store.get_all_channel_details.return_value = {}
        await self.handler.process_archive_params(params, user_id, incoming_channel, response_url)
        self.slack_posting_handler.post_message.assert_any_await(
            user_id=user_id,
            channel_id=incoming_channel,
            message="No archived channels found.",
            response_url=response_url,
        )
        self.block_kit_builder.send_ketchup_archive_block_kit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_process_archive_params_error(self) -> None:
        """Test process_archive_params when an exception is raised.

        Expects an error message to be sent to the user.
        """
        params = ArchiveCommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C123",
            command_text="archive",
            response_url="https://slack.com/response",
            command_type=CommandType.ARCHIVE,
            original_command="/ketchup archive",
            context=CommandContext.DIRECT_MESSAGE,
            archive_days=5,
        )
        user_id = "U123"
        incoming_channel = "C123"
        response_url = "https://slack.com/response"
        self.dynamodb_store.get_all_channel_details.side_effect = Exception("fail!")
        await self.handler.process_archive_params(params, user_id, incoming_channel, response_url)
        self.slack_posting_handler.post_message.assert_any_await(
            user_id=user_id,
            channel_id=incoming_channel,
            message="Error processing archive request: fail!",
            response_url=response_url,
        )
