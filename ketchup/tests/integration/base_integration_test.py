#!/usr/bin/env python3
"""
Base class for all integration tests requiring the full DI container.

This module provides a reusable framework for integration tests that need
access to real services like DynamoDB, Slack API, OpenAI, etc.
"""
import os
import sys
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from packages.core.di_container import DIContainer
from packages.core.logging import setup_logger


class BaseIntegrationTest(ABC):
    """Base class for integration tests requiring full DI container."""

    def __init__(
        self,
        test_name: str,
        aws_profile: str = "campaign_prod_v7",
        aws_region: str = "eu-west-1",
        env_vars: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the integration test framework.

        Args:
            test_name: Name of the test for logging
            aws_profile: AWS profile to use (default: campaign_prod_v7)
            aws_region: AWS region (default: eu-west-1)
            env_vars: Additional environment variables to set
        """
        self.test_name = test_name
        self.aws_profile = aws_profile
        self.aws_region = aws_region
        self.env_vars = env_vars or {}
        self.container: Optional[DIContainer] = None
        self.logger = setup_logger(f"integration.{test_name}")

    async def setup_environment(self):
        """Set up environment variables for the test."""
        # Set AWS credentials
        os.environ["AWS_PROFILE"] = self.aws_profile
        os.environ["AWS_DEFAULT_REGION"] = self.aws_region

        # Set any additional environment variables
        for key, value in self.env_vars.items():
            os.environ[key] = value
            self.logger.info(f"Set environment variable: {key}")

    async def initialize_container(self) -> DIContainer:
        """Initialize the DI container with all dependencies."""
        self.logger.info("Initializing DI container...")
        self.container = DIContainer()
        await self.container.initialize()
        self.logger.info("DI container initialized successfully")
        return self.container

    def get_service(self, service_name: str) -> Any:
        """
        Get a single service from the container.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            The requested service instance
        """
        if not self.container:
            raise RuntimeError(
                "Container not initialized. Call initialize_container() first."
            )
        return self.container.get_by_name(service_name)

    def get_services(self, service_names: List[str]) -> Dict[str, Any]:
        """
        Get multiple services from the container.

        Args:
            service_names: List of service names to retrieve

        Returns:
            Dictionary mapping service names to instances
        """
        if not self.container:
            raise RuntimeError(
                "Container not initialized. Call initialize_container() first."
            )

        services = {}
        for name in service_names:
            services[name] = self.container.get_by_name(name)
        return services

    @abstractmethod
    async def run_test(self) -> bool:
        """
        Run the actual test logic. Must be implemented by subclasses.

        Returns:
            True if test passed, False otherwise
        """
        pass

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
            await self.setup_environment()

            # Initialize container
            await self.initialize_container()

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

        finally:
            # Clean up container resources
            if self.container:
                try:
                    await self.container.cleanup()
                except Exception as e:
                    self.logger.error(f"Error during container cleanup: {e}")


class SimpleIntegrationTest(BaseIntegrationTest):
    """
    A simpler integration test class for tests that don't need custom subclassing.

    This allows passing a test function directly instead of creating a subclass.
    """

    def __init__(
        self,
        test_name: str,
        test_func: Callable,
        required_services: List[str],
        aws_profile: str = "campaign_prod_v7",
        aws_region: str = "eu-west-1",
        env_vars: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize with a test function and required services.

        Args:
            test_name: Name of the test
            test_func: Async function to run as the test
            required_services: List of service names needed by the test
            aws_profile: AWS profile to use
            aws_region: AWS region
            env_vars: Additional environment variables
        """
        super().__init__(test_name, aws_profile, aws_region, env_vars)
        self.test_func = test_func
        self.required_services = required_services

    async def run_test(self) -> bool:
        """Run the provided test function with required services."""
        # Get all required services
        services = self.get_services(self.required_services)

        # Call the test function with services
        return await self.test_func(services, self.logger)


async def run_simple_integration_test(
    test_name: str,
    test_func: Callable,
    required_services: List[str],
    env_vars: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Convenience function to run a simple integration test.

    Args:
        test_name: Name of the test
        test_func: Async function to run as the test
        required_services: List of service names needed
        env_vars: Additional environment variables

    Returns:
        True if test passed, False otherwise
    """
    test = SimpleIntegrationTest(
        test_name=test_name,
        test_func=test_func,
        required_services=required_services,
        env_vars=env_vars,
    )
    return await test.execute()
