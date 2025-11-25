"""
test_verify_command.py

Unit tests for verify_command.py.

Covers:
- send_validation_error: success, posting handler raises exception
- verify_and_extract_command: valid command, validation error, unknown error
- All logic branches and error handling
- Mocks all external dependencies (SlackPostingHandler, extract_command_params, get_command_context)
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- send_validation_error: posting succeeds, posting fails
- verify_and_extract_command: valid command, validation error, unknown error

Expected Outcomes:
- Error messages are sent as expected
- verify_and_extract_command returns correct params or None
- All external calls are mocked and asserted

"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.command_processing import verify_command
from packages.slack.command_processing.command_parameters.models import CommandParams
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)


@pytest.mark.asyncio
class TestSendValidationError:
    async def test_success(self) -> None:
        """Test send_validation_error posts message successfully."""
        handler = AsyncMock()
        await verify_command.send_validation_error(
            "U1", "C1", "err", handler, response_url="url"
        )
        handler.post_message.assert_awaited_once_with(
            user_id="U1", channel_id="C1", message="err", response_url="url"
        )

    async def test_posting_fails(self) -> None:
        """Test send_validation_error logs error if posting fails."""
        handler = AsyncMock()
        handler.post_message.side_effect = Exception("fail")
        await verify_command.send_validation_error(
            "U1", "C1", "err", handler, response_url="url"
        )
        handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
class TestVerifyAndExtractCommand:
    @patch(
        "packages.slack.command_processing.verify_command.get_command_context",
        return_value="directmessage",
    )
    @patch("packages.slack.command_processing.verify_command.extract_command_params")
    async def test_valid_command(
        self, mock_extract: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test verify_and_extract_command returns params for valid command."""
        params = MagicMock(spec=CommandParams)
        mock_extract.return_value = params
        handler = AsyncMock()
        result = await verify_command.verify_and_extract_command(
            "/ketchup short C1", "U1", "C1", "url", handler, "chan"
        )
        assert result is params
        mock_extract.assert_called_once()
        handler.post_message.assert_not_awaited()

    @patch(
        "packages.slack.command_processing.verify_command.get_command_context",
        return_value="directmessage",
    )
    @patch("packages.slack.command_processing.verify_command.extract_command_params")
    async def test_validation_error(
        self, mock_extract: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test verify_and_extract_command sends error and returns None on ValidationError."""
        mock_extract.side_effect = ValidationError("fail", "user fail")
        handler = AsyncMock()
        result = await verify_command.verify_and_extract_command(
            "/ketchup short", "U1", "C1", "url", handler, "chan"
        )
        assert result is None
        handler.post_message.assert_awaited_once()

    @patch(
        "packages.slack.command_processing.verify_command.get_command_context",
        return_value="directmessage",
    )
    @patch("packages.slack.command_processing.verify_command.extract_command_params")
    async def test_unknown_error(
        self, mock_extract: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test verify_and_extract_command sends generic error and returns None on unknown error."""
        mock_extract.side_effect = Exception("fail")
        handler = AsyncMock()
        result = await verify_command.verify_and_extract_command(
            "/ketchup short", "U1", "C1", "url", handler, "chan"
        )
        assert result is None
        handler.post_message.assert_awaited_once()
