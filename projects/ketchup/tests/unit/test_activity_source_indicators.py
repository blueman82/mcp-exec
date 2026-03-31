"""
Test activity source indicators in status generator.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ketchup_unified_scheduler.services.status.generator import AutoStatusGenerator


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for AutoStatusGenerator."""
    return {
        "db_store": AsyncMock(),
        "mcp_client": AsyncMock(),
        "secrets_manager": AsyncMock(),
        "slack_config": MagicMock(),
        "openai_handler": AsyncMock(),
        "channel_info_ops": AsyncMock(),  # Added missing parameter
        "channel_msg_ops": AsyncMock(),
        "posting_handler": AsyncMock(),
        "channel_operations": AsyncMock(),
    }


class TestActivitySourceIndicators:
    """Test activity source indicators in status updates."""

    def test_format_message_with_slack_only(self, mock_dependencies):
        """Test formatting with only Slack activity."""
        generator = AutoStatusGenerator(**mock_dependencies)

        content = "Overview: Test content"
        result = generator._format_final_message(
            content=content,
            channel_name="test-channel",
            channel_id="C123456",
            has_slack_activity=True,
            has_jira_activity=False,
        )

        assert ":slack:" in result
        assert ":jira-logo:" not in result
        assert "Activity source: :slack:" in result

    def test_format_message_with_jira_only(self, mock_dependencies):
        """Test formatting with only JIRA activity."""
        generator = AutoStatusGenerator(**mock_dependencies)

        content = "Overview: Test content"
        result = generator._format_final_message(
            content=content,
            channel_name="test-channel",
            channel_id="C123456",
            has_slack_activity=False,
            has_jira_activity=True,
        )

        assert ":slack:" not in result
        assert ":jira-logo:" in result
        assert "Activity source: :jira-logo:" in result

    def test_format_message_with_both_sources(self, mock_dependencies):
        """Test formatting with both Slack and JIRA activity."""
        generator = AutoStatusGenerator(**mock_dependencies)

        content = "Overview: Test content"
        result = generator._format_final_message(
            content=content,
            channel_name="test-channel",
            channel_id="C123456",
            has_slack_activity=True,
            has_jira_activity=True,
        )

        assert ":slack:" in result
        assert ":jira-logo:" in result
        assert "Activity source: :slack: :jira-logo:" in result

    def test_format_message_with_no_activity(self, mock_dependencies):
        """Test formatting with no activity (edge case)."""
        generator = AutoStatusGenerator(**mock_dependencies)

        content = "Overview: Test content"
        result = generator._format_final_message(
            content=content,
            channel_name="test-channel",
            channel_id="C123456",
            has_slack_activity=False,
            has_jira_activity=False,
        )

        # Should not show activity source line at all
        assert ":slack:" not in result
        assert ":jira-logo:" not in result
        assert "Activity source:" not in result

    def test_format_message_header_structure(self, mock_dependencies):
        """Test that header maintains proper structure with activity indicators."""
        generator = AutoStatusGenerator(**mock_dependencies)

        content = "Overview: Test content"
        result = generator._format_final_message(
            content=content,
            channel_name="test-channel",
            channel_id="C123456",
            has_slack_activity=True,
            has_jira_activity=True,
        )

        # Check header structure
        lines = result.split("\n")
        assert lines[0] == "*Ketchup Automated Status Update*"
        assert "Channel: <#C123456|test-channel>" in lines[1]
        assert "Activity source: :slack: :jira-logo:" in lines[2]
        assert "Status checked hourly: Updates posted only when activity detected" in lines[3]
        assert "This auto-generated summary is based on Jira and Slack discussions." in lines[4]
        assert "─" * 40 in lines[5]
