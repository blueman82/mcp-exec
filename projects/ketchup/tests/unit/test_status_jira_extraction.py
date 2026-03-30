"""
Test JIRA ticket extraction and correction in status generator.
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
        "channel_info_ops": AsyncMock(),
        "channel_msg_ops": AsyncMock(),
        "posting_handler": AsyncMock(),
        "channel_operations": AsyncMock(),
    }


class TestJIRAExtraction:
    """Test JIRA ticket extraction and formatting."""

    def test_extract_valid_jira_ticket(self, mock_dependencies):
        """Test extraction of valid JIRA tickets from text."""
        generator = AutoStatusGenerator(**mock_dependencies)

        # Test valid tickets
        assert generator._extract_valid_jira_ticket("Working on CPGNREQ-12345") == "CPGNREQ-12345"
        assert generator._extract_valid_jira_ticket("Issue NEO-999 is fixed") == "NEO-999"
        assert generator._extract_valid_jira_ticket("See PLATIR-1 for details") == "PLATIR-1"
        assert generator._extract_valid_jira_ticket("cpgncc-789 lowercase") == "CPGNCC-789"
        assert generator._extract_valid_jira_ticket("Tracking in CAMP-59130") == "CAMP-59130"

        # Test invalid tickets (not in approved list)
        assert generator._extract_valid_jira_ticket("Working on INVALID-12345") is None
        assert generator._extract_valid_jira_ticket("Issue ABC-999") is None

        # Test ServiceNow URLs should not match
        assert (
            generator._extract_valid_jira_ticket(
                "https://adobe.service-now.com/x/adosy/cso_portal/cso/202507030023"
            )
            is None
        )

        # Test multiple tickets - should return first valid one
        assert generator._extract_valid_jira_ticket("INVALID-123 and CPGNREQ-456") == "CPGNREQ-456"

    def test_remove_jira_line(self, mock_dependencies):
        """Test removal of JIRA lines from content."""
        generator = AutoStatusGenerator(**mock_dependencies)

        # Test various JIRA line formats
        content = """Overview: Test content

JIRA Ticket: https://adobe.service-now.com/x/adosy/cso_portal/cso/202507030023"""

        result = generator._remove_jira_line(content)
        assert "JIRA Ticket:" not in result
        assert "Overview: Test content" in result

        # Test case insensitive
        content2 = "Some text\njira ticket: TEST-123\nMore text"
        result2 = generator._remove_jira_line(content2)
        assert "jira ticket:" not in result2.lower()
        assert "Some text" in result2
        assert "More text" in result2

    def test_apply_corrections_with_db_ticket(self, mock_dependencies):
        """Test corrections when JIRA ticket exists in database."""
        generator = AutoStatusGenerator(**mock_dependencies)

        content = """Overview: Issue resolved.

What's been done / What's next:
• Fixed the problem
• Tested the solution
• Deployed to staging
• Will monitor for issues

JIRA Ticket: https://adobe.service-now.com/wrong-url"""

        channel_details = {"jira_ticket": "CPGNREQ-180311", "customer_name": "TestCorp"}

        result = generator._apply_corrections(content, "test-channel", channel_details)

        # Should have correct JIRA format
        assert (
            "JIRA Ticket: <https://jira.corp.adobe.com/browse/CPGNREQ-180311|CPGNREQ-180311>"
            in result
        )
        # Should not have ServiceNow URL
        assert "service-now.com" not in result

    def test_apply_corrections_extract_from_content(self, mock_dependencies):
        """Test corrections when JIRA ticket is extracted from content."""
        generator = AutoStatusGenerator(**mock_dependencies)

        content = """Overview: Working on NEO-4567 issue.

What's been done / What's next:
• Identified root cause
• Created fix for NEO-4567
• Testing in progress
• Will deploy tomorrow"""

        channel_details = {
            "jira_ticket": "NOT YET AVAILABLE",
            "customer_name": "TestCorp",
        }

        result = generator._apply_corrections(content, "test-channel", channel_details)

        # Should extract and format NEO-4567
        assert "JIRA Ticket: <https://jira.corp.adobe.com/browse/NEO-4567|NEO-4567>" in result

    def test_apply_corrections_no_jira(self, mock_dependencies):
        """Test corrections when no JIRA ticket exists."""
        generator = AutoStatusGenerator(**mock_dependencies)

        content = """Overview: General maintenance work.

What's been done / What's next:
• Updated documentation
• Cleaned up code
• Fixed minor bugs
• Will continue tomorrow"""

        channel_details = {
            "jira_ticket": "NOT YET AVAILABLE",
            "customer_name": "TestCorp",
        }

        result = generator._apply_corrections(content, "test-channel", channel_details)

        # Should not add JIRA line when no valid ticket found
        assert "JIRA Ticket:" not in result
        assert result.strip().endswith("Will continue tomorrow")
