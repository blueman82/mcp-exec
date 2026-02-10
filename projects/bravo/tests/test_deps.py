"""Tests for FastAPI Depends() helpers and wired routes."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bravo.api import admin
from bravo.api.deps import get_nudge_service, get_poller_service
from bravo.di.registry import ServiceRegistry
from bravo.protocols import NudgeServiceProto, PollerServiceProto
from bravo.services.gates import GateEvaluation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeNudgeService:
    """Stub implementing NudgeServiceProto."""

    async def evaluate_ticket(self, ticket_key: str) -> dict[str, Any]:
        return {
            "ticket_key": ticket_key,
            "gate_result": GateEvaluation(
                g1_passed=True, g2_passed=False, g3_passed=True, g4_passed=True
            ),
            "should_nudge": True,
            "nudge_reason": "Failed gates: G2 (stale)",
        }


class _FakePollerService:
    """Stub implementing PollerServiceProto."""

    async def run_poll(self) -> dict[str, Any]:
        return {"poll_id": "fake-id", "tickets_fetched": 0}


def _build_registry() -> ServiceRegistry:
    """Build a registry with fake services pre-loaded."""
    registry = ServiceRegistry()
    # Bypass normal init — directly inject instances
    registry._initialized = True
    registry._services["nudge_service"] = SimpleNamespace(
        instance=_FakeNudgeService()
    )
    registry._services["poller_service"] = SimpleNamespace(
        instance=_FakePollerService()
    )
    return registry


@pytest.fixture()
def registry() -> ServiceRegistry:
    return _build_registry()


@pytest.fixture()
def mock_request(registry: ServiceRegistry) -> SimpleNamespace:
    """Fake FastAPI Request with app.state.container."""
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=registry)))


# ---------------------------------------------------------------------------
# deps.py helper tests
# ---------------------------------------------------------------------------


def test_get_nudge_service_returns_protocol(mock_request: SimpleNamespace) -> None:
    svc = get_nudge_service(mock_request)  # type: ignore[arg-type]
    assert isinstance(svc, NudgeServiceProto)


def test_get_poller_service_returns_protocol(mock_request: SimpleNamespace) -> None:
    svc = get_poller_service(mock_request)  # type: ignore[arg-type]
    assert isinstance(svc, PollerServiceProto)


def test_get_nudge_service_unknown_key_raises() -> None:
    empty_registry = ServiceRegistry()
    empty_registry._initialized = True
    empty_registry._services = {}
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(container=empty_registry))
    )
    with pytest.raises(KeyError, match="nudge_service"):
        get_nudge_service(request)  # type: ignore[arg-type]


def test_get_nudge_service_assertion_error_on_wrong_type() -> None:
    registry = ServiceRegistry()
    registry._initialized = True
    registry._services["nudge_service"] = SimpleNamespace(instance="not_a_service")
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(container=registry))
    )
    with pytest.raises(AssertionError):
        get_nudge_service(request)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Admin route tests (update_config, trigger_poll, get_logs)
# ---------------------------------------------------------------------------


def _make_app(registry: ServiceRegistry) -> FastAPI:
    """Create a minimal FastAPI app with the admin router and test container."""
    app = FastAPI()
    app.state.container = registry
    app.include_router(admin.router, prefix="/admin")
    return app


def test_update_config_applies_poll_interval() -> None:
    """PATCH /admin/config updates runtime settings."""
    from bravo.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    original = settings.poll_interval_minutes

    app = _make_app(_build_registry())
    client = TestClient(app)

    resp = client.patch(
        "/admin/config",
        json={"poll_interval_minutes": 30},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["poll_interval_minutes"] == 30

    # Restore
    settings.poll_interval_minutes = original
    get_settings.cache_clear()


def test_update_config_applies_gate_settings() -> None:
    """PATCH /admin/config updates gate thresholds."""
    from bravo.config import get_settings

    get_settings.cache_clear()

    app = _make_app(_build_registry())
    client = TestClient(app)

    resp = client.patch(
        "/admin/config",
        json={"gates": {"g2_stale_hours": 8}},
    )
    assert resp.status_code == 200
    assert resp.json()["gates"]["g2_stale_hours"] == 8

    get_settings.cache_clear()


def test_trigger_poll_returns_202() -> None:
    """POST /admin/poll/trigger returns 202 with queued status."""
    app = _make_app(_build_registry())
    client = TestClient(app)

    resp = client.post("/admin/poll/trigger")
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "queued"
    assert data["poll_id"] is not None


def test_get_logs_empty_when_no_file() -> None:
    """GET /admin/logs returns empty when log file doesn't exist."""
    app = _make_app(_build_registry())
    client = TestClient(app)

    resp = client.get("/admin/logs")
    assert resp.status_code == 200
    assert resp.json()["logs"] == []


def test_get_logs_reads_json_lines(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    """GET /admin/logs reads and parses JSON log lines."""
    log_file = tmp_path / "bravo.log"
    lines = [
        json.dumps({"timestamp": "2026-02-10T12:00:00", "level": "info", "event": "started"}),
        json.dumps({"timestamp": "2026-02-10T12:01:00", "level": "error", "event": "failed", "detail": "oops"}),
    ]
    log_file.write_text("\n".join(lines))
    monkeypatch.setattr(admin, "LOG_FILE", log_file)

    app = _make_app(_build_registry())
    client = TestClient(app)

    resp = client.get("/admin/logs")
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    assert len(logs) == 2
    # Most recent first (reversed)
    assert logs[0]["level"] == "ERROR"
    assert logs[0]["message"] == "failed"
    assert logs[0]["context"]["detail"] == "oops"
    assert logs[1]["level"] == "INFO"


def test_get_logs_filters_by_level(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    """GET /admin/logs?level=ERROR filters entries."""
    log_file = tmp_path / "bravo.log"
    lines = [
        json.dumps({"timestamp": "2026-02-10T12:00:00", "level": "info", "event": "ok"}),
        json.dumps({"timestamp": "2026-02-10T12:01:00", "level": "error", "event": "bad"}),
    ]
    log_file.write_text("\n".join(lines))
    monkeypatch.setattr(admin, "LOG_FILE", log_file)

    app = _make_app(_build_registry())
    client = TestClient(app)

    resp = client.get("/admin/logs?level=ERROR")
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["message"] == "bad"
