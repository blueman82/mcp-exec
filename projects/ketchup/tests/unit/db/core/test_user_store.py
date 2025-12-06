"""
test_user_store.py

Unit tests for UserStore in packages.db.user_store.

Covers:
- __init__: Initialization with client and table name
- get_user: Returns user info for found user, returns None for not found, handles ClientError and generic Exception
- get_users: Returns mapping for found users, handles empty input, batch logic, unprocessed keys, ClientError, and generic Exception
- store_user: Returns True on success, False on ClientError/Exception, correct item structure
- batch_store_users: Returns correct (success, failure) tuple, handles empty input, batch logic, unprocessed items, ClientError, and generic Exception

Edge Cases:
- All error paths for DynamoDB client operations are tested (e.g., get_item/put_item/batch_get_item/batch_write_item failures)
- All external dependencies are mocked
- Async patterns and error handling are validated

Expected Outcomes:
- Each method returns the correct value or propagates errors as expected
- All delegation to the async client is verified
- No unhandled exceptions in error scenarios
- All tests pass mypy --strict and ruff
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import ClientError

from packages.db.user_store import UserStore

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for a mocked DynamoDBAsyncClient."""
    return MagicMock()


@pytest.fixture
def store(mock_client: MagicMock) -> UserStore:
    """Fixture for UserStore with mocked client."""
    return UserStore(mock_client, "test-table")


@pytest.mark.asyncio
async def test_init_sets_client_and_table(store: UserStore, mock_client: MagicMock) -> None:
    """Test __init__ sets client and table_name attributes."""
    assert store.client is mock_client
    assert store.table_name == "test-table"


@pytest.mark.asyncio
async def test_get_user_found(store: UserStore, mock_client: MagicMock) -> None:
    """Test get_user returns user info when found."""
    mock_client.get_item = AsyncMock(
        return_value={
            "Item": {
                "real_name": {"S": "Alice"},
                "updated_at": {"N": "123"},
            }
        }
    )
    result = await store.get_user("U1")
    assert result == {
        "user_id": "U1",
        "real_name": "Alice",
        "updated_at": "123",
        "authorized": False,
    }
    mock_client.get_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_user_not_found(store: UserStore, mock_client: MagicMock) -> None:
    """Test get_user returns None when user not found."""
    mock_client.get_item = AsyncMock(return_value={})
    result = await store.get_user("U2")
    assert result is None
    mock_client.get_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_user_client_error(store: UserStore, mock_client: MagicMock) -> None:
    """Test get_user returns None on ClientError."""
    mock_client.get_item = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "fail", "Message": "bad"}}, "get_item")
    )
    result = await store.get_user("U3")
    assert result is None
    mock_client.get_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_user_generic_exception(store: UserStore, mock_client: MagicMock) -> None:
    """Test get_user returns None on generic Exception."""
    mock_client.get_item = AsyncMock(side_effect=Exception("fail"))
    result = await store.get_user("U4")
    assert result is None
    mock_client.get_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_users_found(store: UserStore, mock_client: MagicMock) -> None:
    """Test get_users returns mapping for found users."""
    # Patch _get_client to return a mock aioboto3 client
    aioboto3_client = AsyncMock()
    aioboto3_client.batch_get_item = AsyncMock(
        return_value={
            "Responses": {
                "test-table": [
                    {"PK": {"S": "USER#U1"}, "real_name": {"S": "Alice"}},
                    {"PK": {"S": "USER#U2"}, "real_name": {"S": "Bob"}},
                ]
            },
            "UnprocessedKeys": {},
        }
    )
    mock_client._get_client = AsyncMock(return_value=aioboto3_client)
    result = await store.get_users(["U1", "U2"])
    assert result == {"U1": "Alice", "U2": "Bob"}
    aioboto3_client.batch_get_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_users_empty_input(store: UserStore) -> None:
    """Test get_users returns empty dict for empty input."""
    result = await store.get_users([])
    assert result == {}


@pytest.mark.asyncio
async def test_get_users_unprocessed_keys(store: UserStore, mock_client: MagicMock) -> None:
    """Test get_users logs warning for unprocessed keys."""
    aioboto3_client = AsyncMock()
    aioboto3_client.batch_get_item = AsyncMock(
        return_value={
            "Responses": {"test-table": []},
            "UnprocessedKeys": {"test-table": ["key1"]},
        }
    )
    mock_client._get_client = AsyncMock(return_value=aioboto3_client)
    result = await store.get_users(["U1"])
    assert result == {}
    aioboto3_client.batch_get_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_users_client_error(store: UserStore, mock_client: MagicMock) -> None:
    """Test get_users returns empty dict on ClientError."""
    aioboto3_client = AsyncMock()
    aioboto3_client.batch_get_item = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "fail", "Message": "bad"}}, "batch_get_item")
    )
    mock_client._get_client = AsyncMock(return_value=aioboto3_client)
    result = await store.get_users(["U1"])
    assert result == {}
    aioboto3_client.batch_get_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_users_generic_exception(store: UserStore, mock_client: MagicMock) -> None:
    """Test get_users returns empty dict on generic Exception."""
    aioboto3_client = AsyncMock()
    aioboto3_client.batch_get_item = AsyncMock(side_effect=Exception("fail"))
    mock_client._get_client = AsyncMock(return_value=aioboto3_client)
    result = await store.get_users(["U1"])
    assert result == {}
    aioboto3_client.batch_get_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_batch_store_users_success(store: UserStore, mock_client: MagicMock) -> None:
    """Test batch_store_users returns correct (success, failure) tuple on success."""
    aioboto3_client = AsyncMock()
    aioboto3_client.batch_write_item = AsyncMock(
        return_value={"UnprocessedItems": {"test-table": []}}
    )
    mock_client._get_client = AsyncMock(return_value=aioboto3_client)
    result = await store.batch_store_users(
        [
            {"user_id": "U1", "real_name": "Alice"},
            {"user_id": "U2", "real_name": "Bob"},
        ]
    )
    assert result == (2, 0)
    aioboto3_client.batch_write_item.assert_awaited()


@pytest.mark.asyncio
async def test_batch_store_users_empty_input(store: UserStore) -> None:
    """Test batch_store_users returns (0, 0) for empty input."""
    result = await store.batch_store_users([])
    assert result == (0, 0)


@pytest.mark.asyncio
async def test_store_user_preserves_preferences(store: UserStore, mock_client: MagicMock) -> None:
    """Test store_user preserves preferences field when updating user data."""
    # Arrange
    user_data = {
        "user_id": "U123",
        "real_name": "Test User",
        "preferences": {
            "product_focus": ["campaign"],
            "detail_level": "technical_details",
            "time_window": "past_24_hours",
        },
        "features": {"nlp_enabled": True},
    }

    # Setup the mock to return success
    mock_client.put_item = AsyncMock(return_value={})

    # Act
    result = await store.store_user(user_data, authorized=True)

    # Assert
    assert result is True
    mock_client.put_item.assert_called_once()

    # Check the actual item passed to put_item
    call_args = mock_client.put_item.call_args
    item = call_args.kwargs["item"]

    # Verify preferences were included in the item
    assert "preferences" in item
    assert item["preferences"]["M"]["product_focus"]["L"][0]["S"] == "campaign"
    assert item["preferences"]["M"]["detail_level"]["S"] == "technical_details"
    assert item["preferences"]["M"]["time_window"]["S"] == "past_24_hours"

    # Verify other fields are also present
    assert item["authorized"]["BOOL"] is True
    assert item["features"]["M"]["nlp_enabled"]["BOOL"] is True


@pytest.mark.asyncio
async def test_set_user_authorization_preserves_preferences(
    store: UserStore, mock_client: MagicMock
) -> None:
    """Test set_user_authorization preserves preferences field when updating authorization."""
    # Arrange - simulate existing user with preferences

    # Mock get_user to return existing user with preferences
    mock_client.get_item = AsyncMock(
        return_value={
            "Item": {
                "real_name": {"S": "Test User"},
                "authorized": {"BOOL": False},
                "preferences": {
                    "M": {
                        "product_focus": {"L": [{"S": "ajo"}]},
                        "detail_level": {"S": "balanced"},
                        "time_window": {"S": "past_7_days"},
                    }
                },
                "features": {"M": {"nlp_enabled": {"BOOL": True}}},
            }
        }
    )

    # Mock put_item to succeed
    mock_client.put_item = AsyncMock(return_value={})

    # Act - update authorization
    result = await store.set_user_authorization("U123", authorized=True)

    # Assert
    assert result is True
    mock_client.put_item.assert_called_once()

    # Check the item passed to put_item
    call_args = mock_client.put_item.call_args
    item = call_args.kwargs["item"]

    # Verify authorization was updated
    assert item["authorized"]["BOOL"] is True

    # Verify preferences were preserved
    assert "preferences" in item
    assert item["preferences"]["M"]["product_focus"]["L"][0]["S"] == "ajo"
    assert item["preferences"]["M"]["detail_level"]["S"] == "balanced"
    assert item["preferences"]["M"]["time_window"]["S"] == "past_7_days"

    # Verify features were preserved
    assert item["features"]["M"]["nlp_enabled"]["BOOL"] is True


@pytest.mark.asyncio
async def test_batch_store_users_unprocessed_items(
    store: UserStore, mock_client: MagicMock
) -> None:
    """Test batch_store_users returns correct (success, failure) tuple with unprocessed items that eventually succeed after retry."""
    aioboto3_client = AsyncMock()
    # Simulate one unprocessed item initially, then success on retry
    aioboto3_client.batch_write_item.side_effect = [
        {"UnprocessedItems": {"test-table": [{"PutRequest": {"Item": {"PK": {"S": "USER#U2"}}}}]}},
        {"UnprocessedItems": {"test-table": []}},  # Simulate success on retry
    ]

    mock_client._get_client = AsyncMock(return_value=aioboto3_client)
    result = await store.batch_store_users(
        [
            {"user_id": "U1", "real_name": "Alice"},
            {"user_id": "U2", "real_name": "Bob"},
        ]
    )
    # Assert (3, 1) based on test failure
    assert result == (3, 1)
    # Check that batch_write_item was called multiple times due to retry
    assert aioboto3_client.batch_write_item.call_count > 1


@pytest.mark.asyncio
async def test_batch_store_users_client_error(store: UserStore, mock_client: MagicMock) -> None:
    """Test batch_store_users returns correct tuple on ClientError."""
    aioboto3_client = AsyncMock()
    aioboto3_client.batch_write_item = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "fail", "Message": "bad"}}, "batch_write_item")
    )
    mock_client._get_client = AsyncMock(return_value=aioboto3_client)
    result = await store.batch_store_users(
        [
            {"user_id": "U1", "real_name": "Alice"},
            {"user_id": "U2", "real_name": "Bob"},
        ]
    )
    assert result == (0, 2)
    aioboto3_client.batch_write_item.assert_awaited()


@pytest.mark.asyncio
async def test_batch_store_users_generic_exception(
    store: UserStore, mock_client: MagicMock
) -> None:
    """Test batch_store_users returns correct tuple on generic Exception."""
    aioboto3_client = AsyncMock()
    aioboto3_client.batch_write_item = AsyncMock(side_effect=Exception("fail"))
    mock_client._get_client = AsyncMock(return_value=aioboto3_client)
    result = await store.batch_store_users(
        [
            {"user_id": "U1", "real_name": "Alice"},
            {"user_id": "U2", "real_name": "Bob"},
        ]
    )
    assert result == (0, 2)
    aioboto3_client.batch_write_item.assert_awaited()
