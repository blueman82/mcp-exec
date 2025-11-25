"""
Unit tests for FlagReviewModalManager.

Tests modal creation and management for flag review functionality.
"""

from unittest.mock import Mock

import pytest

from packages.slack.interactive_elements.flag_review.modals import (
    FlagReviewModalManager,
)


class TestFlagReviewModalManager:
    """Test suite for FlagReviewModalManager."""

    @pytest.fixture
    def mock_secrets_manager(self):
        """Create a mock secrets manager."""
        mock = Mock()
        return mock

    @pytest.fixture
    def modal_manager(self, mock_secrets_manager):
        """Create modal manager with mocked dependencies."""
        return FlagReviewModalManager(mock_secrets_manager)

    @pytest.mark.asyncio
    async def test_display_feedback_modal(self, modal_manager):
        """Test displaying feedback modal."""
        result = await modal_manager.display_feedback_modal(
            trigger_id="trigger_123",
            channel_id="C123",
            message_ts="1234567890.123456",
            status_update_id="123456_abc",
        )

        # Should return True (modal view created and validated)
        assert result is True

    def test_create_feedback_modal_view(self, modal_manager):
        """Test creating feedback modal view."""
        modal_view = modal_manager.create_feedback_modal_view(
            channel_id="C123",
            message_ts="1234567890.123456",
            status_update_id="123456_abc",
        )

        assert modal_view["type"] == "modal"
        assert modal_view["callback_id"] == "flag_review_modal"
        assert "C123|1234567890.123456|123456_abc" in modal_view["private_metadata"]
        assert modal_view["title"]["text"] == "Flag Summary for Review"

    def test_create_reply_modal_view(self, modal_manager):
        """Test creating reply modal view."""
        modal_view = modal_manager.create_reply_modal_view(
            flag_id="C123_1234567890.123456",
            user_id="U123",
            feedback_text="Original feedback",
            is_command=False,
        )

        assert modal_view["type"] == "modal"
        assert modal_view["callback_id"] == "reply_feedback_modal"
        assert "C123_1234567890.123456|U123" in modal_view["private_metadata"]
        assert modal_view["title"]["text"] == "Reply to Feedback"

    def test_create_command_feedback_modal_view(self, modal_manager):
        """Test creating command feedback modal view."""
        modal_view = modal_manager.create_command_feedback_modal_view(
            channel_id="C123",
            command_execution_id="cmd_123",
            command_type="status",
            command_output="Status output here",
        )

        assert modal_view["type"] == "modal"
        assert modal_view["callback_id"] == "command_flag_review_modal"
        assert "C123|cmd_123|status" in modal_view["private_metadata"]
        assert modal_view["title"]["text"] == "Flag Command Output"

    @pytest.mark.asyncio
    async def test_handle_review_modal_update(self, modal_manager):
        """Test handling modal update with review data."""
        modal_view = {"title": {"text": "Original Title"}, "blocks": []}
        review_data = {
            "status": "acknowledged",
            "additional_blocks": [{"type": "divider"}],
        }

        updated = await modal_manager.handle_review_modal_update(
            modal_view, review_data
        )

        assert updated["title"]["text"] == "Review - acknowledged"
        assert len(updated["blocks"]) == 1
        assert updated["blocks"][0]["type"] == "divider"

    def test_initialization(self, modal_manager):
        """Test that modal manager initializes correctly."""
        assert modal_manager.secrets_manager is not None
        assert hasattr(modal_manager, "display_feedback_modal")
        assert hasattr(modal_manager, "create_feedback_modal_view")
        assert hasattr(modal_manager, "create_reply_modal_view")
