"""
test_text_preprocessing.py

Unit tests for text preprocessing utilities.
"""

from packages.core.utils import normalize_prompt_for_agent


class TestNormalizePromptForAgent:
    """Test the normalize_prompt_for_agent function."""

    def test_removes_multiple_newlines(self):
        """Test that multiple consecutive newlines are replaced with single space."""
        input_text = """Line 1
        
        
        Line 2
        
        Line 3"""
        expected = "Line 1 Line 2 Line 3"
        assert normalize_prompt_for_agent(input_text) == expected

    def test_preserves_structured_lists(self):
        """Test that structured lists are preserved."""
        input_text = """Search for tickets:
1. First item
2. Second item
- Bullet point
- Another bullet"""
        expected = "Search for tickets: 1. First item 2. Second item - Bullet point - Another bullet"
        assert normalize_prompt_for_agent(input_text) == expected

    def test_handles_complex_report_prompt(self):
        """Test handling of complex multi-line report prompts."""
        input_text = """You are to generate a report titled "Weekly Report".
        
        Format:
        
        Section 1:
        - Item A
        - Item B
        
        
        Section 2:
        - Item C"""
        expected = 'You are to generate a report titled "Weekly Report". Format: Section 1: - Item A - Item B Section 2: - Item C'
        assert normalize_prompt_for_agent(input_text) == expected

    def test_handles_empty_input(self):
        """Test that empty input returns empty string."""
        assert normalize_prompt_for_agent("") == ""
        assert normalize_prompt_for_agent(None) is None

    def test_normalizes_whitespace(self):
        """Test that multiple spaces are normalized."""
        input_text = "Too    many     spaces    between"
        expected = "Too many spaces between"
        assert normalize_prompt_for_agent(input_text) == expected

    def test_strips_leading_trailing_whitespace(self):
        """Test that leading and trailing whitespace is removed."""
        input_text = "   \n\n  Content with spaces  \n\n   "
        expected = "Content with spaces"
        assert normalize_prompt_for_agent(input_text) == expected

    def test_preserves_single_line_breaks_after_colons(self):
        """Test that line breaks after colons are preserved as spaces."""
        input_text = """JQL Query:
project = CPGN AND status = Open"""
        expected = "JQL Query: project = CPGN AND status = Open"
        assert normalize_prompt_for_agent(input_text) == expected
