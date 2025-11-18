"""
Unit tests for AccessRequest model.

Tests the AccessRequest dataclass model for:
- Proper initialization and field validation
- DynamoDB serialization/deserialization
- TTL calculation
- Field defaults and optionals
"""

from unittest.mock import patch

from packages.db.models.access_request import AccessRequest


class TestAccessRequestModel:
    """Test suite for AccessRequest model."""

    def test_model_initialization_required_fields(self):
        """Test AccessRequest model initialization with required fields only."""
        # Test with minimum required fields
        request = AccessRequest(
            user_id="U123456789",
            user_name="test_user",
            user_email="test@adobe.com",
            request_timestamp=1640995200.0,  # 2022-01-01 00:00:00 UTC
            status="pending",
        )

        # Verify required fields
        assert request.user_id == "U123456789"
        assert request.user_name == "test_user"
        assert request.user_email == "test@adobe.com"
        assert request.request_timestamp == 1640995200.0
        assert request.status == "pending"

        # Verify optional fields have defaults
        assert request.reason_for_access is None
        assert request.decided_by_id is None
        assert request.decided_by_name is None
        assert request.decision_timestamp is None
        assert request.rejection_reason is None
        assert request.channel_ts is None
        assert request.response_url is None
        assert request.request_metadata == {}
        # TTL is auto-calculated in __post_init__, should not be None
        assert request.ttl is not None
        assert isinstance(request.ttl, int)
        assert request.ttl > 0

    def test_model_initialization_all_fields(self):
        """Test AccessRequest model initialization with all fields."""
        metadata = {"channel_type": "D", "retry_count": 0}

        request = AccessRequest(
            user_id="U123456789",
            user_name="test_user",
            user_email="test@adobe.com",
            request_timestamp=1640995200.0,
            status="approved",
            reason_for_access="Need access for incident response",
            decided_by_id="U987654321",
            decided_by_name="admin_user",
            decision_timestamp=1640995300.0,
            rejection_reason=None,
            channel_ts="1640995200.123456",
            response_url="https://hooks.slack.com/actions/...",
            request_metadata=metadata,
            ttl=1641081600,  # 24 hours later
        )

        # Verify all fields are set correctly
        assert request.user_id == "U123456789"
        assert request.user_name == "test_user"
        assert request.user_email == "test@adobe.com"
        assert request.request_timestamp == 1640995200.0
        assert request.status == "approved"
        assert request.reason_for_access == "Need access for incident response"
        assert request.decided_by_id == "U987654321"
        assert request.decided_by_name == "admin_user"
        assert request.decision_timestamp == 1640995300.0
        assert request.rejection_reason is None
        assert request.channel_ts == "1640995200.123456"
        assert request.response_url == "https://hooks.slack.com/actions/..."
        assert request.request_metadata == metadata
        assert request.ttl == 1641081600

    def test_to_item_conversion(self):
        """Test conversion to DynamoDB item format."""
        request = AccessRequest(
            user_id="U123456789",
            user_name="test_user",
            user_email="test@adobe.com",
            request_timestamp=1640995200.0,
            status="pending",
            reason_for_access="Test reason",
            request_metadata={"test": "value"},
        )

        item = request.to_item()

        # Verify item structure - DynamoDB format includes type descriptors
        assert isinstance(item, dict)
        assert item["PK"] == {"S": "USER#U123456789"}
        assert item["SK"] == {"S": "ACCESS_REQUEST#1640995200.0"}
        assert item["user_id"] == {"S": "U123456789"}
        assert item["user_name"] == {"S": "test_user"}
        assert item["user_email"] == {"S": "test@adobe.com"}
        assert item["request_timestamp"] == {"N": "1640995200.0"}
        assert item["status"] == {"S": "pending"}
        assert item["reason_for_access"] == {"S": "Test reason"}
        assert item["request_metadata"] == {"S": '{"test": "value"}'}

        # Verify None values are NOT included in the item
        assert "decided_by_id" not in item
        assert "decided_by_name" not in item
        assert "decision_timestamp" not in item
        assert "rejection_reason" not in item
        assert "channel_ts" not in item
        assert "response_url" not in item
        assert "ttl" in item  # TTL is auto-calculated, should be present

    def test_from_item_conversion(self):
        """Test conversion from DynamoDB item format."""
        item = {
            "user_id": "U123456789",
            "user_name": "test_user",
            "user_email": "test@adobe.com",
            "request_timestamp": 1640995200.0,
            "status": "approved",
            "reason_for_access": "Test reason",
            "decided_by_id": "U987654321",
            "decided_by_name": "admin_user",
            "decision_timestamp": 1640995300.0,
            "request_metadata": '{"test": "value"}',  # Should be JSON string
            "ttl": 1641081600,
        }

        request = AccessRequest.from_item(item)

        # Verify all fields are correctly restored
        assert request.user_id == "U123456789"
        assert request.user_name == "test_user"
        assert request.user_email == "test@adobe.com"
        assert request.request_timestamp == 1640995200.0
        assert request.status == "approved"
        assert request.reason_for_access == "Test reason"
        assert request.decided_by_id == "U987654321"
        assert request.decided_by_name == "admin_user"
        assert request.decision_timestamp == 1640995300.0
        assert request.request_metadata == {"test": "value"}
        assert request.ttl == 1641081600

        # Verify missing fields get None defaults
        assert request.rejection_reason is None
        assert request.channel_ts is None
        assert request.response_url is None

    def test_from_item_without_user_email(self):
        """Test conversion from DynamoDB item without user_email field."""
        item = {
            "user_id": {"S": "U123456789"},
            "user_name": {"S": "test_user"},
            "request_timestamp": {"N": "1640995200.0"},
            "status": {"S": "pending"},
            "ttl": {"N": "1641081600"},
        }

        request = AccessRequest.from_item(item)

        # Verify fields are correctly restored
        assert request.user_id == "U123456789"
        assert request.user_name == "test_user"
        assert request.user_email is None  # Should be None when not in item
        assert request.request_timestamp == 1640995200.0
        assert request.status == "pending"
        assert request.ttl == 1641081600

    def test_round_trip_serialization(self):
        """Test that to_item() and from_item() are inverse operations."""
        original = AccessRequest(
            user_id="U123456789",
            user_name="test_user",
            user_email="test@adobe.com",
            request_timestamp=1640995200.0,
            status="pending",
            reason_for_access="Test reason",
            request_metadata={"nested": {"key": "value"}},
        )

        # Convert to item and back
        item = original.to_item()
        restored = AccessRequest.from_item(item)

        # Should be identical
        assert original.user_id == restored.user_id
        assert original.user_name == restored.user_name
        assert original.user_email == restored.user_email
        assert original.request_timestamp == restored.request_timestamp
        assert original.status == restored.status
        assert original.reason_for_access == restored.reason_for_access
        assert original.request_metadata == restored.request_metadata

        # Optional fields should match too
        assert original.decided_by_id == restored.decided_by_id
        assert original.decided_by_name == restored.decided_by_name
        assert original.decision_timestamp == restored.decision_timestamp
        assert original.rejection_reason == restored.rejection_reason
        assert original.channel_ts == restored.channel_ts
        assert original.response_url == restored.response_url
        assert original.ttl == restored.ttl

    def test_ttl_calculation_in_post_init(self):
        """Test that TTL is calculated automatically in __post_init__."""
        # Mock time to ensure predictable TTL calculation
        with patch(
            "packages.db.models.access_request.time.time", return_value=1640995200.0
        ):
            request = AccessRequest(
                user_id="U123456789",
                user_name="test_user",
                user_email="test@adobe.com",
                request_timestamp=1640995200.0,
                status="pending",
            )

            # TTL should be set to 24 hours from now
            expected_ttl = int(1640995200.0 + (24 * 60 * 60))  # +24 hours
            assert request.ttl == expected_ttl

    def test_ttl_not_overridden_if_set(self):
        """Test that TTL is not overridden if explicitly set."""
        explicit_ttl = 1641081600  # Some future timestamp

        request = AccessRequest(
            user_id="U123456789",
            user_name="test_user",
            user_email="test@adobe.com",
            request_timestamp=1640995200.0,
            status="pending",
            ttl=explicit_ttl,
        )

        # TTL should remain as explicitly set
        assert request.ttl == explicit_ttl

    def test_status_values(self):
        """Test that different status values are accepted."""
        valid_statuses = ["pending", "approved", "rejected", "expired"]

        for status in valid_statuses:
            request = AccessRequest(
                user_id="U123456789",
                user_name="test_user",
                user_email="test@adobe.com",
                request_timestamp=1640995200.0,
                status=status,
            )
            assert request.status == status

    def test_metadata_dictionary_handling(self):
        """Test that metadata dictionary is handled correctly."""
        # Test with nested dictionary
        complex_metadata = {
            "channel_type": "D",
            "retry_count": 3,
            "source": "command_router",
            "nested": {"key1": "value1", "key2": ["item1", "item2"]},
        }

        request = AccessRequest(
            user_id="U123456789",
            user_name="test_user",
            user_email="test@adobe.com",
            request_timestamp=1640995200.0,
            status="pending",
            request_metadata=complex_metadata,
        )

        # Verify metadata is stored correctly
        assert request.request_metadata == complex_metadata
        assert request.request_metadata["channel_type"] == "D"
        assert request.request_metadata["retry_count"] == 3
        assert request.request_metadata["nested"]["key1"] == "value1"
        assert request.request_metadata["nested"]["key2"] == ["item1", "item2"]

    def test_email_validation_format(self):
        """Test that email format is preserved correctly."""
        test_emails = [
            "test@adobe.com",
            "test.user@adobe.com",
            "test+tag@adobe.com",
            "test-user@subdomain.adobe.com",
        ]

        for email in test_emails:
            request = AccessRequest(
                user_id="U123456789",
                user_name="test_user",
                user_email=email,
                request_timestamp=1640995200.0,
                status="pending",
            )
            assert request.user_email == email

    def test_primary_key_generation(self):
        """Test that PK and SK are generated correctly in to_item()."""
        request = AccessRequest(
            user_id="U123456789",
            user_name="test_user",
            user_email="test@adobe.com",
            request_timestamp=1640995200.0,
            status="pending",
        )

        item = request.to_item()

        # Should generate PK and SK based on user_id and timestamp
        assert item["PK"] == {"S": "USER#U123456789"}
        assert item["SK"] == {"S": "ACCESS_REQUEST#1640995200.0"}

    def test_key_uniqueness(self):
        """Test that PK/SK combinations are unique for different users/times."""
        request1 = AccessRequest(
            user_id="U123456789",
            user_name="test_user1",
            user_email="test1@adobe.com",
            request_timestamp=1640995200.0,
            status="pending",
        )

        request2 = AccessRequest(
            user_id="U987654321",
            user_name="test_user2",
            user_email="test2@adobe.com",
            request_timestamp=1640995200.0,
            status="pending",
        )

        request3 = AccessRequest(
            user_id="U123456789",
            user_name="test_user1",
            user_email="test1@adobe.com",
            request_timestamp=1640995300.0,
            status="pending",
        )

        # All should have different PK/SK combinations
        item1 = request1.to_item()
        item2 = request2.to_item()
        item3 = request3.to_item()

        # Different users, same time - different PK
        assert item1["PK"] != item2["PK"]
        assert item1["SK"] == item2["SK"]  # Same time, same SK prefix

        # Same user, different time - same PK, different SK
        assert item1["PK"] == item3["PK"]
        assert item1["SK"] != item3["SK"]
