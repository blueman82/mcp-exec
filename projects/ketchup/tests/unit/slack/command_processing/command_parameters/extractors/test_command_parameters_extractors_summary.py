"""
test_command_parameters_extractors_summary.py

Unit tests for extractors/summary.py (extract_summary_params).

Covers:
- extract_summary_params: DM and public channel logic, all error branches
- All logic branches and error handling
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- DM: missing channel ID, invalid channel ID, valid
- Public: too many arguments, valid

Expected Outcomes:
- Returns SummaryCommandParams for valid input
- Raises ValidationError for all invalid input cases

"""

import pytest

from packages.slack.command_processing.command_parameters.extractors.summary import (
    extract_summary_params,
)
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    SummaryCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)


class TestExtractSummaryParams:
    def test_dm_missing_channel_id(self) -> None:
        """Test DM: raises ValidationError if channel ID is missing."""
        with pytest.raises(ValidationError) as exc:
            extract_summary_params("/ketchup short", CommandContext.DIRECT_MESSAGE, "C123")
        assert "Missing channel ID" in exc.value.message

    def test_dm_invalid_channel_id(self) -> None:
        """Test DM: raises ValidationError if channel ID is invalid."""
        with pytest.raises(ValidationError) as exc:
            extract_summary_params(
                "/ketchup short notachannel", CommandContext.DIRECT_MESSAGE, "C123"
            )
        assert "Invalid channel format:" in exc.value.message

    def test_dm_valid(self) -> None:
        """Test DM: returns SummaryCommandParams for valid input."""
        params = extract_summary_params(
            "/ketchup short C12345678", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, SummaryCommandParams)
        assert params.command_type == CommandType.SHORT
        assert params.target_channel_id == "C12345678"
        assert params.summary_type == "short"

    def test_public_too_many_arguments(self) -> None:
        """Test public: raises ValidationError if too many arguments are provided."""
        with pytest.raises(ValidationError) as exc:
            extract_summary_params(
                "/ketchup short C12345678", CommandContext.PUBLIC_CHANNEL, "C123"
            )
        assert (
            "too many arguments" in exc.value.message.lower()
            or "without additional arguments" in exc.value.user_message
        )

    def test_public_valid(self) -> None:
        """Test public: returns SummaryCommandParams for valid input."""
        params = extract_summary_params("/ketchup short", CommandContext.PUBLIC_CHANNEL, "C123")
        assert isinstance(params, SummaryCommandParams)
        assert params.command_type == CommandType.SHORT
        assert params.target_channel_id == "C123"
        assert params.summary_type == "short"

    def test_dm_channel_mention_valid(self) -> None:
        """Test DM: accepts valid channel mention format."""
        mention = "<#C12345678|general>"
        params = extract_summary_params(
            f"/ketchup short {mention}", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, SummaryCommandParams)
        assert params.command_type == CommandType.SHORT
        assert params.target_channel_id == mention  # Stored as-is, resolved later
        assert params.summary_type == "short"

    def test_dm_channel_name_valid(self) -> None:
        """Test DM: accepts valid channel name format."""
        channel_name = "#general"
        params = extract_summary_params(
            f"/ketchup long {channel_name}", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, SummaryCommandParams)
        assert params.command_type == CommandType.LONG
        assert params.target_channel_id == channel_name  # Stored as-is, resolved later
        assert params.summary_type == "long"

    def test_dm_group_channel_valid(self) -> None:
        """Test DM: accepts valid group channel ID format."""
        group_id = "G12345678"
        params = extract_summary_params(
            f"/ketchup short {group_id}", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, SummaryCommandParams)
        assert params.command_type == CommandType.SHORT
        assert params.target_channel_id == group_id
        assert params.summary_type == "short"

    def test_dm_real_world_mention(self) -> None:
        """Test DM: accepts real-world channel mention format."""
        mention = "<#C08U5S51Z4N|sit_room_202505280031_acs_stena_76893>"
        params = extract_summary_params(
            f"/ketchup long {mention}", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, SummaryCommandParams)
        assert params.command_type == CommandType.LONG
        assert params.target_channel_id == mention  # Stored as-is, resolved later
        assert params.summary_type == "long"

    def test_dm_invalid_channel_formats_summary(self) -> None:
        """Test DM: rejects various invalid channel formats in summary context."""
        invalid_formats = [
            "notachannel",  # No prefix
            "D12345678",  # DM channel (not supported)
            "C123",  # Too short
            "#",  # Just hash
            "<#C12345678>",  # Missing pipe and name
            "#General",  # Uppercase in name
        ]

        for invalid_format in invalid_formats:
            with pytest.raises(ValidationError) as exc:
                extract_summary_params(
                    f"/ketchup short {invalid_format}",
                    CommandContext.DIRECT_MESSAGE,
                    "C123",
                )
            assert "Invalid channel" in exc.value.message or "channel format" in exc.value.message
