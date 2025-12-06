"""
Unit tests for auto-status prompts
"""

from packages.ai.prompts.auto_status import (
    get_auto_status_prompt,
    get_auto_status_system_prompt,
)


class TestAutoStatusPrompts:
    """Test cases for auto-status prompt generation"""

    def test_get_auto_status_system_prompt(self):
        """Test system prompt generation"""
        prompt = get_auto_status_system_prompt()

        assert isinstance(prompt, str)
        assert (
            "AI assistant specialized in generating ultra-concise channel status reports" in prompt
        )
        assert "CRITICAL ACCURACY REQUIREMENTS" in prompt
        assert "technical details" in prompt

    def test_get_auto_status_prompt_basic(self):
        """Test basic auto-status prompt generation"""
        channel_info = {
            "channel_name": "test-channel",
            "channel_id": "C12345",
            "customer_name": "Test Customer",
            "jira_ticket": "TEST-123",
            "product": "test-product",
        }

        prompt = get_auto_status_prompt(channel_info)

        # Check key components
        assert "Generate a status update for <#test-channel|C12345>" in prompt
        assert "Customer: Test Customer" in prompt
        assert "JIRA: TEST-123" in prompt
        assert "*Overview:*" in prompt
        assert "*What's been done / What's next:*" in prompt
        assert "EXACTLY 4 bullets, no more, no less" in prompt
        assert "Under 150 words" in prompt

    def test_get_auto_status_prompt_missing_info(self):
        """Test prompt generation with missing information"""
        channel_info = {"channel_name": "test-channel", "channel_id": "C12345"}

        prompt = get_auto_status_prompt(channel_info)

        # Check defaults are used
        assert "Customer: Unknown" in prompt
        assert "JIRA: None" in prompt

    def test_get_auto_status_prompt_with_preferences(self):
        """Test that function works with all required parameters"""
        channel_info = {
            "channel_name": "test-channel",
            "channel_id": "C12345",
            "customer_name": "Test Customer",
            "jira_ticket": "TEST-123",
        }

        prompt = get_auto_status_prompt(channel_info)

        # Should generate a valid prompt with all provided info
        assert "Customer: Test Customer" in prompt
        assert "JIRA: TEST-123" in prompt
        assert "Generate a status update for <#test-channel|C12345>" in prompt

    def test_get_auto_status_prompt_formatting_rules(self):
        """Test that formatting rules are included in prompt"""
        channel_info = {"channel_name": "test-channel", "channel_id": "C12345"}

        prompt = get_auto_status_prompt(channel_info)

        # Check all formatting rules
        assert "1-2 sentences maximum" in prompt
        assert "EXACTLY 4 bullets" in prompt
        assert "past tense for completed" in prompt
        assert "future tense for planned" in prompt
        assert "Under 150 words" in prompt
        assert "MUST appear verbatim in the source" in prompt
