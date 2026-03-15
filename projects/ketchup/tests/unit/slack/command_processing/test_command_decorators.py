"""
test_command_decorators.py

Unit tests for command_decorators.py (handle_archived_channel).

Covers:
- handle_archived_channel: all logic branches, error handling, and edge cases
- Channel parameter resolution within decorator
- Uses dummy handler class and async method to test decorator
- Mocks all dependencies (restore_ops, slack_posting_handler, channel_name_resolver)
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- All required parameters present, restore succeeds, original function called
- Missing required parameters (user_id, channel_id)
- Missing restore_ops dependency
- Restore operation fails (returns False)
- Exception in decorated function
- Exception in decorator logic
- Error posting via response_url
- Channel parameter resolution (mentions, names, IDs)

Expected Outcomes:
- Decorated function is called only if all checks pass
- Error responses are returned and error messages posted as expected
- All external calls are mocked and asserted
- Channel parameters are resolved before API calls

"""

from unittest.mock import AsyncMock, patch

import pytest

from packages.slack.channel_events.models import ProcessingResult
from packages.slack.command_processing import command_decorators


@pytest.mark.asyncio
class TestHandleArchivedChannel:
    def setup_method(self) -> None:
        class DummyHandler:
            def __init__(self) -> None:
                self.channel_restore_ops = AsyncMock()
                self.slack_posting_handler = AsyncMock()

            @command_decorators.handle_archived_channel
            async def do_command(self, **kwargs):
                return ProcessingResult(status_code=200, body="ok", feedback_sent=True)

        self.handler = DummyHandler()

    async def test_successful_restore_and_command(self) -> None:
        self.handler.channel_restore_ops.restore_archived_channel.return_value = (
            True,
            True,
        )
        result = await self.handler.do_command(
            user_id="U1", channel_id="C1", incoming_channel="C1", response_url="url"
        )
        assert result == ProcessingResult(status_code=200, body="ok", feedback_sent=True)
        self.handler.channel_restore_ops.restore_archived_channel.assert_awaited_once()

    async def test_missing_required_parameters(self) -> None:
        result = await self.handler.do_command(channel_id="C1", response_url="url")
        assert result.status_code == 400
        self.handler.slack_posting_handler.post_message.assert_awaited_once()

    async def test_missing_restore_ops(self) -> None:
        self.handler.channel_restore_ops = None
        result = await self.handler.do_command(user_id="U1", channel_id="C1", response_url="url")
        assert result.status_code == 500
        self.handler.slack_posting_handler.post_message.assert_awaited_once()

    async def test_restore_fails(self) -> None:
        self.handler.channel_restore_ops.restore_archived_channel.return_value = (
            False,
            True,
        )
        result = await self.handler.do_command(user_id="U1", channel_id="C1", response_url="url")
        assert result.status_code == 400
        self.handler.channel_restore_ops.restore_archived_channel.assert_awaited_once()

    async def test_exception_in_command(self) -> None:
        class DummyHandler:
            def __init__(self) -> None:
                self.channel_restore_ops = AsyncMock()
                self.slack_posting_handler = AsyncMock()

            @command_decorators.handle_archived_channel
            async def do_command(self, **kwargs):
                raise RuntimeError("fail")

        handler = DummyHandler()
        handler.channel_restore_ops.restore_archived_channel.return_value = (True, True)
        result = await handler.do_command(user_id="U1", channel_id="C1", response_url="url")
        assert result.status_code == 500
        handler.slack_posting_handler.post_message.assert_awaited_once()

    async def test_exception_in_decorator(self) -> None:
        # Patch restore_archived_channel to raise
        self.handler.channel_restore_ops.restore_archived_channel.side_effect = Exception("fail")
        result = await self.handler.do_command(user_id="U1", channel_id="C1", response_url="url")
        assert result.status_code == 500
        self.handler.slack_posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
class TestHandleArchivedChannelResolution:
    """Test channel parameter resolution within the decorator."""

    def setup_method(self) -> None:
        class DummyHandler:
            def __init__(self) -> None:
                self.channel_restore_ops = AsyncMock()
                self.slack_posting_handler = AsyncMock()
                self.received_kwargs = {}

            @command_decorators.handle_archived_channel
            async def do_command(self, **kwargs):
                # Store kwargs to verify resolution worked
                self.received_kwargs = kwargs.copy()
                return ProcessingResult(status_code=200, body="ok", feedback_sent=True)

        self.handler = DummyHandler()
        self.handler.channel_restore_ops.restore_archived_channel.return_value = (
            True,
            False,
        )

    async def test_channel_id_no_resolution_needed(self) -> None:
        """Test that valid channel IDs are passed through unchanged."""
        channel_id = "C1234567890"

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_typed_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                channel_id,
                "channel_id",
            )
            mock_registry = AsyncMock()
            mock_registry.aget.return_value = mock_resolver
            mock_get_typed_registry.return_value = mock_registry

            result = await self.handler.do_command(
                user_id="U1",
                channel_id=channel_id,
                text=f"status {channel_id}",
                response_url="url",
            )

            assert result.status_code == 200
            # Verify the channel_id was not changed (already valid)
            assert self.handler.received_kwargs["channel_id"] == channel_id
            mock_resolver.resolve_channel_parameter.assert_awaited_once_with(channel_id)

    async def test_channel_mention_resolution(self) -> None:
        """Test that channel mentions are resolved to channel IDs."""
        mention = "<#C1234567890|general>"
        resolved_id = "C1234567890"
        original_text = f"status {mention}"
        expected_text = f"status {resolved_id}"

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_typed_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                resolved_id,
                "channel_mention",
            )
            mock_registry = AsyncMock()
            mock_registry.aget.return_value = mock_resolver
            mock_get_typed_registry.return_value = mock_registry

            result = await self.handler.do_command(
                user_id="U1", channel_id=mention, text=original_text, response_url="url"
            )

            assert result.status_code == 200
            # Verify the channel_id was resolved
            assert self.handler.received_kwargs["channel_id"] == resolved_id
            # Verify the text was updated
            assert self.handler.received_kwargs["text"] == expected_text
            mock_resolver.resolve_channel_parameter.assert_awaited_once_with(mention)

    async def test_channel_name_resolution(self) -> None:
        """Test that channel names are resolved to channel IDs."""
        channel_name = "#general"
        resolved_id = "C1234567890"
        original_text = f"status {channel_name}"
        expected_text = f"status {resolved_id}"

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_typed_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                resolved_id,
                "channel_name",
            )
            mock_registry = AsyncMock()
            mock_registry.aget.return_value = mock_resolver
            mock_get_typed_registry.return_value = mock_registry

            result = await self.handler.do_command(
                user_id="U1",
                channel_id=channel_name,
                text=original_text,
                response_url="url",
            )

            assert result.status_code == 200
            # Verify the channel_id was resolved
            assert self.handler.received_kwargs["channel_id"] == resolved_id
            # Verify the text was updated
            assert self.handler.received_kwargs["text"] == expected_text
            mock_resolver.resolve_channel_parameter.assert_awaited_once_with(channel_name)

    async def test_resolver_not_available(self) -> None:
        """Test behavior when ChannelNameResolver is not available."""
        channel_param = "<#C1234567890|general>"

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_typed_registry:
            mock_registry = AsyncMock()
            mock_registry.aget.return_value = None  # Resolver not available
            mock_get_typed_registry.return_value = mock_registry

            result = await self.handler.do_command(
                user_id="U1",
                channel_id=channel_param,
                text=f"status {channel_param}",
                response_url="url",
            )

            assert result.status_code == 200
            # Channel parameter should use fallback regex extraction for mentions
            # The fallback extracts "C1234567890" from "<#C1234567890|general>"
            assert self.handler.received_kwargs["channel_id"] == "C1234567890"

    async def test_resolution_exception_handling(self) -> None:
        """Test handling of exceptions during channel resolution."""
        channel_param = "#general"

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_typed_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.side_effect = Exception("Resolution failed")
            mock_registry = AsyncMock()
            mock_registry.aget.return_value = mock_resolver
            mock_get_typed_registry.return_value = mock_registry

            result = await self.handler.do_command(
                user_id="U1",
                channel_id=channel_param,
                text=f"status {channel_param}",
                response_url="url",
            )

            assert result.status_code == 200
            # Channel parameter should be unchanged when resolution fails
            assert self.handler.received_kwargs["channel_id"] == channel_param

    async def test_real_world_mention_example(self) -> None:
        """Test with the real-world mention that caused the original bug."""
        mention = "<#C08U5S51Z4N|sit_room_202505280031_acs_stena_76893>"
        resolved_id = "C08U5S51Z4N"
        original_text = f"status {mention}"
        expected_text = f"status {resolved_id}"

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_typed_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                resolved_id,
                "channel_mention",
            )
            mock_registry = AsyncMock()
            mock_registry.aget.return_value = mock_resolver
            mock_get_typed_registry.return_value = mock_registry

            result = await self.handler.do_command(
                user_id="U1", channel_id=mention, text=original_text, response_url="url"
            )

            assert result.status_code == 200
            # Verify the channel_id was properly extracted
            assert self.handler.received_kwargs["channel_id"] == resolved_id
            # Verify the text was updated
            assert self.handler.received_kwargs["text"] == expected_text

            # Verify restore_archived_channel was called with resolved ID, not the mention
            self.handler.channel_restore_ops.restore_archived_channel.assert_awaited_once()
            call_args = self.handler.channel_restore_ops.restore_archived_channel.call_args
            assert call_args.kwargs["channel_id"] == resolved_id

    async def test_target_channel_id_from_dm_context(self) -> None:
        """Test channel resolution when channel_id comes from incoming_channel (DM context)."""
        mention = "<#C1234567890|general>"
        resolved_id = "C1234567890"

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_typed_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                resolved_id,
                "channel_mention",
            )
            mock_registry = AsyncMock()
            mock_registry.aget.return_value = mock_resolver
            mock_get_typed_registry.return_value = mock_registry

            # In DM context, channel_id might be None and incoming_channel contains the target
            result = await self.handler.do_command(
                user_id="U1",
                channel_id=None,  # No explicit channel_id
                incoming_channel=mention,  # Target channel in incoming_channel
                text=f"status {mention}",
                response_url="url",
            )

            assert result["statusCode"] == 200
            # Verify resolution occurred and restore was called with resolved ID
            self.handler.channel_restore_ops.restore_archived_channel.assert_awaited_once()
            call_args = self.handler.channel_restore_ops.restore_archived_channel.call_args
            assert call_args.kwargs["channel_id"] == resolved_id

    async def test_rearchive_uses_resolved_channel_id(self) -> None:
        """Test that re-archive operation uses the resolved channel ID, not the original mention."""
        mention = "<#C1234567890|general>"
        resolved_id = "C1234567890"

        # Mock restore_ops to return (True, True) indicating channel was originally archived
        self.handler.channel_restore_ops.restore_archived_channel.return_value = (
            True,
            True,
        )
        self.handler.channel_restore_ops.rearchive_channel_if_needed = AsyncMock()

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_typed_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                resolved_id,
                "channel_mention",
            )
            mock_registry = AsyncMock()
            mock_registry.aget.return_value = mock_resolver
            mock_get_typed_registry.return_value = mock_registry

            result = await self.handler.do_command(
                user_id="U1",
                channel_id=mention,  # Channel mention as input
                incoming_channel="D1",
                text=f"status {mention}",
                response_url="url",
            )

            assert result["statusCode"] == 200

            # Verify that restore was called with resolved ID
            self.handler.channel_restore_ops.restore_archived_channel.assert_awaited_once()
            restore_call_args = self.handler.channel_restore_ops.restore_archived_channel.call_args
            assert restore_call_args.kwargs["channel_id"] == resolved_id

            # CRITICAL TEST: Verify that rearchive was called with resolved ID, not the mention
            self.handler.channel_restore_ops.rearchive_channel_if_needed.assert_awaited_once()
            rearchive_call_args = (
                self.handler.channel_restore_ops.rearchive_channel_if_needed.call_args
            )
            assert (
                rearchive_call_args.kwargs["channel_id"] == resolved_id
            ), f"Re-archive should use resolved ID '{resolved_id}', not mention '{mention}'"

    async def test_real_world_bug_reproduction(self) -> None:
        """Test the exact bug scenario reported: channel mention not re-archived after command."""
        # This is the exact mention format from the reported logs
        mention = "<#C090WV8M7H6|cso_202506050045_adobe_campaign_77552>"
        resolved_id = "C090WV8M7H6"

        # Mock restore_ops to return (True, True) indicating channel was originally archived
        self.handler.channel_restore_ops.restore_archived_channel.return_value = (
            True,
            True,
        )
        self.handler.channel_restore_ops.rearchive_channel_if_needed = AsyncMock()

        with patch(
            "packages.slack.command_processing.channel_resolver.get_typed_registry"
        ) as mock_get_typed_registry:
            mock_resolver = AsyncMock()
            mock_resolver.resolve_channel_parameter.return_value = (
                resolved_id,
                "channel_mention",
            )
            mock_registry = AsyncMock()
            mock_registry.aget.return_value = mock_resolver
            mock_get_typed_registry.return_value = mock_registry

            # Simulate the exact command that caused the issue
            result = await self.handler.do_command(
                user_id="W7MGASQ2K",  # From logs
                channel_id=mention,  # Channel mention as input (the problematic format)
                incoming_channel="D0840EX80R5",  # From logs
                text=f"status {mention}",
                response_url="url",
            )

            assert result["statusCode"] == 200

            # Verify that restore was called with resolved ID (this worked before)
            self.handler.channel_restore_ops.restore_archived_channel.assert_awaited_once()
            restore_call_args = self.handler.channel_restore_ops.restore_archived_channel.call_args
            assert restore_call_args.kwargs["channel_id"] == resolved_id

            # THE BUG FIX: Verify that rearchive was called with resolved ID, not the mention
            # Before the fix, this would have been called with the mention format, causing the bug
            self.handler.channel_restore_ops.rearchive_channel_if_needed.assert_awaited_once()
            rearchive_call_args = (
                self.handler.channel_restore_ops.rearchive_channel_if_needed.call_args
            )

            # This assertion would have FAILED before the fix because it would receive the mention
            assert rearchive_call_args.kwargs["channel_id"] == resolved_id, (
                f"CRITICAL BUG: Re-archive received '{rearchive_call_args.kwargs['channel_id']}' "
                + f"instead of resolved ID '{resolved_id}'. This causes the channel to remain unarchived!"
            )
