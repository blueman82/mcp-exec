"""
Business Rule Services Registration Module

Registers business rule services including rule engines, policy validation,
compliance checking, auditing, and governance services:
- Rule engine for business rule evaluation
- Policy validation and requirement checking
- Compliance status checking and monitoring
- Audit event logging and trail management
- Governance rule application and policy management

These services provide comprehensive business rule and governance functionality.
All registrations use protocol-first pattern with concrete class aliasing.
"""

from typing import TYPE_CHECKING, List

from packages.core.logging import setup_logger
from packages.core.typed_di.service_spec import ServiceSpec, register_from_specs

# Essential imports for business rule services
from packages.core.business import (
    AuditService,
    ComplianceService,
    GovernanceService,
    PolicyValidationService,
    RuleEngineService,
)

# Protocol imports
if TYPE_CHECKING:
    from ..manager import ServiceRegistrationManager

from ..protocols import (
    AuditServiceProtocol,
    ComplianceServiceProtocol,
    GovernanceServiceProtocol,
    PolicyValidationServiceProtocol,
    RuleEngineServiceProtocol,
)

logger = setup_logger(__name__)


# =============================================================================
# ServiceSpec Declarations (declarative registration - minimal boilerplate)
# =============================================================================


def _get_business_rule_specs() -> List[ServiceSpec]:
    """Return specs for all business rule services (all have no dependencies)."""
    return [
        ServiceSpec(
            protocol=RuleEngineServiceProtocol,
            concrete=RuleEngineService,
            deps={},
        ),
        ServiceSpec(
            protocol=PolicyValidationServiceProtocol,
            concrete=PolicyValidationService,
            deps={},
        ),
        ServiceSpec(
            protocol=ComplianceServiceProtocol,
            concrete=ComplianceService,
            deps={},
        ),
        ServiceSpec(
            protocol=AuditServiceProtocol,
            concrete=AuditService,
            deps={},
        ),
        ServiceSpec(
            protocol=GovernanceServiceProtocol,
            concrete=GovernanceService,
            deps={},
        ),
    ]


# =============================================================================
# Main Registration Entry Point
# =============================================================================


def register_business_rule_services(manager: "ServiceRegistrationManager") -> None:
    """
    Register business rule services for rule engine, policy, compliance, audit, and governance.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any critical service registration fails
    """
    logger.info("Registering business rule services")

    register_from_specs(manager, _get_business_rule_specs(), "business_rules")

    logger.info("Business rule services registered successfully (5 services)")
