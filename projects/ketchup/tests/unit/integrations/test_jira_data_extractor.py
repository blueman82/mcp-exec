"""
test_jira_data_extractor.py

Unit tests for JIRA data extraction with caching and performance optimization.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from packages.integrations.jira_cache import JIRACache
from packages.integrations.jira_data_extractor import JIRADataExtractor

pytestmark = pytest.mark.unit


class TestJIRACache:
    """Test JIRA cache functionality."""

    @pytest.mark.asyncio
    async def test_set_and_get_valid_cache(self):
        """Test setting and getting valid cached data."""
        cache = JIRACache(ttl_seconds=300)

        test_data = {"key": "TEST-1", "summary": "Test Issue"}
        await cache.set("TEST-1", test_data)

        result = await cache.get("TEST-1")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_expired_cache(self):
        """Test getting expired cached data returns None."""
        cache = JIRACache(ttl_seconds=1)

        test_data = {"key": "TEST-1", "summary": "Test Issue"}
        await cache.set("TEST-1", test_data)

        # Mock time to simulate expiry
        with patch("time.time", return_value=time.time() + 2):
            result = await cache.get("TEST-1")
            assert result is None

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Test clearing cache."""
        cache = JIRACache()

        await cache.set("TEST-1", {"data": "test1"})
        await cache.set("TEST-2", {"data": "test2"})

        await cache.invalidate()  # clear() method doesn't exist, use invalidate()

        assert await cache.get("TEST-1") is None
        assert await cache.get("TEST-2") is None

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test cache statistics."""
        cache = JIRACache()

        # Initial stats
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0

        # Add entries and test hits/misses
        await cache.set("TEST-1", {"data": "test"})
        await cache.get("TEST-1")  # Hit
        await cache.get("TEST-2")  # Miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == 0.5


class TestJIRADataExtractor:
    """Test JIRA data extractor functionality."""

    @pytest.fixture
    def mock_mcp_client(self):
        """Create mock MCP client."""
        client = AsyncMock()
        client.search_issues = AsyncMock()
        client.get_issue = AsyncMock()
        return client

    @pytest.fixture
    def mock_dynamodb_store(self):
        """Create mock DynamoDB store."""
        store = AsyncMock()
        store.get_channel_metadata = AsyncMock()
        return store

    @pytest.fixture
    def mock_cache(self):
        """Create mock cache."""
        return JIRACache()

    def test_extract_jira_tickets_from_text(self, mock_mcp_client, mock_dynamodb_store, mock_cache):
        """Test extracting JIRA ticket IDs from text."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        text = "Check out TEST-123 and PROJ-456 for details. Also see ABC-1."
        tickets = extractor.extract_ticket_ids([text])

        assert tickets == ["TEST-123", "PROJ-456", "ABC-1"]

    def test_extract_jira_tickets_no_duplicates(
        self, mock_mcp_client, mock_dynamodb_store, mock_cache
    ):
        """Test extracting JIRA tickets removes duplicates."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        text = "TEST-123 is related to TEST-123 and TEST-456"
        tickets = extractor.extract_ticket_ids([text])

        assert tickets == ["TEST-123", "TEST-456"]

    def test_extract_jira_tickets_invalid_format(
        self, mock_mcp_client, mock_dynamodb_store, mock_cache
    ):
        """Test invalid JIRA ticket formats are ignored."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        text = "test-123 and TEST123 and T-12345678901 are invalid"
        tickets = extractor.extract_ticket_ids([text])

        assert tickets == []

    @pytest.mark.asyncio
    async def test_get_jira_context_from_metadata(
        self, mock_mcp_client, mock_dynamodb_store, mock_cache
    ):
        """Test extracting JIRA data from channel metadata."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        # Mock channel metadata with jira_ticket field
        mock_dynamodb_store.get_channel_details.return_value = {
            "channel_id": "C123",
            "name": "test-channel",
            "jira_ticket": "TEST-123",
        }

        # Mock JIRA response
        mock_mcp_client.get_issue.return_value = {
            "key": "TEST-123",
            "fields": {"summary": "Test Issue"},
        }

        result = await extractor.get_jira_context("C123", [])

        assert result is not None
        assert result["ticket_id"] == "TEST-123"
        assert result["data"]["key"] == "TEST-123"
        assert result["source"] == "channel_metadata"

    @pytest.mark.asyncio
    async def test_get_jira_context_from_messages(
        self, mock_mcp_client, mock_dynamodb_store, mock_cache
    ):
        """Test extracting JIRA data from messages."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        message_texts = ["Working on BUG-789", "Fixed FEAT-101"]

        # Mock no channel metadata
        mock_dynamodb_store.get_channel_details.return_value = None

        # Mock JIRA response for first ticket found
        mock_mcp_client.get_issue.return_value = {
            "key": "BUG-789",
            "fields": {"summary": "Bug fix"},
        }

        result = await extractor.get_jira_context("C123", message_texts)

        assert result is not None
        assert result["ticket_id"] == "BUG-789"
        assert result["data"]["key"] == "BUG-789"
        assert result["source"] == "message_text"
        assert result["all_tickets"] == ["BUG-789", "FEAT-101"]

    @pytest.mark.asyncio
    async def test_caching_behavior(self, mock_mcp_client, mock_dynamodb_store, mock_cache):
        """Test that cache is used to avoid duplicate API calls."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        # Mock no channel metadata
        mock_dynamodb_store.get_channel_details.return_value = None

        # Mock JIRA response
        mock_mcp_client.get_issue.return_value = {
            "key": "TEST-123",
            "fields": {"summary": "Cached Issue"},
        }

        # First call - should hit API
        result1 = await extractor.get_jira_context("C123", ["Check TEST-123"])

        # Second call - should use cache
        result2 = await extractor.get_jira_context("C123", ["TEST-123 again"])

        # Verify API was only called once (cache should be used for second call)
        assert mock_mcp_client.get_issue.call_count == 1

        # Verify both results have same ticket data
        assert result1["ticket_id"] == result2["ticket_id"]

    @pytest.mark.asyncio
    async def test_api_error_handling(self, mock_mcp_client, mock_dynamodb_store, mock_cache):
        """Test handling of API errors."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        # Mock no channel metadata
        mock_dynamodb_store.get_channel_details.return_value = None

        # Mock API error
        mock_mcp_client.get_issue.side_effect = Exception("API Error")

        result = await extractor.get_jira_context("C123", ["Check TEST-123"])

        # Should return None on error
        assert result is None

    @pytest.mark.asyncio
    async def test_search_related_tickets(self, mock_mcp_client, mock_dynamodb_store, mock_cache):
        """Test searching for related tickets with JQL."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        # Mock search response
        mock_mcp_client.search_issues.return_value = {
            "issues": [
                {"key": "TEST-1", "fields": {"summary": "Issue 1"}},
                {"key": "TEST-2", "fields": {"summary": "Issue 2"}},
            ]
        }

        result = await extractor.search_related_tickets("project = TEST")

        assert result is not None
        assert len(result) == 2
        assert result[0]["key"] == "TEST-1"
        assert result[1]["key"] == "TEST-2"

    @pytest.mark.asyncio
    async def test_warm_cache(self, mock_mcp_client, mock_dynamodb_store, mock_cache):
        """Test cache warming functionality."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        # Mock channel metadata for multiple channels
        mock_dynamodb_store.get_channel_metadata.side_effect = [
            {"channel_id": "C1", "jira_ticket": "TEST-1"},
            {"channel_id": "C2", "jira_ticket": "TEST-2"},
        ]

        # Mock JIRA responses
        mock_mcp_client.get_issue.side_effect = [
            {"key": "TEST-1", "fields": {"summary": "Issue 1"}},
            {"key": "TEST-2", "fields": {"summary": "Issue 2"}},
        ]

        # Warm cache for channels
        await extractor.warm_cache(["C1", "C2"])

        # Verify both tickets were fetched
        assert mock_mcp_client.get_issue.call_count == 2

        # Now get context should use cache (no additional API calls)
        mock_mcp_client.get_issue.reset_mock()
        await extractor.get_jira_context("C1", [])
        assert mock_mcp_client.get_issue.call_count == 0  # Should use cache

    def test_get_cache_stats(self, mock_mcp_client, mock_dynamodb_store):
        """Test getting cache statistics."""
        cache = JIRACache()
        JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, cache)

        stats = cache.get_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats
        assert "hit_rate" in stats

    @pytest.mark.asyncio
    async def test_empty_channel_metadata(self, mock_mcp_client, mock_dynamodb_store, mock_cache):
        """Test handling empty channel metadata."""
        extractor = JIRADataExtractor(mock_mcp_client, mock_dynamodb_store, mock_cache)

        # Mock empty metadata
        mock_dynamodb_store.get_channel_details.return_value = None

        # No tickets in messages either
        result = await extractor.get_jira_context("C123", ["No tickets here"])

        assert result is None
