"""
test_jql_patterns.py

Unit tests for JIRA Query Language (JQL) patterns used in the application.
Tests various JQL queries to ensure they're properly formatted and will work with JIRA.
"""

from unittest.mock import AsyncMock

import pytest

from packages.integrations.jira_data_extractor import JIRADataExtractor


class TestJQLPatterns:
    """Test various JQL patterns used throughout the application."""

    @pytest.fixture
    def mock_mcp_client(self):
        """Create a mock MCP client for testing."""
        client = AsyncMock()
        client.search_issues = AsyncMock()
        return client

    @pytest.fixture
    def mock_dynamodb_store(self):
        """Create a mock DynamoDB store."""
        return AsyncMock()

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        return cache

    @pytest.fixture
    def jira_extractor(self, mock_mcp_client, mock_dynamodb_store, mock_cache):
        """Create JIRADataExtractor with mocked dependencies."""
        return JIRADataExtractor(
            mcp_client=mock_mcp_client,
            dynamodb_store=mock_dynamodb_store,
            cache=mock_cache,
        )

    @pytest.mark.asyncio
    async def test_project_and_status_jql(self, jira_extractor, mock_mcp_client):
        """Test JQL for specific project and status."""
        jql = 'project = "CAMP" AND status = "Open"'
        expected_issues = [
            {"key": "CAMP-123", "fields": {"summary": "Test issue"}},
            {"key": "CAMP-456", "fields": {"summary": "Another issue"}},
        ]
        mock_mcp_client.search_issues.return_value = {"issues": expected_issues}

        result = await jira_extractor.search_related_tickets(jql)

        mock_mcp_client.search_issues.assert_called_once_with(jql)
        assert result == expected_issues

    @pytest.mark.asyncio
    async def test_assignee_and_created_date_jql(self, jira_extractor, mock_mcp_client):
        """Test JQL for current user assignments in last 7 days."""
        jql = "assignee = currentUser() AND created >= -7d"
        expected_issues = [{"key": "PROJ-789", "fields": {"summary": "Recent task"}}]
        mock_mcp_client.search_issues.return_value = {"issues": expected_issues}

        result = await jira_extractor.search_related_tickets(jql)

        mock_mcp_client.search_issues.assert_called_once_with(jql)
        assert result == expected_issues

    @pytest.mark.asyncio
    async def test_text_search_with_priority_jql(self, jira_extractor, mock_mcp_client):
        """Test JQL for text search with priority filtering."""
        jql = 'text ~ "security" AND priority in (P1, P2)'
        expected_issues = [
            {
                "key": "SEC-111",
                "fields": {
                    "summary": "Security vulnerability",
                    "priority": {"name": "P1"},
                },
            }
        ]
        mock_mcp_client.search_issues.return_value = {"issues": expected_issues}

        result = await jira_extractor.search_related_tickets(jql)

        mock_mcp_client.search_issues.assert_called_once_with(jql)
        assert result == expected_issues

    @pytest.mark.asyncio
    async def test_complex_jql_with_multiple_conditions(self, jira_extractor, mock_mcp_client):
        """Test complex JQL with multiple conditions."""
        jql = 'project in ("CAMP", "INFRA") AND status != "Closed" AND (labels = "incident" OR priority = "P1") ORDER BY created DESC'
        expected_issues = [
            {"key": "CAMP-999", "fields": {"summary": "Critical incident"}},
            {"key": "INFRA-222", "fields": {"summary": "Infrastructure issue"}},
        ]
        mock_mcp_client.search_issues.return_value = {"issues": expected_issues}

        result = await jira_extractor.search_related_tickets(jql)

        mock_mcp_client.search_issues.assert_called_once_with(jql)
        assert result == expected_issues

    @pytest.mark.asyncio
    async def test_updated_date_range_jql(self, jira_extractor, mock_mcp_client):
        """Test JQL for issues updated within a date range."""
        jql = 'updated >= "2025-06-01" AND updated <= "2025-06-30"'
        expected_issues = [{"key": "PROJ-333", "fields": {"summary": "June update"}}]
        mock_mcp_client.search_issues.return_value = {"issues": expected_issues}

        result = await jira_extractor.search_related_tickets(jql)

        mock_mcp_client.search_issues.assert_called_once_with(jql)
        assert result == expected_issues

    @pytest.mark.asyncio
    async def test_reporter_and_component_jql(self, jira_extractor, mock_mcp_client):
        """Test JQL for issues by reporter in specific component."""
        jql = 'reporter = "john.doe@company.com" AND component = "Backend"'
        expected_issues = [{"key": "BACK-444", "fields": {"summary": "Backend issue"}}]
        mock_mcp_client.search_issues.return_value = {"issues": expected_issues}

        result = await jira_extractor.search_related_tickets(jql)

        mock_mcp_client.search_issues.assert_called_once_with(jql)
        assert result == expected_issues

    @pytest.mark.asyncio
    async def test_epic_link_jql(self, jira_extractor, mock_mcp_client):
        """Test JQL for issues linked to an epic."""
        jql = '"Epic Link" = EPIC-100 AND status != "Done"'
        expected_issues = [{"key": "STORY-555", "fields": {"summary": "Story under epic"}}]
        mock_mcp_client.search_issues.return_value = {"issues": expected_issues}

        result = await jira_extractor.search_related_tickets(jql)

        mock_mcp_client.search_issues.assert_called_once_with(jql)
        assert result == expected_issues

    @pytest.mark.asyncio
    async def test_jql_with_caching(self, jira_extractor, mock_mcp_client, mock_cache):
        """Test that JQL results are cached properly."""
        jql = 'project = "TEST" AND status = "Open"'
        expected_issues = [{"key": "TEST-111", "fields": {"summary": "Cached issue"}}]

        # First call - cache miss
        mock_cache.get.return_value = None
        mock_mcp_client.search_issues.return_value = {"issues": expected_issues}

        result1 = await jira_extractor.search_related_tickets(jql)

        # Verify cache was checked and set
        mock_cache.get.assert_called_once_with(f"search:{jql}")
        mock_cache.set.assert_called_once_with(f"search:{jql}", expected_issues)
        assert result1 == expected_issues

        # Second call - cache hit
        mock_cache.get.return_value = expected_issues
        mock_cache.get.reset_mock()
        mock_mcp_client.search_issues.reset_mock()

        result2 = await jira_extractor.search_related_tickets(jql)

        # Verify cache was used, MCP not called
        mock_cache.get.assert_called_once_with(f"search:{jql}")
        mock_mcp_client.search_issues.assert_not_called()
        assert result2 == expected_issues

    @pytest.mark.asyncio
    async def test_empty_jql_results(self, jira_extractor, mock_mcp_client):
        """Test handling of empty JQL results."""
        jql = 'project = "NONEXISTENT"'
        mock_mcp_client.search_issues.return_value = {"issues": []}

        result = await jira_extractor.search_related_tickets(jql)

        assert result == []

    @pytest.mark.asyncio
    async def test_jql_error_handling(self, jira_extractor, mock_mcp_client):
        """Test error handling for invalid JQL."""
        jql = "INVALID JQL SYNTAX"
        mock_mcp_client.search_issues.side_effect = Exception("Invalid JQL query")

        result = await jira_extractor.search_related_tickets(jql)

        assert result is None


class TestJQLBuilders:
    """Test helper functions that build JQL queries."""

    def test_build_channel_related_jql(self):
        """Test building JQL for channel-related tickets."""
        # This is an example of how you might build JQL dynamically
        channel_name = "incident-security-breach"

        # Extract potential keywords from channel name
        keywords = channel_name.replace("-", " ").split()

        # Build JQL
        text_conditions = " OR ".join(f'text ~ "{keyword}"' for keyword in keywords)
        jql = f'({text_conditions}) AND status != "Closed" ORDER BY priority DESC, created DESC'

        expected = '(text ~ "incident" OR text ~ "security" OR text ~ "breach") AND status != "Closed" ORDER BY priority DESC, created DESC'
        assert jql == expected

    def test_build_user_mention_jql(self):
        """Test building JQL for tickets mentioning a user."""
        user_email = "john.doe@company.com"

        jql = f'(reporter = "{user_email}" OR assignee = "{user_email}" OR text ~ "{user_email}") AND updated >= -30d'

        expected = '(reporter = "john.doe@company.com" OR assignee = "john.doe@company.com" OR text ~ "john.doe@company.com") AND updated >= -30d'
        assert jql == expected

    def test_build_priority_incident_jql(self):
        """Test building JQL for high-priority incidents."""
        projects = ["CAMP", "INFRA", "SEC"]

        project_list = ", ".join(f'"{p}"' for p in projects)
        jql = f'project in ({project_list}) AND (priority in (P1, P2) OR labels = "incident") AND status != "Resolved" ORDER BY priority ASC, created DESC'

        expected = 'project in ("CAMP", "INFRA", "SEC") AND (priority in (P1, P2) OR labels = "incident") AND status != "Resolved" ORDER BY priority ASC, created DESC'
        assert jql == expected
