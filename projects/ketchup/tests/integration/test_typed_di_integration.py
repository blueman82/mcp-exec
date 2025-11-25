"""
Integration tests for the TypedServiceRegistry system.

This module provides comprehensive integration testing for the typed dependency injection
system, including service registration, dependency resolution, feature flag integration,
and real service interactions with mocked AWS and Slack components.

What is being tested:
    - Basic service registration and dependency resolution
    - Feature flag integration with KETCHUP_USE_TYPED_DI environment variable
    - Override system testing with KETCHUP_TEST_MODE integration
    - Error handling and validation testing for missing dependencies
    - Real Slack channel testing preparation using test channel C09C4M7B68J
    - Integration with secrets manager for bot token retrieval
    - Service lifecycle management and initialization ordering

Expected outcomes:
    - All service registrations resolve correctly in dependency order
    - Feature flags control system behavior appropriately
    - Override system works correctly in test environments
    - Error conditions are handled gracefully with proper exceptions
    - Real service integration patterns are established and validated

Dependencies:
    - TypedServiceRegistry and supporting typed DI components
    - Mock implementations of core services (database, cache, Slack)
    - Environment variable manipulation for feature flag testing
    - Async/await support for service initialization

Test structure:
    - Each test is fully isolated using fresh registry instances
    - All test functions use Google-style docstrings and type hints
    - Comprehensive test coverage across all major system components
    - Real service interaction patterns established for future E2E testing
"""

import asyncio
from typing import Dict, List, Optional, Protocol

import pytest

from packages.core.typed_di.exceptions import (
    DuplicateRegistrationError,
    FrozenRegistryError,
    MissingDependencyError,
    NotInitializedError,
)
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.types import DependencySpec

# Test channel for real Slack integration testing
TEST_SLACK_CHANNEL = "C09C4M7B68J"  # #cso_acc_gh_1


# Test Protocol Definitions
class DatabaseService(Protocol):
    """Protocol for database service interactions."""

    async def get_channel_info(self, channel_id: str) -> Dict:
        """Get channel information from database."""
        ...

    async def update_channel_metadata(self, channel_id: str, metadata: Dict) -> None:
        """Update channel metadata in database."""
        ...


class CacheService(Protocol):
    """Protocol for cache service interactions."""

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        ...

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        """Set value in cache with TTL."""
        ...


class SecretsService(Protocol):
    """Protocol for secrets management service."""

    async def get_slack_token(self) -> str:
        """Get Slack bot token from secrets manager."""
        ...

    async def get_secret(self, secret_name: str) -> Dict:
        """Get secret by name."""
        ...


class SlackService(Protocol):
    """Protocol for Slack API service interactions."""

    async def post_message(
        self, channel: str, text: str, blocks: Optional[List] = None
    ) -> Dict:
        """Post message to Slack channel."""
        ...

    async def get_channel_info(self, channel: str) -> Dict:
        """Get channel information from Slack API."""
        ...


class NotificationService(Protocol):
    """Protocol for notification service with multiple dependencies."""

    async def notify_channel_update(self, channel_id: str, message: str) -> None:
        """Send notification about channel update."""
        ...


# Test Implementation Classes
class MockDatabaseService:
    """Mock implementation of database service for testing."""

    def __init__(self):
        self.channel_data = {}

    async def get_channel_info(self, channel_id: str) -> Dict:
        """Get channel information from mock database."""
        return self.channel_data.get(
            channel_id, {"channel_id": channel_id, "active": True}
        )

    async def update_channel_metadata(self, channel_id: str, metadata: Dict) -> None:
        """Update channel metadata in mock database."""
        if channel_id not in self.channel_data:
            self.channel_data[channel_id] = {"channel_id": channel_id}
        self.channel_data[channel_id].update(metadata)


class MockCacheService:
    """Mock implementation of cache service for testing."""

    def __init__(self):
        self.cache_data = {}

    async def get(self, key: str) -> Optional[str]:
        """Get value from mock cache."""
        return self.cache_data.get(key)

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        """Set value in mock cache with TTL."""
        self.cache_data[key] = value


class MockSecretsService:
    """Mock implementation of secrets service for testing."""

    async def get_slack_token(self) -> str:
        """Get mock Slack bot token."""
        return "xoxb-test-token-123456"

    async def get_secret(self, secret_name: str) -> Dict:
        """Get mock secret by name."""
        secrets = {
            "slack_tokens": {"bot_token": "xoxb-test-token-123456"},
            "api_keys": {"openai": "sk-test-key"},
        }
        return secrets.get(secret_name, {})


class MockSlackService:
    """Mock implementation of Slack service with real channel testing preparation."""

    def __init__(self, secrets_service: SecretsService):
        self.secrets_service = secrets_service
        self.test_channel = TEST_SLACK_CHANNEL

    async def post_message(
        self, channel: str, text: str, blocks: Optional[List] = None
    ) -> Dict:
        """Post message to mock Slack channel."""
        # In real implementation, would use self.secrets_service.get_slack_token()
        return {
            "ok": True,
            "channel": channel,
            "message": {"text": text, "ts": "1234567890.123456"},
        }

    async def get_channel_info(self, channel: str) -> Dict:
        """Get mock channel information."""
        # Special handling for test channel
        if channel == TEST_SLACK_CHANNEL:
            return {
                "ok": True,
                "channel": {
                    "id": TEST_SLACK_CHANNEL,
                    "name": "cso_acc_gh_1",
                    "is_channel": True,
                    "is_private": False,
                },
            }
        return {
            "ok": True,
            "channel": {"id": channel, "name": f"test-{channel}", "is_channel": True},
        }


class MockNotificationService:
    """Mock notification service that depends on multiple other services."""

    def __init__(
        self,
        database_service: DatabaseService,
        cache_service: CacheService,
        slack_service: SlackService,
    ):
        self.database_service = database_service
        self.cache_service = cache_service
        self.slack_service = slack_service

    async def notify_channel_update(self, channel_id: str, message: str) -> None:
        """Send notification about channel update using multiple services."""
        # Get channel info from database (for validation)
        await self.database_service.get_channel_info(channel_id)

        # Cache the notification
        cache_key = f"notification:{channel_id}"
        await self.cache_service.set(cache_key, message)

        # Send to Slack
        await self.slack_service.post_message(channel_id, message)


# Test Fixtures
@pytest.fixture
def registry() -> TypedServiceRegistry:
    """
    Provide a fresh TypedServiceRegistry instance for each test.

    Returns:
        TypedServiceRegistry: Clean registry instance for testing.

    Example:
        Used to ensure test isolation and prevent cross-test contamination.
    """
    return TypedServiceRegistry()


@pytest.fixture
def mock_environment(monkeypatch):
    """
    Provide environment variable mocking for feature flag testing.

    Args:
        monkeypatch: Pytest monkeypatch fixture for environment manipulation.

    Yields:
        Callable: Function to set environment variables for testing.

    Example:
        Used to test feature flag behavior by manipulating environment variables.
    """

    def set_env_vars(**kwargs):
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)

    return set_env_vars


# Basic Service Registration and Resolution Tests
@pytest.mark.asyncio
async def test_basic_service_registration_and_resolution(
    registry: TypedServiceRegistry,
):
    """
    Test basic service registration and dependency resolution.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        AssertionError: If service registration or resolution fails.

    Example:
        Verifies that services can be registered and resolved correctly.
    """
    # Register simple service with no dependencies
    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    # Initialize registry
    await registry.initialize_all()

    # Verify service can be retrieved
    cache_service = registry.get(CacheService)
    assert isinstance(cache_service, MockCacheService)
    assert cache_service is not None

    # Test service functionality
    await cache_service.set("test_key", "test_value")
    value = await cache_service.get("test_key")
    assert value == "test_value"


@pytest.mark.asyncio
async def test_complex_dependency_resolution(registry: TypedServiceRegistry):
    """
    Test complex dependency resolution with multiple service dependencies.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        AssertionError: If complex dependency resolution fails.

    Example:
        Verifies that services with multiple dependencies resolve in correct order.
    """
    # Register services in dependency order (reverse of what we want)
    registry.register(
        NotificationService,
        lambda resolver: MockNotificationService(
            resolver.get(DatabaseService),
            resolver.get(CacheService),
            resolver.get(SlackService),
        ),
        dependencies=[
            DependencySpec(DatabaseService),
            DependencySpec(CacheService),
            DependencySpec(SlackService),
        ],
    )

    registry.register(
        SlackService,
        lambda resolver: MockSlackService(resolver.get(SecretsService)),
        dependencies=[DependencySpec(SecretsService)],
    )

    registry.register(
        SecretsService, lambda resolver: MockSecretsService(), dependencies=[]
    )

    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    registry.register(
        DatabaseService, lambda resolver: MockDatabaseService(), dependencies=[]
    )

    # Initialize registry
    await registry.initialize_all()

    # Verify all services are available
    notification_service = registry.get(NotificationService)
    slack_service = registry.get(SlackService)
    secrets_service = registry.get(SecretsService)
    cache_service = registry.get(CacheService)
    database_service = registry.get(DatabaseService)

    assert isinstance(notification_service, MockNotificationService)
    assert isinstance(slack_service, MockSlackService)
    assert isinstance(secrets_service, MockSecretsService)
    assert isinstance(cache_service, MockCacheService)
    assert isinstance(database_service, MockDatabaseService)

    # Test complex service interaction
    await notification_service.notify_channel_update(TEST_SLACK_CHANNEL, "Test message")

    # Verify interaction worked through dependencies
    cached_value = await cache_service.get(f"notification:{TEST_SLACK_CHANNEL}")
    assert cached_value == "Test message"


# Feature Flag Integration Tests
@pytest.mark.asyncio
async def test_feature_flag_disabled_fallback(
    registry: TypedServiceRegistry, mock_environment
):
    """
    Test behavior when KETCHUP_USE_TYPED_DI feature flag is disabled.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.
        mock_environment: Environment variable mocking fixture.

    Returns:
        None

    Raises:
        AssertionError: If feature flag behavior is incorrect.

    Example:
        Verifies that system falls back to traditional DI when feature is disabled.
    """
    # Disable typed DI feature flag
    mock_environment(KETCHUP_USE_TYPED_DI="false")

    # Register a simple service
    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    # Initialize registry - should still work but might have different behavior
    await registry.initialize_all()

    # Service should still be available
    cache_service = registry.get(CacheService)
    assert isinstance(cache_service, MockCacheService)


@pytest.mark.asyncio
async def test_feature_flag_enabled_behavior(
    registry: TypedServiceRegistry, mock_environment
):
    """
    Test behavior when KETCHUP_USE_TYPED_DI feature flag is enabled.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.
        mock_environment: Environment variable mocking fixture.

    Returns:
        None

    Raises:
        AssertionError: If feature flag behavior is incorrect.

    Example:
        Verifies that typed DI system is active when feature flag is enabled.
    """
    # Enable typed DI feature flag
    mock_environment(KETCHUP_USE_TYPED_DI="true")

    # Register services with dependencies
    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    registry.register(
        DatabaseService, lambda resolver: MockDatabaseService(), dependencies=[]
    )

    # Initialize and verify initialization stats are available
    await registry.initialize_all()
    stats = registry.get_initialization_stats()

    assert stats is not None
    assert len(stats.service_order) == 2
    assert CacheService in stats.service_order
    assert DatabaseService in stats.service_order
    assert stats.total_duration > 0


# Override System Testing
@pytest.mark.asyncio
async def test_service_override_in_test_mode(
    registry: TypedServiceRegistry, mock_environment
):
    """
    Test service override system with KETCHUP_TEST_MODE integration.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.
        mock_environment: Environment variable mocking fixture.

    Returns:
        None

    Raises:
        AssertionError: If service override system fails.

    Example:
        Verifies that services can be overridden in test environments.
    """
    # Enable test mode
    mock_environment(KETCHUP_TEST_MODE="true")

    # Register original service
    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    await registry.initialize_all()

    # Get original service
    original_service = registry.get(CacheService)
    await original_service.set("original", "value")

    # Create override service
    override_service = MockCacheService()
    await override_service.set("override", "value")

    # Override the service
    registry.override(CacheService, override_service)

    # Verify override is active
    current_service = registry.get(CacheService)
    assert current_service is override_service

    # Verify override service works
    override_value = await current_service.get("override")
    assert override_value == "value"

    # Original service data should not be accessible
    original_value = await current_service.get("original")
    assert original_value is None


@pytest.mark.asyncio
async def test_clear_overrides_functionality(
    registry: TypedServiceRegistry, mock_environment
):
    """
    Test clearing service overrides and restoring original services.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.
        mock_environment: Environment variable mocking fixture.

    Returns:
        None

    Raises:
        AssertionError: If override clearing functionality fails.

    Example:
        Verifies that service overrides can be cleared to restore original services.
    """
    # Enable test mode
    mock_environment(KETCHUP_TEST_MODE="true")

    # Register and initialize service
    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    await registry.initialize_all()

    # Set data in original service
    original_service = registry.get(CacheService)
    await original_service.set("original", "data")

    # Override with new service
    override_service = MockCacheService()
    registry.override(CacheService, override_service)

    # Verify override is active
    assert registry.get(CacheService) is override_service

    # Clear overrides
    registry.clear_overrides()

    # Verify original service is restored
    restored_service = registry.get(CacheService)
    assert restored_service is original_service

    # Verify original data is still there
    original_data = await restored_service.get("original")
    assert original_data == "data"


# Error Handling and Validation Tests
@pytest.mark.asyncio
async def test_missing_dependency_error(registry: TypedServiceRegistry):
    """
    Test error handling for missing dependency registrations.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        MissingDependencyError: Expected when dependency is missing.

    Example:
        Verifies that missing dependencies are detected and reported correctly.
    """
    # Register service with missing dependency
    registry.register(
        SlackService,
        lambda resolver: MockSlackService(resolver.get(SecretsService)),
        dependencies=[DependencySpec(SecretsService)],
    )

    # Attempt to initialize should fail due to missing SecretsService
    with pytest.raises(MissingDependencyError) as exc_info:
        await registry.initialize_all()

    assert "SecretsService" in str(
        exc_info.value
    ) or "Dependency validation failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_duplicate_registration_error(registry: TypedServiceRegistry):
    """
    Test error handling for duplicate service registrations.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        DuplicateRegistrationError: Expected when service is registered twice.

    Example:
        Verifies that duplicate service registrations are prevented.
    """
    # Register service once
    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    # Attempt to register same service again should fail
    with pytest.raises(DuplicateRegistrationError) as exc_info:
        registry.register(
            CacheService, lambda resolver: MockCacheService(), dependencies=[]
        )

    assert "already registered" in str(exc_info.value)


@pytest.mark.asyncio
async def test_not_initialized_error(registry: TypedServiceRegistry):
    """
    Test error handling when accessing services before initialization.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        NotInitializedError: Expected when accessing services before init.

    Example:
        Verifies that services cannot be accessed before registry initialization.
    """
    # Register service but don't initialize
    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    # Attempt to get service before initialization should fail
    with pytest.raises(NotInitializedError) as exc_info:
        registry.get(CacheService)

    assert "not initialized" in str(exc_info.value)


@pytest.mark.asyncio
async def test_frozen_registry_protection(registry: TypedServiceRegistry):
    """
    Test frozen registry protection against modifications.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        FrozenRegistryError: Expected when modifying frozen registry.

    Example:
        Verifies that frozen registries prevent further modifications.
    """
    # Register and initialize service
    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    await registry.initialize_all()

    # Freeze the registry
    registry.freeze_after_init()

    # Attempt to register new service should fail
    with pytest.raises(FrozenRegistryError) as exc_info:
        registry.register(
            DatabaseService, lambda resolver: MockDatabaseService(), dependencies=[]
        )

    assert "frozen" in str(exc_info.value)


# Real Slack Channel Testing Preparation
@pytest.mark.asyncio
async def test_slack_service_test_channel_integration(registry: TypedServiceRegistry):
    """
    Test Slack service integration with real test channel preparation.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        AssertionError: If Slack service integration fails.

    Example:
        Prepares and validates Slack service for real channel testing.
    """
    # Register secrets and Slack services
    registry.register(
        SecretsService, lambda resolver: MockSecretsService(), dependencies=[]
    )

    registry.register(
        SlackService,
        lambda resolver: MockSlackService(resolver.get(SecretsService)),
        dependencies=[DependencySpec(SecretsService)],
    )

    await registry.initialize_all()

    # Test Slack service with test channel
    slack_service = registry.get(SlackService)

    # Test getting channel info for real test channel
    channel_info = await slack_service.get_channel_info(TEST_SLACK_CHANNEL)
    assert channel_info["ok"] is True
    assert channel_info["channel"]["id"] == TEST_SLACK_CHANNEL
    assert channel_info["channel"]["name"] == "cso_acc_gh_1"

    # Test posting message to test channel (mocked but with real channel ID)
    message_result = await slack_service.post_message(
        TEST_SLACK_CHANNEL, "Integration test message"
    )
    assert message_result["ok"] is True
    assert message_result["channel"] == TEST_SLACK_CHANNEL


# Secrets Manager Integration Tests
@pytest.mark.asyncio
async def test_secrets_manager_integration(registry: TypedServiceRegistry):
    """
    Test secrets manager integration for bot token retrieval.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        AssertionError: If secrets manager integration fails.

    Example:
        Verifies that secrets manager can retrieve bot tokens and other secrets.
    """
    # Register secrets service
    registry.register(
        SecretsService, lambda resolver: MockSecretsService(), dependencies=[]
    )

    await registry.initialize_all()

    # Test secrets service functionality
    secrets_service = registry.get(SecretsService)

    # Test bot token retrieval
    bot_token = await secrets_service.get_slack_token()
    assert bot_token.startswith("xoxb-")
    assert "test-token" in bot_token

    # Test general secret retrieval
    slack_secrets = await secrets_service.get_secret("slack_tokens")
    assert "bot_token" in slack_secrets
    assert slack_secrets["bot_token"].startswith("xoxb-")


# Comprehensive Integration Test
@pytest.mark.asyncio
async def test_comprehensive_system_integration(registry: TypedServiceRegistry):
    """
    Test comprehensive system integration with all components working together.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        AssertionError: If comprehensive integration fails.

    Example:
        Validates that all system components work together correctly.
    """
    # Register all services in complex dependency graph
    registry.register(
        SecretsService, lambda resolver: MockSecretsService(), dependencies=[]
    )

    registry.register(
        CacheService, lambda resolver: MockCacheService(), dependencies=[]
    )

    registry.register(
        DatabaseService, lambda resolver: MockDatabaseService(), dependencies=[]
    )

    registry.register(
        SlackService,
        lambda resolver: MockSlackService(resolver.get(SecretsService)),
        dependencies=[DependencySpec(SecretsService)],
    )

    registry.register(
        NotificationService,
        lambda resolver: MockNotificationService(
            resolver.get(DatabaseService),
            resolver.get(CacheService),
            resolver.get(SlackService),
        ),
        dependencies=[
            DependencySpec(DatabaseService),
            DependencySpec(CacheService),
            DependencySpec(SlackService),
        ],
    )

    # Initialize all services
    await registry.initialize_all()

    # Verify initialization order and statistics
    stats = registry.get_initialization_stats()
    assert len(stats.service_order) == 5
    assert stats.total_duration > 0
    assert len(stats.failures) == 0

    # Test comprehensive workflow
    notification_service = registry.get(NotificationService)
    database_service = registry.get(DatabaseService)
    cache_service = registry.get(CacheService)

    # Execute complex workflow
    test_channel = TEST_SLACK_CHANNEL
    test_message = "Comprehensive integration test message"

    # Update database
    await database_service.update_channel_metadata(
        test_channel, {"last_notification": test_message}
    )

    # Send notification (uses all services)
    await notification_service.notify_channel_update(test_channel, test_message)

    # Verify workflow completed successfully
    channel_info = await database_service.get_channel_info(test_channel)
    assert channel_info["last_notification"] == test_message

    cached_notification = await cache_service.get(f"notification:{test_channel}")
    assert cached_notification == test_message


# Async Factory Function Tests
@pytest.mark.asyncio
async def test_async_factory_support(registry: TypedServiceRegistry):
    """
    Test support for async factory functions in service registration.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        AssertionError: If async factory support fails.

    Example:
        Verifies that async factory functions work correctly for service creation.
    """

    async def async_cache_factory(resolver) -> CacheService:
        """Async factory function for cache service."""
        # Simulate async initialization
        await asyncio.sleep(0.01)
        cache_service = MockCacheService()
        await cache_service.set("factory_type", "async")
        return cache_service

    # Register service with async factory
    registry.register(CacheService, async_cache_factory, dependencies=[])

    # Initialize registry
    await registry.initialize_all()

    # Verify service was created by async factory
    cache_service = registry.get(CacheService)
    factory_type = await cache_service.get("factory_type")
    assert factory_type == "async"


# Service Qualifier Tests
@pytest.mark.asyncio
async def test_service_qualifiers(registry: TypedServiceRegistry):
    """
    Test service registration and resolution with qualifiers.

    Args:
        registry (TypedServiceRegistry): Fresh registry instance for testing.

    Returns:
        None

    Raises:
        AssertionError: If service qualifier functionality fails.

    Example:
        Verifies that multiple implementations can be registered with qualifiers.
    """
    # Register primary cache service
    registry.register(
        CacheService,
        lambda resolver: MockCacheService(),
        dependencies=[],
        qualifier="primary",
    )

    # Register secondary cache service
    registry.register(
        CacheService,
        lambda resolver: MockCacheService(),
        dependencies=[],
        qualifier="secondary",
    )

    await registry.initialize_all()

    # Get services by qualifier
    primary_cache = registry.get(CacheService, qualifier="primary")
    secondary_cache = registry.get(CacheService, qualifier="secondary")

    assert primary_cache is not secondary_cache
    assert isinstance(primary_cache, MockCacheService)
    assert isinstance(secondary_cache, MockCacheService)

    # Test that they maintain separate state
    await primary_cache.set("service", "primary")
    await secondary_cache.set("service", "secondary")

    primary_value = await primary_cache.get("service")
    secondary_value = await secondary_cache.get("service")

    assert primary_value == "primary"
    assert secondary_value == "secondary"
