"""Unit tests for Slack Block Kit message formatters.

Tests the formatting functions for final queries, clarifying questions,
and uncertainty messages using Slack's Block Kit structure.
"""

from asksplunk.slack.formatter import (
    format_clarifying_question,
    format_final_query,
    format_uncertainty_message,
)


class TestSlackFormatter:
    """Test Slack Block Kit message formatters."""

    def test_format_final_query_includes_plain_explanation(self):
        """Final query should include plain language explanation."""
        blocks = format_final_query(
            plain_explanation="This finds email bounces",
            spl_query="index=campaign_prod failureType=*",
            technical_explanation="Uses failureType field",
        )

        # Find plain explanation section
        plain_sections = [
            b
            for b in blocks
            if b.get("type") == "section"
            and b.get("text", {}).get("text", "").startswith("*Plain Language:*")
        ]
        assert len(plain_sections) == 1
        assert "email bounces" in plain_sections[0]["text"]["text"]

    def test_format_final_query_includes_spl_code_block(self):
        """SPL query should be in code block (no language identifier)."""
        blocks = format_final_query(
            plain_explanation="Test",
            spl_query="index=campaign_prod",
            technical_explanation="Test",
        )

        # Find code block (no language identifier to prevent copy issues)
        code_sections = [
            b
            for b in blocks
            if b.get("type") == "section" and "```\n" in b.get("text", {}).get("text", "")
        ]
        assert len(code_sections) >= 1
        assert "index=campaign_prod" in code_sections[0]["text"]["text"]

    def test_format_final_query_includes_technical_details(self):
        """Final query should include technical explanation in context block."""
        blocks = format_final_query(
            plain_explanation="Test",
            spl_query="index=campaign_prod",
            technical_explanation="Uses campaign_prod index",
        )

        # Find context block with technical details
        context_blocks = [
            b
            for b in blocks
            if b.get("type") == "context"
            and any("Technical:" in elem.get("text", "") for elem in b.get("elements", []))
        ]
        assert len(context_blocks) >= 1
        assert any(
            "campaign_prod index" in elem.get("text", "") for elem in context_blocks[0]["elements"]
        )

    def test_format_final_query_includes_session_complete_message(self):
        """Final query should include session complete notification."""
        blocks = format_final_query(
            plain_explanation="Test",
            spl_query="index=campaign_prod",
            technical_explanation="Test",
        )

        # Find session complete context block
        session_complete_blocks = [
            b
            for b in blocks
            if b.get("type") == "context"
            and any("Session complete" in elem.get("text", "") for elem in b.get("elements", []))
        ]
        assert len(session_complete_blocks) == 1
        assert any(
            "all data cleared" in elem.get("text", "")
            for elem in session_complete_blocks[0]["elements"]
        )

    def test_format_clarifying_question_with_numbered_list(self):
        """Clarifying question should have numbered options list."""
        blocks = format_clarifying_question(
            question="Which log type?", options=["mta_log", "web_log"]
        )

        # Should have 3 blocks: question section, options section, context
        assert len(blocks) == 3
        assert blocks[0]["type"] == "section"
        assert blocks[1]["type"] == "section"
        assert blocks[2]["type"] == "context"

        # Verify numbered options format
        options_text = blocks[1]["text"]["text"]
        assert "*1.* mta_log" in options_text
        assert "*2.* web_log" in options_text

    def test_format_clarifying_question_includes_question_text(self):
        """Clarifying question should display the question text."""
        blocks = format_clarifying_question(
            question="Which log type?", options=["mta_log", "web_log"]
        )

        # Find section with question
        question_sections = [b for b in blocks if b.get("type") == "section"]
        assert len(question_sections) >= 1
        assert "Which log type?" in question_sections[0]["text"]["text"]

    def test_format_uncertainty_message_includes_warning(self):
        """Uncertainty message should include warning emoji and missing info."""
        blocks = format_uncertainty_message(missing_info="log retention period")

        # Find warning section
        warning_sections = [
            b
            for b in blocks
            if b.get("type") == "section" and "⚠️" in b.get("text", {}).get("text", "")
        ]
        assert len(warning_sections) >= 1
        assert "log retention period" in warning_sections[0]["text"]["text"]

    def test_format_uncertainty_message_suggests_clarification(self):
        """Uncertainty message should suggest user provide more details."""
        blocks = format_uncertainty_message(missing_info="field name")

        # Find clarification suggestion
        clarification_sections = [
            b
            for b in blocks
            if b.get("type") == "section"
            and "more details" in b.get("text", {}).get("text", "").lower()
        ]
        assert len(clarification_sections) >= 1

    def test_format_final_query_with_very_long_spl(self):
        """Should handle very long SPL queries without truncation."""
        long_query = "index=campaign_prod " + " OR ".join([f"field{i}=value{i}" for i in range(50)])
        blocks = format_final_query(
            plain_explanation="Test",
            spl_query=long_query,
            technical_explanation="Test",
        )

        # Find code block (no language identifier)
        code_sections = [
            b
            for b in blocks
            if b.get("type") == "section" and "```\n" in b.get("text", {}).get("text", "")
        ]
        assert len(code_sections) >= 1
        assert "field49=value49" in code_sections[0]["text"]["text"]

    def test_format_final_query_with_special_characters(self):
        """Should properly escape special characters in explanations."""
        blocks = format_final_query(
            plain_explanation="Find records with * and _ characters",
            spl_query="index=campaign_prod search=*",
            technical_explanation="Uses wildcards (*) for pattern matching",
        )

        # Verify special characters preserved
        plain_sections = [
            b
            for b in blocks
            if b.get("type") == "section"
            and b.get("text", {}).get("text", "").startswith("*Plain Language:*")
        ]
        assert "*" in plain_sections[0]["text"]["text"]
        assert "_" in plain_sections[0]["text"]["text"]

    def test_format_clarifying_question_with_multiple_options(self):
        """Should handle multiple numbered options correctly."""
        options = ["option1", "option2", "option3", "option4", "option5"]
        blocks = format_clarifying_question(question="Choose one:", options=options)

        # Should have 3 blocks
        assert len(blocks) == 3

        # Verify all options present with numbers
        options_text = blocks[1]["text"]["text"]
        for i, opt in enumerate(options, 1):
            assert f"*{i}.* {opt}" in options_text

    def test_format_final_query_has_divider(self):
        """Final query should include divider for visual separation."""
        blocks = format_final_query(
            plain_explanation="Test",
            spl_query="index=campaign_prod",
            technical_explanation="Test",
        )

        # Find divider block
        divider_blocks = [b for b in blocks if b.get("type") == "divider"]
        assert len(divider_blocks) >= 1

    def test_format_clarifying_question_includes_reply_instructions(self):
        """Clarifying question should include instructions for replying."""
        blocks = format_clarifying_question(question="Choose:", options=["opt1", "opt2", "opt3"])

        # Find context block with instructions
        context_blocks = [b for b in blocks if b.get("type") == "context"]
        assert len(context_blocks) == 1

        instruction_text = context_blocks[0]["elements"][0]["text"]
        assert "Reply with a number" in instruction_text
        assert "(1, 2, etc.)" in instruction_text
