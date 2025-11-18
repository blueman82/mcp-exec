#!/usr/bin/env python3
"""
Integration tests for method visibility and naming consistency.

Tests that would have caught production bug #1:
- Method name mismatches (_validate_trigger_id vs validate_trigger_id)
- Private vs public method visibility issues
"""

import inspect
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestMethodVisibility:
    """Test suite for method visibility and naming consistency."""

    @pytest.fixture
    def handler(self):
        """Create a FlagReviewHandler with minimal mocks."""
        from packages.slack.interactive_elements.flag_review_handler import FlagReviewHandler

        posting_handler = Mock()
        posting_handler.post_message = AsyncMock(return_value={"ok": True})
        posting_handler.post_ephemeral_message = AsyncMock(return_value={"ok": True})

        db_store = Mock()
        db_store.client = AsyncMock()
        db_store.client.put_item = AsyncMock(return_value={})
        db_store.table_name = "test_table"

        secrets_manager = Mock()
        secrets_manager.get_slack_api_token_async = AsyncMock(return_value="test-token")

        return FlagReviewHandler(posting_handler, db_store, secrets_manager)

    @pytest.mark.asyncio
    async def test_modal_orchestrator_method_visibility(self, handler):
        """Test that modal orchestrator methods have correct visibility.

        This test would have caught the bug where modules were calling
        public methods that should have been private.
        """
        modal = handler.modal_orchestrator

        # These private methods MUST exist
        assert hasattr(modal, '_validate_trigger_id'), "Missing _validate_trigger_id (private)"
        assert hasattr(modal, '_display_modal_via_api'), "Missing _display_modal_via_api (private)"
        assert hasattr(modal, '_create_command_feedback_modal_view'), "Missing _create_command_feedback_modal_view"
        assert hasattr(modal, '_make_modal_api_request'), "Missing _make_modal_api_request"

        # These public versions should NOT exist (the bug)
        assert not hasattr(modal, 'validate_trigger_id'), "Public validate_trigger_id should not exist"
        assert not hasattr(modal, 'display_modal_via_api'), "Public display_modal_via_api should not exist"

    @pytest.mark.asyncio
    async def test_status_processor_calls_private_methods(self):
        """Test that status processor calls modal methods with correct visibility."""
        from packages.slack.interactive_elements.flag_review.status_flag_processor import StatusFlagProcessor

        # Check the source code for incorrect method calls
        source = inspect.getsource(StatusFlagProcessor)

        # These incorrect calls should NOT exist
        if 'modal_orchestrator.validate_trigger_id' in source:
            pytest.fail("StatusFlagProcessor calls public validate_trigger_id (should be _validate_trigger_id)")
        if 'modal_orchestrator.display_modal_via_api' in source:
            pytest.fail("StatusFlagProcessor calls public display_modal_via_api (should be _display_modal_via_api)")

        # Verify correct calls exist (optional - may not be directly visible)
        # This is more about ensuring the wrong pattern doesn't exist

    @pytest.mark.asyncio
    async def test_admin_processor_method_visibility(self, handler):
        """Test that admin processor methods have correct visibility."""
        admin = handler.admin_action_processor

        # Public methods that should exist
        assert hasattr(admin, 'handle_acknowledgment'), "Missing public handle_acknowledgment"
        assert hasattr(admin, 'handle_reply_button_click'), "Missing public handle_reply_button_click"
        assert hasattr(admin, 'handle_reply_submission'), "Missing public handle_reply_submission"

        # Check that these are actually callable
        assert callable(admin.handle_acknowledgment)
        assert callable(admin.handle_reply_button_click)
        assert callable(admin.handle_reply_submission)

    @pytest.mark.asyncio
    async def test_cross_module_private_method_calls(self, handler):
        """Test that modules correctly call each other's private methods."""
        # Mock the internal API call
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"ok": True})
            mock_session.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aexit__ = AsyncMock()

            # This payload triggers a cross-module call
            payload = {
                "type": "block_actions",
                "trigger_id": "trigger_" + "x" * 30,  # Valid trigger ID
                "user": {"id": "U123", "username": "test"},
                "channel": {"id": "D123"},
                "actions": [{
                    "action_id": "flag_status_review",
                    "value": "D123|1234567890.123456|cmd_123"
                }]
            }

            # This should work if methods are called correctly
            result = await handler.process_flag_action(payload)
            assert result is True, "Cross-module private method call failed"

    @pytest.mark.asyncio
    async def test_production_bug1_scenario(self, handler):
        """Test the exact scenario that caused bug 1 in production.

        Bug: StatusFlagProcessor called modal_orchestrator.validate_trigger_id()
        instead of modal_orchestrator._validate_trigger_id()
        """
        modal = handler.modal_orchestrator

        # This should NOT work (the bug)
        with pytest.raises(AttributeError):
            modal.validate_trigger_id("test")

        # This SHOULD work (the fix)
        result = modal._validate_trigger_id("test_trigger_123456789012345678901234567890")
        assert result is True

        # Test invalid trigger ID
        result = modal._validate_trigger_id("short")
        assert result is False

    @pytest.mark.asyncio
    async def test_all_processors_initialized(self, handler):
        """Test that all processor modules are properly initialized."""
        # All processors should be initialized
        assert hasattr(handler, 'status_flag_processor')
        assert hasattr(handler, 'command_flag_processor')
        assert hasattr(handler, 'admin_action_processor')
        assert hasattr(handler, 'modal_orchestrator')
        assert hasattr(handler, 'validators')

        # Each should be an instance, not None
        assert handler.status_flag_processor is not None
        assert handler.command_flag_processor is not None
        assert handler.admin_action_processor is not None
        assert handler.modal_orchestrator is not None
        assert handler.validators is not None

    @pytest.mark.asyncio
    async def test_validator_method_visibility(self, handler):
        """Test that validator methods have correct visibility."""
        validators = handler.validators

        # Public methods that should exist
        assert hasattr(validators, 'check_rate_limit'), "Missing public check_rate_limit"
        assert callable(validators.check_rate_limit)

        # Test rate limiting works
        user_id = "U123"
        result = validators.check_rate_limit(user_id)
        assert isinstance(result, bool), "check_rate_limit should return boolean"