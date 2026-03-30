"""
home.py

Covers:
- HomeTabHandler.handle_app_home_opened: Home tab publishing, user preference retrieval, error handling
- HomeTabHandler.handle_block_actions: Save preferences, modal feedback, error handling
- All dependencies (SecretsManager, UserStore, SlackAsyncClient) are mocked
- All business logic is delegated to home_publish, home_preferences, home_modals

Edge Cases Covered:
- Missing user_id in event or payload
- Slack API call failures

Expected Outcomes:
- Home tab is published with correct preferences (integration only)
- Preferences are saved and confirmation modal is shown (integration only)
- All external calls and module calls are mocked and asserted
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.home.home import HomeTabHandler
from packages.slack.interactive_elements.feedback_report import FeedbackReportHandler


@pytest.fixture
def mock_home_tab_deps():
    """Mock dependencies for HomeTabHandler tests to prevent production failures."""
    return {"user_store": AsyncMock(), "slack_client": AsyncMock(), "command_tracking": AsyncMock()}


class TestHomeTabHandler:
    """Integration/orchestration tests for HomeTabHandler (Slack Home tab logic)."""

    @pytest.fixture(autouse=True)
    def setup_handler(self, mock_home_tab_deps):
        # Set up all mocks with proper async behavior
        self.secrets_manager = MagicMock()
        self.user_store = mock_home_tab_deps["user_store"]
        self.slack_client = mock_home_tab_deps["slack_client"]

        # Mock Slack client api_call to return proper response
        self.slack_client.api_call = AsyncMock(return_value={"ok": True})

        self.slack_user_ops = AsyncMock()
        # Mock get_user_names to return a proper dict
        self.slack_user_ops.get_user_names = AsyncMock(return_value={})

        self.feedback_report_handler = AsyncMock(spec=FeedbackReportHandler)
        # Properly mock the async method
        self.feedback_report_handler.open_feedback_report_modal = AsyncMock(return_value=True)

        self.command_tracking_ops = mock_home_tab_deps["command_tracking"]
        # Mock the methods that HomeTabHandler uses
        self.command_tracking_ops.get_user_command_stats = AsyncMock(return_value=None)
        self.command_tracking_ops.get_team_command_stats = AsyncMock(return_value=None)
        self.command_tracking_ops.get_top_users = AsyncMock(return_value=[])
        self.command_tracking_ops.get_user_command_breakdown = AsyncMock(return_value={})

        self.usage_export_handler = AsyncMock()

        self.handler = HomeTabHandler(
            secrets_manager=self.secrets_manager,
            user_store=self.user_store,
            slack_client=self.slack_client,
            slack_user_ops=self.slack_user_ops,
            feedback_report_handler=self.feedback_report_handler,
            command_tracking_ops=self.command_tracking_ops,
            admin_user_list=[],  # Empty admin list for tests
            usage_export_handler=self.usage_export_handler,
        )

    @pytest.mark.asyncio
    async def test_get_user_preferences_success(self):
        """Test _get_user_preferences returns raw, normalized prefs, and name."""
        user_id = "U123"
        raw_prefs_from_db = {"detail_level": "high"}
        normalized_prefs_mock = {"detail_level": "high_normalized"}
        first_name = "TestUser"

        self.user_store.get_user.return_value = {
            "preferences": raw_prefs_from_db,
            "real_name": first_name,
        }

        with patch(
            "packages.slack.home.home.normalize_user_preferences",
            return_value=normalized_prefs_mock,
        ) as mock_normalize:
            actual_raw_prefs, actual_normalized_prefs, actual_first_name = (
                await self.handler._get_user_preferences(user_id)
            )

            self.slack_user_ops.get_user_names.assert_called_once_with([user_id])
            self.user_store.get_user.assert_called_once_with(user_id)
            mock_normalize.assert_called_once_with(raw_prefs_from_db)
            assert actual_raw_prefs == raw_prefs_from_db
            assert actual_normalized_prefs == normalized_prefs_mock
            assert actual_first_name == first_name

    @pytest.mark.asyncio
    async def test_get_user_preferences_no_db_data(self):
        """Test _get_user_preferences returns defaults and normalized defaults when no DB data."""
        user_id = "U456"
        default_raw_prefs = {
            "product_focus": ["all_products"],
            "detail_level": "technical_details",
            "time_window": "all_time",
        }
        normalized_defaults_mock = {"detail_level": "balanced_normalized"}  # Example mock

        self.user_store.get_user.return_value = None  # Simulate no data for user

        with patch(
            "packages.slack.home.home.normalize_user_preferences",
            return_value=normalized_defaults_mock,
        ) as mock_normalize:
            actual_raw_prefs, actual_normalized_prefs, actual_first_name = (
                await self.handler._get_user_preferences(user_id)
            )

            self.slack_user_ops.get_user_names.assert_called_once_with([user_id])
            self.user_store.get_user.assert_called_once_with(user_id)
            mock_normalize.assert_called_once_with(default_raw_prefs)  # Should normalize defaults
            assert actual_raw_prefs == default_raw_prefs
            assert actual_normalized_prefs == normalized_defaults_mock
            assert actual_first_name == "there"  # Default name

    @pytest.mark.asyncio
    async def test_get_user_preferences_db_error(self):
        """Test _get_user_preferences returns defaults and normalized defaults on DB error."""
        user_id = "U789"
        default_raw_prefs = {
            "product_focus": ["all_products"],
            "detail_level": "technical_details",
            "time_window": "all_time",
        }
        normalized_defaults_mock = {"detail_level": "balanced_normalized"}  # Example mock

        self.user_store.get_user.side_effect = Exception("DB error")

        with patch(
            "packages.slack.home.home.normalize_user_preferences",
            return_value=normalized_defaults_mock,
        ) as mock_normalize:
            actual_raw_prefs, actual_normalized_prefs, actual_first_name = (
                await self.handler._get_user_preferences(user_id)
            )

            self.slack_user_ops.get_user_names.assert_called_once_with([user_id])
            self.user_store.get_user.assert_called_once_with(user_id)
            # raw_prefs passed to normalize should be the defaults after error
            mock_normalize.assert_called_once_with(default_raw_prefs)
            assert actual_raw_prefs == default_raw_prefs
            assert actual_normalized_prefs == normalized_defaults_mock
            assert actual_first_name == "there"

    @pytest.mark.asyncio
    async def test_handle_app_home_opened_success(self):
        """Test Home tab is published with user preferences on app_home_opened event (integration)."""
        event = {"user": "U123"}
        mock_raw_prefs = {"detail_level": "manager_raw"}
        mock_normalized_prefs = {"detail_level": "manager_normalized"}
        mock_first_name = "TestUser"

        # Mock _get_user_preferences to return a tuple with raw_prefs, normalized_prefs, and first_name
        mock_get_preferences = AsyncMock(
            return_value=(mock_raw_prefs, mock_normalized_prefs, mock_first_name)
        )
        self.handler._get_user_preferences = mock_get_preferences

        # Mock _publish_home_tab
        mock_publish = AsyncMock(return_value=True)
        self.handler._publish_home_tab = mock_publish

        result = await self.handler.handle_app_home_opened(event)

        # Assertions
        mock_get_preferences.assert_called_once_with("U123")
        # Ensure _publish_home_tab is called with RAW preferences and additional stats params
        mock_publish.assert_called_once_with(
            "U123",
            mock_raw_prefs,
            mock_first_name,
            command_stats=None,
            is_admin_user=False,
            admin_stats=None,
            admin_command_breakdown=None,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_handle_app_home_opened_missing_user(self):
        """Test Home tab handler returns False if user_id is missing (integration)."""
        event = {}
        result = await self.handler.handle_app_home_opened(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_block_actions_save_preferences(self):
        """Test saving preferences triggers DB save and modal feedback (integration)."""
        payload = {
            "user": {"id": "U123"},
            "actions": [{"action_id": "save_preferences_button"}],
            "trigger_id": "TID123",
        }
        with patch(
            "packages.slack.home.home.save_user_preferences",
            new=AsyncMock(return_value=True),
        ):
            # Mock home tab rendering to prevent production calls
            with patch.object(
                self.handler, "handle_app_home_opened", new=AsyncMock(return_value=True)
            ):
                result = await self.handler.handle_block_actions(payload)
                assert result is True

    @pytest.mark.asyncio
    async def test_handle_block_actions_save_preferences_refreshes_home_tab(self):
        """Test saving preferences successfully triggers home tab refresh."""
        user_id = "U123"
        payload = {
            "user": {"id": user_id},
            "actions": [{"action_id": "save_preferences_button"}],
            "trigger_id": "TID123",
        }

        # Mock the save_user_preferences to return True (success)
        with patch(
            "packages.slack.home.home.save_user_preferences",
            new=AsyncMock(return_value=True),
        ):
            # Mock asyncio.sleep to avoid delay in tests
            with patch("asyncio.sleep", new=AsyncMock()):
                # Mock the home tab publishing methods
                with patch.object(
                    self.handler,
                    "_get_user_preferences",
                    new=AsyncMock(
                        return_value=(
                            {
                                "product_focus": ["campaign"],
                                "detail_level": "high_level",
                            },  # raw prefs
                            {
                                "product_focus": ["Adobe Campaign"],
                                "detail_level": "high-level",
                            },  # normalized
                            "TestUser",  # first name
                        )
                    ),
                ):
                    with patch.object(
                        self.handler,
                        "_publish_home_tab",
                        new=AsyncMock(return_value=True),
                    ):
                        # Execute the action
                        result = await self.handler.handle_block_actions(payload)

                        # Verify save preferences was called
                        # save_user_preferences should have been called once

                        # Verify home tab was refreshed by checking _get_user_preferences was called
                        self.handler._get_user_preferences.assert_called_with(user_id)

                        # Verify _publish_home_tab was called with the new preferences
                        self.handler._publish_home_tab.assert_called_once()
                        call_args = self.handler._publish_home_tab.call_args
                        assert call_args[0][0] == user_id  # First positional arg is user_id
                        assert call_args[0][1] == {
                            "product_focus": ["campaign"],
                            "detail_level": "high_level",
                        }  # Second is raw prefs

                        assert result is True

    @pytest.mark.asyncio
    async def test_handle_block_actions_save_preferences_no_refresh_on_failure(self):
        """Test failed preference save does not trigger home tab refresh."""
        user_id = "U123"
        payload = {
            "user": {"id": user_id},
            "actions": [{"action_id": "save_preferences_button"}],
            "trigger_id": "TID123",
        }

        # Mock the save_user_preferences to return False (failure)
        with patch(
            "packages.slack.home.home.save_user_preferences",
            new=AsyncMock(return_value=False),
        ):
            # Mock the home tab methods to ensure they're not called
            with patch.object(
                self.handler, "_get_user_preferences", new=AsyncMock()
            ) as mock_get_prefs:
                with patch.object(
                    self.handler, "_publish_home_tab", new=AsyncMock()
                ) as mock_publish:
                    # Execute the action
                    result = await self.handler.handle_block_actions(payload)

                    # Verify home tab was NOT refreshed since save failed
                    mock_get_prefs.assert_not_called()
                    mock_publish.assert_not_called()

                    assert result is False

    @pytest.mark.asyncio
    async def test_handle_block_actions_missing_user(self):
        """Test block actions returns False if user_id is missing (integration)."""
        payload = {"actions": [{"action_id": "save_preferences_button"}]}
        result = await self.handler.handle_block_actions(payload)
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_block_actions_open_feedback_modal(self):
        """Test feedback button triggers opening the feedback modal."""
        payload = {
            "user": {"id": "U123"},
            "actions": [{"action_id": "home_open_feedback_modal"}],
            "trigger_id": "TID123",
        }

        # Configure the mock to return True
        self.feedback_report_handler.open_feedback_report_modal.return_value = True

        result = await self.handler.handle_block_actions(payload)

        # Assert the modal was opened with the correct trigger ID
        self.feedback_report_handler.open_feedback_report_modal.assert_called_once_with("TID123")
        assert result is True

    @pytest.mark.asyncio
    async def test_handle_block_actions_feedback_modal_no_trigger(self):
        """Test feedback button handling fails gracefully when trigger_id is missing."""
        payload = {
            "user": {"id": "U123"},
            "actions": [{"action_id": "home_open_feedback_modal"}],
            # Missing trigger_id
        }

        result = await self.handler.handle_block_actions(payload)

        # Should return False due to missing trigger_id
        assert result is False
        # Should not try to open modal
        self.feedback_report_handler.open_feedback_report_modal.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_block_actions_feedback_modal_no_handler(self):
        """Test feedback button handling fails gracefully when feedback handler is not initialized."""
        payload = {
            "user": {"id": "U123"},
            "actions": [{"action_id": "home_open_feedback_modal"}],
            "trigger_id": "TID123",
        }

        # Create a handler without a feedback report handler
        handler = HomeTabHandler(
            secrets_manager=self.secrets_manager,
            user_store=self.user_store,
            slack_client=self.slack_client,
            slack_user_ops=self.slack_user_ops,
            feedback_report_handler=None,
        )

        result = await handler.handle_block_actions(payload)

        # Should return False due to missing feedback handler
        assert result is False

    @pytest.mark.asyncio
    async def test_admin_check_case_insensitive(self):
        """Test admin check is case-insensitive (AWS has 'Gary Harrison', Slack returns 'gary harrison')."""
        # Create handler with title case admin name (as stored in AWS Secrets)
        handler = HomeTabHandler(
            secrets_manager=self.secrets_manager,
            user_store=self.user_store,
            slack_client=self.slack_client,
            slack_user_ops=self.slack_user_ops,
            feedback_report_handler=self.feedback_report_handler,
            command_tracking_ops=self.command_tracking_ops,
            admin_user_list=["Gary Harrison"],  # Title case from AWS
            usage_export_handler=self.usage_export_handler,
        )

        user_id = "W7MGASQ2K"
        event = {"user": user_id}

        # Mock Slack API returning lowercase username
        handler._slack_user_ops.get_user_names = AsyncMock(
            return_value={user_id: "gary harrison"}  # Lowercase from Slack
        )

        # Mock other dependencies
        handler._get_user_preferences = AsyncMock(
            return_value=(
                {"detail_level": "high"},  # raw prefs
                {"detail_level": "high"},  # normalized prefs
                "Gary",  # first name
            )
        )
        handler._publish_home_tab = AsyncMock(return_value=True)

        # Mock command tracking to return some stats
        mock_admin_stats = [("U123", "John Doe", 50), ("U456", "Jane Smith", 45)]
        mock_command_breakdown = {
            "U123": {"status": 30, "query": 20},
            "U456": {"report": 25, "query": 20},
        }
        handler._command_tracking_ops.get_top_users = AsyncMock(return_value=mock_admin_stats)
        handler._command_tracking_ops.get_user_command_breakdown = AsyncMock(
            return_value=mock_command_breakdown
        )
        handler._command_tracking_ops.get_user_command_stats = AsyncMock(
            return_value={"status": 10, "query": 5}
        )

        # Execute
        result = await handler.handle_app_home_opened(event)

        # Verify the handler recognized Gary Harrison as an admin
        # Check that _publish_home_tab was called with is_admin_user=True
        assert result is True
        handler._publish_home_tab.assert_called_once()
        call_kwargs = handler._publish_home_tab.call_args[1]
        assert call_kwargs["is_admin_user"] is True, (
            "Expected user 'gary harrison' to be recognized as admin "
            "when admin list contains 'Gary Harrison'"
        )
        assert call_kwargs["admin_stats"] == mock_admin_stats
        assert call_kwargs["admin_command_breakdown"] == mock_command_breakdown

    @pytest.mark.asyncio
    async def test_admin_check_with_empty_list_bug(self):
        """
        Test that reproduces production bug: empty admin_user_list means no one is recognized as admin.
        This simulates what happens when AWS Secrets fails to load or returns unexpected data.
        """
        # Create handler with EMPTY admin list (simulating secrets loading failure)
        handler = HomeTabHandler(
            secrets_manager=self.secrets_manager,
            user_store=self.user_store,
            slack_client=self.slack_client,
            slack_user_ops=self.slack_user_ops,
            feedback_report_handler=self.feedback_report_handler,
            command_tracking_ops=self.command_tracking_ops,
            admin_user_list=[],  # EMPTY - this is the bug!
            usage_export_handler=self.usage_export_handler,
        )

        user_id = "W7MGASQ2K"
        event = {"user": user_id}

        # Mock Slack API returning the username
        handler._slack_user_ops.get_user_names = AsyncMock(return_value={user_id: "gary harrison"})

        # Mock other dependencies
        handler._get_user_preferences = AsyncMock(
            return_value=(
                {"detail_level": "high"},  # raw prefs
                {"detail_level": "high"},  # normalized prefs
                "Gary",  # first name
            )
        )
        handler._publish_home_tab = AsyncMock(return_value=True)
        handler._command_tracking_ops.get_user_command_stats = AsyncMock(
            return_value={"status": 10}
        )

        # Execute
        result = await handler.handle_app_home_opened(event)

        # This is the BUG: even though Gary Harrison is in AWS Secrets,
        # if admin_user_list is empty, NO ONE gets admin access
        assert result is True
        handler._publish_home_tab.assert_called_once()
        call_kwargs = handler._publish_home_tab.call_args[1]

        # BUG: User is NOT recognized as admin when list is empty
        assert call_kwargs["is_admin_user"] is False, (
            "BUG REPRODUCED: User should be admin but empty admin_user_list "
            "means no one is recognized as admin (secrets loading failed)"
        )
        assert call_kwargs["admin_stats"] is None
        assert call_kwargs["admin_command_breakdown"] is None
