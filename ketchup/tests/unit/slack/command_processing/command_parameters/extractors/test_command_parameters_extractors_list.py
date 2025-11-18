"""
test_command_parameters_extractors_list.py

Unit tests for extractors/list.py (extract_list_params).

Covers:
- extract_list_params: valid command, wrong context, too many arguments
- All logic branches and error handling
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- Valid: /ketchup list in DM context
- Invalid: /ketchup list in public channel
- Invalid: /ketchup list with extra arguments

Expected Outcomes:
- Returns ListCommandParams for valid input
- Raises ValidationError for invalid context or too many arguments

"""

import pytest

from packages.slack.command_processing.command_parameters.extractors.list import (
    extract_list_params,
)
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    ListCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)


class TestExtractListParams:
    def test_valid_list_command(self) -> None:
        """Test extract_list_params returns ListCommandParams for valid DM command."""
        params = extract_list_params("/ketchup list", CommandContext.DIRECT_MESSAGE)
        assert isinstance(params, ListCommandParams)
        assert params.command_type == CommandType.LIST
        assert params.original_command == "/ketchup list"
        assert params.context == CommandContext.DIRECT_MESSAGE
        assert params.list_type == "all"

    def test_invalid_context(self) -> None:
        """Test extract_list_params raises ValidationError for public channel context."""
        with pytest.raises(ValidationError) as exc:
            extract_list_params("/ketchup list", CommandContext.PUBLIC_CHANNEL)
        assert "only available in direct messages" in str(exc.value.user_message)

    def test_too_many_arguments(self) -> None:
        """Test extract_list_params raises ValidationError for extra arguments."""
        with pytest.raises(ValidationError) as exc:
            extract_list_params("/ketchup list extra", CommandContext.DIRECT_MESSAGE)
        assert "without additional arguments" in str(exc.value.user_message)
