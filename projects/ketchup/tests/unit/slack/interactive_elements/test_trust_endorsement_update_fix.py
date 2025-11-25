"""Test trust endorsement update logic to prevent duplicate trust lines."""

from unittest.mock import AsyncMock, Mock

import pytest

from packages.slack.interactive_elements.trust_endorsement_handler import (
    TrustEndorsementHandler,
)


class TestTrustEndorsementUpdateFix:
    """Test that trust endorsement updates existing trust display instead of appending."""

    @pytest.fixture
    def handler(self):
        """Create handler with mocked dependencies."""
        db_store = Mock()
        posting_handler = Mock()
        posting_handler.update_message = AsyncMock()
        secrets_manager = Mock()
        secrets_manager.get_slack_api_token_async = AsyncMock(
            return_value="xoxb-test-token"
        )

        return TrustEndorsementHandler(
            db_store=db_store,
            posting_handler=posting_handler,
            secrets_manager=secrets_manager,
        )

    @pytest.mark.asyncio
    async def test_update_existing_trust_display(self, handler):
        """Test that existing trust display is updated, not duplicated."""
        # Mock message blocks with existing trust display
        existing_blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Status update content here"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "✓ Trusted by: <@U123>"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✓ Trust this summary"},
                        "action_id": "trust_status_update",
                    }
                ],
            },
        ]

        # Update with new trust display
        new_trust_display = "✓ Trusted by: <@U123>, <@U456>"

        await handler._update_message_with_trust(
            channel_id="C123",
            message_ts="123.456",
            message_blocks=existing_blocks,
            trust_display=new_trust_display,
            show_button=True,
        )

        # Verify the update was called
        handler.posting_handler.update_message.assert_called_once()

        # Get the updated blocks
        call_args = handler.posting_handler.update_message.call_args
        updated_blocks = call_args.kwargs["blocks"]

        # Verify structure
        assert len(updated_blocks) == 3  # Content, trust display, actions

        # Verify only one trust display block exists
        trust_blocks = [
            b
            for b in updated_blocks
            if b.get("type") == "section"
            and "✓ Trusted by:" in b.get("text", {}).get("text", "")
        ]
        assert len(trust_blocks) == 1

        # Verify it has the updated content
        assert trust_blocks[0]["text"]["text"] == new_trust_display

    @pytest.mark.asyncio
    async def test_add_trust_display_when_none_exists(self, handler):
        """Test that trust display is added when it doesn't exist."""
        # Mock message blocks without trust display
        existing_blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Status update content here"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✓ Trust this summary"},
                        "action_id": "trust_status_update",
                    }
                ],
            },
        ]

        # Add trust display
        trust_display = "✓ Trusted by: <@U123>"

        await handler._update_message_with_trust(
            channel_id="C123",
            message_ts="123.456",
            message_blocks=existing_blocks,
            trust_display=trust_display,
            show_button=True,
        )

        # Get the updated blocks
        call_args = handler.posting_handler.update_message.call_args
        updated_blocks = call_args.kwargs["blocks"]

        # Verify structure
        assert len(updated_blocks) == 3  # Content, trust display, actions

        # Verify trust display was added before actions
        assert updated_blocks[1]["type"] == "section"
        assert updated_blocks[1]["text"]["text"] == trust_display
        assert updated_blocks[2]["type"] == "actions"

    @pytest.mark.asyncio
    async def test_preserve_other_block_types(self, handler):
        """Test that other block types like dividers are preserved."""
        # Mock message blocks with divider
        existing_blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Status update content here"},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "✓ Trusted by: <@U123>"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✓ Trust this summary"},
                        "action_id": "trust_status_update",
                    }
                ],
            },
        ]

        # Update trust display
        new_trust_display = "✓ Trusted by: <@U123>, <@U456>"

        await handler._update_message_with_trust(
            channel_id="C123",
            message_ts="123.456",
            message_blocks=existing_blocks,
            trust_display=new_trust_display,
            show_button=True,
        )

        # Get the updated blocks
        call_args = handler.posting_handler.update_message.call_args
        updated_blocks = call_args.kwargs["blocks"]

        # Verify divider is preserved
        assert any(b.get("type") == "divider" for b in updated_blocks)

        # Verify only one trust display
        trust_blocks = [
            b
            for b in updated_blocks
            if b.get("type") == "section"
            and "✓ Trusted by:" in b.get("text", {}).get("text", "")
        ]
        assert len(trust_blocks) == 1
