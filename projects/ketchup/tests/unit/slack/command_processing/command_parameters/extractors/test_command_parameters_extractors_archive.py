"""
test_command_parameters_extractors_archive.py

Unit tests for extractors/archive.py (extract_archive_params).

Covers:
- extract_archive_params: DM logic, all error branches
- All logic branches and error handling
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- Not DM context (public channel)
- Missing days parameter
- Non-numeric days
- Days out of range (0, 181)
- Valid days (1, 180)

Expected Outcomes:
- Returns ArchiveCommandParams for valid input
- Raises ValidationError for all invalid input cases

"""

import pytest

from packages.slack.command_processing.command_parameters.extractors.archive import (
    extract_archive_params,
)
from packages.slack.command_processing.command_parameters.models import (
    ArchiveCommandParams,
    CommandContext,
    CommandType,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)


class TestExtractArchiveParams:
    def test_not_dm_context(self) -> None:
        """Test raises ValidationError if not in DM context."""
        with pytest.raises(ValidationError) as exc:
            extract_archive_params("/ketchup archive 7", CommandContext.PUBLIC_CHANNEL)
        assert "only available in direct messages" in exc.value.user_message

    def test_missing_days(self) -> None:
        """Test raises ValidationError if days parameter is missing."""
        with pytest.raises(ValidationError) as exc:
            extract_archive_params("/ketchup archive", CommandContext.DIRECT_MESSAGE)
        assert "Missing days parameter" in exc.value.message

    def test_non_numeric_days(self) -> None:
        """Test raises ValidationError if days is not a number."""
        with pytest.raises(ValidationError) as exc:
            extract_archive_params("/ketchup archive foo", CommandContext.DIRECT_MESSAGE)
        assert "not a number" in exc.value.message

    @pytest.mark.parametrize("days", [0, 181])
    def test_days_out_of_range(self, days: int) -> None:
        """Test raises ValidationError if days is out of range."""
        with pytest.raises(ValidationError) as exc:
            extract_archive_params(f"/ketchup archive {days}", CommandContext.DIRECT_MESSAGE)
        assert "must be between 1 and 180" in exc.value.user_message

    @pytest.mark.parametrize("days", [1, 180])
    def test_valid_days(self, days: int) -> None:
        """Test returns ArchiveCommandParams for valid days."""
        params = extract_archive_params(f"/ketchup archive {days}", CommandContext.DIRECT_MESSAGE)
        assert isinstance(params, ArchiveCommandParams)
        assert params.command_type == CommandType.ARCHIVE
        assert params.archive_days == days
