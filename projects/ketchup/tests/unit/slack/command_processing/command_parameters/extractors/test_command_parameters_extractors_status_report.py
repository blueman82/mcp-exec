"""
test_command_parameters_extractors_status_report.py

Unit tests for extractors/status_report.py (extract_status_report_params).

Covers:
- extract_status_report_params: DM and public channel logic, all error branches
- All logic branches and error handling
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- DM: missing channel ID, invalid channel ID, valid
- Public: too many arguments, valid

Expected Outcomes:
- Returns StatusReportCommandParams for valid input
- Raises ValidationError for all invalid input cases

"""

import pytest

from packages.slack.command_processing.command_parameters.extractors.status_report import (
    extract_status_report_params,
)
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    StatusReportCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)


class TestExtractStatusReportParams:
    def test_dm_missing_channel_id(self) -> None:
        """Test DM: raises ValidationError if channel ID is missing."""
        with pytest.raises(ValidationError) as exc:
            extract_status_report_params("/ketchup status", CommandContext.DIRECT_MESSAGE, "C123")
        assert "Missing channel parameter" in exc.value.message

    def test_dm_invalid_channel_id(self) -> None:
        """Test DM: raises ValidationError if channel ID is invalid."""
        with pytest.raises(ValidationError) as exc:
            extract_status_report_params(
                "/ketchup status notachannel", CommandContext.DIRECT_MESSAGE, "C123"
            )
        assert "Invalid channel format:" in exc.value.message

    def test_dm_valid(self) -> None:
        """Test DM: returns StatusReportCommandParams for valid input."""
        params = extract_status_report_params(
            "/ketchup status C12345678", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, StatusReportCommandParams)
        assert params.command_type == CommandType.STATUS
        assert params.target_channel_id == "C12345678"
        assert params.report_type == "status"

    def test_public_too_many_arguments(self) -> None:
        """Test public: raises ValidationError if too many arguments are provided."""
        with pytest.raises(ValidationError) as exc:
            extract_status_report_params(
                "/ketchup status C12345678", CommandContext.PUBLIC_CHANNEL, "C123"
            )
        assert (
            "too many arguments" in exc.value.message.lower()
            or "without additional arguments" in exc.value.user_message
        )

    def test_public_valid(self) -> None:
        """Test public: returns StatusReportCommandParams for valid input."""
        params = extract_status_report_params(
            "/ketchup status", CommandContext.PUBLIC_CHANNEL, "C123"
        )
        assert isinstance(params, StatusReportCommandParams)
        assert params.command_type == CommandType.STATUS
        assert params.target_channel_id == "C123"
        assert params.report_type == "status"

    def test_dm_channel_mention_valid(self) -> None:
        """Test DM: accepts valid channel mention format."""
        mention = "<#C12345678|general>"
        params = extract_status_report_params(
            f"/ketchup status {mention}", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, StatusReportCommandParams)
        assert params.command_type == CommandType.STATUS
        assert params.target_channel_id == mention  # Stored as-is, resolved later
        assert params.report_type == "status"

    def test_dm_channel_name_valid(self) -> None:
        """Test DM: accepts valid channel name format."""
        channel_name = "#general"
        params = extract_status_report_params(
            f"/ketchup status {channel_name}", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, StatusReportCommandParams)
        assert params.command_type == CommandType.STATUS
        assert params.target_channel_id == channel_name  # Stored as-is, resolved later
        assert params.report_type == "status"

    def test_dm_group_channel_id_valid(self) -> None:
        """Test DM: accepts valid group channel ID format."""
        group_id = "G12345678"
        params = extract_status_report_params(
            f"/ketchup status {group_id}", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, StatusReportCommandParams)
        assert params.command_type == CommandType.STATUS
        assert params.target_channel_id == group_id
        assert params.report_type == "status"

    def test_dm_real_world_mention(self) -> None:
        """Test DM: accepts real-world channel mention format."""
        mention = "<#C08U5S51Z4N|sit_room_202505280031_acs_stena_76893>"
        params = extract_status_report_params(
            f"/ketchup status {mention}", CommandContext.DIRECT_MESSAGE, "C123"
        )
        assert isinstance(params, StatusReportCommandParams)
        assert params.command_type == CommandType.STATUS
        assert params.target_channel_id == mention  # Stored as-is, resolved later
        assert params.report_type == "status"

    def test_dm_invalid_channel_format_comprehensive(self) -> None:
        """Test DM: rejects various invalid channel formats."""
        invalid_formats = [
            "notachannel",  # No prefix
            "D12345678",  # DM channel (not supported)
            "C123",  # Too short
            "C123456789012",  # Too long
            "#",  # Just hash
            "<#C12345678>",  # Missing pipe and name
            "<C12345678|name>",  # Missing hash
            "#General",  # Uppercase in name
            "#-test",  # Invalid name start
        ]

        for invalid_format in invalid_formats:
            with pytest.raises(ValidationError) as exc:
                extract_status_report_params(
                    f"/ketchup status {invalid_format}",
                    CommandContext.DIRECT_MESSAGE,
                    "C123",
                )
            assert "Invalid channel" in exc.value.message or "channel format" in exc.value.message
