"""
Unit tests for UserJoinNotificationService.

Tests the core notification service including:
- AI content generation with mocked OpenAI responses
- Ephemeral message posting
- Error handling and logging
- Data collection workflow
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.services.user_join_notification_service import (
    UserJoinNotificationService,
)


class TestUserJoinNotificationService:
    """Test suite for UserJoinNotificationService."""

    @pytest.fixture
    def mock_openai_handler(self):
        """Mock OpenAI handler with correct response format."""
        handler = AsyncMock()
        handler._api_executor = AsyncMock()
        # Mock build_openai_payload method
        handler._api_executor.build_openai_payload = MagicMock(
            return_value={"messages": [], "max_tokens": 1024, "temperature": 0.1}
        )
        # Mock correct OpenAI response format (learned from rollback)
        handler._api_executor.execute_request = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": "Overview: Test channel is active with recent discussions.\n\nWhat's been done / What's next:\n• Recent bug fixes completed\n• Testing phase in progress\n• Documentation updates pending\n• Deployment scheduled for next week"
                        }
                    }
                ]
            }
        )
        return handler

    @pytest.fixture
    def mock_posting_handler(self):
        """Mock Slack posting handler."""
        handler = AsyncMock()
        handler._post_ephemeral = AsyncMock(return_value={"ok": True})
        return handler

    @pytest.fixture
    def mock_channel_info_ops(self):
        """Mock channel info operations."""
        ops = AsyncMock()
        ops.get_channel_info_from_api = AsyncMock(
            return_value={
                "name": "test-channel",
                "is_member": True,
                "customer_name": "Test Customer",
                "jira_ticket": "CPGNCX-12345",
                "product": "Test Product",
            }
        )
        return ops

    @pytest.fixture
    def mock_channel_msg_ops(self):
        """Mock channel message operations."""
        ops = AsyncMock()
        ops.fetch_channel_messages = AsyncMock(
            return_value=["User message 1", "User message 2", "User message 3"]
        )
        return ops

    @pytest.fixture
    def mock_jira_extractor(self):
        """Mock JIRA data extractor."""
        extractor = AsyncMock()
        # Return proper dictionary structure like real jira_extractor
        extractor.get_jira_context = AsyncMock(
            return_value={
                "source": "channel_metadata",
                "ticket_id": "CPGNCX-12345",
                "data": {"key": "CPGNCX-12345", "summary": "Test ticket"},
            }
        )
        return extractor

    @pytest.fixture
    def mock_user_store(self):
        """Mock user store for preference checking."""
        store = AsyncMock()
        # Default: user has notifications enabled
        store.get_user = AsyncMock(
            return_value={
                "user_id": "U12345",
                "real_name": "John Doe",
                "preferences": {"join_notifications_enabled": "enabled"},
            }
        )
        return store

    @pytest.fixture
    def notification_service(
        self,
        mock_openai_handler,
        mock_posting_handler,
        mock_channel_info_ops,
        mock_channel_msg_ops,
        mock_jira_extractor,
        mock_user_store,
    ):
        """Create UserJoinNotificationService with mocked dependencies."""
        return UserJoinNotificationService(
            openai_handler=mock_openai_handler,
            posting_handler=mock_posting_handler,
            channel_info_ops=mock_channel_info_ops,
            channel_msg_ops=mock_channel_msg_ops,
            jira_extractor=mock_jira_extractor,
            user_store=mock_user_store,
        )

    @pytest.fixture
    def service_without_jira(
        self,
        mock_openai_handler,
        mock_posting_handler,
        mock_channel_info_ops,
        mock_channel_msg_ops,
    ):
        """Create service without JIRA extractor."""
        return UserJoinNotificationService(
            openai_handler=mock_openai_handler,
            posting_handler=mock_posting_handler,
            channel_info_ops=mock_channel_info_ops,
            channel_msg_ops=mock_channel_msg_ops,
            jira_extractor=None,
        )

    @pytest.mark.asyncio
    async def test_send_join_notification_success(self, notification_service):
        """Test successful join notification sending."""
        # Test user profile for first name extraction
        user_profile = {"real_name": "John Doe"}

        result = await notification_service.send_join_notification(
            user_id="U12345", channel_id="C12345", user_profile=user_profile
        )

        assert result is True
        notification_service.posting_handler._post_ephemeral.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_join_notification_data_collection_failure(self, notification_service):
        """Test handling of data collection failure."""
        # Make channel info lookup fail
        notification_service.channel_info_ops.get_channel_info_from_api.side_effect = Exception(
            "API error"
        )

        result = await notification_service.send_join_notification(
            user_id="U12345", channel_id="C12345"
        )

        assert result is False
        notification_service.posting_handler._post_ephemeral.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_join_notification_ai_generation_failure(self, notification_service):
        """Test handling of AI content generation failure."""
        # Make OpenAI call return invalid format
        notification_service.openai_handler._api_executor.execute_request.return_value = {}

        result = await notification_service.send_join_notification(
            user_id="U12345", channel_id="C12345"
        )

        assert result is False
        notification_service.posting_handler._post_ephemeral.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_join_notification_ephemeral_posting_failure(self, notification_service):
        """Test handling of ephemeral posting failure."""
        # Make ephemeral posting fail
        notification_service.posting_handler._post_ephemeral.return_value = {
            "ok": False,
            "error": "channel_not_found",
        }

        result = await notification_service.send_join_notification(
            user_id="U12345", channel_id="C12345"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_collect_channel_data_success(self, notification_service):
        """Test successful channel data collection."""
        channel_data = await notification_service._collect_channel_data("C12345")

        assert channel_data is not None
        assert channel_data["channel_id"] == "C12345"
        assert channel_data["channel_name"] == "test-channel"
        assert "channel_details" in channel_data
        assert "messages" in channel_data
        assert "jira_context" in channel_data

        # Verify correct data collection calls
        notification_service.channel_info_ops.get_channel_info_from_api.assert_called_once_with(
            "C12345"
        )
        notification_service.channel_msg_ops.fetch_channel_messages.assert_called_once_with(
            channel_id="C12345", limit=999999999, use_parallel_pagination=True
        )
        notification_service.jira_extractor.get_jira_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_channel_data_not_member(self, notification_service):
        """Test channel data collection when bot is not a member."""
        # Make bot not a member
        notification_service.channel_info_ops.get_channel_info_from_api.return_value = {
            "name": "test-channel",
            "is_member": False,
        }

        channel_data = await notification_service._collect_channel_data("C12345")

        assert channel_data is None

    @pytest.mark.asyncio
    async def test_collect_channel_data_without_jira(self, service_without_jira):
        """Test channel data collection without JIRA extractor."""
        channel_data = await service_without_jira._collect_channel_data("C12345")

        assert channel_data is not None
        assert channel_data["jira_context"] == ""

    @pytest.mark.asyncio
    async def test_generate_notification_content_success(self, notification_service):
        """Test successful AI content generation."""
        channel_data = {
            "channel_details": {
                "customer_name": "Test Customer",
                "jira_ticket": "CPGNCX-12345",
                "product": "Test Product",
            },
            "messages": ["Test message 1", "Test message 2"],
            "jira_context": "Test JIRA context",
            "channel_id": "C12345",
            "channel_name": "test-channel",
        }

        content = await notification_service._generate_notification_content(channel_data)

        assert content is not None
        assert "Overview: Test channel is active" in content
        assert "What's been done / What's next:" in content

    @pytest.mark.asyncio
    async def test_generate_notification_content_invalid_response(self, notification_service):
        """Test AI content generation with invalid OpenAI response."""
        # Mock invalid response format
        notification_service.openai_handler._api_executor.execute_request.return_value = {
            "invalid": "response"
        }

        channel_data = {
            "channel_details": {
                "customer_name": "Test",
                "jira_ticket": "None",
                "product": "Test",
            },
            "messages": ["Test"],
            "jira_context": "",
            "channel_id": "C12345",
            "channel_name": "test",
        }

        content = await notification_service._generate_notification_content(channel_data)

        assert content is None

    def test_format_final_notification_with_jira(self, notification_service):
        """Test final notification formatting with JIRA ticket."""
        ai_content = "Overview: Test overview\n\nWhat's been done / What's next:\n• Bullet 1\n• Bullet 2\n• Bullet 3\n• Bullet 4"
        channel_data = {
            "channel_id": "C12345",
            "channel_name": "test-channel",
            "channel_details": {},
            "jira_ticket": "CPGNCX-12345",  # Now extracted from jira_context
        }
        user_profile = {"real_name": "John Doe"}

        with patch(
            "packages.slack.services.user_join_notification_service.datetime"
        ) as mock_datetime:
            # Mock specific datetime for consistent testing
            mock_datetime.now.return_value = datetime(2025, 1, 28, 15, 30, 0, tzinfo=timezone.utc)
            mock_datetime.strftime = datetime.strftime

            message = notification_service._format_final_notification(
                ai_content=ai_content,
                channel_data=channel_data,
                user_profile=user_profile,
            )

        # Verify exact format per plan specification
        assert message.startswith("👋 Hi *John!* Welcome to <#C12345|test-channel>!")
        assert (
            "Here's what's happening in this channel (Generated: 28-Jan-2025, 15:30 UTC)" in message
        )
        assert "Overview: Test overview" in message
        assert "• Bullet 1" in message
        assert (
            "JIRA Ticket: <https://jira.corp.adobe.com/browse/CPGNCX-12345|CPGNCX-12345>" in message
        )
        assert "Want more details? Try `/ketchup status` or `/ketchup report`" in message

    def test_format_final_notification_without_jira(self, notification_service):
        """Test final notification formatting without JIRA ticket."""
        ai_content = "Overview: Test overview\n\nWhat's been done / What's next:\n• Bullet 1"
        channel_data = {
            "channel_id": "C12345",
            "channel_name": "test-channel",
            "channel_details": {},
            "jira_ticket": "NOT YET AVAILABLE",  # Now at top level
        }

        message = notification_service._format_final_notification(
            ai_content=ai_content, channel_data=channel_data
        )

        # Should not include JIRA line for "NOT YET AVAILABLE"
        assert "JIRA Ticket:" not in message
        assert "👋 Hi *there!* Welcome to <#C12345|test-channel>!" in message

    def test_format_final_notification_first_name_extraction(self, notification_service):
        """Test first name extraction from user profile."""
        ai_content = "Test content"
        channel_data = {
            "channel_id": "C12345",
            "channel_name": "test",
            "channel_details": {},
        }

        # Test various name formats
        test_cases = [
            ({"real_name": "John Doe Smith"}, "John"),
            ({"real_name": "Sarah"}, "Sarah"),
            ({"real_name": ""}, "there"),
            ({}, "there"),
            ({"real_name": "  "}, "there"),
        ]

        for user_profile, expected_name in test_cases:
            message = notification_service._format_final_notification(
                ai_content=ai_content,
                channel_data=channel_data,
                user_profile=user_profile,
            )
            assert f"👋 Hi *{expected_name}!*" in message

    @pytest.mark.asyncio
    async def test_send_ephemeral_notification_success(self, notification_service):
        """Test successful ephemeral notification sending."""
        result = await notification_service._send_ephemeral_notification(
            user_id="U12345", channel_id="C12345", message="Test message"
        )

        assert result is True
        notification_service.posting_handler._post_ephemeral.assert_called_once_with(
            user_id="U12345", channel_id="C12345", message="Test message"
        )

    @pytest.mark.asyncio
    async def test_send_ephemeral_notification_failure(self, notification_service):
        """Test ephemeral notification failure handling."""
        # Mock failure response
        notification_service.posting_handler._post_ephemeral.return_value = {
            "ok": False,
            "error": "user_not_in_channel",
        }

        result = await notification_service._send_ephemeral_notification(
            user_id="U12345", channel_id="C12345", message="Test message"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_ephemeral_notification_exception(self, notification_service):
        """Test ephemeral notification exception handling."""
        # Mock exception during posting
        notification_service.posting_handler._post_ephemeral.side_effect = Exception(
            "Network error"
        )

        result = await notification_service._send_ephemeral_notification(
            user_id="U12345", channel_id="C12345", message="Test message"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_collect_channel_data_empty_messages(self, notification_service):
        """Test data collection with empty message list."""
        # Mock empty message list
        notification_service.channel_msg_ops.fetch_channel_messages.return_value = []

        channel_data = await notification_service._collect_channel_data("C12345")

        assert channel_data is not None
        assert channel_data["messages"] == ["(No messages found in channel)"]

    @pytest.mark.asyncio
    async def test_collect_channel_data_jira_enrichment_failure(self, notification_service):
        """Test data collection when JIRA enrichment fails."""
        # Make JIRA enrichment fail
        notification_service.jira_extractor.get_jira_context.side_effect = Exception(
            "JIRA API error"
        )

        channel_data = await notification_service._collect_channel_data("C12345")

        # Should continue without JIRA context
        assert channel_data is not None
        assert channel_data["jira_context"] == ""

    @pytest.mark.asyncio
    async def test_end_to_end_notification_workflow(self, notification_service):
        """Test complete end-to-end notification workflow."""
        user_profile = {"real_name": "Jane Smith"}

        result = await notification_service.send_join_notification(
            user_id="U12345", channel_id="C12345", user_profile=user_profile
        )

        assert result is True

        # Verify all steps called in correct order
        notification_service.channel_info_ops.get_channel_info_from_api.assert_called_once()
        notification_service.channel_msg_ops.fetch_channel_messages.assert_called_once()
        notification_service.jira_extractor.get_jira_context.assert_called_once()
        notification_service.openai_handler._api_executor.execute_request.assert_called_once()
        notification_service.posting_handler._post_ephemeral.assert_called_once()

        # Verify final message format
        call_args = notification_service.posting_handler._post_ephemeral.call_args
        final_message = call_args.kwargs["message"]

        assert "👋 Hi *Jane!* Welcome to <#C12345|test-channel>!" in final_message
        assert "Overview: Test channel is active" in final_message
        assert (
            "JIRA Ticket: <https://jira.corp.adobe.com/browse/CPGNCX-12345|CPGNCX-12345>"
            in final_message
        )
        assert "Want more details? Try `/ketchup status` or `/ketchup report`" in final_message

    @pytest.mark.asyncio
    async def test_notification_disabled_by_user_preference(self, notification_service):
        """Test that notification is skipped when user has disabled it."""
        # Set user preference to disabled
        notification_service.user_store.get_user.return_value = {
            "user_id": "U12345",
            "real_name": "John Doe",
            "preferences": {"join_notifications_enabled": "disabled"},
        }

        result = await notification_service.send_join_notification(
            user_id="U12345", channel_id="C12345"
        )

        # Should return True (success) but not send notification
        assert result is True
        notification_service.posting_handler._post_ephemeral.assert_not_called()

    @pytest.mark.asyncio
    async def test_notification_enabled_by_user_preference(self, notification_service):
        """Test that notification is sent when user has enabled it."""
        # User preference is already set to enabled in fixture

        result = await notification_service.send_join_notification(
            user_id="U12345", channel_id="C12345"
        )

        assert result is True
        notification_service.posting_handler._post_ephemeral.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_default_when_no_preference(self, notification_service):
        """Test that notification defaults to enabled when user has no preference."""
        # Set user with no preferences
        notification_service.user_store.get_user.return_value = {
            "user_id": "U12345",
            "real_name": "John Doe",
        }

        result = await notification_service.send_join_notification(
            user_id="U12345", channel_id="C12345"
        )

        # Should default to enabled and send notification
        assert result is True
        notification_service.posting_handler._post_ephemeral.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_without_user_store(
        self,
        mock_openai_handler,
        mock_posting_handler,
        mock_channel_info_ops,
        mock_channel_msg_ops,
        mock_jira_extractor,
    ):
        """Test that notification works when user_store is not available."""
        # Create service without user_store
        service = UserJoinNotificationService(
            openai_handler=mock_openai_handler,
            posting_handler=mock_posting_handler,
            channel_info_ops=mock_channel_info_ops,
            channel_msg_ops=mock_channel_msg_ops,
            jira_extractor=mock_jira_extractor,
            user_store=None,  # No user store
        )

        result = await service.send_join_notification(user_id="U12345", channel_id="C12345")

        # Should send notification when user_store is not available
        assert result is True
        mock_posting_handler._post_ephemeral.assert_called_once()
