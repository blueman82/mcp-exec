"""
Test access request Block Kit UI components.
"""

from unittest.mock import patch

import pytest

from packages.core.constants import KETCHUP_WIKI_URL
from packages.slack.blockkits.handlers.access_request_blocks import AccessRequestBlocks


class TestAccessRequestBlocks:
    """Test AccessRequestBlocks class."""

    @pytest.fixture
    def blocks_builder(self):
        """Create AccessRequestBlocks instance."""
        return AccessRequestBlocks()

    def test_build_unauthorized_message_with_button(self, blocks_builder):
        """Test building unauthorized message with request button."""
        user_id = "U123456"
        blocks = blocks_builder.build_unauthorized_message(
            user_id=user_id, show_request_button=True
        )

        # Check header
        assert blocks[0]["type"] == "header"
        assert blocks[0]["text"]["text"] == "🔒 Access Required"

        # Check message
        assert blocks[1]["type"] == "section"
        assert (
            "don't currently have access to Ketchup commands"
            in blocks[1]["text"]["text"]
        )

        # Find the actions block
        actions_block = None
        for block in blocks:
            if block["type"] == "actions":
                actions_block = block
                break

        assert actions_block is not None
        assert len(actions_block["elements"]) == 1

        # Check button
        button = actions_block["elements"][0]
        assert button["type"] == "button"
        assert button["text"]["text"] == "Request Access"
        assert button["action_id"] == "request_access"
        assert button["style"] == "primary"
        assert button["value"] == user_id

    def test_build_unauthorized_message_without_button(self, blocks_builder):
        """Test building unauthorized message without request button."""
        blocks = blocks_builder.build_unauthorized_message(
            user_id="U123456", show_request_button=False
        )

        # Should have fallback email message
        email_section = None
        for block in blocks:
            if block.get("type") == "section" and "email" in block.get("text", {}).get(
                "text", ""
            ):
                email_section = block
                break

        assert email_section is not None
        assert "org-omeara-all@adobe.com" in email_section["text"]["text"]

    def test_build_unauthorized_message_with_rate_limit(self, blocks_builder):
        """Test building unauthorized message with rate limit message."""
        rate_limit_msg = "You can request access again in 30 minutes"
        blocks = blocks_builder.build_unauthorized_message(
            user_id="U123456",
            show_request_button=False,
            rate_limit_message=rate_limit_msg,
        )

        # Find rate limit section
        rate_limit_section = None
        for block in blocks:
            if block.get("type") == "section" and "Rate Limit" in block.get(
                "text", {}
            ).get("text", ""):
                rate_limit_section = block
                break

        assert rate_limit_section is not None
        assert rate_limit_msg in rate_limit_section["text"]["text"]

    @patch(
        "packages.slack.blockkits.handlers.access_request_blocks.convert_timestamp_to_utc"
    )
    def test_build_access_request_notification(self, mock_convert_time, blocks_builder):
        """Test building access request notification for approvers."""
        mock_convert_time.return_value = "2024-01-15 10:30:00 UTC"

        blocks = blocks_builder.build_access_request_notification(
            user_id="U123456",
            user_name="testuser",
            user_email="test@example.com",
            reason="Need access for incident response",
            request_time=1234567890.0,
        )

        # Check header
        assert blocks[0]["type"] == "header"
        assert blocks[0]["text"]["text"] == "🔐 New Access Request"

        # Check user info section
        fields_section = blocks[1]
        assert fields_section["type"] == "section"
        assert len(fields_section["fields"]) == 4

        # Check fields contain correct info
        field_texts = [field["text"] for field in fields_section["fields"]]
        assert any("<@U123456>" in text for text in field_texts)
        assert any("testuser" in text for text in field_texts)
        assert any("test@example.com" in text for text in field_texts)
        # Check that mock was called
        mock_convert_time.assert_called_once_with(1234567890.0)

        # Check reason section exists
        reason_section = blocks[2]
        assert reason_section["type"] == "section"
        assert "Need access for incident response" in reason_section["text"]["text"]

        # Find actions block
        actions_block = None
        for block in blocks:
            if block["type"] == "actions":
                actions_block = block
                break

        assert actions_block is not None
        assert len(actions_block["elements"]) == 2

        # Check approve button
        approve_btn = actions_block["elements"][0]
        assert approve_btn["text"]["text"] == "✅ Approve"
        assert approve_btn["action_id"] == "approve_access_U123456"
        assert approve_btn["style"] == "primary"
        assert approve_btn["value"] == "U123456|1234567890.0"

        # Check reject button
        reject_btn = actions_block["elements"][1]
        assert reject_btn["text"]["text"] == "❌ Reject"
        assert reject_btn["action_id"] == "reject_access_U123456"
        assert reject_btn["style"] == "danger"
        assert reject_btn["value"] == "U123456|1234567890.0"

    @patch(
        "packages.slack.blockkits.handlers.access_request_blocks.convert_timestamp_to_utc"
    )
    def test_build_request_processed_blocks_approved(
        self, mock_convert_time, blocks_builder
    ):
        """Test building processed request blocks for approval."""
        mock_convert_time.return_value = "2024-01-15 11:00:00 UTC"

        original_blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Header"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "User info"}},
        ]

        updated_blocks = blocks_builder.build_request_processed_blocks(
            original_blocks=original_blocks,
            processed_by="U789",
            decision="approved",
            decision_time=1234568890.0,
        )

        # Should keep first two blocks
        assert len(updated_blocks) == 3
        assert updated_blocks[0] == original_blocks[0]
        assert updated_blocks[1] == original_blocks[1]

        # Check decision block
        decision_block = updated_blocks[2]
        assert decision_block["type"] == "section"
        assert "✅ *Approved by* <@U789>" in decision_block["text"]["text"]
        # Check that mock was called
        mock_convert_time.assert_called_once_with(1234568890.0)

    @patch(
        "packages.slack.blockkits.handlers.access_request_blocks.convert_timestamp_to_utc"
    )
    def test_build_request_processed_blocks_rejected(
        self, mock_convert_time, blocks_builder
    ):
        """Test building processed request blocks for rejection."""
        mock_convert_time.return_value = "2024-01-15 11:00:00 UTC"

        original_blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Header"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "User info"}},
        ]

        updated_blocks = blocks_builder.build_request_processed_blocks(
            original_blocks=original_blocks,
            processed_by="U789",
            decision="rejected",
            decision_time=1234568890.0,
            rejection_reason="Account not verified",
        )

        # Check decision block
        decision_block = updated_blocks[2]
        assert decision_block["type"] == "section"
        assert "❌ *Rejected by* <@U789>" in decision_block["text"]["text"]
        assert "Account not verified" in decision_block["text"]["text"]

    def test_build_approval_dm(self, blocks_builder):
        """Test building approval DM message."""
        blocks = blocks_builder.build_approval_dm("U123456")

        # Check welcome message
        assert blocks[0]["type"] == "section"
        assert "Welcome to Ketchup 1.0!" in blocks[0]["text"]["text"]
        assert "<@U123456>" in blocks[0]["text"]["text"]

        # Check that key sections exist
        section_texts = [
            block.get("text", {}).get("text", "")
            for block in blocks
            if block["type"] == "section"
        ]

        # Should have info about Ketchup
        assert any("AI-Powered CSO Assistant" in text for text in section_texts)

        # Should have caveats
        assert any(
            "Caveats:" in text
            and "should not be shared directly with customers" in text
            for text in section_texts
        )

        # Should have commands
        assert any("/ketchup status" in text for text in section_texts)
        # Analyze command was removed - skip this assertion

        # Should have contact information
        assert any("Questions? Contact the team!" in text for text in section_texts)
        assert any("ketchup_feedback" in text for text in section_texts)

    def test_build_rejection_modal(self, blocks_builder):
        """Test building rejection reason modal."""
        modal = blocks_builder.build_rejection_modal()

        assert modal["type"] == "modal"
        assert modal["callback_id"] == "reject_reason_modal"
        assert modal["title"]["text"] == "Rejection Reason"
        assert modal["submit"]["text"] == "Submit"

        # Check input block
        assert len(modal["blocks"]) == 1
        input_block = modal["blocks"][0]
        assert input_block["type"] == "input"
        assert input_block["block_id"] == "reason_block"

        # Check text input element
        element = input_block["element"]
        assert element["type"] == "plain_text_input"
        assert element["action_id"] == "reason_input"
        assert element["multiline"] is True
