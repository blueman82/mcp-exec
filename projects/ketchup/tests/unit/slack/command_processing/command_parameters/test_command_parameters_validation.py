"""
test_command_parameters_validation.py

Unit tests for command parameter validation utilities in validation.py.

Covers:
- ValidationError: initialization, attributes, string representation
- get_command_context: all possible channel name inputs, edge cases
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- ValidationError: correct assignment of message and user_message
- get_command_context: directmessage, None, empty string, other values

Expected Outcomes:
- ValidationError behaves as expected for all arguments
- get_command_context returns correct CommandContext for all cases

"""

import pytest

from packages.slack.command_processing.command_parameters.models import CommandContext
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
    get_command_context,
)


class TestValidationError:
    def test_init_and_attributes(self) -> None:
        """Test ValidationError initialization and attributes."""
        err = ValidationError("tech msg", "user msg")
        assert err.message == "tech msg"
        assert err.user_message == "user msg"
        assert str(err) == "tech msg"


class TestGetCommandContext:
    @pytest.mark.parametrize(
        "channel_name,expected",
        [
            ("directmessage", CommandContext.DIRECT_MESSAGE),
            (None, CommandContext.PUBLIC_CHANNEL),
            ("", CommandContext.PUBLIC_CHANNEL),
            ("random", CommandContext.PUBLIC_CHANNEL),
        ],
    )
    def test_get_command_context(self, channel_name: str, expected: CommandContext) -> None:
        """Test get_command_context for all possible channel name inputs."""
        result = get_command_context(channel_name)
        assert result == expected
