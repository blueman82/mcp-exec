#!/usr/bin/env python3
"""
Lazy Services Resolution Tests - Phase 3, Subtask 3.3

Tests all 9 lazy-initialized services can resolve via CompatibilityBridge fallback.

Production Issue: Various lazy services failed to resolve
Expected Fix: All should resolve via CompatibilityBridge fallback

Services tested:
- user_store, openai, archive_ops, info_ops, membership_ops
- user_ops, msg_ops, restore_state, secrets_manager
"""

import asyncio
import os
import unittest
from unittest.mock import Mock, patch

from packages.core.logging import setup_logger
from packages.core.typed_di_integration import get_unified_container

logger = setup_logger(__name__)


class TestLazyServicesResolution(unittest.IsolatedAsyncioTestCase):
    """Test lazy services resolution via CompatibilityBridge."""

    def setUp(self):
        """Set up test environment."""
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
        """Restore environment variables."""
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

    async def test_all_lazy_initialized_services_resolution(self):
        """
        Test all 9 lazy-initialized services can resolve.

        Production Issue: Various lazy services failed to resolve
        Expected Fix: All should resolve via CompatibilityBridge fallback
        """
        lazy_services = [
            "user_store",
            "openai",
            "archive_ops",
            "info_ops",
            "membership_ops",
            "user_ops",
            "msg_ops",
            "restore_state",
            "secrets_manager",
        ]

        mock_fallback_manager = self._create_mock_fallback_manager()
        service_mocks = {name: Mock() for name in lazy_services}

        def mock_get_instance(service_key):
            return service_mocks.get(service_key, Mock())

        with self._patch_typed_di_components(mock_fallback_manager), patch(
            "packages.core.client_factory_utils.get_instance",
            side_effect=mock_get_instance,
        ):
            container = await get_unified_container()
            self.assertIsNotNone(container)

            resolved_services = {}
            for service_name in lazy_services:
                try:
                    service_instance = container.get_by_name(service_name)
                    resolved_services[service_name] = service_instance
                    self.assertIsNotNone(
                        service_instance, f"{service_name} should not be None"
                    )
                    logger.info(f"✓ {service_name} resolved successfully")
                except Exception as e:
                    self.fail(f"Failed to resolve {service_name}: {e}")

            self.assertEqual(
                len(resolved_services),
                len(lazy_services),
                f"Expected {len(lazy_services)} services, got {len(resolved_services)}",
            )

        logger.info(f"✓ All {len(lazy_services)} lazy services resolved successfully")

    def _create_mock_fallback_manager(self) -> Mock:
        """Create mock fallback manager for all services."""
        mock_fallback_manager = Mock()
        mock_fallback_manager.should_fallback.return_value = True
        mock_fallback_manager.get_legacy_service_key.side_effect = lambda x: x
        return mock_fallback_manager

    def _patch_typed_di_components(self, mock_fallback_manager: Mock):
        """Context manager for patching TypedDI components."""
        return patch(
            "packages.core.typed_di.service_registrations.register_all_services"
        ), patch(
            "packages.core.typed_di.fallback_system.initialize_critical_service_mappings"
        ), patch(
            "packages.core.typed_di.fallback_system.get_fallback_manager",
            return_value=mock_fallback_manager,
        )


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    unittest.main()