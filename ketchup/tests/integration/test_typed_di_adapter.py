"""
Integration tests for the TypedDIContainerAdapter and feature-flag bridge.

Covers:
- Adapter contract: get(Type) vs get_by_name(str)
- Error handling for invalid params and unknown services
- End-to-end resolution via get_unified_container with feature flag
- Feature flag transitions and rollback behavior
"""

from typing import Protocol

import pytest

from packages.core.typed_di.compatibility import CompatibilityBridge
from packages.core.typed_di.exceptions import (
    MissingDependencyError,
    NotInitializedError,
)
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di_integration import TypedDIContainerAdapter


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
async def build_adapter_with_mapping() -> (
    tuple[TypedDIContainerAdapter, TypedServiceRegistry]
):
    """Create a typed registry + compatibility bridge + adapter with test mapping.

    Returns:
        (adapter, registry) ready for use; registry already initialized and frozen.
    """
    registry = TypedServiceRegistry()
    registry.register(SlackConfigProtocol, lambda r: SlackConfigImpl(), dependencies=[])
    await registry.initialize_all()
    registry.freeze_after_init()

    bridge = CompatibilityBridge(registry)
    # Override mapping for deterministic behavior in tests
    bridge._string_to_type_map = {  # type: ignore[attr-defined]
        "slack_config": (SlackConfigProtocol, None)
    }

    adapter = TypedDIContainerAdapter(registry, bridge)
    return adapter, registry


# --- Adapter Contract Tests (unit-level) --- #
@pytest.mark.asyncio
async def test_legacy_string_access_path() -> None:
    """container.get_by_name('slack_config') resolves via bridge (legacy path)."""
    adapter, _ = await build_adapter_with_mapping()
    result = adapter.get_by_name("slack_config")
    assert isinstance(result, SlackConfigImpl)
    assert result.some_method() == "ok"


@pytest.mark.asyncio
async def test_typed_access_path() -> None:
    """container.get(SlackConfigProtocol) resolves via typed registry (new path)."""
    adapter, _ = await build_adapter_with_mapping()
    result = adapter.get(SlackConfigProtocol)
    assert isinstance(result, SlackConfigImpl)


@pytest.mark.asyncio
async def test_access_parity() -> None:
    """Both access paths return functionally equivalent instances (parity, not identity)."""
    adapter, _ = await build_adapter_with_mapping()
    legacy_result = adapter.get_by_name("slack_config")
    typed_result = adapter.get(SlackConfigProtocol)

    assert type(legacy_result) is type(typed_result)
    assert legacy_result.some_method() == typed_result.some_method()


@pytest.mark.asyncio
async def test_adapter_error_handling() -> None:
    """Cover unknown key, unknown type, pre-init, and invalid param errors."""
    # Unknown string key → RuntimeError with clear message
    adapter, _ = await build_adapter_with_mapping()
    with pytest.raises(RuntimeError, match="Unknown service key: nonexistent"):
        adapter.get_by_name("nonexistent")

    # Unknown type → MissingDependencyError bubbling from registry
    with pytest.raises(MissingDependencyError):
        adapter.get(UnregisteredProtocol)  # type: ignore[arg-type]

    # Calling before registry initialization → NotInitializedError
    uninitialized_registry = TypedServiceRegistry()
    bridge = CompatibilityBridge(uninitialized_registry)
    bridge._string_to_type_map = {  # type: ignore[attr-defined]
        "slack_config": (SlackConfigProtocol, None)
    }
    uninitialized_adapter = TypedDIContainerAdapter(uninitialized_registry, bridge)
    with pytest.raises(NotInitializedError):
        uninitialized_adapter.get(SlackConfigProtocol)

    # Invalid parameter types to get() → TypeError (production bug prevention)
    with pytest.raises(TypeError, match=r"get\(\) expects Type\[T\], got str"):
        adapter.get("slack_config")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_production_bug_prevention() -> None:
    """Directly validate the production bug pattern raises a clear TypeError."""
    adapter, _ = await build_adapter_with_mapping()
    with pytest.raises(
        TypeError, match=r"Expected Type\[T\], got str|expects Type\[T\], got str"
    ):
        adapter.get("slack_config")  # type: ignore[arg-type]


# --- End-to-End Resolution via get_unified_container --- #
@pytest.mark.asyncio
async def test_typed_di_enabled_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """KETCHUP_USE_TYPED_DI=true path returns adapter; both resolution paths work."""
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "true")

    # Prepare typed instances and inject into integration layer globals
    registry = TypedServiceRegistry()
    registry.register(SlackConfigProtocol, lambda r: SlackConfigImpl(), dependencies=[])
    await registry.initialize_all()
    registry.freeze_after_init()

    bridge = CompatibilityBridge(registry)
    bridge._string_to_type_map = {  # type: ignore[attr-defined]
        "slack_config": (SlackConfigProtocol, None)
    }

    # Inject globals so get_unified_container reuses them
    import importlib

    integ = importlib.import_module("packages.core.typed_di_integration")

    integ._typed_registry = registry  # type: ignore[attr-defined]
    integ._compatibility_bridge = bridge  # type: ignore[attr-defined]
    integ._legacy_container = None  # type: ignore[attr-defined]

    container = await integ.get_unified_container()
    assert isinstance(container, TypedDIContainerAdapter)

    # Both paths resolve
    assert container.get_by_name("slack_config").some_method() == "ok"
    assert container.get(SlackConfigProtocol).some_method() == "ok"

    await integ.cleanup_unified_container()


@pytest.mark.asyncio
async def test_legacy_di_enabled_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """KETCHUP_USE_TYPED_DI=false path returns a DIContainer (legacy)."""
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "false")

    # Provide a lightweight legacy container to avoid heavy initialization
    class DummyLegacyContainer:
        """Lightweight legacy-like container stub with get_by_name support."""

        def __init__(self) -> None:
            self._deps = {"slack_config": SlackConfigImpl()}

        async def initialize(self) -> None:  # pragma: no cover - not used
            pass

        async def cleanup(self) -> None:  # pragma: no cover - not used
            pass

        def get_by_name(self, name: str):
            return self._deps.get(name)

    async def stub_get_container():
        return DummyLegacyContainer()

    # Preload stub module into sys.modules to bypass heavy imports
    import importlib
    import types

    async def stub_cleanup_container():
        return None

    legacy_mod = types.SimpleNamespace(
        get_container=stub_get_container, cleanup_container=stub_cleanup_container
    )
    monkeypatch.setitem(
        __import__("sys").modules, "packages.core.di_container", legacy_mod
    )
    integ = importlib.import_module("packages.core.typed_di_integration")

    container = await integ.get_unified_container()
    assert not isinstance(container, TypedDIContainerAdapter)

    assert container.get_by_name("slack_config").some_method() == "ok"


# --- Feature Flag Transition & Rollback --- #
@pytest.mark.asyncio
async def test_flag_switching_functional_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Switching flags maintains functional parity between legacy and typed paths."""
    # Legacy mode
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "false")

    class DummyLegacyContainer:
        def __init__(self) -> None:
            self._deps = {"slack_config": SlackConfigImpl()}

        def get_by_name(self, name: str):
            return self._deps.get(name)

    async def stub_get_container():
        return DummyLegacyContainer()

    # Preload stubbed legacy module before import
    import importlib
    import types

    async def stub_cleanup_container():
        return None

    legacy_mod = types.SimpleNamespace(
        get_container=stub_get_container, cleanup_container=stub_cleanup_container
    )
    monkeypatch.setitem(
        __import__("sys").modules, "packages.core.di_container", legacy_mod
    )
    integ = importlib.import_module("packages.core.typed_di_integration")

    legacy_container = await integ.get_unified_container()
    legacy_result = legacy_container.get_by_name("slack_config")

    # Reset and switch to typed mode
    await integ.cleanup_unified_container()
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "true")

    registry = TypedServiceRegistry()
    registry.register(SlackConfigProtocol, lambda r: SlackConfigImpl(), dependencies=[])
    await registry.initialize_all()
    registry.freeze_after_init()

    bridge = CompatibilityBridge(registry)
    bridge._string_to_type_map = {  # type: ignore[attr-defined]
        "slack_config": (SlackConfigProtocol, None)
    }

    import importlib

    integ = importlib.import_module("packages.core.typed_di_integration")

    integ._typed_registry = registry  # type: ignore[attr-defined]
    integ._compatibility_bridge = bridge  # type: ignore[attr-defined]
    integ._legacy_container = None  # type: ignore[attr-defined]

    typed_container = await integ.get_unified_container()
    typed_result = typed_container.get_by_name("slack_config")

    # Functional parity (not identity)
    assert type(legacy_result) is type(typed_result)


@pytest.mark.asyncio
async def test_rollback_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    """Typed mode → cleanup → legacy mode (rollback) returns legacy container."""
    # Start in typed mode
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "true")

    registry = TypedServiceRegistry()
    registry.register(SlackConfigProtocol, lambda r: SlackConfigImpl(), dependencies=[])
    await registry.initialize_all()
    registry.freeze_after_init()

    bridge = CompatibilityBridge(registry)
    bridge._string_to_type_map = {  # type: ignore[attr-defined]
        "slack_config": (SlackConfigProtocol, None)
    }

    import importlib

    integ = importlib.import_module("packages.core.typed_di_integration")

    integ._typed_registry = registry  # type: ignore[attr-defined]
    integ._compatibility_bridge = bridge  # type: ignore[attr-defined]
    integ._legacy_container = None  # type: ignore[attr-defined]

    adapter = await integ.get_unified_container()
    assert isinstance(adapter, TypedDIContainerAdapter)

    # Cleanup and switch to legacy
    await integ.cleanup_unified_container()
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "false")

    class DummyLegacyContainer:
        def __init__(self) -> None:
            self._deps = {"slack_config": SlackConfigImpl()}

        def get_by_name(self, name: str):
            return self._deps.get(name)

    async def stub_get_container():
        return DummyLegacyContainer()

    import types

    legacy_mod = types.SimpleNamespace(get_container=stub_get_container)
    monkeypatch.setitem(
        __import__("sys").modules, "packages.core.di_container", legacy_mod
    )

    rollback_container = await integ.get_unified_container()
    assert not isinstance(rollback_container, TypedDIContainerAdapter)


@pytest.mark.asyncio
async def test_di_container_delegates_to_typed_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy di_container.get_container delegates to unified adapter when flag is true.

    Stubs out heavy client_factory imports so we can import di_container without extra deps.
    """
    monkeypatch.setenv("KETCHUP_USE_TYPED_DI", "true")

    # Note: All client factory modules have been deleted in Phase 2 Tier 4
    # di_container.py no longer imports any factories
    # This test verifies di_container.get_container() delegates to TypedDI adapter

    # Now import di_container and ensure it delegates to typed adapter
    import importlib

    di = importlib.import_module("packages.core.di_container")
    container = await di.get_container()
    assert isinstance(container, TypedDIContainerAdapter)
