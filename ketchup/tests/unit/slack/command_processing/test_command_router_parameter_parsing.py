"""
test_command_router_parameter_parsing.py

Targeted unit tests for the parameter parsing scenario fixes:
1. Channel ID is never None in command logging (defaults to empty string)
2. Command logging handles missing channel_id gracefully
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.db.operations.command_tracking_operations import CommandTrackingOperations
from packages.slack.command_processing.command_parameters.models import (
    CommandType,
)
from packages.slack.command_processing.command_router import CommandRouter


@pytest.mark.asyncio
class TestCommandRouterParameterParsing:
    """Test parameter parsing fixes in command router."""

    def setup_method(self) -> None:
        """Set up test dependencies."""
        self.mock_handlers = {
            "analyze": AsyncMock(),
            "list": AsyncMock(),
            "status": AsyncMock(),
        }
        self.mock_posting_handler = AsyncMock()
        self.mock_user_verifier = MagicMock()
        self.mock_user_verifier.validate_user_id = AsyncMock(return_value=True)
        self.mock_command_tracking = AsyncMock(spec=CommandTrackingOperations)
        self.mock_user_store = MagicMock()
        self.mock_user_store.get_user = AsyncMock(return_value=None)

        self.router = CommandRouter(
            command_handlers=self.mock_handlers,
            slack_posting_handler=self.mock_posting_handler,
            user_verifier=self.mock_user_verifier,
            user_store=self.mock_user_store,
            command_tracking_ops=self.mock_command_tracking,
        )

    # Note: analyze command test was removed as part of LangChain cleanup

    @patch(
        "packages.slack.command_processing.command_router.verify_and_extract_command",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.command_processing.command_router.extract_command_details",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.command_processing.command_router.log_command_execution",
        new_callable=AsyncMock,
    )
    async def test_channel_id_fallback_to_incoming_channel(
        self,
        mock_log_execution: AsyncMock,
        mock_extract_details: AsyncMock,
        mock_verify: AsyncMock,
    ) -> None:
        """Test that channel_id falls back to incoming_channel when not in command details."""
        # Create list command params (no target channel)
        params = MagicMock()
        params.command_type = CommandType.LIST
        params.original_command = "/ketchup list"

        # extract_command_details doesn't include channel_id
        mock_extract_details.return_value = {
            "command_type": "list",
            # No channel_id key
            "command_text": params.original_command,
        }

        mock_verify.return_value = params
        self.mock_handlers["list"].process_list_params.return_value = {"ok": True}

        # Body with channel info
        body = {
            "command": ["/ketchup"],
            "text": ["list"],
            "channel_id": ["C12345"],  # Public channel
            "channel_name": ["general"],
            "user_id": ["U123"],
            "user_name": ["testuser"],
            "response_url": ["https://hooks.slack.com/response"],
        }

        # Execute command
        await self.router.route_command(body)

        # Verify log_command_execution was called with incoming channel
        mock_log_execution.assert_called_once()
        call_args = mock_log_execution.call_args[1]
        assert call_args["channel_id"] == "C12345"  # Should use incoming channel
        assert call_args["command_type"] == "list"

    @patch(
        "packages.slack.command_processing.command_router.verify_and_extract_command",
        new_callable=AsyncMock,
    )
    async def test_command_logging_handles_exceptions_gracefully(
        self,
        mock_verify: AsyncMock,
    ) -> None:
        """Test that command logging exceptions don't break the main flow."""
        # Create command params
        params = MagicMock()
        params.command_type = CommandType.LIST
        params.original_command = "/ketchup list"

        mock_verify.return_value = params
        self.mock_handlers["list"].process_list_params.return_value = {"ok": True}

        # Make command tracking raise an exception
        self.mock_command_tracking.log_command.side_effect = Exception("DynamoDB error")

        # Body with channel info
        body = {
            "command": ["/ketchup"],
            "text": ["list"],
            "channel_id": ["C12345"],
            "channel_name": ["general"],
            "user_id": ["U123"],
            "user_name": ["testuser"],
            "response_url": ["https://hooks.slack.com/response"],
        }

        # Execute command - should not raise exception
        result = await self.router.route_command(body)

        # Verify command still executed successfully
        assert result == {"ok": True}
        self.mock_handlers["list"].process_list_params.assert_called_once()

    @patch(
        "packages.slack.command_processing.command_router.verify_and_extract_command",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.command_processing.command_router.extract_command_details",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.command_processing.command_router.log_command_execution",
        new_callable=AsyncMock,
    )
    async def test_status_command_with_channel_reference(
        self,
        mock_log_execution: AsyncMock,
        mock_extract_details: AsyncMock,
        mock_verify: AsyncMock,
    ) -> None:
        """Test status command with channel reference gets proper channel_id."""
        # Create status command params with target channel
        params = MagicMock()
        params.command_type = CommandType.STATUS
        params.report_type = "status"
        params.target_channel_id = "C999888777"  # The actual channel being queried
        params.original_command = "/ketchup status #some-channel"

        mock_extract_details.return_value = {
            "command_type": "status",
            "channel_id": "C999888777",  # Extracted target channel
            "command_text": params.original_command,
        }

        mock_verify.return_value = params
        self.mock_handlers["status"].process_status_request.return_value = {"ok": True}

        # Body shows command was run in DM
        body = {
            "command": ["/ketchup"],
            "text": ["status #some-channel"],
            "channel_id": ["D0840EX80R5"],  # DM channel where command was run
            "channel_name": ["directmessage"],
            "user_id": ["U123"],
            "user_name": ["testuser"],
            "response_url": ["https://hooks.slack.com/response"],
        }

        # Execute command
        await self.router.route_command(body)

        # Verify log_command_execution was called with target channel, not DM channel
        mock_log_execution.assert_called_once()
        call_args = mock_log_execution.call_args[1]
        assert call_args["channel_id"] == "C999888777"  # Should use target channel
        assert call_args["command_type"] == "status"
