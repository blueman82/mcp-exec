"""
Test thread activity detection in status generator and channel operations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_status_updater.status_generator import AutoStatusGenerator
from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for AutoStatusGenerator."""
    return {
        "db_store": AsyncMock(),
        "mcp_client": AsyncMock(),
        "secrets_manager": AsyncMock(),
        "slack_config": MagicMock(),
        "openai_handler": AsyncMock(),
        "channel_info_ops": AsyncMock(),
        "channel_msg_ops": AsyncMock(),
        "posting_handler": AsyncMock(),
        "channel_operations": AsyncMock(),
    }


class TestThreadActivityDetection:
    """Test thread activity detection functionality."""

    @pytest.mark.asyncio
    async def test_check_recent_thread_activity_with_new_replies(self):
        """Test detection of new thread replies."""
        # Mock all dependencies
        mock_user_ops = MagicMock()
        mock_archive_ops = MagicMock()
        mock_slack_config = MagicMock()

        channel_ops = SlackChannelMessageOps(
            user_ops=mock_user_ops,
            archive_ops=mock_archive_ops,
            slack_config=mock_slack_config,
        )

        # Mock the API response with messages that have threads
        mock_response = {
            "body": """{"ok": true, "messages": [
                {
                    "ts": "1234567890.000100",
                    "thread_ts": "1234567890.000100",
                    "reply_count": 5,
                    "latest_reply": "1234567900.000200"
                },
                {
                    "ts": "1234567880.000100",
                    "thread_ts": "1234567880.000100",
                    "reply_count": 3,
                    "latest_reply": "1234567885.000100"
                }
            ]}"""
        }

        with (
            patch.object(channel_ops, "_make_api_request", AsyncMock(return_value=mock_response)),
            patch.object(
                channel_ops,
                "get_api_base_url",
                AsyncMock(return_value="https://slack.com/api"),
            ),
        ):
            # Check for activity since timestamp 1234567895
            has_activity, latest_ts, active_threads = (
                await channel_ops.check_recent_thread_activity("C123456", "1234567895.000000")
            )

            assert has_activity is True
            assert latest_ts == "1234567900.000200"  # The newest thread reply

    @pytest.mark.asyncio
    async def test_check_recent_thread_activity_no_new_replies(self):
        """Test when there are no new thread replies."""
        # Mock all dependencies
        mock_user_ops = MagicMock()
        mock_archive_ops = MagicMock()
        mock_slack_config = MagicMock()

        channel_ops = SlackChannelMessageOps(
            user_ops=mock_user_ops,
            archive_ops=mock_archive_ops,
            slack_config=mock_slack_config,
        )

        # Mock response with old thread replies
        mock_response = {
            "body": """{"ok": true, "messages": [
                {
                    "ts": "1234567890.000100",
                    "thread_ts": "1234567890.000100",
                    "reply_count": 5,
                    "latest_reply": "1234567892.000200"
                }
            ]}"""
        }

        with (
            patch.object(channel_ops, "_make_api_request", AsyncMock(return_value=mock_response)),
            patch.object(
                channel_ops,
                "get_api_base_url",
                AsyncMock(return_value="https://slack.com/api"),
            ),
        ):
            # Check for activity since a later timestamp
            has_activity, latest_ts, active_threads = (
                await channel_ops.check_recent_thread_activity("C123456", "1234567895.000000")
            )

            assert has_activity is False
            assert latest_ts == "1234567895.000000"  # No change from input

    @pytest.mark.asyncio
    async def test_status_generator_check_activity_includes_threads(self, mock_dependencies):
        """Test that status generator properly checks for thread activity."""
        generator = AutoStatusGenerator(**mock_dependencies)

        # Mock channel details with thread timestamp
        mock_dependencies["channel_operations"].query_ops.get_channel_details.return_value = {
            "auto_status_last_message_ts": "100000",
            "auto_status_last_thread_ts": "100000",
            "auto_status_last_jira_comment_ts": "0",
        }

        # Mock message preparer
        with patch("ketchup_status_updater.status_generator.MessagePreparer") as mock_preparer:

            # Mock no new messages but has thread activity
            preparer_instance = MagicMock()
            preparer_instance.prepare_messages_for_auto_status = AsyncMock(
                return_value=(
                    "No messages found",
                    {
                        "latest_ts": "100000",
                        "has_channel_messages": False,
                        "has_thread_activity": True,
                    },
                )
            )
            mock_preparer.return_value = preparer_instance

            # Mock thread activity check to return new activity
            mock_dependencies["channel_msg_ops"].check_recent_thread_activity.return_value = (
                True,
                "200000",
                ["thread1", "thread2"],  # Has activity, new timestamp, active threads
            )

            # Mock JIRA (no updates)
            mock_dependencies["channel_operations"].get_channel_details.return_value = {
                "jira_ticket": ""
            }

            result = await generator.check_for_activity("C123456", {})

            assert result["has_activity"] is True
            assert result["has_thread_activity"] is True
            assert result["has_new_messages"] is False
            assert result["latest_thread_ts"] == "200000"

    @pytest.mark.asyncio
    async def test_activity_check_updates_all_timestamps(self, mock_dependencies):
        """Test that both message and thread timestamps are tracked."""
        generator = AutoStatusGenerator(**mock_dependencies)

        # Mock channel details
        mock_dependencies["channel_operations"].query_ops.get_channel_details.return_value = {
            "auto_status_last_message_ts": "100000",
            "auto_status_last_thread_ts": "100000",
            "auto_status_last_jira_comment_ts": "0",
        }

        with patch("ketchup_status_updater.status_generator.MessagePreparer") as mock_preparer:

            # Mock new messages and thread activity
            preparer_instance = MagicMock()
            preparer_instance.prepare_messages_for_auto_status = AsyncMock(
                return_value=(
                    "New messages",
                    {
                        "latest_ts": "150000",
                        "has_channel_messages": True,
                        "has_thread_activity": True,
                    },
                )
            )
            mock_preparer.return_value = preparer_instance

            # Mock thread activity
            mock_dependencies["channel_msg_ops"].check_recent_thread_activity.return_value = (
                True,
                "200000",
                [],  # Has activity, new timestamp, no specific threads
            )

            # Mock JIRA
            mock_dependencies["channel_operations"].get_channel_details.return_value = {
                "jira_ticket": ""
            }

            result = await generator.check_for_activity("C123456", {})

            assert result["has_activity"] is True
            assert result["has_new_messages"] is True
            assert result["has_thread_activity"] is True
            assert result["latest_message_ts"] == "150000"
            assert result["latest_thread_ts"] == "200000"
