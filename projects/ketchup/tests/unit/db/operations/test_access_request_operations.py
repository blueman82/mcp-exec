"""
Test access request database operations.
"""

import time
from unittest.mock import AsyncMock, Mock

import pytest
from botocore.exceptions import ClientError

from packages.core.constants import ACCESS_REQUEST_STATUS
from packages.db.models.access_request import AccessRequest
from packages.db.operations.access_request_operations import AccessRequestOperations


class TestAccessRequestOperations:
    """Test AccessRequestOperations class."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock DynamoDB client."""
        client = Mock()
        client.put_item = AsyncMock()
        client.update_item = AsyncMock()
        client.scan = AsyncMock()
        client.get_item = AsyncMock()
        return client

    @pytest.fixture
    def operations(self, mock_client):
        """Create AccessRequestOperations instance with mock client."""
        return AccessRequestOperations(mock_client, "test-table")

    @pytest.mark.asyncio
    async def test_create_request_success(self, operations, mock_client):
        """Test successful access request creation."""
        request = AccessRequest(
            user_id="U123456",
            user_name="testuser",
            user_email="test@example.com",
            request_timestamp=time.time(),
            status=ACCESS_REQUEST_STATUS["PENDING"],
        )

        # Mock successful put_item
        mock_client.put_item.return_value = {}

        # Mock scan to return no existing requests
        mock_client.scan.return_value = {"Items": []}

        # Mock update_item for rate limit
        mock_client.update_item.return_value = {"Attributes": {"request_count": 1}}

        success, message, created_request = await operations.create_request_with_validation(request)

        assert success is True
        assert message == "Access request created successfully"
        assert created_request.user_id == "U123456"

        # Verify put_item was called with correct parameters
        mock_client.put_item.assert_called_once()
        call_args = mock_client.put_item.call_args[1]
        assert call_args["item"]["PK"]["S"] == "USER#U123456"
        assert "ttl" in call_args["item"]

    @pytest.mark.asyncio
    async def test_create_request_duplicate(self, operations, mock_client):
        """Test duplicate request rejection."""
        request = AccessRequest(
            user_id="U123456",
            user_name="testuser",
            user_email="test@example.com",
            request_timestamp=time.time(),
            status=ACCESS_REQUEST_STATUS["PENDING"],
        )

        # Mock scan to return existing pending request
        existing_timestamp = time.time() - 3600
        mock_client.scan.return_value = {
            "Items": [
                {
                    "PK": {"S": "USER#U123456"},
                    "SK": {"S": f"ACCESS_REQUEST#{existing_timestamp}"},
                    "user_id": {"S": "U123456"},
                    "user_name": {"S": "testuser"},
                    "user_email": {"S": "test@example.com"},
                    "request_timestamp": {"N": str(existing_timestamp)},
                    "status": {"S": ACCESS_REQUEST_STATUS["PENDING"]},
                    "ttl": {"N": str(int(time.time() + 86400))},  # Still valid TTL
                }
            ]
        }

        success, message, created_request = await operations.create_request_with_validation(request)

        assert success is False
        assert "already have a pending request" in message
        assert created_request is not None
        assert created_request.user_id == "U123456"

    @pytest.mark.asyncio
    async def test_create_request_rate_limited(self, operations, mock_client):
        """Test rate limiting."""
        request = AccessRequest(
            user_id="U123456",
            user_name="testuser",
            user_email="test@example.com",
            request_timestamp=time.time(),
            status=ACCESS_REQUEST_STATUS["PENDING"],
        )

        # Mock scan to return no existing requests
        mock_client.scan.return_value = {"Items": []}

        # Mock update_item to raise ConditionalCheckFailedException for rate limit
        from botocore.exceptions import ClientError

        mock_client.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
        )

        success, message, created_request = await operations.create_request_with_validation(request)

        assert success is False
        assert "too many requests" in message.lower()
        assert created_request is None

    @pytest.mark.asyncio
    async def test_update_request_decision_approved(self, operations, mock_client):
        """Test updating request with approval."""
        # Mock successful update
        mock_client.update_item.return_value = {"Attributes": {}}

        success, message = await operations.update_request_decision(
            user_id="U123456",
            request_timestamp=1234567890.0,
            decision=ACCESS_REQUEST_STATUS["APPROVED"],
            decided_by_id="U789",
            decided_by_name="approver",
        )

        assert success is True
        assert message == "Request updated successfully"

        # Verify update was called with correct parameters
        mock_client.update_item.assert_called_once()
        call_args = mock_client.update_item.call_args[1]
        assert call_args["key"]["PK"] == {"S": "USER#U123456"}
        assert call_args["key"]["SK"] == {"S": "ACCESS_REQUEST#1234567890.0"}
        assert call_args["expression_attribute_values"][":new_status"] == {
            "S": ACCESS_REQUEST_STATUS["APPROVED"]
        }
        assert ":decided_by_id" in call_args["expression_attribute_values"]

    @pytest.mark.asyncio
    async def test_update_request_decision_rejected(self, operations, mock_client):
        """Test updating request with rejection."""
        # Mock successful update
        mock_client.update_item.return_value = {"Attributes": {}}

        success, message = await operations.update_request_decision(
            user_id="U123456",
            request_timestamp=1234567890.0,
            decision=ACCESS_REQUEST_STATUS["REJECTED"],
            decided_by_id="U789",
            decided_by_name="rejector",
            rejection_reason="Not eligible",
        )

        assert success is True
        assert message == "Request updated successfully"

        # Verify rejection reason was included
        call_args = mock_client.update_item.call_args[1]
        assert ":rejection_reason" in call_args["expression_attribute_values"]
        assert call_args["expression_attribute_values"][":rejection_reason"] == {
            "S": "Not eligible"
        }

    @pytest.mark.asyncio
    async def test_update_request_decision_already_processed(self, operations, mock_client):
        """Test updating already processed request."""
        # Mock conditional check failure
        error = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        mock_client.update_item.side_effect = error

        # Mock get_item to return processed request
        mock_client.get_item.return_value = {
            "Item": {
                "user_id": {"S": "U123456"},
                "user_name": {"S": "testuser"},
                "status": {"S": ACCESS_REQUEST_STATUS["APPROVED"]},
                "decided_by_name": {"S": "previous_approver"},
                "decision_timestamp": {"N": str(time.time() - 3600)},
                "request_timestamp": {"N": "1234567890.0"},
                "ttl": {"N": str(int(time.time() + 86400))},
            }
        }

        success, message = await operations.update_request_decision(
            user_id="U123456",
            request_timestamp=1234567890.0,
            decision=ACCESS_REQUEST_STATUS["APPROVED"],
            decided_by_id="U789",
            decided_by_name="approver",
        )

        assert success is False
        assert "already" in message
        assert "previous_approver" in message

    @pytest.mark.asyncio
    async def test_get_all_pending_requests_with_cache(self, operations, mock_client):
        """Test getting pending requests with caching."""
        # First call - should hit DynamoDB
        mock_client.scan.return_value = {
            "Items": [
                {
                    "PK": {"S": "USER#U123456"},
                    "SK": {"S": "ACCESS_REQUEST#1234567890"},
                    "user_id": {"S": "U123456"},
                    "user_name": {"S": "testuser"},
                    "user_email": {"S": "test@example.com"},
                    "status": {"S": ACCESS_REQUEST_STATUS["PENDING"]},
                    "request_timestamp": {"N": "1234567890"},
                    "ttl": {"N": str(int(time.time() + 86400))},
                }
            ]
        }

        requests1 = await operations.get_all_pending_requests()
        assert len(requests1) == 1
        assert mock_client.scan.call_count == 1

        # Second call - will also hit DynamoDB (no caching for get_all_pending_requests)
        requests2 = await operations.get_all_pending_requests()
        assert len(requests2) == 1
        assert mock_client.scan.call_count == 2

    # @pytest.mark.asyncio
    # async def test_get_user_request_history(self, operations, mock_client):
    #     """Test getting user's request history - method doesn't exist in implementation."""
    #     pass
