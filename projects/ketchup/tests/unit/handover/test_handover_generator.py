"""
Unit tests for handover summary generator.
"""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from ketchup_unified_scheduler.services.handover.generator import generate_and_post_handover
from packages.core.constants import ACCESS_REQUEST_CHANNEL, FEEDBACK_CHANNEL


class TestHandoverGenerator:
    """Test cases for handover summary generator"""

    @pytest.fixture
    def current_time_in_schedule(self):
        """Get current time formatted for HANDOVER_SCHEDULE_TIMES"""
        return datetime.now(timezone.utc).strftime("%H:%M")

    @pytest.fixture
    def mock_container(self):
        """Create mock TypedDI container with all required services"""
        container = AsyncMock()

        # Mock all service dependencies
        mock_channel_ops = AsyncMock()
        mock_channel_ops.query_ops = AsyncMock()
        mock_channel_ops.query_ops.get_all_active_channels = AsyncMock(return_value=[])
        mock_channel_ops.query_ops.get_channel_details = AsyncMock(
            return_value={
                "customer_name": "Test Customer",
                "jira_ticket": "TEST-123",
            }
        )

        mock_channel_msg_ops = AsyncMock()
        mock_channel_membership_ops = AsyncMock()
        mock_channel_membership_ops.lookup_membership_of_channels = AsyncMock(
            return_value=[{"id": "C03PWLW9P5H"}]
        )

        mock_mcp_client = AsyncMock()
        mock_mcp_client.get_issue_comments = AsyncMock(return_value=[])

        mock_openai_handler = AsyncMock()
        mock_openai_handler.execute_prompt = AsyncMock(
            return_value="• Incident resolved\n• No further action needed"
        )

        mock_posting_handler = AsyncMock()
        mock_posting_handler._post_channel_message = AsyncMock()

        # Set up container.aget to return mocks
        async def mock_aget(protocol):
            from packages.core.typed_di.service_registrations.protocols import (
                ChannelMembershipOpsProtocol,
                ChannelOperationsProtocol,
                MCPAsyncClientProtocol,
                OpenAIHandlerProtocol,
                SlackChannelMessageOpsProtocol,
                SlackPostingHandlerProtocol,
            )

            if protocol == ChannelOperationsProtocol:
                return mock_channel_ops
            elif protocol == SlackChannelMessageOpsProtocol:
                return mock_channel_msg_ops
            elif protocol == ChannelMembershipOpsProtocol:
                return mock_channel_membership_ops
            elif protocol == MCPAsyncClientProtocol:
                return mock_mcp_client
            elif protocol == OpenAIHandlerProtocol:
                return mock_openai_handler
            elif protocol == SlackPostingHandlerProtocol:
                return mock_posting_handler
            else:
                return AsyncMock()

        container.aget = mock_aget

        # Store mocks for easy access in tests
        container._mock_channel_ops = mock_channel_ops
        container._mock_channel_msg_ops = mock_channel_msg_ops
        container._mock_channel_membership_ops = mock_channel_membership_ops
        container._mock_mcp_client = mock_mcp_client
        container._mock_openai_handler = mock_openai_handler
        container._mock_posting_handler = mock_posting_handler

        return container

    @pytest.mark.asyncio
    async def test_feature_flag_disabled_returns_disabled_status(self, mock_container):
        """Test generator returns disabled status when feature flag is off"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "false"}):
            result = await generate_and_post_handover(mock_container)

            assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_feature_flag_missing_returns_disabled_status(self, mock_container):
        """Test generator returns disabled status when feature flag is not set"""
        with patch.dict(os.environ, {}, clear=True):
            result = await generate_and_post_handover(mock_container)

            assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_no_active_channels_returns_success_with_zero_count(
        self, mock_container, current_time_in_schedule
    ):
        """Test generator returns success with channel_count=0 when no active channels"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Mock no active channels
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.return_value = []

                result = await generate_and_post_handover(mock_container)

                assert result["status"] == "success"
                assert result["channel_count"] == 0

    @pytest.mark.asyncio
    async def test_channels_with_no_data_included_with_no_updates_summary(
        self, mock_container, current_time_in_schedule
    ):
        """Test channels with no messages and no JIRA comments are included with 'no updates' summary"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Mock channel with no data
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.return_value = [
                    {"channel_id": "C12345", "channel_name": "empty-channel"}
                ]

                # Mock MessagePreparer to return no messages
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "",  # No messages
                            {"has_channel_messages": False},  # No messages metadata
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    # Mock no JIRA comments
                    mock_container._mock_mcp_client.get_issue_comments.return_value = []

                    result = await generate_and_post_handover(mock_container)

                    assert result["status"] == "success"
                    assert (
                        result["channel_count"] == 1
                    )  # No-activity channels included with summary

    @pytest.mark.asyncio
    async def test_feedback_channel_is_filtered_out(self, mock_container, current_time_in_schedule):
        """Test FEEDBACK_CHANNEL is filtered out"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Mock channels including FEEDBACK_CHANNEL
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.return_value = [
                    {"channel_id": FEEDBACK_CHANNEL, "channel_name": "feedback"},
                    {"channel_id": "C12345", "channel_name": "normal-channel"},
                ]

                # Mock MessagePreparer
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "Some messages",
                            {"has_channel_messages": True},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    result = await generate_and_post_handover(mock_container)

                    # Should only process 1 channel (not FEEDBACK_CHANNEL)
                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

    @pytest.mark.asyncio
    async def test_access_request_channel_is_filtered_out(
        self, mock_container, current_time_in_schedule
    ):
        """Test ACCESS_REQUEST_CHANNEL is filtered out"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Mock channels including ACCESS_REQUEST_CHANNEL
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.return_value = [
                    {"channel_id": ACCESS_REQUEST_CHANNEL, "channel_name": "access-requests"},
                    {"channel_id": "C12345", "channel_name": "normal-channel"},
                ]

                # Mock MessagePreparer
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "Some messages",
                            {"has_channel_messages": True},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    result = await generate_and_post_handover(mock_container)

                    # Should only process 1 channel (not ACCESS_REQUEST_CHANNEL)
                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

    @pytest.mark.asyncio
    async def test_handover_target_channel_is_filtered_out(
        self, mock_container, current_time_in_schedule
    ):
        """Test HANDOVER_TARGET_CHANNEL itself is filtered out"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Mock channels including the target channel itself
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.return_value = [
                    {"channel_id": "C03PWLW9P5H", "channel_name": "handover-target"},
                    {"channel_id": "C12345", "channel_name": "normal-channel"},
                ]

                # Mock MessagePreparer
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "Some messages",
                            {"has_channel_messages": True},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    result = await generate_and_post_handover(mock_container)

                    # Should only process 1 channel (not target channel)
                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

    @pytest.mark.asyncio
    async def test_bot_not_member_returns_not_member_status(
        self, mock_container, current_time_in_schedule
    ):
        """Test generator returns not_member status when bot is not in target channel"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Mock bot not being a member
                mock_container._mock_channel_membership_ops.lookup_membership_of_channels.return_value = (
                    []
                )

                result = await generate_and_post_handover(mock_container)

                assert result["status"] == "not_member"

    @pytest.mark.asyncio
    async def test_successful_generation_posts_to_target_channel(
        self, mock_container, current_time_in_schedule
    ):
        """Test successful generation posts message to target channel"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Mock one active channel with data
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.return_value = [
                    {"channel_id": "C12345", "channel_name": "test-incident"}
                ]

                # Mock MessagePreparer
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "Test message content",
                            {"has_channel_messages": True},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    result = await generate_and_post_handover(mock_container)

                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

                    # Verify posting handler was called
                    mock_container._mock_posting_handler._post_channel_message.assert_called_once()

                    # Verify it was posted to correct channel
                    call_args = mock_container._mock_posting_handler._post_channel_message.call_args
                    assert call_args[1]["channel_id"] == "C03PWLW9P5H"

    @pytest.mark.asyncio
    async def test_result_includes_timestamp(self, mock_container, current_time_in_schedule):
        """Test result includes ISO format timestamp"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                result = await generate_and_post_handover(mock_container)

                assert "timestamp" in result
                # Verify it's a valid ISO format timestamp
                datetime.fromisoformat(result["timestamp"])

    @pytest.mark.asyncio
    async def test_error_handling_returns_error_status(
        self, mock_container, current_time_in_schedule
    ):
        """Test error during generation returns error status"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Mock an error in channel operations
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.side_effect = (
                    Exception("Test error")
                )

                result = await generate_and_post_handover(mock_container)

                assert result["status"] == "error"
                assert "error" in result
                assert "Test error" in result["error"]

    @pytest.mark.asyncio
    async def test_channel_with_messages_but_no_jira_is_processed(
        self, mock_container, current_time_in_schedule
    ):
        """Test channel with Slack messages but no JIRA comments is still processed"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.return_value = [
                    {"channel_id": "C12345", "channel_name": "test-channel"}
                ]

                # Mock MessagePreparer with messages
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "User: Issue reported",
                            {"has_channel_messages": True},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    # No JIRA comments
                    mock_container._mock_mcp_client.get_issue_comments.return_value = []

                    result = await generate_and_post_handover(mock_container)

                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

    @pytest.mark.asyncio
    async def test_channel_with_jira_but_no_messages_is_processed(
        self, mock_container, current_time_in_schedule
    ):
        """Test channel with JIRA comments but no Slack messages is still processed"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.return_value = [
                    {"channel_id": "C12345", "channel_name": "test-channel"}
                ]

                # Mock MessagePreparer with no messages
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "",
                            {"has_channel_messages": False},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    # Mock JIRA comments
                    mock_container._mock_mcp_client.get_issue_comments.return_value = [
                        {
                            "author": {"displayName": "John Doe"},
                            "created": "2024-01-01T10:00:00",
                            "body": "Working on resolution",
                        }
                    ]

                    result = await generate_and_post_handover(mock_container)

                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

    @pytest.mark.asyncio
    async def test_openai_handler_called_with_correct_prompts(
        self, mock_container, current_time_in_schedule
    ):
        """Test OpenAI handler is called with system and channel prompts"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                mock_container._mock_channel_ops.query_ops.get_all_active_channels.return_value = [
                    {"channel_id": "C12345", "channel_name": "test-channel"}
                ]

                # Mock MessagePreparer
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "Test messages",
                            {"has_channel_messages": True},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    await generate_and_post_handover(mock_container)

                    # Verify OpenAI handler was called
                    mock_container._mock_openai_handler.execute_prompt.assert_called_once()

                    # Verify messages structure
                    call_args = mock_container._mock_openai_handler.execute_prompt.call_args
                    messages = call_args[1]["messages"]

                    assert len(messages) == 2
                    assert messages[0]["role"] == "system"
                    assert messages[1]["role"] == "user"
                    assert "test-channel" in messages[1]["content"]


class TestSanitizeMrkdwn:
    """Test cases for mrkdwn sanitization"""

    def test_strips_channel_broadcast(self):
        from ketchup_unified_scheduler.services.handover.generator import _sanitize_mrkdwn

        assert "alert" in _sanitize_mrkdwn("<!channel> alert")
        assert "<!channel>" not in _sanitize_mrkdwn("<!channel> alert")

    def test_strips_here_broadcast(self):
        from ketchup_unified_scheduler.services.handover.generator import _sanitize_mrkdwn

        assert "<!here>" not in _sanitize_mrkdwn("<!here> update")

    def test_strips_everyone_broadcast(self):
        from ketchup_unified_scheduler.services.handover.generator import _sanitize_mrkdwn

        assert "<!everyone>" not in _sanitize_mrkdwn("<!everyone> notice")

    def test_strips_user_mentions(self):
        from ketchup_unified_scheduler.services.handover.generator import _sanitize_mrkdwn

        result = _sanitize_mrkdwn("Assigned to <@U0123ABCD>")
        assert "<@U0123ABCD>" not in result
        assert "Assigned to" in result

    def test_strips_user_mentions_with_display_name(self):
        from ketchup_unified_scheduler.services.handover.generator import _sanitize_mrkdwn

        result = _sanitize_mrkdwn("CC <@U0123ABCD|john.doe>")
        assert "<@U0123ABCD|john.doe>" not in result

    def test_preserves_normal_text(self):
        from ketchup_unified_scheduler.services.handover.generator import _sanitize_mrkdwn

        text = "• Investigating memory leak in production server"
        assert _sanitize_mrkdwn(text) == text
