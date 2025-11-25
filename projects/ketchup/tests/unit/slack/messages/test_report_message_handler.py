# pylint: disable=W0212,W0621
"""
Unit tests for packages.slack.blockkits.handlers.report.ReportMessageHandler

Covers all logic branches, error cases, and edge conditions for send_message.
Mocks all dependencies. Follows project test standards.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.slack.blockkits.handlers.report import ReportMessageHandler


@pytest.fixture
def handler():
    """Fixture for a configured ReportMessageHandler with all dependencies mocked."""
    h = ReportMessageHandler()
    h._posting_handler = AsyncMock()
    h._fallback_getter = AsyncMock(
        return_value={
            "channel_id": "C1",
            "channel_name": "chan1",
            "customer_name": "Cust1",
            "jira_ticket": "JIRA-1",
        }
    )
    h._build_feedback_blocks = AsyncMock(
        return_value=[
            {"type": "section", "text": {"type": "plain_text", "text": "Feedback"}}
        ]
    )
    return h


@pytest.mark.asyncio
async def test_send_message_normal_with_feedback(handler):
    """Test normal send_message flow with feedback blocks present."""
    await handler.send_message(
        combined_command="/report foo",
        response_url="http://slack.com/response",
        response_text="Report content",
        query="foo",
        target_channel="C1",
    )
    handler._posting_handler.post_message.assert_awaited()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["response_url"] == "http://slack.com/response"
    assert "Report content" in call["message"]
    assert isinstance(call["blocks"], list)
    assert any(b.get("type") == "section" for b in call["blocks"])


@pytest.mark.asyncio
async def test_send_message_normal_no_feedback(handler):
    """Test normal send_message flow with no feedback blocks (build_feedback_blocks is None)."""
    handler._build_feedback_blocks = None
    await handler.send_message(
        combined_command="/report foo",
        response_url="C1",
        response_text="Report content",
        query="foo",
        target_channel="C1",
    )
    handler._posting_handler.post_message.assert_awaited()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["channel_id"] == "C1"
    assert "Report content" in call["message"]
    assert isinstance(call["blocks"], list)


@pytest.mark.asyncio
async def test_send_message_channel_details_error(handler):
    """Test send_message when fallback_getter raises: logs error, continues with None channel_details."""
    handler._fallback_getter = AsyncMock(side_effect=Exception("fail details"))
    await handler.send_message(
        combined_command="/report foo",
        response_url="C1",
        response_text="Report content",
        query="foo",
        target_channel="C1",
    )
    handler._posting_handler.post_message.assert_awaited()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["channel_id"] == "C1"
    assert "Report content" in call["message"]


@pytest.mark.asyncio
async def test_send_message_feedback_block_error(handler):
    """Test send_message when build_feedback_blocks raises: logs error, continues."""
    handler._build_feedback_blocks = AsyncMock(side_effect=Exception("fail feedback"))
    await handler.send_message(
        combined_command="/report foo",
        response_url="C1",
        response_text="Report content",
        query="foo",
        target_channel="C1",
    )
    handler._posting_handler.post_message.assert_awaited()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["channel_id"] == "C1"
    assert "Report content" in call["message"]


@pytest.mark.asyncio
async def test_send_message_posting_error_triggers_fallback(handler):
    """Test send_message when posting_handler.post_message raises: triggers fallback with text-only message."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=[Exception("fail post"), MagicMock()]
    )
    await handler.send_message(
        combined_command="/report foo",
        response_url="C1",
        response_text="Report content",
        query="foo",
        target_channel="C1",
    )
    assert handler._posting_handler.post_message.await_count == 2
    fallback_call = handler._posting_handler.post_message.await_args_list[1][1]
    assert fallback_call["channel_id"] == "C1"
    assert "Report content" in fallback_call["message"]
    # No blocks in fallback
    assert "blocks" not in fallback_call or fallback_call["blocks"] is None


@pytest.mark.asyncio
async def test_send_message_fallback_error_logs(handler):
    """Test send_message when both posting and fallback raise: logs both errors, does not crash."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=[Exception("fail post"), Exception("fail fallback")]
    )
    await handler.send_message(
        combined_command="/report foo",
        response_url="C1",
        response_text="Report content",
        query="foo",
        target_channel="C1",
    )
    assert handler._posting_handler.post_message.await_count == 2
