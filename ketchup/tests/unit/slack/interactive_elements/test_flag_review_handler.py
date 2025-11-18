"""
Unit tests for FlagReviewHandler orchestrator.

Tests only the public interface and orchestration logic.
Individual module tests are in separate files.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from packages.slack.interactive_elements.flag_review_handler import FlagReviewHandler


class TestFlagReviewHandlerOrchestrator:
    """Test suite for FlagReviewHandler orchestrator."""

    @pytest.fixture
    def mock_posting_handler(self):
        """Create a mock posting handler."""
        mock = Mock()
        mock.post_message = AsyncMock(
            return_value={"ok": True, "ts": "1234567890.123456"}
        )
        mock.post_ephemeral_message = AsyncMock(return_value={"ok": True})
        mock.update_message = AsyncMock(return_value={"ok": True})
        mock.open_modal = AsyncMock(return_value={"ok": True})
        return mock

    @pytest.fixture
    def mock_db_store(self):
        """Create a mock database store."""
        mock = Mock()
        mock.client = Mock()
        mock.client.put_item = AsyncMock(return_value={"ResponseMetadata": {}})
        mock.client.get_item = AsyncMock(return_value={"Item": {}})
        mock.client.query = AsyncMock(return_value={"Items": []})
        return mock

    @pytest.fixture
    def mock_secrets_manager(self):
        """Create a mock secrets manager."""
        mock = Mock()
        mock.get_slack_api_token_async = AsyncMock(return_value="test-token")
        return mock

    @pytest.fixture
    def handler(self, mock_posting_handler, mock_db_store, mock_secrets_manager):
        """Create handler with mocked dependencies."""
        return FlagReviewHandler(
            mock_posting_handler, mock_db_store, mock_secrets_manager
        )

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, handler):
        """Test that orchestrator initializes all sub-modules."""
        # Verify new modular processors are initialized
        assert hasattr(handler, "status_flag_processor")
        assert hasattr(handler, "command_flag_processor")
        assert hasattr(handler, "admin_action_processor")
        assert hasattr(handler, "modal_orchestrator")
        assert hasattr(handler, "validators")
        assert hasattr(handler, "database")  # Backward compatibility

    @pytest.mark.asyncio
    async def test_process_flag_action_success(self, handler):
        """Test successful flag action processing."""
        payload = {
            "type": "block_actions",
            "user": {"id": "U123", "username": "testuser"},
            "actions": [
                {
                    "action_id": "flag_status_review",
                    "value": "C123|1234567890.123456|123456_abc",
                }
            ],
            "trigger_id": "trigger_123",
        }

        # Mock the new modular processors
        handler.validators.check_rate_limit = Mock(return_value=True)
        handler.status_flag_processor.handle_flag_button_click = AsyncMock(return_value=True)

        result = await handler.process_flag_action(payload)

        assert result is True
        handler.validators.check_rate_limit.assert_called_once_with("U123")
        handler.status_flag_processor.handle_flag_button_click.assert_called_once_with(payload)

    @pytest.mark.asyncio
    async def test_process_flag_action_already_flagged(self, handler):
        """Test flag action when already flagged."""
        payload = {
            "type": "block_actions",
            "trigger_id": "trigger_123456",
            "user": {"id": "U123", "username": "testuser"},
            "actions": [
                {
                    "action_id": "flag_status_review",
                    "value": "C123|1234567890.123456|123456_abc",
                }
            ],
        }

        # Mock the status flag processor to return False for already flagged
        handler.validators.check_rate_limit = Mock(return_value=True)
        handler.status_flag_processor.handle_flag_button_click = AsyncMock(
            return_value=False  # Return False when already flagged
        )

        result = await handler.process_flag_action(payload)

        assert result is False  # Should return False when already flagged
        handler.status_flag_processor.handle_flag_button_click.assert_called_once_with(
            payload
        )

    @pytest.mark.asyncio
    async def test_process_flag_action_rate_limited(self, handler):
        """Test flag action when rate limited."""
        payload = {
            "type": "block_actions",
            "trigger_id": "trigger_123456",
            "user": {"id": "U123", "username": "testuser"},
            "channel": {"id": "C123"},
            "actions": [
                {
                    "action_id": "flag_status_review",
                    "value": "C123|1234567890.123456|123456_abc",
                }
            ],
            "response_url": "https://hooks.slack.com/test",
        }

        # Mock sub-modules - rate limited
        handler.validators.check_rate_limit = Mock(return_value=False)
        handler.modal_orchestrator._display_modal_via_api = AsyncMock(return_value=True)

        result = await handler.process_flag_action(payload)

        assert result is False
        handler.validators.check_rate_limit.assert_called_once_with("U123")
        # Should show rate limit modal
        handler.modal_orchestrator._display_modal_via_api.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_command_flag_action_success(self, handler):
        """Test successful command flag action processing."""
        payload = {
            "type": "view_submission",
            "view": {
                "callback_id": "command_flag_review_modal",
                "private_metadata": "C123|cmd_123|status",
                "state": {
                    "values": {
                        "feedback_block": {
                            "feedback_input": {"value": "Command output is incorrect"}
                        }
                    }
                },
            },
            "user": {"id": "U123", "username": "testuser"},
        }

        # Mock the command_flag_processor which handles command flag actions
        handler.command_flag_processor.process_command_flag_action = AsyncMock(
            return_value=True
        )

        result = await handler.process_command_flag_action(payload)

        assert result is True
        handler.command_flag_processor.process_command_flag_action.assert_called_once_with(
            payload
        )

    @pytest.mark.asyncio
    async def test_public_interface_unchanged(self, handler):
        """Test that public interface remains unchanged."""
        # Verify public methods exist
        assert hasattr(handler, "process_flag_action")
        assert hasattr(handler, "process_command_flag_action")

        # Verify they are async methods
        assert callable(handler.process_flag_action)
        assert callable(handler.process_command_flag_action)
