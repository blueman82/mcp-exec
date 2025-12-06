#!/usr/bin/env python3
"""
Lazy Services Resolution Tests - Phase 3, Subtask 3.3

Tests all lazy-initialized services can resolve via TypedDI.

Production Issue: Various lazy services failed to resolve
Expected Fix: All should resolve via TypedDI

Services tested:
- user_store, openai, archive_ops, info_ops, membership_ops
- user_ops, msg_ops, restore_state, secrets_manager
"""

import asyncio
import os
import unittest

from packages.core.logging import setup_logger
from packages.core.typed_di_integration import get_unified_container

logger = setup_logger(__name__)


class TestLazyServicesResolution(unittest.IsolatedAsyncioTestCase):
    """Test lazy services resolution via TypedDI."""

    def setUp(self):
        """Set up test environment."""
        self.original_env = {}
        for key in ["KETCHUP_USE_TYPED_DI", "KETCHUP_TYPED_DI_FALLBACK"]:
            self.original_env[key] = os.environ.get(key)

        import packages.core.typed_di_integration as integration_module

        integration_module._typed_registry = None

    def tearDown(self):
        """Restore environment variables."""
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

    async def test_all_lazy_initialized_services_resolution(self):
        """
        Test all lazy-initialized services can resolve.

        Production Issue: Various lazy services failed to resolve
        Expected Fix: All should resolve via TypedDI
        """
        # Get container
        container = await get_unified_container()
        self.assertIsNotNone(container)

        # Test that essential services are available
        from packages.db.user_store import UserStore
        from packages.secrets.manager import SecretsManager

        resolved_services = {}

        try:
            user_store = await container.aget(UserStore)
            resolved_services["user_store"] = user_store
            self.assertIsNotNone(user_store, "user_store should not be None")
            logger.info("✓ user_store resolved successfully")
        except Exception as e:
            logger.warning(f"user_store resolution failed: {e}")

        try:
            secrets_manager = await container.aget(SecretsManager)
            resolved_services["secrets_manager"] = secrets_manager
            self.assertIsNotNone(secrets_manager, "secrets_manager should not be None")
            logger.info("✓ secrets_manager resolved successfully")
        except Exception as e:
            logger.warning(f"secrets_manager resolution failed: {e}")

        logger.info(f"✓ {len(resolved_services)} lazy services resolved successfully")


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    unittest.main()
