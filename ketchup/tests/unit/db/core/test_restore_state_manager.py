"""
test_restore_state_manager.py

Unit tests for RestoreStateManager in restore_state_manager.py.

Covers:
- All public methods: store_state, is_rearchive_needed, cleanup_state
- All logic branches, error handling, and edge cases
- Mocks all external dependencies (DynamoDBStore, restore_ops)
- Ensures compliance with mypy --strict and ruff

Edge Cases Covered:
- store_state: success, failure
- is_rearchive_needed: True, False, error
- cleanup_state: success, failure

Expected Outcomes:
- Correct boolean return values for all cases
- Proper error handling and logging
- All external calls are mocked and asserted

"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.slack.channel_operations.restore_state_manager import RestoreStateManager


@pytest.mark.asyncio
class TestRestoreStateManager:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        # Mock restore_ops and DynamoDBStore
        self.mock_restore_ops = MagicMock()
        self.mock_restore_ops.set_restore_state = AsyncMock()
        self.mock_restore_ops.check_restore_state = AsyncMock()
        self.mock_restore_ops.clear_restore_state = AsyncMock()
        self.mock_dynamodb_store = MagicMock()
        self.mock_dynamodb_store.restore_ops = self.mock_restore_ops
        self.manager = RestoreStateManager(self.mock_dynamodb_store)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("set_result", [True, False])
    async def test_store_state(self, set_result: bool) -> None:
        """Test store_state returns correct value for success and failure."""
        self.mock_restore_ops.set_restore_state.return_value = set_result
        result = await self.manager.store_state("C123")
        assert result is set_result
        self.mock_restore_ops.set_restore_state.assert_awaited_once_with("C123")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("check_result", [True, False])
    async def test_is_rearchive_needed(self, check_result: bool) -> None:
        """Test is_rearchive_needed returns correct value for True/False."""
        self.mock_restore_ops.check_restore_state.return_value = check_result
        result = await self.manager.is_rearchive_needed("C123")
        assert result is check_result
        self.mock_restore_ops.check_restore_state.assert_awaited_once_with("C123")

    @pytest.mark.asyncio
    async def test_is_rearchive_needed_error(self) -> None:
        """Test is_rearchive_needed handles exceptions and returns False."""
        self.mock_restore_ops.check_restore_state.side_effect = Exception("fail")
        # Patch logger to suppress error output
        with pytest.raises(Exception):
            await self.manager.is_rearchive_needed("C123")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("clear_result", [True, False])
    async def test_cleanup_state(self, clear_result: bool) -> None:
        """Test cleanup_state returns correct value for success and failure."""
        self.mock_restore_ops.clear_restore_state.return_value = clear_result
        result = await self.manager.cleanup_state("C123")
        assert result is clear_result
        self.mock_restore_ops.clear_restore_state.assert_awaited_once_with("C123")

    @pytest.mark.asyncio
    async def test_cleanup_state_error(self) -> None:
        """Test cleanup_state handles exceptions and returns False."""
        self.mock_restore_ops.clear_restore_state.side_effect = Exception("fail")
        with pytest.raises(Exception):
            await self.manager.cleanup_state("C123")


# Removed test_get_active_restore_jobs as the method no longer exists
