# pylint: disable=W0212,W0621
"""
Unit tests for packages.slack.blockkits.handlers.archive.ArchiveMessageHandler

Covers all logic branches, error cases, and edge conditions for send_message.
Mocks all dependencies. Follows project test standards.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import InvalidBlocksForResponseUrlError
from packages.slack.blockkits.handlers.archive import ArchiveMessageHandler


@pytest.fixture
def handler():
    """Fixture for a configured ArchiveMessageHandler with all dependencies mocked."""
    h = ArchiveMessageHandler()
    h._posting_handler = AsyncMock()
    h._channel_details_getter = AsyncMock()
    return h


@pytest.mark.asyncio
async def test_send_message_normal_block_kit(handler):
    """Test normal send_message flow with block kit posting succeeds."""
    summaries = [
        {
            "channel_id": "C1",
            "channel_name": "chan1",
            "archived_at": 1234567890,
            "customer_name": "Cust1",
            "jira_ticket": "JIRA-1",
        }
    ]
    await handler.send_message(
        response_url="http://slack.com/response",
        summaries=summaries,
        incoming_channel="C1",
    )
    handler._posting_handler.post_message.assert_awaited_once()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["response_url"] == "http://slack.com/response"
    assert "Archived Channels" in call["message"]
    assert isinstance(call["blocks"], list)


@pytest.mark.asyncio
async def test_send_message_invalid_blocks_triggers_fallback_batches(handler):
    """Test send_message when InvalidBlocksForResponseUrlError is raised: triggers fallback batching."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=InvalidBlocksForResponseUrlError("invalid blocks")
    )
    summaries = [
        {
            "channel_id": f"C{i}",
            "channel_name": f"chan{i}",
            "archived_at": 1234567890 + i,
            "customer_name": f"Cust{i}",
            "jira_ticket": f"JIRA-{i}",
        }
        for i in range(3)
    ]
    await handler.send_message(
        response_url="http://slack.com/response",
        summaries=summaries,
        incoming_channel="C1",
    )
    # Fallback batches should be attempted
    assert handler._posting_handler.post_message.await_count >= 2


@pytest.mark.asyncio
async def test_send_message_invalid_blocks_no_response_url(handler):
    """Test send_message InvalidBlocksForResponseUrlError with no response_url (not http): logs error, no fallback."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=InvalidBlocksForResponseUrlError("invalid blocks")
    )
    summaries = [
        {
            "channel_id": "C1",
            "channel_name": "chan1",
            "archived_at": 1234567890,
            "customer_name": "Cust1",
            "jira_ticket": "JIRA-1",
        }
    ]
    await handler.send_message(
        response_url="C1",
        summaries=summaries,
        incoming_channel="C1",
    )
    # Only one attempt, no fallback
    assert handler._posting_handler.post_message.await_count == 1


@pytest.mark.asyncio
async def test_send_message_general_posting_error_triggers_text_fallback(handler):
    """Test send_message when general posting error occurs: triggers general text-only fallback."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=[Exception("fail post"), MagicMock()]
    )
    summaries = [
        {
            "channel_id": "C1",
            "channel_name": "chan1",
            "archived_at": 1234567890,
            "customer_name": "Cust1",
            "jira_ticket": "JIRA-1",
        }
    ]
    await handler.send_message(
        response_url="C1",
        summaries=summaries,
        incoming_channel="C1",
    )
    assert handler._posting_handler.post_message.await_count == 2
    fallback_call = handler._posting_handler.post_message.await_args_list[1][1]
    assert fallback_call["channel_id"] == "C1"
    assert "Archived Channels" in fallback_call["message"]


@pytest.mark.asyncio
async def test_send_message_general_posting_error_and_fallback_error_logs(handler):
    """Test send_message when both posting and fallback raise: logs both errors, does not crash."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=[Exception("fail post"), Exception("fail fallback")]
    )
    summaries = [
        {
            "channel_id": "C1",
            "channel_name": "chan1",
            "archived_at": 1234567890,
            "customer_name": "Cust1",
            "jira_ticket": "JIRA-1",
        }
    ]
    await handler.send_message(
        response_url="C1",
        summaries=summaries,
        incoming_channel="C1",
    )
    assert handler._posting_handler.post_message.await_count == 2
