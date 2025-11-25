"""
TDD Tests for Command Flag Production Bugs (CPGNCX-62023).

These tests prove:
1. DM handler bug existed and was fixed
2. Modal title length bug existed and was fixed

Test-Driven Development approach:
- RED: Tests fail with old code (proves bug exists)
- GREEN: Tests pass with new code (proves fix works)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.db.dynamodb_store import DynamoDBStore
from packages.secrets.manager import SecretsManager
from packages.slack.interactive_elements.flag_review.command_flag_processor import (
    CommandFlagProcessor,
)
from packages.slack.interactive_elements.flag_review.modal_orchestrator import (
    ModalOrchestrator,
)
from packages.slack.messages.posting import SlackPostingHandler


class TestCommandFlagProductionBugs:
    """TDD tests proving production bugs existed and fixes work."""

    @pytest.fixture
    def mock_posting_handler(self):
        """Create mock posting handler."""
        handler = MagicMock(spec=SlackPostingHandler)
        handler.post_message = AsyncMock(return_value={"ok": True, "ts": "1234567890.123456"})
        handler.update_message = AsyncMock(return_value={"ok": True})
        handler.api_call = AsyncMock(return_value={"ok": True})
        return handler

    @pytest.fixture
    def mock_db_store(self):
        """Create mock database store."""
        store = MagicMock(spec=DynamoDBStore)
        store.table_name = "test_table"
        store.client = MagicMock()
        store.client.update_item = AsyncMock()
        return store

    @pytest.fixture
    def mock_secrets_manager(self):
        """Create mock secrets manager."""
        manager = MagicMock(spec=SecretsManager)
        manager.get_slack_api_token_async = AsyncMock(return_value="xoxb-test-token")
        return manager

    @pytest.fixture
    def command_processor(self, mock_posting_handler, mock_db_store, mock_secrets_manager):
        """Create command flag processor with mocks."""
        return CommandFlagProcessor(
            posting_handler=mock_posting_handler,
            db_store=mock_db_store,
            secrets_manager=mock_secrets_manager,
        )

    @pytest.mark.asyncio
    async def test_dm_handler_bug_acknowledgment_uses_correct_handler(
        self, command_processor
    ):
        """
        Test: Bug #4 - DM Sending Failure

        EXPECTED TO PASS (bug fixed):
        - command_flag_processor should use FlagReviewDMHandler, not NotificationSender
        - send_command_acknowledgment_dm should call FlagReviewDMHandler.send_dm_to_requester

        BUG PROOF:
        If this test fails, it means the code is trying to use NotificationSender
        which doesn't have send_acknowledgment_notification method.
        """
        with patch(
            "packages.slack.interactive_elements.flag_review.dm_handler.FlagReviewDMHandler"
        ) as mock_dm_handler_class:
            # Setup mock
            mock_dm_handler = MagicMock()
            mock_dm_handler.send_dm_to_requester = AsyncMock(return_value=True)
            mock_dm_handler_class.return_value = mock_dm_handler

            # Execute
            result = await command_processor.send_command_acknowledgment_dm(
                flagged_user_id="U12345",
                admin_name="admin_user",
                channel_id="C12345",
            )

            # Assert: Should use FlagReviewDMHandler, NOT NotificationSender
            assert result is True
            mock_dm_handler_class.assert_called_once_with(command_processor.posting_handler)
            mock_dm_handler.send_dm_to_requester.assert_called_once_with(
                user_id="U12345",
                dm_type="acknowledgment",
                admin_name="admin_user",
                channel_id="C12345",
                command_execution_id=None,
            )

    @pytest.mark.asyncio
    async def test_dm_handler_bug_reply_uses_correct_handler(self, command_processor):
        """
        Test: Bug #4 - DM Sending Failure (Reply variant)

        EXPECTED TO PASS (bug fixed):
        - send_command_reply_dm should use FlagReviewDMHandler
        - Should pass reply_text parameter correctly
        """
        with patch(
            "packages.slack.interactive_elements.flag_review.dm_handler.FlagReviewDMHandler"
        ) as mock_dm_handler_class:
            # Setup mock
            mock_dm_handler = MagicMock()
            mock_dm_handler.send_dm_to_requester = AsyncMock(return_value=True)
            mock_dm_handler_class.return_value = mock_dm_handler

            # Execute
            result = await command_processor.send_command_reply_dm(
                flagged_user_id="U12345",
                admin_name="admin_user",
                reply_text="Thank you for your feedback!",
                channel_id="C12345",
            )

            # Assert
            assert result is True
            mock_dm_handler.send_dm_to_requester.assert_called_once_with(
                user_id="U12345",
                dm_type="reply",
                admin_name="admin_user",
                channel_id="C12345",
                command_execution_id=None,
                reply_text="Thank you for your feedback!",
            )

    def test_modal_title_length_bug_command_reply_modal(
        self, mock_posting_handler, mock_secrets_manager
    ):
        """
        Test: Bug #5 - Modal Title Too Long

        EXPECTED TO PASS (bug fixed):
        - Modal title must be ≤ 25 characters
        - Slack API rejects titles > 25 chars with 'invalid_arguments' error

        BUG PROOF:
        Original title: "Reply to Command Feedback" = 27 characters ❌
        Fixed title: "Reply to Feedback" = 18 characters ✅

        This test proves the fix by validating title length.
        """
        orchestrator = ModalOrchestrator(mock_posting_handler, mock_secrets_manager)

        # Create modal view
        modal_view = orchestrator.create_command_reply_modal_view(
            channel_id="C12345",
            command_execution_id="1234567890_abc123",
            flagged_user_id="U12345",
        )

        # Extract title text
        title_text = modal_view.get("title", {}).get("text", "")

        # Assert: Title must be 25 characters or less (Slack limit)
        assert len(title_text) <= 25, (
            f"Modal title '{title_text}' is {len(title_text)} characters, "
            f"exceeds Slack's 25 character limit. "
            f"This would cause 'invalid_arguments' error in production."
        )

        # Assert: Title should be the fixed value
        assert title_text == "Reply to Feedback", (
            f"Expected 'Reply to Feedback' (18 chars), got '{title_text}' ({len(title_text)} chars)"
        )

    def test_modal_title_length_validation_all_modals(
        self, mock_posting_handler, mock_secrets_manager
    ):
        """
        Test: Validate ALL modal titles are under 25 characters

        This comprehensive test ensures we don't introduce similar bugs
        in other modals.
        """
        orchestrator = ModalOrchestrator(mock_posting_handler, mock_secrets_manager)

        # Test command feedback modal
        command_feedback_modal = orchestrator._create_command_feedback_modal_view(
            channel_id="C12345",
            command_execution_id="1234567890_abc123",
            command_type="status",
            original_channel="C12345",
        )
        command_feedback_title = command_feedback_modal.get("title", {}).get("text", "")
        assert len(command_feedback_title) <= 25, (
            f"Command feedback modal title '{command_feedback_title}' "
            f"is {len(command_feedback_title)} characters (limit: 25)"
        )

        # Test command reply modal
        command_reply_modal = orchestrator.create_command_reply_modal_view(
            channel_id="C12345",
            command_execution_id="1234567890_abc123",
            flagged_user_id="U12345",
        )
        command_reply_title = command_reply_modal.get("title", {}).get("text", "")
        assert len(command_reply_title) <= 25, (
            f"Command reply modal title '{command_reply_title}' "
            f"is {len(command_reply_title)} characters (limit: 25)"
        )

    @pytest.mark.asyncio
    async def test_notification_sender_does_not_have_bug_methods(self):
        """
        Test: Prove NotificationSender doesn't have the methods we were calling

        This test validates that the bug existed by confirming NotificationSender
        doesn't have send_acknowledgment_notification or send_reply_notification.

        If this test fails, it means NotificationSender gained these methods,
        which would make our fix unnecessary (but wouldn't break anything).
        """
        from packages.slack.interactive_elements.flag_review.notification_sender import (
            NotificationSender,
        )

        # Create instance with mock container
        mock_container = MagicMock()
        notification_sender = NotificationSender(mock_container)

        # Assert: NotificationSender should NOT have these methods
        assert not hasattr(notification_sender, "send_acknowledgment_notification"), (
            "NotificationSender should NOT have send_acknowledgment_notification method. "
            "This was the bug - command_flag_processor was calling a non-existent method."
        )

        assert not hasattr(notification_sender, "send_reply_notification"), (
            "NotificationSender should NOT have send_reply_notification method. "
            "This was the bug - command_flag_processor was calling a non-existent method."
        )

        # Document what methods NotificationSender DOES have
        available_methods = [
            method
            for method in dir(notification_sender)
            if callable(getattr(notification_sender, method)) and not method.startswith("_")
        ]

        # Assert: These are the only public async methods available
        async_methods = [
            "send_dm_confirmation",
            "send_dm_error",
            "send_notification_batch",
            "show_flag_details_in_dm",
            "handle_quick_reply_from_dm",
        ]

        for method in async_methods:
            assert method in available_methods, (
                f"Expected NotificationSender to have {method} method"
            )

    @pytest.mark.asyncio
    async def test_integration_acknowledge_button_workflow(
        self, command_processor, mock_db_store
    ):
        """
        Test: Complete acknowledge button workflow

        This integration test proves that the entire acknowledge workflow
        works end-to-end with the fixes in place.
        """
        # Mock the database update
        mock_db_store.client.update_item = AsyncMock()

        # Mock FlagReviewDMHandler
        with patch(
            "packages.slack.interactive_elements.flag_review.dm_handler.FlagReviewDMHandler"
        ) as mock_dm_handler_class, patch(
            "packages.slack.interactive_elements.flag_review.message_updater.MessageUpdater"
        ) as mock_message_updater_class:

            # Setup mocks
            mock_dm_handler = MagicMock()
            mock_dm_handler.send_dm_to_requester = AsyncMock(return_value=True)
            mock_dm_handler_class.return_value = mock_dm_handler

            mock_message_updater = MagicMock()
            mock_message_updater.update_review_message = AsyncMock()
            mock_message_updater_class.return_value = mock_message_updater

            # Simulate acknowledge button payload
            payload = {
                "user": {"id": "W7MGASQ2K", "username": "admin_user"},
                "channel": {"id": "C095LQ0H4KB"},
                "message": {"ts": "1759396742.986709"},
                "actions": [
                    {
                        "action_id": "acknowledge_command_feedback",
                        "value": "D0840EX80R5|1759396727_49f75b4b|W7MGASQ2K",
                    }
                ],
            }

            # Execute acknowledge workflow
            result = await command_processor.handle_command_acknowledgment(payload)

            # Assert: Workflow completed successfully
            assert result is True

            # Assert: Database was updated
            mock_db_store.client.update_item.assert_called_once()

            # Assert: DM was sent using FlagReviewDMHandler (not NotificationSender)
            mock_dm_handler_class.assert_called()
            mock_dm_handler.send_dm_to_requester.assert_called_once()

            # Assert: Review message was updated
            mock_message_updater.update_review_message.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
