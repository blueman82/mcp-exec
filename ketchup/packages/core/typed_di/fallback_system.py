"""
TypedDI Graceful Fallback System

Phase 2: Graceful Fallback System with Dedicated Gating
- Gate fallback with dedicated flag separate from main TypedDI flag
- Log and metric every fallback (type, qualifier, derived key)
- Start with whitelist of critical services
- Maintain tested Type↔string mapping shared with the bridge
- Full observability for fallback events and system health
"""

import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, Union

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class FallbackReason(Enum):
    """Enumeration of possible fallback reasons."""

    SERVICE_NOT_FOUND = "service_not_found"
    INITIALIZATION_FAILED = "initialization_failed"
    RESOLUTION_ERROR = "resolution_error"
    REGISTRY_UNAVAILABLE = "registry_unavailable"
    TIMEOUT = "timeout"
    CRITICAL_SERVICE_MISSING = "critical_service_missing"


@dataclass
class FallbackEvent:
    """Detailed fallback event for logging and metrics."""

    timestamp: float
    service_type: str
    qualifier: Optional[str]
    derived_key: str
    reason: FallbackReason
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None


class FallbackMetrics:
    """Metrics collector for fallback events."""

    def __init__(self):
        self.events: List[FallbackEvent] = []
        self.counts_by_reason: Dict[FallbackReason, int] = defaultdict(int)
        self.counts_by_service: Dict[str, int] = defaultdict(int)
        self.total_fallbacks = 0

    def record_fallback(self, event: FallbackEvent) -> None:
        """Record a fallback event with comprehensive metrics."""
        self.events.append(event)
        self.counts_by_reason[event.reason] += 1
        self.counts_by_service[event.service_type] += 1
        self.total_fallbacks += 1

        logger.warning(
            f"TypedDI fallback recorded: {event.service_type} "
            f"(qualifier={event.qualifier}, key={event.derived_key}, "
            f"reason={event.reason.value})"
        )

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        return {
            "total_fallbacks": self.total_fallbacks,
            "counts_by_reason": {
                reason.value: count for reason, count in self.counts_by_reason.items()
            },
            "counts_by_service": dict(self.counts_by_service),
            "recent_events": [
                asdict(event) for event in self.events[-10:]
            ],  # Last 10 events
        }


class CriticalServiceRegistry:
    """Registry for critical services that require special fallback handling."""

    def __init__(self):
        # Start with whitelist of critical services as specified
        # Include all services that the smoke check validates
        self.critical_services: Set[str] = {
            "SecretsManager",
            "SlackConfig",
            "SlackPostingHandler",
            "SlackAsyncClient",
            "UserVerifier",
            "MetricsStorage",
        }
        self.type_to_string_mapping: Dict[Type, str] = {}
        self.string_to_type_mapping: Dict[str, Type] = {}

    def register_critical_service(self, service_type: Type, string_key: str) -> None:
        """Register a critical service with its string mapping."""
        type_name = service_type.__name__
        self.critical_services.add(type_name)
        self.type_to_string_mapping[service_type] = string_key
        self.string_to_type_mapping[string_key] = service_type

        logger.info(f"Registered critical service: {type_name} -> {string_key}")

    def is_critical_service(self, service_type: Union[Type, str]) -> bool:
        """Check if a service is considered critical."""
        if isinstance(service_type, type):
            return service_type.__name__ in self.critical_services
        return service_type in self.critical_services

    def get_string_key(self, service_type: Type) -> Optional[str]:
        """Get string key for a service type (for legacy DI bridge)."""
        return self.type_to_string_mapping.get(service_type)

    def get_type_from_string(self, string_key: str) -> Optional[Type]:
        """Get type from string key (for legacy DI bridge)."""
        return self.string_to_type_mapping.get(string_key)


class GracefulFallbackManager:
    """
    Manages graceful fallback from TypedDI to Legacy DI system.

    Implements Phase 2 requirements:
    - Gate fallback with dedicated flag separate from main TypedDI flag
    - Log and metric every fallback (type, qualifier, derived key)
    - Start with whitelist of critical services
    - Maintain tested Type↔string mapping shared with the bridge

    Phase 1 enhancements:
    - Initialize legacy DI on first fallback if not already initialized
    - Emit single "legacy init performed" log to avoid noise; cache the state
    """

    def __init__(self, enable_fallback: bool = True):
        self.enable_fallback = enable_fallback  # Dedicated fallback flag
        self.metrics = FallbackMetrics()
        self.critical_registry = CriticalServiceRegistry()
        self.legacy_di_initialized = False  # Cache state for legacy DI initialization
        self.legacy_init_logged = False  # Avoid log noise
        self.health_status = {
            "fallback_enabled": enable_fallback,
            "system_healthy": True,
            "last_check": time.time(),
        }

        logger.info(
            f"GracefulFallbackManager initialized with fallback_enabled={enable_fallback}"
        )

    def should_fallback(
        self, service_type: Union[Type, str], qualifier: Optional[str] = None
    ) -> bool:
        """
        Determine if fallback should be triggered for a service.

        Considers:
        - Dedicated fallback flag
        - Critical service status
        - System health status
        """
        if not self.enable_fallback:
            logger.debug("Fallback disabled via dedicated flag")
            return False

        # Always allow fallback for critical services
        if self.critical_registry.is_critical_service(service_type):
            logger.debug(f"Allowing fallback for critical service: {service_type}")
            return True

        # Check system health for non-critical services
        if not self.health_status["system_healthy"]:
            logger.debug("System unhealthy, allowing fallback")
            return True

        return False

    def record_fallback_event(
        self,
        service_type: Union[Type, str],
        reason: FallbackReason,
        qualifier: Optional[str] = None,
        error_message: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> None:
        """Record a fallback event with comprehensive logging and metrics."""
        if isinstance(service_type, type):
            type_name = service_type.__name__
        else:
            type_name = service_type

        derived_key = self._generate_derived_key(type_name, qualifier)

        event = FallbackEvent(
            timestamp=time.time(),
            service_type=type_name,
            qualifier=qualifier,
            derived_key=derived_key,
            reason=reason,
            error_message=error_message,
            stack_trace=stack_trace,
        )

        self.metrics.record_fallback(event)

        # Log detailed fallback information
        logger.error(
            f"TypedDI → Legacy DI fallback: {type_name} "
            f"(qualifier='{qualifier}', key='{derived_key}', reason={reason.value})"
        )

        if error_message:
            logger.error(f"Fallback error: {error_message}")

        # Update health status based on fallback patterns
        self._update_health_status(event)

    def _generate_derived_key(self, type_name: str, qualifier: Optional[str]) -> str:
        """Generate a derived key for service identification."""
        if qualifier:
            return f"{type_name}:{qualifier}"
        return type_name

    def _update_health_status(self, event: FallbackEvent) -> None:
        """Update system health status based on fallback patterns."""
        # Mark system as unhealthy if too many fallbacks in short time
        recent_events = [
            e for e in self.metrics.events if time.time() - e.timestamp < 60
        ]  # Last minute

        if len(recent_events) > 10:  # More than 10 fallbacks per minute
            self.health_status["system_healthy"] = False
            logger.warning("System marked as unhealthy due to excessive fallbacks")

        self.health_status["last_check"] = time.time()

    def get_legacy_service_key(
        self, service_type: Type, qualifier: Optional[str] = None
    ) -> Optional[str]:
        """
        Get the legacy DI service key for a service type.

        Maintains tested Type↔string mapping shared with the bridge.
        """
        # First try the explicit mapping
        string_key = self.critical_registry.get_string_key(service_type)
        if string_key:
            return string_key

        # Fallback to type name (common pattern)
        type_name = service_type.__name__

        # Apply common transformations for legacy keys
        legacy_key = self._transform_to_legacy_key(type_name)

        logger.debug(f"Generated legacy key: {service_type} -> {legacy_key}")
        return legacy_key

    def _transform_to_legacy_key(self, type_name: str) -> str:
        """Transform a type name to legacy DI key format."""
        # Common transformations:
        # MyService -> my_service
        # ServiceHandler -> service_handler
        import re

        # Convert CamelCase to snake_case
        snake_case = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", type_name)
        snake_case = re.sub("([a-z0-9])([A-Z])", r"\1_\2", snake_case).lower()

        # Remove common suffixes
        snake_case = (
            snake_case.replace("_handler", "")
            .replace("_service", "")
            .replace("_manager", "")
        )

        return snake_case

    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status including metrics."""
        return {
            **self.health_status,
            "metrics": self.metrics.get_metrics_summary(),
            "critical_services": list(self.critical_registry.critical_services),
        }

    def reset_health_status(self) -> None:
        """Reset health status (for recovery scenarios)."""
        self.health_status["system_healthy"] = True
        self.health_status["last_check"] = time.time()
        logger.info("System health status reset")


# Global fallback manager instance
_fallback_manager: Optional[GracefulFallbackManager] = None


def get_fallback_manager(enable_fallback: bool = True) -> GracefulFallbackManager:
    """Get or create the global fallback manager."""
    global _fallback_manager

    if _fallback_manager is None:
        _fallback_manager = GracefulFallbackManager(enable_fallback)

    return _fallback_manager


def initialize_critical_service_mappings() -> None:
    """Initialize critical service mappings for the fallback system."""
    fallback_manager = get_fallback_manager()

    # Import and register critical services
    try:
        # Core services
        # DynamoDB services (Phase 1 requirement)
        from packages.core.local_metrics import MetricsStorage
        from packages.db.config.dynamodb_config import DynamoDBConfig
        from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
        from packages.db.dynamodb_store import DynamoDBStore
        from packages.secrets.manager import SecretsManager
        from packages.slack.authorisation.user_verification import UserVerifier
        from packages.slack.channel_operations.channel_archive_ops import (
            SlackChannelArchiveOps,
        )

        # Slack core operations services (Batch 1 additions)
        from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
        from packages.slack.channel_operations.channel_membership_ops import (
            ChannelMembershipOps,
        )
        from packages.slack.channel_operations.channel_msg_ops import (
            SlackChannelMessageOps,
        )
        from packages.slack.config.slack_config import SlackConfig
        from packages.slack.interactive_elements.channel_metadata_edit import (
            ChannelMetadataEditHandler,
        )

        # Batch 2: High-traffic handlers
        from packages.slack.interactive_elements.feedback_reactions import (
            FeedbackReactionsHandler,
        )
        from packages.slack.interactive_elements.feedback_report import (
            FeedbackReportHandler,
        )
        from packages.slack.interactive_elements.shortcuts import ShortcutHandler
        from packages.slack.messages.posting import SlackPostingHandler
        from packages.slack.user_operations.user_ops import SlackUserOps

        # Register core services
        fallback_manager.critical_registry.register_critical_service(
            SecretsManager, "secrets_manager"
        )
        fallback_manager.critical_registry.register_critical_service(
            SlackConfig, "slack_config"
        )
        fallback_manager.critical_registry.register_critical_service(
            SlackPostingHandler, "slack_posting"
        )

        # Register DynamoDB services with explicit mappings (Phase 1 requirement)
        fallback_manager.critical_registry.register_critical_service(
            DynamoDBConfig, "dynamodb_config"
        )
        fallback_manager.critical_registry.register_critical_service(
            DynamoDBAsyncClient, "dynamodb_async_client"
        )
        fallback_manager.critical_registry.register_critical_service(
            DynamoDBStore, "dynamodb_store"
        )

        # Register Slack core operations services (Batch 1 additions)
        fallback_manager.critical_registry.register_critical_service(
            ChannelInfoOps, "info_ops"
        )
        fallback_manager.critical_registry.register_critical_service(
            ChannelMembershipOps, "membership_ops"
        )
        fallback_manager.critical_registry.register_critical_service(
            SlackChannelMessageOps, "msg_ops"
        )
        fallback_manager.critical_registry.register_critical_service(
            SlackChannelArchiveOps, "archive_ops"
        )

        # Register Batch 2: High-traffic handlers
        fallback_manager.critical_registry.register_critical_service(
            MetricsStorage, "metrics"
        )
        fallback_manager.critical_registry.register_critical_service(
            SlackUserOps, "user_ops"
        )
        fallback_manager.critical_registry.register_critical_service(
            FeedbackReactionsHandler, "feedback_reactions_handler"
        )
        fallback_manager.critical_registry.register_critical_service(
            FeedbackReportHandler, "feedback_report_handler"
        )
        fallback_manager.critical_registry.register_critical_service(
            ChannelMetadataEditHandler, "channel_metadata_edit_handler"
        )
        fallback_manager.critical_registry.register_critical_service(
            ShortcutHandler, "shortcut_handler"
        )
        fallback_manager.critical_registry.register_critical_service(
            UserVerifier, "user_verifier"
        )

        logger.info(
            "Critical service mappings initialized successfully (including DynamoDB + Slack core operations services + Batch 2 high-traffic handlers)"
        )

    except ImportError as e:
        logger.warning(f"Failed to initialize some critical service mappings: {e}")
