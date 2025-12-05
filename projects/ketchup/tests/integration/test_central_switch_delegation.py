"""
Integration test for central switch delegation.

Verifies that packages.core.typed_di_integration properly provides
the TypedDI system for service resolution.
"""

import pytest

from packages.core.typed_di import TypedServiceRegistry


@pytest.mark.asyncio
async def test_central_switch_uses_typed_di() -> None:
    """Test that get_unified_container returns TypedServiceRegistry."""
    from packages.core.typed_di_integration import get_unified_container

    # Get container
    container = await get_unified_container()

    # Verify it returns TypedServiceRegistry
    assert isinstance(
        container, TypedServiceRegistry
    ), f"Expected TypedServiceRegistry, got {type(container).__name__}"


@pytest.mark.asyncio
async def test_container_lifecycle() -> None:
    """Test that cleanup_unified_container works properly."""
    from packages.core.typed_di_integration import (
        cleanup_unified_container,
        get_unified_container,
    )

    # Initialize TypedDI container
    container = await get_unified_container()
    assert isinstance(container, TypedServiceRegistry)

    # Test cleanup (should not raise errors)
    await cleanup_unified_container()

    # Verify we can initialize again after cleanup
    container2 = await get_unified_container()
    assert isinstance(container2, TypedServiceRegistry)

    await cleanup_unified_container()  # Final cleanup


@pytest.mark.asyncio
async def test_essential_services_available() -> None:
    """Test that essential services are properly registered and available."""
    from packages.core.typed_di_integration import get_unified_container
    from packages.secrets.manager import SecretsManager
    from packages.slack.config.slack_config import SlackConfig

    container = await get_unified_container()

    # Test essential services
    secrets_manager = await container.aget(SecretsManager)
    assert secrets_manager is not None

    slack_config = await container.aget(SlackConfig)
    assert slack_config is not None
