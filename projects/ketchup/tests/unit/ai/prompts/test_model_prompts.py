"""
test_model_prompts.py

Unit tests for packages.ai.model_prompts.get_prompt_for_command.

Covers:
- All command types: /ketchup list, query, status, report
- Edge cases: unrecognized command, missing/optional arguments
- Patching of all imported prompt constants/functions
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import MagicMock, patch

import pytest

from packages.ai.model_prompts import get_prompt_for_command


@pytest.mark.unit
class TestGetPromptForCommand:
    """Unit tests for get_prompt_for_command in model_prompts.py."""

    @patch("packages.ai.model_prompts.COMMON_GUIDELINES_PROMPT", "COMMON")
    @patch(
        "packages.ai.model_prompts.get_customer_name_extraction_prompt",
        return_value="CUSTOMER",
    )
    def test_list_command(self, mock_customer: MagicMock) -> None:
        """Test /ketchup list command returns combined guidelines and customer extraction prompt."""
        result = get_prompt_for_command("/ketchup list")
        assert result == "COMMON\nCUSTOMER"
        mock_customer.assert_called_once_with()

    @patch("packages.ai.model_prompts.COMMON_GUIDELINES_PROMPT", "COMMON")
    @patch("packages.ai.model_prompts.get_query_prompt", return_value="QUERY")
    def test_query_command(self, mock_query: MagicMock) -> None:
        """Test /ketchup query command returns combined guidelines and query prompt."""
        result = get_prompt_for_command("/ketchup query", query_text="foo?")
        assert result == "COMMON\nQUERY"
        mock_query.assert_called_once_with("foo?")

    @patch("packages.ai.model_prompts.COMMON_GUIDELINES_PROMPT", "COMMON")
    @patch("packages.ai.model_prompts.get_status_prompt", return_value="STATUS")
    def test_status_command(self, mock_status: MagicMock) -> None:
        """Test /ketchup status command returns common guidelines + status prompt."""
        result = get_prompt_for_command("/ketchup status")
        assert result == "COMMON\nSTATUS"

    @patch("packages.ai.model_prompts.get_report_prompt", return_value="REPORT")
    def test_report_command(self, mock_report: MagicMock) -> None:
        """Test /ketchup report command returns only the report prompt (no guidelines)."""
        result = get_prompt_for_command(command="/ketchup report")
        assert result == "REPORT"
        mock_report.assert_called_once_with(user_prefs=None)

    def test_unrecognized_command(self) -> None:
        """Test that an unrecognized command returns None."""
        result = get_prompt_for_command("/ketchup unknown")
        assert result is None
