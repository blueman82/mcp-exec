"""
Unit tests for TrustEndorsementHandler
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.config.feature_flags import FeatureFlags
from packages.slack.interactive_elements.trust_endorsement_handler import (
    TrustEndorsementHandler,
)
from tests.unit.test_utils.aiohttp_helpers import (
    MockAiohttpResponse,
    create_mock_session_class,
)


@pytest.fixture
def mock_posting_handler():
    """Create a mock posting handler."""
    mock = MagicMock()
    mock.update_message = AsyncMock()
    return mock


@pytest.fixture
def mock_db_store():
    """Create a mock database store."""
    mock = MagicMock()
    mock.trust_ops = MagicMock()
    mock.trust_ops.add_trust_endorsement = AsyncMock()
    mock.trust_ops.add_command_trust_endorsement = AsyncMock()
    mock.table_name = "test-table"
    return mock


@pytest.fixture
def mock_secrets_manager():
    """Create a mock secrets manager."""
    mock = MagicMock()
    mock.get_slack_api_token_async = AsyncMock(return_value="xoxb-test-token")
    return mock


@pytest.fixture
def trust_handler(mock_posting_handler, mock_db_store, mock_secrets_manager):
    """Create a TrustEndorsementHandler instance with mocked dependencies."""
    handler = TrustEndorsementHandler(
        posting_handler=mock_posting_handler,
        db_store=mock_db_store,
        secrets_manager=mock_secrets_manager,
    )
    return handler


@pytest.fixture
def sample_payload():
    """Create a sample Slack interactive payload."""
    return {
        "user": {"id": "U123456", "name": "testuser"},
        "actions": [{"action_id": "trust_status_update", "value": "1234567890_abcd1234"}],
        "channel": {"id": "C123456"},
        "message": {
            "ts": "1234567890.123456",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Status update content"},
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✓ Trust this summary",
                            },
                            "action_id": "trust_status_update",
                            "value": "1234567890_abcd1234",
                        }
                    ],
                },
            ],
        },
    }


class TestTrustEndorsementHandler:
    """Test cases for TrustEndorsementHandler."""

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_process_trust_action_success(
        self,
        mock_feature_flag,
        trust_handler,
        sample_payload,
        mock_db_store,
        mock_posting_handler,
    ):
        """Test successful trust endorsement."""
        # Mock the trust data response
        mock_trust_data = {
            "status_update_id": "1234567890_abcd1234",
            "trusted_by": [
                {
                    "user_id": "U123456",
                    "user_name": "testuser",
                    "trusted_at": int(datetime.now(timezone.utc).timestamp()),
                }
            ],
            "trust_count": 1,
            "user_already_trusted": False,
        }
        mock_db_store.trust_ops.add_trust_endorsement.return_value = mock_trust_data

        # Process the trust action
        result = await trust_handler.process_trust_action(sample_payload)

        # Verify success
        assert result is True

        # Verify trust endorsement was added
        mock_db_store.trust_ops.add_trust_endorsement.assert_called_once_with(
            channel_id="C123456",
            status_update_id="1234567890_abcd1234",
            user_id="U123456",
            user_name="testuser",
        )

        # Verify message was updated
        mock_posting_handler.update_message.assert_called_once()
        call_args = mock_posting_handler.update_message.call_args[1]
        assert call_args["channel_id"] == "C123456"
        assert call_args["ts"] == "1234567890.123456"
        assert call_args["message"] == ""
        assert len(call_args["blocks"]) > 0

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_process_trust_action_already_trusted(
        self,
        mock_feature_flag,
        trust_handler,
        sample_payload,
        mock_db_store,
        mock_posting_handler,
    ):
        """Test trust endorsement when user already trusted."""
        # Mock response indicating user already trusted
        mock_trust_data = {
            "status_update_id": "1234567890_abcd1234",
            "trusted_by": [
                {
                    "user_id": "U123456",
                    "user_name": "testuser",
                    "trusted_at": 1234567890,
                }
            ],
            "trust_count": 1,
            "user_already_trusted": True,
        }
        mock_db_store.trust_ops.add_trust_endorsement.return_value = mock_trust_data

        # Process the trust action
        result = await trust_handler.process_trust_action(sample_payload)

        # Verify success
        assert result is True

        # Verify message was NOT updated (user already trusted)
        mock_posting_handler.update_message.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=False)
    async def test_process_trust_action_feature_disabled(
        self, mock_feature_flag, trust_handler, sample_payload, mock_db_store
    ):
        """Test trust endorsement when feature is disabled."""
        result = await trust_handler.process_trust_action(sample_payload)

        # Should return False when feature is disabled
        assert result is False
        mock_db_store.trust_ops.add_trust_endorsement.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_process_trust_action_missing_data(self, mock_feature_flag, trust_handler):
        """Test trust endorsement with missing required data."""
        invalid_payload = {
            "user": {"id": "U123456"},
            "actions": [{"value": ""}],  # Missing status_update_id
            "channel": {"id": "C123456"},
            "message": {"ts": "1234567890.123456"},
        }

        result = await trust_handler.process_trust_action(invalid_payload)

        # Should return False due to missing data
        assert result is False

    def test_check_rate_limit(self, trust_handler):
        """Test rate limiting functionality."""
        user_id = "U123456"

        # Should allow first 10 requests
        for i in range(10):
            assert trust_handler._check_rate_limit(user_id) is True

        # 11th request should be blocked
        assert trust_handler._check_rate_limit(user_id) is False

    def test_format_trust_display(self, trust_handler):
        """Test trust display formatting."""
        # Test with no trusts
        result = trust_handler._format_trust_display([])
        assert result["display"] == ""
        assert result["user_already_trusted"] is False

        # Test with 1-3 trusts
        trusted_by = [
            {"user_id": "U123", "user_name": "user1", "trusted_at": 1234567890},
            {"user_id": "U456", "user_name": "user2", "trusted_at": 1234567891},
        ]
        result = trust_handler._format_trust_display(trusted_by)
        assert "✓ Trusted by: <@U456>, <@U123>" in result["display"]
        assert result["count"] == 2

        # Test with more than 3 trusts
        trusted_by = [
            {"user_id": "U123", "user_name": "user1", "trusted_at": 1234567890},
            {"user_id": "U456", "user_name": "user2", "trusted_at": 1234567891},
            {"user_id": "U789", "user_name": "user3", "trusted_at": 1234567892},
            {"user_id": "U012", "user_name": "user4", "trusted_at": 1234567893},
            {"user_id": "U345", "user_name": "user5", "trusted_at": 1234567894},
        ]
        result = trust_handler._format_trust_display(trusted_by)
        assert "✓ Trusted by:" in result["display"]
        assert ", +2" in result["display"]
        assert result["count"] == 5

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_update_message_with_trust(
        self, mock_feature_flag, trust_handler, mock_posting_handler
    ):
        """Test message update with trust display."""
        message_blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Status content"}},
            {
                "type": "actions",
                "elements": [{"type": "button", "action_id": "trust_status_update"}],
            },
        ]

        await trust_handler._update_message_with_trust(
            channel_id="C123456",
            message_ts="1234567890.123456",
            message_blocks=message_blocks,
            trust_display="✓ Trusted by: @user1, @user2",
            show_button=True,
        )

        # Verify update was called
        mock_posting_handler.update_message.assert_called_once()
        call_args = mock_posting_handler.update_message.call_args[1]

        # Verify trust display was added
        blocks = call_args["blocks"]
        trust_blocks = [b for b in blocks if "✓ Trusted by:" in b.get("text", {}).get("text", "")]
        assert len(trust_blocks) == 1

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_process_command_trust_action_first_time(
        self, mock_feature_flag, trust_handler, mock_db_store, mock_secrets_manager
    ):
        """Test processing command trust action for first-time trust."""
        # Setup mock response for modal API call
        mock_response = MockAiohttpResponse(status=200, json_data={"ok": True})

        # Patch aiohttp.ClientSession with proper mock
        with patch("aiohttp.ClientSession", create_mock_session_class({"post": mock_response})):
            # Setup trust data response
            mock_db_store.trust_ops.add_command_trust_endorsement.return_value = {
                "trust_count": 1,
                "user_already_trusted": False,
                "trusted_by": [{"user_id": "U123456", "user_name": "testuser"}],
            }

            # Setup command execution lookup
            mock_scan_response = {
                "Items": [{"PK": {"S": "CHANNEL#C789012"}, "channel_id": {"S": "C789012"}}]
            }
            mock_underlying_client = AsyncMock()
            mock_underlying_client.scan = AsyncMock(return_value=mock_scan_response)
            mock_db_store.client = MagicMock()
            mock_db_store.client._get_client = AsyncMock(return_value=mock_underlying_client)

            # Create payload with trigger_id
            payload = {
                "user": {"id": "U123456", "name": "testuser"},
                "actions": [{"value": "1234567890_abcd1234"}],
                "channel": {"id": "C123456"},
                "trigger_id": "test_trigger_id_123",
            }

            result = await trust_handler.process_command_trust_action(payload)

            # Verify success
            assert result is True

            # Verify trust was recorded
            mock_db_store.trust_ops.add_command_trust_endorsement.assert_called_once()

            # We can't directly verify session.post since it's inside the mocked ClientSession
            # but we can verify the trust operation was successful

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_process_command_trust_action_already_trusted(
        self, mock_feature_flag, trust_handler, mock_db_store, mock_secrets_manager
    ):
        """Test processing command trust action when user already trusted."""
        # Setup mock response for modal API call
        mock_response = MockAiohttpResponse(status=200, json_data={"ok": True})

        # Patch aiohttp.ClientSession with proper mock
        with patch("aiohttp.ClientSession", create_mock_session_class({"post": mock_response})):
            # Setup trust data response - user already trusted
            mock_db_store.trust_ops.add_command_trust_endorsement.return_value = {
                "trust_count": 5,
                "user_already_trusted": True,
                "trusted_by": [{"user_id": "U123456", "user_name": "testuser"}],
            }

            # Setup command execution lookup
            mock_scan_response = {
                "Items": [{"PK": {"S": "CHANNEL#C789012"}, "channel_id": {"S": "C789012"}}]
            }
            mock_underlying_client = AsyncMock()
            mock_underlying_client.scan = AsyncMock(return_value=mock_scan_response)
            mock_db_store.client = MagicMock()
            mock_db_store.client._get_client = AsyncMock(return_value=mock_underlying_client)

            # Create payload with trigger_id
            payload = {
                "user": {"id": "U123456", "name": "testuser"},
                "actions": [{"value": "1234567890_abcd1234"}],
                "channel": {"id": "C123456"},
                "trigger_id": "test_trigger_id_456",
            }

            result = await trust_handler.process_command_trust_action(payload)

            # Verify success
            assert result is True

            # Verify the trust operation was called and returned user_already_trusted=True
            mock_db_store.trust_ops.add_command_trust_endorsement.assert_called_once()
            call_args = mock_db_store.trust_ops.add_command_trust_endorsement.call_args
            assert call_args[1]["user_id"] == "U123456"

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_process_command_trust_action_no_trigger_id(
        self, mock_feature_flag, trust_handler, mock_db_store
    ):
        """Test processing command trust action without trigger_id."""
        # Setup trust data response
        mock_db_store.trust_ops.add_command_trust_endorsement.return_value = {
            "trust_count": 1,
            "user_already_trusted": False,
            "trusted_by": [{"user_id": "U123456", "user_name": "testuser"}],
        }

        # Setup command execution lookup
        mock_scan_response = {
            "Items": [{"PK": {"S": "CHANNEL#C789012"}, "channel_id": {"S": "C789012"}}]
        }
        mock_underlying_client = AsyncMock()
        mock_underlying_client.scan = AsyncMock(return_value=mock_scan_response)
        mock_db_store.client = MagicMock()
        mock_db_store.client._get_client = AsyncMock(return_value=mock_underlying_client)

        # Create payload WITHOUT trigger_id
        payload = {
            "user": {"id": "U123456", "name": "testuser"},
            "actions": [{"value": "1234567890_abcd1234"}],
            "channel": {"id": "C123456"},
            # No trigger_id
        }

        result = await trust_handler.process_command_trust_action(payload)

        # Should still succeed even without modal
        assert result is True

        # Verify trust was recorded
        mock_db_store.trust_ops.add_command_trust_endorsement.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_trust_acknowledgment_modal_api_error(
        self, trust_handler, mock_secrets_manager
    ):
        """Test modal display when Slack API returns error."""
        # Setup mock response for modal API call with error
        mock_response = MockAiohttpResponse(
            status=200, json_data={"ok": False, "error": "invalid_trigger"}
        )

        with patch("aiohttp.ClientSession", create_mock_session_class({"post": mock_response})):
            result = await trust_handler._show_trust_acknowledgment_modal(
                trigger_id="invalid_trigger", already_trusted=False
            )

            # Should return False on API error
            assert result is False
