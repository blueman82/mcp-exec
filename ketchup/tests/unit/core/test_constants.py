"""
Test module for core constants, particularly the new channel regex patterns.
"""

from packages.core.constants import (
    SLACK_CHANNEL_ID_REGEX,
    SLACK_CHANNEL_MENTION_REGEX,
    SLACK_CHANNEL_NAME_REGEX,
)


class TestSlackChannelRegexPatterns:
    """Test cases for Slack channel regex patterns."""

    def test_slack_channel_id_regex_valid_patterns(self):
        """Test that valid channel IDs match the regex."""
        valid_channel_ids = [
            "C1234567890",  # Standard channel
            "G1234567890",  # Group/private channel
            "C12345678",  # 8 characters (minimum)
            "C12345678901",  # 11 characters (maximum)
            "CABCDEFGHIJ",  # Mixed letters and numbers
        ]

        for channel_id in valid_channel_ids:
            assert SLACK_CHANNEL_ID_REGEX.match(
                channel_id
            ), f"Should match: {channel_id}"

    def test_slack_channel_id_regex_invalid_patterns(self):
        """Test that invalid channel IDs don't match the regex."""
        invalid_channel_ids = [
            "D1234567890",  # DM channel (not supported)
            "c1234567890",  # Lowercase prefix
            "C123456",  # Too short (6 chars)
            "C123456789012",  # Too long (12 chars)
            "C123456789a",  # Lowercase in ID part
            "1234567890",  # Missing prefix
            "",  # Empty string
            "C",  # Just prefix
            "C!@#$%^&*()",  # Special characters
        ]

        for channel_id in invalid_channel_ids:
            assert not SLACK_CHANNEL_ID_REGEX.match(
                channel_id
            ), f"Should not match: {channel_id}"

    def test_slack_channel_mention_regex_valid_patterns(self):
        """Test that valid channel mentions match the regex."""
        valid_mentions = [
            "<#C1234567890|general>",
            "<#G1234567890|private-channel>",
            "<#C12345678|short>",
            "<#C12345678901|very-long-channel-name>",
            "<#CABCDEFGHIJ|channel_with_underscores>",
            "<#C1234567890|channel-123>",
        ]

        for mention in valid_mentions:
            match = SLACK_CHANNEL_MENTION_REGEX.match(mention)
            assert match, f"Should match: {mention}"
            # Verify we can extract channel ID and name
            channel_id = match.group(1)
            channel_name = match.group(2)
            assert channel_id.startswith(("C", "G"))
            assert len(channel_name) > 0

    def test_slack_channel_mention_regex_invalid_patterns(self):
        """Test that invalid channel mentions don't match the regex."""
        invalid_mentions = [
            "<#D1234567890|dm>",  # DM channel
            "<#c1234567890|general>",  # Lowercase prefix
            "<#C123456|short>",  # ID too short
            "<C1234567890|general>",  # Missing #
            "<#C1234567890>",  # Missing pipe and name
            "<#C1234567890|>",  # Empty name
            "C1234567890|general",  # Missing brackets
            "<#C1234567890|general",  # Missing closing bracket
            "",  # Empty string
        ]

        for mention in invalid_mentions:
            assert not SLACK_CHANNEL_MENTION_REGEX.match(
                mention
            ), f"Should not match: {mention}"

    def test_slack_channel_mention_regex_extraction(self):
        """Test extracting channel ID and name from mentions."""
        test_cases = [
            (
                "<#C08U5S51Z4N|sit_room_202505280031_acs_stena_76893>",
                "C08U5S51Z4N",
                "sit_room_202505280031_acs_stena_76893",
            ),
            ("<#G1234567890|private-channel>", "G1234567890", "private-channel"),
            ("<#CABCDEFGHIJ|test_channel>", "CABCDEFGHIJ", "test_channel"),
        ]

        for mention, expected_id, expected_name in test_cases:
            match = SLACK_CHANNEL_MENTION_REGEX.match(mention)
            assert match, f"Should match: {mention}"
            assert match.group(1) == expected_id, f"Channel ID mismatch for {mention}"
            assert (
                match.group(2) == expected_name
            ), f"Channel name mismatch for {mention}"

    def test_slack_channel_name_regex_valid_patterns(self):
        """Test that valid channel names match the regex."""
        valid_names = [
            "#general",
            "#random",
            "#sit-room-2025",
            "#test_channel",
            "#a",  # Single character
            "#test-123",  # With numbers
            "#channel_with_underscores",
            "#sit_room_202505280031_acs_stena_76893",  # Long real example
        ]

        for name in valid_names:
            match = SLACK_CHANNEL_NAME_REGEX.match(name)
            assert match, f"Should match: {name}"
            # Verify we can extract the name part (without #)
            extracted_name = match.group(1)
            assert extracted_name == name[1:], f"Name extraction failed for {name}"

    def test_slack_channel_name_regex_invalid_patterns(self):
        """Test that invalid channel names don't match the regex."""
        invalid_names = [
            "general",  # Missing #
            "#General",  # Uppercase
            "#-test",  # Starting with hyphen
            "#_test",  # Starting with underscore
            "#test!",  # Special character
            "#test channel",  # Space
            "#test@channel",  # @ symbol
            "#",  # Just #
            "",  # Empty string
            "#a" * 82,  # Too long (82+ chars)
        ]

        for name in invalid_names:
            assert not SLACK_CHANNEL_NAME_REGEX.match(name), f"Should not match: {name}"

    def test_slack_channel_name_regex_extraction(self):
        """Test extracting channel name without # prefix."""
        test_cases = [
            ("#general", "general"),
            (
                "#sit_room_202505280031_acs_stena_76893",
                "sit_room_202505280031_acs_stena_76893",
            ),
            ("#test-channel-123", "test-channel-123"),
        ]

        for full_name, expected_name in test_cases:
            match = SLACK_CHANNEL_NAME_REGEX.match(full_name)
            assert match, f"Should match: {full_name}"
            assert (
                match.group(1) == expected_name
            ), f"Name extraction failed for {full_name}"
