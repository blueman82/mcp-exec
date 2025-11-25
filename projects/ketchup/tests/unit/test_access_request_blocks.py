"""
Unit tests for AccessRequestBlocks UI components.

Tests the AccessRequestBlocks class for:
- Proper Block Kit structure generation
- Correct button action_ids
- Rate limiting message handling
- All UI scenarios (unauthorized, notifications, approvals, rejections)
"""

from datetime import datetime, timezone
from unittest.mock import patch

from packages.slack.blockkits.handlers.access_request_blocks import AccessRequestBlocks


class TestAccessRequestBlocks:
    """Test suite for AccessRequestBlocks UI components."""

    def test_build_unauthorized_message_with_button(self):
        """Test unauthorized message generation with request button."""
        user_id = "U123456789"

        blocks = AccessRequestBlocks.build_unauthorized_message(
            user_id=user_id, show_request_button=True
        )

        # Verify block structure
        assert isinstance(blocks, list)
        assert len(blocks) >= 3  # Should have header, section, actions

        # Check header block
        header_block = blocks[0]
        assert header_block["type"] == "header"
        assert header_block["text"]["type"] == "plain_text"
        assert "Access Required" in header_block["text"]["text"]

        # Check section block
        section_block = blocks[1]
        assert section_block["type"] == "section"
        assert section_block["text"]["type"] == "mrkdwn"
        assert (
            "don't currently have access to Ketchup commands"
            in section_block["text"]["text"]
        )

        # Check actions block
        actions_block = next(block for block in blocks if block["type"] == "actions")
        assert actions_block["type"] == "actions"
        assert len(actions_block["elements"]) == 1

        # Check button
        button = actions_block["elements"][0]
        assert button["type"] == "button"
        assert button["text"]["type"] == "plain_text"
        assert "Request Access" in button["text"]["text"]
        assert button["style"] == "primary"
        assert button["action_id"] == "request_access"
        assert button["value"] == user_id

    def test_build_unauthorized_message_without_button(self):
        """Test unauthorized message generation without request button."""
        user_id = "U123456789"

        blocks = AccessRequestBlocks.build_unauthorized_message(
            user_id=user_id, show_request_button=False
        )

        # Verify block structure
        assert isinstance(blocks, list)

        # Should not have actions block
        action_blocks = [block for block in blocks if block["type"] == "actions"]
        assert len(action_blocks) == 0

        # Should have alternative text with email
        has_contact_text = any(
            "org-omeara-all@adobe.com" in block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        )
        assert has_contact_text

    def test_build_unauthorized_message_with_rate_limit(self):
        """Test unauthorized message with rate limiting message."""
        user_id = "U123456789"
        rate_limit_message = "You have exceeded the rate limit (3 requests per hour)"

        blocks = AccessRequestBlocks.build_unauthorized_message(
            user_id=user_id, rate_limit_message=rate_limit_message
        )

        # Should have rate limit warning
        has_rate_limit = any(
            rate_limit_message in block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        )
        assert has_rate_limit

        # Should have rate limit emoji
        has_warning_emoji = any(
            "⏱️" in block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        )
        assert has_warning_emoji

    def test_build_access_request_notification(self):
        """Test access request notification for admins."""
        user_id = "U123456789"
        user_name = "test_user"
        user_email = "test@adobe.com"
        reason = "Need access for incident response"
        request_time = 1640995200.0  # 2022-01-01 00:00:00 UTC

        blocks = AccessRequestBlocks.build_access_request_notification(
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            reason=reason,
            request_time=request_time,
        )

        # Verify block structure
        assert isinstance(blocks, list)
        assert len(blocks) >= 4  # Header, user info, timestamp, actions

        # Check header
        header_block = blocks[0]
        assert header_block["type"] == "header"
        assert "New Access Request" in header_block["text"]["text"]

        # Check user info in fields
        user_info_found = False
        for block in blocks:
            if block["type"] == "section" and "fields" in block:
                for field in block["fields"]:
                    if user_name in field.get("text", ""):
                        user_info_found = True
                        break
        assert user_info_found

        # Check email in fields
        email_found = False
        for block in blocks:
            if block["type"] == "section" and "fields" in block:
                for field in block["fields"]:
                    if user_email in field.get("text", ""):
                        email_found = True
                        break
        assert email_found

        # Check actions block
        actions_block = next(block for block in blocks if block["type"] == "actions")
        assert len(actions_block["elements"]) == 2  # Approve and Reject buttons

        # Check approve button
        approve_button = actions_block["elements"][0]
        assert approve_button["type"] == "button"
        assert approve_button["style"] == "primary"
        assert approve_button["action_id"] == f"approve_access_{user_id}"
        assert "Approve" in approve_button["text"]["text"]
        assert approve_button["value"] == f"{user_id}|{request_time}"

        # Check reject button
        reject_button = actions_block["elements"][1]
        assert reject_button["type"] == "button"
        assert reject_button["style"] == "danger"
        assert reject_button["action_id"] == f"reject_access_{user_id}"
        assert "Reject" in reject_button["text"]["text"]
        assert reject_button["value"] == f"{user_id}|{request_time}"

    def test_build_request_processed_blocks_approved(self):
        """Test request processed blocks for approved requests."""
        original_blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Original message"}}
        ]
        processed_by = "admin_user"
        decision = "approved"
        decision_time = 1640995300.0
        rejection_reason = None

        blocks = AccessRequestBlocks.build_request_processed_blocks(
            original_blocks=original_blocks,
            processed_by=processed_by,
            decision=decision,
            decision_time=decision_time,
            rejection_reason=rejection_reason,
        )

        # Verify block structure
        assert isinstance(blocks, list)

        # Check for approval confirmation
        approval_found = any(
            "✅" in block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        )
        assert approval_found

        # Check admin name is mentioned
        admin_found = any(
            processed_by in block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        )
        assert admin_found

    def test_build_request_processed_blocks_rejected(self):
        """Test request processed blocks for rejected requests."""
        original_blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Original message"}}
        ]
        processed_by = "admin_user"
        decision = "rejected"
        decision_time = 1640995300.0
        rejection_reason = "Not a valid reason for access"

        blocks = AccessRequestBlocks.build_request_processed_blocks(
            original_blocks=original_blocks,
            processed_by=processed_by,
            decision=decision,
            decision_time=decision_time,
            rejection_reason=rejection_reason,
        )

        # Verify block structure
        assert isinstance(blocks, list)

        # Check for rejection indicator
        rejection_found = any(
            "❌" in block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        )
        assert rejection_found

        # Check admin name is mentioned
        admin_found = any(
            processed_by in block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        )
        assert admin_found

    def test_build_approval_dm(self):
        """Test approval DM message generation."""
        user_id = "U123456789"

        blocks = AccessRequestBlocks.build_approval_dm(user_id=user_id)

        # Verify block structure
        assert isinstance(blocks, list)

        # Check welcome message
        welcome_found = any(
            "Welcome to Ketchup" in block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        )
        assert welcome_found

        # Check user mention
        user_found = any(
            user_id in block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        )
        assert user_found

        # Check for help information
        help_found = any(
            "ketchup" in block.get("text", {}).get("text", "").lower()
            for block in blocks
            if block["type"] == "section"
        )
        assert help_found

    def test_build_rejection_modal(self):
        """Test rejection modal generation."""
        modal = AccessRequestBlocks.build_rejection_modal()

        # Verify modal structure
        assert isinstance(modal, dict)
        assert modal["type"] == "modal"
        assert modal["callback_id"] == "reject_reason_modal"

        # Check title
        assert modal["title"]["type"] == "plain_text"
        assert "Rejection Reason" in modal["title"]["text"]

        # Check submit button
        assert modal["submit"]["type"] == "plain_text"
        assert "Submit" in modal["submit"]["text"]

        # Check close button
        assert modal["close"]["type"] == "plain_text"
        assert "Cancel" in modal["close"]["text"]

        # Check blocks
        assert "blocks" in modal
        assert len(modal["blocks"]) >= 1

        # Modal has 1 block: just the input
        assert len(modal["blocks"]) == 1

        # First block is the input
        input_block = modal["blocks"][0]
        assert input_block["type"] == "input"
        assert input_block["block_id"] == "reason_block"

        # Check text input element
        element = input_block["element"]
        assert element["type"] == "plain_text_input"
        assert element["action_id"] == "reason_input"
        assert element["multiline"] is True

    def test_block_kit_structure_validation(self):
        """Test that all generated blocks follow proper Block Kit structure."""
        user_id = "U123456789"

        # Test all block generation methods
        test_cases = [
            AccessRequestBlocks.build_unauthorized_message(user_id),
            AccessRequestBlocks.build_access_request_notification(
                user_id=user_id,
                user_name="test",
                user_email="test@adobe.com",
                reason="Test reason",
                request_time=datetime.now(timezone.utc).timestamp(),
            ),
            AccessRequestBlocks.build_request_processed_blocks(
                original_blocks=[
                    {"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}
                ],
                processed_by="admin",
                decision="approved",
                decision_time=datetime.now(timezone.utc).timestamp(),
                rejection_reason=None,
            ),
            AccessRequestBlocks.build_approval_dm(user_id),
        ]

        for blocks in test_cases:
            assert isinstance(blocks, list)

            for block in blocks:
                assert isinstance(block, dict)
                assert "type" in block
                assert block["type"] in [
                    "header",
                    "section",
                    "actions",
                    "divider",
                    "context",
                ]

                # Validate text blocks
                if "text" in block:
                    assert "type" in block["text"]
                    assert block["text"]["type"] in ["plain_text", "mrkdwn"]
                    assert "text" in block["text"]
                    assert isinstance(block["text"]["text"], str)

                # Validate action blocks
                if block["type"] == "actions":
                    assert "elements" in block
                    assert isinstance(block["elements"], list)

                    for element in block["elements"]:
                        assert "type" in element
                        assert element["type"] == "button"
                        assert "text" in element
                        assert "action_id" in element

    def test_action_id_format_consistency(self):
        """Test that action_id formats are consistent."""
        user_id = "U123456789"
        request_time = 1640995200.0

        # Test unauthorized message button
        unauthorized_blocks = AccessRequestBlocks.build_unauthorized_message(user_id)
        actions_block = next(
            block for block in unauthorized_blocks if block["type"] == "actions"
        )
        button = actions_block["elements"][0]
        assert button["action_id"] == "request_access"

        # Test notification buttons
        notification_blocks = AccessRequestBlocks.build_access_request_notification(
            user_id=user_id,
            user_name="test",
            user_email="test@adobe.com",
            reason="Test reason",
            request_time=request_time,
        )

        actions_block = next(
            block for block in notification_blocks if block["type"] == "actions"
        )
        approve_button = actions_block["elements"][0]
        reject_button = actions_block["elements"][1]

        assert approve_button["action_id"] == f"approve_access_{user_id}"
        assert reject_button["action_id"] == f"reject_access_{user_id}"

        # Verify values contain user data
        assert user_id in approve_button["value"]
        assert user_id in reject_button["value"]

    def test_button_values_consistency(self):
        """Test that button values are set correctly."""
        user_id = "U123456789"
        request_time = 1640995200.0

        # Test unauthorized message button value
        unauthorized_blocks = AccessRequestBlocks.build_unauthorized_message(user_id)
        actions_block = next(
            block for block in unauthorized_blocks if block["type"] == "actions"
        )
        button = actions_block["elements"][0]
        assert button["value"] == user_id

        # Test notification button values
        notification_blocks = AccessRequestBlocks.build_access_request_notification(
            user_id=user_id,
            user_name="test",
            user_email="test@adobe.com",
            reason="Test reason",
            request_time=request_time,
        )

        actions_block = next(
            block for block in notification_blocks if block["type"] == "actions"
        )
        approve_button = actions_block["elements"][0]
        reject_button = actions_block["elements"][1]

        expected_value = f"{user_id}|{request_time}"
        assert approve_button["value"] == expected_value
        assert reject_button["value"] == expected_value

    def test_timestamp_formatting(self):
        """Test that timestamps are formatted correctly in blocks."""
        user_id = "U123456789"
        request_time = 1640956245.0  # 2022-01-01 12:30:45 UTC as epoch

        with patch(
            "packages.slack.blockkits.handlers.access_request_blocks.convert_timestamp_to_utc"
        ) as mock_convert:
            mock_convert.return_value = "12:30:45, 01-Jan-2022"

            blocks = AccessRequestBlocks.build_access_request_notification(
                user_id=user_id,
                user_name="test",
                user_email="test@adobe.com",
                reason="Test reason",
                request_time=request_time,
            )

            # Verify timestamp conversion was called with the epoch time
            mock_convert.assert_called_once_with(request_time)

            # Verify formatted timestamp appears in blocks
            timestamp_found = any(
                "12:30:45, 01-Jan-2022" in str(block) for block in blocks
            )
            assert timestamp_found
