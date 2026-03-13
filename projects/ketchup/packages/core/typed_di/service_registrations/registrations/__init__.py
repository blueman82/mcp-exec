"""
Registrations Package

Focused service registration modules organized by domain for maintainability.
Each module contains ≤400 lines and handles a specific domain of services.

Supports role-based registration via register_for_role() so each container
only registers the services it actually needs.
"""

from __future__ import annotations

from collections.abc import Callable

from packages.core.logging import setup_logger

# Import all registration functions from focused modules
from .agent_services import register_agent_services, register_chromadb_services
from .ai_operational import register_ai_operational
from .command_processing import register_command_processing
from .core_infrastructure import register_core_infrastructure
from .core_primitives import register_core_primitives

# CSOPM notifier services (4 services) - state tracking, JIRA polling, Slack notifications, reminders
from .csopm_services import register_csopm_services
from .event_processing import register_event_processing
from .integrations import register_integrations

# Maintenance detection services (3 services) - Raven client, maintenance checker, JIRA prompt handler
from .maintenance_registrations import register_maintenance_services
from .slack_core import register_slack_core
from .slack_handlers import register_slack_handlers
from .ui_services import register_ui_services

logger = setup_logger(__name__)

__all__ = [
    "register_core_primitives",
    "register_core_infrastructure",
    "register_slack_core",
    "register_slack_handlers",
    "register_ai_operational",
    "register_integrations",
    "register_command_processing",
    "register_event_processing",
    "register_ui_services",
    "register_maintenance_services",
    "register_csopm_services",
    "register_chromadb_services",
    "register_agent_services",
    "register_all_focused_services",
    "register_for_role",
]

# ---------------------------------------------------------------------------
# Role-to-module mapping
#
# Each role maps to the registration functions needed by that container.
# Derived from tracing every aget() call in each container's code, plus
# transitive dependencies between registration modules.
#
# Key dependencies that informed this mapping:
#   - SCHEDULER needs command_processing for FeatureServiceProtocol
#   - SCHEDULER needs slack_handlers because integrations → HomeTabHandler
#     → FeedbackReportHandler (from slack_handlers)
#   - ACCESS_MONITOR needs core_infrastructure for DistributedLock,
#     AccessRequestOperations
# ---------------------------------------------------------------------------

_ROLE_MODULES: dict[str, list[Callable]] = {
    # APP: all modules (same as register_all_focused_services)
    "app": [
        register_core_primitives,
        register_core_infrastructure,
        register_slack_core,
        register_slack_handlers,
        register_ai_operational,
        register_integrations,
        register_command_processing,
        register_event_processing,
        register_ui_services,
        register_maintenance_services,
        register_csopm_services,
        register_agent_services,
    ],
    # SCHEDULER: drops event_processing, ui_services
    # Includes csopm_services because command_processing → MetricsDataCollector
    # → CSOPMStateTrackerProtocol (non-optional)
    "scheduler": [
        register_core_primitives,
        register_core_infrastructure,
        register_slack_core,
        register_slack_handlers,
        register_ai_operational,
        register_integrations,
        register_command_processing,
        register_maintenance_services,
        register_csopm_services,
        register_agent_services,
    ],
    # CSOPM_NOTIFIER: core + slack_core + slack_handlers + ai_operational + integrations + csopm
    # Includes slack_handlers because integrations → HomeTabHandler
    # → FeedbackReportHandler (non-optional, from slack_handlers)
    # Includes ai_operational because slack_core → UserJoinNotificationService
    # → OpenAIHandlerProtocol (non-optional, from ai_operational)
    "csopm": [
        register_core_primitives,
        register_core_infrastructure,
        register_slack_core,
        register_slack_handlers,
        register_ai_operational,
        register_integrations,
        register_csopm_services,
    ],
    # ACCESS_MONITOR: core_primitives + core_infrastructure only
    "access": [
        register_core_primitives,
        register_core_infrastructure,
    ],
}


def register_for_role(role_value: str, manager: object) -> None:
    """
    Register only the services needed for the given container role.

    Args:
        role_value: The ContainerRole.value string (e.g. "app", "scheduler")
        manager: ServiceRegistrationManager instance
    """
    modules = _ROLE_MODULES.get(role_value)
    if modules is None:
        raise ValueError(
            f"Unknown container role: {role_value!r}. " f"Valid roles: {list(_ROLE_MODULES.keys())}"
        )

    logger.info(
        "Registering services for role=%s (%d modules)",
        role_value,
        len(modules),
    )

    for register_fn in modules:
        register_fn(manager)


def register_all_focused_services(manager: object) -> None:
    """
    Register all services using focused modules.

    Orchestrates service registration across all focused modules,
    maintaining the exact same registration behavior as the original.

    Args:
        manager: ServiceRegistrationManager instance
    """
    # Core primitives - fundamental services (secrets, config, DB trio)
    register_core_primitives(manager)

    # Core infrastructure - SQS and other infra singletons
    register_core_infrastructure(manager)

    # Slack core operations - channel info/membership/archive/message ops
    register_slack_core(manager)

    # Slack handlers - Feedback*, metadata editor, shortcuts, verifier
    register_slack_handlers(manager)

    # AI operational - TokenTracker, OpenAI handler, Slack bot helpers
    register_ai_operational(manager)

    # Integration services - JIRA, MCP, external APIs
    register_integrations(manager)

    # Command processing - user command handlers and routing
    register_command_processing(manager)

    # Event processing - Slack events and channel lifecycle
    register_event_processing(manager)

    # UI services - BlockKit builders, modal handlers, and UI interactions
    register_ui_services(manager)

    # Maintenance detection services (3 services) - Raven client, maintenance checker, JIRA prompt handler
    register_maintenance_services(manager)

    # CSOPM notifier services (4 services) - state tracking, JIRA polling, Slack notifications, reminders
    register_csopm_services(manager)

    # ChromaDB foundation + Agent services
    # ChromaDB (4 services): embeddings, vector store, conversation store, realtime ingestor
    # Agent (8 services): retriever, context builder, thread manager, filter, JIRA backfill, backfill ingestor, engine, handler
    # Gated by KETCHUP_CHROMADB_ENABLED and KETCHUP_AGENT_ENABLED feature flags
    register_agent_services(manager)
