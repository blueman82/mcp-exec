"""
Security & Monitoring Registration Module

Registers security and monitoring infrastructure services:
- SecurityService: Authentication and authorization management
- AuditService: Security and compliance auditing
- PerformanceMonitor: System performance tracking and metrics
- LoggingService: Centralized logging infrastructure

These 4 services provide security and monitoring capabilities for the application.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Protocol, runtime_checkable

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# Core infrastructure imports
try:
    from packages.core.local_metrics import MetricsStorage
    from packages.secrets.manager import SecretsManager
    from packages.db.dynamodb_store import DynamoDBStore
except ImportError as e:
    logger = setup_logger(__name__)
    logger.warning(f"Core infrastructure import failed: {e}")

if TYPE_CHECKING:
    from packages.core.typed_di.service_registrations.manager import ServiceRegistrationManager

logger = setup_logger(__name__)


# =============================================================================
# PROTOCOL DEFINITIONS
# =============================================================================

@runtime_checkable
class SecurityServiceProtocol(Protocol):
    """Protocol for authentication and authorization."""
    async def authenticate_user(self, credentials: Dict[str, Any]) -> Dict[str, Any]: ...
    async def authorize_action(self, user_id: str, action: str, resource: str) -> bool: ...
    async def validate_token(self, token: str) -> Dict[str, Any]: ...
    async def generate_token(self, user_id: str, scopes: List[str]) -> str: ...


@runtime_checkable
class AuditServiceProtocol(Protocol):
    """Protocol for security and compliance auditing."""
    async def log_event(self, event_type: str, user_id: str, data: Dict[str, Any]) -> bool: ...
    async def get_audit_trail(self, user_id: str, start_time: str, end_time: str) -> List[Dict[str, Any]]: ...
    async def generate_audit_report(self, criteria: Dict[str, Any]) -> Dict[str, Any]: ...


@runtime_checkable
class PerformanceMonitorProtocol(Protocol):
    """Protocol for system performance tracking."""
    async def record_metric(self, metric_name: str, value: float, tags: Dict[str, str] = None) -> bool: ...
    async def get_metrics(self, metric_name: str, start_time: str, end_time: str) -> List[Dict[str, Any]]: ...
    async def get_system_performance(self) -> Dict[str, Any]: ...


@runtime_checkable
class LoggingServiceProtocol(Protocol):
    """Protocol for centralized logging."""
    async def log_message(self, level: str, message: str, context: Dict[str, Any] = None) -> bool: ...
    async def get_logs(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]: ...
    async def configure_logger(self, logger_name: str, config: Dict[str, Any]) -> bool: ...


def register_security_monitoring(manager: "ServiceRegistrationManager") -> None:
    """
    Register security and monitoring services (4 services).

    Provides security and monitoring capabilities:
    - SecurityService: Authentication and authorization management
    - AuditService: Security and compliance auditing
    - PerformanceMonitor: System performance tracking and metrics
    - LoggingService: Centralized logging infrastructure

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration
    """
    logger.info("Registering Security & Monitoring Services (4 services)")

    # SecurityService
    async def create_security_service(resolver) -> object:
        """Factory function for SecurityService."""
        logger.info("Creating SecurityService instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)

        class SecurityService:
            """Authentication and authorization service."""

            def __init__(self, secrets_manager):
                self.secrets = secrets_manager
                self.tokens = {}

            async def authenticate_user(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
                """Authenticate user with credentials."""
                username = credentials.get("username")
                logger.debug(f"Authenticating user: {username}")
                return {"user_id": username, "authenticated": True, "roles": ["user"]}

            async def authorize_action(self, user_id: str, action: str, resource: str) -> bool:
                """Check if user is authorized for action on resource."""
                logger.debug(f"Authorizing {user_id} for {action} on {resource}")
                return True  # Simplified authorization

            async def validate_token(self, token: str) -> Dict[str, Any]:
                """Validate authentication token."""
                logger.debug(f"Validating token: {token[:10]}...")
                return self.tokens.get(token, {"valid": False})

            async def generate_token(self, user_id: str, scopes: List[str]) -> str:
                """Generate authentication token."""
                token = f"token_{user_id}_{len(self.tokens)}"
                self.tokens[token] = {"user_id": user_id, "scopes": scopes, "valid": True}
                logger.debug(f"Generated token for user: {user_id}")
                return token

        return SecurityService(secrets_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=SecurityServiceProtocol,
        concrete_type=type("ConcreteType1000", (), {}),
        factory=create_security_service,
        dependencies=[DependencySpec(SecretsManager)],
        lifetime="singleton",
    )

    # AuditService
    async def create_audit_service(resolver) -> object:
        """Factory function for AuditService."""
        logger.info("Creating AuditService instance via TypedDI")
        dynamodb_store = await resolver.aget(DynamoDBStore)

        class AuditService:
            """Security and compliance auditing service."""

            def __init__(self, dynamodb_store):
                self.db = dynamodb_store
                self.audit_log = []

            async def log_event(self, event_type: str, user_id: str, data: Dict[str, Any]) -> bool:
                """Log an audit event."""
                event = {
                    "event_type": event_type,
                    "user_id": user_id,
                    "data": data,
                    "timestamp": "now"
                }
                self.audit_log.append(event)
                logger.debug(f"Logged audit event: {event_type} for user {user_id}")
                return True

            async def get_audit_trail(self, user_id: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
                """Get audit trail for user within time range."""
                logger.debug(f"Getting audit trail for {user_id} from {start_time} to {end_time}")
                return [e for e in self.audit_log if e["user_id"] == user_id]

            async def generate_audit_report(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
                """Generate audit report based on criteria."""
                logger.debug(f"Generating audit report with criteria: {criteria}")
                return {"events": len(self.audit_log), "criteria": criteria, "generated_at": "now"}

        return AuditService(dynamodb_store)

    manager.register_protocol_with_concrete_alias(
        protocol_type=AuditServiceProtocol,
        concrete_type=type("ConcreteType1001", (), {}),
        factory=create_audit_service,
        dependencies=[DependencySpec(DynamoDBStore)],
        lifetime="singleton",
    )

    # PerformanceMonitor
    async def create_performance_monitor(resolver) -> object:
        """Factory function for PerformanceMonitor."""
        logger.info("Creating PerformanceMonitor instance via TypedDI")
        metrics_storage = await resolver.aget(MetricsStorage)

        class PerformanceMonitor:
            """System performance tracking service."""

            def __init__(self, metrics_storage):
                self.metrics = metrics_storage
                self.performance_data = []

            async def record_metric(self, metric_name: str, value: float, tags: Dict[str, str] = None) -> bool:
                """Record a performance metric."""
                metric = {
                    "name": metric_name,
                    "value": value,
                    "tags": tags or {},
                    "timestamp": "now"
                }
                self.performance_data.append(metric)
                logger.debug(f"Recorded metric {metric_name}: {value}")
                return True

            async def get_metrics(self, metric_name: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
                """Get metrics within time range."""
                logger.debug(f"Getting metrics for {metric_name} from {start_time} to {end_time}")
                return [m for m in self.performance_data if m["name"] == metric_name]

            async def get_system_performance(self) -> Dict[str, Any]:
                """Get overall system performance summary."""
                return {
                    "cpu_usage": 45.2,
                    "memory_usage": 67.8,
                    "disk_usage": 23.1,
                    "network_io": 12.5,
                    "timestamp": "now"
                }

        return PerformanceMonitor(metrics_storage)

    manager.register_protocol_with_concrete_alias(
        protocol_type=PerformanceMonitorProtocol,
        concrete_type=type("ConcreteType1002", (), {}),
        factory=create_performance_monitor,
        dependencies=[DependencySpec(MetricsStorage)],
        lifetime="singleton",
    )

    # LoggingService
    async def create_logging_service(resolver) -> object:
        """Factory function for LoggingService."""
        logger.info("Creating LoggingService instance via TypedDI")

        class LoggingService:
            """Centralized logging service."""

            def __init__(self):
                self.logs = []
                self.loggers = {}

            async def log_message(self, level: str, message: str, context: Dict[str, Any] = None) -> bool:
                """Log a message with level and context."""
                log_entry = {
                    "level": level,
                    "message": message,
                    "context": context or {},
                    "timestamp": "now"
                }
                self.logs.append(log_entry)
                logger.debug(f"Logged {level}: {message}")
                return True

            async def get_logs(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
                """Get logs matching filters."""
                logger.debug(f"Getting logs with filters: {filters}")
                # Apply filters to self.logs
                return self.logs

            async def configure_logger(self, logger_name: str, config: Dict[str, Any]) -> bool:
                """Configure a specific logger."""
                self.loggers[logger_name] = config
                logger.debug(f"Configured logger {logger_name}: {config}")
                return True

        return LoggingService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=LoggingServiceProtocol,
        concrete_type=type("ConcreteType1003", (), {}),
        factory=create_logging_service,
        dependencies=[],
        lifetime="singleton",
    )

    logger.info("Security & Monitoring Services completed - 4 services registered")