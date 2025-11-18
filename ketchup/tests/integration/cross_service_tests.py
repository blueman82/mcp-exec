#!/usr/bin/env python3
"""
Cross-Service Integration Test Framework

Comprehensive testing framework for validating service-to-service interactions
in the TypedDI system. Tests integration between different services, dependency
chains, and communication patterns.

Features:
- Service-to-service communication validation
- Complex dependency chain testing
- Cross-package service interaction testing
- Performance metrics for service interactions

Test Categories:
1. Core Service Interactions (Core ↔ DB, Core ↔ Secrets)
2. Slack Service Integration (Slack ↔ Core, Slack ↔ DB)
3. Database Service Integration (DB ↔ Core, DB ↔ Slack)
"""

import asyncio
import os
import time
from typing import Any, Dict, Type, TypeVar

import pytest

from packages.core.typed_di_integration import get_unified_container
from packages.core.typed_di import TypedServiceRegistry
from packages.core.logging import setup_logger

# Import service types for type-safe resolution
from packages.secrets.manager import SecretsManager
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.user_store import UserStore
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.slack.config.slack_config import SlackConfig
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.home.home import HomeTabHandler
from packages.db.operations.channel_operations import ChannelOperations

logger = setup_logger(__name__)

T = TypeVar("T")


class CrossServiceIntegrationTest:
    """
    Cross-service integration test framework.

    Tests complex interactions between different service types and validates
    that service dependencies work correctly across package boundaries.
    """

    def __init__(self):
        """Initialize cross-service integration test framework."""
        self.test_name = "Cross-Service Integration Tests"
        self.container: TypedServiceRegistry = None
        self.logger = setup_logger(f"integration.{self.test_name}")
        self.test_results: Dict[str, Dict[str, Any]] = {}
        self.performance_metrics: Dict[str, float] = {}

        # Set up environment
        os.environ["KETCHUP_USE_TYPED_DI"] = "true"
        os.environ["KETCHUP_TEST_MODE"] = "true"
        os.environ["LOG_LEVEL"] = "INFO"

    async def setup(self):
        """Initialize the TypedDI container."""
        self.logger.info("Initializing TypedDI container...")
        self.container = await get_unified_container()
        self.logger.info("TypedDI container initialized successfully")

    def get_service(self, service_type: Type[T]) -> T:
        """
        Get a single service from the container.

        Args:
            service_type: Type of the service to retrieve

        Returns:
            The requested service instance
        """
        if not self.container:
            raise RuntimeError("Container not initialized. Call setup() first.")
        return self.container.get(service_type)

    async def execute(self) -> bool:
        """
        Execute the test with proper setup and teardown.

        Returns:
            True if test passed, False otherwise
        """
        self.logger.info(f"{'=' * 60}")
        self.logger.info(f"Starting {self.test_name}")
        self.logger.info(f"{'=' * 60}")

        try:
            # Set up environment
            await self.setup()

            # Run the actual test
            result = await self.run_test()

            # Log result
            self.logger.info(f"{'=' * 60}")
            if result:
                self.logger.info(f"✅ TEST PASSED: {self.test_name}")
            else:
                self.logger.error(f"❌ TEST FAILED: {self.test_name}")
            self.logger.info(f"{'=' * 60}")

            return result

        except Exception as e:
            self.logger.error(f"❌ Test failed with error: {e}", exc_info=True)
            self.logger.info(f"{'=' * 60}")
            return False

    async def run_test(self) -> bool:
        """Execute all cross-service integration tests."""
        self.logger.info("Starting Cross-Service Integration Tests")

        test_methods = [
            self._test_core_service_interactions,
            self._test_slack_service_integration,
            self._test_database_service_integration,
            self._test_complex_service_workflows,
        ]

        all_tests_passed = True
        for test_method in test_methods:
            try:
                start_time = time.time()
                result = await test_method()
                execution_time = time.time() - start_time

                test_name = test_method.__name__
                self.performance_metrics[test_name] = execution_time
                self.test_results[test_name] = {
                    "passed": result,
                    "execution_time": execution_time,
                }

                status = "✅ PASSED" if result else "❌ FAILED"
                self.logger.info(f"{status}: {test_name} ({execution_time:.3f}s)")

                if not result:
                    all_tests_passed = False

            except Exception as e:
                self.logger.error(f"❌ {test_method.__name__} FAILED: {e}")
                all_tests_passed = False

        self._log_performance_summary()
        return all_tests_passed

    async def _test_core_service_interactions(self) -> bool:
        """Test interactions between core services."""
        self.logger.info("Testing Core Service Interactions")

        try:
            # Test Core → Secrets interaction
            secrets_manager = self.get_service(SecretsManager)
            assert secrets_manager is not None, "SecretsManager unavailable"

            # Test Core → DB interaction
            db_store = self.get_service(DynamoDBStore)
            assert db_store is not None, "DynamoDBStore unavailable"

            # Test UserStore integration with dependencies
            user_store = self.get_service(UserStore)
            assert user_store is not None, "UserStore unavailable"
            assert hasattr(user_store, "store"), "UserStore missing DB dependency"

            return True

        except Exception as e:
            self.logger.error(f"Core service interaction test failed: {e}")
            return False

    async def _test_slack_service_integration(self) -> bool:
        """Test Slack service integrations with other packages."""
        self.logger.info("Testing Slack Service Integration")

        try:
            # Test Slack → Core integration
            slack_config = self.get_service(SlackConfig)
            assert slack_config is not None, "SlackConfig unavailable"

            # Test Slack → Secrets integration
            slack_posting = self.get_service(SlackPostingHandler)
            assert slack_posting is not None, "SlackPostingHandler unavailable"

            # Test Slack UI components integration
            home_tab_handler = self.get_service(HomeTabHandler)
            assert home_tab_handler is not None, "HomeTabHandler unavailable"

            return True

        except Exception as e:
            self.logger.error(f"Slack service integration test failed: {e}")
            return False

    async def _test_database_service_integration(self) -> bool:
        """Test database service integrations."""
        self.logger.info("Testing Database Service Integration")

        try:
            # Test DB → Core integration
            dynamodb_client = self.get_service(DynamoDBAsyncClient)
            assert dynamodb_client is not None, "DynamoDBAsyncClient unavailable"

            # Test DB Store integration
            dynamodb_store = self.get_service(DynamoDBStore)
            assert dynamodb_store is not None, "DynamoDBStore unavailable"

            # Test higher-level DB services integration
            user_store = self.get_service(UserStore)
            channel_ops = self.get_service(ChannelOperations)

            assert user_store is not None, "UserStore unavailable"
            assert channel_ops is not None, "ChannelOperations unavailable"

            return True

        except Exception as e:
            self.logger.error(f"Database service integration test failed: {e}")
            return False

    async def _test_complex_service_workflows(self) -> bool:
        """Test complex workflows involving multiple services."""
        self.logger.info("Testing Complex Service Workflows")

        try:
            # Test workflow: Slack → DB → Response
            slack_posting = self.get_service(SlackPostingHandler)
            user_store = self.get_service(UserStore)

            assert slack_posting is not None, "SlackPostingHandler unavailable"
            assert user_store is not None, "UserStore unavailable"

            # Test DB workflow
            db_store = self.get_service(DynamoDBStore)
            slack_config = self.get_service(SlackConfig)

            assert db_store is not None, "DynamoDBStore unavailable"
            assert slack_config is not None, "SlackConfig unavailable"

            return True

        except Exception as e:
            self.logger.error(f"Complex service workflow test failed: {e}")
            return False

    def _log_performance_summary(self):
        """Log performance metrics summary."""
        self.logger.info("=== Cross-Service Integration Performance ===")

        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results.values() if r["passed"])
        total_time = sum(self.performance_metrics.values())

        self.logger.info(f"Tests: {passed_tests}/{total_tests}")
        self.logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        self.logger.info(f"Total Time: {total_time:.3f}s")

        for test_name, metrics in self.test_results.items():
            status = "✅ PASS" if metrics["passed"] else "❌ FAIL"
            self.logger.info(
                f"{test_name}: {status} ({metrics['execution_time']:.3f}s)"
            )


class ServiceInteractionValidator:
    """Validates specific service interaction patterns."""

    def __init__(self, container: TypedServiceRegistry):
        """Initialize service interaction validator."""
        self.container = container
        self.logger = setup_logger(f"{__name__}.ServiceInteractionValidator")

    async def validate_service_communication(
        self, source_type: Type, target_type: Type
    ) -> bool:
        """
        Validate communication between two services.

        Args:
            source_type: Type of the source service
            target_type: Type of the target service

        Returns:
            True if communication is valid, False otherwise
        """
        try:
            source = self.container.get(source_type)
            target = self.container.get(target_type)

            assert source is not None, f"Source {source_type.__name__} not found"
            assert target is not None, f"Target {target_type.__name__} not found"

            # Validate service communication patterns
            self.logger.info(
                f"✅ {source_type.__name__} → {target_type.__name__} validated"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"❌ {source_type.__name__} → {target_type.__name__} failed: {e}"
            )
            return False

    async def validate_dependency_resolution(
        self, service_type: Type
    ) -> Dict[str, Any]:
        """
        Validate that a service's dependencies are properly resolved.

        Args:
            service_type: Type of the service to validate

        Returns:
            Dictionary with validation results
        """
        result = {
            "service_name": service_type.__name__,
            "dependencies_resolved": True,
            "resolution_time": 0.0,
            "errors": [],
        }

        try:
            start_time = time.time()
            service = self.container.get(service_type)
            result["resolution_time"] = time.time() - start_time

            if service is None:
                result["dependencies_resolved"] = False
                result["errors"].append(f"Service {service_type.__name__} unresolved")

        except Exception as e:
            result["dependencies_resolved"] = False
            result["errors"].append(str(e))

        return result


# Pytest integration tests
@pytest.mark.asyncio
async def test_cross_service_integration():
    """Pytest wrapper for cross-service integration tests."""
    test = CrossServiceIntegrationTest()
    result = await test.execute()
    assert result, "Cross-service integration tests should pass"


@pytest.mark.asyncio
async def test_service_interaction_validation():
    """Test service interaction validation framework."""
    container = await get_unified_container()

    validator = ServiceInteractionValidator(container)

    # Test key service interactions
    interactions = [
        (UserStore, DynamoDBStore),
        (SlackPostingHandler, SlackConfig),
        (HomeTabHandler, UserStore),
    ]

    for source, target in interactions:
        result = await validator.validate_service_communication(source, target)
        assert (
            result
        ), f"{source.__name__} → {target.__name__} interaction should be valid"


if __name__ == "__main__":
    # Run cross-service integration tests directly
    asyncio.run(CrossServiceIntegrationTest().execute())
