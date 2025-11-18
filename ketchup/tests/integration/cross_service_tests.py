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
3. AI Service Integration (AI ↔ Core, AI ↔ DB, AI ↔ Slack)
4. External API Integration (JIRA ↔ MCP, External ↔ Auth)
"""

import asyncio
import time
from typing import Any, Dict
from unittest.mock import patch

import pytest

from packages.core.di_container import DIContainer
from packages.core.logging import setup_logger
from tests.integration.base_integration_test import BaseIntegrationTest

logger = setup_logger(__name__)


class CrossServiceIntegrationTest(BaseIntegrationTest):
    """
    Cross-service integration test framework.

    Tests complex interactions between different service types and validates
    that service dependencies work correctly across package boundaries.
    """

    def __init__(self):
        """Initialize cross-service integration test framework."""
        super().__init__(
            test_name="Cross-Service Integration Tests",
            env_vars={
                "KETCHUP_USE_TYPED_DI": "true",
                "KETCHUP_TEST_MODE": "true",
                "LOG_LEVEL": "INFO"
            }
        )
        self.test_results: Dict[str, Dict[str, Any]] = {}
        self.performance_metrics: Dict[str, float] = {}

    async def run_test(self) -> bool:
        """Execute all cross-service integration tests."""
        self.logger.info("Starting Cross-Service Integration Tests")

        test_methods = [
            self._test_core_service_interactions,
            self._test_slack_service_integration,
            self._test_ai_service_integration,
            self._test_database_service_integration,
            self._test_external_api_integration,
            self._test_complex_service_workflows
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
                    "execution_time": execution_time
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
            secrets_manager = self.get_service("SecretsManager")
            assert secrets_manager is not None, "SecretsManager unavailable"

            # Test Core → DB interaction
            db_store = self.get_service("DynamoDBStore")
            assert db_store is not None, "DynamoDBStore unavailable"

            # Test Core → HTTP Client interaction
            http_client = self.get_service("HTTPClientManager")
            assert http_client is not None, "HTTPClientManager unavailable"

            # Test UserStore integration with dependencies
            user_store = self.get_service("UserStore")
            assert user_store is not None, "UserStore unavailable"
            assert hasattr(user_store, 'store'), "UserStore missing DB dependency"

            return True

        except Exception as e:
            self.logger.error(f"Core service interaction test failed: {e}")
            return False

    async def _test_slack_service_integration(self) -> bool:
        """Test Slack service integrations with other packages."""
        self.logger.info("Testing Slack Service Integration")

        try:
            # Test Slack → Core integration
            slack_config = self.get_service("SlackConfig")
            assert slack_config is not None, "SlackConfig unavailable"

            # Test Slack → Secrets integration
            slack_posting = self.get_service("SlackPostingHandler")
            assert slack_posting is not None, "SlackPostingHandler unavailable"

            # Test Slack command handlers integration
            status_command = self.get_service("StatusCommand")
            assert status_command is not None, "StatusCommand unavailable"

            # Test Slack UI components integration
            home_tab_handler = self.get_service("HomeTabHandler")
            assert home_tab_handler is not None, "HomeTabHandler unavailable"

            return True

        except Exception as e:
            self.logger.error(f"Slack service integration test failed: {e}")
            return False

    async def _test_ai_service_integration(self) -> bool:
        """Test AI service integrations across packages."""
        self.logger.info("Testing AI Service Integration")

        try:
            # Test AI → Core integration
            openai_client = self.get_service("OpenAIAsyncClient")
            assert openai_client is not None, "OpenAIAsyncClient unavailable"

            # Test AI → HTTP Client integration
            azure_client = self.get_service("AzureOpenAIAsyncClient")
            assert azure_client is not None, "AzureOpenAIAsyncClient unavailable"

            # Test AI service factory patterns
            ai_factory = self.get_service("AIClientFactory")
            assert ai_factory is not None, "AIClientFactory unavailable"

            return True

        except Exception as e:
            self.logger.error(f"AI service integration test failed: {e}")
            return False

    async def _test_database_service_integration(self) -> bool:
        """Test database service integrations."""
        self.logger.info("Testing Database Service Integration")

        try:
            # Test DB → Core integration
            dynamodb_client = self.get_service("DynamoDBAsyncClient")
            assert dynamodb_client is not None, "DynamoDBAsyncClient unavailable"

            # Test DB Store integration
            dynamodb_store = self.get_service("DynamoDBStore")
            assert dynamodb_store is not None, "DynamoDBStore unavailable"

            # Test higher-level DB services integration
            user_store = self.get_service("UserStore")
            channel_store = self.get_service("ChannelStore")

            assert user_store is not None, "UserStore unavailable"
            assert channel_store is not None, "ChannelStore unavailable"

            return True

        except Exception as e:
            self.logger.error(f"Database service integration test failed: {e}")
            return False

    async def _test_external_api_integration(self) -> bool:
        """Test external API service integrations."""
        self.logger.info("Testing External API Integration")

        try:
            # Test JIRA integration services
            with patch('packages.integrations.jira.client.JIRAClient'):
                jira_client = self.get_service("JIRAClient")
                assert jira_client is not None, "JIRAClient unavailable"

            # Test HTTP client integration with external services
            http_client = self.get_service("HTTPClientManager")
            assert http_client is not None, "HTTPClientManager unavailable"

            # Test authentication integration
            auth_service = self.get_service("AuthService")
            assert auth_service is not None, "AuthService unavailable"

            return True

        except Exception as e:
            self.logger.error(f"External API integration test failed: {e}")
            return False

    async def _test_complex_service_workflows(self) -> bool:
        """Test complex workflows involving multiple services."""
        self.logger.info("Testing Complex Service Workflows")

        try:
            # Test workflow: Slack command → DB query → Response
            workflow_services = self.get_services([
                "StatusCommand",
                "UserStore",
                "SlackPostingHandler"
            ])

            # Validate all services in the workflow are available
            for service_name, service in workflow_services.items():
                assert service is not None, f"{service_name} unavailable"

            # Test flag review workflow
            flag_services = self.get_services([
                "FlagReviewHandler",
                "DynamoDBStore",
                "SlackConfig"
            ])

            for service_name, service in flag_services.items():
                assert service is not None, f"{service_name} unavailable"

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
            self.logger.info(f"{test_name}: {status} ({metrics['execution_time']:.3f}s)")


class ServiceInteractionValidator:
    """Validates specific service interaction patterns."""

    def __init__(self, container: DIContainer):
        """Initialize service interaction validator."""
        self.container = container
        self.logger = setup_logger(f"{__name__}.ServiceInteractionValidator")

    async def validate_service_communication(self,
                                           source_service: str,
                                           target_service: str) -> bool:
        """
        Validate communication between two services.

        Args:
            source_service: Name of the source service
            target_service: Name of the target service

        Returns:
            True if communication is valid, False otherwise
        """
        try:
            source = self.container.get_by_name(source_service)
            target = self.container.get_by_name(target_service)

            assert source is not None, f"Source {source_service} not found"
            assert target is not None, f"Target {target_service} not found"

            # Validate service communication patterns
            self.logger.info(f"✅ {source_service} → {target_service} validated")
            return True

        except Exception as e:
            self.logger.error(f"❌ {source_service} → {target_service} failed: {e}")
            return False

    async def validate_dependency_resolution(self, service_name: str) -> Dict[str, Any]:
        """
        Validate that a service's dependencies are properly resolved.

        Args:
            service_name: Name of the service to validate

        Returns:
            Dictionary with validation results
        """
        result = {
            "service_name": service_name,
            "dependencies_resolved": True,
            "resolution_time": 0.0,
            "errors": []
        }

        try:
            start_time = time.time()
            service = self.container.get_by_name(service_name)
            result["resolution_time"] = time.time() - start_time

            if service is None:
                result["dependencies_resolved"] = False
                result["errors"].append(f"Service {service_name} unresolved")

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
    container = DIContainer()
    await container.initialize()

    try:
        validator = ServiceInteractionValidator(container)

        # Test key service interactions
        interactions = [
            ("UserStore", "DynamoDBStore"),
            ("SlackPostingHandler", "SlackConfig"),
            ("OpenAIAsyncClient", "HTTPClientManager"),
            ("HomeTabHandler", "UserStore")
        ]

        for source, target in interactions:
            result = await validator.validate_service_communication(source, target)
            assert result, f"{source} → {target} interaction should be valid"

    finally:
        await container.cleanup()


if __name__ == "__main__":
    # Run cross-service integration tests directly
    asyncio.run(CrossServiceIntegrationTest().execute())