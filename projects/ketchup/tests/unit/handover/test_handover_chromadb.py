"""
Unit tests for ChromaDB integration in handover summary generator.

Tests the fallback behavior: ChromaDB first, then Slack API.
"""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from ketchup_unified_scheduler.services.handover.generator import generate_and_post_handover


class TestHandoverChromaDBFallback:
    """Test ChromaDB -> Slack API fallback mechanism"""

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
        mock_channel_ops.query_ops.get_all_active_channels = AsyncMock(
            return_value=[{"channel_id": "C12345", "channel_name": "test-channel"}]
        )
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
                AgentConversationStoreProtocol,
                AgentVectorStoreProtocol,
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
            elif protocol == AgentVectorStoreProtocol:
                # Return None to trigger the fallback
                return None
            elif protocol == AgentConversationStoreProtocol:
                # Simulate agent services not available
                raise Exception("Agent services not available")
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
    async def test_chromadb_returns_docs_uses_them_no_slack_api_call(
        self, mock_container, current_time_in_schedule
    ):
        """Test that ChromaDB docs are used and MessagePreparer is NOT instantiated"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Create a mock vector store that returns documents
                mock_vector_store = AsyncMock()
                chromadb_docs = [
                    {"text": "User: Issue detected in production"},
                    {"text": "User: Investigating root cause"},
                ]
                mock_vector_store.get_by_time_range = AsyncMock(return_value=chromadb_docs)

                # Setup container to return the vector store
                original_aget = mock_container.aget

                async def mock_aget_with_vector_store(protocol):
                    from packages.core.typed_di.service_registrations.protocols import (
                        AgentVectorStoreProtocol,
                    )

                    if protocol == AgentVectorStoreProtocol:
                        return mock_vector_store
                    return await original_aget(protocol)

                mock_container.aget = mock_aget_with_vector_store

                # Patch MessagePreparer to track if it's instantiated
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    result = await generate_and_post_handover(mock_container)

                    # Verify success
                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

                    # CRITICAL: MessagePreparer should NOT be instantiated
                    # because ChromaDB returned docs
                    mock_preparer_class.assert_not_called()

                    # Verify ChromaDB was called with correct parameters
                    mock_vector_store.get_by_time_range.assert_called_once()
                    call_kwargs = mock_vector_store.get_by_time_range.call_args[1]
                    assert call_kwargs["channel_id"] == "C12345"
                    assert "since_ts" in call_kwargs

    @pytest.mark.asyncio
    async def test_chromadb_returns_empty_list_falls_back_to_slack_api(
        self, mock_container, current_time_in_schedule
    ):
        """Test that empty ChromaDB result triggers Slack API fallback"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Create a mock vector store that returns empty list
                mock_vector_store = AsyncMock()
                mock_vector_store.get_by_time_range = AsyncMock(return_value=[])

                # Setup container to return the vector store
                original_aget = mock_container.aget

                async def mock_aget_with_vector_store(protocol):
                    from packages.core.typed_di.service_registrations.protocols import (
                        AgentVectorStoreProtocol,
                    )

                    if protocol == AgentVectorStoreProtocol:
                        return mock_vector_store
                    return await original_aget(protocol)

                mock_container.aget = mock_aget_with_vector_store

                # Patch MessagePreparer to track calls
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "Slack API message content",
                            {"has_channel_messages": True},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    result = await generate_and_post_handover(mock_container)

                    # Verify success
                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

                    # Verify ChromaDB was called first
                    mock_vector_store.get_by_time_range.assert_called_once()

                    # Verify MessagePreparer WAS instantiated (fallback)
                    mock_preparer_class.assert_called_once()
                    mock_preparer.prepare_messages_for_auto_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_chromadb_raises_exception_falls_back_to_slack_api(
        self, mock_container, current_time_in_schedule
    ):
        """Test that ChromaDB exception triggers Slack API fallback"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Create a mock vector store that raises an exception
                mock_vector_store = AsyncMock()
                mock_vector_store.get_by_time_range = AsyncMock(
                    side_effect=Exception("ChromaDB connection timeout")
                )

                # Setup container to return the vector store
                original_aget = mock_container.aget

                async def mock_aget_with_vector_store(protocol):
                    from packages.core.typed_di.service_registrations.protocols import (
                        AgentVectorStoreProtocol,
                    )

                    if protocol == AgentVectorStoreProtocol:
                        return mock_vector_store
                    return await original_aget(protocol)

                mock_container.aget = mock_aget_with_vector_store

                # Patch MessagePreparer to track calls
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "Fallback from Slack API",
                            {"has_channel_messages": True},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    result = await generate_and_post_handover(mock_container)

                    # Verify success (graceful degradation)
                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

                    # Verify ChromaDB was called first
                    mock_vector_store.get_by_time_range.assert_called_once()

                    # Verify MessagePreparer WAS instantiated (fallback)
                    mock_preparer_class.assert_called_once()
                    mock_preparer.prepare_messages_for_auto_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_store_is_none_goes_straight_to_slack_api(
        self, mock_container, current_time_in_schedule
    ):
        """Test that when vector_store is None, Slack API is used directly"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # container.aget returns None for AgentVectorStoreProtocol (default)
                # This is handled by the default mock_container fixture

                # Patch MessagePreparer to track calls
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "Slack API fallback content",
                            {"has_channel_messages": True},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    result = await generate_and_post_handover(mock_container)

                    # Verify success
                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

                    # Verify MessagePreparer was instantiated (no ChromaDB path)
                    mock_preparer_class.assert_called_once()
                    mock_preparer.prepare_messages_for_auto_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_chromadb_docs_format_correctly_joined(
        self, mock_container, current_time_in_schedule
    ):
        """Test that ChromaDB docs are correctly joined with newlines"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Create a mock vector store that returns multiple documents
                mock_vector_store = AsyncMock()
                chromadb_docs = [
                    {"text": "First message"},
                    {"text": "Second message"},
                    {"text": "Third message"},
                ]
                mock_vector_store.get_by_time_range = AsyncMock(return_value=chromadb_docs)

                # Setup container to return the vector store
                original_aget = mock_container.aget

                async def mock_aget_with_vector_store(protocol):
                    from packages.core.typed_di.service_registrations.protocols import (
                        AgentVectorStoreProtocol,
                    )

                    if protocol == AgentVectorStoreProtocol:
                        return mock_vector_store
                    return await original_aget(protocol)

                mock_container.aget = mock_aget_with_vector_store

                # Patch OpenAI to capture the prepared messages
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    # Capture what OpenAI receives
                    captured_messages = []

                    async def capture_prompt(**kwargs):
                        captured_messages.append(kwargs.get("messages"))
                        return "• Summary"

                    mock_container._mock_openai_handler.execute_prompt = AsyncMock(
                        side_effect=capture_prompt
                    )

                    result = await generate_and_post_handover(mock_container)

                    # Verify success
                    assert result["status"] == "success"

                    # Verify MessagePreparer was NOT called
                    mock_preparer_class.assert_not_called()

                    # Verify OpenAI received properly joined messages
                    assert len(captured_messages) > 0
                    user_message_content = captured_messages[0][1]["content"]
                    # The prepared messages should be joined with newlines
                    assert "First message" in user_message_content
                    assert "Second message" in user_message_content
                    assert "Third message" in user_message_content

    @pytest.mark.asyncio
    async def test_no_activity_channel_shows_last_update_from_watermark(
        self, mock_container, current_time_in_schedule
    ):
        """Test that channels with no recent activity show last update timestamp from watermark"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                # Create a mock vector store that returns empty list (no recent messages)
                mock_vector_store = AsyncMock()
                mock_vector_store.get_by_time_range = AsyncMock(return_value=[])

                # Create a mock conversation store with watermark
                mock_conversation_store = AsyncMock()
                from packages.agent.conversation.models import MessageWatermark

                watermark = MessageWatermark(
                    channel_id="C12345",
                    latest_ingested_ts="1710000000.000000",
                    backfill_complete=True,
                    backfill_started_at=None,
                    total_ingested=42,
                )
                mock_conversation_store.get_watermark = AsyncMock(return_value=watermark)

                # Setup container to return both stores
                original_aget = mock_container.aget

                async def mock_aget_with_stores(protocol):
                    from packages.core.typed_di.service_registrations.protocols import (
                        AgentConversationStoreProtocol,
                        AgentVectorStoreProtocol,
                    )

                    if protocol == AgentVectorStoreProtocol:
                        return mock_vector_store
                    elif protocol == AgentConversationStoreProtocol:
                        return mock_conversation_store
                    return await original_aget(protocol)

                mock_container.aget = mock_aget_with_stores

                # Patch MessagePreparer to return no messages
                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=(
                            "",  # Empty message content
                            {"has_channel_messages": False},
                        )
                    )
                    mock_preparer_class.return_value = mock_preparer

                    result = await generate_and_post_handover(mock_container)

                    # Verify success
                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

                    # Verify posting handler was called
                    mock_container._mock_posting_handler._post_channel_message.assert_called_once()

                    # Get the posted blocks to verify watermark timestamp is included
                    call_kwargs = (
                        mock_container._mock_posting_handler._post_channel_message.call_args[1]
                    )
                    blocks = call_kwargs["blocks"]

                    # Convert blocks to text to check for expected messages
                    blocks_text = str(blocks)
                    assert "No updates in the last" in blocks_text
                    # Watermark gives timestamp only (no message text for AI)
                    assert "Last activity:" in blocks_text

    @pytest.mark.asyncio
    async def test_no_activity_channel_gets_ai_summary_of_last_messages(
        self, mock_container, current_time_in_schedule
    ):
        """Test that no-activity channels pass last messages through AI for a clean summary"""
        with patch.dict(os.environ, {"KETCHUP_HANDOVER_SUMMARY_ENABLED": "true"}):
            with patch(
                "ketchup_unified_scheduler.services.handover.generator.HANDOVER_SCHEDULE_TIMES",
                [current_time_in_schedule],
            ):
                import json

                # Vector store returns empty (no recent messages in window)
                mock_vector_store = AsyncMock()
                mock_vector_store.get_by_time_range = AsyncMock(return_value=[])

                # Slack API returns last messages with text
                mock_slack_resp = {
                    "status": 200,
                    "body": json.dumps(
                        {
                            "ok": True,
                            "messages": [
                                {
                                    "ts": "1710000000.000000",
                                    "text": "Resolved: customer confirmed fix deployed successfully",
                                }
                            ],
                        }
                    ).encode(),
                    "headers": {},
                    "content_type": "application/json",
                    "url": "",
                }

                original_aget = mock_container.aget

                async def mock_aget_with_stores(protocol):
                    from packages.core.typed_di.service_registrations.protocols import (
                        AgentVectorStoreProtocol,
                    )

                    if protocol == AgentVectorStoreProtocol:
                        return mock_vector_store
                    return await original_aget(protocol)

                mock_container.aget = mock_aget_with_stores

                # Setup channel_msg_ops to return Slack API response
                mock_container._mock_channel_msg_ops.get_api_base_url = AsyncMock(
                    return_value="https://slack.com/api"
                )
                mock_container._mock_channel_msg_ops.headers = {"Authorization": "Bearer test"}
                mock_container._mock_channel_msg_ops._make_api_request = AsyncMock(
                    return_value=mock_slack_resp
                )

                # AI returns a clean summary of the last messages
                mock_container._mock_openai_handler.execute_prompt = AsyncMock(
                    return_value="• *Issue resolved*; customer confirmed fix deployed"
                )

                with patch(
                    "ketchup_unified_scheduler.services.handover.generator.MessagePreparer"
                ) as mock_preparer_class:
                    mock_preparer = AsyncMock()
                    mock_preparer.prepare_messages_for_auto_status = AsyncMock(
                        return_value=("", {"has_channel_messages": False})
                    )
                    mock_preparer_class.return_value = mock_preparer

                    result = await generate_and_post_handover(mock_container)

                    assert result["status"] == "success"
                    assert result["channel_count"] == 1

                    # Verify AI was called with the last messages
                    mock_container._mock_openai_handler.execute_prompt.assert_called_once()
                    ai_call_kwargs = mock_container._mock_openai_handler.execute_prompt.call_args[1]
                    user_content = ai_call_kwargs["messages"][1]["content"]
                    assert "customer confirmed fix deployed" in user_content

                    # Verify the posted summary uses AI output, not raw text
                    call_kwargs = (
                        mock_container._mock_posting_handler._post_channel_message.call_args[1]
                    )
                    blocks_text = str(call_kwargs["blocks"])
                    assert "No updates in the last" in blocks_text
                    assert "last activity" in blocks_text
                    assert "Issue resolved" in blocks_text
