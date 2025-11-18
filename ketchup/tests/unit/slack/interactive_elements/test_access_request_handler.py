"""
Test access request interactive handler.
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from packages.core.constants import ACCESS_REQUEST_CHANNEL, ACCESS_REQUEST_STATUS
from packages.db.models.access_request import AccessRequest
from packages.slack.interactive_elements.access_request_handler import (
    AccessRequestHandler,
)


class TestAccessRequestHandler:
    """Test AccessRequestHandler class."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies."""
        slack_client = Mock()
        slack_client.api_call = AsyncMock()
        slack_client._make_api_request = AsyncMock()
        slack_client.get_api_base_url = AsyncMock(return_value="https://slack.com/api")
        slack_client.headers = {}

        access_request_ops = Mock()
        access_request_ops.create_request_with_validation = AsyncMock()
        access_request_ops.update_request_decision = AsyncMock()
        access_request_ops._table = Mock()
        access_request_ops._table.update_item = AsyncMock()
        access_request_ops.client = Mock()
        access_request_ops.client.update_item = AsyncMock()

        secrets_manager = Mock()
        secrets_manager.add_authorized_user = AsyncMock()

        metrics_service = Mock()
        metrics_service.increment_metric = AsyncMock()

        distributed_lock = Mock()

        return {
            "slack_client": slack_client,
            "access_request_ops": access_request_ops,
            "secrets_manager": secrets_manager,
            "metrics_service": metrics_service,
            "distributed_lock": distributed_lock,
        }

    @pytest.fixture
    def handler(self, mock_dependencies):
        """Create AccessRequestHandler instance."""
        return AccessRequestHandler(**mock_dependencies)

    @pytest.fixture
    def sample_payload(self):
        """Create a sample Slack payload."""
        return {
            "user": {"id": "U123456", "name": "testuser"},
            "channel": {"id": "C789012"},
            "message": {
                "ts": "1234567890.123456",
                "blocks": [{"type": "section", "text": {"text": "Original message"}}],
            },
            "trigger_id": "12345.67890.abcdef",
            "actions": [{"action_id": "request_access", "value": "U123456"}],
        }

    @pytest.mark.asyncio
    async def test_handle_request_access_success(
        self, handler, mock_dependencies, sample_payload
    ):
        """Test successful access request creation."""
        # Setup mocks - mock both api_call and _make_api_request for different parts
        mock_dependencies["slack_client"].api_call.return_value = {
            "ok": True,
            "ts": "1234567890.123456",
        }
        mock_dependencies["slack_client"]._make_api_request.return_value = {
            "body": '{"ok": true, "user": {"profile": {"email": "test@example.com"}}}',
            "status": 200,
        }

        created_request = AccessRequest(
            user_id="U123456",
            user_name="testuser",
            user_email="test@example.com",
            request_timestamp=time.time(),
            status=ACCESS_REQUEST_STATUS["PENDING"],
        )

        mock_dependencies[
            "access_request_ops"
        ].create_request_with_validation.return_value = (
            True,
            "Request created successfully",
            created_request,
        )

        # Execute
        response = await handler.handle_request_access(sample_payload)

        # Verify
        assert response["response_type"] == "ephemeral"
        assert "✅" in response["text"]
        assert "submitted" in response["text"]

        # Check that user info was fetched via direct API request
        mock_dependencies["slack_client"]._make_api_request.assert_called_once()

        # Check that notification was posted
        mock_dependencies["slack_client"].api_call.assert_any_call(
            "chat.postMessage",
            {
                "channel": ACCESS_REQUEST_CHANNEL,
                "blocks": mock_dependencies["slack_client"].api_call.call_args_list[-1][
                    0
                ][1]["blocks"],
                "text": "New access request from testuser",
            },
        )

        # Check metrics
        mock_dependencies["metrics_service"].increment_metric.assert_called_with(
            "created", user_id="U123456", user_name="testuser"
        )

    @pytest.mark.asyncio
    async def test_handle_request_access_rate_limited(
        self, handler, mock_dependencies, sample_payload
    ):
        """Test rate limited access request."""
        mock_dependencies[
            "access_request_ops"
        ].create_request_with_validation.return_value = (
            False,
            "Too many requests. Please try again later.",
            None,
        )

        response = await handler.handle_request_access(sample_payload)

        assert response["response_type"] == "ephemeral"
        assert "Too many requests" in response["text"]

        mock_dependencies["metrics_service"].increment_metric.assert_called_with(
            "rate_limited", user_id="U123456"
        )

    @pytest.mark.asyncio
    async def test_handle_request_access_duplicate(
        self, handler, mock_dependencies, sample_payload
    ):
        """Test duplicate request handling."""
        mock_dependencies[
            "access_request_ops"
        ].create_request_with_validation.return_value = (
            False,
            "You already have a pending request.",
            None,
        )

        response = await handler.handle_request_access(sample_payload)

        assert response["response_type"] == "ephemeral"
        assert "already have a pending request" in response["text"]

        mock_dependencies["metrics_service"].increment_metric.assert_called_with(
            "duplicate", user_id="U123456"
        )

    @pytest.mark.asyncio
    async def test_handle_approve_access_success(self, handler, mock_dependencies):
        """Test successful access approval."""
        payload = {
            "user": {"id": "U789", "name": "approver"},
            "channel": {"id": ACCESS_REQUEST_CHANNEL},
            "message": {"ts": "1234567890.123456", "blocks": [{"type": "section"}]},
            "actions": [{"value": "U123456|1234567890.0"}],
        }

        # Mock distributed lock
        mock_lock_context = MagicMock()
        mock_lock_context.__aenter__ = AsyncMock(return_value=True)
        mock_lock_context.__aexit__ = AsyncMock()
        mock_dependencies["distributed_lock"].acquire_lock = Mock(
            return_value=mock_lock_context
        )

        # Mock update success
        mock_dependencies["access_request_ops"].update_request_decision.return_value = (
            True,
            "Request updated successfully",
        )

        # Mock secrets manager
        mock_dependencies["secrets_manager"].add_authorized_user.return_value = True

        # Mock Slack API calls
        mock_dependencies["slack_client"].api_call.return_value = {
            "ok": True,
            "channel": {"id": "D123456"},
        }

        # Execute
        response = await handler.handle_approve_access(payload)

        # Verify
        assert response["response_type"] == "ephemeral"
        assert "✅" in response["text"]
        assert "approved" in response["text"].lower()
        assert "<@U123456>" in response["text"]

        # Check that user was added to authorized list
        mock_dependencies[
            "secrets_manager"
        ].add_authorized_user.assert_called_once_with("U123456")

        # Check that DM was sent
        dm_calls = [
            call
            for call in mock_dependencies["slack_client"].api_call.call_args_list
            if call[0][0] == "conversations.open"
        ]
        assert len(dm_calls) > 0

        # Check metrics
        mock_dependencies["metrics_service"].increment_metric.assert_called_with(
            "approved", user_id="U123456", approver_id="U789"
        )

    @pytest.mark.asyncio
    async def test_handle_approve_access_lock_failed(self, handler, mock_dependencies):
        """Test approval when lock acquisition fails."""
        payload = {
            "user": {"id": "U789", "name": "approver"},
            "actions": [{"value": "U123456|1234567890.0"}],
        }

        # Mock distributed lock failure
        mock_lock_context = MagicMock()
        mock_lock_context.__aenter__ = AsyncMock(return_value=False)
        mock_lock_context.__aexit__ = AsyncMock()
        mock_dependencies["distributed_lock"].acquire_lock = Mock(
            return_value=mock_lock_context
        )

        response = await handler.handle_approve_access(payload)

        assert response["response_type"] == "ephemeral"
        assert "Another approver is processing" in response["text"]

    @pytest.mark.asyncio
    async def test_handle_reject_access(self, handler, mock_dependencies):
        """Test opening rejection modal."""
        payload = {
            "trigger_id": "12345.67890.abcdef",
            "message": {"blocks": [{"type": "section"}], "ts": "1234567890.123456"},
            "actions": [{"value": "U123456|1234567890.0"}],
        }

        await handler.handle_reject_access(payload)

        # Check that modal was opened
        modal_calls = [
            call
            for call in mock_dependencies["slack_client"].api_call.call_args_list
            if call[0][0] == "views.open"
        ]
        assert len(modal_calls) == 1

        modal_call = modal_calls[0][0][1]
        assert modal_call["trigger_id"] == "12345.67890.abcdef"
        assert modal_call["view"]["callback_id"] == "reject_reason_modal"

        # Check private metadata
        private_metadata = json.loads(modal_call["view"]["private_metadata"])
        assert private_metadata["user_id"] == "U123456"
        assert private_metadata["request_timestamp"] == "1234567890.0"

    @pytest.mark.asyncio
    async def test_handle_rejection_submission(self, handler, mock_dependencies):
        """Test rejection modal submission."""
        payload = {
            "user": {"id": "U789", "name": "rejector"},
            "view": {
                "state": {
                    "values": {
                        "reason_block": {
                            "reason_input": {"value": "Not eligible for access"}
                        }
                    }
                },
                "private_metadata": json.dumps(
                    {
                        "user_id": "U123456",
                        "request_timestamp": "1234567890.0",
                        "channel_ts": "1234567890.123456",
                        "original_blocks": [{"type": "section"}],
                    }
                ),
            },
        }

        # Mock update success
        mock_dependencies["access_request_ops"].update_request_decision.return_value = (
            True,
            "Request updated successfully",
        )

        # Mock Slack API calls
        mock_dependencies["slack_client"].api_call.return_value = {
            "ok": True,
            "channel": {"id": "D123456"},
        }

        response = await handler.handle_rejection_submission(payload)

        assert response["response_type"] == "clear"

        # Check that rejection was recorded
        mock_dependencies[
            "access_request_ops"
        ].update_request_decision.assert_called_once_with(
            user_id="U123456",
            request_timestamp=1234567890.0,
            decision=ACCESS_REQUEST_STATUS["REJECTED"],
            decided_by_id="U789",
            decided_by_name="rejector",
            rejection_reason="Not eligible for access",
        )

        # Check that DM was sent
        dm_calls = [
            call
            for call in mock_dependencies["slack_client"].api_call.call_args_list
            if call[0][0] == "chat.postMessage" and "rejected" in str(call[0][1])
        ]
        assert len(dm_calls) > 0

        # Check metrics
        mock_dependencies["metrics_service"].increment_metric.assert_called_with(
            "rejected", user_id="U123456", rejector_id="U789"
        )

    @pytest.mark.asyncio
    async def test_handle_request_access_error_handling(
        self, handler, mock_dependencies, sample_payload
    ):
        """Test error handling in request access."""
        # Mock an exception
        mock_dependencies[
            "access_request_ops"
        ].create_request_with_validation.side_effect = Exception("DB Error")

        response = await handler.handle_request_access(sample_payload)

        assert response["response_type"] == "ephemeral"
        assert "❌" in response["text"]
        assert "error occurred" in response["text"].lower()

        mock_dependencies["metrics_service"].increment_metric.assert_called_with(
            "error", user_id="U123456", error="DB Error"
        )
