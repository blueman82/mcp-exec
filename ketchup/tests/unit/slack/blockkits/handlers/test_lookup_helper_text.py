"""
Test for lookup handler with helper text functionality.
"""

from unittest.mock import AsyncMock

import pytest

from packages.slack.blockkits.handlers.lookup import LookupMessageHandler


@pytest.mark.asyncio
async def test_lookup_handler_with_helper_text():
    """Test that helper text is included when requested."""
    # Setup
    handler = LookupMessageHandler()
    posting_handler = AsyncMock()
    channel_details_getter = AsyncMock()

    handler.configure(
        posting_handler=posting_handler, channel_details_getter=channel_details_getter
    )

    # Test data
    channels_list = [
        {
            "channel_id": "C123456",
            "channel_name": "test-channel",
            "customer_name": "TEST CUSTOMER",
            "jira_ticket": "TEST-123",
            "last_updated": "2024-01-01",
        }
    ]

    # Execute
    await handler.send_message(
        response_url="https://hooks.slack.com/response",
        channels_list=channels_list,
        include_helper_text=True,
    )

    # Verify
    posting_handler.post_message.assert_called_once()
    call_args = posting_handler.post_message.call_args

    # Check that blocks were passed
    assert "blocks" in call_args.kwargs
    blocks = call_args.kwargs["blocks"]

    # Find the helper text block
    helper_block = None
    for block in blocks:
        if block.get("type") == "section" and "text" in block:
            text = block["text"].get("text", "")
            if "/ketchup status" in text:
                helper_block = block
                break

    assert helper_block is not None, "Helper text block not found"
    assert "/ketchup status <Channel ID>" in helper_block["text"]["text"]
    assert "/ketchup query <Channel ID> <question>" in helper_block["text"]["text"]
    assert "/ketchup report <Channel ID>" in helper_block["text"]["text"]


@pytest.mark.asyncio
async def test_lookup_handler_without_helper_text():
    """Test that helper text is not included when not requested."""
    # Setup
    handler = LookupMessageHandler()
    posting_handler = AsyncMock()
    channel_details_getter = AsyncMock()

    handler.configure(
        posting_handler=posting_handler, channel_details_getter=channel_details_getter
    )

    # Test data
    channels_list = [
        {
            "channel_id": "C123456",
            "channel_name": "test-channel",
            "customer_name": "TEST CUSTOMER",
            "jira_ticket": "TEST-123",
            "last_updated": "2024-01-01",
        }
    ]

    # Execute
    await handler.send_message(
        response_url="https://hooks.slack.com/response",
        channels_list=channels_list,
        include_helper_text=False,
    )

    # Verify
    posting_handler.post_message.assert_called_once()
    call_args = posting_handler.post_message.call_args

    # Check that blocks were passed
    assert "blocks" in call_args.kwargs
    blocks = call_args.kwargs["blocks"]

    # Verify no helper text block exists
    for block in blocks:
        if block.get("type") == "section" and "text" in block:
            text = block["text"].get("text", "")
            assert "/ketchup status" not in text


@pytest.mark.asyncio
async def test_lookup_handler_empty_list_no_helper_text():
    """Test that helper text is not included for empty channel lists."""
    # Setup
    handler = LookupMessageHandler()
    posting_handler = AsyncMock()
    channel_details_getter = AsyncMock()

    handler.configure(
        posting_handler=posting_handler, channel_details_getter=channel_details_getter
    )

    # Execute with empty list
    await handler.send_message(
        response_url="https://hooks.slack.com/response",
        channels_list=[],
        include_helper_text=True,
    )

    # Verify
    posting_handler.post_message.assert_called_once()
    call_args = posting_handler.post_message.call_args

    # Check that blocks were passed
    assert "blocks" in call_args.kwargs
    blocks = call_args.kwargs["blocks"]

    # Verify no helper text block exists (because list is empty)
    for block in blocks:
        if block.get("type") == "section" and "text" in block:
            text = block["text"].get("text", "")
            assert "/ketchup status" not in text
