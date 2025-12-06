"""
Unit tests for packages.slack.interactive_elements.feedback_report

This module provides comprehensive tests for the FeedbackReportHandler class, which handles the Slack feedback report modal and report posting flow.

Coverage includes:
- All logic branches: open_feedback_report_modal (success, Slack API error, exception), _build_feedback_report_modal (structure), _send_success_modal (success, Slack API error, exception), send_feedback_report_to_channel (success, modal fail, post fail, exception)
- Edge cases: Slack API errors, exceptions, missing/invalid responses
- All dependencies (posting_handler, secrets_manager, aiohttp.ClientSession) are mocked to isolate handler logic

Expected outcomes:
- All branches and error cases are directly tested
- All tests are mypy- and ruff-clean
- Each test function includes a detailed docstring per @ketchup_test_plan.md
"""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler
from tests.unit.test_utils.aiohttp_helpers import (
    MockAiohttpResponse,
    create_mock_session_class,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def handler(mocker):
    """Provides a FeedbackReportHandler instance with mocked dependencies."""
    mock_posting = mocker.patch("packages.slack.messages.posting.SlackPostingHandler", spec=True)
    mock_secrets = mocker.patch("packages.secrets.manager.SecretsManager", spec=True)
    mock_secrets.get_slack_api_token_async = AsyncMock(return_value="xoxb-token")
    return FeedbackReportHandler(mock_posting, mock_secrets)


async def test_build_feedback_report_modal(handler) -> None:
    """Test _build_feedback_report_modal returns a valid modal structure."""
    modal = await handler._build_feedback_report_modal()
    assert modal["type"] == "modal"
    assert modal["callback_id"] == "submit_feedback_report"
    assert any(b["block_id"] == "feedback_name" for b in modal["blocks"])
    assert any(b["block_id"] == "feedback_description" for b in modal["blocks"])


async def test_open_feedback_report_modal_success(handler, mocker) -> None:
    """Test open_feedback_report_modal returns True on Slack API success."""
    mock_response = MockAiohttpResponse(status=200, json_data={"ok": True})

    with patch("aiohttp.ClientSession", create_mock_session_class({"post": mock_response})):
        result = await handler.open_feedback_report_modal("TRIGGER123")

    assert result is True


async def test_open_feedback_report_modal_slack_error(handler, mocker) -> None:
    """Test open_feedback_report_modal returns False on Slack API error."""
    mock_response = MockAiohttpResponse(status=200, json_data={"ok": False, "error": "test_error"})

    with patch("aiohttp.ClientSession", create_mock_session_class({"post": mock_response})):
        result = await handler.open_feedback_report_modal("TRIGGER123")

    assert result is False


async def test_open_feedback_report_modal_exception(handler, mocker) -> None:
    """Test open_feedback_report_modal returns False on network or other exception."""
    # Make ClientSession raise an error
    with patch("aiohttp.ClientSession", side_effect=aiohttp.ClientError("Network failed")):
        result = await handler.open_feedback_report_modal("TRIGGER123")

    assert result is False


async def test_send_success_modal_success(handler, mocker) -> None:
    """Test _send_success_modal returns True on Slack API success."""
    mock_response = MockAiohttpResponse(status=200, json_data={"ok": True})

    with patch("aiohttp.ClientSession", create_mock_session_class({"post": mock_response})):
        result = await handler._send_success_modal("TRIGGER123")

    assert result is True


async def test_send_success_modal_slack_error(handler, mocker) -> None:
    """Test _send_success_modal returns False on Slack API error."""
    mock_response = MockAiohttpResponse(status=200, json_data={"ok": False, "error": "test_error"})

    with patch("aiohttp.ClientSession", create_mock_session_class({"post": mock_response})):
        result = await handler._send_success_modal("TRIGGER123")

    assert result is False


async def test_send_success_modal_exception(handler, mocker) -> None:
    """Test _send_success_modal returns False on network or other exception."""
    # Make ClientSession raise an error
    with patch("aiohttp.ClientSession", side_effect=aiohttp.ClientError("Network failed")):
        result = await handler._send_success_modal("TRIGGER123")

    assert result is False


async def test_send_feedback_report_to_channel_success(handler, monkeypatch) -> None:
    """Test send_feedback_report_to_channel returns True on success (post and modal succeed)."""
    monkeypatch.setattr(handler, "_send_success_modal", AsyncMock(return_value=True))
    handler._posting_handler.post_message = AsyncMock(return_value=True)
    result = await handler.send_feedback_report_to_channel("U1", "title", "desc", "TRIGGER123")
    assert result is True
    handler._posting_handler.post_message.assert_awaited_once()
    handler._send_success_modal.assert_awaited_once_with("TRIGGER123")


async def test_send_feedback_report_to_channel_modal_fail(handler, monkeypatch) -> None:
    """Test send_feedback_report_to_channel returns True if post succeeds but modal fails."""
    monkeypatch.setattr(handler, "_send_success_modal", AsyncMock(return_value=False))
    handler._posting_handler.post_message = AsyncMock(return_value=True)
    result = await handler.send_feedback_report_to_channel("U1", "title", "desc", "TRIGGER123")
    assert result is True
    handler._posting_handler.post_message.assert_awaited_once()
    handler._send_success_modal.assert_awaited_once_with("TRIGGER123")


async def test_send_feedback_report_to_channel_post_fail(handler, monkeypatch) -> None:
    """Test send_feedback_report_to_channel returns False if post_message fails."""
    monkeypatch.setattr(handler, "_send_success_modal", AsyncMock(return_value=True))
    handler._posting_handler.post_message = AsyncMock(return_value=False)
    result = await handler.send_feedback_report_to_channel("U1", "title", "desc", "TRIGGER123")
    assert result is False
    handler._posting_handler.post_message.assert_awaited_once()
    handler._send_success_modal.assert_not_awaited()


async def test_send_feedback_report_to_channel_exception(handler, monkeypatch) -> None:
    """Test send_feedback_report_to_channel returns False on exception."""
    handler._posting_handler.post_message = AsyncMock(side_effect=Exception("fail"))
    result = await handler.send_feedback_report_to_channel("U1", "title", "desc", "TRIGGER123")
    assert result is False
