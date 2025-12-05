"""
test_events_bot_filtering.py

Unit tests for bot message filtering in SlackEventHandler.
"""

from unittest.mock import AsyncMock

import pytest

from packages.slack.channel_events.events import SlackEventHandler


class TestEventsBotFiltering:
    """Test suite for bot message filtering in SlackEventHandler."""

    @pytest.fixture
    def secrets_manager(self):
        """Create mock secrets manager."""
        mock = AsyncMock()
        mock.get_bot_slack_user_id_async = AsyncMock(return_value="U084HFUQMFE")
        return mock

    @pytest.fixture
    def dynamodb_store(self):
        """Create mock DynamoDB store."""
        return AsyncMock()

    @pytest.fixture
    def posting_handler(self):
        """Create mock posting handler."""
        mock = AsyncMock()
        mock.post_message = AsyncMock()
        return mock

    @pytest.fixture
    def channel_info_ops(self):
        """Create mock channel info ops."""
        return AsyncMock()

    @pytest.fixture
    def channel_membership_ops(self):
        """Create mock channel membership ops."""
        return AsyncMock()

    @pytest.fixture
    def channel_restore_ops(self):
        """Create mock channel restore ops."""
        return AsyncMock()

    @pytest.fixture
    def block_kit_builder(self):
        """Create mock block kit builder."""
        return AsyncMock()

    @pytest.fixture
    def channel_eligibility_service(self):
        """Create mock channel eligibility service."""
        return AsyncMock()

    @pytest.fixture
    def event_handler(
        self,
        secrets_manager,
        dynamodb_store,
        posting_handler,
        channel_info_ops,
        channel_membership_ops,
        channel_restore_ops,
        block_kit_builder,
        channel_eligibility_service,
    ):
        """Create a SlackEventHandler instance with mocked dependencies."""
        return SlackEventHandler(
            secrets_manager=secrets_manager,
            dynamodb_store=dynamodb_store,
            posting_handler=posting_handler,
            channel_info_ops=channel_info_ops,
            channel_membership_ops=channel_membership_ops,
            channel_restore_ops=channel_restore_ops,
            block_kit_builder=block_kit_builder,
            channel_eligibility_service=channel_eligibility_service,
        )

    @pytest.mark.asyncio
    async def test_handle_message_filters_bot_user(self, event_handler, posting_handler):
        """Test that messages from the bot itself are filtered out."""
        # Create event from bot
        event = {
            "type": "message",
            "user": "U084HFUQMFE",  # Bot's user ID
            "text": "Some response from bot",
            "channel": "C123456",
        }

        # Handle the event
        await event_handler.handle_message(event)

        # Verify no message was posted (bot's own messages are filtered)
        posting_handler.post_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_filters_bot_id(self, event_handler, posting_handler):
        """Test that messages with bot_id are filtered out."""
        # Create event with bot_id
        event = {
            "type": "message",
            "user": "U123456",  # Different user
            "bot_id": "B084ETPM1FV",  # Has bot_id
            "text": "Message from a bot",
            "channel": "C123456",
        }

        # Handle the event
        await event_handler.handle_message(event)

        # Verify no message was posted (bot messages are filtered)
        posting_handler.post_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_processes_user_mention(self, event_handler, posting_handler):
        """Test that regular user messages with bot mention are logged."""
        # Create event from regular user mentioning bot
        event = {
            "type": "message",
            "user": "U123456",  # Regular user
            "text": "<@U084HFUQMFE> analyze something",  # Mentions bot
            "channel": "C123456",
        }

        # Handle the event - should log the mention but not post a message
        await event_handler.handle_message(event)

        # Current implementation just logs mentions, doesn't post responses
        # Verify no automatic response is posted
        posting_handler.post_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_im_filters_bot_user(self, event_handler, posting_handler):
        """Test that DMs from the bot itself are filtered out."""
        # Create DM event from bot
        event = {
            "type": "message",
            "user": "U084HFUQMFE",  # Bot's user ID
            "text": "Some response from bot",
            "channel": "D123456",
        }

        # Handle the event
        await event_handler.handle_message_im(event)

        # Verify no message was posted (bot's own messages are filtered)
        posting_handler.post_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_im_filters_bot_id(self, event_handler, posting_handler):
        """Test that DMs with bot_id are filtered out."""
        # Create DM event with bot_id
        event = {
            "type": "message",
            "user": "U123456",  # Different user
            "bot_id": "B084ETPM1FV",  # Has bot_id
            "text": "DM from a bot",
            "channel": "D123456",
        }

        # Handle the event
        await event_handler.handle_message_im(event)

        # Verify no message was posted (bot messages are filtered)
        posting_handler.post_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_im_processes_user_message(self, event_handler, posting_handler):
        """Test that regular user DMs are processed."""
        # Create DM event from regular user
        event = {
            "type": "message",
            "user": "U123456",  # Regular user
            "text": "Help me with something",
            "channel": "D123456",
        }

        # Handle the event
        await event_handler.handle_message_im(event)

        # Verify a message WAS posted directing users to slash commands
        posting_handler.post_message.assert_called_once_with(
            channel_id="D123456",
            message="Thanks for your message! Please use `/ketchup` to see available commands.",
        )

    @pytest.mark.asyncio
    async def test_handle_message_im_filters_ketchup_generated(
        self, event_handler, posting_handler
    ):
        """Test that Ketchup-generated messages are filtered in DMs."""
        # Create DM event with Ketchup marker
        event = {
            "type": "message",
            "user": "U123456",  # Regular user
            "text": "Generated by Ketchup - some response",
            "channel": "D123456",
        }

        # Handle the event
        await event_handler.handle_message_im(event)

        # Verify no message was posted (Ketchup-generated messages are filtered)
        posting_handler.post_message.assert_not_called()
