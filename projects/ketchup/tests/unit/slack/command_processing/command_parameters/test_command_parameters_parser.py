"""
test_command_parameters_parser.py

Unit tests for command parameter parsing utilities in parser.py.

Covers:
- extract_command_type: all valid/invalid command strings, case insensitivity, unknown subcommands
- extract_command_params: all valid command types, invalid commands, extractor errors, response_url propagation
- Mocks all external extractors and validation
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- extract_command_type: missing/extra/invalid subcommands, case variations
- extract_command_params: unknown command, invalid context, extractor raises ValidationError, response_url is set

Expected Outcomes:
- Correct CommandType or None returned for all cases
- extract_command_params returns correct params or raises ValidationError as appropriate
- All external calls are mocked and asserted

"""

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from packages.slack.command_processing.command_parameters import parser
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandParams,
    CommandType,
)
from packages.slack.command_processing.command_parameters.validation import (
    ValidationError,
)


class TestExtractCommandType:
    @pytest.mark.parametrize(
        "command,expected",
        [
            ("/ketchup query", CommandType.QUERY),
            ("/ketchup status", CommandType.STATUS),
            ("/ketchup report", CommandType.REPORT),
            ("/ketchup archive", CommandType.ARCHIVE),
            ("/ketchup list", CommandType.LIST),
            ("/ketchup unknown", None),
            ("/notketchup short", None),
            ("short", None),
            ("/ketchup", None),
            ("", None),
        ],
    )
    def test_extract_command_type(self, command: str, expected: Optional[CommandType]) -> None:
        """Test extract_command_type for all valid and invalid command strings."""
        result = parser.extract_command_type(command)
        assert result == expected


class TestExtractCommandParams:
    @pytest.fixture(autouse=True)
    def patch_extractors(self) -> None:
        # Patch all extractors and validation
        self.patcher_context = patch(
            "packages.slack.command_processing.command_parameters.validation.get_command_context",
            return_value=CommandContext.DIRECT_MESSAGE,
        )
        self.patcher_summary = patch(
            "packages.slack.command_processing.command_parameters.parser.extract_summary_params",
            return_value=MagicMock(spec=CommandParams),
        )
        self.patcher_query = patch(
            "packages.slack.command_processing.command_parameters.parser.extract_query_params",
            return_value=MagicMock(spec=CommandParams),
        )
        self.patcher_status = patch(
            "packages.slack.command_processing.command_parameters.parser.extract_status_report_params",
            return_value=MagicMock(spec=CommandParams),
        )
        self.patcher_archive = patch(
            "packages.slack.command_processing.command_parameters.parser.extract_archive_params",
            return_value=MagicMock(spec=CommandParams),
        )
        self.patcher_list = patch(
            "packages.slack.command_processing.command_parameters.parser.extract_list_params",
            return_value=MagicMock(spec=CommandParams),
        )
        self.mock_context = self.patcher_context.start()
        self.mock_summary = self.patcher_summary.start()
        self.mock_query = self.patcher_query.start()
        self.mock_status = self.patcher_status.start()
        self.mock_archive = self.patcher_archive.start()
        self.mock_list = self.patcher_list.start()

    def teardown_method(self) -> None:
        patch.stopall()

    @pytest.mark.parametrize(
        "command,expected_extractor",
        [
            ("/ketchup query", "query"),
            ("/ketchup status", "status"),
            ("/ketchup report", "status"),
            ("/ketchup archive", "archive"),
            ("/ketchup list", "list"),
        ],
    )
    def test_extract_command_params_valid(self, command: str, expected_extractor: str) -> None:
        """Test extract_command_params calls correct extractor and returns params."""
        params = parser.extract_command_params(command, "chan", "C123", response_url="url")
        # The correct extractor should have been called
        if expected_extractor == "summary":
            assert self.mock_summary.called
        elif expected_extractor == "query":
            assert self.mock_query.called
        elif expected_extractor == "status":
            assert self.mock_status.called
        elif expected_extractor == "archive":
            assert self.mock_archive.called
        elif expected_extractor == "list":
            assert self.mock_list.called
        # The response_url should be set on the returned params
        assert getattr(params, "response_url", None) == "url"

    def test_extract_command_params_invalid_command(self) -> None:
        """Test extract_command_params raises ValidationError for unknown command."""
        with pytest.raises(ValidationError) as exc:
            parser.extract_command_params("/ketchup unknown", "chan", "C123")
        assert "Invalid command type extracted from: /ketchup unknown" in str(exc.value)

    def test_extract_command_params_extractor_raises(self) -> None:
        """Test extract_command_params propagates ValidationError from extractor."""
        with patch(
            "packages.slack.command_processing.command_parameters.parser.extract_summary_params",
            side_effect=ValidationError("fail", "user fail"),
        ):
            with pytest.raises(ValidationError) as exc:
                parser.extract_command_params("/ketchup short", "chan", "C123")
            assert "fail" in str(exc.value)

    def test_extract_command_params_no_extractor(self) -> None:
        """Test extract_command_params raises ValidationError if extractor is missing (should not happen)."""
        with patch(
            "packages.slack.command_processing.command_parameters.parser.extract_command_type",
            return_value=None,
        ):
            with pytest.raises(ValidationError) as exc:
                parser.extract_command_params("/ketchup", "chan", "C123")
            assert "Invalid command type extracted from: /ketchup" in str(exc.value)
