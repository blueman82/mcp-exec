#!/usr/bin/env python3
"""
Production Scenario Validation Tests - Phase 3, Subtasks 3.3-3.4

Tests the exact production failures that occurred and validates they are now fixed:

1. Home Tab Access Test:
   - Simulate dependency_setup.py line 190: container.get_by_name("user_store")
   - Ensure UserStoreProtocol resolves correctly via CompatibilityBridge

2. Status Command Test:
   - Simulate status command handler accessing user_store
   - Verify resolution through TypedDI -> CompatibilityBridge -> Legacy DI

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

        os.environ["KETCHUP_USE_TYPED_DI"] = "true"
        os.environ["KETCHUP_TYPED_DI_FALLBACK"] = "true"

        import packages.core.typed_di_integration as integration_module

        integration_module._typed_registry = None
        integration_module._compatibility_bridge = None
        integration_module._legacy_container = None

    def tearDown(self):
        """Restore original environment variables."""
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

    async def test_home_tab_access_user_store_resolution(self):
        """
        Test Home Tab Access - dependency_setup.py line 190.

        Production Issue: container.get_by_name("user_store") failed with "Service not found"
        Expected Fix: UserStoreProtocol resolves correctly via CompatibilityBridge
        """
        mock_fallback_manager = self._create_mock_fallback_manager("user_store")
        mock_user_store = Mock(spec=UserStore)
        mock_user_store.get_user_preferences = AsyncMock(return_value={})

        with self._patch_typed_di_components(mock_fallback_manager), patch(
            "packages.core.client_factory_utils.get_instance",
            return_value=mock_user_store,
        ):
            container = await get_unified_container()
            self.assertIsNotNone(container)

            try:
                user_store_result = container.get_by_name("user_store")
                self.assertIsNotNone(user_store_result)
                self.assertEqual(user_store_result, mock_user_store)
                logger.info("✓ user_store resolved successfully via get_by_name")
            except Exception as e:
                self.fail(f"Production failure reproduced: {e}")

        logger.info("✓ Home Tab Access test completed successfully")

    async def test_status_command_user_store_access(self):
        """
        Test Status Command - user_store access through CompatibilityBridge.

        Production Issue: Status command handler couldn't access user_store
        Expected Fix: Resolution works through TypedDI -> CompatibilityBridge -> Legacy DI
        """
        from packages.slack.command_processing.status_report_command import SlackReports

        mock_fallback_manager = self._create_mock_fallback_manager("user_store")
        mock_user_store = Mock(spec=UserStore)
        mock_deps = self._create_mock_command_dependencies()

        with self._patch_typed_di_components(mock_fallback_manager), patch(
            "packages.core.client_factory_utils.get_instance",
            return_value=mock_user_store,
        ):
            container = await get_unified_container()

            try:
                slack_reports = SlackReports(
                    user_store=container.get_by_name("user_store"), **mock_deps
                )
                self.assertIsNotNone(slack_reports.user_store)
                self.assertEqual(slack_reports.user_store, mock_user_store)
                logger.info("✓ Status command user_store injection successful")
            except Exception as e:
                self.fail(f"Status command user_store access failed: {e}")

        logger.info("✓ Status Command test completed successfully")

    async def test_dependency_setup_line_190_exact_reproduction(self):
        """
        Test exact reproduction of dependency_setup.py line 190 failure.

        This is the exact line that failed in production:
        user_store = cast(UserStore, container.get_by_name("user_store"))
        """
        mock_fallback_manager = self._create_mock_fallback_manager("user_store")
        mock_user_store = Mock(spec=UserStore)

        with self._patch_typed_di_components(mock_fallback_manager), patch(
            "packages.core.client_factory_utils.get_instance",
            return_value=mock_user_store,
        ):
            container = await get_unified_container()

            try:
                user_store = cast(UserStore, container.get_by_name("user_store"))
                self.assertIsNotNone(user_store)
                self.assertEqual(user_store, mock_user_store)
                logger.info("✓ dependency_setup.py line 190 executed successfully")
            except Exception as e:
                self.fail(f"Line 190 reproduction failed: {e}")

        logger.info("✓ Exact line 190 reproduction test completed successfully")

    def _create_mock_fallback_manager(self, service_key: str) -> Mock:
        """Create a mock fallback manager for testing."""
        mock_fallback_manager = Mock()
        mock_fallback_manager.should_fallback.return_value = True
        mock_fallback_manager.get_legacy_service_key.return_value = service_key
        return mock_fallback_manager

    def _patch_typed_di_components(self, mock_fallback_manager: Mock):
        """Context manager for patching TypedDI components."""
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch(
            "packages.core.typed_di.service_registrations.register_all_services"
        ))
        stack.enter_context(patch(
            "packages.core.typed_di.fallback_system.initialize_critical_service_mappings"
        ))
        stack.enter_context(patch(
            "packages.core.typed_di.fallback_system.get_fallback_manager",
            return_value=mock_fallback_manager,
        ))
        return stack

    def _create_mock_command_dependencies(self) -> dict:
        """Create mock dependencies for command handlers."""
        return {
            "channel_info_ops": Mock(),
            "archive_ops": Mock(),
            "openai_handler": Mock(),
            "block_kit_builder": Mock(),
            "secrets_manager": Mock(),
            "slack_config": Mock(),
            "slack_posting_handler": Mock(),
        }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    unittest.main()