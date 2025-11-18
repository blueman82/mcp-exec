"""
Test the get_user_usernames method in SlackUserOps.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.user_operations.user_ops import SlackUserOps


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for SlackUserOps."""
    user_store = AsyncMock()
    slack_config = MagicMock()
    slack_config.get_api_base_url.return_value = "https://slack.com/api"
    slack_config.get_headers.return_value = {"Authorization": "Bearer token"}

    return user_store, slack_config


@pytest.fixture
def user_ops(mock_dependencies):
    """Create SlackUserOps instance with mocked dependencies."""
    user_store, slack_config = mock_dependencies
    return SlackUserOps(
        user_store=user_store, slack_config=slack_config, max_concurrent_requests=10
    )


@pytest.mark.asyncio
async def test_get_user_usernames_returns_username_not_display_name(user_ops):
    """Test that get_user_usernames returns the username field, not display name."""
    # Setup
    user_id = "U123456"

    # Mock user data from Slack API
    mock_user_data = {
        "id": user_id,
        "name": "harrison",  # This is the username
        "profile": {
            "real_name": "Gary Harrison",  # This is the display name
            "display_name": "Gary Harrison",
        },
    }

    # Mock the API response in SafeResponse format
    mock_response = {
        "status": 200,
        "headers": {},
        "body": json.dumps({"ok": True, "user": mock_user_data}).encode(),
    }

    # Mock empty DB response to force API call
    user_ops.user_store.get_users = AsyncMock(return_value={})
    # Mock batch_store_users to return expected tuple
    user_ops.user_store.batch_store_users = AsyncMock(return_value=(1, 0))

    # Mock the API request
    with patch.object(
        user_ops, "_make_api_request", AsyncMock(return_value=mock_response)
    ):
        # Call the method
        result = await user_ops.get_user_usernames([user_id])

    # Assert
    assert result[user_id] == "harrison"  # Should return username, not "Gary Harrison"


@pytest.mark.asyncio
async def test_get_user_usernames_from_cache(user_ops):
    """Test that get_user_usernames uses cached data when available."""
    # Setup
    user_id = "U123456"

    # Pre-populate cache
    user_ops._user_cache[user_id] = {
        "id": user_id,
        "name": "harrison",
        "profile": {"real_name": "Gary Harrison"},
    }

    # Call the method
    result = await user_ops.get_user_usernames([user_id])

    # Assert
    assert result[user_id] == "harrison"
    # Verify no API calls were made
    user_ops.user_store.get_users.assert_not_called()


@pytest.mark.asyncio
async def test_get_user_usernames_fallback_to_id(user_ops):
    """Test that get_user_usernames falls back to user ID when name is missing."""
    # Setup
    user_id = "U123456"

    # Mock user data without name field
    mock_user_data = {
        "id": user_id,
        "profile": {"real_name": "Gary Harrison"},
        # Note: no "name" field
    }

    # Mock the API response in SafeResponse format
    mock_response = {
        "status": 200,
        "headers": {},
        "body": json.dumps({"ok": True, "user": mock_user_data}).encode(),
    }

    # Mock empty DB response
    user_ops.user_store.get_users = AsyncMock(return_value={})
    # Mock batch_store_users to return expected tuple
    user_ops.user_store.batch_store_users = AsyncMock(return_value=(1, 0))

    # Mock the API request
    with patch.object(
        user_ops, "_make_api_request", AsyncMock(return_value=mock_response)
    ):
        # Call the method
        result = await user_ops.get_user_usernames([user_id])

    # Assert - should fall back to user ID
    assert result[user_id] == user_id


@pytest.mark.asyncio
async def test_get_user_usernames_multiple_users(user_ops):
    """Test get_user_usernames with multiple users."""
    # Setup
    user_ids = ["U123456", "U789012", "U345678"]

    # Mock different scenarios for each user
    mock_users = {
        "U123456": {
            "id": "U123456",
            "name": "harrison",
            "profile": {"real_name": "Gary Harrison"},
        },
        "U789012": {
            "id": "U789012",
            "name": "jsmith",
            "profile": {"real_name": "John Smith"},
        },
        "U345678": {
            "id": "U345678",
            # No name field - should fall back to ID
            "profile": {"real_name": "Jane Doe"},
        },
    }

    # Mock DB to return first user only
    user_ops.user_store.get_users = AsyncMock(
        return_value={"U123456": "harrison"}  # DB has cached username
    )
    # Mock batch_store_users to return expected tuple
    user_ops.user_store.batch_store_users = AsyncMock(return_value=(2, 0))

    # Mock API responses for remaining users
    async def mock_api_request(url, method, headers, params):
        user_id = params["user"]
        mock_response = {
            "status": 200,
            "headers": {},
            "body": json.dumps({"ok": True, "user": mock_users[user_id]}).encode(),
        }
        return mock_response

    with patch.object(user_ops, "_make_api_request", side_effect=mock_api_request):
        # Call the method
        result = await user_ops.get_user_usernames(user_ids)

    # Assert
    assert result["U123456"] == "harrison"
    assert result["U789012"] == "jsmith"
    assert result["U345678"] == "U345678"  # Falls back to ID


@pytest.mark.asyncio
async def test_get_user_names_still_returns_display_names(user_ops):
    """Verify that get_user_names still returns display names for backward compatibility."""
    # Setup
    user_id = "U123456"

    # Mock user data
    mock_user_data = {
        "id": user_id,
        "name": "harrison",
        "profile": {"real_name": "Gary Harrison"},
    }

    # Mock the API response in SafeResponse format
    mock_response = {
        "status": 200,
        "headers": {},
        "body": json.dumps({"ok": True, "user": mock_user_data}).encode(),
    }

    # Mock empty DB response
    user_ops.user_store.get_users = AsyncMock(return_value={})
    # Mock batch_store_users to return expected tuple
    user_ops.user_store.batch_store_users = AsyncMock(return_value=(1, 0))

    # Mock the API request
    with patch.object(
        user_ops, "_make_api_request", AsyncMock(return_value=mock_response)
    ):
        # Call the original method
        result = await user_ops.get_user_names([user_id])

    # Assert - should return display name
    assert result[user_id] == "Gary Harrison"
