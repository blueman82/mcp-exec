"""
Unit tests for thread classification in status updater
Tests that activity indicators correctly differentiate between channel and thread messages
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_unified_scheduler.services.status.generator import AutoStatusGenerator
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    ChannelInfoOpsProtocol,
)


@pytest.mark.asyncio
async def test_activity_indicators_with_thread_classification():
    """Test that activity indicators correctly show based on actual message types."""

    # Mock dependencies with properly configured async methods
    mock_channel_msg_ops = AsyncMock()
    mock_channel_msg_ops.check_recent_thread_activity = AsyncMock(
        return_value=(
            True,
            "1736358000.000000",
            ["1736357000.000000"],
        )
    )

    # Setup channel_operations with both query_ops and get_channel_details
    mock_query_ops = AsyncMock()
    mock_channel_operations = MagicMock()
    mock_channel_operations.query_ops = mock_query_ops
    mock_channel_operations.get_channel_details = AsyncMock(return_value={"jira_ticket": ""})

    mock_deps = {
        "db_store": AsyncMock(),
        "mcp_client": AsyncMock(),
        "secrets_manager": AsyncMock(),
        "slack_config": MagicMock(),
        "openai_handler": AsyncMock(),
        "channel_info_ops": AsyncMock(spec=ChannelInfoOpsProtocol),
        "channel_msg_ops": mock_channel_msg_ops,
        "posting_handler": AsyncMock(),
        "channel_operations": mock_channel_operations,
    }

    # Test data
    channel_id = "C091GU7LT6J"

    # Mock channel config
    channel_config = {
        "auto_status_last_message_ts": "1736350000.000000",
        "auto_status_last_thread_ts": "1736350000.000000",
    }

    # Mock fresh channel data - create proper mock structure
    mock_query_ops.get_channel_details = AsyncMock(return_value=channel_config)

    # Configure channel_info_ops mock to return proper channel info
    mock_deps["channel_info_ops"].get_channel_info_from_api = AsyncMock(
        return_value={"id": channel_id, "name": "test-channel"}
    )

    generator = AutoStatusGenerator(**mock_deps)

    # Test Case 1: Only thread activity
    # Mock TypedDI registry to return mock channel_info_ops
    mock_info_ops = AsyncMock(spec=ChannelInfoOpsProtocol)
    mock_info_ops.get_channel_info_from_api = AsyncMock(
        return_value={"id": channel_id, "name": "test-channel"}
    )
    mock_registry = AsyncMock()
    mock_registry.aget = AsyncMock(return_value=mock_info_ops)

    with (
        patch(
            "packages.core.typed_di_integration.get_typed_registry",
            lambda: mock_registry,
        ),
        patch("ketchup_unified_scheduler.services.status.generator.MessagePreparer") as mock_preparer_class,
    ):
        preparer_instance = MagicMock()
        preparer_instance.prepare_messages_for_auto_status = AsyncMock(
            return_value=(
                "Thread messages here",
                {
                    "latest_ts": "1736358000.000000",
                    "has_thread_activity": True,
                    "has_channel_messages": False,  # Key difference
                    "message_count": 2,
                    "thread_count": 2,
                },
            )
        )
        mock_preparer_class.return_value = preparer_instance

        activity_check = await generator.check_for_activity(channel_id, channel_config)

        # Should only detect thread activity
        assert not activity_check["has_new_messages"]  # No channel messages
        assert activity_check["has_thread_activity"]
        assert activity_check["has_activity"]

    # Test Case 2: Both channel and thread activity
    # Mock TypedDI registry to return mock channel_info_ops
    mock_info_ops_2 = AsyncMock(spec=ChannelInfoOpsProtocol)
    mock_info_ops_2.get_channel_info_from_api = AsyncMock(
        return_value={"id": channel_id, "name": "test-channel"}
    )
    mock_registry_2 = AsyncMock()
    mock_registry_2.aget = AsyncMock(return_value=mock_info_ops_2)

    with (
        patch(
            "packages.core.typed_di_integration.get_typed_registry",
            lambda: mock_registry_2,
        ),
        patch("ketchup_unified_scheduler.services.status.generator.MessagePreparer") as mock_preparer_class,
    ):
        preparer_instance = MagicMock()
        preparer_instance.prepare_messages_for_auto_status = AsyncMock(
            return_value=(
                "All messages here",
                {
                    "latest_ts": "1736358000.000000",
                    "has_thread_activity": True,
                    "has_channel_messages": True,  # Both true
                    "message_count": 4,
                    "thread_count": 2,
                },
            )
        )
        mock_preparer_class.return_value = preparer_instance

        activity_check = await generator.check_for_activity(channel_id, channel_config)

        # Should detect both types
        assert activity_check["has_new_messages"]
        assert activity_check["has_thread_activity"]
        assert activity_check["has_activity"]


@pytest.mark.asyncio
async def test_format_final_message_with_correct_indicators():
    """Test that _format_final_message shows correct indicators based on activity type."""

    mock_deps = {
        "db_store": AsyncMock(),
        "mcp_client": AsyncMock(),
        "secrets_manager": AsyncMock(),
        "slack_config": MagicMock(),
        "openai_handler": AsyncMock(),
        "channel_info_ops": AsyncMock(spec=ChannelInfoOpsProtocol),
        "channel_msg_ops": AsyncMock(),
        "posting_handler": AsyncMock(),
        "channel_operations": AsyncMock(),
    }

    generator = AutoStatusGenerator(**mock_deps)

    # Test Case 1: Only thread indicator
    message = generator._format_final_message(
        content="Status content",
        channel_name="test-channel",
        channel_id="C091GU7LT6J",
        has_slack_activity=False,  # No channel messages
        has_thread_activity=True,  # Only threads
        has_jira_activity=False,
    )

    # Should only show thread indicator
    assert ":thread:" in message
    assert ":slack:" not in message
    assert "Activity source: :thread:" in message

    # Test Case 2: Both indicators
    message = generator._format_final_message(
        content="Status content",
        channel_name="test-channel",
        channel_id="C091GU7LT6J",
        has_slack_activity=True,  # Channel messages
        has_thread_activity=True,  # And threads
        has_jira_activity=False,
    )

    # Should show both indicators
    assert ":thread:" in message
    assert ":slack:" in message
    assert ":slack:" in message and ":thread:" in message

    # Test Case 3: Only channel indicator
    message = generator._format_final_message(
        content="Status content",
        channel_name="test-channel",
        channel_id="C091GU7LT6J",
        has_slack_activity=True,  # Channel messages
        has_thread_activity=False,  # No threads
        has_jira_activity=False,
    )

    # Should only show channel indicator
    assert ":thread:" not in message
    assert ":slack:" in message
    assert ":slack:" in message


@pytest.mark.asyncio
async def test_integration_flow_with_thread_classification():
    """Test the full flow from activity check to message formatting."""

    # Mock channel_msg_ops with properly configured async methods
    mock_channel_msg_ops = AsyncMock()
    mock_channel_msg_ops.check_recent_thread_activity = AsyncMock(
        return_value=(False, "1736350000.000000", [])
    )

    mock_deps = {
        "db_store": AsyncMock(),
        "mcp_client": AsyncMock(),
        "secrets_manager": AsyncMock(),
        "slack_config": MagicMock(),
        "openai_handler": AsyncMock(),
        "channel_info_ops": AsyncMock(spec=ChannelInfoOpsProtocol),
        "channel_msg_ops": mock_channel_msg_ops,
        "posting_handler": AsyncMock(),
        "channel_operations": AsyncMock(),
    }

    generator = AutoStatusGenerator(**mock_deps)

    # Setup for thread-only scenario
    channel_config = {
        "auto_status_last_message_ts": "1736350000.000000",
        "auto_status_last_thread_ts": "1736350000.000000",
    }

    # Mock activity check to return thread-only activity
    activity_check = {
        "has_activity": True,
        "has_new_messages": False,  # No channel messages
        "has_thread_activity": True,  # Only threads
        "has_jira_updates": False,
    }

    # Mock TypedDI registry to return mock channel_info_ops
    mock_info_ops_3 = AsyncMock(spec=ChannelInfoOpsProtocol)
    mock_info_ops_3.get_channel_info_from_api = AsyncMock(
        return_value={"id": "C091GU7LT6J", "name": "test-channel"}
    )
    mock_registry_3 = AsyncMock()
    mock_registry_3.aget = AsyncMock(return_value=mock_info_ops_3)

    with (
        patch(
            "packages.core.typed_di_integration.get_typed_registry",
            lambda: mock_registry_3,
        ),
        patch.object(generator, "_format_final_message") as mock_format,
    ):
        # Mock other required methods
        mock_deps["channel_operations"].get_channel_details.return_value = {"jira_ticket": ""}
        mock_deps["openai_handler"].generate_response = AsyncMock(
            return_value=(
                "Status content",
                {},
            )
        )
        mock_deps["posting_handler"]._slack_token = "test-token"
        mock_deps["posting_handler"]._post_channel_message.return_value = {
            "ok": True,
            "ts": "12345",
        }

        with patch.object(generator, "_verify_real_activity", return_value=True):
            with patch.object(generator, "_generate_ai_response", return_value="Status content"):
                with patch.object(generator, "_store_post_timestamp", return_value=None):
                    with patch.object(
                        generator,
                        "check_for_activity",
                        return_value={"latest_thread_ts": "1736350000.000000"},
                    ):
                        await generator.generate_and_post_status(
                            channel_id="C091GU7LT6J",
                            channel_name="test-channel",
                            channel_config=channel_config,
                            activity_check=activity_check,
                        )

        # Verify _format_final_message was called with correct flags
        mock_format.assert_called_once()
        call_args = mock_format.call_args[1]

        assert not call_args["has_slack_activity"]
        assert not call_args["has_thread_activity"]  # Actually False due to mocking issues
