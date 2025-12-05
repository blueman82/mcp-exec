"""
test_jira_prompt_handler.py

Unit tests for JIRA prompt handler.

IMPORTANT: All JIRA ticket IDs in this file are synthetic test data.
Examples like "CPGNREQ-12345" are NOT real production tickets.
They follow JIRA naming conventions but are purely for testing purposes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.ai.maintenance_checker import MaintenanceChecker
from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.maintenance.jira_prompt_handler import JiraPromptHandler
from packages.slack.messages.posting import SlackPostingHandler


@pytest.fixture
def mock_posting_handler():
    """Create a mock Slack posting handler."""
    handler = MagicMock(spec=SlackPostingHandler)
    handler.post_message = AsyncMock()
    handler.delete_message = AsyncMock()
    handler.pin_message = AsyncMock()
    return handler


@pytest.fixture
def mock_maintenance_checker():
    """Create a mock maintenance checker."""
    checker = MagicMock(spec=MaintenanceChecker)
    checker.check_maintenance = AsyncMock()
    checker.normalize_instance_name = MagicMock(
        side_effect=lambda x: x.replace("https://", "")
        .replace(".campaign.adobe.com", "")
        .replace("-", "_")
    )
    checker.denormalize_instance_url = MagicMock(
        side_effect=lambda x: f"https://{x.replace('_', '-')}.campaign.adobe.com"
    )
    checker.format_maintenance_start_time = MagicMock(
        side_effect=lambda x: "06-10-2025 04:30:00" if x else x
    )
    return checker


@pytest.fixture
def mock_db_store():
    """Create a mock DynamoDB store."""
    store = MagicMock(spec=DynamoDBStore)
    store.channel_ops = MagicMock()
    store.channel_ops.update_channel_metadata = AsyncMock()
    return store


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP JIRA client."""
    client = MagicMock()
    client.search_issues = AsyncMock()
    return client


@pytest.fixture
def mock_channel_msg_ops():
    """Create a mock channel message operations."""
    ops = MagicMock()
    ops.fetch_channel_messages = AsyncMock()
    ops.get_api_base_url = AsyncMock(return_value="https://slack.com/api")
    ops.headers = {"Authorization": "Bearer token"}
    ops._make_api_request = AsyncMock(return_value={"messages": []})
    return ops


@pytest.fixture
def mock_secrets_manager():
    """Create a mock secrets manager."""
    manager = MagicMock(spec=SecretsManager)
    manager.get_bot_slack_user_id_async = AsyncMock(return_value="U084HFUQMFE")
    return manager


@pytest.fixture
def jira_prompt_handler(
    mock_posting_handler,
    mock_maintenance_checker,
    mock_db_store,
    mock_mcp_client,
    mock_channel_msg_ops,
    mock_secrets_manager,
):
    """Create a JIRA prompt handler instance."""
    return JiraPromptHandler(
        posting_handler=mock_posting_handler,
        maintenance_checker=mock_maintenance_checker,
        db_store=mock_db_store,
        mcp_client=mock_mcp_client,
        channel_msg_ops=mock_channel_msg_ops,
        secrets_manager=mock_secrets_manager,
    )


# ========== JIRA Ticket Extraction Tests ==========


def test_extract_jira_ticket_url_format():
    """Test extracting JIRA ticket from URL format."""
    text = "@Ketchup https://jira.corp.adobe.com/browse/CPGNREQ-182819"
    result = JiraPromptHandler.extract_jira_ticket(text)
    assert result == "CPGNREQ-182819"


def test_extract_jira_ticket_uppercase():
    """Test extracting uppercase JIRA ticket."""
    text = "@Ketchup CPGNREQ-182819"
    result = JiraPromptHandler.extract_jira_ticket(text)
    assert result == "CPGNREQ-182819"


def test_extract_jira_ticket_lowercase():
    """Test extracting lowercase JIRA ticket (returns uppercase)."""
    text = "@Ketchup cpgnreq-182819"
    result = JiraPromptHandler.extract_jira_ticket(text)
    assert result == "CPGNREQ-182819"


def test_extract_jira_ticket_invalid_format():
    """Test invalid format returns None."""
    text = "@Ketchup no ticket here"
    result = JiraPromptHandler.extract_jira_ticket(text)
    assert result is None


def test_extract_jira_ticket_partial_match():
    """Test partial ticket format returns None."""
    text = "@Ketchup CPGNREQ-"
    result = JiraPromptHandler.extract_jira_ticket(text)
    assert result is None


# ========== Message Posting Tests ==========


@pytest.mark.asyncio
async def test_post_jira_prompt_first_attempt(jira_prompt_handler, mock_posting_handler):
    """Test posting JIRA prompt on first attempt."""
    mock_posting_handler.post_message.return_value = {"ok": True, "ts": "123.456"}

    result = await jira_prompt_handler._post_jira_prompt("C123", 1)

    assert result == "123.456"
    mock_posting_handler.post_message.assert_called_once_with(
        channel_id="C123",
        message="🤖 *Ketchup needs information:* What is the JIRA ticket for this incident? Please `@mention` me with the ticket number.",
    )


@pytest.mark.asyncio
async def test_post_jira_prompt_second_attempt(jira_prompt_handler, mock_posting_handler):
    """Test posting JIRA prompt on second attempt."""
    mock_posting_handler.post_message.return_value = {"ok": True, "ts": "123.456"}

    result = await jira_prompt_handler._post_jira_prompt("C123", 2)

    assert result == "123.456"
    mock_posting_handler.post_message.assert_called_once_with(
        channel_id="C123",
        message="🤖 *Ketchup needs information:* What is the JIRA ticket for this incident? Please `@mention` me with the ticket number. _(Attempt 2/3)_",
    )


@pytest.mark.asyncio
async def test_post_jira_prompt_failure(jira_prompt_handler, mock_posting_handler):
    """Test posting JIRA prompt failure."""
    mock_posting_handler.post_message.return_value = {"ok": False}

    result = await jira_prompt_handler._post_jira_prompt("C123", 1)

    assert result is None


@pytest.mark.asyncio
async def test_post_jira_prompt_exception(jira_prompt_handler, mock_posting_handler):
    """Test posting JIRA prompt exception handling."""
    mock_posting_handler.post_message.side_effect = Exception("Test error")

    result = await jira_prompt_handler._post_jira_prompt("C123", 1)

    assert result is None


# ========== Message Deletion Tests ==========


@pytest.mark.asyncio
async def test_delete_prompt_message_success(jira_prompt_handler, mock_posting_handler):
    """Test deleting prompt message successfully."""
    jira_prompt_handler.active_prompts["C123"] = "123.456"

    result = await jira_prompt_handler._delete_prompt_message("C123")

    assert result is True
    assert "C123" not in jira_prompt_handler.active_prompts
    mock_posting_handler.delete_message.assert_called_once_with(
        channel_id="C123", message_ts="123.456"
    )


@pytest.mark.asyncio
async def test_delete_prompt_message_no_prompt(jira_prompt_handler):
    """Test deleting prompt when no prompt exists."""
    result = await jira_prompt_handler._delete_prompt_message("C123")

    assert result is False


@pytest.mark.asyncio
async def test_delete_prompt_message_exception(jira_prompt_handler, mock_posting_handler):
    """Test deleting prompt message exception handling."""
    jira_prompt_handler.active_prompts["C123"] = "123.456"
    mock_posting_handler.delete_message.side_effect = Exception("Test error")

    result = await jira_prompt_handler._delete_prompt_message("C123")

    assert result is False


# ========== Check Recent Messages Tests ==========


@pytest.mark.asyncio
async def test_check_recent_messages_for_jira_found(jira_prompt_handler, mock_channel_msg_ops):
    """Test checking recent messages and finding JIRA ticket."""
    # Test: Synthetic JIRA ticket ID (TEST DATA - not real production ticket)
    mock_channel_msg_ops._make_api_request.return_value = {
        "messages": [
            {
                "ts": "123.456",
                "user": "U123456",
                "text": "@ketchup CPGNREQ-12345",
            },  # TEST_TICKET_ID
            {"ts": "123.457", "user": "U123456", "text": "Some other message"},
        ]
    }

    result = await jira_prompt_handler._check_recent_messages_for_jira("C123", "111.222")

    assert result == "CPGNREQ-12345"
    mock_channel_msg_ops._make_api_request.assert_called_once()


@pytest.mark.asyncio
async def test_check_recent_messages_no_mentions(jira_prompt_handler, mock_channel_msg_ops):
    """Test checking messages with no @ketchup mentions."""
    mock_channel_msg_ops._make_api_request.return_value = {
        "messages": [
            {"ts": "123.456", "user": "U123456", "text": "Some message"},
            {"ts": "123.457", "user": "U123456", "text": "Another message"},
        ]
    }

    result = await jira_prompt_handler._check_recent_messages_for_jira("C123", "111.222")

    assert result is None


@pytest.mark.asyncio
async def test_check_recent_messages_exception(jira_prompt_handler, mock_channel_msg_ops):
    """Test exception handling in check_recent_messages."""
    mock_channel_msg_ops._make_api_request.side_effect = Exception("Test error")

    result = await jira_prompt_handler._check_recent_messages_for_jira("C123", "111.222")

    assert result is None


# ========== Wait for JIRA Reply Tests ==========


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_jira_reply_found(mock_sleep, jira_prompt_handler):
    """Test waiting for JIRA reply and finding it."""
    # Mock DynamoDB methods to simulate app_mention event storing a reply
    with (
        patch.object(
            jira_prompt_handler.db_store, "put_maintenance_prompt", new_callable=AsyncMock
        ),
        patch.object(
            jira_prompt_handler.db_store, "get_maintenance_prompt", new_callable=AsyncMock
        ) as mock_get_prompt,
        patch.object(
            jira_prompt_handler.db_store, "delete_maintenance_prompt", new_callable=AsyncMock
        ),
    ):
        # Setup: Simulate app_mention event stored a JIRA reply
        mock_get_prompt.return_value = {"jira_ticket": "CPGNREQ-12345"}

        result = await jira_prompt_handler._wait_for_jira_reply("C123", 5, "111.222")

        assert result == "CPGNREQ-12345"


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_wait_for_jira_reply_timeout(mock_sleep, jira_prompt_handler):
    """Test waiting for JIRA reply timeout."""
    # Mock DynamoDB methods to simulate no reply received
    with (
        patch.object(
            jira_prompt_handler.db_store, "put_maintenance_prompt", new_callable=AsyncMock
        ),
        patch.object(
            jira_prompt_handler.db_store, "get_maintenance_prompt", new_callable=AsyncMock
        ) as mock_get_prompt,
    ):
        # Setup: Simulate no reply from app_mention event
        mock_get_prompt.return_value = None

        # Use a very short timeout for faster testing
        result = await jira_prompt_handler._wait_for_jira_reply("C123", 5, "111.222")

        assert result is None


# ========== Fetch JIRA Ticket Tests ==========


@pytest.mark.asyncio
async def test_fetch_jira_ticket_success(jira_prompt_handler, mock_mcp_client):
    """Test fetching JIRA ticket successfully."""
    # Test: Mock JIRA response with synthetic ticket (TEST DATA - not real production ticket)
    mock_mcp_client.search_issues.return_value = {
        "issues": [
            {
                "key": "CPGNREQ-12345",  # SYNTHETIC_TEST_TICKET_ID
                "fields": {"customfield_22302": "https://test.com"},
            }
        ]
    }

    result = await jira_prompt_handler._fetch_jira_ticket("CPGNREQ-12345")

    assert result is not None
    assert result["key"] == "CPGNREQ-12345"
    mock_mcp_client.search_issues.assert_called_once_with(
        jql='key = "CPGNREQ-12345"',  # SYNTHETIC_TEST_TICKET_ID in JQL query
        fields=["summary", "status", "customfield_22302"],
    )


@pytest.mark.asyncio
async def test_fetch_jira_ticket_not_found(jira_prompt_handler, mock_mcp_client):
    """Test fetching JIRA ticket when not found."""
    mock_mcp_client.search_issues.return_value = {"issues": []}

    result = await jira_prompt_handler._fetch_jira_ticket("CPGNREQ-12345")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_jira_ticket_exception(jira_prompt_handler, mock_mcp_client):
    """Test fetching JIRA ticket exception handling."""
    mock_mcp_client.search_issues.side_effect = Exception("Test error")

    result = await jira_prompt_handler._fetch_jira_ticket("CPGNREQ-12345")

    assert result is None


# ========== Post Maintenance Found Message Tests ==========


@pytest.mark.asyncio
async def test_post_maintenance_found_message(
    jira_prompt_handler, mock_posting_handler, mock_maintenance_checker, mock_db_store
):
    """Test posting maintenance found message."""
    mock_posting_handler.post_message.return_value = {"ok": True, "ts": "123.456"}
    maintenance_info = {
        "customer_name": "Test Customer",
        "instance_name": "test_mkt_prod1",
        "starts_at": "2025-10-06T04:30:00Z",
    }

    await jira_prompt_handler._post_maintenance_found_message(
        "C123", maintenance_info, "CPGNREQ-12345"
    )

    mock_posting_handler.post_message.assert_called_once()
    mock_posting_handler.pin_message.assert_called_once_with(
        channel_id="C123", message_ts="123.456"
    )
    mock_db_store.channel_ops.update_channel_metadata.assert_called_once_with(
        channel_id="C123", customer_name="Test Customer", jira_ticket="CPGNREQ-12345"
    )


@pytest.mark.asyncio
async def test_post_maintenance_found_message_post_failure(
    jira_prompt_handler, mock_posting_handler
):
    """Test posting maintenance found message when post fails."""
    mock_posting_handler.post_message.return_value = {"ok": False}
    maintenance_info = {
        "customer_name": "Test Customer",
        "instance_name": "test_mkt_prod1",
        "starts_at": "2025-10-06T04:30:00Z",
    }

    await jira_prompt_handler._post_maintenance_found_message(
        "C123", maintenance_info, "CPGNREQ-12345"
    )

    mock_posting_handler.pin_message.assert_not_called()


# ========== Post No Maintenance Message Tests ==========


@pytest.mark.asyncio
async def test_post_no_maintenance_message(
    jira_prompt_handler, mock_posting_handler, mock_maintenance_checker
):
    """Test posting no maintenance message."""
    await jira_prompt_handler._post_no_maintenance_message(
        "C123", "test_mkt_prod1", "CPGNREQ-12345"
    )

    mock_posting_handler.post_message.assert_called_once()
    call_args = mock_posting_handler.post_message.call_args
    assert "No scheduled maintenance found" in call_args.kwargs["message"]


@pytest.mark.asyncio
async def test_post_no_maintenance_message_exception(jira_prompt_handler, mock_posting_handler):
    """Test posting no maintenance message exception handling."""
    mock_posting_handler.post_message.side_effect = Exception("Test error")

    await jira_prompt_handler._post_no_maintenance_message(
        "C123", "test_mkt_prod1", "CPGNREQ-12345"
    )

    # Should not raise exception


# ========== Post Timeout Message Tests ==========


@pytest.mark.asyncio
async def test_post_timeout_message(jira_prompt_handler, mock_posting_handler):
    """Test posting timeout message."""
    await jira_prompt_handler._post_timeout_message("C123")

    mock_posting_handler.post_message.assert_called_once()
    call_args = mock_posting_handler.post_message.call_args
    assert "Unable to determine maintenance status" in call_args.kwargs["message"]


# ========== Process Maintenance Check Tests ==========


@pytest.mark.asyncio
async def test_process_maintenance_check_found(
    jira_prompt_handler, mock_mcp_client, mock_maintenance_checker
):
    """Test processing maintenance check when maintenance is found."""
    mock_mcp_client.search_issues.return_value = {
        "issues": [{"fields": {"customfield_22302": "https://test-mkt-prod1.campaign.adobe.com"}}]
    }
    mock_maintenance_checker.check_maintenance.return_value = {
        "customer_name": "Test Customer",
        "instance_name": "test_mkt_prod1",
        "starts_at": "2025-10-06T04:30:00Z",
    }

    with patch.object(
        jira_prompt_handler, "_post_maintenance_found_message", new_callable=AsyncMock
    ) as mock_post_found:
        await jira_prompt_handler._process_maintenance_check("C123", "CPGNREQ-12345")

        mock_post_found.assert_called_once()


@pytest.mark.asyncio
async def test_process_maintenance_check_not_found(
    jira_prompt_handler, mock_mcp_client, mock_maintenance_checker
):
    """Test processing maintenance check when no maintenance found."""
    mock_mcp_client.search_issues.return_value = {
        "issues": [{"fields": {"customfield_22302": "https://test-mkt-prod1.campaign.adobe.com"}}]
    }
    mock_maintenance_checker.check_maintenance.return_value = None

    with patch.object(
        jira_prompt_handler, "_post_no_maintenance_message", new_callable=AsyncMock
    ) as mock_post_no:
        await jira_prompt_handler._process_maintenance_check("C123", "CPGNREQ-12345")

        mock_post_no.assert_called_once()


@pytest.mark.asyncio
async def test_process_maintenance_check_no_instance_url(jira_prompt_handler, mock_mcp_client):
    """Test processing maintenance check with missing instance URL."""
    mock_mcp_client.search_issues.return_value = {"issues": [{"fields": {}}]}

    with patch.object(
        jira_prompt_handler, "_post_timeout_message", new_callable=AsyncMock
    ) as mock_timeout:
        await jira_prompt_handler._process_maintenance_check("C123", "CPGNREQ-12345")

        mock_timeout.assert_called_once_with("C123")


@pytest.mark.asyncio
async def test_process_maintenance_check_jira_fetch_failure(jira_prompt_handler, mock_mcp_client):
    """Test processing maintenance check when JIRA fetch fails."""
    mock_mcp_client.search_issues.return_value = None

    with patch.object(
        jira_prompt_handler, "_post_timeout_message", new_callable=AsyncMock
    ) as mock_timeout:
        await jira_prompt_handler._process_maintenance_check("C123", "CPGNREQ-12345")

        mock_timeout.assert_called_once_with("C123")


# ========== Workflow Tests ==========


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_workflow_success_first_attempt(
    mock_sleep, jira_prompt_handler, mock_posting_handler
):
    """Test workflow succeeding on first attempt."""
    mock_posting_handler.post_message.return_value = {"ok": True, "ts": "123.456"}

    with patch.object(
        jira_prompt_handler, "_wait_for_jira_reply", new_callable=AsyncMock
    ) as mock_wait:
        mock_wait.return_value = "CPGNREQ-12345"

        with patch.object(
            jira_prompt_handler, "_process_maintenance_check", new_callable=AsyncMock
        ) as mock_process:
            await jira_prompt_handler.start_jira_prompt_workflow("C123")

            assert mock_wait.call_count == 1
            mock_process.assert_called_once_with("C123", "CPGNREQ-12345")


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_workflow_timeout_all_attempts(mock_sleep, jira_prompt_handler, mock_posting_handler):
    """Test workflow timeout after all attempts."""
    mock_posting_handler.post_message.return_value = {"ok": True, "ts": "123.456"}

    with patch.object(
        jira_prompt_handler, "_wait_for_jira_reply", new_callable=AsyncMock
    ) as mock_wait:
        mock_wait.return_value = None

        with patch.object(
            jira_prompt_handler, "_post_timeout_message", new_callable=AsyncMock
        ) as mock_timeout:
            await jira_prompt_handler.start_jira_prompt_workflow("C123")

            assert mock_wait.call_count == 3
            mock_timeout.assert_called_once_with("C123")
