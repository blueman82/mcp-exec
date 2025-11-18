"""
Test for new channel verification fix.

This test ensures that new channels with "0" timestamp don't cause
API errors during verification and that first-run channels get status posts.
"""

import time
from unittest.mock import AsyncMock, Mock, patch

import orjson
import pytest

from ketchup_status_updater.processor import AutoStatusProcessor
from ketchup_status_updater.status_generator import AutoStatusGenerator

# Save reference to real orjson.dumps in case it gets mocked
_real_orjson_dumps = orjson.dumps


class TestNewChannelVerification:
    """Test verification for new channels with no prior activity."""

    @pytest.mark.asyncio
    async def test_verify_real_activity_new_channel_no_error(self):
        """Test that new channels with '0' timestamp don't cause API errors."""
        # Setup mocks
        mock_channel_ops = Mock()
        mock_channel_ops.query_ops.get_channel_details = AsyncMock(
            return_value={
                "channel_id": "C0959GWTN7Q",
                "channel_name": "test-new-channel",
                "jira_ticket": "TEST-123",
                "auto_status_last_run": 0,
            }
        )

        mock_channel_msg_ops = Mock()
        mock_channel_msg_ops.get_api_base_url = AsyncMock(
            return_value="https://slack.com/api"
        )
        mock_channel_msg_ops.headers = {"Authorization": "Bearer test"}
        mock_channel_msg_ops._bot_user_id = "U12345"
        mock_channel_msg_ops.check_recent_thread_activity = AsyncMock(
            return_value=(False, "0", set())
        )

        # Mock the API request to verify params
        api_params_captured = None

        async def mock_api_request(url, method, headers, params):
            nonlocal api_params_captured
            api_params_captured = params
            return {
                "body": _real_orjson_dumps(
                    {
                        "ok": True,
                        "messages": [
                            {
                                "user": "U99999",
                                "text": "Test message",
                                "ts": "1752231013.338099",
                            }
                        ],
                    }
                )
            }

        mock_channel_msg_ops._make_api_request = mock_api_request

        # Create generator
        generator = AutoStatusGenerator(
            db_store=Mock(),
            mcp_client=Mock(),
            secrets_manager=Mock(),
            slack_config=Mock(),
            openai_handler=Mock(),
            channel_info_ops=Mock(),
            channel_msg_ops=mock_channel_msg_ops,
            posting_handler=Mock(),
            channel_operations=mock_channel_ops,
        )

        # Test with new channel (all timestamps are "0")
        channel_config = {
            "auto_status_last_message_ts": "0",
            "auto_status_last_thread_ts": "0",
            "auto_status_last_jira_comment_ts": "0",
            "auto_status_last_run": 0,
        }

        # This should not raise an error
        result = await generator._verify_real_activity(
            channel_id="C0959GWTN7Q",
            channel_config=channel_config,
            original_last_message_ts="0",
            original_last_thread_ts="0",
            original_last_jira_ts="0",
        )

        # Verify behavior
        assert result is True  # Found activity
        assert api_params_captured is not None
        assert api_params_captured["channel"] == "C0959GWTN7Q"
        assert api_params_captured["limit"] == 10
        # Critical: oldest should NOT be in params when timestamp is "0"
        assert "oldest" not in api_params_captured

    @pytest.mark.asyncio
    async def test_verify_real_activity_existing_channel_preserves_oldest(self):
        """Test that existing channels still include oldest parameter."""
        # Setup mocks
        mock_channel_ops = Mock()
        mock_channel_ops.query_ops.get_channel_details = AsyncMock(
            return_value={
                "channel_id": "C123456",
                "channel_name": "test-existing-channel",
                "auto_status_last_run": 1752230000,
            }
        )

        mock_channel_msg_ops = Mock()
        mock_channel_msg_ops.get_api_base_url = AsyncMock(
            return_value="https://slack.com/api"
        )
        mock_channel_msg_ops.headers = {"Authorization": "Bearer test"}
        mock_channel_msg_ops._bot_user_id = "U12345"
        mock_channel_msg_ops.check_recent_thread_activity = AsyncMock(
            return_value=(False, "0", set())
        )

        # Mock the API request to verify params
        api_params_captured = None

        async def mock_api_request(url, method, headers, params):
            nonlocal api_params_captured
            api_params_captured = params
            return {"body": _real_orjson_dumps({"ok": True, "messages": []})}

        mock_channel_msg_ops._make_api_request = mock_api_request

        # Create generator
        generator = AutoStatusGenerator(
            db_store=Mock(),
            mcp_client=Mock(),
            secrets_manager=Mock(),
            slack_config=Mock(),
            openai_handler=Mock(),
            channel_info_ops=Mock(),
            channel_msg_ops=mock_channel_msg_ops,
            posting_handler=Mock(),
            channel_operations=mock_channel_ops,
        )

        # Test with existing channel (has valid timestamp)
        channel_config = {
            "auto_status_last_message_ts": "1752230000.123456",
            "auto_status_last_thread_ts": "0",
            "auto_status_last_jira_comment_ts": "0",
        }

        result = await generator._verify_real_activity(
            channel_id="C123456",
            channel_config=channel_config,
            original_last_message_ts="1752230000.123456",
        )

        # Verify behavior
        assert result is False  # No new activity
        assert api_params_captured is not None
        assert api_params_captured["channel"] == "C123456"
        assert api_params_captured["limit"] == 10
        # Critical: oldest SHOULD be included for existing channels (with 5-second buffer applied)
        assert "oldest" in api_params_captured
        assert api_params_captured["oldest"] == "1752229995.123456"  # 5 seconds subtracted for safety buffer

    @pytest.mark.asyncio
    async def test_first_run_channel_forces_status_post(self):
        """Test that channels without auto_status fields get status posted on first run."""
        # Setup channel data WITHOUT auto_status fields (simulating new channel)
        channel_data = {
            "channel_id": "C0959GWTN7Q",
            "channel_name": "test-new-channel",
            "jira_ticket": "TEST-123",
            "created_at": int(time.time()),
            # Note: No auto_status_last_message_ts field!
        }

        # Mock dependencies
        mock_channel_ops = Mock()
        mock_channel_ops.query_ops.get_channel_details = AsyncMock(
            return_value=channel_data
        )
        mock_channel_ops.update_channel_fields = AsyncMock()

        mock_channel_membership_ops = Mock()
        mock_channel_membership_ops.lookup_membership_of_channels = AsyncMock(
            return_value=[{"id": "C0959GWTN7Q", "name": "test-new-channel"}]
        )

        mock_channel_msg_ops = Mock()

        # Mock the message preparer to return some messages
        mock_openai_handler = Mock()
        mock_openai_handler.generate_response = AsyncMock(
            return_value={"success": True, "response": "Test status update"}
        )

        mock_posting_handler = Mock()
        mock_posting_handler.post_message = AsyncMock(
            return_value={"success": True, "ts": "1752231986.123456"}
        )

        # Create processor
        processor = AutoStatusProcessor(
            db_store=Mock(),
            mcp_client=Mock(),
            secrets_manager=Mock(),
            slack_config=Mock(),
            openai_handler=mock_openai_handler,
            channel_info_ops=Mock(),
            channel_msg_ops=mock_channel_msg_ops,
            posting_handler=mock_posting_handler,
            channel_operations=mock_channel_ops,
            channel_membership_ops=mock_channel_membership_ops,
            feature_service=Mock(),
        )

        # Mock activity check to return messages found but no "new" activity
        with patch.object(
            AutoStatusGenerator,
            "check_for_activity",
            return_value={
                "has_activity": False,  # No NEW activity
                "has_new_messages": False,
                "has_thread_activity": False,
                "has_jira_updates": False,
                "latest_message_ts": "1752231013.338099",  # But we found messages
                "latest_thread_ts": "0",
            },
        ):
            with patch.object(
                AutoStatusGenerator, "generate_and_post_status", return_value=True
            ) as mock_post:
                # Process the channel
                result = await processor._process_channel(channel_data)

                # Verify it posted status despite no "new" activity
                assert result
                mock_post.assert_called_once()

                # Verify it updated the timestamps
                mock_channel_ops.update_channel_fields.assert_called()
                calls = mock_channel_ops.update_channel_fields.call_args_list
                # Should have timestamp update call
                timestamp_call = [
                    c for c in calls if "auto_status_last_message_ts" in c[1]["updates"]
                ][0]
                assert (
                    timestamp_call[1]["updates"]["auto_status_last_message_ts"]
                    == 1752231013  # Converted to integer (decimal precision removed)
                )
