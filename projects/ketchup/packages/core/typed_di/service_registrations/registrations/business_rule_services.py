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

from typing import TYPE_CHECKING

from packages.core.logging import setup_logger

# Essential imports for business rule services
try:
    from packages.core.business import (
        AuditService,
        ComplianceService,
        GovernanceService,
        PolicyValidationService,
        RuleEngineService,
    )
except ImportError:
    # Allow module to load even with missing imports for testing
    pass

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


def register_business_rule_services(manager: "ServiceRegistrationManager") -> None:
    """
    Register business rule services for rule engine, policy, compliance, audit, and governance.

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration

    Raises:
        RuntimeError: If any critical service registration fails
    """
    logger.info("Registering business rule services")

    _register_rule_engine_services(manager)
    _register_policy_services(manager)
    _register_compliance_services(manager)
    _register_audit_services(manager)
    _register_governance_services(manager)

    logger.info("Business rule services registered successfully (5 services)")


def _register_rule_engine_services(manager: "ServiceRegistrationManager") -> None:
    """Register rule engine services."""

    # RuleEngineService
    async def create_rule_engine_service(resolver) -> RuleEngineService:
        """Factory function for RuleEngineService using TypedResolver."""
        logger.info("Creating RuleEngineService instance via TypedDI")
        return RuleEngineService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=RuleEngineServiceProtocol,
        concrete_type=RuleEngineService,
        factory=create_rule_engine_service,
        dependencies=[],
        lifetime="singleton",
    )


def _register_policy_services(manager: "ServiceRegistrationManager") -> None:
    """Register policy validation services."""

    # PolicyValidationService
    async def create_policy_validation_service(resolver) -> PolicyValidationService:
        """Factory function for PolicyValidationService using TypedResolver."""
        logger.info("Creating PolicyValidationService instance via TypedDI")
        return PolicyValidationService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=PolicyValidationServiceProtocol,
        concrete_type=PolicyValidationService,
        factory=create_policy_validation_service,
        dependencies=[],
        lifetime="singleton",
    )


def _register_compliance_services(manager: "ServiceRegistrationManager") -> None:
    """Register compliance checking services."""

    # ComplianceService
    async def create_compliance_service(resolver) -> ComplianceService:
        """Factory function for ComplianceService using TypedResolver."""
        logger.info("Creating ComplianceService instance via TypedDI")
        return ComplianceService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=ComplianceServiceProtocol,
        concrete_type=ComplianceService,
        factory=create_compliance_service,
        dependencies=[],
        lifetime="singleton",
    )


def _register_audit_services(manager: "ServiceRegistrationManager") -> None:
    """Register audit and logging services."""

    # AuditService
    async def create_audit_service(resolver) -> AuditService:
        """Factory function for AuditService using TypedResolver."""
        logger.info("Creating AuditService instance via TypedDI")
        return AuditService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=AuditServiceProtocol,
        concrete_type=AuditService,
        factory=create_audit_service,
        dependencies=[],
        lifetime="singleton",
    )


def _register_governance_services(manager: "ServiceRegistrationManager") -> None:
    """Register governance and policy management services."""

    # GovernanceService
    async def create_governance_service(resolver) -> GovernanceService:
        """Factory function for GovernanceService using TypedResolver."""
        logger.info("Creating GovernanceService instance via TypedDI")
        return GovernanceService()

    manager.register_protocol_with_concrete_alias(
        protocol_type=GovernanceServiceProtocol,
        concrete_type=GovernanceService,
        factory=create_governance_service,
        dependencies=[],
        lifetime="singleton",
    )
