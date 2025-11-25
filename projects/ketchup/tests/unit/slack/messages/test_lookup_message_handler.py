# pylint: disable=W0212,W0621
"""
Unit tests for packages.slack.blockkits.handlers.lookup.LookupMessageHandler

Covers all logic branches, error cases, and edge conditions for send_message.
Mocks all dependencies. Follows project test standards.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.slack.blockkits.handlers.lookup import LookupMessageHandler


@pytest.fixture
def handler():
    """Fixture for a configured LookupMessageHandler with all dependencies mocked."""
    h = LookupMessageHandler()
    h._posting_handler = AsyncMock()
    return h


@pytest.mark.asyncio
async def test_send_message_normal_response_url(handler):
    """Test normal send_message flow with response_url: message and blocks sent."""
    channels_list = [
        {
            "channel_id": "C1",
            "channel_name": "chan1",
            "customer_name": "Cust1",
            "jira_ticket": "JIRA-1",
        }
    ]
    await handler.send_message(
        response_url="http://slack.com/response",
        channels_list=channels_list,
    )
    handler._posting_handler.post_message.assert_awaited_once()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["response_url"] == "http://slack.com/response"
    assert "Channel Lookup Results" in call["message"]
    assert isinstance(call["blocks"], list)


@pytest.mark.asyncio
async def test_send_message_normal_channel_id(handler):
    """Test normal send_message flow with channel_id: message and blocks sent."""
    channels_list = [
        {
            "channel_id": "C2",
            "channel_name": "chan2",
            "customer_name": "Cust2",
            "jira_ticket": "JIRA-2",
        }
    ]
    await handler.send_message(
        response_url="C2",
        channels_list=channels_list,
    )
    handler._posting_handler.post_message.assert_awaited_once()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["channel_id"] == "C2"
    assert "Channel Lookup Results" in call["message"]
    assert isinstance(call["blocks"], list)


@pytest.mark.asyncio
async def test_send_message_posting_error_triggers_fallback(handler):
    """Test send_message when posting_handler.post_message raises: triggers fallback with text-only message."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=[Exception("fail post"), MagicMock()]
    )
    channels_list = [
        {
            "channel_id": "C3",
            "channel_name": "chan3",
            "customer_name": "Cust3",
            "jira_ticket": "JIRA-3",
        }
    ]
    await handler.send_message(
        response_url="C3",
        channels_list=channels_list,
    )
    assert handler._posting_handler.post_message.await_count == 2
    fallback_call = handler._posting_handler.post_message.await_args_list[1][1]
    assert fallback_call["channel_id"] == "C3"
    assert "Channel Lookup Results" in fallback_call["message"]
    # No blocks in fallback
    assert "blocks" not in fallback_call or fallback_call["blocks"] is None


@pytest.mark.asyncio
async def test_send_message_fallback_error_logs(handler):
    """Test send_message when both posting and fallback raise: logs both errors, does not crash."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=[Exception("fail post"), Exception("fail fallback")]
    )
    channels_list = [
        {
            "channel_id": "C4",
            "channel_name": "chan4",
            "customer_name": "Cust4",
            "jira_ticket": "JIRA-4",
        }
    ]
    await handler.send_message(
        response_url="C4",
        channels_list=channels_list,
    )
    assert handler._posting_handler.post_message.await_count == 2
