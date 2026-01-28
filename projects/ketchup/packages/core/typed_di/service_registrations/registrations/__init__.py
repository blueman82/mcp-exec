"""
Registrations Package

Focused service registration modules organized by domain for maintainability.
Each module contains ≤400 lines and handles a specific domain of services.
"""

# Import all registration functions from focused modules
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
    # Maintenance detection services (3 services)
    "register_maintenance_services",
    # CSOPM notifier services (4 services)
    "register_csopm_services",
]


def register_all_focused_services(manager) -> None:
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
