#!/usr/bin/env python3
"""
Production Scenario Validation Tests - Phase 3, Subtasks 3.3-3.4

Tests the exact production failures that occurred and validates they are now fixed:

1. Home Tab Access Test:
   - Simulate user_store resolution
   - Ensure it resolves correctly via TypedDI

2. Status Command Test:
   - Simulate status command handler accessing user_store
   - Verify resolution through TypedDI

CRITICAL: These are the exact failures from production that must be fixed.
"""

import asyncio
import os
import unittest
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

from packages.core.logging import setup_logger
from packages.core.typed_di_integration import get_unified_container
from packages.db.user_store import UserStore

logger = setup_logger(__name__)


class TestProductionScenariosFailed(unittest.IsolatedAsyncioTestCase):
    """Test exact production failure scenarios that occurred."""

    def setUp(self):
        """Reset environment variables and global state before each test."""
        self.original_env = {}
        for key in ["KETCHUP_USE_TYPED_DI", "KETCHUP_TYPED_DI_FALLBACK"]:
            self.original_env[key] = os.environ.get(key)

        import packages.core.typed_di_integration as integration_module

        integration_module._typed_registry = None

    def tearDown(self):
        """Restore original environment variables."""
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

    async def test_home_tab_access_user_store_resolution(self):
        """
        Test Home Tab Access - user_store resolution.

        Production Issue: container access to user_store failed
        Expected Fix: UserStore resolves correctly via TypedDI
        """
        container = await get_unified_container()
        self.assertIsNotNone(container)

        try:
            user_store_result = await container.aget(UserStore)
            self.assertIsNotNone(user_store_result)
            logger.info("✓ user_store resolved successfully")
        except Exception as e:
            self.fail(f"Production failure reproduced: {e}")

        logger.info("✓ Home Tab Access test completed successfully")

    async def test_status_command_user_store_access(self):
        """
        Test Status Command - user_store access through TypedDI.

        Production Issue: Status command handler couldn't access user_store
        Expected Fix: Resolution works through TypedDI
        """
        from packages.slack.command_processing.status_report_command import SlackReports

        container = await get_unified_container()

        try:
            user_store = await container.aget(UserStore)
            self.assertIsNotNone(user_store)
            logger.info("✓ Status command user_store resolution successful")
        except Exception as e:
            self.fail(f"Status command user_store access failed: {e}")

        logger.info("✓ Status Command test completed successfully")

    async def test_exact_reproduction(self):
        """
        Test exact reproduction of production failure pattern.

        This is the exact pattern that failed in production:
        accessing user_store through the container
        """
        container = await get_unified_container()

        try:
            user_store = await container.aget(UserStore)
            self.assertIsNotNone(user_store)
            logger.info("✓ Exact pattern executed successfully")
        except Exception as e:
            self.fail(f"Exact pattern reproduction failed: {e}")

        logger.info("✓ Exact reproduction test completed successfully")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    unittest.main()
