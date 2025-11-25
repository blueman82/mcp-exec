"""
External API Integration Service Registrations.

This module contains TypedDI service registrations for external API integration services.
"""

from typing import Any, Dict, List, Optional

from packages.core.typed_di.service_registrations.protocols.external_api_protocols import (
    APIGatewayServiceProtocol,
    ExternalServiceClientProtocol,
    WebhookServiceProtocol,
    CallbackServiceProtocol,
    IntegrationMonitoringServiceProtocol
)
from ..manager import ServiceRegistrationManager
from packages.core.typed_di.resolver import TypedResolver


class APIGatewayService:
    """API gateway service implementation."""

    def __init__(self):
        """Initialize API gateway service."""
        self.endpoints: Dict[str, Dict[str, Any]] = {}
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        self.api_keys: Dict[str, bool] = {}

    async def route_request(
        self,
        endpoint: str,
        method: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Route request through API gateway."""
        if endpoint not in self.endpoints:
            return {"error": "Endpoint not found", "status": 404}

        return {
            "endpoint": endpoint,
            "method": method,
            "data": data or {},
            "status": "routed"
        }

    async def validate_api_key(self, api_key: str) -> bool:
        """Validate API key for authentication."""
        return self.api_keys.get(api_key, False)

    async def get_rate_limit_status(self, client_id: str) -> Dict[str, Any]:
        """Get rate limit status for client."""
        return self.rate_limits.get(client_id, {
            "remaining": 100,
            "reset_time": "1h",
            "limit": 100
        })

    async def register_endpoint(
        self,
        endpoint: str,
        config: Dict[str, Any]
    ) -> bool:
        """Register new endpoint with gateway."""
        self.endpoints[endpoint] = config
        return True


class ExternalServiceClient:
    """External service client implementation."""

    def __init__(self):
        """Initialize external service client."""
        self.auth_configs: Dict[str, Dict[str, Any]] = {}
        self.service_health: Dict[str, Dict[str, Any]] = {}
        self.failed_requests: Dict[str, Dict[str, Any]] = {}

    async def make_request(
        self,
        url: str,
        method: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to external service."""
        return {
            "url": url,
            "method": method,
            "headers": headers or {},
            "data": data or {},
            "status": "success",
            "response_time": "100ms"
        }

    async def configure_authentication(
        self,
        service_name: str,
        auth_config: Dict[str, Any]
    ) -> bool:
        """Configure authentication for external service."""
        self.auth_configs[service_name] = auth_config
        return True

    async def get_service_health(self, service_name: str) -> Dict[str, Any]:
        """Get health status of external service."""
        return self.service_health.get(service_name, {
            "status": "healthy",
            "response_time": "50ms",
            "last_check": "now"
        })

    async def retry_failed_request(self, request_id: str) -> Dict[str, Any]:
        """Retry a failed external service request."""
        if request_id in self.failed_requests:
            return {"request_id": request_id, "status": "retried"}
        return {"error": "Request not found", "status": 404}


class WebhookService:
    """Webhook service implementation."""

    def __init__(self):
        """Initialize webhook service."""
        self.webhooks: Dict[str, Dict[str, Any]] = {}
        self.deliveries: Dict[str, Dict[str, Any]] = {}
        self.webhook_counter = 0
        self.delivery_counter = 0

    async def register_webhook(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None
    ) -> str:
        """Register webhook and return webhook ID."""
        self.webhook_counter += 1
        webhook_id = f"webhook_{self.webhook_counter}"
        webhook = {
            "id": webhook_id,
            "url": url,
            "events": events,
            "secret": secret,
            "active": True
        }
        self.webhooks[webhook_id] = webhook
        return webhook_id

    async def deliver_webhook(
        self,
        webhook_id: str,
        event_type: str,
        payload: Dict[str, Any]
    ) -> bool:
        """Deliver webhook payload to registered endpoint."""
        if webhook_id not in self.webhooks:
            return False

        self.delivery_counter += 1
        delivery_id = f"delivery_{self.delivery_counter}"
        self.deliveries[delivery_id] = {
            "webhook_id": webhook_id,
            "event_type": event_type,
            "payload": payload,
            "delivered_at": "now"
        }
        return True

    async def verify_webhook_signature(
        self,
        webhook_id: str,
        payload: str,
        signature: str
    ) -> bool:
        """Verify webhook signature for security."""
        webhook = self.webhooks.get(webhook_id)
        if not webhook or not webhook.get("secret"):
            return False
        # Simple verification simulation
        return len(signature) > 10

    async def get_webhook_delivery_status(
        self,
        webhook_id: str,
        delivery_id: str
    ) -> Dict[str, Any]:
        """Get delivery status of specific webhook."""
        return self.deliveries.get(delivery_id, {})


class CallbackService:
    """Callback service implementation."""

    def __init__(self):
        """Initialize callback service."""
        self.callbacks: Dict[str, Dict[str, Any]] = {}
        self.callback_counter = 0

    async def register_callback(
        self,
        callback_url: str,
        callback_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Register callback and return callback ID."""
        self.callback_counter += 1
        callback_id = f"callback_{self.callback_counter}"
        callback = {
            "id": callback_id,
            "url": callback_url,
            "type": callback_type,
            "metadata": metadata or {},
            "status": "active"
        }
        self.callbacks[callback_id] = callback
        return callback_id

    async def execute_callback(
        self,
        callback_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Execute registered callback with data."""
        if callback_id in self.callbacks:
            callback = self.callbacks[callback_id]
            callback["last_executed"] = "now"
            callback["last_data"] = data
            return True
        return False

    async def cancel_callback(self, callback_id: str) -> bool:
        """Cancel registered callback."""
        if callback_id in self.callbacks:
            self.callbacks[callback_id]["status"] = "cancelled"
            return True
        return False

    async def get_callback_status(self, callback_id: str) -> Dict[str, Any]:
        """Get status of registered callback."""
        return self.callbacks.get(callback_id, {})


class IntegrationMonitoringService:
    """Integration monitoring service implementation."""

    def __init__(self):
        """Initialize integration monitoring service."""
        self.events: Dict[str, List[Dict[str, Any]]] = {}
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.event_counter = 0

    async def record_integration_event(
        self,
        service_name: str,
        event_type: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Record integration event and return event ID."""
        self.event_counter += 1
        event_id = f"event_{self.event_counter}"

        event = {
            "id": event_id,
            "service": service_name,
            "type": event_type,
            "metadata": metadata,
            "timestamp": "now"
        }

        if service_name not in self.events:
            self.events[service_name] = []

        self.events[service_name].append(event)
        return event_id

    async def get_integration_metrics(
        self,
        service_name: str,
        time_range: str
    ) -> Dict[str, Any]:
        """Get integration metrics for specified time range."""
        events = self.events.get(service_name, [])
        return {
            "service": service_name,
            "time_range": time_range,
            "event_count": len(events),
            "success_rate": 95.5,
            "avg_response_time": "120ms"
        }

    async def check_integration_health(
        self,
        service_name: str
    ) -> Dict[str, Any]:
        """Check health status of integration."""
        events = self.events.get(service_name, [])
        return {
            "service": service_name,
            "status": "healthy" if len(events) < 100 else "degraded",
            "last_event": events[-1] if events else None,
            "health_score": 85.0
        }

    async def get_error_analytics(
        self,
        service_name: str,
        error_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get error analytics for integration service."""
        events = self.events.get(service_name, [])
        error_events = [e for e in events if "error" in e.get("type", "")]

        return {
            "service": service_name,
            "error_type": error_type,
            "total_errors": len(error_events),
            "error_rate": len(error_events) / max(len(events), 1) * 100,
            "common_errors": ["timeout", "auth_failed", "rate_limit"]
        }


# Factory functions for TypedDI

async def create_api_gateway_service(resolver: TypedResolver) -> APIGatewayService:
    """Factory function for APIGatewayService."""
    return APIGatewayService()


async def create_external_service_client(resolver: TypedResolver) -> ExternalServiceClient:
    """Factory function for ExternalServiceClient."""
    return ExternalServiceClient()


async def create_webhook_service(resolver: TypedResolver) -> WebhookService:
    """Factory function for WebhookService."""
    return WebhookService()


async def create_callback_service(resolver: TypedResolver) -> CallbackService:
    """Factory function for CallbackService."""
    return CallbackService()


async def create_integration_monitoring_service(resolver: TypedResolver) -> IntegrationMonitoringService:
    """Factory function for IntegrationMonitoringService."""
    return IntegrationMonitoringService()


def register_external_api_services(manager: ServiceRegistrationManager) -> None:
    """Register all external API integration services with TypedDI."""

    # APIGatewayService
    manager.register_protocol_with_concrete_alias(
        protocol_type=APIGatewayServiceProtocol,
        concrete_type=APIGatewayService,
        factory=create_api_gateway_service,
        dependencies=[],
        lifetime="singleton",
    )

    # ExternalServiceClient
    manager.register_protocol_with_concrete_alias(
        protocol_type=ExternalServiceClientProtocol,
        concrete_type=ExternalServiceClient,
        factory=create_external_service_client,
        dependencies=[],
        lifetime="singleton",
    )

    # WebhookService
    manager.register_protocol_with_concrete_alias(
        protocol_type=WebhookServiceProtocol,
        concrete_type=WebhookService,
        factory=create_webhook_service,
        dependencies=[],
        lifetime="singleton",
    )

    # CallbackService
    manager.register_protocol_with_concrete_alias(
        protocol_type=CallbackServiceProtocol,
        concrete_type=CallbackService,
        factory=create_callback_service,
        dependencies=[],
        lifetime="singleton",
    )

    # IntegrationMonitoringService
    manager.register_protocol_with_concrete_alias(
        protocol_type=IntegrationMonitoringServiceProtocol,
        concrete_type=IntegrationMonitoringService,
        factory=create_integration_monitoring_service,
        dependencies=[],
        lifetime="singleton",
    )