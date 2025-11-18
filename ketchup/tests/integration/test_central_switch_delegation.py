"""
Integration test for central switch delegation.

Verifies that packages.core.di_container.get_container() properly delegates
to TypedDI system when KETCHUP_USE_TYPED_DI=true.
"""

import pytest

from packages.core.typed_di_integration import TypedDIContainerAdapter


@pytest.mark.asyncio
async def test_central_switch_delegates_to_typed_di(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that di_container.get_container() returns TypedDIContainerAdapter when flag is true."""
    # Enable TypedDI via environment variable
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "true")

    # Import after setting environment variable to ensure flag is detected
    from packages.core.di_container import get_container

    # Get container through the central switch
    container = await get_container()

    # Verify it returns TypedDIContainerAdapter (TypedDI system)
    assert isinstance(container, TypedDIContainerAdapter), (
        f"Expected TypedDIContainerAdapter when KETCHUP_USE_TYPED_DI=true, "
        f"got {type(container).__name__}"
    )


@pytest.mark.asyncio
async def test_central_switch_uses_legacy_when_flag_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that di_container.get_container() uses legacy DIContainer when flag is false."""
    # Disable TypedDI via environment variable
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "false")

    from packages.core.di_container import DIContainer, get_container

    # Get container through the central switch
    container = await get_container()

    # Verify it returns legacy DIContainer
    assert isinstance(container, DIContainer), (
        f"Expected DIContainer when KETCHUP_USE_TYPED_DI=false, "
        f"got {type(container).__name__}"
    )

    # Clean up the singleton for next test
    from packages.core.di_container import cleanup_container

    await cleanup_container()


@pytest.mark.asyncio
async def test_central_switch_cleanup_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that cleanup_container() also delegates properly to TypedDI cleanup."""
    # Enable TypedDI
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "true")

    from packages.core.di_container import cleanup_container, get_container

    # Initialize TypedDI container
    container = await get_container()
    assert isinstance(container, TypedDIContainerAdapter)

    # Test cleanup delegation (should not raise errors)
    await cleanup_container()

    # Verify we can initialize again after cleanup
    container2 = await get_container()
    assert isinstance(container2, TypedDIContainerAdapter)

    await cleanup_container()  # Final cleanup


@pytest.mark.asyncio
async def test_central_switch_fallback_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that get_container() falls back to legacy when TypedDI import fails."""
    # Enable TypedDI flag but simulate ImportError
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "true")

    # Mock ImportError by making the module import fail
    import builtins
    import sys

    original_modules = sys.modules.copy()

    try:
        # Remove typed_di_integration from modules to simulate ImportError
        if "packages.core.typed_di_integration" in sys.modules:
            del sys.modules["packages.core.typed_di_integration"]

        # Mock __import__ to raise ImportError for typed_di_integration
        def mock_import(name, *args, **kwargs):
            if name == "packages.core.typed_di_integration" or name.endswith(
                "typed_di_integration"
            ):
                raise ImportError("Simulated ImportError for fallback testing")
            return original_import(name, *args, **kwargs)

        original_import = builtins.__import__
        monkeypatch.setattr(builtins, "__import__", mock_import)

        from packages.core.di_container import DIContainer, get_container

        # Get container - should fall back to legacy despite flag=true
        container = await get_container()

        # Verify it returns legacy DIContainer due to ImportError fallback
        assert isinstance(container, DIContainer), (
            f"Expected DIContainer fallback when TypedDI import fails, "
            f"got {type(container).__name__}"
        )

        # Clean up
        from packages.core.di_container import cleanup_container

        await cleanup_container()

    finally:
        # Restore original modules
        sys.modules.clear()
        sys.modules.update(original_modules)
        monkeypatch.undo()
