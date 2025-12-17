"""
Test activity source indicators flow in status generator.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_unified_scheduler.services.status.generator import AutoStatusGenerator


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for AutoStatusGenerator."""
    return {
        "db_store": AsyncMock(),
        "mcp_client": AsyncMock(),
        "secrets_manager": AsyncMock(),
        "slack_config": MagicMock(),
        "openai_handler": AsyncMock(),
        "channel_info_ops": AsyncMock(),  # Added missing parameter
        "channel_msg_ops": AsyncMock(),
        "posting_handler": AsyncMock(),
        "channel_operations": AsyncMock(),
    }


class TestActivityIndicatorsFlow:
    """Test activity source indicators through the full flow."""

    @pytest.mark.asyncio
    async def test_jira_only_activity_flow(self, mock_dependencies):
        """Test when only JIRA has new activity."""
        generator = AutoStatusGenerator(**mock_dependencies)

        # Mock MessagePreparer directly
        with patch("ketchup_unified_scheduler.services.status.generator.MessagePreparer") as mock_preparer:

            # Mock MessagePreparer to return no new messages
            preparer_instance = MagicMock()
            preparer_instance.prepare_messages_for_auto_status = AsyncMock(
                return_value=(
                    "No messages found",
                    {
                        "latest_ts": "100000",
                        "has_channel_messages": False,
                        "has_thread_activity": False,
                    },
                )
            )
            mock_preparer.return_value = preparer_instance

            # Mock channel details
            mock_dependencies["channel_operations"].get_channel_details.return_value = {
                "jira_ticket": "CPGNREQ-12345",
                "customer_name": "TestCorp",
            }

            # Mock JIRA methods
            generator._fetch_jira_comments_raw = AsyncMock(
                return_value="[2025-01-07] User: Test JIRA comment"
            )
            generator._get_latest_jira_comment_timestamp = AsyncMock(
                return_value="2025-01-07T10:00:00"
            )
            generator._generate_ai_response = AsyncMock(
                return_value="Overview: JIRA updates received.\n\nWhat's been done / What's next:\n• Item 1\n• Item 2\n• Item 3\n• Item 4"
            )
            generator._generate_status_update_id = MagicMock(return_value="123_abc")
            generator._verify_real_activity = AsyncMock(return_value=True)
            generator._post_to_slack_public = AsyncMock(
                return_value={
                    "success": True,
                    "message_ts": "123",
                    "status_update_id": "123_abc",
                }
            )

            # Execute
            await generator.generate_and_post_status(
                channel_id="C123456",
                channel_name="test-channel",
                channel_config={
                    "auto_status_last_message_ts": "100000",
                    "auto_status_last_jira_comment_ts": "2025-01-06T10:00:00",
                },
            )

            # Verify the AI was called with JIRA-specific instructions
            ai_call_args = generator._generate_ai_response.call_args
            user_prompt = ai_call_args[1]["user_prompt"]
            assert (
                "While there are no new Slack messages, there ARE new JIRA comments" in user_prompt
            )
            assert (
                "Your Overview MUST mention that this update is based on JIRA activity"
                in user_prompt
            )

            # Verify the posted message includes JIRA indicator
            post_call_args = generator._post_to_slack_public.call_args
            posted_content = post_call_args[0][1]  # Second positional arg is content
            assert ":jira-logo:" in posted_content
            assert ":slack:" not in posted_content  # Should NOT have Slack indicator
            assert "Activity source: :jira-logo:" in posted_content

    @pytest.mark.asyncio
    async def test_both_sources_activity_flow(self, mock_dependencies):
        """Test when both Slack and JIRA have new activity."""
        generator = AutoStatusGenerator(**mock_dependencies)

        # Mock MessagePreparer directly
        with patch("ketchup_unified_scheduler.services.status.generator.MessagePreparer") as mock_preparer:

            # Mock MessagePreparer to return new messages
            preparer_instance = MagicMock()
            preparer_instance.prepare_messages_for_auto_status = AsyncMock(
                return_value=(
                    "New Slack messages here",
                    {
                        "latest_ts": "200000",
                        "has_channel_messages": True,
                        "has_thread_activity": False,
                    },
                )
            )
            mock_preparer.return_value = preparer_instance

            # Mock channel operations
            mock_dependencies["channel_operations"].get_channel_details.return_value = {
                "jira_ticket": "CPGNREQ-12345",
                "customer_name": "TestCorp",
            }
            # Mock other methods
            generator._fetch_jira_comments_raw = AsyncMock(
                return_value="[2025-01-07] User: Test JIRA comment"
            )
            generator._get_latest_jira_comment_timestamp = AsyncMock(
                return_value="2025-01-07T10:00:00"
            )
            generator._generate_ai_response = AsyncMock(
                return_value="Overview: Updates from multiple sources.\n\nWhat's been done / What's next:\n• Item 1\n• Item 2\n• Item 3\n• Item 4"
            )
            generator._generate_status_update_id = MagicMock(return_value="123_abc")
            generator._verify_real_activity = AsyncMock(return_value=True)
            generator._post_to_slack_public = AsyncMock(
                return_value={
                    "success": True,
                    "message_ts": "123",
                    "status_update_id": "123_abc",
                }
            )

            # Execute
            await generator.generate_and_post_status(
                channel_id="C123456",
                channel_name="test-channel",
                channel_config={
                    "auto_status_last_message_ts": "100000",
                    "auto_status_last_jira_comment_ts": "2025-01-06T10:00:00",
                },
            )

            # Verify the AI was called with both-sources instructions
            ai_call_args = generator._generate_ai_response.call_args
            user_prompt = ai_call_args[1]["user_prompt"]
            assert (
                "There are both new Slack messages" in user_prompt
                and "AND new JIRA comments" in user_prompt
            )

            # Verify the posted message includes both indicators
            post_call_args = generator._post_to_slack_public.call_args
            posted_content = post_call_args[0][1]
            assert ":slack:" in posted_content
            assert ":jira-logo:" in posted_content
            assert "Activity source: :slack: :jira-logo:" in posted_content

    @pytest.mark.asyncio
    async def test_slack_only_activity_flow(self, mock_dependencies):
        """Test when only Slack has new activity."""
        generator = AutoStatusGenerator(**mock_dependencies)

        # Mock MessagePreparer directly
        with patch("ketchup_unified_scheduler.services.status.generator.MessagePreparer") as mock_preparer:

            # Mock MessagePreparer to return new messages
            preparer_instance = MagicMock()
            preparer_instance.prepare_messages_for_auto_status = AsyncMock(
                return_value=(
                    "New Slack messages here",
                    {
                        "latest_ts": "200000",
                        "has_channel_messages": True,
                        "has_thread_activity": False,
                    },
                )
            )
            mock_preparer.return_value = preparer_instance

            # Mock channel operations
            mock_dependencies["channel_operations"].get_channel_details.return_value = {
                "jira_ticket": "CPGNREQ-12345",
                "customer_name": "TestCorp",
            }
            # Mock JIRA to return no updates
            generator._fetch_jira_comments_raw = AsyncMock(return_value=None)
            generator._get_latest_jira_comment_timestamp = AsyncMock(
                return_value="2025-01-06T10:00:00"
            )  # Same as last time
            generator._generate_ai_response = AsyncMock(
                return_value="Overview: Slack activity detected.\n\nWhat's been done / What's next:\n• Item 1\n• Item 2\n• Item 3\n• Item 4"
            )
            generator._generate_status_update_id = MagicMock(return_value="123_abc")
            generator._verify_real_activity = AsyncMock(return_value=True)
            generator._post_to_slack_public = AsyncMock(
                return_value={
                    "success": True,
                    "message_ts": "123",
                    "status_update_id": "123_abc",
                }
            )

            # Execute
            await generator.generate_and_post_status(
                channel_id="C123456",
                channel_name="test-channel",
                channel_config={
                    "auto_status_last_message_ts": "100000",
                    "auto_status_last_jira_comment_ts": "2025-01-06T10:00:00",
                },
            )

            # Verify the posted message includes only Slack indicator
            post_call_args = generator._post_to_slack_public.call_args
            posted_content = post_call_args[0][1]
            assert ":slack:" in posted_content
            assert ":jira-logo:" not in posted_content
            assert "Activity source: :slack:" in posted_content
