"""
Registrations Package

Focused service registration modules organized by domain for maintainability.
Each module contains ≤400 lines and handles a specific domain of services.
"""

# Import all registration functions from focused modules
from .advanced_infrastructure import register_advanced_infrastructure
from .ai_enhancements import register_ai_enhancements
from .ai_operational import register_ai_operational

# Archive processing services (5 services) - archive processor, validation, reporting, analytics, cleanup
from .archive_processing import register_archive_processing_services

# Core infrastructure extensions (16 services) - modular breakdown
from .basic_infrastructure import register_basic_infrastructure

from .caching_storage import register_caching_storage

# Channel management services (5 services) - business logic
from .channel_management import register_channel_management
from .command_processing import register_command_processing
from .communication_services import register_communication_services
from .core_infrastructure import register_core_infrastructure
from .core_primitives import register_core_primitives

# Missing modules for service expansion (3 functional modules)
from .cross_component_integration import register_cross_component_integration

# CSOPM notifier services (4 services) - state tracking, JIRA polling, Slack notifications, reminders
from .csopm_services import register_csopm_services
from .database_batches import register_database_batches
from .event_processing import register_event_processing
from .external_api_services import register_external_api_services
from .integration_management import register_integration_management
from .integrations import register_integrations
from .jira_services import register_jira_services

# Maintenance detection services (3 services) - Raven client, maintenance checker, JIRA prompt handler
from .maintenance_registrations import register_maintenance_services
from .security_monitoring import register_security_monitoring
from .slack_core import register_slack_core
from .slack_handlers import register_slack_handlers
from .ui_services import register_ui_services

# Workflow management services (5 services) - workflow engine, task management, process automation, state management, transitions
from .workflow_management import register_workflow_management_services

__all__ = [
    "register_core_primitives",
    "register_core_infrastructure",
    "register_slack_core",
    "register_slack_handlers",
    "register_ai_operational",
    "register_integrations",
    "register_database_batches",
    "register_ai_enhancements",
    "register_command_processing",
    "register_event_processing",
    "register_ui_services",
    "register_advanced_infrastructure",
    "register_integration_management",
    # Core infrastructure extensions (16 services)
    "register_basic_infrastructure",
    "register_caching_storage",
    "register_security_monitoring",
    "register_communication_services",
    # Channel management services (5 services)
    "register_channel_management",
    # Workflow management services (5 services)
    "register_workflow_management_services",
    # Archive processing services (5 services)
    "register_archive_processing_services",
    # Missing module functions (3 functional modules)
    "register_cross_component_integration",
    "register_external_api_services",
    "register_jira_services",
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

    # Database batch operations - batch operations and DB utilities
    register_database_batches(manager)

    # AI enhancements - additional AI and ML services
    register_ai_enhancements(manager)

    # Command processing - user command handlers and routing
    register_command_processing(manager)

    # Event processing - Slack events and channel lifecycle
    register_event_processing(manager)

    # UI services - BlockKit builders, modal handlers, and UI interactions
    register_ui_services(manager)

    # Advanced infrastructure - JIRA, MCP, API gateway services (185-195)
    register_advanced_infrastructure(manager)

    # Integration management - data sync, monitoring, management services (196-204)
    register_integration_management(manager)

    # Core infrastructure extensions (16 additional services)
    register_basic_infrastructure(manager)
    register_caching_storage(manager)
    register_security_monitoring(manager)
    register_communication_services(manager)

    # Channel management services (5 business logic services)
    register_channel_management(manager)

    # Workflow management services (5 workflow services)
    register_workflow_management_services(manager)

    # Archive processing services (5 archive services)
    register_archive_processing_services(manager)

    # Cross-component integration services (5 services) - Services 205-209
    register_cross_component_integration(manager)

    # External API services (5 services) - API gateway, webhooks, callbacks
    register_external_api_services(manager)

    # JIRA services (5 services) - Core JIRA, tickets, workflow, reporting, analytics
    register_jira_services(manager)

    # Maintenance detection services (3 services) - Raven client, maintenance checker, JIRA prompt handler
    register_maintenance_services(manager)

    # CSOPM notifier services (4 services) - state tracking, JIRA polling, Slack notifications, reminders
    register_csopm_services(manager)
