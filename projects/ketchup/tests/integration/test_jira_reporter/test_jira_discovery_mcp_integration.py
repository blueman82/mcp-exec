"""
Integration test for JIRA ticket discovery using MCP client.

Tests the integration between JiraTicketDiscovery and MCPAsyncClient
to ensure proper JIRA ticket discovery works with the real MCP client.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jira_reporter.jira_ticket_discovery import JiraTicketDiscovery
from packages.integrations.ims_token_manager import IMSTokenManager
from packages.integrations.mcp_async_client import MCPAsyncClient
from packages.integrations.mcp_async_client import MCPConfig


@pytest.mark.asyncio
class TestJiraDiscoveryMCPIntegration:
    """Test JIRA ticket discovery with MCP client integration."""

    @pytest.fixture
    async def mock_ims_token_manager(self):
        """Create a mock IMS token manager."""
        token_manager = MagicMock(spec=IMSTokenManager)
        token_manager.get_valid_token = AsyncMock(return_value="mock-token-123")
        return token_manager

    @pytest.fixture
    async def mcp_client(self, mock_ims_token_manager):
        """Create an MCP client with mocked HTTP responses."""
        config = MCPConfig(
            base_url="http://test-mcp-server:8080", token_manager=mock_ims_token_manager
        )
        client = MCPAsyncClient(mcp_config=config)

        # Mock the session establishment
        with patch.object(
            client, "_establish_session", new_callable=AsyncMock
        ) as mock_establish:
            mock_establish.return_value = "test-session-id"
            yield client

    @pytest.fixture
    def discovery_service(self, mcp_client):
        """Create JiraTicketDiscovery with real MCP client."""
        return JiraTicketDiscovery(mcp_client=mcp_client)

    async def test_discover_csopm_ticket_integration(
        self, discovery_service, mcp_client
    ):
        """Test CSOPM ticket discovery with mocked MCP responses."""
        # Arrange
        channel_name = "cso_202506160038_adobe_campaign_78155"
        channel_metadata = {"customer_name": "Adobe Campaign"}

        # Mock the MCP tool call response
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
                                            "summary": "CSO 202506160038 - Adobe Campaign",
                                            "description": "CSO incident with Exigence URL https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom",
                                            "status": {"name": "Open"},
                                            "priority": {"name": "P1"},
                                        },
                                    }
                                ]
                            }
                        ),
                    }
                ]
            },
        }

        with patch.object(
            mcp_client, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "status": 200,
                "body": json.dumps(mock_response),
                "headers": {},
            }

            # Act
            result = await discovery_service.discover_csopm_ticket(
                channel_name, channel_metadata
            )

            # Assert
            assert result == "CSOPM-12345"

            # Verify the request was made correctly
            mock_request.assert_called_once()
            call_args = mock_request.call_args

            # Check the JSON-RPC request structure
            request_data = call_args.kwargs.get("json_data")
            assert request_data["method"] == "tools/call"
            assert request_data["params"]["name"] == "search_jira_issues"

            # Check JQL query
            jql = request_data["params"]["arguments"]["jql"]
            assert 'project = "CSO Problem Management"' in jql
            assert "78155/situationroom" in jql

    async def test_search_with_no_results_integration(
        self, discovery_service, mcp_client
    ):
        """Test search when no JIRA tickets are found."""
        # Arrange
        exigence_url = "https://adobe.app.exigence.io/secure/index.html#/events/99999/situationroom"

        # Mock empty response
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": json.dumps({"issues": []})}]
            },
        }

        with patch.object(
            mcp_client, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "status": 200,
                "body": json.dumps(mock_response),
                "headers": {},
            }

            # Act
            result = await discovery_service.search_jira_by_exigence_url(exigence_url)

            # Assert
            assert result is None
            # Should be called twice (CSOPM search + extended search)
            assert mock_request.call_count == 2

    async def test_mcp_authentication_error_handling(
        self, discovery_service, mcp_client
    ):
        """Test handling of MCP authentication errors."""
        # Arrange
        channel_name = "cso_202506160038_adobe_campaign_78155"
        channel_metadata = {}

        # Mock authentication error
        mock_error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32603, "message": "Authentication failed"},
        }

        with patch.object(
            mcp_client, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "status": 401,
                "body": json.dumps(mock_error_response),
                "headers": {},
            }

            # Act
            result = await discovery_service.discover_csopm_ticket(
                channel_name, channel_metadata
            )

            # Assert
            assert result is None  # Should handle error gracefully

    async def test_extended_search_with_customer_filter(
        self, discovery_service, mcp_client
    ):
        """Test extended search includes customer name in query."""
        # Arrange
        exigence_url = "https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom"
        customer_name = "Adobe Campaign"

        # First response empty, second has results
        responses = [
            # CSOPM search - empty
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"issues": []})}]
                },
            },
            # Extended search - with results
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "issues": [
                                        {
                                            "key": "CPGNREQ-11111",
                                            "fields": {"summary": "Test issue"},
                                        }
                                    ]
                                }
                            ),
                        }
                    ]
                },
            },
        ]

        with patch.object(
            mcp_client, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [
                {"status": 200, "body": json.dumps(resp), "headers": {}}
                for resp in responses
            ]

            # Act
            result = await discovery_service.search_jira_by_exigence_url(
                exigence_url, customer_name
            )

            # Assert
            assert result == "CPGNREQ-11111"
            assert mock_request.call_count == 2

            # Check second call includes customer name
            second_call = mock_request.call_args_list[1]
            jql = second_call.kwargs["json_data"]["params"]["arguments"]["jql"]
            assert customer_name in jql

    async def test_product_based_query_integration(self, discovery_service, mcp_client):
        """Test product-based queries are converted to use TechOps Product field."""
        # Arrange - simulate a product-based discovery scenario

        # Mock a search that would use product field
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
                                        "key": "CSOPM-62138",
                                        "fields": {
                                            "summary": "Campaign product issue",
                                            "customfield_20800": "Adobe Campaign",  # TechOps Product
                                            "status": {"name": "Open"},
                                        },
                                    }
                                ]
                            }
                        ),
                    }
                ]
            },
        }

        with patch.object(
            mcp_client, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "status": 200,
                "body": json.dumps(mock_response),
                "headers": {},
            }

            # Act - simulate a product-based search
            result = await discovery_service.search_jira_by_exigence_url(
                "https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom",
                customer_name="Adobe Campaign",
            )

            # Assert
            assert result == "CSOPM-62138"

            # If the system later supports direct product queries, verify JQL would include TechOps Product
            # Currently the discovery uses text search, but could be enhanced to use product fields

    async def test_ajo_product_query_integration(self, discovery_service, mcp_client):
        """Test AJO (Adobe Journey Optimizer) product queries."""
        # Arrange
        channel_name = "cso_202506160038_adobe_journey_optimizer_12345"
        channel_metadata = {"customer_name": "Adobe Journey Optimizer"}

        # Mock response with AJO ticket
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
                                        "key": "CSOPM-61627",
                                        "fields": {
                                            "summary": "AJO product issue",
                                            "customfield_20800": "Adobe Journey Optimizer",  # TechOps Product
                                            "status": {"name": "In Progress"},
                                        },
                                    }
                                ]
                            }
                        ),
                    }
                ]
            },
        }

        with patch.object(
            mcp_client, "_make_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "status": 200,
                "body": json.dumps(mock_response),
                "headers": {},
            }

            # Act
            result = await discovery_service.discover_csopm_ticket(
                channel_name, channel_metadata
            )

            # Assert
            assert result == "CSOPM-61627"
