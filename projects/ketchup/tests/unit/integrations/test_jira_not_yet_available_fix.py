"""
Test to verify that 'NOT YET AVAILABLE' JIRA tickets are handled gracefully.
"""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_jira_data_extractor_skips_not_yet_available():
    """Test that JiraDataExtractor skips 'NOT YET AVAILABLE' tickets."""
    from packages.integrations.jira_data_extractor import JIRADataExtractor

    # Mock dependencies
    mock_mcp_client = AsyncMock()
    mock_dynamodb_store = AsyncMock()
    mock_cache = AsyncMock()

    # Set up the extractor
    extractor = JIRADataExtractor(
        mcp_client=mock_mcp_client, dynamodb_store=mock_dynamodb_store
    )
    extractor.cache = mock_cache

    # Mock channel metadata with 'NOT YET AVAILABLE' ticket
    mock_dynamodb_store.get_channel_details.return_value = {
        "channel_id": "C123456",
        "jira_ticket": "NOT YET AVAILABLE",
        "customer_name": "Test Customer",
    }

    # Mock cache to return None (not cached)
    mock_cache.get.return_value = None

    # Call get_jira_context
    result = await extractor.get_jira_context(channel_id="C123456", message_texts=[])

    # Verify that the MCP client was NOT called with invalid ticket
    mock_mcp_client.get_issue.assert_not_called()
    mock_mcp_client.get_issue_comments.assert_not_called()

    # Verify result is None (no JIRA context found)
    assert result is None


@pytest.mark.asyncio
async def test_get_ticket_data_validates_ticket_id():
    """Test that _get_ticket_data validates ticket ID before API call."""
    from packages.integrations.jira_data_extractor import JIRADataExtractor

    # Mock dependencies
    mock_mcp_client = AsyncMock()
    mock_dynamodb_store = AsyncMock()
    mock_cache = AsyncMock()

    # Set up the extractor
    extractor = JIRADataExtractor(
        mcp_client=mock_mcp_client, dynamodb_store=mock_dynamodb_store
    )
    extractor.cache = mock_cache

    # Test with 'NOT YET AVAILABLE'
    result = await extractor._get_ticket_data("NOT YET AVAILABLE")

    # Should return None without calling API
    assert result is None
    mock_mcp_client.get_issue.assert_not_called()

    # Test with empty string
    result = await extractor._get_ticket_data("")

    # Should return None without calling API
    assert result is None
    mock_mcp_client.get_issue.assert_not_called()

    # Test with None
    result = await extractor._get_ticket_data(None)

    # Should return None without calling API
    assert result is None
    mock_mcp_client.get_issue.assert_not_called()


@pytest.mark.asyncio
async def test_valid_jira_ticket_still_works():
    """Test that valid JIRA tickets are still processed correctly."""
    from packages.integrations.jira_data_extractor import JIRADataExtractor

    # Mock dependencies
    mock_mcp_client = AsyncMock()
    mock_dynamodb_store = AsyncMock()
    mock_cache = AsyncMock()

    # Set up the extractor
    extractor = JIRADataExtractor(
        mcp_client=mock_mcp_client, dynamodb_store=mock_dynamodb_store
    )
    extractor.cache = mock_cache

    # Mock channel metadata with valid ticket
    mock_dynamodb_store.get_channel_details.return_value = {
        "channel_id": "C123456",
        "jira_ticket": "CPGNCX-12345",
        "customer_name": "Test Customer",
    }

    # Mock cache to return None (not cached)
    mock_cache.get.return_value = None

    # Mock JIRA API responses
    mock_mcp_client.get_issue.return_value = {
        "key": "CPGNCX-12345",
        "fields": {"summary": "Test Issue", "description": "Test Description"},
    }
    mock_mcp_client.get_issue_comments.return_value = []

    # Call get_jira_context
    result = await extractor.get_jira_context(channel_id="C123456", message_texts=[])

    # Verify that the MCP client WAS called with valid ticket
    mock_mcp_client.get_issue.assert_called_once_with("CPGNCX-12345")
    mock_mcp_client.get_issue_comments.assert_called_once_with("CPGNCX-12345")

    # Verify result contains ticket data
    assert result is not None
    assert result["ticket_id"] == "CPGNCX-12345"
    assert result["source"] == "channel_metadata"
