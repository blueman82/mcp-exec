"""
Unit tests for access request automation feature flag integration.

Tests the feature flag controls in command router and payload processor.
"""

from unittest.mock import AsyncMock, patch

import pytest

from packages.slack.command_processing.command_router import CommandRouter
from packages.slack.interactive_elements.payload_processor import (
    process_interactive_payload,
)


class TestAccessRequestFeatureFlag:
    """Test suite for access request automation feature flag."""

    @pytest.mark.asyncio
    async def test_command_router_with_feature_enabled(self):
        """Test command router shows request button when feature is enabled."""
        # Mock dependencies
        mock_handlers = {}
        mock_posting_handler = AsyncMock()
        mock_user_verifier = AsyncMock()
        mock_user_verifier.validate_user_id = AsyncMock(return_value=False)
        mock_user_store = AsyncMock()

        # Create router
        router = CommandRouter(
            command_handlers=mock_handlers,
            slack_posting_handler=mock_posting_handler,
            user_verifier=mock_user_verifier,
            user_store=mock_user_store,
        )

        # Mock the feature flag to be enabled
        with patch(
            "packages.slack.command_processing.command_router.FeatureFlags.is_access_request_automation_enabled",
            return_value=True,
        ):

            # Test unauthorized user gets button (in DM)
            await router.route_command(
                {
                    "command": "/ketchup",
                    "text": "status",
                    "user_id": "U123456",
                    "user_name": "testuser",
                    "team_id": "T123456",
                    "channel_id": "D123456",  # DM channel ID
                    "response_url": "https://hooks.slack.com/test",
                }
            )

            # Verify access request blocks were posted with button
            assert mock_posting_handler.post_message.called
            call_args = mock_posting_handler.post_message.call_args
            # Get keyword arguments
            kwargs = call_args[1] if len(call_args) > 1 else call_args.kwargs
            blocks = kwargs.get("blocks", [])

            # Check for button in blocks
            has_button = any(
                block.get("type") == "actions"
                and any(elem.get("type") == "button" for elem in block.get("elements", []))
                for block in blocks
            )
            assert has_button, "Should show request button when feature is enabled"

    @pytest.mark.asyncio
    async def test_command_router_with_feature_disabled(self):
        """Test command router doesn't show request button when feature is disabled."""
        # Mock dependencies
        mock_handlers = {}
        mock_posting_handler = AsyncMock()
        mock_user_verifier = AsyncMock()
        mock_user_verifier.validate_user_id = AsyncMock(return_value=False)
        mock_user_store = AsyncMock()

        # Create router
        router = CommandRouter(
            command_handlers=mock_handlers,
            slack_posting_handler=mock_posting_handler,
            user_verifier=mock_user_verifier,
            user_store=mock_user_store,
        )

        # Mock the feature flag to be disabled
        with patch(
            "packages.slack.command_processing.command_router.FeatureFlags.is_access_request_automation_enabled",
            return_value=False,
        ):

            # Test unauthorized user doesn't get button
            await router.route_command(
                {
                    "command": "/ketchup",
                    "text": "status",
                    "user_id": "U123456",
                    "user_name": "testuser",
                    "team_id": "T123456",
                    "channel_id": "C123456",
                    "response_url": "https://hooks.slack.com/test",
                }
            )

            # Verify access request blocks were posted without button
            assert mock_posting_handler.post_message.called
            call_args = mock_posting_handler.post_message.call_args
            # Get keyword arguments
            kwargs = call_args[1] if len(call_args) > 1 else call_args.kwargs
            blocks = kwargs.get("blocks", [])

            # Check no button in blocks
            has_button = any(
                block.get("type") == "actions"
                and any(elem.get("type") == "button" for elem in block.get("elements", []))
                for block in blocks
            )
            assert not has_button, "Should not show request button when feature is disabled"

    @pytest.mark.asyncio
    async def test_payload_processor_with_feature_enabled(self):
        """Test payload processor handles access request actions when feature is enabled."""
        # Mock handlers
        mock_posting_handler = AsyncMock()
        mock_access_request_handler = AsyncMock()
        mock_access_request_handler.handle_request_access = AsyncMock(
            return_value={"response_type": "ephemeral", "text": "Request created"}
        )

        # Mock other required handlers
        mock_feedback_handler = AsyncMock()
        mock_shortcut_handler = AsyncMock()
        mock_feedback_report_handler = AsyncMock()
        mock_metadata_handler = AsyncMock()
        mock_home_handler = AsyncMock()
        mock_trust_handler = AsyncMock()

        # Test payload
        payload = {
            "type": "block_actions",
            "user": {"id": "U123456"},
            "channel": {"id": "C123456"},
            "actions": [{"action_id": "request_access", "value": "U123456"}],
        }

        # Mock the feature flag to be enabled
        with patch(
            "packages.slack.interactive_elements.payload_processor.FeatureFlags.is_access_request_automation_enabled",
            return_value=True,
        ):

            result = await process_interactive_payload(
                payload_input=payload,
                posting_handler=mock_posting_handler,
                feedback_handler=mock_feedback_handler,
                shortcut_handler=mock_shortcut_handler,
                feedback_report_handler=mock_feedback_report_handler,
                channel_metadata_edit_handler=mock_metadata_handler,
                home_tab_handler=mock_home_handler,
                trust_endorsement_handler=mock_trust_handler,
                access_request_handler=mock_access_request_handler,
            )

            # Verify action was handled
            assert result is True
            assert mock_access_request_handler.handle_request_access.called

    @pytest.mark.asyncio
    async def test_payload_processor_with_feature_disabled(self):
        """Test payload processor ignores access request actions when feature is disabled."""
        # Mock handlers
        mock_posting_handler = AsyncMock()
        mock_access_request_handler = AsyncMock()

        # Mock other required handlers
        mock_feedback_handler = AsyncMock()
        mock_shortcut_handler = AsyncMock()
        mock_feedback_report_handler = AsyncMock()
        mock_metadata_handler = AsyncMock()
        mock_home_handler = AsyncMock()
        mock_trust_handler = AsyncMock()

        # Test payload
        payload = {
            "type": "block_actions",
            "user": {"id": "U123456"},
            "channel": {"id": "C123456"},
            "actions": [{"action_id": "request_access", "value": "U123456"}],
        }

        # Mock the feature flag to be disabled
        with patch(
            "packages.slack.interactive_elements.payload_processor.FeatureFlags.is_access_request_automation_enabled",
            return_value=False,
        ):

            result = await process_interactive_payload(
                payload_input=payload,
                posting_handler=mock_posting_handler,
                feedback_handler=mock_feedback_handler,
                shortcut_handler=mock_shortcut_handler,
                feedback_report_handler=mock_feedback_report_handler,
                channel_metadata_edit_handler=mock_metadata_handler,
                home_tab_handler=mock_home_handler,
                trust_endorsement_handler=mock_trust_handler,
                access_request_handler=mock_access_request_handler,
            )

            # Verify action was not handled (returns false for unknown action)
            assert result is True  # Still returns true but posts "Unknown command"
            assert not mock_access_request_handler.handle_request_access.called

            # Should post unknown action message
            assert mock_posting_handler.post_message.called
            call_args = mock_posting_handler.post_message.call_args
            assert "Unknown action" in call_args[1]["message"]

    def test_feature_flag_environment_variable(self):
        """Test that feature flag reads from correct environment variable."""
        from packages.core.config.feature_flags import FeatureFlags

        # Test with feature disabled (default)
        with patch.dict("os.environ", {}, clear=True):
            assert FeatureFlags.is_access_request_automation_enabled() is False
            assert FeatureFlags.is_access_request_automation_global() is False

        # Test with feature enabled
        with patch.dict(
            "os.environ",
            {
                "KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE": "true",
                "KETCHUP_ACCESS_REQUEST_AUTOMATION_GLOBAL": "true",
            },
        ):
            assert FeatureFlags.is_access_request_automation_enabled() is True
            assert FeatureFlags.is_access_request_automation_global() is True

        # Test case insensitive
        with patch.dict(
            "os.environ",
            {
                "KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE": "TRUE",
                "KETCHUP_ACCESS_REQUEST_AUTOMATION_GLOBAL": "TrUe",
            },
        ):
            assert FeatureFlags.is_access_request_automation_enabled() is True
            assert FeatureFlags.is_access_request_automation_global() is True
