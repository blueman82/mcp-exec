"""
test_query_command.py

Unit tests for SlackQueryHandler in packages.slack.command_processing.query_command.

Covers:
- process_query_request: valid, invalid, and edge-case command parameters
- Channel parameter resolution functionality
- Error handling, dependency calls, and async patterns
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.channel_events.models import ProcessingResult
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandParams,
    CommandType,
    QueryCommandParams,
)
from packages.slack.command_processing.query_command import SlackQueryHandler


@pytest.mark.asyncio
@pytest.mark.unit
class TestSlackQueryHandler:
    """Unit tests for SlackQueryHandler.process_query_request.

    Tests valid, invalid, and edge-case scenarios for the /ketchup query command.
    """

    @pytest.fixture(autouse=True)
    def setup_handler(self) -> None:
        """Set up a SlackQueryHandler with all dependencies mocked."""
        self.channel_info_ops = AsyncMock()
        self.channel_info_ops.get_channel_details.return_value = (
            "chan-name",
            True,
            None,
            None,
        )
        self.archive_ops = AsyncMock()
        self.openai_handler = AsyncMock()
        self.block_kit_builder = AsyncMock()
        self.channel_message_ops = AsyncMock()
        self.slack_posting_handler = AsyncMock()
        self.user_store = AsyncMock()
        self.slack_config = AsyncMock()
        self.secrets_manager = AsyncMock()
        self.user_ops = AsyncMock()
        self.channel_restore_ops = MagicMock()
        # Fix mock return value for the decorator
        self.channel_restore_ops.restore_archived_channel = AsyncMock(return_value=(True, False))
        self.handler = SlackQueryHandler(
            channel_info_ops=self.channel_info_ops,
            archive_ops=self.archive_ops,
            openai_handler=self.openai_handler,
            block_kit_builder=self.block_kit_builder,
            channel_message_ops=self.channel_message_ops,
            slack_posting_handler=self.slack_posting_handler,
            user_store=self.user_store,
            slack_config=self.slack_config,
            secrets_manager=self.secrets_manager,
            user_ops=self.user_ops,
            channel_restore_ops=self.channel_restore_ops,
        )

    @pytest.mark.asyncio
    async def test_process_query_request_valid(self) -> None:
        """Test process_query_request with valid parameters and successful processing.

        Expects a success response and correct calls to dependencies.
        """
        params = QueryCommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C1",
            command_text="query C1 test query",
            response_url="https://slack.com/response",
            command_type=CommandType.QUERY,
            context=CommandContext.PUBLIC_CHANNEL,
            query_text="test query",
            original_command="/ketchup query C1 test query",
            target_channel_id="C1",
        )
        with patch.object(
            self.handler,
            "_process_query",
            new_callable=AsyncMock,
            return_value="Generated Text",
        ) as mock_process_query:
            result = await self.handler.process_query_request(
                params=params,
                user_id="U1",
                channel_id="C1",
                dm_channel_id="D1",
                response_url="http://response.url",
            )
        assert isinstance(result, ProcessingResult)
        assert result.status_code == 200
        mock_process_query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_query_request_invalid_params(self) -> None:
        """Test process_query_request with invalid params type.

        Expects a validation error response and no query processing.
        """
        params = CommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C123",
            command_text="query",
            response_url="https://slack.com/response",
            command_type=CommandType.QUERY,
            original_command="/ketchup query",
            context=CommandContext.DIRECT_MESSAGE,
        )
        user_id = "U123"
        with patch.object(self.handler, "_process_query", new_callable=AsyncMock) as mock_proc:
            result = await self.handler.process_query_request(params, user_id)
            assert result is not None
            assert isinstance(result, ProcessingResult)
            assert result.status_code == 400
            mock_proc.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_query_request_missing_messaging_channel(self) -> None:
        """Test process_query_request when no messaging channel is provided.

        Expects an error response about missing messaging channel.
        """
        params = QueryCommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C1",
            command_text="query C1 test query",
            response_url="https://slack.com/response",
            command_type=CommandType.QUERY,
            context=CommandContext.PUBLIC_CHANNEL,
            query_text="test query",
            original_command="/ketchup query C1 test query",
            target_channel_id="C1",
        )
        result = await self.handler.process_query_request(
            params=params,
            user_id="U1",
            channel_id="C1",
            dm_channel_id=None,
            incoming_channel=None,
            response_url="http://response.url",
        )
        assert isinstance(result, ProcessingResult)
        assert result.status_code == 500
        assert "No messaging channel provided" in result.body

    @pytest.mark.asyncio
    async def test_process_query_request_process_query_raises(self) -> None:
        """Test process_query_request when _process_query raises an exception.

        Expects an error response and error message in the response.
        """
        params = QueryCommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C1",
            command_text="query C1 test query",
            response_url="https://slack.com/response",
            command_type=CommandType.QUERY,
            context=CommandContext.PUBLIC_CHANNEL,
            query_text="test query",
            original_command="/ketchup query C1 test query",
            target_channel_id="C1",
        )
        with patch.object(
            self.handler, "_process_query", new_callable=AsyncMock
        ) as mock_process_query:
            mock_process_query.side_effect = Exception("test error")
            result = await self.handler.process_query_request(
                params=params,
                user_id="U1",
                channel_id="C1",
                dm_channel_id="D1",
                response_url="http://response.url",
            )
        assert isinstance(result, ProcessingResult)
        assert result.status_code == 500
        assert "test error" in result.body


@pytest.mark.asyncio
@pytest.mark.unit
class TestSlackQueryHandlerChannelResolution:
    """Unit tests for SlackQueryHandler channel resolution functionality."""

    @pytest.fixture(autouse=True)
    def setup_handler(self) -> None:
        """Set up a SlackQueryHandler with all dependencies mocked."""
        self.channel_info_ops = AsyncMock()
        self.channel_info_ops.get_channel_details.return_value = (
            "chan-name",
            True,
            None,
            None,
        )
        self.archive_ops = AsyncMock()
        self.openai_handler = AsyncMock()
        self.block_kit_builder = AsyncMock()
        self.channel_message_ops = AsyncMock()
        self.slack_posting_handler = AsyncMock()
        self.user_store = AsyncMock()
        self.slack_config = AsyncMock()
        self.secrets_manager = AsyncMock()
        self.user_ops = AsyncMock()
        self.channel_restore_ops = MagicMock()
        self.channel_restore_ops.restore_archived_channel = AsyncMock(return_value=(True, False))
        self.handler = SlackQueryHandler(
            channel_info_ops=self.channel_info_ops,
            archive_ops=self.archive_ops,
            openai_handler=self.openai_handler,
            block_kit_builder=self.block_kit_builder,
            channel_message_ops=self.channel_message_ops,
            slack_posting_handler=self.slack_posting_handler,
            user_store=self.user_store,
            slack_config=self.slack_config,
            secrets_manager=self.secrets_manager,
            user_ops=self.user_ops,
            channel_restore_ops=self.channel_restore_ops,
        )

    @pytest.mark.asyncio
    async def test_channel_mention_resolution_success(self) -> None:
        """Test successful resolution of channel mention to channel ID."""
        mention = "<#C1234567890|general>"
        resolved_id = "C1234567890"

        params = QueryCommandParams(
            user_id="U1",
            user_name="testuser",
            channel_id=mention,
            command_text=f"query {mention} test query",
            response_url="http://response.url",
            command_type=CommandType.QUERY,
            context=CommandContext.DIRECT_MESSAGE,
            query_text="test query",
            original_command=f"/ketchup query {mention} test query",
            target_channel_id=mention,
        )

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                resolved_id,
                "channel_mention",
            )
            mock_registry = MagicMock()
            mock_registry.aget = AsyncMock(return_value=mock_resolver)
            mock_get_registry.return_value = mock_registry

            with patch.object(
                self.handler,
                "_process_query",
                new_callable=AsyncMock,
                return_value="Generated Text",
            ):
                result = await self.handler.process_query_request(
                    params=params,
                    user_id="U1",
                    channel_id=mention,
                    dm_channel_id="D1",
                    response_url="http://response.url",
                )

            assert isinstance(result, ProcessingResult)
            assert result.status_code == 200
            mock_resolver.resolve_channel_parameter.assert_awaited_with(mention)

    @pytest.mark.asyncio
    async def test_channel_name_resolution_success(self) -> None:
        """Test successful resolution of channel name to channel ID."""
        channel_name = "#general"
        resolved_id = "C1234567890"

        params = QueryCommandParams(
            user_id="U1",
            user_name="testuser",
            channel_id=channel_name,
            command_text=f"query {channel_name} test query",
            response_url="http://response.url",
            command_type=CommandType.QUERY,
            context=CommandContext.DIRECT_MESSAGE,
            query_text="test query",
            original_command=f"/ketchup query {channel_name} test query",
            target_channel_id=channel_name,
        )

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                resolved_id,
                "channel_name",
            )
            mock_registry = MagicMock()
            mock_registry.aget = AsyncMock(return_value=mock_resolver)
            mock_get_registry.return_value = mock_registry

            with patch.object(
                self.handler,
                "_process_query",
                new_callable=AsyncMock,
                return_value="Generated Text",
            ):
                result = await self.handler.process_query_request(
                    params=params,
                    user_id="U1",
                    channel_id=channel_name,
                    dm_channel_id="D1",
                    response_url="http://response.url",
                )

            assert isinstance(result, ProcessingResult)
            assert result.status_code == 200
            mock_resolver.resolve_channel_parameter.assert_awaited_with(channel_name)

    @pytest.mark.asyncio
    async def test_channel_resolution_failure(self) -> None:
        """Test handling of channel resolution failure."""
        invalid_channel = "#nonexistent"

        params = QueryCommandParams(
            user_id="U1",
            user_name="testuser",
            channel_id=invalid_channel,
            command_text=f"query {invalid_channel} test query",
            response_url="http://response.url",
            command_type=CommandType.QUERY,
            context=CommandContext.DIRECT_MESSAGE,
            query_text="test query",
            original_command=f"/ketchup query {invalid_channel} test query",
            target_channel_id=invalid_channel,
        )

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                None,
                "Channel not found",
            )
            mock_registry = MagicMock()
            mock_registry.aget = AsyncMock(return_value=mock_resolver)
            mock_get_registry.return_value = mock_registry

            result = await self.handler.process_query_request(
                params=params,
                user_id="U1",
                channel_id=invalid_channel,
                dm_channel_id="D1",
                response_url="http://response.url",
            )

            assert isinstance(result, ProcessingResult)
            assert result.status_code == 400
            assert "Could not resolve the specified channel" in result.body
            mock_resolver.resolve_channel_parameter.assert_awaited_with(invalid_channel)

    @pytest.mark.asyncio
    async def test_channel_resolution_unavailable(self) -> None:
        """Test behavior when ChannelNameResolver is not available."""
        channel_param = "<#C1234567890|general>"

        params = QueryCommandParams(
            user_id="U1",
            user_name="testuser",
            channel_id=channel_param,
            command_text=f"query {channel_param} test query",
            response_url="http://response.url",
            command_type=CommandType.QUERY,
            context=CommandContext.DIRECT_MESSAGE,
            query_text="test query",
            original_command=f"/ketchup query {channel_param} test query",
            target_channel_id=channel_param,
        )

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_registry:
            mock_get_registry.return_value = None

            with patch.object(
                self.handler,
                "_process_query",
                new_callable=AsyncMock,
                return_value="Generated Text",
            ):
                result = await self.handler.process_query_request(
                    params=params,
                    user_id="U1",
                    channel_id=channel_param,
                    dm_channel_id="D1",
                    response_url="http://response.url",
                )

            assert isinstance(result, ProcessingResult)
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_real_world_mention_resolution(self) -> None:
        """Test resolution of the real-world mention that caused the original issue."""
        mention = "<#C08U5S51Z4N|sit_room_202505280031_acs_stena_76893>"
        resolved_id = "C08U5S51Z4N"

        params = QueryCommandParams(
            user_id="U1",
            user_name="testuser",
            channel_id=mention,
            command_text=f"query {mention} What was the root cause?",
            response_url="http://response.url",
            command_type=CommandType.QUERY,
            context=CommandContext.DIRECT_MESSAGE,
            query_text="What was the root cause?",
            original_command=f"/ketchup query {mention} What was the root cause?",
            target_channel_id=mention,
        )

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                resolved_id,
                "channel_mention",
            )
            mock_registry = MagicMock()
            mock_registry.aget = AsyncMock(return_value=mock_resolver)
            mock_get_registry.return_value = mock_registry

            with patch.object(
                self.handler,
                "_process_query",
                new_callable=AsyncMock,
                return_value="Generated Text",
            ):
                result = await self.handler.process_query_request(
                    params=params,
                    user_id="U1",
                    channel_id=mention,
                    dm_channel_id="D1",
                    response_url="http://response.url",
                )

            assert isinstance(result, ProcessingResult)
            assert result.status_code == 200
            mock_resolver.resolve_channel_parameter.assert_awaited_with(mention)
