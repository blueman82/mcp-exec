"""
Unit test to replicate the empty content bug in query command.

Issue: OpenAI returns 1024 output tokens but response_data["choices"][0]["message"]["content"] is empty.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_openai_response_with_empty_content():
    """Mock OpenAI response with 1024 tokens but empty content field."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4",
        "usage": {
            "prompt_tokens": 29850,
            "completion_tokens": 1024,  # 1024 tokens returned!
            "total_tokens": 30874,
        },
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",  # BUT CONTENT IS EMPTY!
                },
                "finish_reason": "stop",
                "index": 0,
            }
        ],
    }


@pytest.fixture
def mock_openai_response_with_json_in_content():
    """Mock OpenAI response with JSON content when response_format is json_object."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4",
        "usage": {
            "prompt_tokens": 29850,
            "completion_tokens": 1024,
            "total_tokens": 30874,
        },
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"response_text": "This is the actual response from the AI with 1024 tokens"}',
                },
                "finish_reason": "stop",
                "index": 0,
            }
        ],
    }


@pytest.mark.asyncio
@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
async def test_query_command_with_empty_content_field(
    mock_openai_response_with_empty_content,
):
    """Test that query command fails when content field is empty despite 1024 tokens."""
    from packages.slack.command_processing.query_command import SlackQueryHandler

    # Create mock dependencies
    mock_openai_handler = AsyncMock()
    mock_openai_handler.call_openai_endpoint.return_value = mock_openai_response_with_empty_content

    # Mock the channel_info_ops to return valid channel details
    mock_channel_info_ops = AsyncMock()
    mock_channel_info_ops.get_channel_details.return_value = ("test", True, False, False)

    # Mock the user_store to return empty user data
    mock_user_store = AsyncMock()
    mock_user_store.get_user.return_value = None

    # Mock the posting handler to do nothing
    mock_posting_handler = AsyncMock()
    mock_posting_handler.post_message = AsyncMock()

    # Create handler with all required dependencies
    handler = SlackQueryHandler(
        channel_info_ops=mock_channel_info_ops,
        archive_ops=MagicMock(),
        openai_handler=mock_openai_handler,
        block_kit_builder=MagicMock(),
        channel_message_ops=MagicMock(),
        slack_posting_handler=mock_posting_handler,
        user_store=mock_user_store,
        slack_config=MagicMock(),
        secrets_manager=MagicMock(),
        user_ops=MagicMock(),
    )

    # This should replicate the bug:
    # - OpenAI returns 1024 tokens
    # - But content field is empty ""
    # - orjson.loads("") will fail with "input data is empty"

    # Execute query using _process_query (the actual method that exists)
    result = await handler._process_query(
        channel_id="C123",
        query_text="test query",
        user_id="U123",
        messaging_channel="C123",
        response_url=None,
        user_name="testuser",
    )

    # The result should be empty string (the fallback when JSON parsing fails)
    assert result == ""  # This is the bug!


@pytest.mark.asyncio
@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
async def test_query_command_with_valid_json_content(
    mock_openai_response_with_json_in_content,
):
    """Test that query command works when content has valid JSON."""
    from packages.slack.command_processing.query_command import SlackQueryHandler

    # Create mock dependencies
    mock_openai_handler = AsyncMock()
    mock_openai_handler.call_openai_endpoint.return_value = (
        mock_openai_response_with_json_in_content
    )

    # Mock the channel_info_ops to return valid channel details
    mock_channel_info_ops = AsyncMock()
    mock_channel_info_ops.get_channel_details.return_value = ("test", True, False, False)

    # Mock the user_store to return empty user data
    mock_user_store = AsyncMock()
    mock_user_store.get_user.return_value = None

    # Mock the posting handler to do nothing
    mock_posting_handler = AsyncMock()
    mock_posting_handler.post_message = AsyncMock()

    # Create handler with all required dependencies
    handler = SlackQueryHandler(
        channel_info_ops=mock_channel_info_ops,
        archive_ops=MagicMock(),
        openai_handler=mock_openai_handler,
        block_kit_builder=MagicMock(),
        channel_message_ops=MagicMock(),
        slack_posting_handler=mock_posting_handler,
        user_store=mock_user_store,
        slack_config=MagicMock(),
        secrets_manager=MagicMock(),
        user_ops=MagicMock(),
    )

    # Execute query using _process_query (the actual method that exists)
    result = await handler._process_query(
        channel_id="C123",
        query_text="test query",
        user_id="U123",
        messaging_channel="C123",
        response_url=None,
        user_name="testuser",
    )

    # Should extract the response_text from JSON
    assert result == "This is the actual response from the AI with 1024 tokens"
