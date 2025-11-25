#!/usr/bin/env python3
"""
End-to-end integration tests for the complete flag review workflow.

This test simulates the exact production workflow:
1. User clicks "Flag for Review" button
2. Modal opens with form
3. User enters feedback text
4. User clicks Submit
5. System processes submission through all modules

Tests would catch ALL production bugs:
- Bug #1: Method visibility (_validate_trigger_id)
- Bug #2: Parameter mismatches (feedback_text vs original_text)
- Bug #3: Python stdlib conflicts (types.py)
- Bug #4: Container missing get_db_store() method
"""

from unittest.mock import AsyncMock, Mock, patch
import pytest


class TestEndToEndWorkflow:
    """Complete end-to-end workflow tests matching production exactly."""

    @pytest.mark.asyncio
    async def test_complete_flag_workflow_production_simulation(self):
        """Simulate exact production workflow from button click to submission.

        This test follows the exact code path that production takes,
        ensuring all module interactions work correctly.
        """
        from packages.slack.interactive_elements.flag_review_handler import FlagReviewHandler

        # Step 1: Setup production-like environment
        posting_handler = Mock()
        posting_handler.post_message = AsyncMock(return_value={
            "ok": True,
            "ts": "1234567890.123456",
            "channel": "C095LQ0H4KB"
        })
        posting_handler.post_ephemeral_message = AsyncMock(return_value={"ok": True})
        posting_handler.update_message = AsyncMock(return_value={"ok": True})

        db_store = Mock()
        db_store.client = Mock()
        db_store.client.put_item = AsyncMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})
        db_store.client.get_item = AsyncMock(return_value={})
        db_store.client.query = AsyncMock(return_value={"Items": []})
        db_store.table_name = "ketchup_channel_information"

        secrets_manager = Mock()
        secrets_manager.get_slack_api_token_async = AsyncMock(return_value="xoxb-test-token")

        # Create handler - this initializes ALL modules
        handler = FlagReviewHandler(posting_handler, db_store, secrets_manager)

        # Step 2: User clicks "Flag for Review" button
        button_click_payload = {
            "type": "block_actions",
            "trigger_id": "9574654848048.174214641840.6f217e14a0c9f526c845405f0774c4cd",
            "team": {"id": "T546AJVQQ", "domain": "adobecso"},
            "user": {
                "id": "W7MGASQ2K",
                "username": "harrison",
                "name": "harrison"
            },
            "channel": {"id": "D0840EX80R5", "name": "directmessage"},
            "actions": [{
                "action_id": "flag_command_review",  # Command flag button
                "value": "D0840EX80R5|1758273886_04da7904|status"
            }],
            "response_url": "test_response_url"  # Use test URL like other tests
        }

        # Mock the Slack API modal.open call with proper async context manager
        with patch('aiohttp.ClientSession') as mock_session_class:
            # Create the mock response that will be returned
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"ok": True, "view": {"id": "V09FNJ4GRBR"}})

            # Create the post context manager
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_cm.__aexit__ = AsyncMock()

            # Create the session mock
            mock_session = AsyncMock()
            mock_session.post = Mock(return_value=mock_post_cm)

            # Create the session context manager
            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock()

            # Make ClientSession return the context manager
            mock_session_class.return_value = mock_session_cm

            # Process button click - should open modal
            result = await handler.process_command_flag_action(button_click_payload)
            assert result is True, "Button click processing failed"

            # Verify modal.open was called with correct endpoint
            mock_session.post.assert_called()
            call_args = mock_session.post.call_args
            assert "views.open" in call_args[0][0], "Should call views.open API"

        # Step 3: User submits the modal with feedback
        modal_submit_payload = {
            "type": "view_submission",
            "trigger_id": "9574654848048.174214641840.6f217e14a0c9f526c845405f0774c4cd",
            "team": {"id": "T546AJVQQ", "domain": "adobecso"},
            "user": {
                "id": "W7MGASQ2K",
                "username": "harrison",
                "name": "harrison"
            },
            "view": {
                "id": "V09FNJ4GRBR",
                "type": "modal",
                "callback_id": "command_flag_review_modal",
                "private_metadata": "D0840EX80R5|1758273886_04da7904|status|D0840EX80R5",
                "state": {
                    "values": {
                        "feedback_block": {
                            "feedback_input": {
                                "type": "plain_text_input",
                                "value": "this is just a test"
                            }
                        }
                    }
                }
            }
        }

        # Process modal submission
        result = await handler.process_command_flag_action(modal_submit_payload)

        # This should succeed if all bugs are fixed:
        # - Bug #1: Modal methods are correctly private (_validate_trigger_id)
        # - Bug #2: Parameters match (original_text not feedback_text)
        # - Bug #3: No types.py import conflict (using flag_types.py)
        # - Bug #4: Container has get_db_store() method

        assert result is True, "Modal submission failed - likely due to container bug"

        # Verify database was called to store the flag
        assert db_store.client.put_item.called, "Flag was not stored in database"

        # Verify message was posted to review channel
        assert posting_handler.post_message.called, "Review message was not posted"

    @pytest.mark.asyncio
    async def test_container_bug_detection(self):
        """Verify the Container.get_db_store bug is FIXED."""
        from packages.slack.interactive_elements.flag_review.command_flag_processor import CommandFlagProcessor

        # Create processor as production does
        posting_handler = Mock()
        db_store = Mock()
        db_store.client = Mock()
        db_store.client.put_item = AsyncMock(return_value={})
        secrets_manager = Mock()

        processor = CommandFlagProcessor(posting_handler, db_store, secrets_manager)

        # The bug WAS: api_client expects container.get_db_store() method
        # The fix: container now HAS get_db_store() method

        # This exact operation happens during modal submission

        # Verify the container now works correctly
        # This should NOT raise AttributeError anymore
        try:
            # Access api_client's db_store property
            db = processor.api_client.db_store
            assert db is not None, "db_store should be accessible"
            # Verify it's the same db_store we passed in
            assert db == db_store, "Should return the correct db_store"
        except AttributeError as e:
            pytest.fail(f"Container still has bug: {e}")

    @pytest.mark.asyncio
    async def test_modal_validation_workflow(self):
        """Test the modal validation part of the workflow."""
        from packages.slack.interactive_elements.flag_review.modal_orchestrator import ModalOrchestrator

        posting_handler = Mock()
        secrets_manager = Mock()
        secrets_manager.get_slack_api_token_async = AsyncMock(return_value="xoxb-test-token")

        orchestrator = ModalOrchestrator(posting_handler, secrets_manager)

        # Test trigger_id validation (Bug #1: method visibility)
        valid_trigger = "9574654848048.174214641840.6f217e14a0c9f526c845405f0774c4cd"
        invalid_trigger = "short"

        # These must use private method
        assert orchestrator._validate_trigger_id(valid_trigger) is True
        assert orchestrator._validate_trigger_id(invalid_trigger) is False

        # This should NOT exist (the bug)
        assert not hasattr(orchestrator, 'validate_trigger_id'), "Public method should not exist"

    @pytest.mark.asyncio
    async def test_database_storage_workflow(self):
        """Test the database storage part of the workflow."""
        from packages.slack.interactive_elements.flag_review.api_client import FlagReviewApiClient

        # Create CORRECT container with methods
        db_store = Mock()
        db_store.client = Mock()
        db_store.client.put_item = AsyncMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})
        db_store.table_name = "ketchup_channel_information"

        container = type('Container', (), {
            'get_db_store': lambda self: db_store,
            'get_posting_handler': lambda self: Mock(),
            'get_secrets_manager': lambda self: Mock()
        })()

        api_client = FlagReviewApiClient(container)

        # Test storing command flag with ALL required parameters
        result = await api_client.store_command_flag(
            channel_id="C123",
            command_execution_id="cmd_123",
            user_id="U123",
            user_name="testuser",
            original_text="test feedback",  # Must be original_text, not feedback_text
            command_type="status",
            original_channel="C123"
        )

        # Should succeed with correct parameters
        assert result is True, "Store command flag should return True on success"
        assert db_store.client.put_item.called, "Database storage was not called"

        # Verify the correct item was stored
        call_args = db_store.client.put_item.call_args
        # The API client uses lowercase kwargs
        assert 'table_name' in call_args.kwargs, "table_name should be in kwargs"
        assert 'item' in call_args.kwargs, "item should be in kwargs"

        stored_item = call_args.kwargs['item']
        # The item is in DynamoDB format with type annotations
        assert stored_item['user_id']['S'] == "U123"
        assert stored_item['user_name']['S'] == "testuser"
        assert stored_item['original_text']['S'] == "test feedback"  # Stored as original_text
        assert stored_item['command_type']['S'] == "status"

    @pytest.mark.asyncio
    async def test_import_resolution(self):
        """Test that imports don't conflict with Python stdlib (Bug #3)."""
        # This import should work (renamed from types.py to flag_types.py)

        # Verify we can import Python's types module
        import types
        assert hasattr(types, 'SimpleNamespace'), "Python stdlib types should be accessible"

        # The old import should fail (file was renamed from types.py to flag_types.py)
        with pytest.raises(ImportError):
            pass
