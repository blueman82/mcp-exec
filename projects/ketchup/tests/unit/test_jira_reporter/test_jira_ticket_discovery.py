"""
Unit tests for the JIRA ticket discovery service.

Tests the JiraTicketDiscovery class that extracts Exigence IDs from channel names
and searches for associated JIRA tickets.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from jira_reporter.jira_ticket_discovery import JiraTicketDiscovery


class TestJiraTicketDiscovery:
    """Test the JiraTicketDiscovery functionality."""

    @pytest.fixture
    def mock_mcp_client(self):
        """Create a mock MCP client."""
        client = MagicMock()
        client.search_issues = AsyncMock()
        return client

    @pytest.fixture
    def discovery_service(self, mock_mcp_client):
        """Create a JiraTicketDiscovery instance with mocked MCP client."""
        return JiraTicketDiscovery(mcp_client=mock_mcp_client)

    def test_extract_exigence_id_from_channel_names(self, discovery_service):
        """Test extraction of 5-digit Exigence IDs from various channel name formats."""
        # Test cases with expected results
        test_cases = [
            ("cso_202506160038_adobe_campaign_78155", "78155"),
            ("#st_cso_202507010005_acc_samsungeu_78993", "78993"),
            ("sit_room_202505280031_acs_stena_76893", "76893"),
            ("cso_202501010001_customer_12345", "12345"),
            ("cso_stock_incident_98765", "98765"),  # Adobe Stock channel
            ("test_channel_no_numbers", None),
            ("channel_123", None),  # Too few digits
            ("channel_123456", None),  # Too many digits
            ("202501010001_no_exigence", None),  # Only date, no 5-digit ID
        ]

        for channel_name, expected_id in test_cases:
            result = discovery_service.extract_exigence_id(channel_name)
            assert result == expected_id, f"Failed for channel: {channel_name}"

    def test_build_exigence_url(self, discovery_service):
        """Test building Exigence URLs from event IDs."""
        event_id = "78155"
        expected_url = "https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom"

        result = discovery_service.build_exigence_url(event_id)
        assert result == expected_url

    @pytest.mark.asyncio
    async def test_search_jira_by_exigence_url_csopm_found(
        self, discovery_service, mock_mcp_client
    ):
        """Test successful JIRA search in CSOPM project."""
        # Arrange
        exigence_url = "https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom"
        mock_response = {
            "issues": [{"key": "CSOPM-12345", "fields": {"summary": "Test issue"}}]
        }
        mock_mcp_client.search_issues.return_value = mock_response

        # Act
        result = await discovery_service.search_jira_by_exigence_url(exigence_url)

        # Assert
        assert result == "CSOPM-12345"
        mock_mcp_client.search_issues.assert_called_once()
        call_args = mock_mcp_client.search_issues.call_args
        assert 'project = "CSO Problem Management"' in call_args[0][0]
        assert exigence_url in call_args[0][0]

    @pytest.mark.asyncio
    async def test_search_jira_by_exigence_url_extended_search(
        self, discovery_service, mock_mcp_client
    ):
        """Test extended JIRA search across multiple projects."""
        # Arrange
        exigence_url = "https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom"
        customer_name = "Adobe Campaign"

        # First call returns empty (CSOPM search)
        mock_mcp_client.search_issues.side_effect = [
            {"issues": []},  # CSOPM search - no results
            {  # Extended search - finds results
                "issues": [
                    {"key": "CPGNREQ-11111", "fields": {"summary": "Other issue"}},
                    {"key": "CSOPM-22222", "fields": {"summary": "CSOPM issue"}},
                    {"key": "NEO-33333", "fields": {"summary": "NEO issue"}},
                    {"key": "STKOPS-44444", "fields": {"summary": "Stock issue"}},
                ]
            },
        ]

        # Act
        result = await discovery_service.search_jira_by_exigence_url(
            exigence_url, customer_name
        )

        # Assert
        assert result == "CSOPM-22222"  # Prefers CSOPM even in extended search
        assert mock_mcp_client.search_issues.call_count == 2

        # Check extended search includes customer name
        second_call = mock_mcp_client.search_issues.call_args_list[1]
        assert customer_name in second_call[0][0]

    @pytest.mark.asyncio
    async def test_search_jira_by_exigence_url_no_results(
        self, discovery_service, mock_mcp_client
    ):
        """Test JIRA search when no tickets are found."""
        # Arrange
        exigence_url = "https://adobe.app.exigence.io/secure/index.html#/events/99999/situationroom"
        mock_mcp_client.search_issues.side_effect = [
            {"issues": []},  # CSOPM search
            {"issues": []},  # Extended search
        ]

        # Act
        result = await discovery_service.search_jira_by_exigence_url(exigence_url)

        # Assert
        assert result is None
        assert mock_mcp_client.search_issues.call_count == 2

    @pytest.mark.asyncio
    async def test_search_jira_handles_json_errors(
        self, discovery_service, mock_mcp_client
    ):
        """Test handling of malformed JSON responses."""
        # Arrange
        exigence_url = "https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom"
        mock_mcp_client.search_issues.side_effect = Exception("API Error")

        # Act
        result = await discovery_service.search_jira_by_exigence_url(exigence_url)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_search_jira_handles_exceptions(
        self, discovery_service, mock_mcp_client
    ):
        """Test handling of exceptions during JIRA search."""
        # Arrange
        exigence_url = "https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom"
        mock_mcp_client.search_issues.side_effect = Exception("API Error")

        # Act
        result = await discovery_service.search_jira_by_exigence_url(exigence_url)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_discover_jira_ticket_with_existing_valid_ticket(
        self, discovery_service, mock_mcp_client
    ):
        """Test discovery when channel already has a valid JIRA ticket."""
        # Arrange
        channel_metadata = {
            "channel_name": "cso_202501010001_customer_12345",
            "jira_ticket": "CPGNREQ-12345",
        }

        # Act
        result = await discovery_service.discover_jira_ticket(
            channel_metadata["channel_name"], channel_metadata
        )

        # Assert
        assert result == "CPGNREQ-12345"
        # Should not call search since ticket already exists
        # The mcp_client is mocked at the fixture level
        assert mock_mcp_client.search_issues.call_count == 0

    @pytest.mark.asyncio
    async def test_discover_jira_ticket_no_exigence_id(
        self, discovery_service, mock_mcp_client
    ):
        """Test discovery when channel name has no Exigence ID."""
        # Arrange
        channel_metadata = {"channel_name": "general_discussion", "jira_ticket": ""}

        # Act
        result = await discovery_service.discover_jira_ticket(
            channel_metadata["channel_name"], channel_metadata
        )

        # Assert
        assert result is None
        # Should not call search since no Exigence ID
        assert mock_mcp_client.search_issues.call_count == 0

    @pytest.mark.asyncio
    async def test_discover_jira_ticket_full_flow(
        self, discovery_service, mock_mcp_client
    ):
        """Test full discovery flow from channel name to JIRA ticket."""
        # Arrange
        channel_metadata = {
            "channel_name": "cso_202501010001_customer_78155",
            "jira_ticket": "NOT YET AVAILABLE",
            "customer_name": "Adobe Campaign",
        }

        mock_response = {"issues": [{"key": "CSOPM-78155"}]}
        mock_mcp_client.search_issues.return_value = mock_response

        # Act
        result = await discovery_service.discover_jira_ticket(
            channel_metadata["channel_name"], channel_metadata
        )

        # Assert
        assert result == "CSOPM-78155"

        # Verify the URL was constructed correctly
        call_args = mock_mcp_client.search_issues.call_args
        assert "78155/situationroom" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_mcp_client_configured(self):
        """Test behavior when no MCP client is configured."""
        # Arrange
        discovery_no_client = JiraTicketDiscovery(mcp_client=None)

        # Act
        result = await discovery_no_client.search_jira_by_exigence_url(
            "https://adobe.app.exigence.io/secure/index.html#/events/12345/situationroom"
        )

        # Assert
        assert result is None
