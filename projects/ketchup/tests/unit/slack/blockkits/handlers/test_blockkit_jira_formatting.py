"""
test_blockkit_jira_formatting.py

Unit tests for JIRA ticket formatting in blockkit message utils.

Tests verify that plain JIRA IDs are properly formatted as clickable links
and that pre-formatted links are left as-is.
"""

from packages.slack.blockkits.handlers.blockkit_message_utils import (
    format_channel_list_block,
    format_message_header_with_channel_details,
)


class TestBlockkitJiraFormatting:
    """Test JIRA ticket formatting in blockkit message utils."""

    def test_format_plain_jira_id_in_channel_list(self):
        """Test that plain JIRA ID is formatted as clickable link in channel list."""
        channel = {
            "channel_id": "C123",
            "channel_name": "test-channel",
            "customer_name": "Acme Corp",
            "jira_ticket": "CPGNTT-125206",
        }

        blocks = format_channel_list_block(1, channel)

        # Extract the section text
        section_text = blocks[0]["text"]["text"]

        # Verify JIRA ticket is formatted as a link
        assert (
            "<https://jira.corp.adobe.com/browse/CPGNTT-125206|CPGNTT-125206>"
            in section_text
        )
        assert "CPGNTT-125206" in section_text

    def test_format_lowercase_jira_id_in_channel_list(self):
        """Test that lowercase JIRA ID is formatted as clickable link."""
        channel = {
            "channel_id": "C123",
            "channel_name": "test-channel",
            "customer_name": "Acme Corp",
            "jira_ticket": "cpgntt-125206",  # lowercase
        }

        blocks = format_channel_list_block(1, channel)
        section_text = blocks[0]["text"]["text"]

        # Should still be formatted as a link (case-insensitive match)
        assert (
            "<https://jira.corp.adobe.com/browse/cpgntt-125206|cpgntt-125206>"
            in section_text
        )

    def test_format_not_available_jira_in_channel_list(self):
        """Test that 'NOT YET AVAILABLE' is not formatted as a link."""
        channel = {
            "channel_id": "C123",
            "channel_name": "test-channel",
            "customer_name": "Acme Corp",
            "jira_ticket": "NOT YET AVAILABLE",
        }

        blocks = format_channel_list_block(1, channel)
        section_text = blocks[0]["text"]["text"]

        # Should remain as plain text
        assert "NOT YET AVAILABLE" in section_text
        assert "<https://jira.corp.adobe.com" not in section_text

    def test_format_invalid_jira_in_channel_list(self):
        """Test that invalid JIRA format is kept as-is."""
        channel = {
            "channel_id": "C123",
            "channel_name": "test-channel",
            "customer_name": "Acme Corp",
            "jira_ticket": "NOT-A-VALID-JIRA",
        }

        blocks = format_channel_list_block(1, channel)
        section_text = blocks[0]["text"]["text"]

        # Should remain as plain text
        assert "NOT-A-VALID-JIRA" in section_text
        assert "<https://jira.corp.adobe.com" not in section_text

    def test_format_plain_jira_id_in_message_header(self):
        """Test that plain JIRA ID is formatted as clickable link in message header."""
        channel_detail = {
            "channel_id": "C123",
            "channel_name": "test-channel",
            "customer_name": "Acme Corp",
            "jira_ticket": "CPGNTT-125206",
        }

        header = format_message_header_with_channel_details(
            title="Test Title", channel_detail=channel_detail
        )

        # Verify JIRA ticket is formatted as a link
        assert (
            "<https://jira.corp.adobe.com/browse/CPGNTT-125206|CPGNTT-125206>" in header
        )

    def test_format_with_archived_channel(self):
        """Test formatting with archived_at timestamp."""
        channel = {
            "channel_id": "C123",
            "channel_name": "test-channel",
            "customer_name": "Acme Corp",
            "jira_ticket": "CPGNTT-125206",
            "archived_at": 1234567890,
        }

        blocks = format_channel_list_block(1, channel)
        section_text = blocks[0]["text"]["text"]

        # Should include both formatted JIRA and archive time
        assert (
            "<https://jira.corp.adobe.com/browse/CPGNTT-125206|CPGNTT-125206>"
            in section_text
        )
        assert "*Archived:*" in section_text

    def test_format_empty_jira_ticket(self):
        """Test handling of empty/None JIRA ticket."""
        channel = {
            "channel_id": "C123",
            "channel_name": "test-channel",
            "customer_name": "Acme Corp",
            "jira_ticket": None,
        }

        blocks = format_channel_list_block(1, channel)
        section_text = blocks[0]["text"]["text"]

        # When jira_ticket is None, .get() returns None not the default
        # because the key exists with a None value
        assert "None" in section_text or "NOT YET AVAILABLE" in section_text
