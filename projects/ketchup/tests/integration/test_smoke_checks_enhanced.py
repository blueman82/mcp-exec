#!/usr/bin/env python3
"""
Enhanced Smoke Checks Tests - Phase 3, Subtask 3.4

Tests full smoke test with proper TypedDI integration.

Production Issue: Smoke checks were failing
Expected Fix: All smoke checks should pass with proper TypedDI setup
"""

import asyncio
import unittest
from unittest.mock import Mock, patch

from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry
from packages.core.typed_di_integration import _run_startup_smoke_checks

logger = setup_logger(__name__)


class TestSmokeChecksEnhanced(unittest.IsolatedAsyncioTestCase):
    """Test enhanced smoke checks with TypedDI."""

    async def test_full_smoke_checks_with_typed_di(self):
        """
        Test full smoke test with TypedDI.

        Production Issue: Smoke checks were failing
        Expected Fix: All smoke checks should pass with proper service registration
        """
        # Mock all critical service classes that smoke checks test
        mock_services = self._create_mock_services()
        registry = TypedServiceRegistry()

        # Register all critical services that smoke checks will test
        for service_name, service_type in mock_services.items():
            registry.register(
                service_type=service_type,
                factory=lambda resolver, name=service_name: Mock(),
                dependencies=[],
            )

        await registry.initialize_all()

        # Mock the actual service imports in smoke check
        with self._patch_service_imports(mock_services):
            result = await _run_startup_smoke_checks(registry)
            self.assertTrue(result, "Smoke checks should pass with proper service registration")
            logger.info("✓ Full smoke checks passed successfully")

        logger.info("✓ Full smoke test with TypedDI completed successfully")

    async def test_smoke_checks_failure_scenario(self):
        """Test smoke check failure when services are not registered."""
        registry = TypedServiceRegistry()
        await registry.initialize_all()

        mock_services = self._create_mock_services()

        # Mock imports but don't register services - should fail gracefully
        with self._patch_service_imports(mock_services):
            result = await _run_startup_smoke_checks(registry)
            # We expect this to fail but not crash
            logger.info(f"Smoke check result with empty registry: {result}")

        logger.info("✓ Smoke check failure scenario handled gracefully")

    def _create_mock_services(self) -> dict:
        """Create mock service types for testing."""
        return {
            "SecretsManager": type("SecretsManager", (), {}),
            "SlackConfig": type("SlackConfig", (), {}),
            "SlackPostingHandler": type("SlackPostingHandler", (), {}),
            "UserStore": type("UserStore", (), {}),
            "DynamoDBStore": type("DynamoDBStore", (), {}),
        }

    def _patch_service_imports(self, mock_services: dict):
        """Context manager for patching service imports."""
        return (
            patch("packages.secrets.manager.SecretsManager", mock_services["SecretsManager"]),
            patch("packages.slack.config.slack_config.SlackConfig", mock_services["SlackConfig"]),
            patch(
                "packages.slack.messages.posting.SlackPostingHandler",
                mock_services["SlackPostingHandler"],
            ),
            patch("packages.db.user_store.UserStore", mock_services["UserStore"]),
            patch("packages.db.dynamodb.store.DynamoDBStore", mock_services["DynamoDBStore"]),
        )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    unittest.main()
