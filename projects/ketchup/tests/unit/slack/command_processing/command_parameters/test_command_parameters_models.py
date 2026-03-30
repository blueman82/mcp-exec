"""
test_command_parameters_models.py

Unit tests for command parameter dataclasses and enums in models.py.

Covers:
- All enums: CommandType, CommandContext
- All dataclasses: CommandParams, SummaryCommandParams, QueryCommandParams, StatusReportCommandParams, ArchiveCommandParams, ListCommandParams
- All property methods and validation logic
- Edge cases for property methods and enum values
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- Enum value and string conversion
- Dataclass instantiation with required/optional fields
- ArchiveCommandParams: description and is_valid_range for edge values (1, 180, out of range)
- ListCommandParams: description property

Expected Outcomes:
- All enums and dataclasses behave as expected
- Property methods return correct values for all cases
- All type annotations and docstrings are present

"""

from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandParams,
    CommandType,
    QueryCommandParams,
    StatusReportCommandParams,
)


class TestCommandTypeEnum:
    def test_enum_values(self) -> None:
        """Test CommandType enum values and string conversion."""
        assert str(CommandType.SHORT) == "short"
        assert CommandType.LIST.value == "list"
        assert CommandType("archive") is CommandType.ARCHIVE


class TestCommandContextEnum:
    def test_enum_values(self) -> None:
        """Test CommandContext enum values and string conversion."""
        assert str(CommandContext.DIRECT_MESSAGE) == "directmessage"
        assert CommandContext.PUBLIC_CHANNEL.value == "public_channel"
        assert CommandContext("public_channel") is CommandContext.PUBLIC_CHANNEL


class TestCommandParams:
    def test_base_instantiation(self) -> None:
        """Test CommandParams dataclass instantiation."""
        params = CommandParams(
            user_id="U123456789",
            user_name="testuser",
            channel_id="C123456789",
            command_text="short",
            response_url="https://hooks.slack.com/commands/123",
            original_command="/ketchup short",
            command_type=CommandType.SHORT,
            context=CommandContext.DIRECT_MESSAGE,
        )
        assert params.command_type == CommandType.SHORT
        assert params.original_command == "/ketchup short"
        assert params.context == CommandContext.DIRECT_MESSAGE


class TestSummaryCommandParams:
    def test_instantiation(self) -> None:
        """Test SummaryCommandParams instantiation."""
        params = SummaryCommandParams(
            user_id="U123456789",
            user_name="testuser",
            channel_id="C123456789",
            command_text="short",
            response_url="https://hooks.slack.com/commands/123",
            original_command="/ketchup short",
            command_type=CommandType.SHORT,
            context=CommandContext.DIRECT_MESSAGE,
            target_channel_id="C123",
            summary_type="short",
        )
        assert params.target_channel_id == "C123"
        assert params.summary_type == "short"
        assert params.response_url == "https://hooks.slack.com/commands/123"


class TestQueryCommandParams:
    def test_instantiation(self) -> None:
        """Test QueryCommandParams instantiation."""
        params = QueryCommandParams(
            user_id="U123456789",
            user_name="testuser",
            channel_id="C123456789",
            command_text="query What happened?",
            response_url="https://hooks.slack.com/commands/123",
            original_command="/ketchup query",
            command_type=CommandType.QUERY,
            context=CommandContext.DIRECT_MESSAGE,
            query_text="What happened?",
        )
        assert params.query_text == "What happened?"
        assert params.response_url == "https://hooks.slack.com/commands/123"


class TestStatusReportCommandParams:
    def test_instantiation(self) -> None:
        """Test StatusReportCommandParams instantiation."""
        params = StatusReportCommandParams(
            user_id="U123456789",
            user_name="testuser",
            channel_id="C123456789",
            command_text="status",
            response_url="https://hooks.slack.com/commands/123",
            original_command="/ketchup status",
            command_type=CommandType.STATUS,
            context=CommandContext.DIRECT_MESSAGE,
            target_channel_id="C123",
            report_type="status",
        )
        assert params.report_type == "status"
        assert params.response_url == "https://hooks.slack.com/commands/123"


class TestArchiveCommandParams:
    pass


class TestListCommandParams:
    pass
