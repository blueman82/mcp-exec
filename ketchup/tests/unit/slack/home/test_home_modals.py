"""
test_home_modals.py

Covers:
- open_success_modal: Modal publishing logic, error handling, Slack API call
- All dependencies (slack_client) are mocked

Edge Cases Covered:
- Slack API call returns ok: False
- Exception during Slack API call

Expected Outcomes:
- Returns True on successful modal open
- Returns False on error or Slack API failure
- Logs errors appropriately
"""

from unittest.mock import AsyncMock, patch

import pytest

from packages.slack.home.home_modals import open_success_modal


@pytest.mark.asyncio
async def test_open_success_modal_success():
    """Test open_success_modal returns True on successful Slack API call."""
    slack_client = AsyncMock()
    slack_client.api_call.return_value = {"ok": True}
    result = await open_success_modal(slack_client, "TID123", "Gary Harrison")
    assert result is True
    slack_client.api_call.assert_awaited()


@pytest.mark.asyncio
async def test_open_success_modal_slack_error():
    """Test open_success_modal returns False if Slack API returns ok: False."""
    slack_client = AsyncMock()
    slack_client.api_call.return_value = {"ok": False, "error": "fail"}
    with patch("packages.slack.home.home_modals.logger") as mock_logger:
        result = await open_success_modal(slack_client, "TID123", "Gary Harrison")
        assert result is False
        mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_open_success_modal_exception():
    """Test open_success_modal returns False and logs error on exception."""
    slack_client = AsyncMock()
    slack_client.api_call.side_effect = Exception("API error")
    with patch("packages.slack.home.home_modals.logger") as mock_logger:
        result = await open_success_modal(slack_client, "TID123", "Gary Harrison")
        assert result is False
        mock_logger.error.assert_called()
