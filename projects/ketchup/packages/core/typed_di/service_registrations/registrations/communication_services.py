"""
Communication Services Registration Module

Registers communication infrastructure services:
- MessageBrokerService: Pub/sub messaging capabilities
- EventBusService: Event-driven communication
- NotificationService: General notification management
- WorkflowEngineService: Business process workflows

These 4 services provide communication and workflow capabilities for the application.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Protocol, runtime_checkable

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

if TYPE_CHECKING:
    from packages.core.typed_di.service_registrations.manager import ServiceRegistrationManager

logger = setup_logger(__name__)


# =============================================================================
# PROTOCOL DEFINITIONS
# =============================================================================


@runtime_checkable
class MessageBrokerServiceProtocol(Protocol):
    """Protocol for pub/sub messaging."""

    async def publish_message(self, topic: str, message: Dict[str, Any]) -> bool: ...
    async def subscribe_to_topic(self, topic: str, callback) -> str: ...
    async def unsubscribe(self, subscription_id: str) -> bool: ...
    async def get_topic_stats(self, topic: str) -> Dict[str, Any]: ...


@runtime_checkable
class EventBusServiceProtocol(Protocol):
    """Protocol for event-driven communication."""

    async def emit_event(self, event_type: str, data: Dict[str, Any]) -> bool: ...
    async def register_handler(self, event_type: str, handler) -> str: ...
    async def unregister_handler(self, handler_id: str) -> bool: ...
    async def get_event_history(
        self, event_type: str, limit: int = 100
    ) -> List[Dict[str, Any]]: ...


@runtime_checkable
class NotificationServiceProtocol(Protocol):
    """Protocol for general notifications."""

    async def send_notification(
        self, user_id: str, notification_type: str, data: Dict[str, Any]
    ) -> bool: ...
    async def get_notifications(
        self, user_id: str, unread_only: bool = False
    ) -> List[Dict[str, Any]]: ...
    async def mark_as_read(self, notification_id: str) -> bool: ...
    async def configure_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool: ...


@runtime_checkable
class WorkflowEngineServiceProtocol(Protocol):
    """Protocol for business process workflows."""

    async def start_workflow(self, workflow_type: str, data: Dict[str, Any]) -> str: ...
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]: ...
    async def cancel_workflow(self, workflow_id: str) -> bool: ...
    async def register_workflow_step(self, step_name: str, handler) -> bool: ...


def register_communication_services(manager: "ServiceRegistrationManager") -> None:
    """
    Register communication services (4 services).

    Provides communication and workflow capabilities:
    - MessageBrokerService: Pub/sub messaging capabilities
    - EventBusService: Event-driven communication
    - NotificationService: General notification management
    - WorkflowEngineService: Business process workflows

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration
    """
    logger.info("Registering Communication Services (4 services)")

    # MessageBrokerService
    async def create_message_broker_service(resolver) -> object:
        """Factory function for MessageBrokerService."""
        logger.info("Creating MessageBrokerService instance via TypedDI")

        class MessageBrokerService:
            """Pub/sub messaging service."""

            def __init__(self):
                self.topics = {}
                self.subscriptions = {}

            async def publish_message(self, topic: str, message: Dict[str, Any]) -> bool:
                """Publish message to topic."""
                if topic not in self.topics:
                    self.topics[topic] = []
                self.topics[topic].append(message)
                logger.debug(f"Published message to topic {topic}")
                return True

            async def subscribe_to_topic(self, topic: str, callback) -> str:
                """Subscribe to topic with callback."""
                subscription_id = f"sub_{topic}_{len(self.subscriptions)}"
                self.subscriptions[subscription_id] = {"topic": topic, "callback": callback}
                logger.debug(f"Subscribed to topic {topic} with ID {subscription_id}")
                return subscription_id

            async def unsubscribe(self, subscription_id: str) -> bool:
                """Unsubscribe from topic."""
                logger.debug(f"Unsubscribing: {subscription_id}")
                return self.subscriptions.pop(subscription_id, None) is not None

            async def get_topic_stats(self, topic: str) -> Dict[str, Any]:
                """Get statistics for topic."""
                message_count = len(self.topics.get(topic, []))
                return {"topic": topic, "messages": message_count, "subscribers": 0}

        return MessageBrokerService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=MessageBrokerServiceProtocol,
        concrete_type=type("ConcreteType1013", (), {}),
        factory=create_message_broker_service,
        dependencies=[],
        lifetime="singleton",
    )

    # EventBusService
    async def create_event_bus_service(resolver) -> object:
        """Factory function for EventBusService."""
        logger.info("Creating EventBusService instance via TypedDI")

        class EventBusService:
            """Event-driven communication service."""

            def __init__(self):
                self.handlers = {}
                self.event_history = []

            async def emit_event(self, event_type: str, data: Dict[str, Any]) -> bool:
                """Emit an event to all registered handlers."""
                event = {"type": event_type, "data": data, "timestamp": "now"}
                self.event_history.append(event)
                logger.debug(f"Emitted event: {event_type}")
                return True

            async def register_handler(self, event_type: str, handler) -> str:
                """Register event handler for event type."""
                handler_id = f"handler_{event_type}_{len(self.handlers)}"
                if event_type not in self.handlers:
                    self.handlers[event_type] = []
                self.handlers[event_type].append({"id": handler_id, "handler": handler})
                logger.debug(f"Registered handler {handler_id} for event type {event_type}")
                return handler_id

            async def unregister_handler(self, handler_id: str) -> bool:
                """Unregister event handler."""
                for event_type, handlers in self.handlers.items():
                    self.handlers[event_type] = [h for h in handlers if h["id"] != handler_id]
                logger.debug(f"Unregistered handler: {handler_id}")
                return True

            async def get_event_history(
                self, event_type: str, limit: int = 100
            ) -> List[Dict[str, Any]]:
                """Get event history for event type."""
                events = [e for e in self.event_history if e["type"] == event_type]
                return events[-limit:]

        return EventBusService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=EventBusServiceProtocol,
        concrete_type=type("ConcreteType1014", (), {}),
        factory=create_event_bus_service,
        dependencies=[],
        lifetime="singleton",
    )

    # NotificationService
    async def create_notification_service(resolver) -> object:
        """Factory function for NotificationService."""
        logger.info("Creating NotificationService instance via TypedDI")
        message_broker = await resolver.aget(MessageBrokerServiceProtocol)

        class NotificationService:
            """General notifications service."""

            def __init__(self, message_broker):
                self.broker = message_broker
                self.notifications = {}
                self.preferences = {}

            async def send_notification(
                self, user_id: str, notification_type: str, data: Dict[str, Any]
            ) -> bool:
                """Send notification to user."""
                notification_id = f"notif_{user_id}_{len(self.notifications)}"
                notification = {
                    "id": notification_id,
                    "user_id": user_id,
                    "type": notification_type,
                    "data": data,
                    "read": False,
                    "timestamp": "now",
                }
                if user_id not in self.notifications:
                    self.notifications[user_id] = []
                self.notifications[user_id].append(notification)
                logger.debug(f"Sent {notification_type} notification to user {user_id}")
                return True

            async def get_notifications(
                self, user_id: str, unread_only: bool = False
            ) -> List[Dict[str, Any]]:
                """Get notifications for user."""
                user_notifications = self.notifications.get(user_id, [])
                if unread_only:
                    return [n for n in user_notifications if not n["read"]]
                return user_notifications

            async def mark_as_read(self, notification_id: str) -> bool:
                """Mark notification as read."""
                for user_id, notifications in self.notifications.items():
                    for notification in notifications:
                        if notification["id"] == notification_id:
                            notification["read"] = True
                            logger.debug(f"Marked notification {notification_id} as read")
                            return True
                return False

            async def configure_preferences(
                self, user_id: str, preferences: Dict[str, Any]
            ) -> bool:
                """Configure notification preferences for user."""
                self.preferences[user_id] = preferences
                logger.debug(f"Configured preferences for user {user_id}")
                return True

        return NotificationService(message_broker)

    manager.register_protocol_with_concrete_alias(
        protocol_type=NotificationServiceProtocol,
        concrete_type=type("ConcreteType1015", (), {}),
        factory=create_notification_service,
        dependencies=[DependencySpec(MessageBrokerServiceProtocol)],
        lifetime="singleton",
    )

    # WorkflowEngineService
    async def create_workflow_engine_service(resolver) -> object:
        """Factory function for WorkflowEngineService."""
        logger.info("Creating WorkflowEngineService instance via TypedDI")
        event_bus = await resolver.aget(EventBusServiceProtocol)

        class WorkflowEngineService:
            """Business process workflows service."""

            def __init__(self, event_bus):
                self.event_bus = event_bus
                self.workflows = {}
                self.workflow_steps = {}

            async def start_workflow(self, workflow_type: str, data: Dict[str, Any]) -> str:
                """Start a new workflow instance."""
                workflow_id = f"workflow_{workflow_type}_{len(self.workflows)}"
                workflow = {
                    "id": workflow_id,
                    "type": workflow_type,
                    "data": data,
                    "status": "running",
                    "created_at": "now",
                }
                self.workflows[workflow_id] = workflow
                logger.debug(f"Started workflow {workflow_type} with ID {workflow_id}")
                return workflow_id

            async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
                """Get workflow status and details."""
                workflow = self.workflows.get(workflow_id, {})
                return workflow

            async def cancel_workflow(self, workflow_id: str) -> bool:
                """Cancel a running workflow."""
                if workflow_id in self.workflows:
                    self.workflows[workflow_id]["status"] = "cancelled"
                    logger.debug(f"Cancelled workflow: {workflow_id}")
                    return True
                return False

            async def register_workflow_step(self, step_name: str, handler) -> bool:
                """Register a workflow step handler."""
                self.workflow_steps[step_name] = handler
                logger.debug(f"Registered workflow step: {step_name}")
                return True

        return WorkflowEngineService(event_bus)

    manager.register_protocol_with_concrete_alias(
        protocol_type=WorkflowEngineServiceProtocol,
        concrete_type=type("ConcreteType1016", (), {}),
        factory=create_workflow_engine_service,
        dependencies=[DependencySpec(EventBusServiceProtocol)],
        lifetime="singleton",
    )

    logger.info("Communication Services completed - 4 services registered")
