"""
Unit tests for openai_handler.py JSON extraction functionality.

Tests the execute_prompt() and process_with_context() methods
when KETCHUP_STRUCTURED_JSON_OUTPUT feature flag is enabled.
"""

import json
import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from packages.ai.core.openai_handler import OpenAIHandler


@pytest.fixture
def mock_dependencies() -> Dict[str, Any]:
    """Create mock dependencies for OpenAIHandler."""
    return {
        "token_tracker": MagicMock(),
        "secrets_manager": MagicMock(),
        "channel_info_ops": MagicMock(),
        "channel_msg_ops": MagicMock(),
        "channel_ops": MagicMock(),
        "jira_extractor": None,
    }


@pytest.fixture
def openai_handler(mock_dependencies: Dict[str, Any]) -> OpenAIHandler:
    """Create OpenAIHandler instance with mocked dependencies."""
    return OpenAIHandler(**mock_dependencies)


@pytest.mark.asyncio
@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
async def test_execute_prompt_with_json_mode_enabled(
    openai_handler: OpenAIHandler,
) -> None:
    """Test execute_prompt extracts text from JSON when flag is enabled."""
    # Mock the call_openai_endpoint to return JSON response
    json_response = {"response_text": "This is the extracted text from JSON"}
    mock_response = {
        "choices": [{"message": {"content": json.dumps(json_response)}}]
    }

    with patch.object(
        openai_handler, "call_openai_endpoint", return_value=mock_response
    ):
        result = await openai_handler.execute_prompt(
            messages=[{"role": "user", "content": "test"}]
        )

    assert result == "This is the extracted text from JSON"


@pytest.mark.asyncio
@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "false"})
async def test_execute_prompt_with_json_mode_disabled(
    openai_handler: OpenAIHandler,
) -> None:
    """Test execute_prompt returns raw content when flag is disabled."""
    # Mock the call_openai_endpoint to return prose response
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "This is raw prose text without JSON structure"
                }
            }
        ]
    }

    with patch.object(
        openai_handler, "call_openai_endpoint", return_value=mock_response
    ):
        result = await openai_handler.execute_prompt(
            messages=[{"role": "user", "content": "test"}]
        )

    assert result == "This is raw prose text without JSON structure"


@pytest.mark.asyncio
@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
async def test_execute_prompt_fallback_on_invalid_json(
    openai_handler: OpenAIHandler,
) -> None:
    """Test execute_prompt falls back to raw content on JSON parse error."""
    # Mock the call_openai_endpoint to return invalid JSON
    invalid_json = "This is not valid JSON {response_text:"
    mock_response = {"choices": [{"message": {"content": invalid_json}}]}

    with patch.object(
        openai_handler, "call_openai_endpoint", return_value=mock_response
    ):
        result = await openai_handler.execute_prompt(
            messages=[{"role": "user", "content": "test"}]
        )

    # Should fallback to raw content
    assert result == invalid_json


@pytest.mark.asyncio
@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
async def test_process_with_context_with_json_mode_enabled(
    openai_handler: OpenAIHandler,
) -> None:
    """Test process_with_context extracts text from JSON when flag is enabled."""
    # Mock the call_openai_endpoint to return JSON response
    json_response = {
        "response_text": "Contextual response extracted from JSON"
    }
    mock_response = {
        "choices": [{"message": {"content": json.dumps(json_response)}}]
    }

    with patch.object(
        openai_handler, "call_openai_endpoint", return_value=mock_response
    ):
        result = await openai_handler.process_with_context(
            messages=[{"role": "user", "content": "test"}],
            conversation_history=[],
        )

    assert result == "Contextual response extracted from JSON"


@pytest.mark.asyncio
@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "false"})
async def test_process_with_context_with_json_mode_disabled(
    openai_handler: OpenAIHandler,
) -> None:
    """Test process_with_context returns raw content when flag is disabled."""
    # Mock the call_openai_endpoint to return prose response
    mock_response = {
        "choices": [
            {"message": {"content": "Raw contextual prose response"}}
        ]
    }

    with patch.object(
        openai_handler, "call_openai_endpoint", return_value=mock_response
    ):
        result = await openai_handler.process_with_context(
            messages=[{"role": "user", "content": "test"}],
            conversation_history=[],
        )

    assert result == "Raw contextual prose response"


@pytest.mark.asyncio
@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
async def test_process_with_context_fallback_on_invalid_json(
    openai_handler: OpenAIHandler,
) -> None:
    """Test process_with_context falls back to raw content on JSON parse error."""
    # Mock the call_openai_endpoint to return invalid JSON
    invalid_json = "{broken json structure"
    mock_response = {"choices": [{"message": {"content": invalid_json}}]}

    with patch.object(
        openai_handler, "call_openai_endpoint", return_value=mock_response
    ):
        result = await openai_handler.process_with_context(
            messages=[{"role": "user", "content": "test"}],
            conversation_history=[],
        )

    # Should fallback to raw content
    assert result == invalid_json


@pytest.mark.asyncio
@patch.dict(os.environ, {"KETCHUP_STRUCTURED_JSON_OUTPUT": "true"})
async def test_execute_prompt_with_missing_response_text_field(
    openai_handler: OpenAIHandler,
) -> None:
    """Test execute_prompt handles missing response_text field gracefully."""
    # Mock response with valid JSON but missing response_text field
    json_response = {"other_field": "some value"}
    mock_response = {
        "choices": [{"message": {"content": json.dumps(json_response)}}]
    }

    with patch.object(
        openai_handler, "call_openai_endpoint", return_value=mock_response
    ):
        result = await openai_handler.execute_prompt(
            messages=[{"role": "user", "content": "test"}]
        )

    # Should fallback to raw JSON when response_text is missing
    assert result == json.dumps(json_response)
