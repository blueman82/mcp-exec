"""
Integration tests for the trust endorsement feature end-to-end flow.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.config.feature_flags import FeatureFlags
from packages.db.operations.trust_operations import TrustOperations
from packages.slack.interactive_elements.trust_endorsement_handler import (
    TrustEndorsementHandler,
)


@pytest.fixture
def mock_dynamodb_client():
    """Create a mock DynamoDB client."""
    client = MagicMock()
    client.put_item = AsyncMock()
    client.get_item = AsyncMock()
    client.update_item = AsyncMock()
    return client


@pytest.fixture
def mock_posting_handler():
    """Create a mock posting handler."""
    mock = MagicMock()
    mock.update_message = AsyncMock()
    return mock


@pytest.fixture
def real_trust_ops(mock_dynamodb_client):
    """Create a real TrustOperations instance with mocked client."""
    return TrustOperations(client=mock_dynamodb_client, table_name="test-table")


@pytest.fixture
def real_db_store(mock_dynamodb_client, real_trust_ops):
    """Create a real DynamoDBStore instance with trust_ops."""
    db_store = MagicMock()
    db_store.trust_ops = real_trust_ops
    return db_store


@pytest.fixture
def mock_secrets_manager():
    """Create a mock secrets manager."""
    mock = MagicMock()
    mock.get_slack_api_token_async = AsyncMock(return_value="xoxb-test-token")
    return mock


@pytest.fixture
def trust_handler(mock_posting_handler, real_db_store, mock_secrets_manager):
    """Create a real TrustEndorsementHandler with integration components."""
    return TrustEndorsementHandler(
        posting_handler=mock_posting_handler,
        db_store=real_db_store,
        secrets_manager=mock_secrets_manager,
    )


class TestTrustEndorsementIntegration:
    """Integration tests for trust endorsement feature."""

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_end_to_end_trust_flow(
        self,
        mock_feature_flag,
        trust_handler,
        mock_dynamodb_client,
        mock_posting_handler,
        real_db_store,
    ):
        """Test complete flow from status creation to trust endorsement."""
        # Step 1: Simulate storing status update metadata
        channel_id = "C094DQY7HLH"  # Test channel
        status_update_id = f"{int(datetime.now(datetime.UTC).timestamp())}_test1234"
        timestamp = int(status_update_id.split("_")[0])

        # Mock successful put for status metadata
        mock_dynamodb_client.put_item.return_value = {}

        result = await real_db_store.trust_ops.store_status_update_metadata(
            channel_id=channel_id,
            status_update_id=status_update_id,
            timestamp=timestamp,
            content_preview="Test status update",
        )
        assert result is True

        # Step 2: Simulate first user trusting the status
        user1_payload = {
            "user": {"id": "U123456", "name": "user1"},
            "actions": [{"action_id": "trust_status_update", "value": status_update_id}],
            "channel": {"id": channel_id},
            "message": {
                "ts": "1234567890.123456",
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Status update"},
                    },
                    {
                        "type": "actions",
                        "elements": [{"type": "button", "action_id": "trust_status_update"}],
                    },
                ],
            },
        }

        # Mock get_item to return the stored status
        mock_dynamodb_client.get_item.return_value = {
            "Item": {
                "PK": {"S": f"CHANNEL#{channel_id}"},
                "SK": {"S": f"STATUS#{timestamp}#test1234"},
                "status_update_id": {"S": status_update_id},
                "timestamp": {"N": str(timestamp)},
                "trust_count": {"N": "0"},
                "trusted_by": {"L": []},
            }
        }

        # Mock update_item to return updated trust data
        mock_dynamodb_client.update_item.return_value = {
            "Attributes": {
                "status_update_id": {"S": status_update_id},
                "timestamp": {"N": str(timestamp)},
                "trust_count": {"N": "1"},
                "trusted_by": {
                    "L": [
                        {
                            "M": {
                                "user_id": {"S": "U123456"},
                                "user_name": {"S": "user1"},
                                "trusted_at": {"N": str(timestamp)},
                            }
                        }
                    ]
                },
            }
        }

        # Process first trust
        result = await trust_handler.process_trust_action(user1_payload)
        assert result is True

        # Verify message was updated with trust count
        mock_posting_handler.update_message.assert_called_once()
        call_args = mock_posting_handler.update_message.call_args[1]
        blocks = call_args["blocks"]

        # Should have trust display block
        trust_display_blocks = [
            b for b in blocks if "✓ Trusted by:" in b.get("text", {}).get("text", "")
        ]
        assert len(trust_display_blocks) == 1
        assert "<@U123456>" in trust_display_blocks[0]["text"]["text"]

        # Step 3: Simulate second user trusting
        user2_payload = {
            "user": {"id": "U789012", "name": "user2"},
            "actions": [{"action_id": "trust_status_update", "value": status_update_id}],
            "channel": {"id": channel_id},
            "message": user1_payload["message"],
        }

        # Update mocks for second trust
        mock_dynamodb_client.get_item.return_value = {
            "Item": {
                "PK": {"S": f"CHANNEL#{channel_id}"},
                "SK": {"S": f"STATUS#{timestamp}#test1234"},
                "status_update_id": {"S": status_update_id},
                "timestamp": {"N": str(timestamp)},
                "trust_count": {"N": "1"},
                "trusted_by": {
                    "L": [
                        {
                            "M": {
                                "user_id": {"S": "U123456"},
                                "user_name": {"S": "user1"},
                                "trusted_at": {"N": str(timestamp)},
                            }
                        }
                    ]
                },
            }
        }

        mock_dynamodb_client.update_item.return_value = {
            "Attributes": {
                "status_update_id": {"S": status_update_id},
                "timestamp": {"N": str(timestamp)},
                "trust_count": {"N": "2"},
                "trusted_by": {
                    "L": [
                        {
                            "M": {
                                "user_id": {"S": "U123456"},
                                "user_name": {"S": "user1"},
                                "trusted_at": {"N": str(timestamp)},
                            }
                        },
                        {
                            "M": {
                                "user_id": {"S": "U789012"},
                                "user_name": {"S": "user2"},
                                "trusted_at": {"N": str(timestamp + 1)},
                            }
                        },
                    ]
                },
            }
        }

        # Reset mock
        mock_posting_handler.update_message.reset_mock()

        # Process second trust
        result = await trust_handler.process_trust_action(user2_payload)
        assert result is True

        # Verify message was updated with both users
        mock_posting_handler.update_message.assert_called_once()
        call_args = mock_posting_handler.update_message.call_args[1]
        blocks = call_args["blocks"]

        trust_display_blocks = [
            b for b in blocks if "✓ Trusted by:" in b.get("text", {}).get("text", "")
        ]
        assert len(trust_display_blocks) == 1
        trust_text = trust_display_blocks[0]["text"]["text"]
        assert "<@U789012>" in trust_text
        assert "<@U123456>" in trust_text

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_duplicate_trust_handling(
        self,
        mock_feature_flag,
        trust_handler,
        mock_dynamodb_client,
        mock_posting_handler,
    ):
        """Test that duplicate trusts from same user are handled correctly."""
        channel_id = "C094DQY7HLH"
        status_update_id = f"{int(datetime.now(datetime.UTC).timestamp())}_test5678"
        timestamp = int(status_update_id.split("_")[0])

        payload = {
            "user": {"id": "U123456", "name": "user1"},
            "actions": [{"action_id": "trust_status_update", "value": status_update_id}],
            "channel": {"id": channel_id},
            "message": {
                "ts": "1234567890.123456",
                "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": "Status"}},
                    {"type": "actions", "elements": [{"type": "button"}]},
                ],
            },
        }

        # Mock get_item to show user already trusted
        mock_dynamodb_client.get_item.return_value = {
            "Item": {
                "PK": {"S": f"CHANNEL#{channel_id}"},
                "SK": {"S": f"STATUS#{timestamp}#test5678"},
                "status_update_id": {"S": status_update_id},
                "timestamp": {"N": str(timestamp)},
                "trust_count": {"N": "1"},
                "trusted_by": {
                    "L": [
                        {
                            "M": {
                                "user_id": {"S": "U123456"},
                                "user_name": {"S": "user1"},
                                "trusted_at": {"N": str(timestamp)},
                            }
                        }
                    ]
                },
            }
        }

        # Process duplicate trust
        result = await trust_handler.process_trust_action(payload)
        assert result is True

        # Verify update_item was NOT called (no new trust to add)
        mock_dynamodb_client.update_item.assert_not_called()

        # Verify message was still updated but button removed
        mock_posting_handler.update_message.assert_called_once()
        call_args = mock_posting_handler.update_message.call_args[1]
        blocks = call_args["blocks"]

        # Should not have action block (button hidden for user who already trusted)
        action_blocks = [b for b in blocks if b.get("type") == "actions"]
        assert len(action_blocks) == 0

    @pytest.mark.asyncio
    @patch.object(FeatureFlags, "is_trust_endorsement_enabled", return_value=True)
    async def test_rate_limiting_integration(
        self, mock_feature_flag, trust_handler, mock_dynamodb_client
    ):
        """Test rate limiting prevents spam trusts."""
        user_id = "U_SPAMMER"
        channel_id = "C094DQY7HLH"

        # Create payload template
        def make_payload(status_id):
            return {
                "user": {"id": user_id, "name": "spammer"},
                "actions": [{"action_id": "trust_status_update", "value": status_id}],
                "channel": {"id": channel_id},
                "message": {"ts": "1234567890.123456", "blocks": []},
            }

        # Mock get_item to always return a valid status
        mock_dynamodb_client.get_item.return_value = {
            "Item": {
                "PK": {"S": f"CHANNEL#{channel_id}"},
                "SK": {"S": "STATUS#1234567890#test"},
                "status_update_id": {"S": "1234567890_test"},
                "timestamp": {"N": "1234567890"},
                "trust_count": {"N": "0"},
                "trusted_by": {"L": []},
            }
        }

        # Process 10 trust actions (should all succeed)
        for i in range(10):
            status_id = f"1234567890_test{i}"
            result = await trust_handler.process_trust_action(make_payload(status_id))
            assert result is True

        # 11th request should be rate limited
        result = await trust_handler.process_trust_action(make_payload("1234567890_test11"))
        assert result is True  # Still returns True but doesn't process

        # Verify no trust was added for rate-limited request
        # update_item should have been called 10 times, not 11
        assert mock_dynamodb_client.update_item.call_count == 10
