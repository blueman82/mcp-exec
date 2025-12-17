"""
Tests for customer extraction context validation to prevent domain-based misidentification.
"""

import logging
from unittest.mock import AsyncMock, Mock

import pytest

from ketchup_unified_scheduler.services.metadata.extractor import MetadataExtractor
from packages.ai.core.openai_handler import OpenAIHandler


class TestCustomerExtractionContextValidation:
    """Test cases for context-aware customer extraction."""

    @pytest.fixture
    def mock_ai_handler(self):
        """Create a mock AI handler."""
        handler = Mock(spec=OpenAIHandler)
        handler.call_openai_endpoint = AsyncMock()
        return handler

    @pytest.fixture
    def extractor(self, mock_ai_handler):
        """Create a MetadataExtractor instance."""
        extractor = MetadataExtractor(mock_ai_handler)
        # Enable log propagation for caplog to work
        logger = logging.getLogger("ketchup_unified_scheduler.services.metadata.extractor")
        logger.propagate = True
        return extractor

    def test_parse_ai_response_legitimate_adobe_customer(self, extractor):
        """Test that legitimate Adobe customer is correctly identified."""
        ai_response = "ADOBE\nCPGNREQ-12345"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "ADOBE"
        assert result["jira_ticket"] == "CPGNREQ-12345"

    def test_parse_ai_response_non_adobe_customer_with_adobe_urls(self, extractor):
        """Test that non-Adobe customer is correctly identified despite Adobe URLs."""
        ai_response = "ZENIMAX MEDIA INC\nCPGNREQ-12345"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "ZENIMAX MEDIA INC"
        assert result["jira_ticket"] == "CPGNREQ-12345"

    def test_parse_ai_response_multiple_customers_including_adobe(self, extractor):
        """Test multiple customers where one is Adobe."""
        ai_response = "ADOBE, MICROSOFT, ZENIMAX MEDIA INC\nCPGNREQ-12345"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "ADOBE, MICROSOFT, ZENIMAX MEDIA INC"
        assert result["jira_ticket"] == "CPGNREQ-12345"

    def test_parse_ai_response_no_customer_available(self, extractor):
        """Test fallback when no customer is identified."""
        ai_response = "NOT YET AVAILABLE\nCPGNREQ-12345"

        result = extractor.parse_ai_response(ai_response)

        assert result["customer_name"] == "NOT YET AVAILABLE"
        assert result["jira_ticket"] == "CPGNREQ-12345"

    def test_validate_customer_extraction_adobe_warning(self, extractor, caplog):
        """Test that Adobe extraction triggers validation warning."""
        with caplog.at_level(logging.WARNING, logger="ketchup_unified_scheduler.services.metadata.extractor"):
            extractor._validate_customer_extraction("ADOBE")

        assert "Potential domain-based misidentification detected" in caplog.text
        assert "ADOBE" in caplog.text

    def test_validate_customer_extraction_microsoft_warning(self, extractor, caplog):
        """Test that Microsoft extraction triggers validation warning."""
        with caplog.at_level(logging.WARNING, logger="ketchup_unified_scheduler.services.metadata.extractor"):
            extractor._validate_customer_extraction("MICROSOFT")

        assert "Potential domain-based misidentification detected" in caplog.text
        assert "MICROSOFT" in caplog.text

    def test_validate_customer_extraction_legitimate_customer_no_warning(self, extractor, caplog):
        """Test that legitimate customer names don't trigger warnings."""
        extractor._validate_customer_extraction("ZENIMAX MEDIA INC")

        assert "Potential domain-based misidentification detected" not in caplog.text

    def test_validate_customer_extraction_not_available_no_warning(self, extractor, caplog):
        """Test that NOT YET AVAILABLE doesn't trigger warnings."""
        extractor._validate_customer_extraction("NOT YET AVAILABLE")

        assert "Potential domain-based misidentification detected" not in caplog.text

    def test_validate_customer_extraction_mixed_names_with_adobe(self, extractor, caplog):
        """Test validation for mixed customer names including Adobe.

        Note: The production code only checks for exact matches of 'ADOBE' or 'MICROSOFT',
        so mixed names like 'ADOBE, ZENIMAX MEDIA INC' won't trigger the warning.
        """
        with caplog.at_level(logging.INFO, logger="ketchup_unified_scheduler.services.metadata.extractor"):
            extractor._validate_customer_extraction("ADOBE, ZENIMAX MEDIA INC")

        # Mixed names don't trigger the warning, only exact matches do
        assert "Potential domain-based misidentification detected" not in caplog.text
        # But the info log should still mention the customer name
        assert "Customer extracted: 'ADOBE, ZENIMAX MEDIA INC'" in caplog.text

    @pytest.mark.asyncio
    async def test_extract_metadata_context_aware_adobe_legitimate(self, extractor):
        """Test full extraction flow with legitimate Adobe customer."""
        messages = [
            "We're working with the Adobe team on this authentication issue.",
            "Adobe customer reported login problems this morning.",
            "Created ticket: https://jira.corp.adobe.com/browse/CPGNREQ-12345",
        ]

        # Mock AI response for legitimate Adobe customer
        extractor.ai_handler.call_openai_endpoint.return_value = {
            "choices": [{"message": {"content": "ADOBE\nCPGNREQ-12345"}}]
        }

        result = await extractor.extract_metadata_with_ai("C123", messages)

        assert result["customer_name"] == "ADOBE"
        assert result["jira_ticket"] == "CPGNREQ-12345"

    @pytest.mark.asyncio
    async def test_extract_metadata_context_aware_non_adobe_customer(self, extractor):
        """Test full extraction flow with non-Adobe customer."""
        messages = [
            "ZENIMAX MEDIA INC is experiencing authentication issues.",
            "Customer ZENIMAX MEDIA INC team contacted us about login problems.",
            "Created ticket: https://jira.corp.adobe.com/browse/CPGNREQ-12345",
        ]

        # Mock AI response for non-Adobe customer
        extractor.ai_handler.call_openai_endpoint.return_value = {
            "choices": [{"message": {"content": "ZENIMAX MEDIA INC\nCPGNREQ-12345"}}]
        }

        result = await extractor.extract_metadata_with_ai("C123", messages)

        assert result["customer_name"] == "ZENIMAX MEDIA INC"
        assert result["jira_ticket"] == "CPGNREQ-12345"

    @pytest.mark.asyncio
    async def test_extract_metadata_url_only_no_customer_context(self, extractor):
        """Test extraction when only URLs are present without customer context."""
        messages = [
            "Issue reported in system.",
            "Check ticket: https://jira.corp.adobe.com/browse/CPGNREQ-12345",
            "Status: In Progress",
        ]

        # Mock AI response with no customer identified
        extractor.ai_handler.call_openai_endpoint.return_value = {
            "choices": [{"message": {"content": "NOT YET AVAILABLE\nCPGNREQ-12345"}}]
        }

        result = await extractor.extract_metadata_with_ai("C123", messages)

        assert result["customer_name"] == "NOT YET AVAILABLE"
        assert result["jira_ticket"] == "CPGNREQ-12345"
