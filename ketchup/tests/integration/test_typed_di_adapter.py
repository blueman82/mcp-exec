"""
Integration tests for TypedServiceRegistry functionality.

Covers:
- Type-safe service resolution
- Error handling for invalid params and unknown services
- End-to-end resolution via get_unified_container
- Registry initialization and lifecycle management
"""

from typing import Protocol

import pytest

from packages.core.typed_di import (
    MissingDependencyError,
    NotInitializedError,
    TypedServiceRegistry,
)


# --- Test Protocols and Implementations --- #
class SlackConfigProtocol(Protocol):
    """Protocol for Slack configuration service."""

    def some_method(self) -> str:
        """Return a string to prove functional behavior."""
        ...


class SlackConfigImpl:
    """Concrete implementation used for tests."""

    def some_method(self) -> str:  # noqa: D401 - simple test method
        return "ok"


class UnregisteredProtocol(Protocol):
    """Protocol not registered with the registry (for negative tests)."""

    def missing(self) -> None:  # pragma: no cover - signature only
        ...


# --- Helpers --- #
async def build_test_registry() -> TypedServiceRegistry:
    """Create a typed registry with test service registration.

    Returns:
        registry: ready for use; registry already initialized and frozen.
    """
    registry = TypedServiceRegistry()
    registry.register(SlackConfigProtocol, lambda r: SlackConfigImpl(), dependencies=[])
    await registry.initialize_all()
    registry.freeze_after_init()
    return registry


# --- Registry Contract Tests (unit-level) --- #
@pytest.mark.asyncio
async def test_typed_access_path() -> None:
    """registry.get(SlackConfigProtocol) resolves via typed registry."""
    registry = await build_test_registry()
    result = await registry.aget(SlackConfigProtocol)
    assert isinstance(result, SlackConfigImpl)
    assert result.some_method() == "ok"


@pytest.mark.asyncio
async def test_registry_error_handling() -> None:
    """Cover unknown type, pre-init, and invalid param errors."""
    # Unknown type → MissingDependencyError bubbling from registry
    registry = await build_test_registry()
    with pytest.raises(MissingDependencyError):
        await registry.aget(UnregisteredProtocol)  # type: ignore[arg-type]

    # Calling before registry initialization → NotInitializedError
    uninitialized_registry = TypedServiceRegistry()
    uninitialized_registry.register(
        SlackConfigProtocol, lambda r: SlackConfigImpl(), dependencies=[]
    )
    with pytest.raises(NotInitializedError):
        await uninitialized_registry.aget(SlackConfigProtocol)


@pytest.mark.asyncio
async def test_production_bug_prevention() -> None:
    """Directly validate the production bug pattern raises a clear error."""
    registry = await build_test_registry()
    # Type system should catch this at compile time, but verify runtime behavior
    with pytest.raises((TypeError, MissingDependencyError)):
        await registry.aget("slack_config")  # type: ignore[arg-type]


# --- End-to-End Resolution via get_unified_container --- #
@pytest.mark.asyncio
async def test_typed_di_resolution() -> None:
    """get_unified_container returns TypedServiceRegistry with proper resolution."""
    from packages.core.typed_di_integration import get_unified_container

    container = await get_unified_container()
    assert isinstance(container, TypedServiceRegistry)

    # Test that essential services are available
    from packages.secrets.manager import SecretsManager

    secrets_manager = await container.aget(SecretsManager)
    assert secrets_manager is not None


@pytest.mark.asyncio
async def test_registry_lifecycle() -> None:
    """Test registry initialization and cleanup lifecycle."""
    from packages.core.typed_di_integration import (
        cleanup_unified_container,
        get_unified_container,
    )

    # Initialize
    container = await get_unified_container()
    assert container is not None

    # Cleanup
    await cleanup_unified_container()

    # Can initialize again
    container2 = await get_unified_container()
    assert container2 is not None

    # Final cleanup
    await cleanup_unified_container()


# --- Service Resolution Tests --- #
@pytest.mark.asyncio
async def test_essential_services_available() -> None:
    """Test that essential services are properly registered and available."""
    from packages.core.typed_di_integration import get_unified_container
    from packages.db.config.dynamodb_config import DynamoDBConfig
    from packages.secrets.manager import SecretsManager
    from packages.slack.config.slack_config import SlackConfig

    container = await get_unified_container()

    # Test essential services
    secrets_manager = await container.aget(SecretsManager)
    assert secrets_manager is not None

    slack_config = await container.aget(SlackConfig)
    assert slack_config is not None

    dynamodb_config = await container.aget(DynamoDBConfig)
    assert dynamodb_config is not None
