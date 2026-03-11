"""
Unit tests for handover summary prompts.
"""

from unittest.mock import patch

from packages.ai.prompts.handover_summary import (
    get_handover_channel_prompt,
    get_handover_system_prompt,
)


class TestHandoverPrompts:
    """Test cases for handover summary prompts"""

    def test_system_prompt_is_non_empty_string(self):
        """Test system prompt returns non-empty string"""
        prompt = get_handover_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_system_prompt_mentions_bullet_points(self):
        """Test system prompt mentions bullet points"""
        prompt = get_handover_system_prompt()

        assert "bullet" in prompt.lower()

    def test_system_prompt_mentions_ultra_compact(self):
        """Test system prompt emphasizes ultra-compact format"""
        prompt = get_handover_system_prompt()

        assert "ultra-compact" in prompt.lower()

    def test_system_prompt_mentions_1_2_bullets(self):
        """Test system prompt specifies 1-2 bullet points"""
        prompt = get_handover_system_prompt()

        assert "1-2 bullet" in prompt.lower()

    def test_channel_prompt_mentions_accuracy_requirements(self):
        """Test channel prompt includes accuracy requirements"""
        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments="Sample comments",
        )

        assert "speculation" in prompt.lower() or "only the slack messages" in prompt.lower()

    def test_channel_prompt_includes_channel_name(self):
        """Test channel prompt includes the channel name"""
        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments="Sample comments",
        )

        assert "test-incident" in prompt

    def test_channel_prompt_includes_customer_name(self):
        """Test channel prompt includes the customer name"""
        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments="Sample comments",
        )

        assert "Acme Corp" in prompt

    def test_channel_prompt_includes_jira_ticket(self):
        """Test channel prompt includes the JIRA ticket"""
        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments="Sample comments",
        )

        assert "TEST-123" in prompt

    def test_channel_prompt_includes_messages_content(self):
        """Test channel prompt includes messages content"""
        messages_text = "User: We're experiencing database issues"

        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages=messages_text,
            jira_comments="Sample comments",
        )

        assert messages_text in prompt

    def test_channel_prompt_includes_jira_comments_content(self):
        """Test channel prompt includes JIRA comments content"""
        jira_text = "[2024-01-01] John: Fixed the issue"

        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments=jira_text,
        )

        assert jira_text in prompt

    def test_channel_prompt_has_slack_messages_section(self):
        """Test channel prompt has SLACK MESSAGES section"""
        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments="Sample comments",
        )

        assert "SLACK MESSAGES" in prompt

    def test_channel_prompt_has_jira_comments_section(self):
        """Test channel prompt has JIRA COMMENTS section"""
        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments="Sample comments",
        )

        assert "JIRA COMMENTS" in prompt

    def test_channel_prompt_has_instructions_section(self):
        """Test channel prompt has instructions section"""
        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments="Sample comments",
        )

        assert "INSTRUCTIONS" in prompt or "instructions" in prompt.lower()

    def test_channel_prompt_mentions_bullet_character(self):
        """Test channel prompt specifies bullet character"""
        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments="Sample comments",
        )

        assert "•" in prompt

    def test_channel_prompt_mentions_max_words(self):
        """Test channel prompt mentions maximum word count"""
        prompt = get_handover_channel_prompt(
            channel_name="test-incident",
            customer_name="Acme Corp",
            jira_ticket="TEST-123",
            messages="Sample messages",
            jira_comments="Sample comments",
        )

        assert "50 words" in prompt.lower()

    def test_channel_prompt_includes_json_schema_when_enabled(self):
        """Test channel prompt includes JSON schema instruction when feature flag enabled"""
        with patch(
            "packages.ai.prompts.handover_summary.FeatureFlags.is_structured_json_output_enabled"
        ) as mock_flag:
            mock_flag.return_value = True

            prompt = get_handover_channel_prompt(
                channel_name="test-incident",
                customer_name="Acme Corp",
                jira_ticket="TEST-123",
                messages="Sample messages",
                jira_comments="Sample comments",
            )

            assert "JSON" in prompt
            assert "response_text" in prompt

    def test_channel_prompt_excludes_json_schema_when_disabled(self):
        """Test channel prompt excludes JSON schema instruction when feature flag disabled"""
        with patch(
            "packages.ai.prompts.handover_summary.FeatureFlags.is_structured_json_output_enabled"
        ) as mock_flag:
            mock_flag.return_value = False

            prompt = get_handover_channel_prompt(
                channel_name="test-incident",
                customer_name="Acme Corp",
                jira_ticket="TEST-123",
                messages="Sample messages",
                jira_comments="Sample comments",
            )

            # Should not contain JSON schema instruction
            assert "response_text" not in prompt
