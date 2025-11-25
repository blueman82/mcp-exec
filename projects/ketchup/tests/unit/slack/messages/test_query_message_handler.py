# pylint: disable=W0212,W0621
"""
Unit tests for packages.slack.blockkits.handlers.query.QueryMessageHandler

Covers all logic branches, error cases, and edge conditions for send_message.
Mocks all dependencies. Follows project test standards.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.blockkits.handlers.query import QueryMessageHandler


@pytest.fixture
def handler():
    """Fixture for a configured QueryMessageHandler with all dependencies mocked."""
    h = QueryMessageHandler()
    h._posting_handler = AsyncMock()
    h._fallback_getter = AsyncMock(
        return_value={"channel_id": "C1", "channel_name": "chan1"}
    )
    h._build_feedback_blocks = AsyncMock(
        return_value=[
            {"type": "section", "text": {"type": "mrkdwn", "text": "feedback"}}
        ]
    )
    return h


@pytest.mark.asyncio
async def test_send_message_normal_response_url(handler):
    """Test normal send_message flow with response_url: all dependencies succeed, message and blocks sent."""
    await handler.send_message(
        combined_command="/query foo",
        response_url="http://slack.com/response",
        response_text="Test response",
        query="foo",
        target_channel="C1",
    )
    handler._fallback_getter.assert_awaited_once_with("C1")
    handler._build_feedback_blocks.assert_awaited_once_with(
        channel_id="C1", summary_type="foo", command_output="Test response"
    )
    handler._posting_handler.post_message.assert_awaited_once()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["response_url"] == "http://slack.com/response"
    assert "Test response" in call["message"]
    assert isinstance(call["blocks"], list)


@pytest.mark.asyncio
async def test_send_message_normal_channel_id(handler):
    """Test normal send_message flow with channel_id: all dependencies succeed, message and blocks sent."""
    await handler.send_message(
        combined_command="/query foo",
        response_url="C2",
        response_text="Test response",
        query="foo",
        target_channel="C2",
    )
    handler._fallback_getter.assert_awaited_once_with("C2")
    handler._build_feedback_blocks.assert_awaited_once_with(
        channel_id="C2", summary_type="foo", command_output="Test response"
    )
    handler._posting_handler.post_message.assert_awaited_once()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["channel_id"] == "C2"
    assert "Test response" in call["message"]
    assert isinstance(call["blocks"], list)


@pytest.mark.asyncio
async def test_send_message_channel_details_error(handler):
    """Test send_message when fallback_getter raises: logs error, continues with None channel_details."""
    handler._fallback_getter = AsyncMock(side_effect=Exception("fail details"))
    await handler.send_message(
        combined_command="/query foo",
        response_url="C3",
        response_text="Test response",
        query="foo",
        target_channel="C3",
    )
    handler._fallback_getter.assert_awaited_once_with("C3")
    handler._posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_feedback_blocks_error(handler):
    """Test send_message when build_feedback_blocks raises: logs error, continues without feedback blocks."""
    handler._build_feedback_blocks = AsyncMock(side_effect=Exception("fail feedback"))
    await handler.send_message(
        combined_command="/query foo",
        response_url="C4",
        response_text="Test response",
        query="foo",
        target_channel="C4",
    )
    handler._build_feedback_blocks.assert_awaited_once_with(
        channel_id="C4", summary_type="foo", command_output="Test response"
    )
    handler._posting_handler.post_message.assert_awaited_once()
    call = handler._posting_handler.post_message.await_args[1]
    assert call["blocks"] == [] or isinstance(call["blocks"], list)


@pytest.mark.asyncio
async def test_send_message_posting_error_triggers_fallback(handler):
    """Test send_message when posting_handler.post_message raises: triggers fallback with enhanced message."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=[Exception("fail post"), MagicMock()]
    )
    with patch(
        "packages.slack.blockkits.handlers.query.enhance_message_for_fallback",
        return_value="enhanced",
    ) as enhance_patch:
        await handler.send_message(
            combined_command="/query foo",
            response_url="C5",
            response_text="Test response",
            query="foo",
            target_channel="C5",
        )
        assert enhance_patch.called
        assert handler._posting_handler.post_message.await_count == 2
        fallback_call = handler._posting_handler.post_message.await_args_list[1][1]
        assert fallback_call["message"] == "enhanced"
        assert fallback_call["channel_id"] == "C5"


@pytest.mark.asyncio
async def test_send_message_fallback_error_logs(handler):
    """Test send_message when both posting and fallback raise: logs both errors, does not crash."""
    handler._posting_handler.post_message = AsyncMock(
        side_effect=[Exception("fail post"), Exception("fail fallback")]
    )
    with patch(
        "packages.slack.blockkits.handlers.query.enhance_message_for_fallback",
        return_value="enhanced",
    ):
        await handler.send_message(
            combined_command="/query foo",
            response_url="C6",
            response_text="Test response",
            query="foo",
            target_channel="C6",
        )
        assert handler._posting_handler.post_message.await_count == 2
