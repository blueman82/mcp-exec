"""
Service Registration Auditing

Provides auditing and monitoring functionality for service registrations,
including domain breakdown analysis and CI auditing reports.
"""

import json
import os
from datetime import datetime

from packages.core.logging import setup_logger

from .manager import ServiceRegistrationManager

logger = setup_logger(__name__)

# Domain categorization patterns for service classification
DOMAIN_PATTERNS = {
    "core_infrastructure": [
        "secretsmanager",
        "slackconfig",
        "distributedlock",
        "sqsclient",
        "backoff",
        "typedresolver",
        "compatibilitybridge",
    ],
    "db_operations": [
        "dynamodb",
        "userstore",
        "channeloperations",
        "commandtrackingoperations",
        "accessrequestoperations",
    ],
    "slack_commands": ["slackarchivecommand", "featurecommand", "featureservice"],
    "slack_interactive": [
        "handler",
        "hometab",
        "usageexport",
        "blockkit",
        "slackposting",
        "feedback",
        "shortcut",
        "trustendorsement",
    ],
    "integrations": ["ims", "jira", "mcp", "tokenmanager", "cache", "dataextractor"],
    "ai_ui_metrics": [
        "openai",
        "userjoin",
        "flagreview",
        "messageformatter",
        "metrics",
        "csv",
        "channelname",
        "userverifier",
        "tokentracker",
    ],
}


def _categorize_service(service_name: str) -> str:
    """Categorize a single service based on naming patterns."""
    service_lower = service_name.lower()

    for domain, patterns in DOMAIN_PATTERNS.items():
        if any(pattern in service_lower for pattern in patterns):
            return domain

    # Default remaining services to slack_interactive
    return "slack_interactive"


def emit_registered_services_summary(
    manager: ServiceRegistrationManager, service_count: int
) -> None:
    """Emit registered services summary JSON for CI auditing and monitoring."""
    try:
        # Get domain-specific counts
        domain_breakdown = get_domain_breakdown(manager)

        # Create summary data structure
        # NOTE: Batch 1-5 represent the initial TypedDI migration
        # (84 services total: 6+4+7+7+13+40)
        # Batch 6 is a catch-all for all services registered after
        # the initial migration
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_services": int(service_count),
            "batch_breakdown": {
                "essential_services": 6,
                "batch_1_slack_core": 4,
                "batch_2_handlers": 7,
                "batch_3_ai_operational": 7,
                "batch_4_integration": 13,
                "batch_5_additional": 40,
                # All services beyond initial 84
                "batch_6_post_migration_services": int(service_count) - 84,
            },
            "domain_breakdown": domain_breakdown,
            "services": get_service_list(manager),
            "protocols_coverage": get_protocols_coverage(manager),
            "qualifiers_implemented": ["primary"],
            "registry_status": "frozen",
            "version": "batch_5_hardening",
        }

        # Write to analysis directory for CI consumption
        output_path = os.path.join("analysis", "registered_services_summary.json")
        os.makedirs("analysis", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Runtime services summary emitted to {output_path} for CI auditing")

    except Exception as e:
        logger.warning(f"Failed to emit registered services summary: {e}")


def get_domain_breakdown(manager: ServiceRegistrationManager) -> dict:
    """Get domain-specific service counts for audit tracking."""
    try:
        services = get_service_list(manager)

        # Initialize domain collections
        domains = {domain: [] for domain in DOMAIN_PATTERNS}

        # Categorize each service
        for service in services:
            domain = _categorize_service(service)
            domains[domain].append(service)

        # Return counts for each domain
        return {
            **{domain: len(service_list) for domain, service_list in domains.items()},
            "total_categorized": sum(len(service_list) for service_list in domains.values()),
        }

    except Exception as e:
        logger.warning(f"Failed to generate domain breakdown: {e}")
        return {"error": "Failed to categorize services by domain"}


def get_service_list(manager: ServiceRegistrationManager) -> list:
    """Extract service list from registration manager."""
    try:
        summary = manager.get_registration_summary()
        services = summary.get("services", {})
        return list(services.keys())
    except Exception:
        return []


def get_protocols_coverage(manager: ServiceRegistrationManager) -> dict:
    """Extract protocol coverage information."""
    try:
        summary = manager.get_registration_summary()
        services = summary.get("services", {})

        # We don't currently store has_protocol_alias in the summary; approximate by protocol mapping size
        total_services = len(services)
        # Use protocol_to_concrete_mapping to get accurate protocol coverage
        protocols_with_concrete = len(getattr(manager, "protocol_to_concrete_mapping", {}))

        return {
            "total_services": total_services,
            "services_with_protocols": protocols_with_concrete,
            "protocol_coverage_percentage": (
                round((protocols_with_concrete / total_services * 100), 1)
                if total_services > 0
                else 0
            ),
        }
    except Exception:
        return {
            "total_services": 0,
            "services_with_protocols": 0,
            "protocol_coverage_percentage": 0,
        }
