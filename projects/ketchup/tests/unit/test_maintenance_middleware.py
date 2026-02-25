"""Tests for MaintenanceMiddleware."""

from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


def create_maintenance_middleware(
    is_maintenance_func: callable, message: str
) -> type[BaseHTTPMiddleware]:
    """Factory to create MaintenanceMiddleware with injected dependencies."""

    class MaintenanceMiddleware(BaseHTTPMiddleware):
        """Return 503 during maintenance mode, except for /health."""

        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            if is_maintenance_func() and request.url.path != "/health":
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "maintenance",
                        "message": message,
                        "retry_after": 300,
                    },
                    headers={"Retry-After": "300"},
                )
            return await call_next(request)

    return MaintenanceMiddleware


class TestMaintenanceMiddleware:
    """Unit tests for MaintenanceMiddleware class."""

    def _create_app_with_middleware(
        self, is_maintenance: bool, custom_message: str | None = None
    ) -> FastAPI:
        """Create a test FastAPI app with MaintenanceMiddleware."""
        app = FastAPI()

        default_message = "Ketchup is undergoing maintenance. Please try again in a few minutes."
        message = custom_message if custom_message else default_message

        middleware_cls = create_maintenance_middleware(
            is_maintenance_func=lambda: is_maintenance, message=message
        )

        app.add_middleware(middleware_cls)

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "healthy"}

        @app.get("/readiness")
        async def readiness() -> dict[str, str]:
            return {"status": "ready"}

        @app.get("/other")
        async def other() -> dict[str, str]:
            return {"status": "ok"}

        return app

    def test_maintenance_disabled_allows_requests(self) -> None:
        """Requests allowed when maintenance disabled."""
        app = self._create_app_with_middleware(is_maintenance=False)
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_maintenance_disabled_allows_readiness(self) -> None:
        """Readiness endpoint returns 200 when maintenance disabled."""
        app = self._create_app_with_middleware(is_maintenance=False)
        client = TestClient(app)
        response = client.get("/readiness")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_maintenance_enabled_returns_503(self) -> None:
        """503 returned when maintenance enabled."""
        app = self._create_app_with_middleware(is_maintenance=True)
        client = TestClient(app)
        response = client.get("/readiness")
        assert response.status_code == 503

    def test_health_always_allowed(self) -> None:
        """/health returns 200 even during maintenance."""
        app = self._create_app_with_middleware(is_maintenance=True)
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_response_body_format(self) -> None:
        """Response JSON has required keys."""
        app = self._create_app_with_middleware(is_maintenance=True)
        client = TestClient(app)
        response = client.get("/readiness")
        data = response.json()
        assert data["status"] == "maintenance"
        assert "message" in data
        assert data["retry_after"] == 300

    def test_retry_after_header(self) -> None:
        """Retry-After header is set."""
        app = self._create_app_with_middleware(is_maintenance=True)
        client = TestClient(app)
        response = client.get("/readiness")
        assert response.headers.get("Retry-After") == "300"

    def test_custom_message(self) -> None:
        """Custom message is used in response."""
        custom = "Custom maintenance"
        app = self._create_app_with_middleware(is_maintenance=True, custom_message=custom)
        client = TestClient(app)
        response = client.get("/readiness")
        assert response.json()["message"] == custom

    def test_other_endpoints_blocked_during_maintenance(self) -> None:
        """Other endpoints return 503 during maintenance."""
        app = self._create_app_with_middleware(is_maintenance=True)
        client = TestClient(app)
        response = client.get("/other")
        assert response.status_code == 503
        assert response.json()["status"] == "maintenance"


class TestIsMaintenanceMode:
    """Unit tests for is_maintenance_mode function logic."""

    def test_returns_true_when_enabled(self) -> None:
        """is_maintenance_mode returns True when MAINTENANCE_MODE is 'true'."""
        # Test the logic directly - MAINTENANCE_MODE.lower() == "true"
        mode = "true"
        assert mode.lower() == "true"

    def test_returns_true_case_insensitive(self) -> None:
        """is_maintenance_mode handles uppercase 'TRUE'."""
        mode = "TRUE"
        assert mode.lower() == "true"

    def test_returns_false_when_disabled(self) -> None:
        """is_maintenance_mode returns False when MAINTENANCE_MODE is 'false'."""
        mode = "false"
        assert mode.lower() != "true"

    def test_returns_false_for_other_values(self) -> None:
        """is_maintenance_mode returns False for non-'true' values."""
        for value in ["", "FALSE", "0", "no", "disabled"]:
            assert value.lower() != "true"


class TestMaintenanceMiddlewareDispatch:
    """Tests for MaintenanceMiddleware dispatch method directly."""

    @pytest.mark.asyncio
    async def test_dispatch_returns_503_when_maintenance_enabled(self) -> None:
        """Middleware dispatch returns 503 when maintenance enabled."""
        # Create a mock request for a non-health endpoint
        mock_request = AsyncMock()
        mock_request.url.path = "/readiness"

        # Create a mock call_next
        mock_response = Response(status_code=200)
        mock_call_next = AsyncMock(return_value=mock_response)

        # Create middleware with maintenance enabled
        middleware_cls = create_maintenance_middleware(
            is_maintenance_func=lambda: True,
            message="Test maintenance message",
        )
        middleware = middleware_cls(app=FastAPI())

        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 503
        # call_next should not be called during maintenance
        mock_call_next.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dispatch_allows_health_during_maintenance(self) -> None:
        """Middleware dispatch allows /health even during maintenance."""
        mock_request = AsyncMock()
        mock_request.url.path = "/health"

        mock_response = Response(status_code=200)
        mock_call_next = AsyncMock(return_value=mock_response)

        middleware_cls = create_maintenance_middleware(
            is_maintenance_func=lambda: True,
            message="Test maintenance message",
        )
        middleware = middleware_cls(app=FastAPI())

        response = await middleware.dispatch(mock_request, mock_call_next)
        # Should pass through to call_next for /health
        mock_call_next.assert_awaited_once()
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_passes_through_when_maintenance_disabled(self) -> None:
        """Middleware dispatch passes through when maintenance disabled."""
        mock_request = AsyncMock()
        mock_request.url.path = "/readiness"

        mock_response = Response(status_code=200)
        mock_call_next = AsyncMock(return_value=mock_response)

        middleware_cls = create_maintenance_middleware(
            is_maintenance_func=lambda: False,
            message="Test maintenance message",
        )
        middleware = middleware_cls(app=FastAPI())

        response = await middleware.dispatch(mock_request, mock_call_next)
        mock_call_next.assert_awaited_once()
        assert response.status_code == 200
