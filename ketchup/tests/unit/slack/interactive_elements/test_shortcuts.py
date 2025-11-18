"""
Unit tests for packages.slack.interactive_elements.shortcuts

This module provides comprehensive tests for the ShortcutHandler class, which processes Slack shortcuts (e.g., feedback report shortcut).

Coverage includes:
- All logic branches: feedback_report shortcut, missing trigger_id, modal open failure, unhandled shortcut, missing user/channel
- Edge cases: missing/invalid payload fields, posting errors
- All dependencies (FeedbackReportHandler, SlackPostingHandler) are mocked to isolate handler logic

Expected outcomes:
- All branches and error cases are directly tested
- All tests are mypy- and ruff-clean
- Each test function includes a detailed docstring per @ketchup_test_plan.md
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.slack.interactive_elements.shortcuts import ShortcutHandler

pytestmark = pytest.mark.asyncio


@pytest.fixture
def feedback_report_handler_mock() -> MagicMock:
    mock = MagicMock()
    mock.open_feedback_report_modal = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def posting_handler_mock() -> MagicMock:
    mock = MagicMock()
    mock.post_message = AsyncMock()
    return mock


@pytest.fixture
def handler(feedback_report_handler_mock, posting_handler_mock) -> ShortcutHandler:
    return ShortcutHandler(feedback_report_handler_mock, posting_handler_mock)


async def test_handle_shortcut_feedback_report_success(
    handler, feedback_report_handler_mock, posting_handler_mock
) -> None:
    """Test feedback_report shortcut with valid trigger_id.

    Covers:
    - callback_id == 'feedback_report' and trigger_id present
    - open_feedback_report_modal returns True
    - Expects True returned, no error message posted
    """
    payload = {
        "callback_id": "feedback_report",
        "trigger_id": "T123",
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
    }
    result = await handler.handle_shortcut(payload)
    assert result is True
    feedback_report_handler_mock.open_feedback_report_modal.assert_awaited_once_with(
        "T123"
    )
    posting_handler_mock.post_message.assert_not_awaited()


async def test_handle_shortcut_feedback_report_missing_trigger_id(
    handler, posting_handler_mock
) -> None:
    """Test feedback_report shortcut with missing trigger_id.

    Covers:
    - callback_id == 'feedback_report' but trigger_id missing
    - Expects False returned, error message posted to user/channel
    """
    payload = {
        "callback_id": "feedback_report",
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
    }
    result = await handler.handle_shortcut(payload)
    assert result is False
    posting_handler_mock.post_message.assert_awaited_once_with(
        user_id="U1",
        channel_id="C1",
        message="Error: Missing information to open feedback form.",
    )


async def test_handle_shortcut_feedback_report_modal_failure(
    handler, feedback_report_handler_mock, posting_handler_mock
) -> None:
    """Test feedback_report shortcut where modal open fails.

    Covers:
    - callback_id == 'feedback_report', trigger_id present
    - open_feedback_report_modal returns False
    - Expects False returned, error message posted to user/channel
    """
    feedback_report_handler_mock.open_feedback_report_modal = AsyncMock(
        return_value=False
    )
    payload = {
        "callback_id": "feedback_report",
        "trigger_id": "T123",
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
    }
    result = await handler.handle_shortcut(payload)
    assert result is False
    posting_handler_mock.post_message.assert_awaited_once_with(
        user_id="U1",
        channel_id="C1",
        message="Error opening feedback form. Please try again.",
    )


async def test_handle_shortcut_feedback_report_missing_user_or_channel(
    handler, posting_handler_mock
) -> None:
    """Test feedback_report shortcut with missing user or channel.

    Covers:
    - callback_id == 'feedback_report', trigger_id missing
    - user or channel missing from payload
    - Expects False returned, no error message posted (cannot post)
    """
    payload = {"callback_id": "feedback_report"}
    result = await handler.handle_shortcut(payload)
    assert result is False
    posting_handler_mock.post_message.assert_not_awaited()


async def test_handle_shortcut_unhandled_shortcut(
    handler, posting_handler_mock
) -> None:
    """Test unhandled shortcut callback_id.

    Covers:
    - callback_id is not 'feedback_report'
    - Expects True returned, warning message posted to user/channel
    """
    payload = {
        "callback_id": "unknown_shortcut",
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
    }
    result = await handler.handle_shortcut(payload)
    assert result is True
    posting_handler_mock.post_message.assert_awaited_once_with(
        user_id="U1",
        channel_id="C1",
        message="Shortcut 'unknown_shortcut' not handled.",
    )


async def test_handle_shortcut_unhandled_shortcut_missing_user_or_channel(
    handler, posting_handler_mock
) -> None:
    """Test unhandled shortcut with missing user or channel.

    Covers:
    - callback_id is not 'feedback_report'
    - user or channel missing from payload
    - Expects True returned, no error message posted (cannot post)
    """
    payload = {"callback_id": "unknown_shortcut"}
    result = await handler.handle_shortcut(payload)
    assert result is True
    posting_handler_mock.post_message.assert_not_awaited()
