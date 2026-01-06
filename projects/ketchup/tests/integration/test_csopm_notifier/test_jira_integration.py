"""
Integration test for CSOPM JIRA poller with MCP client.

Tests the integration between CSOPMJIRAPoller and AsyncMCPClient
to verify proper CSOPM ticket discovery works with the MCP client.

Requires:
- MCP_BASE_URL environment variable or running MCP-JIRA server
- AWS_PROFILE for secrets access (IMS token manager)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller
from packages.integrations.async_ims_token_manager import AsyncIMSTokenManager
from packages.integrations.async_mcp_client import AsyncMCPClient


@pytest.mark.asyncio
class TestCSOPMJIRAPollerIntegration:
    """Test CSOPM JIRA poller with MCP client integration."""

    @pytest.fixture
    async def mock_ims_token_manager(self):
        """Create a mock IMS token manager."""
        token_manager = MagicMock(spec=AsyncIMSTokenManager)
        token_manager.get_valid_token = AsyncMock(return_value="mock-token-123")
        return token_manager

    @pytest.fixture
    async def mcp_client(self, mock_ims_token_manager):
        """Create an MCP client with mocked HTTP responses."""
        client = AsyncMCPClient(
            base_url="http://test-mcp-server:8080",
            token_manager=mock_ims_token_manager,
        )

        # Mock the session establishment
        with patch.object(client, "_establish_mcp_session", new_callable=AsyncMock) as mock_establish:
            mock_establish.return_value = "test-session-id"
            yield client

    @pytest.fixture
    def poller(self, mcp_client):
        """Create CSOPMJIRAPoller with MCP client."""
        return CSOPMJIRAPoller(mcp_client=mcp_client)

    async def test_poll_for_new_assignments_integration(self, poller, mcp_client):
        """Test polling for new CSOPM assignments with mocked MCP responses."""
        # Arrange - Mock JIRA search response with new assignments
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "issues": [
                                    {
                                        "key": "CSOPM-12345",
                                        "fields": {
                                            "summary": "New CSOPM ticket for testing",
                                            "description": "Test ticket with Exigence URL https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom",
                                            "status": {"name": "New"},
                                            "assignee": {
                                                "name": "testuser",
                                                "displayName": "Test User",
                                            },
                                            "created": "2025-01-06T10:30:00.000+0000",
                                        },
                                    },
                                    {
                                        "key": "CSOPM-12346",
                                        "fields": {
                                            "summary": "Another CSOPM ticket",
                                            "description": "No Exigence URL here",
                                            "status": {"name": "New"},
                                            "assignee": {
                                                "name": "testuser2",
                                                "displayName": "Test User 2",
                                            },
                                            "created": "2025-01-06T11:00:00.000+0000",
                                        },
                                    },
                                ]
                            }
                        ),
                    }
                ]
            },
        }

        with patch.object(mcp_client, "_make_api_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "status": 200,
                "body": json.dumps(mock_response),
                "headers": {},
            }

            # Act
            tickets = await poller.poll_for_new_assignments()

            # Assert
            assert len(tickets) == 2
            assert tickets[0].key == "CSOPM-12345"
            assert tickets[0].assignee_username == "testuser"
            assert tickets[0].status == "New"
            assert tickets[0].exigence_id == "78155"

            assert tickets[1].key == "CSOPM-12346"
            assert tickets[1].assignee_username == "testuser2"
            assert tickets[1].exigence_id is None  # No Exigence URL

            # Verify JQL query was correct
            mock_request.assert_called()
            call_args = mock_request.call_args
            request_data = call_args.kwargs.get("json_data")
            jql = request_data["params"]["arguments"]["jql"]
            assert "project = CSOPM" in jql
            assert "status = 'New'" in jql

    async def test_poll_no_new_assignments(self, poller, mcp_client):
        """Test polling when no new assignments are found."""
        # Arrange - Empty response
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": json.dumps({"issues": []})}]},
        }

        with patch.object(mcp_client, "_make_api_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "status": 200,
                "body": json.dumps(mock_response),
                "headers": {},
            }

            # Act
            tickets = await poller.poll_for_new_assignments()

            # Assert
            assert tickets == []

    async def test_get_ticket_details_integration(self, poller, mcp_client):
        """Test getting specific ticket details."""
        # Arrange
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "key": "CSOPM-99999",
                                "fields": {
                                    "summary": "Detailed CSOPM ticket",
                                    "description": "Full description with https://adobe.app.exigence.io/secure/index.html#/events/123456/situationroom",
                                    "status": {"name": "In Progress"},
                                    "assignee": {"name": "csopmuser"},
                                    "created": "2025-01-06T09:00:00.000+0000",
                                },
                            }
                        ),
                    }
                ]
            },
        }

        # Mock search_issues which is called by get_issue internally
        mock_search_result = {
            "issues": [
                {
                    "key": "CSOPM-99999",
                    "fields": {
                        "summary": "Detailed CSOPM ticket",
                        "description": "Full description with https://adobe.app.exigence.io/secure/index.html#/events/123456/situationroom",
                        "status": {"name": "In Progress"},
                        "assignee": {"name": "csopmuser"},
                        "created": "2025-01-06T09:00:00.000+0000",
                    },
                }
            ]
        }

        with patch.object(mcp_client, "search_issues", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_search_result

            # Act
            ticket = await poller.get_ticket_details("CSOPM-99999")

            # Assert
            assert ticket is not None
            assert ticket.key == "CSOPM-99999"
            assert ticket.summary == "Detailed CSOPM ticket"
            assert ticket.status == "In Progress"
            assert ticket.assignee_username == "csopmuser"
            assert ticket.exigence_id == "123456"

    async def test_get_tickets_by_assignee_integration(self, poller, mcp_client):
        """Test getting all active tickets for an assignee."""
        # Arrange
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "issues": [
                                    {
                                        "key": "CSOPM-11111",
                                        "fields": {
                                            "summary": "First assigned ticket",
                                            "status": {"name": "In Progress"},
                                            "assignee": {"name": "csopmassignee"},
                                            "created": "2025-01-05T10:00:00.000+0000",
                                        },
                                    },
                                    {
                                        "key": "CSOPM-22222",
                                        "fields": {
                                            "summary": "Second assigned ticket",
                                            "status": {"name": "New"},
                                            "assignee": {"name": "csopmassignee"},
                                            "created": "2025-01-06T10:00:00.000+0000",
                                        },
                                    },
                                ]
                            }
                        ),
                    }
                ]
            },
        }

        with patch.object(mcp_client, "_make_api_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "status": 200,
                "body": json.dumps(mock_response),
                "headers": {},
            }

            # Act
            tickets = await poller.get_tickets_by_assignee("csopmassignee")

            # Assert
            assert len(tickets) == 2
            assert all(t.assignee_username == "csopmassignee" for t in tickets)

            # Verify JQL includes assignee filter
            call_args = mock_request.call_args
            request_data = call_args.kwargs.get("json_data")
            jql = request_data["params"]["arguments"]["jql"]
            assert "csopmassignee" in jql
            assert "status NOT IN" in jql

    async def test_mcp_authentication_error_handling(self, poller, mcp_client):
        """Test handling of MCP authentication errors."""
        # Arrange - Authentication error
        mock_error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32603, "message": "Authentication failed"},
        }

        with patch.object(mcp_client, "_make_api_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "status": 401,
                "body": json.dumps(mock_error_response),
                "headers": {},
            }

            # Act
            tickets = await poller.poll_for_new_assignments()

            # Assert - Should handle error gracefully and return empty list
            assert tickets == []

    async def test_exigence_id_extraction_patterns(self, poller):
        """Test Exigence ID extraction from various URL patterns."""
        # Test various description patterns
        test_cases = [
            # Standard 5-digit Exigence URL
            (
                "Event link: https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom",
                "78155",
            ),
            # 6-digit Exigence URL
            (
                "See https://adobe.app.exigence.io/secure/index.html#/events/123456/situationroom for details",
                "123456",
            ),
            # Multiple Exigence URLs (should extract first)
            (
                "/events/11111/situationroom and /events/22222/situationroom",
                "11111",
            ),
            # No Exigence URL
            ("Normal description without any URL", None),
            # Empty description
            ("", None),
            # None description
            (None, None),
        ]

        for description, expected_id in test_cases:
            result = poller._extract_exigence_id(description)
            assert result == expected_id, f"Failed for description: {description}"

    async def test_parse_jira_issue_missing_assignee(self, poller):
        """Test parsing issue with missing assignee returns None."""
        issue = {
            "key": "CSOPM-12345",
            "fields": {
                "summary": "Test ticket",
                "status": {"name": "New"},
                "assignee": None,  # No assignee
                "created": "2025-01-06T10:00:00.000+0000",
            },
        }

        result = poller._parse_jira_issue(issue)
        assert result is None

    async def test_parse_jira_issue_empty_assignee_username(self, poller):
        """Test parsing issue with empty assignee username returns None."""
        issue = {
            "key": "CSOPM-12345",
            "fields": {
                "summary": "Test ticket",
                "status": {"name": "New"},
                "assignee": {"name": "", "displayName": ""},  # Empty names
                "created": "2025-01-06T10:00:00.000+0000",
            },
        }

        result = poller._parse_jira_issue(issue)
        assert result is None

    async def test_parse_jira_issue_invalid_date(self, poller):
        """Test parsing issue with invalid created date uses current time."""
        issue = {
            "key": "CSOPM-12345",
            "fields": {
                "summary": "Test ticket",
                "status": {"name": "New"},
                "assignee": {"name": "testuser"},
                "created": "invalid-date-format",
            },
        }

        result = poller._parse_jira_issue(issue)
        # Should succeed but use current time for created_at
        assert result is not None
        assert result.key == "CSOPM-12345"


@pytest.mark.asyncio
class TestCSOPMJIRAPollerConstants:
    """Test CSOPM JIRA poller constants and configuration."""

    def test_new_assignments_jql_query(self):
        """Test the JQL query for new assignments is correctly formatted."""
        assert "project = CSOPM" in CSOPMJIRAPoller.NEW_ASSIGNMENTS_JQL
        assert "assignee IS NOT EMPTY" in CSOPMJIRAPoller.NEW_ASSIGNMENTS_JQL
        assert "status = 'New'" in CSOPMJIRAPoller.NEW_ASSIGNMENTS_JQL
        assert "created >= -1d" in CSOPMJIRAPoller.NEW_ASSIGNMENTS_JQL

    def test_default_fields(self):
        """Test the default fields to retrieve from JIRA."""
        expected_fields = ["summary", "status", "assignee", "created", "description"]
        assert CSOPMJIRAPoller.DEFAULT_FIELDS == expected_fields
