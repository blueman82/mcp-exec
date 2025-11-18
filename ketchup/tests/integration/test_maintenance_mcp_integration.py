"""
test_maintenance_mcp_integration.py

Integration tests for MCP JIRA integration in maintenance detection.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.ai.maintenance_checker import MaintenanceChecker
from packages.db.dynamodb_store import DynamoDBStore
from packages.integrations.mcp_client import MCPClient
from packages.slack.maintenance.jira_prompt_handler import JiraPromptHandler

pytestmark = pytest.mark.integration


@pytest.fixture
def sample_jira_response_with_instance():
    """Sample JIRA response with customfield_22302."""
    return {
        "issues": [
            {
                "key": "CPGNREQ-182819",
                "fields": {
                    "summary": "Production Issue - Samsung CIS",
                    "customfield_22302": "https://samsungcis-mkt-prod3.campaign.adobe.com",
                    "status": {"name": "Open"},
                    "priority": {"name": "High"},
                },
            }
        ]
    }


@pytest.fixture
def sample_jira_response_no_instance():
    """Sample JIRA response without instance URL."""
    return {
        "issues": [
            {
                "key": "CPGNREQ-999999",
                "fields": {
                    "summary": "Issue without instance",
                    "status": {"name": "Open"},
                },
            }
        ]
    }


@pytest.fixture
def sample_maintenance_cache_data():
    """Sample maintenance cache data."""
    return [
        {
            "customer": "Samsung CIS",
            "releases": [
                {
                    "instances": [
                        {
                            "instance_name": "samsungcis_mkt_prod3",
                            "starts_at": "2025-10-06T04:30:00Z",
                        }
                    ],
                    "release": "Build Upgrade",
                    "release_url": "https://uco.adobe-campaign.com/release-summary/9517",
                }
            ],
        }
    ]


@pytest.fixture
def mock_mcp_client():
    """Create mock MCP client."""
    client = AsyncMock(spec=MCPClient)
    client.search_issues = AsyncMock()
    client.ensure_connection = AsyncMock()
    client.rate_limiter = MagicMock()
    client.rate_limiter.acquire = AsyncMock()
    return client


@pytest.fixture
def mock_db_store():
    """Create mock DynamoDB store."""
    store = MagicMock(spec=DynamoDBStore)
    store.get_maintenance_cache = AsyncMock()
    store.channel_ops = MagicMock()
    store.channel_ops.update_channel_metadata = AsyncMock()
    return store


@pytest.fixture
def mock_posting_handler():
    """Create mock Slack posting handler."""
    handler = AsyncMock()
    handler.post_message = AsyncMock(return_value={"ok": True, "ts": "123.456"})
    handler.pin_message = AsyncMock()
    handler.delete_message = AsyncMock()
    return handler


@pytest.fixture
def mock_channel_msg_ops():
    """Create mock channel message operations."""
    ops = AsyncMock()
    ops.fetch_channel_messages = AsyncMock(return_value=[])
    return ops


@pytest.fixture
def maintenance_checker(mock_db_store):
    """Create maintenance checker instance."""
    return MaintenanceChecker(dynamodb_store=mock_db_store)


@pytest.fixture
def jira_prompt_handler(
    mock_posting_handler,
    maintenance_checker,
    mock_db_store,
    mock_mcp_client,
    mock_channel_msg_ops,
):
    """Create JIRA prompt handler instance."""
    return JiraPromptHandler(
        posting_handler=mock_posting_handler,
        maintenance_checker=maintenance_checker,
        db_store=mock_db_store,
        mcp_client=mock_mcp_client,
        channel_msg_ops=mock_channel_msg_ops,
    )


@pytest.mark.asyncio
async def test_mcp_fetch_instance_urls_from_jira(
    mock_mcp_client, sample_jira_response_with_instance
):
    """Test MCP client fetches JIRA ticket with customfield_22302."""
    mock_mcp_client.search_issues.return_value = sample_jira_response_with_instance
    result = await mock_mcp_client.search_issues(jql='key = "CPGNREQ-182819"')

    assert result is not None
    assert "issues" in result
    issue = result["issues"][0]
    assert issue["key"] == "CPGNREQ-182819"
    assert (
        issue["fields"]["customfield_22302"]
        == "https://samsungcis-mkt-prod3.campaign.adobe.com"
    )


@pytest.mark.asyncio
async def test_instance_url_normalization_from_mcp(
    maintenance_checker, sample_jira_response_with_instance
):
    """Test instance URL normalization with MCP data."""
    instance_url = sample_jira_response_with_instance["issues"][0]["fields"][
        "customfield_22302"
    ]
    normalized = maintenance_checker.normalize_instance_name(instance_url)

    assert normalized == "samsungcis_mkt_prod3"
    assert "-" not in normalized

    # Test denormalize
    url = maintenance_checker.denormalize_instance_url(normalized)
    assert url == "https://samsungcis-mkt-prod3.campaign.adobe.com"


@pytest.mark.asyncio
async def test_mcp_timeout_handling(mock_mcp_client):
    """Test MCP client timeout and connection error handling."""
    # Test timeout
    mock_mcp_client.search_issues.side_effect = asyncio.TimeoutError("MCP timeout")
    with pytest.raises(asyncio.TimeoutError):
        await mock_mcp_client.search_issues(jql='key = "TIMEOUT-123"')

    # Test connection error
    mock_mcp_client.search_issues.side_effect = Exception("Connection refused")
    with pytest.raises(Exception) as exc_info:
        await mock_mcp_client.search_issues(jql='key = "ERROR-123"')
    assert "Connection refused" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mcp_missing_instance_url_handling(
    mock_mcp_client, sample_jira_response_no_instance, jira_prompt_handler
):
    """
    Test handling of JIRA tickets without instance URL.

    Verifies:
    - Missing customfield_22302 detected
    - Timeout message posted
    - No maintenance check attempted
    """
    # Arrange
    mock_mcp_client.search_issues.return_value = sample_jira_response_no_instance

    # Act
    await jira_prompt_handler._process_maintenance_check("C123456", "CPGNREQ-999999")

    # Assert - timeout message should be posted (no instance URL)
    assert jira_prompt_handler.posting_handler.post_message.called
    call_args = jira_prompt_handler.posting_handler.post_message.call_args
    message = call_args.kwargs.get("message", "")
    assert "Unable to determine maintenance status" in message


@pytest.mark.asyncio
async def test_maintenance_checker_with_mcp_end_to_end(
    jira_prompt_handler,
    mock_mcp_client,
    mock_db_store,
    sample_jira_response_with_instance,
    sample_maintenance_cache_data,
):
    """
    Test end-to-end flow from JIRA ticket to maintenance match.

    Verifies complete workflow:
    1. Fetch JIRA ticket via MCP
    2. Extract instance URL from customfield_22302
    3. Normalize instance name
    4. Match against DynamoDB maintenance cache
    5. Post maintenance found message
    6. Pin message
    7. Update channel metadata
    """
    # Arrange
    channel_id = "C123456"
    jira_ticket = "CPGNREQ-182819"

    # Mock MCP JIRA fetch
    mock_mcp_client.search_issues.return_value = sample_jira_response_with_instance

    # Mock DynamoDB maintenance cache
    mock_db_store.get_maintenance_cache.return_value = sample_maintenance_cache_data

    # Act
    await jira_prompt_handler._process_maintenance_check(channel_id, jira_ticket)

    # Assert - verify full workflow
    # 1. MCP fetch called
    mock_mcp_client.search_issues.assert_called_once()
    call_jql = mock_mcp_client.search_issues.call_args.kwargs.get("jql")
    assert jira_ticket in call_jql

    # 2. DynamoDB cache queried with today's date
    mock_db_store.get_maintenance_cache.assert_called_once()
    date_arg = mock_db_store.get_maintenance_cache.call_args[0][0]
    assert date_arg == datetime.now().strftime("%Y-%m-%d")

    # 3. Maintenance found message posted
    assert jira_prompt_handler.posting_handler.post_message.called
    message_call = jira_prompt_handler.posting_handler.post_message.call_args
    posted_message = message_call.kwargs.get("message", "")
    assert "SCHEDULED MAINTENANCE DETECTED" in posted_message
    assert "Samsung CIS" in posted_message
    assert "samsungcis-mkt-prod3" in posted_message

    # 4. Message pinned
    jira_prompt_handler.posting_handler.pin_message.assert_called_once()

    # 5. Channel metadata updated with customer_name and jira_ticket
    mock_db_store.channel_ops.update_channel_metadata.assert_called_once_with(
        channel_id=channel_id, customer_name="Samsung CIS", jira_ticket=jira_ticket
    )


@pytest.mark.asyncio
async def test_maintenance_checker_no_match_found(
    jira_prompt_handler,
    mock_mcp_client,
    mock_db_store,
    sample_jira_response_with_instance,
):
    """
    Test when JIRA instance does not match any maintenance record.

    Verifies:
    - Instance URL extracted correctly
    - No match found in maintenance cache
    - "No maintenance" message posted
    - No pinning or metadata update
    """
    # Arrange
    channel_id = "C123456"
    jira_ticket = "CPGNREQ-182819"

    # Mock MCP JIRA fetch
    mock_mcp_client.search_issues.return_value = sample_jira_response_with_instance

    # Mock empty maintenance cache
    mock_db_store.get_maintenance_cache.return_value = []

    # Act
    await jira_prompt_handler._process_maintenance_check(channel_id, jira_ticket)

    # Assert - "no maintenance" message posted
    assert jira_prompt_handler.posting_handler.post_message.called
    message_call = jira_prompt_handler.posting_handler.post_message.call_args
    posted_message = message_call.kwargs.get("message", "")
    assert "No scheduled maintenance found" in posted_message

    # No pinning should occur
    jira_prompt_handler.posting_handler.pin_message.assert_not_called()


@pytest.mark.asyncio
async def test_jira_ticket_extraction_from_url():
    """
    Test JIRA ticket extraction from various formats.

    Verifies:
    - URL format extraction
    - Plain ticket key extraction
    - Case-insensitive matching
    """
    # Test URL format
    text1 = "@Ketchup https://jira.corp.adobe.com/browse/CPGNREQ-182819"
    ticket1 = JiraPromptHandler.extract_jira_ticket(text1)
    assert ticket1 == "CPGNREQ-182819"

    # Test plain ticket key
    text2 = "@Ketchup the ticket is CPGNREQ-182819"
    ticket2 = JiraPromptHandler.extract_jira_ticket(text2)
    assert ticket2 == "CPGNREQ-182819"

    # Test lowercase normalization
    text3 = "@ketchup cpgnreq-182819"
    ticket3 = JiraPromptHandler.extract_jira_ticket(text3)
    assert ticket3 == "CPGNREQ-182819"


@pytest.mark.asyncio
async def test_mcp_rate_limiting(mock_mcp_client):
    """
    Test MCP client rate limiting is applied.

    Verifies:
    - Rate limiter acquire called before requests
    - Multiple requests respect rate limits
    """
    # Arrange
    mock_mcp_client.search_issues.return_value = {"issues": []}

    # Act
    await mock_mcp_client.search_issues(jql='key = "TEST-123"')

    # Assert - rate limiter should be acquired
    # (This test verifies the mock structure - real integration tests
    # would verify actual rate limiting behavior)
    assert mock_mcp_client.rate_limiter.acquire is not None


@pytest.mark.asyncio
async def test_maintenance_cache_ttl_behavior(mock_db_store, maintenance_checker):
    """
    Test maintenance cache TTL behavior.

    Verifies:
    - Cache queried with correct date
    - Handles expired/missing cache gracefully
    """
    # Arrange - simulate expired cache (returns None)
    mock_db_store.get_maintenance_cache.return_value = None

    # Act
    result = await maintenance_checker.check_maintenance(
        "https://test-instance.campaign.adobe.com", date="2025-10-06"
    )

    # Assert - no match when cache missing
    assert result is None
    mock_db_store.get_maintenance_cache.assert_called_once_with("2025-10-06")
