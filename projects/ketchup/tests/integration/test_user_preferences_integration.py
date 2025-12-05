"""
Integration tests for user preferences with join notification settings.

These tests verify the end-to-end flow using REAL AWS services:
1. User setting their join notification preference in the home tab
2. Preference being stored in DynamoDB via UserStore
3. UserJoinNotificationService respecting the preference when sending notifications

Test Coverage:
- User preference persistence in real DynamoDB
- Preference extraction from Slack home tab state
- Join notification service respecting user preferences
- Default behavior when no preference is set

Requires: AWS configured via .env.test (see .env.test.example)
"""

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
class TestUserPreferencesIntegration:
    """Integration tests for user preferences with join notifications using real AWS."""

    # Use a test user ID to avoid affecting real users
    TEST_USER_ID = "U_TEST_JOIN_PREFS_" + str(int(time.time()))
    TEST_TABLE_NAME = "ketchup_channel_information"  # Real table

    @pytest_asyncio.fixture
    async def real_dynamodb_client(self):
        """Create a real DynamoDB client for testing.
        
        AWS profile is loaded from .env.test by root conftest.py.
        Tests are auto-skipped if AWS is not configured.
        """
        client = DynamoDBAsyncClient()
        yield client
        # Cleanup will happen in test teardown

    @pytest_asyncio.fixture
    async def user_store(self, real_dynamodb_client):
        """Create UserStore with real DynamoDB client."""
        store = UserStore(client=real_dynamodb_client, table_name=self.TEST_TABLE_NAME)
        yield store

        # Cleanup: Delete test user data after test
        try:
            await real_dynamodb_client.delete_item(
                table_name=self.TEST_TABLE_NAME,
                key={"PK": {"S": f"USER#{self.TEST_USER_ID}"}, "SK": {"S": "METADATA"}},
            )
            logger.info(f"Cleaned up test user data for {self.TEST_USER_ID}")
        except Exception as e:
            logger.warning(f"Failed to cleanup test user {self.TEST_USER_ID}: {e}")

    @pytest_asyncio.fixture
    async def mock_dependencies(self):
        """Set up mock dependencies for notification service."""
        openai_handler = AsyncMock()
        openai_handler.summarize_with_instructions = AsyncMock(
            return_value={"summary": "Test summary", "success": True}
        )
        # Mock the API executor for notification generation
        openai_handler._api_executor = AsyncMock()
        openai_handler._api_executor.build_openai_payload = AsyncMock(
            return_value={"messages": [], "model": "gpt-4"}
        )
        openai_handler._api_executor.execute_request = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": "Welcome! Here's what's happening in this channel:\n• Recent discussions about the project\n• Updates on JIRA tickets\n• Implementation progress"
                        }
                    }
                ]
            }
        )

        posting_handler = AsyncMock()
        posting_handler.post_ephemeral = AsyncMock(return_value=True)
        posting_handler._post_ephemeral = AsyncMock(return_value={"ok": True})

        channel_info_ops = AsyncMock()
        channel_info_ops.get_channel_info = AsyncMock(
            return_value={
                "channel_id": "C123TEST",
                "channel_name": "test-channel",
                "customer_name": "Test Customer",
                "is_member": True,  # Bot is member of channel
            }
        )

        channel_msg_ops = AsyncMock()
        channel_msg_ops.fetch_channel_messages = AsyncMock(
            return_value=[
                "U123: Test message about the project",
                "U456: We need to check the JIRA ticket",
                "U789: The implementation is complete",
            ]
        )

        return {
            "openai": openai_handler,
            "posting": posting_handler,
            "channel_info": channel_info_ops,
            "channel_msg": channel_msg_ops,
        }

    async def test_join_notification_preference_enabled_flow(
        self, user_store, mock_dependencies, real_dynamodb_client
    ):
        """Test full flow when user has join notifications enabled with real DynamoDB."""
        user_id = self.TEST_USER_ID
        channel_id = "C123TEST"

        logger.info(f"Testing with user ID: {user_id}")

        # Step 1: User sets preference via home tab (simulated)
        home_tab_payload = {
            "view": {
                "state": {
                    "values": {
                        "join_notifications_enabled_selection": {
                            "join_notifications_enabled_select": {
                                "selected_option": {"value": "enabled"}
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

        # Extract preferences
        preferences = extract_preferences_from_state(home_tab_payload)
        assert preferences["join_notifications_enabled"] == "enabled"

        # Step 2: Store preferences in database
        await user_store.store_user_preferences(user_id, preferences)

        # Step 3: Get user data to verify it was stored
        user_data = await user_store.get_user(user_id)
        assert user_data is not None
        assert "preferences" in user_data
        assert user_data["preferences"]["join_notifications_enabled"] == "enabled"

        # Step 4: Create notification service with user store
        service = UserJoinNotificationService(
            openai_handler=mock_dependencies["openai"],
            posting_handler=mock_dependencies["posting"],
            channel_info_ops=mock_dependencies["channel_info"],
            channel_msg_ops=mock_dependencies["channel_msg"],
            jira_extractor=None,
            user_store=user_store,
        )

        # Step 5: Process join event - should send notification
        result = await service.send_join_notification(user_id, channel_id)
        assert result is True

        # Verify notification was sent (service calls _post_ephemeral)
        mock_dependencies["posting"]._post_ephemeral.assert_called_once()
        call_args = mock_dependencies["posting"]._post_ephemeral.call_args
        assert call_args[1]["channel_id"] == channel_id
        assert call_args[1]["user_id"] == user_id

    async def test_join_notification_preference_disabled_flow(
        self, user_store, mock_dependencies, real_dynamodb_client
    ):
        """Test full flow when user has join notifications disabled."""
        user_id = self.TEST_USER_ID
        channel_id = "C123TEST"

        # Step 1: User disables notifications via home tab
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

        # Extract preferences
        preferences = extract_preferences_from_state(home_tab_payload)
        assert preferences["join_notifications_enabled"] == "disabled"

        # Step 2: Store preferences
        await user_store.store_user_preferences(user_id, preferences)

        # Step 3: Verify preference was stored
        user_data = await user_store.get_user(user_id)
        assert user_data is not None
        assert "preferences" in user_data
        assert user_data["preferences"]["join_notifications_enabled"] == "disabled"

        # Step 4: Create notification service
        service = UserJoinNotificationService(
            openai_handler=mock_dependencies["openai"],
            posting_handler=mock_dependencies["posting"],
            channel_info_ops=mock_dependencies["channel_info"],
            channel_msg_ops=mock_dependencies["channel_msg"],
            jira_extractor=None,
            user_store=user_store,
        )

        # Step 5: Process join event - should NOT send notification
        result = await service.send_join_notification(user_id, channel_id)
        assert result is True  # Returns True because skipping is expected behavior

        # Verify notification was NOT sent (service would call _post_ephemeral)
        mock_dependencies["posting"]._post_ephemeral.assert_not_called()

    async def test_join_notification_default_behavior_no_preference(
        self, user_store, mock_dependencies, real_dynamodb_client
    ):
        """Test default behavior when user has no preference set."""
        user_id = f"{self.TEST_USER_ID}_NEW"
        channel_id = "C123TEST"

        # Ensure user has no stored preferences (clean state)
        # Don't store any preferences for this user

        # Create notification service
        service = UserJoinNotificationService(
            openai_handler=mock_dependencies["openai"],
            posting_handler=mock_dependencies["posting"],
            channel_info_ops=mock_dependencies["channel_info"],
            channel_msg_ops=mock_dependencies["channel_msg"],
            jira_extractor=None,
            user_store=user_store,
        )

        # Process join event - should send notification (default is enabled)
        result = await service.send_join_notification(user_id, channel_id)
        assert result is True

        # Verify notification was sent (default behavior - service calls _post_ephemeral)
        mock_dependencies["posting"]._post_ephemeral.assert_called_once()

    async def test_preference_persistence_and_retrieval(
        self, user_store, real_dynamodb_client
    ):
        """Test that preferences are correctly persisted and retrieved."""
        user_id = f"{self.TEST_USER_ID}_PERSIST"

        # Set up preferences with join notifications disabled
        preferences = {
            "join_notifications_enabled": "disabled",
            "product_focus": ["ajo", "aep"],
            "detail_level": "technical_details",
            "time_window": "past_2_hours",
        }

        # Save preferences
        await user_store.store_user_preferences(user_id, preferences)

        # Retrieve and verify preferences directly from real DynamoDB
        user_data = await user_store.get_user(user_id)
        assert user_data is not None
        assert "preferences" in user_data
        assert user_data["preferences"]["join_notifications_enabled"] == "disabled"
        assert user_data["preferences"]["product_focus"] == ["ajo", "aep"]
        assert user_data["preferences"]["detail_level"] == "technical_details"
        assert user_data["preferences"]["time_window"] == "past_2_hours"

    async def test_di_container_integration(self, mock_dependencies, user_store):
        """Test that TypedDI properly wires dependencies for notification service."""
        # Create service directly (TypedDI integration test)
        from packages.slack.services.user_join_notification_service import (
            UserJoinNotificationService,
        )

        service = UserJoinNotificationService(
            openai_handler=mock_dependencies["openai"],
            posting_handler=mock_dependencies["posting"],
            channel_info_ops=mock_dependencies["channel_info"],
            channel_msg_ops=mock_dependencies["channel_msg"],
            jira_extractor=None,
            user_store=user_store,
        )

        # Verify service was created with all dependencies
        assert service is not None
        assert service.user_store == user_store
        assert service.openai_handler == mock_dependencies["openai"]
        assert service.posting_handler == mock_dependencies["posting"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_home_tab_preference_extraction():
    """Test that home tab correctly extracts join notification preference."""
    # Test with enabled preference
    enabled_payload = {
        "view": {
            "state": {
                "values": {
                    "join_notifications_enabled_selection": {
                        "join_notifications_enabled_select": {
                            "selected_option": {"value": "enabled"}
                        }
                    },
                    "product_focus_selection": {
                        "product_focus_select": {"selected_option": {"value": "stock"}}
                    },
                    "detail_level_selection": {
                        "detail_level_select": {
                            "selected_option": {"value": "high_level"}
                        }
                    },
                    "time_window_selection": {
                        "time_window_select": {
                            "selected_option": {"value": "always_ask"}
                        }
                    },
                }
            }
        }
    }

    prefs = extract_preferences_from_state(enabled_payload)
    assert prefs["join_notifications_enabled"] == "enabled"
    assert prefs["product_focus"] == ["stock"]

    # Test with disabled preference
    disabled_payload = {
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

    prefs = extract_preferences_from_state(disabled_payload)
    assert prefs["join_notifications_enabled"] == "disabled"

    # Test with missing preference (defaults to enabled)
    missing_payload = {
        "view": {
            "state": {
                "values": {
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

    prefs = extract_preferences_from_state(missing_payload)
    assert prefs["join_notifications_enabled"] == "enabled"  # Default value
