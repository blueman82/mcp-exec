"""
test_command_parameters_extractors_query.py

Unit tests for extractors/query.py (extract_query_params).

Covers:
- extract_query_params: DM and public channel logic, all error branches
- All logic branches and error handling
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- DM: missing channel ID, invalid channel ID, missing question, valid
- Public: missing question, channel ID mistakenly included, valid

Expected Outcomes:
- Returns QueryCommandParams for valid input
- Raises ValidationError for all invalid input cases

"""

import pytest

from packages.slack.command_processing.command_parameters.extractors.query import (
    extract_query_params,
)
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    QueryCommandParams,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)


class TestExtractQueryParams:
    def test_dm_missing_channel_id(self) -> None:
        """Test DM: raises ValidationError if channel ID is missing."""
        with pytest.raises(ValidationError) as exc:
            extract_query_params(
                "/ketchup query", CommandContext.DIRECT_MESSAGE, "C123"
            )
        assert "Missing channel parameter" in exc.value.message

    def test_dm_invalid_channel_id(self) -> None:
        """Test DM: raises ValidationError if channel ID is invalid."""
        with pytest.raises(ValidationError) as exc:
            extract_query_params(
                "/ketchup query notachannel what happened?",
                CommandContext.DIRECT_MESSAGE,
                "C123",
            )
        assert "Invalid channel format:" in exc.value.message

    def test_dm_missing_question(self) -> None:
        """Test DM: raises ValidationError if question is missing."""
        with pytest.raises(ValidationError) as exc:
            extract_query_params(
                "/ketchup query C12345678", CommandContext.DIRECT_MESSAGE, "C123"
            )
        assert "Missing question" in exc.value.message

    def test_dm_valid(self) -> None:
        """Test DM: returns QueryCommandParams for valid input."""
        params = extract_query_params(
            "/ketchup query C12345678 What happened?",
            CommandContext.DIRECT_MESSAGE,
            "C123",
        )
        assert isinstance(params, QueryCommandParams)
        assert params.command_type == CommandType.QUERY
        assert params.channel_id == "C12345678"
        assert params.query_text == "What happened?"

    def test_public_missing_question(self) -> None:
        """Test public: raises ValidationError if question is missing."""
        with pytest.raises(ValidationError) as exc:
            extract_query_params(
                "/ketchup query", CommandContext.PUBLIC_CHANNEL, "C123"
            )
        assert "Missing question" in exc.value.message

    def test_public_channel_id_included(self) -> None:
        """Test public: raises ValidationError if channel ID is mistakenly included."""
        with pytest.raises(ValidationError) as exc:
            extract_query_params(
                "/ketchup query C12345678 What happened?",
                CommandContext.PUBLIC_CHANNEL,
                "C123",
            )
        assert (
            "should not be included" in exc.value.message
            or "without specifying a channel ID" in exc.value.user_message
        )

    def test_public_valid(self) -> None:
        """Test public: returns QueryCommandParams for valid input."""
        params = extract_query_params(
            "/ketchup query What happened?", CommandContext.PUBLIC_CHANNEL, "C123"
        )
        assert isinstance(params, QueryCommandParams)
        assert params.command_type == CommandType.QUERY
        assert params.channel_id == "C123"
        assert params.query_text == "What happened?"

    def test_dm_channel_mention_valid(self) -> None:
        """Test DM: accepts valid channel mention format."""
        mention = "<#C12345678|general>"
        params = extract_query_params(
            f"/ketchup query {mention} What happened?",
            CommandContext.DIRECT_MESSAGE,
            "C123",
        )
        assert isinstance(params, QueryCommandParams)
        assert params.command_type == CommandType.QUERY
        assert params.channel_id == mention  # Stored as-is, resolved later
        assert params.query_text == "What happened?"

    def test_dm_channel_name_valid(self) -> None:
        """Test DM: accepts valid channel name format."""
        channel_name = "#general"
        params = extract_query_params(
            f"/ketchup query {channel_name} What happened?",
            CommandContext.DIRECT_MESSAGE,
            "C123",
        )
        assert isinstance(params, QueryCommandParams)
        assert params.command_type == CommandType.QUERY
        assert params.channel_id == channel_name  # Stored as-is, resolved later
        assert params.query_text == "What happened?"

    def test_dm_group_channel_valid(self) -> None:
        """Test DM: accepts valid group channel ID format."""
        group_id = "G12345678"
        params = extract_query_params(
            f"/ketchup query {group_id} What happened?",
            CommandContext.DIRECT_MESSAGE,
            "C123",
        )
        assert isinstance(params, QueryCommandParams)
        assert params.command_type == CommandType.QUERY
        assert params.channel_id == group_id
        assert params.query_text == "What happened?"

    def test_dm_real_world_mention(self) -> None:
        """Test DM: accepts real-world channel mention format."""
        mention = "<#C08U5S51Z4N|sit_room_202505280031_acs_stena_76893>"
        params = extract_query_params(
            f"/ketchup query {mention} What was the root cause?",
            CommandContext.DIRECT_MESSAGE,
            "C123",
        )
        assert isinstance(params, QueryCommandParams)
        assert params.command_type == CommandType.QUERY
        assert params.channel_id == mention  # Stored as-is, resolved later
        assert params.query_text == "What was the root cause?"

    def test_dm_complex_query_with_mention(self) -> None:
        """Test DM: handles complex multi-word queries with channel mentions."""
        mention = "<#C12345678|general>"
        query = "What happened between 2pm and 4pm yesterday?"
        params = extract_query_params(
            f"/ketchup query {mention} {query}",
            CommandContext.DIRECT_MESSAGE,
            "C123",
        )
        assert isinstance(params, QueryCommandParams)
        assert params.command_type == CommandType.QUERY
        assert params.channel_id == mention
        assert params.query_text == query

    def test_dm_invalid_channel_formats_query(self) -> None:
        """Test DM: rejects various invalid channel formats in query context."""
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
                extract_query_params(
                    f"/ketchup query {invalid_format} What happened?",
                    CommandContext.DIRECT_MESSAGE,
                    "C123",
                )
            assert (
                "Invalid channel" in exc.value.message
                or "channel format" in exc.value.message
            )
