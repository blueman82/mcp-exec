"""Tests for the dependency injection framework."""

import pytest

from bravo.di import CircularDependencyError, DependencySpec, ServiceRegistry
from bravo.di.resolver import topological_sort

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_object(**_kwargs: object) -> object:
    """Simple async factory that returns a plain object."""
    return object()


class _Closeable:
    """Stub service with a close method for shutdown testing."""

    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# Resolver: topological_sort
# ---------------------------------------------------------------------------


def test_topological_sort_no_deps() -> None:
    specs = {
        "a": DependencySpec(name="a", factory=_make_object),
        "b": DependencySpec(name="b", factory=_make_object),
        "c": DependencySpec(name="c", factory=_make_object),
    }
    order = topological_sort(specs)
    assert set(order) == {"a", "b", "c"}
    assert len(order) == 3


def test_topological_sort_linear() -> None:
    specs = {
        "a": DependencySpec(name="a", factory=_make_object, depends_on=["b"]),
        "b": DependencySpec(name="b", factory=_make_object, depends_on=["c"]),
        "c": DependencySpec(name="c", factory=_make_object),
    }
    order = topological_sort(specs)
    assert order == ["c", "b", "a"]


def test_topological_sort_diamond() -> None:
    specs = {
        "a": DependencySpec(name="a", factory=_make_object),
        "b": DependencySpec(name="b", factory=_make_object, depends_on=["a"]),
        "c": DependencySpec(name="c", factory=_make_object, depends_on=["a"]),
        "d": DependencySpec(name="d", factory=_make_object, depends_on=["b", "c"]),
    }
    order = topological_sort(specs)
    assert order[0] == "a"
    assert order[-1] == "d"
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_circular_dependency_detected() -> None:
    specs = {
        "a": DependencySpec(name="a", factory=_make_object, depends_on=["b"]),
        "b": DependencySpec(name="b", factory=_make_object, depends_on=["a"]),
    }
    with pytest.raises(CircularDependencyError) as exc_info:
        topological_sort(specs)
    assert set(exc_info.value.remaining) == {"a", "b"}


def test_unknown_dependency_raises() -> None:
    specs = {
        "a": DependencySpec(name="a", factory=_make_object, depends_on=["missing"]),
    }
    with pytest.raises(ValueError, match="unknown service 'missing'"):
        topological_sort(specs)


# ---------------------------------------------------------------------------
# Registry: async lifecycle
# ---------------------------------------------------------------------------


async def test_registry_lifecycle() -> None:
    registry = ServiceRegistry()

    async def make_alpha() -> str:
        return "alpha_instance"

    async def make_beta() -> str:
        return "beta_instance"

    registry.register(DependencySpec(name="alpha", factory=make_alpha))
    registry.register(DependencySpec(name="beta", factory=make_beta))
    await registry.initialize_all()

    assert registry.get("alpha") == "alpha_instance"
    assert registry.get("beta") == "beta_instance"


async def test_registry_get_before_init() -> None:
    registry = ServiceRegistry()
    registry.register(DependencySpec(name="svc", factory=_make_object))
    with pytest.raises(RuntimeError, match="not been initialized"):
        registry.get("svc")


async def test_registry_double_register() -> None:
    registry = ServiceRegistry()
    spec = DependencySpec(name="dup", factory=_make_object)
    registry.register(spec)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)


async def test_registry_register_after_init() -> None:
    registry = ServiceRegistry()
    registry.register(DependencySpec(name="svc", factory=_make_object))
    await registry.initialize_all()
    with pytest.raises(RuntimeError, match="Cannot register"):
        registry.register(DependencySpec(name="late", factory=_make_object))


async def test_registry_shutdown_calls_close() -> None:
    closeables: list[_Closeable] = []

    async def make_closeable() -> _Closeable:
        svc = _Closeable()
        closeables.append(svc)
        return svc

    registry = ServiceRegistry()
    registry.register(DependencySpec(name="s1", factory=make_closeable))
    registry.register(DependencySpec(name="s2", factory=make_closeable))
    await registry.initialize_all()
    await registry.shutdown_all()

    assert len(closeables) == 2
    assert all(c.closed for c in closeables)


async def test_registry_initialization_order() -> None:
    init_order: list[str] = []

    async def make_db() -> str:
        init_order.append("db")
        return "db_instance"

    async def make_cache(db: str) -> str:
        init_order.append("cache")
        assert db == "db_instance"
        return "cache_instance"

    async def make_api(db: str, cache: str) -> str:
        init_order.append("api")
        assert db == "db_instance"
        assert cache == "cache_instance"
        return "api_instance"

    registry = ServiceRegistry()
    registry.register(
        DependencySpec(name="api", factory=make_api, depends_on=["db", "cache"])
    )
    registry.register(
        DependencySpec(name="cache", factory=make_cache, depends_on=["db"])
    )
    registry.register(DependencySpec(name="db", factory=make_db))
    await registry.initialize_all()

    assert init_order == ["db", "cache", "api"]
    assert registry.get("api") == "api_instance"


# ---------------------------------------------------------------------------
# Integration: container
# ---------------------------------------------------------------------------


async def test_container_creates_all_services() -> None:
    """Verify create_container registers and initializes all 6 services."""
    from bravo.config import Settings
    from bravo.container import create_container

    settings = Settings()
    container = create_container(settings)
    await container.initialize_all()

    expected = [
        "gate_service",
        "jira_client",
        "slack_service",
        "llm_service",
        "poller_service",
        "nudge_service",
    ]
    for name in expected:
        assert container.get(name) is not None

    await container.shutdown_all()
