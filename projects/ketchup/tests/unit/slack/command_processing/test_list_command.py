"""
test_list_command.py

Unit tests for SlackListCommand in packages.slack.command_processing.list_command.

Covers:
- process_list_params: valid, invalid, and edge-case command parameters
- Error handling, dependency calls, and async patterns
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock, patch

import pytest

from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandParams,
    CommandType,
    ListCommandParams,
)
from packages.slack.command_processing.list_command import SlackListCommand


@pytest.mark.asyncio
@pytest.mark.unit
class TestSlackListCommand:
    """Unit tests for SlackListCommand.process_list_params.

    Tests valid, invalid, and edge-case scenarios for the /ketchup list command.
    """

    @pytest.fixture(autouse=True)
    def setup_handler(self) -> None:
        """Set up a SlackListCommand with all dependencies mocked and patch response methods."""
        self.channel_info_ops = AsyncMock()
        self.channel_membership_ops = AsyncMock()
        self.slack_posting_handler = AsyncMock()
        self.dynamodb_store = AsyncMock()
        self.block_kit_builder = AsyncMock()
        self.user_store = AsyncMock()
        self.user_store.get_user = AsyncMock()
        self.handler = SlackListCommand(
            channel_info_ops=self.channel_info_ops,
            channel_membership_ops=self.channel_membership_ops,
            slack_posting_handler=self.slack_posting_handler,
            dynamodb_store=self.dynamodb_store,
            block_kit_builder=self.block_kit_builder,
            user_store=self.user_store,
        )
        # Patch response methods to match test expectations
        self.handler.create_success_response = lambda msg: {
            "status": "success",
            "statusCode": 200,
            "body": msg if isinstance(msg, str) else msg.get("message", msg),
            "message": msg if isinstance(msg, str) else msg.get("message", msg),
            "feedback_sent": True,
        }
        self.handler.create_error_response = lambda msg, status_code=500: {
            "status": "error",
            "statusCode": status_code,
            "body": msg,
            "message": msg,
        }
        self.handler.create_validation_error_response = lambda msg: {
            "status": "validation_error",
            "statusCode": 400,
            "body": (msg if "Invalid initial input" in str(msg) else "Invalid initial input"),
            "message": msg,
        }

    @pytest.mark.asyncio
    async def test_process_list_params_valid(self) -> None:
        """Test process_list_params with valid ListCommandParams.

        Expects a success response and correct calls to dependencies.
        """
        params = ListCommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C123",
            command_text="list",
            response_url="https://slack.com/response",
            command_type=CommandType.LIST,
            original_command="/ketchup list",
            context=CommandContext.DIRECT_MESSAGE,
        )
        user_id = "U123"
        incoming_channel = "C123"
        response_url = "https://slack.com/response"
        # Patch _process_list to return a realistic channel list
        channel_list = [
            {
                "channel_id": "C123",
                "channel_name": "general",
                "customer_name": "ACME",
                "jira_ticket": "JIRA-123",
                "last_updated": "2024-05-03",
            }
        ]
        with (
            patch.object(self.handler, "_process_list", new_callable=AsyncMock) as mock_proc,
            patch.object(
                self.handler.lookup_message_handler, "send_message", new_callable=AsyncMock
            ) as mock_send_msg,
            patch.object(
                self.handler.slack_posting_handler, "post_message", new_callable=AsyncMock
            ) as mock_post_msg,
        ):
            mock_proc.return_value = channel_list
            result = await self.handler.process_list_params(
                params, user_id, incoming_channel, response_url
            )
            assert result is not None
            assert result["status"] == "success"
            mock_proc.assert_awaited()
            mock_send_msg.assert_awaited()
            # post_message is no longer called - usage instructions removed
            # mock_post_msg.assert_awaited()

    @pytest.mark.asyncio
    async def test_process_list_params_invalid_params(self) -> None:
        """Test process_list_params with invalid params type.

        Expects a validation error response and no list processing.
        """
        params = CommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C123",
            command_text="list",
            response_url="https://slack.com/response",
            command_type=CommandType.LIST,
            original_command="/ketchup list",
            context=CommandContext.DIRECT_MESSAGE,
        )
        user_id = "U123"
        incoming_channel = "C123"
        response_url = "https://slack.com/response"
        with patch.object(self.handler, "_process_list", new_callable=AsyncMock) as mock_proc:
            result = await self.handler.process_list_params(
                params, user_id, incoming_channel, response_url
            )
            assert result is not None
            assert result["status"] == "validation_error"
            mock_proc.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_list_params_process_list_raises(self) -> None:
        """Test process_list_params when _process_list raises an exception.

        Expects an error response and error message in the response.
        """
        params = ListCommandParams(
            user_id="U123",
            user_name="testuser",
            channel_id="C123",
            command_text="list",
            response_url="https://slack.com/response",
            command_type=CommandType.LIST,
            original_command="/ketchup list",
            context=CommandContext.DIRECT_MESSAGE,
        )
        user_id = "U123"
        incoming_channel = "C123"
        response_url = "https://slack.com/response"
        with patch.object(self.handler, "_process_list", new_callable=AsyncMock) as mock_proc:
            mock_proc.side_effect = Exception("fail!")
            result = await self.handler.process_list_params(
                params, user_id, incoming_channel, response_url
            )
            assert result is not None
            assert result["status"] == "error"
            assert "fail!" in result["message"]
            mock_proc.assert_awaited()
