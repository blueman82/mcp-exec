"""
Unit tests for packages/slack/channel_events/processing/join_processor.py

Covers:
- get_channel_name
- process_eligible_bot_join
- handle_member_joined_event
- All error and edge cases, including DB/API fallback, metadata creation, eligibility, and error notification.

All dependencies are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.channel_events.processing.join_processor import (
    handle_member_joined_event,
    process_eligible_bot_join,
    process_regular_user_join,
)


@pytest.mark.asyncio
class TestProcessEligibleBotJoin:
    @patch("packages.slack.channel_events.processing.join_processor.ChannelMetadata")
    async def test_channel_not_in_db_adds_metadata(self, mock_metadata):
        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(return_value=None)
        dynamodb.channel_ops.store_metadata = AsyncMock()
        channel_info_ops = MagicMock()
        channel_info_ops.get_channel_info_from_api = AsyncMock(
            return_value={
                "ok": True,
                "name": "chan",
                "created": "1234567890",
                "is_archived": False,
            }
        )
        posting_handler = MagicMock()
        event = {"event_ts": "1234567890"}
        await process_eligible_bot_join(
            event, "C1", "U1", None, dynamodb, channel_info_ops, posting_handler
        )
        dynamodb.channel_ops.store_metadata.assert_awaited_once()
        mock_metadata.assert_called_once()

    async def test_channel_in_db_no_action(self):
        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(return_value={"foo": "bar"})
        dynamodb.channel_ops.store_metadata = AsyncMock()
        channel_info_ops = MagicMock()
        channel_info_ops.get_channel_info_from_api = AsyncMock()
        posting_handler = MagicMock()
        event = {"event_ts": "1234567890"}
        await process_eligible_bot_join(
            event, "C2", "U2", None, dynamodb, channel_info_ops, posting_handler
        )
        dynamodb.channel_ops.store_metadata.assert_not_awaited()

    async def test_channel_lookup_error(self):
        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(return_value=None)
        dynamodb.channel_ops.store_metadata = AsyncMock()
        channel_info_ops = MagicMock()
        channel_info_ops.get_channel_info_from_api = AsyncMock(side_effect=Exception("fail"))
        posting_handler = MagicMock()
        event = {"event_ts": "1234567890"}
        await process_eligible_bot_join(
            event, "C3", "U3", None, dynamodb, channel_info_ops, posting_handler
        )
        dynamodb.channel_ops.store_metadata.assert_not_awaited()

    async def test_metadata_creation_timestamp_fallback(self):
        # Simulate bad created timestamp, fallback to event_ts, then fallback to now
        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(return_value=None)
        dynamodb.channel_ops.store_metadata = AsyncMock()
        channel_info_ops = MagicMock()
        channel_info_ops.get_channel_info_from_api = AsyncMock(
            return_value={
                "ok": True,
                "name": "chan",
                "created": "bad",
                "is_archived": False,
            }
        )
        posting_handler = MagicMock()
        event = {"event_ts": "bad"}
        with patch("time.time", return_value=1234567890):
            await process_eligible_bot_join(
                event, "C4", "U4", None, dynamodb, channel_info_ops, posting_handler
            )
        dynamodb.channel_ops.store_metadata.assert_awaited_once()

    async def test_outer_exception(self):
        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(side_effect=Exception("fail"))
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"event_ts": "1234567890"}
        # Should not raise
        await process_eligible_bot_join(
            event, "C5", "U5", None, dynamodb, channel_info_ops, posting_handler
        )

    @patch("packages.slack.channel_events.processing.join_processor.os.getenv")
    @patch("packages.slack.channel_events.processing.join_processor.get_jira_prompt_handler")
    async def test_maintenance_detection_feature_disabled(self, mock_get_handler, mock_getenv):
        """Test that maintenance detection is skipped when feature flag is disabled."""
        mock_getenv.return_value = "false"
        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(return_value={"exists": True})
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"event_ts": "1234567890"}

        await process_eligible_bot_join(
            event, "C6", "U6", None, dynamodb, channel_info_ops, posting_handler
        )

        # Handler should not be called when feature is disabled
        mock_get_handler.assert_not_called()

    @patch("packages.slack.channel_events.processing.join_processor.asyncio.create_task")
    @patch("packages.slack.channel_events.processing.join_processor.os.getenv")
    @patch("packages.slack.channel_events.processing.join_processor.get_jira_prompt_handler")
    async def test_maintenance_detection_feature_enabled_success(
        self, mock_get_handler, mock_getenv, mock_create_task
    ):
        """Test that maintenance detection workflow starts when feature flag is enabled."""
        mock_getenv.return_value = "true"
        mock_handler = MagicMock()
        mock_handler.start_jira_prompt_workflow = AsyncMock()
        mock_get_handler.return_value = mock_handler

        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(return_value={"exists": True})
        dynamodb.check_if_temporary_unarchive = AsyncMock(return_value=False)
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"event_ts": "1234567890"}

        await process_eligible_bot_join(
            event, "C7", "U7", None, dynamodb, channel_info_ops, posting_handler
        )

        # Handler should be called and workflow started in background
        dynamodb.check_if_temporary_unarchive.assert_awaited_once_with("C7")
        mock_get_handler.assert_awaited_once()
        mock_create_task.assert_called_once()

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    @patch("packages.slack.channel_events.processing.join_processor.os.getenv")
    @patch("packages.slack.channel_events.processing.join_processor.get_jira_prompt_handler")
    async def test_maintenance_detection_handler_resolution_failure(
        self, mock_get_handler, mock_getenv
    ):
        """Test that bot join continues when maintenance handler resolution fails."""
        mock_getenv.return_value = "true"
        # Setting side_effect on a patched async function causes unavoidable RuntimeWarning
        # This is a known limitation when mocking async functions that raise exceptions
        mock_get_handler.side_effect = Exception("Handler resolution failed")

        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(return_value={"exists": True})
        dynamodb.check_if_temporary_unarchive = AsyncMock(return_value=False)
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"event_ts": "1234567890"}

        # Should not raise exception - bot join should succeed despite handler failure
        await process_eligible_bot_join(
            event, "C8", "U8", None, dynamodb, channel_info_ops, posting_handler
        )

    @patch("packages.slack.channel_events.processing.join_processor.asyncio.create_task")
    @patch("packages.slack.channel_events.processing.join_processor.os.getenv")
    @patch("packages.slack.channel_events.processing.join_processor.get_jira_prompt_handler")
    async def test_maintenance_detection_workflow_start_exception(
        self, mock_get_handler, mock_getenv, mock_create_task
    ):
        """Test that bot join continues when maintenance workflow start fails."""
        mock_getenv.return_value = "true"
        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler
        mock_create_task.side_effect = Exception("Workflow start failed")

        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(return_value={"exists": True})
        dynamodb.check_if_temporary_unarchive = AsyncMock(return_value=False)
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"event_ts": "1234567890"}

        # Should not raise exception - bot join should succeed despite workflow failure
        await process_eligible_bot_join(
            event, "C9", "U9", None, dynamodb, channel_info_ops, posting_handler
        )

        # Verify handler was resolved and task creation was attempted
        dynamodb.check_if_temporary_unarchive.assert_awaited_once_with("C9")
        mock_get_handler.assert_awaited_once()
        mock_create_task.assert_called_once()

    @patch("packages.slack.channel_events.processing.join_processor.asyncio.create_task")
    @patch("packages.slack.channel_events.processing.join_processor.os.getenv")
    @patch("packages.slack.channel_events.processing.join_processor.get_jira_prompt_handler")
    async def test_maintenance_detection_skipped_for_temporary_unarchive(
        self, mock_get_handler, mock_getenv, mock_create_task
    ):
        """Test that maintenance detection is skipped for temporarily unarchived channels."""
        mock_getenv.return_value = "true"

        dynamodb = MagicMock()
        dynamodb.get_channel_details = AsyncMock(return_value={"exists": True})
        dynamodb.check_if_temporary_unarchive = AsyncMock(return_value=True)
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"event_ts": "1234567890"}

        await process_eligible_bot_join(
            event, "C10", "U10", None, dynamodb, channel_info_ops, posting_handler
        )

        # Temporary unarchive check should be called
        dynamodb.check_if_temporary_unarchive.assert_awaited_once_with("C10")
        # Handler should NOT be resolved since channel is temporarily unarchived
        mock_get_handler.assert_not_called()
        mock_create_task.assert_not_called()


@pytest.mark.asyncio
class TestHandleMemberJoinedEvent:
    @patch(
        "packages.slack.channel_events.processing.join_processor.process_eligible_bot_join",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.channel_events.processing.join_processor.handle_ineligible_bot_join",
        new_callable=AsyncMock,
    )
    async def test_bot_join_eligible(self, mock_ineligible, mock_eligible):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_eligibility_service = MagicMock()
        channel_eligibility_service.is_channel_eligible = AsyncMock(return_value=(True, ""))
        dynamodb = MagicMock()
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"channel": "C1", "user": "BOTID", "inviter": "U2"}
        await handle_member_joined_event(
            event,
            None,
            secrets_manager,
            channel_eligibility_service,
            dynamodb,
            channel_info_ops,
            posting_handler,
        )
        mock_eligible.assert_awaited_once()
        mock_ineligible.assert_not_awaited()

    @patch(
        "packages.slack.channel_events.processing.join_processor.process_eligible_bot_join",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.channel_events.processing.join_processor.handle_ineligible_bot_join",
        new_callable=AsyncMock,
    )
    async def test_bot_join_ineligible(self, mock_ineligible, mock_eligible):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_eligibility_service = MagicMock()
        channel_eligibility_service.is_channel_eligible = AsyncMock(
            return_value=(False, "Not allowed")
        )
        dynamodb = MagicMock()
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"channel": "C1", "user": "BOTID", "inviter": "U2"}
        await handle_member_joined_event(
            event,
            None,
            secrets_manager,
            channel_eligibility_service,
            dynamodb,
            channel_info_ops,
            posting_handler,
        )
        mock_eligible.assert_not_awaited()
        mock_ineligible.assert_awaited_once()

    async def test_regular_user_join(self):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_eligibility_service = MagicMock()
        dynamodb = MagicMock()
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"channel": "C1", "user": "U2", "inviter": "U3"}
        # Should not call eligible/ineligible
        await handle_member_joined_event(
            event,
            None,
            secrets_manager,
            channel_eligibility_service,
            dynamodb,
            channel_info_ops,
            posting_handler,
        )

    async def test_missing_channel_or_user(self):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_eligibility_service = MagicMock()
        dynamodb = MagicMock()
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        # Missing channel
        event = {"user": "BOTID"}
        await handle_member_joined_event(
            event,
            None,
            secrets_manager,
            channel_eligibility_service,
            dynamodb,
            channel_info_ops,
            posting_handler,
        )
        # Missing user
        event = {"channel": "C1"}
        await handle_member_joined_event(
            event,
            None,
            secrets_manager,
            channel_eligibility_service,
            dynamodb,
            channel_info_ops,
            posting_handler,
        )

    @patch(
        "packages.slack.channel_events.processing.join_processor.process_eligible_bot_join",
        new_callable=AsyncMock,
    )
    @patch(
        "packages.slack.channel_events.processing.join_processor.handle_ineligible_bot_join",
        new_callable=AsyncMock,
    )
    async def test_eligibility_service_exception(self, mock_ineligible, mock_eligible):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_eligibility_service = MagicMock()
        channel_eligibility_service.is_channel_eligible = AsyncMock(side_effect=Exception("fail"))
        dynamodb = MagicMock()
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        event = {"channel": "C1", "user": "BOTID", "inviter": "U2"}
        # Should not raise
        await handle_member_joined_event(
            event,
            None,
            secrets_manager,
            channel_eligibility_service,
            dynamodb,
            channel_info_ops,
            posting_handler,
        )

    async def test_outer_exception_and_notify(self):
        secrets_manager = MagicMock()
        secrets_manager.get_bot_slack_user_id_async = AsyncMock(return_value="BOTID")
        channel_eligibility_service = MagicMock()
        dynamodb = MagicMock()
        channel_info_ops = MagicMock()
        posting_handler = MagicMock()
        posting_handler.post_message = AsyncMock()
        event = {"channel": "C1", "user": "BOTID", "inviter": "U2"}
        with patch(
            "packages.slack.channel_events.processing.join_processor.process_eligible_bot_join",
            side_effect=Exception("fail"),
        ):
            await handle_member_joined_event(
                event=event,
                response_url=None,
                secrets_manager=secrets_manager,
                channel_eligibility_service=channel_eligibility_service,
                dynamodb_store=dynamodb,
                channel_info_ops=channel_info_ops,
                posting_handler=posting_handler,
            )
        posting_handler.post_message.assert_awaited_once()


@pytest.mark.asyncio
class TestProcessRegularUserJoin:
    """Test process_regular_user_join functionality."""

    @pytest.fixture
    def mock_channel_eligibility_service(self) -> AsyncMock:
        """Create a mock ChannelEligibilityService."""
        mock = AsyncMock()
        mock.is_channel_eligible = AsyncMock(return_value=(True, ""))
        return mock

    @pytest.fixture
    def mock_feature_service(self) -> AsyncMock:
        """Create a mock FeatureService."""
        mock = AsyncMock()
        mock.is_user_join_notifications_enabled_for_channel = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_user_join_notification_service(self) -> AsyncMock:
        """Create a mock UserJoinNotificationService."""
        mock = AsyncMock()
        mock.send_join_notification = AsyncMock(return_value=True)
        return mock

    async def test_regular_user_join_feature_disabled(
        self, mock_channel_eligibility_service: AsyncMock
    ) -> None:
        """Test regular user join when feature service is not available."""
        event = {"channel": "C12345", "user": "U12345"}

        await process_regular_user_join(
            event=event,
            channel_id="C12345",
            user_id="U12345",
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=None,
            user_join_notification_service=None,
        )

        # Should return early, no eligibility or notification calls
        mock_channel_eligibility_service.is_channel_eligible.assert_not_called()

    async def test_regular_user_join_notification_service_unavailable(
        self,
        mock_channel_eligibility_service: AsyncMock,
        mock_feature_service: AsyncMock,
    ) -> None:
        """Test regular user join when notification service is not available."""
        event = {"channel": "C12345", "user": "U12345"}

        await process_regular_user_join(
            event=event,
            channel_id="C12345",
            user_id="U12345",
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=None,
        )

        # Should return early, no eligibility calls
        mock_channel_eligibility_service.is_channel_eligible.assert_not_called()

    async def test_regular_user_join_feature_disabled_for_user(
        self,
        mock_channel_eligibility_service: AsyncMock,
        mock_feature_service: AsyncMock,
        mock_user_join_notification_service: AsyncMock,
    ) -> None:
        """Test regular user join when feature is disabled for channel."""
        mock_feature_service.is_user_join_notifications_enabled_for_channel.return_value = False
        event = {"channel": "C12345", "user": "U12345"}

        await process_regular_user_join(
            event=event,
            channel_id="C12345",
            user_id="U12345",
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
        )

        # Should return early after feature check
        mock_channel_eligibility_service.is_channel_eligible.assert_not_called()
        mock_user_join_notification_service.send_join_notification.assert_not_called()

    async def test_regular_user_join_channel_not_eligible(
        self,
        mock_channel_eligibility_service: AsyncMock,
        mock_feature_service: AsyncMock,
        mock_user_join_notification_service: AsyncMock,
    ) -> None:
        """Test regular user join when channel is not eligible."""
        mock_channel_eligibility_service.is_channel_eligible.return_value = (
            False,
            "Not eligible",
        )
        event = {"channel": "C12345", "user": "U12345"}

        await process_regular_user_join(
            event=event,
            channel_id="C12345",
            user_id="U12345",
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
        )

        # Should check eligibility but not send notification
        mock_channel_eligibility_service.is_channel_eligible.assert_called_once()
        mock_user_join_notification_service.send_join_notification.assert_not_called()

    async def test_regular_user_join_success_with_channel_name(
        self,
        mock_channel_eligibility_service: AsyncMock,
        mock_feature_service: AsyncMock,
        mock_user_join_notification_service: AsyncMock,
    ) -> None:
        """Test successful regular user join with channel name from event."""
        event = {"channel": "C12345", "user": "U12345", "channel_name": "test-channel"}

        await process_regular_user_join(
            event=event,
            channel_id="C12345",
            user_id="U12345",
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
        )

        mock_channel_eligibility_service.is_channel_eligible.assert_called_once()
        mock_user_join_notification_service.send_join_notification.assert_called_once_with(
            user_id="U12345", channel_id="C12345"
        )

    async def test_regular_user_join_success_without_channel_name(
        self,
        mock_channel_eligibility_service: AsyncMock,
        mock_feature_service: AsyncMock,
        mock_user_join_notification_service: AsyncMock,
    ) -> None:
        """Test successful regular user join without channel name in event."""
        event = {"channel": "C12345", "user": "U12345"}

        await process_regular_user_join(
            event=event,
            channel_id="C12345",
            user_id="U12345",
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
        )

        # Should fallback to channel_id as channel_name
        mock_user_join_notification_service.send_join_notification.assert_called_once_with(
            user_id="U12345", channel_id="C12345"
        )

    async def test_regular_user_join_notification_failure(
        self,
        mock_channel_eligibility_service: AsyncMock,
        mock_feature_service: AsyncMock,
        mock_user_join_notification_service: AsyncMock,
    ) -> None:
        """Test regular user join when notification sending fails."""
        mock_user_join_notification_service.send_join_notification.return_value = False
        event = {"channel": "C12345", "user": "U12345"}

        # Should not raise exception even if notification fails
        await process_regular_user_join(
            event=event,
            channel_id="C12345",
            user_id="U12345",
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
        )

        mock_user_join_notification_service.send_join_notification.assert_called_once()

    async def test_regular_user_join_exception_handling(
        self,
        mock_channel_eligibility_service: AsyncMock,
        mock_feature_service: AsyncMock,
        mock_user_join_notification_service: AsyncMock,
    ) -> None:
        """Test regular user join handles exceptions gracefully."""
        mock_feature_service.is_user_join_notifications_enabled_for_channel.side_effect = Exception(
            "Feature service error"
        )
        event = {"channel": "C12345", "user": "U12345"}

        # Should not raise exception
        await process_regular_user_join(
            event=event,
            channel_id="C12345",
            user_id="U12345",
            channel_eligibility_service=mock_channel_eligibility_service,
            feature_service=mock_feature_service,
            user_join_notification_service=mock_user_join_notification_service,
        )
