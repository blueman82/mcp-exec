"""
Integration tests for user preferences with join notification settings using real AWS DynamoDB.

These tests verify the end-to-end flow with actual AWS services:
1. User setting their join notification preference in the home tab
2. Preference being stored in real DynamoDB via UserStore
3. UserJoinNotificationService respecting the preference when sending notifications

Requires: AWS_PROFILE=campaign_prod_v7
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from packages.core.logging import setup_logger
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.user_store import UserStore
from packages.slack.home.home_utils import extract_preferences_from_state
from packages.slack.services.user_join_notification_service import (
    UserJoinNotificationService,
)

logger = setup_logger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestUserPreferencesRealAWS:
    """Integration tests for user preferences with real AWS DynamoDB."""

    # Test data
    TEST_TABLE_NAME = "ketchup_channel_information"
    TEST_USER_PREFIX = "U_TEST_JOIN_"

    @classmethod
    def generate_test_user_id(cls, suffix=""):
        """Generate unique test user ID."""
        return f"{cls.TEST_USER_PREFIX}{int(time.time())}_{suffix}"

    @pytest_asyncio.fixture
    async def aws_client(self):
        """Create real DynamoDB client."""
        if os.environ.get("AWS_PROFILE") != "campaign_prod_v7":
            pytest.skip("AWS_PROFILE must be set to campaign_prod_v7")

        client = DynamoDBAsyncClient()
        yield client

    @pytest_asyncio.fixture
    async def user_store(self, aws_client):
        """Create UserStore with real DynamoDB client."""
        return UserStore(client=aws_client, table_name=self.TEST_TABLE_NAME)

    async def cleanup_test_user(self, aws_client, user_id):
        """Clean up test user data from DynamoDB."""
        try:
            await aws_client.delete_item(
                table_name=self.TEST_TABLE_NAME,
                key={"PK": {"S": f"USER#{user_id}"}, "SK": {"S": "METADATA"}},
            )
            logger.info(f"Cleaned up test user: {user_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup test user {user_id}: {e}")

    async def test_store_and_retrieve_join_notification_preference(
        self, user_store, aws_client
    ):
        """Test storing and retrieving join notification preference in real DynamoDB."""
        user_id = self.generate_test_user_id("STORE_RETRIEVE")
        logger.info(f"Testing store/retrieve with user ID: {user_id}")

        try:
            # Create preferences with join notifications disabled
            preferences = {
                "join_notifications_enabled": "disabled",
                "product_focus": ["ajo", "aep"],
                "detail_level": "technical_details",
                "time_window": "past_2_hours",
            }

            # Store preferences in real DynamoDB
            await user_store.store_user_preferences(user_id, preferences)
            logger.info("Stored preferences in DynamoDB")

            # Wait for eventual consistency
            await asyncio.sleep(1)

            # Retrieve user data
            user_data = await user_store.get_user(user_id)

            # Verify preferences were stored correctly
            assert user_data is not None, "User data should exist"
            assert "preferences" in user_data, "User should have preferences"
            assert user_data["preferences"]["join_notifications_enabled"] == "disabled"
            assert user_data["preferences"]["product_focus"] == ["ajo", "aep"]
            assert user_data["preferences"]["detail_level"] == "technical_details"

            logger.info(
                "✅ Successfully stored and retrieved join notification preference"
            )

        finally:
            await self.cleanup_test_user(aws_client, user_id)

    async def test_preference_extraction_and_storage(self, user_store, aws_client):
        """Test extracting preference from home tab and storing in real DynamoDB."""
        user_id = self.generate_test_user_id("EXTRACT_STORE")
        logger.info(f"Testing extraction and storage with user ID: {user_id}")

        try:
            # Simulate home tab payload with join notifications disabled
            home_tab_payload = {
                "view": {
                    "state": {
                        "values": {
                            "join_notifications_enabled_selection": {
                                "join_notifications_enabled_select": {
                                    "selected_option": {"value": "disabled"}
                                }
                            },
                            "product_focus_selection": {
                                "product_focus_select": {
                                    "selected_option": {"value": "stock"}
                                }
                            },
                            "detail_level_selection": {
                                "detail_level_select": {
                                    "selected_option": {"value": "balanced"}
                                }
                            },
                            "time_window_selection": {
                                "time_window_select": {
                                    "selected_option": {"value": "past_24_hours"}
                                }
                            },
                        }
                    }
                }
            }

            # Extract preferences
            preferences = extract_preferences_from_state(home_tab_payload)
            assert preferences["join_notifications_enabled"] == "disabled"
            assert preferences["product_focus"] == ["stock"]

            # Store in real DynamoDB
            await user_store.store_user_preferences(user_id, preferences)

            # Wait for consistency
            await asyncio.sleep(1)

            # Retrieve and verify
            user_data = await user_store.get_user(user_id)
            assert user_data["preferences"]["join_notifications_enabled"] == "disabled"
            assert user_data["preferences"]["product_focus"] == ["stock"]

            logger.info("✅ Successfully extracted and stored preference from home tab")

        finally:
            await self.cleanup_test_user(aws_client, user_id)

    async def test_notification_service_respects_preference(
        self, user_store, aws_client
    ):
        """Test that notification service respects user preference from real DynamoDB."""
        user_id = self.generate_test_user_id("SERVICE_RESPECT")
        channel_id = "C_TEST_CHANNEL"
        logger.info(f"Testing service respect with user ID: {user_id}")

        try:
            # Store user preference with notifications disabled
            preferences = {
                "join_notifications_enabled": "disabled",
                "product_focus": ["all_products"],
                "detail_level": "balanced",
                "time_window": "past_24_hours",
            }
            await user_store.store_user_preferences(user_id, preferences)

            # Wait for consistency
            await asyncio.sleep(1)

            # Create mock dependencies for notification service
            mock_openai = AsyncMock()
            mock_openai.summarize_with_instructions = AsyncMock(
                return_value={"summary": "Test summary", "success": True}
            )

            mock_posting = AsyncMock()
            mock_posting.post_ephemeral = AsyncMock(return_value=True)

            mock_channel_info = AsyncMock()
            mock_channel_info.get_channel_info = AsyncMock(
                return_value={"channel_id": channel_id, "channel_name": "test-channel"}
            )

            mock_channel_msg = AsyncMock()
            mock_channel_msg.get_recent_messages = AsyncMock(return_value=[])

            # Create notification service with real user store
            service = UserJoinNotificationService(
                openai_handler=mock_openai,
                posting_handler=mock_posting,
                channel_info_ops=mock_channel_info,
                channel_msg_ops=mock_channel_msg,
                jira_extractor=None,
                user_store=user_store,
            )

            # Process join event
            result = await service.process_user_join(user_id, channel_id)

            # Verify notification was NOT sent (user has it disabled)
            assert result is True  # Success, but skipped due to preference
            mock_posting.post_ephemeral.assert_not_called()

            logger.info("✅ Service correctly respected disabled preference")

            # Now test with enabled preference
            user_id_enabled = self.generate_test_user_id("SERVICE_ENABLED")
            preferences["join_notifications_enabled"] = "enabled"
            await user_store.store_user_preferences(user_id_enabled, preferences)
            await asyncio.sleep(1)

            # Process join for enabled user
            result = await service.process_user_join(user_id_enabled, channel_id)

            # Verify notification WAS sent
            assert result is True
            mock_posting.post_ephemeral.assert_called_once()

            logger.info("✅ Service correctly sent notification for enabled preference")

            # Cleanup second user
            await self.cleanup_test_user(aws_client, user_id_enabled)

        finally:
            await self.cleanup_test_user(aws_client, user_id)

    async def test_default_behavior_new_user(self, user_store, aws_client):
        """Test default behavior for new user with no preferences in real DynamoDB."""
        user_id = self.generate_test_user_id("NEW_USER")
        channel_id = "C_TEST_CHANNEL"
        logger.info(f"Testing default behavior with user ID: {user_id}")

        try:
            # Verify user doesn't exist
            user_data = await user_store.get_user(user_id)
            assert user_data is None or "preferences" not in user_data

            # Create mock dependencies
            mock_openai = AsyncMock()
            mock_openai.summarize_with_instructions = AsyncMock(
                return_value={"summary": "Test summary", "success": True}
            )

            mock_posting = AsyncMock()
            mock_posting.post_ephemeral = AsyncMock(return_value=True)

            mock_channel_info = AsyncMock()
            mock_channel_info.get_channel_info = AsyncMock(
                return_value={"channel_id": channel_id, "channel_name": "test-channel"}
            )

            mock_channel_msg = AsyncMock()
            mock_channel_msg.get_recent_messages = AsyncMock(return_value=[])

            # Create service
            service = UserJoinNotificationService(
                openai_handler=mock_openai,
                posting_handler=mock_posting,
                channel_info_ops=mock_channel_info,
                channel_msg_ops=mock_channel_msg,
                jira_extractor=None,
                user_store=user_store,
            )

            # Process join event
            result = await service.process_user_join(user_id, channel_id)

            # Verify notification WAS sent (default is enabled)
            assert result is True
            mock_posting.post_ephemeral.assert_called_once()

            logger.info("✅ Default behavior correctly sends notification for new user")

        finally:
            await self.cleanup_test_user(aws_client, user_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_preference_flow_end_to_end():
    """Test complete end-to-end flow with real AWS DynamoDB."""
    if os.environ.get("AWS_PROFILE") != "campaign_prod_v7":
        pytest.skip("AWS_PROFILE must be set to campaign_prod_v7")

    client = DynamoDBAsyncClient()
    user_store = UserStore(client=client, table_name="ketchup_channel_information")
    user_id = f"U_TEST_E2E_{int(time.time())}"

    try:
        logger.info(f"Running end-to-end test with user ID: {user_id}")

        # Step 1: Extract preference from home tab
        payload = {
            "view": {
                "state": {
                    "values": {
                        "join_notifications_enabled_selection": {
                            "join_notifications_enabled_select": {
                                "selected_option": {"value": "disabled"}
                            }
                        },
                        "product_focus_selection": {
                            "product_focus_select": {
                                "selected_option": {"value": "all_products"}
                            }
                        },
                        "detail_level_selection": {
                            "detail_level_select": {
                                "selected_option": {"value": "balanced"}
                            }
                        },
                        "time_window_selection": {
                            "time_window_select": {
                                "selected_option": {"value": "past_24_hours"}
                            }
                        },
                    }
                }
            }
        }

        preferences = extract_preferences_from_state(payload)
        assert preferences["join_notifications_enabled"] == "disabled"

        # Step 2: Store in DynamoDB
        await user_store.store_user_preferences(user_id, preferences)
        await asyncio.sleep(1)

        # Step 3: Retrieve and verify
        user_data = await user_store.get_user(user_id)
        assert user_data["preferences"]["join_notifications_enabled"] == "disabled"

        # Step 4: Update preference to enabled
        preferences["join_notifications_enabled"] = "enabled"
        await user_store.store_user_preferences(user_id, preferences)
        await asyncio.sleep(1)

        # Step 5: Verify update
        user_data = await user_store.get_user(user_id)
        assert user_data["preferences"]["join_notifications_enabled"] == "enabled"

        logger.info("✅ End-to-end test completed successfully")

    finally:
        # Cleanup
        try:
            await client.delete_item(
                table_name="ketchup_channel_information",
                key={"PK": {"S": f"USER#{user_id}"}, "SK": {"S": "METADATA"}},
            )
            logger.info(f"Cleaned up test user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup: {e}")
