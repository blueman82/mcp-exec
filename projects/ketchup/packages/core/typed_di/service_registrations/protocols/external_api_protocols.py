"""
External API Integration Protocol Definitions.

This module contains protocol definitions for external API integration services
in the TypedDI service registration system.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class APIGatewayServiceProtocol(Protocol):
    """Protocol for API gateway operations."""

    async def route_request(
        self, endpoint: str, method: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Route request through API gateway."""
        ...

    async def validate_api_key(self, api_key: str) -> bool:
        """Validate API key for authentication."""
        ...

    async def get_rate_limit_status(self, client_id: str) -> Dict[str, Any]:
        """Get rate limit status for client."""
        ...

    async def register_endpoint(self, endpoint: str, config: Dict[str, Any]) -> bool:
        """Register new endpoint with gateway."""
        ...


@runtime_checkable
class ExternalServiceClientProtocol(Protocol):
    """Protocol for external service client operations."""

    async def make_request(
        self,
        url: str,
        method: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to external service."""
        ...

    async def configure_authentication(
        self, service_name: str, auth_config: Dict[str, Any]
    ) -> bool:
        """Configure authentication for external service."""
        ...

    async def get_service_health(self, service_name: str) -> Dict[str, Any]:
        """Get health status of external service."""
        ...

    async def retry_failed_request(self, request_id: str) -> Dict[str, Any]:
        """Retry a failed external service request."""
        ...


@runtime_checkable
class WebhookServiceProtocol(Protocol):
    """Protocol for webhook operations."""

    async def register_webhook(
        self, url: str, events: List[str], secret: Optional[str] = None
    ) -> str:
        """Register webhook and return webhook ID."""
        ...

    async def deliver_webhook(
        self, webhook_id: str, event_type: str, payload: Dict[str, Any]
    ) -> bool:
        """Deliver webhook payload to registered endpoint."""
        ...

    async def verify_webhook_signature(self, webhook_id: str, payload: str, signature: str) -> bool:
        """Verify webhook signature for security."""
        ...

    async def get_webhook_delivery_status(
        self, webhook_id: str, delivery_id: str
    ) -> Dict[str, Any]:
        """Get delivery status of specific webhook."""
        ...


@runtime_checkable
class CallbackServiceProtocol(Protocol):
    """Protocol for callback operations."""

    async def register_callback(
        self, callback_url: str, callback_type: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Register callback and return callback ID."""
        ...

    async def execute_callback(self, callback_id: str, data: Dict[str, Any]) -> bool:
        """Execute registered callback with data."""
        ...

    async def cancel_callback(self, callback_id: str) -> bool:
        """Cancel registered callback."""
        ...

    async def get_callback_status(self, callback_id: str) -> Dict[str, Any]:
        """Get status of registered callback."""
        ...


@runtime_checkable
class IntegrationMonitoringServiceProtocol(Protocol):
    """Protocol for integration monitoring operations."""

    async def record_integration_event(
        self, service_name: str, event_type: str, metadata: Dict[str, Any]
    ) -> str:
        """Record integration event and return event ID."""
        ...

    async def get_integration_metrics(self, service_name: str, time_range: str) -> Dict[str, Any]:
        """Get integration metrics for specified time range."""
        ...

    async def check_integration_health(self, service_name: str) -> Dict[str, Any]:
        """Check health status of integration."""
        ...

    async def get_error_analytics(
        self, service_name: str, error_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get error analytics for integration service."""
        ...
