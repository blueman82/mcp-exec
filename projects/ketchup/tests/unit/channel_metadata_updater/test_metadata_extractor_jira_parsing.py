"""
test_metadata_extractor_jira_parsing.py

Unit tests for JIRA ticket ID extraction in the metadata extractor.

Tests verify that various JIRA ticket formats are correctly normalized to plain IDs
for database storage, which will then be formatted as links at display time.
"""

from unittest.mock import MagicMock

from ketchup_unified_scheduler.services.metadata.extractor import MetadataExtractor


class TestMetadataExtractorJiraParsing:
    """Test JIRA ticket parsing in MetadataExtractor."""

    def test_parse_slack_formatted_jira(self):
        """Test extracting ID from Slack-formatted JIRA link."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp\n<https://jira.corp.adobe.com/browse/CPGNTT-125206|CPGNTT-125206>"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "CPGNTT-125206"

    def test_parse_markdown_formatted_jira(self):
        """Test extracting ID from Markdown-formatted JIRA link."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp\n[CPGNTT-125206](https://jira.corp.adobe.com/browse/CPGNTT-125206)"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "CPGNTT-125206"

    def test_parse_plain_jira_url(self):
        """Test extracting ID from plain JIRA URL."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp\nhttps://jira.corp.adobe.com/browse/CPGNTT-125206"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "CPGNTT-125206"

    def test_parse_plain_jira_id(self):
        """Test parsing plain JIRA ID (no conversion needed)."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp\nCPGNTT-125206"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "CPGNTT-125206"

    def test_parse_lowercase_jira_id(self):
        """Test that lowercase JIRA IDs are converted to uppercase."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp\ncpgntt-125206"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "CPGNTT-125206"

    def test_parse_jira_url_with_parameters(self):
        """Test extracting ID from JIRA URL with query parameters."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp\nhttps://jira.corp.adobe.com/browse/CPGNTT-125206?filter=123"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "CPGNTT-125206"

    def test_parse_jira_url_with_trailing_slash(self):
        """Test extracting ID from JIRA URL with trailing slash."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp\nhttps://jira.corp.adobe.com/browse/CPGNTT-125206/"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "CPGNTT-125206"

    def test_parse_non_jira_markdown_link(self):
        """Test that non-JIRA markdown links are kept as-is."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp\n[Some Doc](https://example.com/doc)"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "[Some Doc](https://example.com/doc)"

    def test_parse_malformed_jira_id(self):
        """Test that malformed JIRA IDs are kept as-is."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp\nNOT-A-VALID-JIRA-ID-123"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "NOT-A-VALID-JIRA-ID-123"

    def test_parse_no_jira_ticket(self):
        """Test parsing response with no JIRA ticket line."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = "Acme Corp"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "Acme Corp"
        assert result["jira_ticket"] == "NOT YET AVAILABLE"

    def test_parse_empty_response(self):
        """Test parsing empty AI response."""
        mock_ai_handler = MagicMock()
        extractor = MetadataExtractor(ai_handler=mock_ai_handler)
        ai_response = ""

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "NOT YET AVAILABLE"
        assert result["jira_ticket"] == "NOT YET AVAILABLE"
