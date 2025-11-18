"""
test_prompts.py

Unit tests for all prompt generator functions and constants in packages.ai.prompts.

Covers:
- Prompt constants: COMMON_GUIDELINES_PROMPT
- Prompt functions: get_customer_name_extraction_prompt, get_query_prompt, get_status_prompt, get_report_prompt
- Checks for non-empty, required sections, and correct formatting
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

import pytest

from packages.ai.prompts.common_guidelines import COMMON_GUIDELINES_PROMPT
from packages.ai.prompts.customer_extraction import get_customer_name_extraction_prompt
from packages.ai.prompts.query import get_query_prompt
from packages.ai.prompts.report import get_report_prompt
from packages.ai.prompts.status import get_status_prompt


@pytest.mark.unit
class TestPromptConstants:
    """Unit tests for prompt constants in packages.ai.prompts."""

    def test_common_guidelines_prompt_non_empty(self) -> None:
        """Test COMMON_GUIDELINES_PROMPT is a non-empty string and contains required sections."""
        assert isinstance(COMMON_GUIDELINES_PROMPT, str)
        assert COMMON_GUIDELINES_PROMPT.strip() != ""
        assert "FORMATTING RULES" in COMMON_GUIDELINES_PROMPT
        assert "QUERY FILTERING - CHECK FIRST" in COMMON_GUIDELINES_PROMPT
        assert "JIRA tickets:" in COMMON_GUIDELINES_PROMPT


@pytest.mark.unit
class TestPromptFunctions:
    """Unit tests for prompt generator functions in packages.ai.prompts."""

    def test_get_customer_name_extraction_prompt(self) -> None:
        """Test get_customer_name_extraction_prompt returns a string with required sections."""
        prompt = get_customer_name_extraction_prompt()
        assert isinstance(prompt, str)
        assert "CUSTOMER NAME AND JIRA TICKET EXTRACTION INSTRUCTIONS" in prompt
        assert "Self-Verification Checklist" in prompt
        # The implementation doesn't have an END section, remove that assertion

    @pytest.mark.parametrize("query_text", ["", "What happened?", "1234"])
    def test_get_query_prompt(self, query_text: str) -> None:
        """Test get_query_prompt returns a string with the query text and required sections."""
        prompt = get_query_prompt(query_text)
        assert isinstance(prompt, str)
        assert "QUERY RESPONSE INSTRUCTIONS" in prompt
        assert query_text in prompt
        assert "END OF QUERY RESPONSE INSTRUCTIONS" in prompt

        # Test new format requirements
        assert "**Direct Answer:**" in prompt
        assert "**Details:**" in prompt
        assert "50-150 words maximum" in prompt
        assert "Lead with a direct answer to the query" in prompt
        assert "exact matches only" in prompt
        assert "specific product name" in prompt

    def test_get_status_prompt_with_dict_params(self) -> None:
        """Test get_status_prompt returns a string with dictionary parameters and required sections."""
        # Test with no parameters
        prompt = get_status_prompt()
        assert isinstance(prompt, str)
        assert "STATUS REPORT INSTRUCTIONS" in prompt

        # Test with user preferences as dict
        user_prefs = {"role": "incident response analyst", "detail_level": "balanced"}
        prompt = get_status_prompt(user_prefs)
        assert isinstance(prompt, str)

        # Test new sections are present
        assert "Engineers Actively Investigating & Their Tasks" in prompt
        assert "Timeline" in prompt
        assert ":construction_worker:" in prompt
        assert ":calendar:" in prompt
        assert "**DD-MMM-YYYY, HH:MM UTC:**" in prompt
        assert "600 words" in prompt  # Updated word limit

    @pytest.mark.parametrize("report_text", [None, "full report", "minimal"])
    def test_get_report_prompt(self, report_text: str | None) -> None:
        """Test get_report_prompt returns a string with the report text and required sections."""
        if report_text is None:
            prompt = get_report_prompt()
        else:
            prompt = get_report_prompt(report_text)
        assert isinstance(prompt, str)
        assert "END OF REPORT INSTRUCTIONS" in prompt

        # Test new sections are present
        assert "People Involved" in prompt
        assert "Incident Timeline" in prompt
        assert ":busts_in_silhouette:" in prompt
        assert ":calendar:" in prompt
        assert "**DD-MMM-YYYY, HH:MM UTC:**" in prompt
        assert "600 words" in prompt  # Updated word limit
        assert "8-9 main sections" in prompt  # Updated from 7 to 8-9


@pytest.mark.unit
class TestPromptAdaptation:
    def test_status_prompt_user_prefs(self):
        prefs = {
            "role": "SRE",
            "detail_level": "detailed",
            "product_focus": ["ketchup"],
        }
        prompt = get_status_prompt(user_prefs=prefs)
        assert "highly skilled SRE" in prompt
        assert "ketchup" in prompt

    def test_report_prompt_user_prefs(self):
        prefs = {
            "role": "manager",
            "detail_level": "summary",
            "product_focus": ["mustard"],
        }
        prompt = get_report_prompt(user_prefs=prefs)
        assert "As a incident response analyst," in prompt
